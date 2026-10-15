using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Threading;
using Interop.UIAutomationClient;
using Researchly.Overlay.Core.Eligibility;
using Researchly.Overlay.Core.Placement;
using Researchly.Overlay.Core.Session;
using Researchly.Overlay.Core.Text;
using Researchly.Overlay.Core.WriteBack;
using Researchly.Overlay.Native;

namespace Researchly.Overlay.Capture;

/// <summary>A focused element, described before any of its text is read.</summary>
internal sealed record FieldCandidate(long Token, FieldDescriptor Descriptor, int ProcessId);

/// <summary>The field's text (in memory only), read after the gate said yes.</summary>
internal sealed record TextRead(long Token, long Seq, string Text, int? Caret, bool VisibleOnly, bool HasGeometry);

/// <summary>Screen rectangles (physical pixels), one per line of a suggestion's range.</summary>
internal sealed record LineRects(string Id, IReadOnlyList<Box> Rects);

internal sealed record Measurement(long Token, long Seq, Box Field, IReadOnlyList<LineRects> Items);

internal enum WriteResultKind { Applied, Stale, NotForeground, KeysHeld, Failed, Unexpected }

internal sealed record WriteResult(WriteResultKind Kind, WriteBackMethod? Method)
{
    public string Message => Kind switch
    {
        WriteResultKind.Applied => "Changed.",
        WriteResultKind.Stale => "The text changed since this was checked. Nothing was changed.",
        WriteResultKind.NotForeground => "The app is no longer in front. Nothing was changed.",
        WriteResultKind.KeysHeld => "A key is held down. Release it and try again.",
        WriteResultKind.Unexpected => "The app changed the text differently than expected. Check it, and use undo in the app if needed.",
        _ => "This app did not accept the change. Nothing was changed.",
    };
}

/// <summary>What the controller asks to write back.</summary>
internal sealed record WriteRequest(long Token, PlacedSuggestion Suggestion, string Replacement, string ParagraphText, int ParagraphStart);

/// <summary>
/// The UI Automation side of the client (docs/inline-review-design.md section 6,
/// steps 1, 5 and 8): follows keyboard focus, describes the focused element for
/// the gate, reads the text of an eligible field (events plus polling), measures
/// line rectangles for ranges, and writes accepted revisions back. Every call
/// runs on <see cref="UiaWorker"/>; results come back on the UI thread.
/// Text is kept only in memory, for the attached field.
/// </summary>
internal sealed class FieldWatcher : IDisposable
{
    private const int MaxVisibleChars = 60_000;
    private const int MaxAncestors = 10;
    private const int MaxMeasured = 120;

    private sealed class Field
    {
        public long Token;
        public IUIAutomationElement Element = null!;
        public int Pid;
        public FieldDescriptor Descriptor = new();
        public IUIAutomationTextPattern? Text;
        public IUIAutomationTextPattern2? Text2;
        public IUIAutomationValuePattern? Value;
        // Attached state
        public AppRule? Rule;
        public bool VisibleMode;
        public IUIAutomationTextRange? Root;
        public long Seq;
        public string LastText = "";
        public int? LastCaret;
        public readonly Dictionary<string, IUIAutomationTextRange> RangeCache = new(StringComparer.Ordinal);
        public AutomationEventHandler? TextHandler;
        public PropertyChangedHandler? ValueHandler;
        public Timer? Poll;
        public int ReadQueued;
    }

    private readonly UiaWorker _worker = new();
    private readonly Dispatcher _ui;
    private readonly int _ownPid = Environment.ProcessId;
    private IUIAutomation? _automation;
    private FocusChangedHandler? _focusHandler;
    private Field? _candidate;   // worker thread only
    private Field? _attached;    // worker thread only
    private long _tokens;
    private IUIAutomationElement? _pendingFocus;
    private int _focusQueued;

    private readonly Func<string, AppRule> _ruleFor;

    /// <param name="ui">The UI thread's dispatcher; results are raised there.</param>
    /// <param name="ruleFor">The app rule for a process name (immutable data; safe to call from the worker).</param>
    public FieldWatcher(Dispatcher ui, Func<string, AppRule> ruleFor)
    {
        _ui = ui;
        _ruleFor = ruleFor;
    }

    /// <summary>Focus moved. Null when nothing usable has focus. Raised on the UI thread.</summary>
    public event Action<FieldCandidate?>? FocusChanged;

    /// <summary>The attached field's text was read and differs from the last read. Raised on the UI thread.</summary>
    public event Action<TextRead>? TextRead;

    public void Start() => _worker.Post(() =>
    {
        _automation = new CUIAutomation8();
        if (_automation is IUIAutomation2 a2)
        {
            a2.AutoSetFocus = 0;          // never let UI Automation move focus
            a2.TransactionTimeout = 2000; // a hung app must not hang the client
            a2.ConnectionTimeout = 2000;
        }
        _focusHandler = new FocusChangedHandler(OnFocusEvent);
        _automation.AddFocusChangedEventHandler(null, _focusHandler);
        var focused = Safe(() => _automation.GetFocusedElement(), null);
        if (focused != null) HandleFocus(focused);
    });

    /// <summary>The gate said yes: start reading this field.</summary>
    public void Attach(long token, AppRule rule) => _worker.Post(() =>
    {
        var f = _candidate;
        if (f == null || f.Token != token) return;
        DetachInternal();
        f.Rule = rule;
        f.VisibleMode = rule.TextSource == TextSource.Visible && f.Text != null;
        _attached = f;
        Subscribe(f);
        int interval = rule.PollingNeeded ? rule.PollIntervalMs : 2000;
        f.Poll = new Timer(_ => QueueRead(f), null, interval, interval);
        ReadAndPost(f, force: true);
    });

    /// <summary>Stop reading the field (the gate said no, the writer paused, or focus left).</summary>
    public void Detach() => _worker.Post(DetachInternal);

    /// <summary>Read the attached field now (for example after a write-back).</summary>
    public void RequestRead() => _worker.Post(() =>
    {
        if (_attached != null) ReadAndPost(_attached, force: false);
    });

    /// <summary>Re-describe the focused element (after a pause ends or settings change).</summary>
    public void Refresh() => _worker.Post(() =>
    {
        if (_automation == null) return;
        var focused = Safe(() => _automation.GetFocusedElement(), null);
        _candidate = null;
        if (focused != null) HandleFocus(focused);
        else Raise(null);
    });

    /// <summary>Line rectangles for each suggestion, in physical screen pixels, clipped to the field.</summary>
    public Task<Measurement?> MeasureAsync(long token, long seq, IReadOnlyList<PlacedSuggestion> items) => _worker.Run<Measurement?>(() =>
    {
        var f = _attached;
        if (f == null || f.Token != token || f.Seq != seq || f.Root == null) return null;
        var bounds = f.Element.CurrentBoundingRectangle;
        var field = new Box(bounds.left, bounds.top, bounds.right - bounds.left, bounds.bottom - bounds.top);
        var result = new List<LineRects>();
        int count = 0;
        foreach (var s in items)
        {
            if (++count > MaxMeasured) break;
            try
            {
                if (!f.RangeCache.TryGetValue(s.Id, out var range))
                {
                    range = Locate(f.Root, f.LastText, s.Range, s.FlaggedText);
                    if (range == null) continue;
                    f.RangeCache[s.Id] = range;
                }
                var rects = range.GetBoundingRectangles();
                var lines = new List<Box>();
                if (rects != null)
                {
                    for (int i = 0; i + 3 < rects.Length; i += 4)
                    {
                        var line = new Box(rects[i], rects[i + 1], rects[i + 2], rects[i + 3]).Intersect(field);
                        if (!line.IsEmpty) lines.Add(line);
                    }
                }
                if (lines.Count > 0) result.Add(new LineRects(s.Id, lines));
            }
            catch (COMException)
            {
                f.RangeCache.Remove(s.Id);
            }
        }
        return new Measurement(token, seq, field, result);
    });

    /// <summary>The field's bounds (physical pixels), or null.</summary>
    public Task<Box?> FieldBoundsAsync(long token) => _worker.Run<Box?>(() =>
    {
        var f = _attached ?? _candidate;
        if (f == null || f.Token != token) return null;
        var b = f.Element.CurrentBoundingRectangle;
        return new Box(b.left, b.top, b.right - b.left, b.bottom - b.top);
    });

    /// <summary>Writes an accepted revision back, trying the app rule's methods in order.</summary>
    public Task<WriteResult> WriteBackAsync(WriteRequest request) => _worker.Run(() => WriteBack(request));

    // ---- focus ----------------------------------------------------------

    private void OnFocusEvent(IUIAutomationElement sender)
    {
        // Called on a UI Automation thread: hand the latest element to the worker.
        Interlocked.Exchange(ref _pendingFocus, sender);
        if (Interlocked.Exchange(ref _focusQueued, 1) == 0)
            _worker.Post(DrainFocus);
    }

    private void DrainFocus()
    {
        Interlocked.Exchange(ref _focusQueued, 0);
        var element = Interlocked.Exchange(ref _pendingFocus, null);
        if (element != null) HandleFocus(element);
    }

    private void HandleFocus(IUIAutomationElement element)
    {
        if (_automation == null) return;
        int pid = Safe(() => element.CurrentProcessId, 0);
        if (pid == 0 || pid == _ownPid) return; // our own windows never take focus; ignore them
        if (_candidate != null && Safe(() => _automation.CompareElements(element, _candidate.Element) != 0, false))
            return;

        DetachInternal();
        var f = Describe(element, pid);
        _candidate = f;
        Raise(new FieldCandidate(f.Token, f.Descriptor, pid));
    }

    private Field Describe(IUIAutomationElement e, int pid)
    {
        var f = new Field { Token = Interlocked.Increment(ref _tokens), Element = e, Pid = pid };
        string process = "";
        try
        {
            using var p = Process.GetProcessById(pid);
            process = p.ProcessName + ".exe";
        }
        catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or System.ComponentModel.Win32Exception) { }

        int controlType = Safe(() => e.CurrentControlType, 0);
        bool password = Safe(() => e.CurrentIsPassword != 0, false);
        bool focusable = Safe(() => e.CurrentIsKeyboardFocusable != 0, true);

        // TextPattern2 (caret) where the host offers it; TextPattern for reading and geometry.
        f.Text = Safe(() => e.GetCurrentPattern(UIA_PatternIds.UIA_TextPatternId) as IUIAutomationTextPattern, null);
        f.Text2 = Safe(() => e.GetCurrentPattern(UIA_PatternIds.UIA_TextPattern2Id) as IUIAutomationTextPattern2, null);
        f.Value = Safe(() => e.GetCurrentPattern(UIA_PatternIds.UIA_ValuePatternId) as IUIAutomationValuePattern, null);

        bool textEdit = Safe(() => e.GetCurrentPropertyValue(UIA_PropertyIds.UIA_IsTextEditPatternAvailablePropertyId) is bool b && b, false);
        bool? readOnly = null;
        if (f.Value != null) readOnly = Safe<bool?>(() => f.Value.CurrentIsReadOnly != 0, null);
        if (readOnly == null && f.Text != null)
            readOnly = Safe<bool?>(() => f.Text.DocumentRange.GetAttributeValue(UIA_TextAttributeIds.UIA_IsReadOnlyAttributeId) is bool b ? b : null, null);

        // An edit box counts unless the host says it is read-only. Anything else (a
        // document, a rich-text group) needs positive evidence that it is editable, so a
        // web page's own text is never read as if the writer had typed it.
        bool isEdit = controlType == UIA_ControlTypeIds.UIA_EditControlTypeId;
        bool trustedDocument = controlType == UIA_ControlTypeIds.UIA_DocumentControlTypeId && _ruleFor(process).EditableDocuments;
        bool editLike = isEdit ? readOnly != true : (readOnly == false || textEdit || trustedDocument);
        bool isTextField = focusable && editLike && (f.Text != null || f.Value != null);

        string? labeledBy = Safe(() => e.CurrentLabeledBy?.CurrentName, null);
        string? fullDescription = Safe(() => e.GetCurrentPropertyValue(UIA_PropertyIds.UIA_FullDescriptionPropertyId) as string, null);

        f.Descriptor = new FieldDescriptor
        {
            ProcessName = process,
            IsPassword = password,
            IsReadOnly = readOnly == true,
            IsTextField = isTextField,
            Name = Safe(() => e.CurrentName, null),
            AutomationId = Safe(() => e.CurrentAutomationId, null),
            HelpText = Safe(() => e.CurrentHelpText, null),
            Placeholder = fullDescription,
            LabeledByName = labeledBy,
            AriaRole = Safe(() => e.CurrentAriaRole, null),
            FormNames = FormAncestors(e),
            TextLength = null, // never read text before the gate says yes
        };
        return f;
    }

    /// <summary>Names of enclosing web forms and search regions, nearest first.</summary>
    private IReadOnlyList<string> FormAncestors(IUIAutomationElement e)
    {
        var names = new List<string>();
        if (_automation == null) return names;
        var walker = Safe(() => _automation.ControlViewWalker, null);
        if (walker == null) return names;
        var current = e;
        for (int i = 0; i < MaxAncestors; i++)
        {
            current = Safe(() => walker.GetParentElement(current), null);
            if (current == null) break;
            var node = current;
            string? role = Safe(() => node.CurrentAriaRole, null);
            int landmark = Safe(() => node.GetCurrentPropertyValue(UIA_PropertyIds.UIA_LandmarkTypePropertyId) is int l ? l : 0, 0);
            bool form = string.Equals(role, "form", StringComparison.OrdinalIgnoreCase) || landmark == UIA_LandmarkTypeIds.UIA_FormLandmarkTypeId;
            bool search = string.Equals(role, "search", StringComparison.OrdinalIgnoreCase) || landmark == UIA_LandmarkTypeIds.UIA_SearchLandmarkTypeId;
            if (search) names.Add("search");
            if (form || search)
            {
                string? name = Safe(() => node.CurrentName, null);
                if (!string.IsNullOrWhiteSpace(name)) names.Add(name);
            }
        }
        return names;
    }

    // ---- reading --------------------------------------------------------

    private void Subscribe(Field f)
    {
        if (_automation == null) return;
        if (f.Text != null)
        {
            f.TextHandler = new AutomationEventHandler(_ => QueueRead(f));
            Safe(() =>
            {
                _automation.AddAutomationEventHandler(UIA_EventIds.UIA_Text_TextChangedEventId, f.Element, TreeScope.TreeScope_Element, null, f.TextHandler);
                return true;
            }, false);
        }
        if (f.Value != null)
        {
            f.ValueHandler = new PropertyChangedHandler(_ => QueueRead(f));
            Safe(() =>
            {
                _automation.AddPropertyChangedEventHandler(f.Element, TreeScope.TreeScope_Element, null, f.ValueHandler,
                    new[] { UIA_PropertyIds.UIA_ValueValuePropertyId });
                return true;
            }, false);
        }
    }

    private void DetachInternal()
    {
        var f = _attached;
        _attached = null;
        if (f == null) return;
        f.Poll?.Dispose();
        f.Poll = null;
        if (_automation != null)
        {
            if (f.TextHandler != null)
                Safe(() => { _automation.RemoveAutomationEventHandler(UIA_EventIds.UIA_Text_TextChangedEventId, f.Element, f.TextHandler); return true; }, false);
            if (f.ValueHandler != null)
                Safe(() => { _automation.RemovePropertyChangedEventHandler(f.Element, f.ValueHandler); return true; }, false);
        }
        f.TextHandler = null;
        f.ValueHandler = null;
        f.Root = null;
        f.RangeCache.Clear();
        f.LastText = "";   // forget the text
        f.LastCaret = null;
    }

    private void QueueRead(Field f)
    {
        if (Interlocked.Exchange(ref f.ReadQueued, 1) != 0) return;
        _worker.Post(() =>
        {
            Interlocked.Exchange(ref f.ReadQueued, 0);
            if (ReferenceEquals(_attached, f)) ReadAndPost(f, force: false);
        });
    }

    private void ReadAndPost(Field f, bool force)
    {
        var (text, caret, root) = ReadText(f);
        if (text == null) return;
        bool changed = force || !string.Equals(text, f.LastText, StringComparison.Ordinal);
        if (!changed && caret == f.LastCaret) return;
        if (changed)
        {
            f.Seq++;
            f.Root = root;
            f.RangeCache.Clear();
            f.LastText = text;
        }
        f.LastCaret = caret;
        var read = new TextRead(f.Token, f.Seq, text, caret, f.VisibleMode, f.Root != null);
        _ui.BeginInvoke(new Action(() => TextRead?.Invoke(read)));
    }

    /// <summary>Reads the field's text: the whole field, or the paragraphs on screen.</summary>
    private (string? Text, int? Caret, IUIAutomationTextRange? Root) ReadText(Field f)
    {
        try
        {
            if (f.Text == null)
            {
                string value = f.Value?.CurrentValue ?? "";
                return (value, null, null);
            }
            var rule = f.Rule ?? new AppRule();
            if (!f.VisibleMode)
            {
                var doc = f.Text.DocumentRange;
                string all = doc.GetText(rule.DocumentMaxChars + 1) ?? "";
                if (all.Length <= rule.DocumentMaxChars)
                    return (all, all.Length > 8000 ? CaretOffset(f, doc) : null, doc);
                f.VisibleMode = true; // too long to read whole: read what is on screen from now on
            }

            var visible = f.Text.GetVisibleRanges();
            if (visible == null || visible.Length == 0) return ("", null, null);
            var root = visible.GetElement(0).Clone();
            root.MoveEndpointByRange(TextPatternRangeEndpoint.TextPatternRangeEndpoint_End,
                visible.GetElement(visible.Length - 1), TextPatternRangeEndpoint.TextPatternRangeEndpoint_End);

            // Widen to whole paragraphs so every paragraph sent is complete.
            var head = root.Clone();
            head.MoveEndpointByRange(TextPatternRangeEndpoint.TextPatternRangeEndpoint_End, head, TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start);
            head.ExpandToEnclosingUnit(TextUnit.TextUnit_Paragraph);
            root.MoveEndpointByRange(TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start, head, TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start);
            var tail = root.Clone();
            tail.MoveEndpointByRange(TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start, tail, TextPatternRangeEndpoint.TextPatternRangeEndpoint_End);
            tail.ExpandToEnclosingUnit(TextUnit.TextUnit_Paragraph);
            root.MoveEndpointByRange(TextPatternRangeEndpoint.TextPatternRangeEndpoint_End, tail, TextPatternRangeEndpoint.TextPatternRangeEndpoint_End);

            string text = root.GetText(MaxVisibleChars) ?? "";
            return (text, CaretOffset(f, root), root);
        }
        catch (COMException)
        {
            return (null, null, null);
        }
    }

    /// <summary>The caret's offset within <paramref name="root"/>, when the host reports one.</summary>
    private static int? CaretOffset(Field f, IUIAutomationTextRange root)
    {
        try
        {
            IUIAutomationTextRange? caret = null;
            if (f.Text2 != null) caret = f.Text2.GetCaretRange(out _);
            if (caret == null && f.Text != null)
            {
                var sel = f.Text.GetSelection();
                if (sel != null && sel.Length > 0) caret = sel.GetElement(0);
            }
            if (caret == null) return null;
            if (root.CompareEndpoints(TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start, caret, TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start) > 0)
                return 0;
            if (root.CompareEndpoints(TextPatternRangeEndpoint.TextPatternRangeEndpoint_End, caret, TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start) < 0)
                return null;
            var before = root.Clone();
            before.MoveEndpointByRange(TextPatternRangeEndpoint.TextPatternRangeEndpoint_End, caret, TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start);
            return before.GetText(-1)?.Length;
        }
        catch (COMException)
        {
            return null;
        }
    }

    /// <summary>
    /// The host's range for a UTF-16 range of the snapshot text. First by moving
    /// character by character from the root's start, verified by reading the text
    /// back; when the host counts characters differently (line breaks, surrogate
    /// pairs), by finding the same occurrence of the flagged text instead.
    /// </summary>
    private static IUIAutomationTextRange? Locate(IUIAutomationTextRange root, string snapshotText, TextRange16 range, string flagged)
    {
        try
        {
            var r = root.Clone();
            int movedStart = range.Start == 0 ? 0
                : r.MoveEndpointByUnit(TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start, TextUnit.TextUnit_Character, range.Start);
            if (movedStart == range.Start)
            {
                r.MoveEndpointByRange(TextPatternRangeEndpoint.TextPatternRangeEndpoint_End, r, TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start);
                r.MoveEndpointByUnit(TextPatternRangeEndpoint.TextPatternRangeEndpoint_End, TextUnit.TextUnit_Character, range.Length);
                if (string.Equals(r.GetText(range.Length + 1), flagged, StringComparison.Ordinal)) return r;
            }
        }
        catch (COMException) { }

        int k = Utf16.OccurrenceIndex(snapshotText, flagged, range.Start);
        if (k < 0) return null;
        try
        {
            var search = root.Clone();
            for (int i = 0; i <= k; i++)
            {
                var found = search.FindText(flagged, 0, 0);
                if (found == null) return null;
                if (i == k) return found;
                search.MoveEndpointByRange(TextPatternRangeEndpoint.TextPatternRangeEndpoint_Start, found, TextPatternRangeEndpoint.TextPatternRangeEndpoint_End);
            }
        }
        catch (COMException) { }
        return null;
    }

    // ---- write-back -----------------------------------------------------

    private WriteResult WriteBack(WriteRequest req)
    {
        var f = _attached;
        if (f == null || f.Token != req.Token || f.Rule == null) return new(WriteResultKind.Stale, null);

        var (before, _, root) = ReadText(f);
        if (before == null) return new(WriteResultKind.Failed, null);

        // The snapshot offsets are only trusted while the text is the one they came from.
        bool sameText = string.Equals(before, f.LastText, StringComparison.Ordinal);
        string paragraphExpected = Utf16.Splice(req.ParagraphText,
            new TextRange16(req.Suggestion.Range.Start - req.ParagraphStart, req.Suggestion.Range.End - req.ParagraphStart),
            req.Replacement);
        if (!sameText || !WriteBackPlan.StillApplies(before, req.Suggestion))
            return new(WriteResultKind.Stale, null);
        string expected = WriteBackPlan.Expected(before, req.Suggestion, req.Replacement);

        foreach (var method in f.Rule.WriteBack)
        {
            if (method == WriteBackMethod.ValueSet && (f.Value == null || f.VisibleMode)) continue;
            if (method != WriteBackMethod.ValueSet && root == null) continue;
            if (method == WriteBackMethod.SelectAndType && (req.Replacement.Contains('\r') || req.Replacement.Contains('\n'))) continue;

            if (NativeMethods.ForegroundProcessId() != f.Pid) return new(WriteResultKind.NotForeground, method);
            if (!WaitForModifiersReleased()) return new(WriteResultKind.KeysHeld, method);

            bool attempted = method switch
            {
                WriteBackMethod.SelectAndType => SelectThen(f, root!, req, () => Input.TypeText(req.Replacement)),
                WriteBackMethod.SelectAndPaste => SelectThen(f, root!, req, () => PasteViaClipboard(req.Replacement)),
                WriteBackMethod.ValueSet => SetValue(f, expected),
                _ => false,
            };
            if (!attempted) continue;

            var outcome = Verify(f, before, expected, req.ParagraphText, paragraphExpected);
            if (outcome == WriteBackOutcome.Applied)
            {
                ReadAndPost(f, force: false);
                return new(WriteResultKind.Applied, method);
            }
            if (outcome == WriteBackOutcome.Unexpected)
            {
                ReadAndPost(f, force: false);
                return new(WriteResultKind.Unexpected, method);
            }
            // NoChange: try the next method.
        }
        return new(WriteResultKind.Failed, null);
    }

    private WriteBackOutcome Verify(Field f, string before, string expected, string paragraphBefore, string paragraphExpected)
    {
        WriteBackOutcome Check()
        {
            var (after, _, _) = ReadText(f);
            if (after == null) return WriteBackOutcome.Unexpected;
            return f.VisibleMode
                ? WriteBackPlan.ClassifyParagraph(paragraphBefore, paragraphExpected, after)
                : WriteBackPlan.Classify(before, after, expected);
        }
        Thread.Sleep(120);
        var first = Check();
        if (first != WriteBackOutcome.NoChange) return first;
        Thread.Sleep(300); // a slow host may still be applying the change
        return Check();
    }

    /// <summary>Selects the range in the host, checks the selection holds exactly the flagged text, then runs <paramref name="write"/>.</summary>
    private static bool SelectThen(Field f, IUIAutomationTextRange root, WriteRequest req, Func<bool> write)
    {
        var range = Locate(root, f.LastText, req.Suggestion.Range, req.Suggestion.FlaggedText);
        if (range == null || f.Text == null) return false;
        try
        {
            range.Select();
            Thread.Sleep(40);
            var sel = f.Text.GetSelection();
            if (sel == null || sel.Length != 1) return false;
            string selected = sel.GetElement(0).GetText(req.Suggestion.FlaggedText.Length + 1) ?? "";
            // Never type over a selection we cannot confirm.
            if (!string.Equals(selected, req.Suggestion.FlaggedText, StringComparison.Ordinal)) return false;
        }
        catch (COMException)
        {
            return false;
        }
        return write();
    }

    private bool PasteViaClipboard(string replacement)
    {
        if (replacement.Length == 0) return Input.PressDelete();
        ClipboardGuard? guard = null;
        try
        {
            bool set = false;
            _ui.Invoke(() =>
            {
                guard = ClipboardGuard.Take();
                set = guard.SetPrivateText(replacement);
            });
            if (!set) return false;
            bool sent = Input.PressCtrlV();
            Thread.Sleep(350); // let the host read the clipboard before it is restored
            return sent;
        }
        catch (Exception e) when (e is COMException or ExternalException or InvalidOperationException or OutOfMemoryException)
        {
            return false;
        }
        finally
        {
            if (guard != null)
            {
                try { _ui.Invoke(() => guard.Restore()); }
                catch (Exception e) when (e is COMException or ExternalException or InvalidOperationException) { }
            }
        }
    }

    private static bool SetValue(Field f, string expected)
    {
        try
        {
            f.Value!.SetValue(expected);
            return true;
        }
        catch (COMException)
        {
            return false;
        }
    }

    private static bool WaitForModifiersReleased()
    {
        for (int i = 0; i < 12; i++)
        {
            if (!NativeMethods.AnyModifierDown()) return true;
            Thread.Sleep(50);
        }
        return false;
    }

    // ---- helpers --------------------------------------------------------

    private void Raise(FieldCandidate? candidate) =>
        _ui.BeginInvoke(new Action(() => FocusChanged?.Invoke(candidate)));

    private static T Safe<T>(Func<T> f, T fallback)
    {
        try { return f(); }
        catch (COMException) { return fallback; }
        catch (InvalidCastException) { return fallback; }
        catch (InvalidOperationException) { return fallback; }
        catch (UnauthorizedAccessException) { return fallback; }
        catch (NotImplementedException) { return fallback; }
    }

    public void Dispose()
    {
        _worker.Post(() =>
        {
            DetachInternal();
            if (_automation != null)
                Safe(() => { _automation.RemoveAllEventHandlers(); return true; }, false);
            _candidate = null;
        });
        _worker.Dispose();
    }
}
