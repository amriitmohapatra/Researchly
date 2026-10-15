using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.State;
using Researchly.Overlay.Core.Text;
using Researchly.Overlay.Core.Timing;

namespace Researchly.Overlay.Core.Session;

/// <summary>A suggestion placed in the current snapshot (absolute UTF-16 offsets in the field text).</summary>
public sealed record PlacedSuggestion(Suggestion Suggestion, TextRange16 Range, string FlaggedText, string ParagraphId)
{
    public string Id => Suggestion.Id;
}

/// <summary>
/// The platform-neutral loop for one focused field (docs/inline-review-design.md
/// section 6, steps 3 and 4 and the states of section 3): keeps a snapshot of
/// the text, diffs it by paragraph, waits for the typing pause, sends only the
/// paragraphs that changed with a revision number, drops stale replies, retries
/// with backoff when offline, and places suggestions back on the current text.
/// Not thread-safe: the shell calls it, and the scheduler and engine
/// continuations run, on one thread (the UI thread).
/// Text is held in memory only while the field has focus; <see cref="Stop"/> drops it.
/// </summary>
public sealed class LiveCheckSession : IDisposable
{
    /// <summary>At most this many paragraphs per request; the rest follow in the next one (the engine takes 50).</summary>
    public const int MaxParagraphsPerRequest = 20;
    /// <summary>
    /// About this many characters per request (one longer paragraph is still sent alone): well inside
    /// the engine's 20,000, and under the hosted engine's word cap for a caller without an account (1,500 words).
    /// </summary>
    public const int MaxCharsPerRequest = 6_000;

    private sealed class Record
    {
        public string Text = "";
        public bool Dirty;
        public bool IsHeading;
        public string? Heading;
        public string? SentHeading;
        /// <summary>Refused by the engine as sent (422 and the like): not sent again until its text changes.</summary>
        public bool Rejected;
        /// <summary>Longer than the engine checks at once (LiveLimits): never sent.</summary>
        public bool TooLong;
        public List<Suggestion> Results = new();
    }

    private readonly IEngineClient _engine;
    private readonly IScheduler _scheduler;
    private readonly Func<CheckOptionsPayload> _options;
    private readonly Debouncer _debouncer;
    private readonly RetryBackoff _backoff = new();
    private readonly Dictionary<string, Record> _records = new(StringComparer.Ordinal);
    private readonly HashSet<string> _dismissed = new(StringComparer.Ordinal);
    private List<TrackedParagraph> _tracked = new();
    private List<PlacedSuggestion> _visible = new();
    private CancellationTokenSource? _inflight;
    private IDisposable? _retryTimer;
    private IDisposable? _followUp;
    private long _revision;
    private long _generation;
    private int _nextParagraphId;
    private bool _running;
    private bool _lastPartial;
    private string? _lastPartialDetail;

    public LiveCheckSession(IEngineClient engine, IScheduler scheduler, Func<CheckOptionsPayload> options, TimeSpan? debounce = null)
    {
        _engine = engine;
        _scheduler = scheduler;
        _options = options;
        _debouncer = new Debouncer(scheduler, debounce ?? Debouncer.DefaultDelay, SendCheck);
    }

    public StateMachine State { get; } = new();
    public TextSnapshot Snapshot { get; private set; } = TextSnapshot.Empty;
    public IReadOnlyList<PlacedSuggestion> Visible => _visible;

    /// <summary>Preferences are hidden unless the writer switches them on (CLAUDE.md rule 3).</summary>
    public bool ShowPreferences { get; private set; }

    /// <summary>Shows or hides Preference suggestions, and asks the engine again (it may have left them out).</summary>
    public void SetShowPreferences(bool show)
    {
        if (ShowPreferences == show) return;
        ShowPreferences = show;
        RebuildVisible();
        SuggestionsChanged?.Invoke();
        RecheckAll();
    }

    /// <summary>The caret's offset in the field text, when known; paragraphs near it are checked first.</summary>
    public int? CaretOffset { get; set; }

    /// <summary>The revision of the most recent request.</summary>
    public long Revision => _revision;
    public int StaleRepliesDropped { get; private set; }
    public int InvalidSuggestionsDropped { get; private set; }
    public int RequestsSent { get; private set; }
    /// <summary>When offline, when the next retry is due.</summary>
    public DateTimeOffset? NextRetryAt { get; private set; }
    public bool IsRunning => _running;

    /// <summary>Raised when <see cref="Visible"/> changes.</summary>
    public event Action? SuggestionsChanged;

    /// <summary>The field gained focus and passed the gate: check it straight away.</summary>
    public void Start(string text, IReadOnlyList<string?>? styles = null)
    {
        ResetText();
        _running = true;
        State.FieldEntered();
        ApplyText(text, styles);
        _debouncer.Cancel();
        SendCheck();
    }

    /// <summary>The field's text was read again (an event or a poll). Cheap when nothing changed.</summary>
    public void UpdateText(string text, IReadOnlyList<string?>? styles = null)
    {
        if (!_running) return;
        if (string.Equals(text, Snapshot.Text, StringComparison.Ordinal) && styles == null) return;
        bool changed = ApplyText(text, styles);
        if (!changed) return;
        _generation++;
        if (AnyDirty())
        {
            State.Edited();
            _debouncer.Poke();
        }
        else
        {
            Settle();
        }
    }

    /// <summary>Leave the field, become ineligible or pause: hide and forget the text.</summary>
    public void Stop()
    {
        _running = false;
        ResetText();
        State.Hide();
        SuggestionsChanged?.Invoke();
    }

    /// <summary>"Not an issue": hide this suggestion for the rest of this session (kept in memory only).</summary>
    public void Dismiss(string suggestionId)
    {
        if (!_dismissed.Add(suggestionId)) return;
        RebuildVisible();
        State.CountChanged(_visible.Count);
    }

    /// <summary>
    /// Check every paragraph again, now (the options or the engine changed). The
    /// writer asked for it, so a pending offline retry does not hold it back.
    /// </summary>
    public void RecheckAll()
    {
        if (!_running) return;
        foreach (var r in _records.Values)
            if (!r.IsHeading && !r.TooLong && !string.IsNullOrWhiteSpace(r.Text))
            {
                r.Dirty = true;
                r.Rejected = false;
            }
        _generation++;
        State.Edited();
        _debouncer.Cancel();
        _retryTimer?.Dispose();
        _retryTimer = null;
        NextRetryAt = null;
        SendCheck();
    }

    /// <summary>Retry now (the writer asked, or the network came back).</summary>
    public void RetryNow()
    {
        if (!_running) return;
        _retryTimer?.Dispose();
        _retryTimer = null;
        NextRetryAt = null;
        SendCheck();
    }

    public PlacedSuggestion? Find(string suggestionId) => _visible.FirstOrDefault(v => v.Id == suggestionId);

    /// <summary>The visible suggestions covering an absolute offset, most important category first.</summary>
    public IReadOnlyList<PlacedSuggestion> At(int offset) =>
        _visible.Where(v => offset >= v.Range.Start && offset < v.Range.End)
                .OrderBy(v => (int)v.Suggestion.Category).ToList();

    public void Dispose()
    {
        Stop();
        _debouncer.Dispose();
    }

    // ---- internals -------------------------------------------------------

    private void ResetText()
    {
        _inflight?.Cancel();
        _inflight?.Dispose();
        _inflight = null;
        _retryTimer?.Dispose();
        _retryTimer = null;
        _followUp?.Dispose();
        _followUp = null;
        _debouncer.Cancel();
        _backoff.Reset();
        NextRetryAt = null;
        _records.Clear();
        _tracked = new List<TrackedParagraph>();
        _visible = new List<PlacedSuggestion>();
        _dismissed.Clear();
        Snapshot = TextSnapshot.Empty;
        _lastPartial = false;
        _lastPartialDetail = null;
    }

    /// <summary>Diffs the new text into the records. Returns true when anything changed.</summary>
    private bool ApplyText(string text, IReadOnlyList<string?>? styles)
    {
        var snapshot = TextSnapshot.Create(text ?? "", styles);
        var previous = _tracked.Select(t => (t.Id, t.Text)).ToList();
        var diff = ParagraphDiff.Diff(previous, snapshot, NewParagraphId);
        var headings = HeadingDetector.NearestHeadings(snapshot.Paragraphs);

        bool changed = diff.HasChanges;
        foreach (var id in diff.RemovedIds) _records.Remove(id);

        for (int i = 0; i < diff.Paragraphs.Count; i++)
        {
            var tp = diff.Paragraphs[i];
            bool isHeading = HeadingDetector.IsHeading(tp.Paragraph);
            if (!_records.TryGetValue(tp.Id, out var rec))
            {
                rec = new Record();
                _records[tp.Id] = rec;
            }

            if (tp.Change == ParagraphChange.Changed && tp.PreviousText != null)
            {
                // Keep suggestions the edit did not touch, moved to their new place.
                var edit = Utf16.ComputeEdit(tp.PreviousText, tp.Text);
                var kept = new List<Suggestion>();
                foreach (var s in rec.Results)
                {
                    var moved = Utf16.ShiftThroughEdit(new TextRange16(s.Begin, s.End), edit);
                    if (moved is { } m && Utf16.IsValidRange(tp.Text, m.Start, m.End))
                        kept.Add(s with { Begin = m.Start, End = m.End });
                }
                rec.Results = kept;
                rec.Dirty = true;
                rec.Rejected = false;
            }
            else if (tp.Change == ParagraphChange.Added)
            {
                rec.Results = new List<Suggestion>();
                rec.Dirty = true;
                rec.Rejected = false;
            }

            rec.Text = tp.Text;
            rec.TooLong = LiveLimits.Characters(rec.Text) > LiveLimits.MaxCharacters;
            if (rec.IsHeading != isHeading) changed = true;
            rec.IsHeading = isHeading;
            rec.Heading = headings[i];
            // A new heading above a paragraph changes its section: check it again.
            if (!rec.Dirty && !rec.Rejected && !isHeading && rec.SentHeading != rec.Heading && !string.IsNullOrWhiteSpace(rec.Text))
            {
                rec.Dirty = true;
                changed = true;
            }
            if (isHeading || string.IsNullOrWhiteSpace(rec.Text) || rec.TooLong)
            {
                rec.Dirty = false;
                rec.Results = new List<Suggestion>();
            }
        }

        _tracked = diff.Paragraphs.ToList();
        Snapshot = snapshot;
        RebuildVisible();
        SuggestionsChanged?.Invoke();
        return changed;
    }

    private string NewParagraphId() => "p" + (++_nextParagraphId).ToString(CultureInfo.InvariantCulture);

    private bool AnyDirty() => _records.Values.Any(r => r.Dirty);

    private void SendCheck()
    {
        if (!_running) return;
        _followUp?.Dispose();
        _followUp = null;
        // While a retry is scheduled, edits wait for it rather than adding requests.
        if (_retryTimer != null && State.State == OverlayState.Offline) return;

        var batch = PickBatch();
        if (batch.Count == 0)
        {
            Settle();
            return;
        }

        var request = new CheckParagraphsRequest
        {
            Revision = ++_revision,
            Options = _options(),
        };
        foreach (var (id, rec) in batch)
            request.Paragraphs.Add(new ParagraphPayload { Id = id, Text = rec.Text, Heading = Clip(rec.Heading) });

        _inflight?.Cancel();
        _inflight?.Dispose();
        _inflight = new CancellationTokenSource();
        RequestsSent++;
        State.RequestSent();
        _ = RunAsync(request, _revision, _generation, _inflight.Token);
    }

    /// <summary>A heading the engine accepts (at most 300 characters); a longer one is cut at a character boundary.</summary>
    private static string? Clip(string? heading)
    {
        if (heading == null || heading.Length <= LiveLimits.MaxHeadingCharacters) return heading;
        int end = LiveLimits.MaxHeadingCharacters;
        if (char.IsHighSurrogate(heading[end - 1])) end--;
        return heading.Substring(0, end);
    }

    private List<(string Id, Record Rec)> PickBatch()
    {
        var dirty = new List<(string Id, Record Rec, int Distance)>();
        foreach (var tp in _tracked)
        {
            if (!_records.TryGetValue(tp.Id, out var rec) || !rec.Dirty || rec.TooLong) continue;
            int distance = CaretOffset is int c
                ? (c < tp.Paragraph.Start ? tp.Paragraph.Start - c : c > tp.Paragraph.End ? c - tp.Paragraph.End : 0)
                : 0;
            dirty.Add((tp.Id, rec, distance));
        }
        var batch = new List<(string, Record)>();
        int chars = 0;
        foreach (var d in dirty.OrderBy(d => d.Distance))
        {
            if (batch.Count >= MaxParagraphsPerRequest) break;
            if (batch.Count > 0 && chars + d.Rec.Text.Length > MaxCharsPerRequest) break;
            batch.Add((d.Id, d.Rec));
            chars += d.Rec.Text.Length;
        }
        return batch;
    }

    private async Task RunAsync(CheckParagraphsRequest request, long revision, long generation, CancellationToken token)
    {
        CheckReply reply;
        try
        {
            reply = await _engine.CheckAsync(request, token);
        }
        catch (OperationCanceledException) when (token.IsCancellationRequested)
        {
            return; // superseded by a newer request, or the session stopped
        }
        catch (EngineException e)
        {
            OnFailure(e, request, revision);
            return;
        }
        catch (Exception e)
        {
            OnFailure(new EngineException("unreachable", "The engine could not be reached.", inner: e), request, revision);
            return;
        }
        OnReply(reply, request, revision, generation);
    }

    private void OnReply(CheckReply reply, CheckParagraphsRequest request, long revision, long generation)
    {
        if (!_running) return;
        bool stale = revision != _revision
                     || (reply.Revision is long echoed && echoed != revision)
                     || generation != _generation;
        if (stale)
        {
            StaleRepliesDropped++;
            // A reply that arrived after an edit says nothing reliable about the
            // engine being down; if we were offline, contact is restored.
            if (State.State == OverlayState.Offline && revision == _revision)
                RecoverFromOffline();
            return;
        }

        RecoverFromOffline();
        InvalidSuggestionsDropped += reply.DroppedSuggestions;
        foreach (var p in request.Paragraphs)
        {
            if (!_records.TryGetValue(p.Id, out var rec) || !string.Equals(rec.Text, p.Text, StringComparison.Ordinal))
                continue;
            rec.Results = reply.ByParagraph.TryGetValue(p.Id, out var list) ? list.ToList() : new List<Suggestion>();
            rec.Dirty = false;
            rec.SentHeading = p.Heading;
        }
        _lastPartial = reply.Partial;
        _lastPartialDetail = reply.PartialDetail;
        RebuildVisible();
        SuggestionsChanged?.Invoke();

        if (AnyDirty())
        {
            // More paragraphs than fit in one request: send the rest straight away.
            _followUp = _scheduler.Schedule(TimeSpan.Zero, SendCheck);
            return;
        }
        ReportReply();
    }

    private void RecoverFromOffline()
    {
        _backoff.Reset();
        _retryTimer?.Dispose();
        _retryTimer = null;
        NextRetryAt = null;
        if (State.State == OverlayState.Offline)
            State.FieldEntered(); // leave offline; the reply sets the final state
    }

    private void OnFailure(EngineException e, CheckParagraphsRequest request, long revision)
    {
        if (!_running || revision != _revision) return;
        if (!e.Retryable)
        {
            // Refused as sent (422 and the like): the same request would be refused again.
            // Say so, keep these paragraphs out until they are edited, and do not retry.
            foreach (var p in request.Paragraphs)
            {
                if (!_records.TryGetValue(p.Id, out var rec) || !string.Equals(rec.Text, p.Text, StringComparison.Ordinal))
                    continue;
                rec.Rejected = true;
                rec.Dirty = false;
                rec.Results = new List<Suggestion>();
            }
            _backoff.Reset();
            _retryTimer?.Dispose();
            _retryTimer = null;
            NextRetryAt = null;
            RebuildVisible();
            SuggestionsChanged?.Invoke();
            State.RequestFailed(OfflineDetail(e));
            return;
        }
        var delay = _backoff.Next();
        if (e.RetryAfter is { } ra && ra > delay) delay = ra > TimeSpan.FromSeconds(120) ? TimeSpan.FromSeconds(120) : ra;
        State.RequestFailed(OfflineDetail(e));
        _retryTimer?.Dispose();
        NextRetryAt = _scheduler.Now + delay;
        _retryTimer = _scheduler.Schedule(delay, () =>
        {
            _retryTimer = null;
            NextRetryAt = null;
            SendCheck();
        });
    }

    private static string OfflineDetail(EngineException e) => e.Code switch
    {
        "unreachable" => "Can’t check right now: the engine cannot be reached. Check that it is running, or choose another engine.",
        "timeout" => "Can’t check right now: the engine did not answer in time.",
        "rate_limited" => "Can’t check right now: the engine is busy. Retrying shortly.",
        "not_found" => "Can’t check right now: this engine does not offer live checks. Update it, or choose another engine.",
        "bad_reply" => "Can’t check right now: the engine's reply could not be read.",
        "sign_in_required" => "Can’t check this here: without an account the engine checks only a little text at a time. Choose This computer in the Researchly menu, or check a shorter passage.",
        "payload_too_large" => "Can’t check this as you type: the text is too long. Researchly will try again after your next edit.",
        "invalid_request" or "malformed_request" or "malformed_json" =>
            "Can’t check this text as it was sent. Researchly will try again after your next edit; if this keeps happening, update the engine or this app.",
        "no_engine" => "Can’t check right now: no engine is chosen. Choose This computer, or set a hosted address, in the Researchly menu.",
        _ => "Can’t check right now: the engine refused the request.",
    };

    private void Settle()
    {
        if (State.State is OverlayState.Hidden or OverlayState.Offline) return;
        if (_inflight != null && !_inflight.IsCancellationRequested && AnyDirty()) return;
        ReportReply();
    }

    /// <summary>The state after a reply: partial when a tier was down, or when some paragraphs could not be checked.</summary>
    private void ReportReply()
    {
        string? notChecked = UncheckedDetail();
        bool partial = _lastPartial || notChecked != null;
        string? detail = string.Join(" ", new[] { _lastPartial ? _lastPartialDetail : null, notChecked }.Where(d => d != null));
        State.ReplyReceived(_visible.Count, partial, partial ? detail : null);
    }

    /// <summary>Why some paragraphs have no underlines although they were not checked clear; null when all were.</summary>
    public string? UncheckedDetail()
    {
        int rejected = _records.Values.Count(r => r.Rejected && !r.IsHeading);
        int tooLong = _records.Values.Count(r => r.TooLong && !r.IsHeading);
        var parts = new List<string>();
        if (rejected == 1) parts.Add("One paragraph couldn’t be checked; it will be after you edit it.");
        else if (rejected > 1) parts.Add(rejected.ToString(CultureInfo.InvariantCulture) + " paragraphs couldn’t be checked; they will be after you edit them.");
        if (tooLong == 1) parts.Add("One paragraph is too long to check as you type.");
        else if (tooLong > 1) parts.Add(tooLong.ToString(CultureInfo.InvariantCulture) + " paragraphs are too long to check as you type.");
        return parts.Count == 0 ? null : string.Join(" ", parts);
    }

    private void RebuildVisible()
    {
        var list = new List<PlacedSuggestion>();
        foreach (var tp in _tracked)
        {
            if (!_records.TryGetValue(tp.Id, out var rec)) continue;
            foreach (var s in rec.Results)
            {
                if (_dismissed.Contains(s.Id)) continue;
                if (s.Category == Category.Preference && !ShowPreferences) continue;
                if (!Utf16.IsValidRange(tp.Text, s.Begin, s.End)) continue;
                string flagged = tp.Text.Substring(s.Begin, s.End - s.Begin);
                // The engine's flagged words must still be exactly there: a write-back checks the same words.
                if (s.Text.Length > 0 && !string.Equals(flagged, s.Text, StringComparison.Ordinal)) continue;
                var range = new TextRange16(tp.Paragraph.Start + s.Begin, tp.Paragraph.Start + s.End);
                list.Add(new PlacedSuggestion(s, range, flagged, tp.Id));
            }
        }
        _visible = list;
    }
}
