using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Threading;
using Researchly.Overlay.Capture;
using Researchly.Overlay.Core.Eligibility;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Placement;
using Researchly.Overlay.Core.Session;
using Researchly.Overlay.Core.Settings;
using Researchly.Overlay.Core.State;
using Researchly.Overlay.Native;
using Researchly.Overlay.Platform;
using Researchly.Overlay.Tray;
using Researchly.Overlay.Ui;

namespace Researchly.Overlay;

/// <summary>
/// Wires the loop of docs/inline-review-design.md section 6 together on the UI
/// thread: focus and gate, text and live check, geometry and underlines,
/// hover teaser and card, write-back, the field widget and the menu.
/// </summary>
internal sealed class OverlayController : IDisposable
{
    private static readonly string Version = typeof(OverlayController).Assembly.GetName().Version?.ToString(3) ?? "0.1.0";
    private static readonly TimeSpan HoverDelay = TimeSpan.FromMilliseconds(350);
    private static readonly TimeSpan LeaveDelay = TimeSpan.FromMilliseconds(400);

    private const string PrivacyText =
        "Researchly reads the text of the field you are typing in, only while that field has focus, " +
        "and only in apps and fields it is allowed in. It never reads password fields, or fields whose " +
        "labels mention passwords, card numbers, signing in and similar.\n\n" +
        "Changed paragraphs go to the engine you chose (This computer, or the hosted address) to be " +
        "checked in memory. Nothing else receives your text.\n\n" +
        "Researchly does not store document text. The only file it writes is its settings " +
        "(overlay-settings.json in your AppData\\Roaming\\Researchly folder).\n\n" +
        "You can pause it at any time from this menu.";

    private readonly Dispatcher _ui;
    private readonly string _settingsPath = SettingsStore.DefaultPath();
    private readonly Theme _theme = new();
    private readonly SwitchableEngine _engine = new();
    private OverlaySettings _settings = new();
    private EligibilityGate? _gate;
    private FieldWatcher? _watcher;
    private LiveCheckSession? _session;
    private OverlayWindow? _overlay;
    private FieldWidget? _widget;
    private TeaserWindow? _teaser;
    private CardWindow? _card;
    private TipWindow? _tip;
    private TrayIcon? _tray;
    private DispatcherTimer? _hoverTimer;
    private DispatcherTimer? _remeasureTimer;
    private DispatcherTimer? _measureSoon;
    private DispatcherTimer? _pauseTimer;
    private DispatcherTimer? _tipTimer;

    private FieldCandidate? _candidate;
    private AppRule? _rule;
    private long _attachedToken;
    private long _seq;
    private bool _hasGeometry;
    private Measurement? _measurement;
    private Box? _fieldBounds;
    private bool _measuring;
    private bool _measureAgain;

    private NativeMethods.WinEventDelegate? _winEventProc;
    private IntPtr _locationHook;
    private IntPtr _systemHook;

    private string? _hoverId;
    private DateTime _hoverSince;
    private DateTime _awaySince;

    public OverlayController(Dispatcher ui) => _ui = ui;

    private LiveCheckSession Session => _session!;

    public void Start()
    {
        _settings = SettingsStore.Load(_settingsPath);
        _gate = EligibilityGate.Load(RulesLocator.Find());
        _engine.Configure(_settings, Version);

        _session = new LiveCheckSession(_engine, new DispatcherScheduler(_ui), Options);
        _session.SetShowPreferences(_settings.ShowPreferences);
        _session.State.Changed += (_, _) => OnStateChanged();
        _session.SuggestionsChanged += OnSuggestionsChanged;

        _overlay = new OverlayWindow(_theme);
        _overlay.DpiMoved += RequestMeasure;
        _widget = new FieldWidget(_theme);
        _widget.Clicked += OnWidgetClicked;
        _widget.Dragged += OnWidgetDragged;
        _widget.Hovered += OnWidgetHovered;
        _teaser = new TeaserWindow(_theme);
        _teaser.Clicked += OpenCard;
        _card = new CardWindow(_theme);
        _card.AcceptRequested += Accept;
        _card.DismissRequested += Dismiss;
        _card.StepRequested += Step;
        _card.CloseRequested += () => _card.HideCard();
        _tip = new TipWindow(_theme);
        _theme.Changed += OnThemeChanged;

        _tray = new TrayIcon();
        _tray.PauseHour += () => ChangeSettings(s => s.PauseForOneHour(DateTimeOffset.UtcNow));
        _tray.PauseTomorrow += () => ChangeSettings(s => s.PauseUntilTomorrow(DateTimeOffset.Now));
        _tray.Resume += () => ChangeSettings(s => s.ResumeEverywhere());
        _tray.PauseApp += () => { if (CurrentProcess() is { } p) ChangeSettings(s => s.PauseApp(p)); };
        _tray.ResumeApp += () => { if (CurrentProcess() is { } p) ChangeSettings(s => s.ResumeApp(p)); };
        _tray.UseThisComputer += () => ChangeEngine(s => s.Engine = EngineChoice.ThisComputer);
        _tray.UseHosted += () =>
        {
            if (string.IsNullOrEmpty(_settings.HostedUrl)) AskHostedAddress();
            else ChangeEngine(s => s.Engine = EngineChoice.Hosted);
        };
        _tray.SetHostedAddress += AskHostedAddress;
        _tray.TogglePreferences += () =>
        {
            ChangeSettings(s => s.ShowPreferences = !s.ShowPreferences);
            Session.SetShowPreferences(_settings.ShowPreferences);
        };
        _tray.RetryNow += () => Session.RetryNow();
        _tray.ShowPrivacy += () => MessageBox.Show(PrivacyText, "Researchly and your text", MessageBoxButton.OK, MessageBoxImage.Information);
        _tray.Quit += () => Application.Current.Shutdown();
        _tray.LeftClicked += () => { if (Session.Visible.Count > 0) OpenCard(Session.Visible[0].Id); };

        _hoverTimer = Timer(TimeSpan.FromMilliseconds(80), OnHoverTick, start: true);
        _remeasureTimer = Timer(TimeSpan.FromMilliseconds(500), () => { if (_attachedToken != 0) RequestMeasure(); }, start: true);
        _measureSoon = Timer(TimeSpan.FromMilliseconds(60), () => { _measureSoon!.Stop(); RequestMeasure(); }, start: false);
        _pauseTimer = Timer(TimeSpan.FromSeconds(30), OnPauseTick, start: true);
        _tipTimer = Timer(TimeSpan.FromSeconds(5), () => { _tipTimer!.Stop(); _tip?.Hide(); }, start: false);

        var apps = _gate.Apps;
        _watcher = new FieldWatcher(_ui, apps.For);
        _watcher.FocusChanged += OnFocusChanged;
        _watcher.TextRead += OnTextRead;
        _watcher.Start();
        UpdateTray();
    }

    private CheckOptionsPayload Options() => new() { ShowPreferences = _settings.ShowPreferences, Spelling = _settings.Spelling };

    private DispatcherTimer Timer(TimeSpan interval, Action tick, bool start)
    {
        var t = new DispatcherTimer(DispatcherPriority.Background, _ui) { Interval = interval };
        t.Tick += (_, _) => tick();
        if (start) t.Start();
        return t;
    }

    // ---- focus and gate -------------------------------------------------

    private void OnFocusChanged(FieldCandidate? candidate)
    {
        HideTransient();
        _candidate = candidate;
        Evaluate();
    }

    private void Evaluate()
    {
        var c = _candidate;
        if (c == null || _gate == null)
        {
            StopField();
            UpdateTray();
            return;
        }
        var verdict = _gate.Evaluate(c.Descriptor, _settings, DateTimeOffset.UtcNow);
        _rule = verdict.App;
        if (verdict.IsEligible)
        {
            if (_attachedToken != c.Token)
            {
                StopField();
                _attachedToken = c.Token;
                _watcher!.Attach(c.Token, verdict.App);
                HookLocation(c.ProcessId);
            }
        }
        else
        {
            StopField();
        }
        UpdateTray();
    }

    private void StopField()
    {
        if (_attachedToken != 0) _watcher?.Detach();
        _attachedToken = 0;
        _measurement = null;
        _fieldBounds = null;
        _hoverId = null;
        Unhook();
        _session?.Stop();
        _overlay?.Clear();
        _widget?.Hide();
        HideTransient();
    }

    private void OnTextRead(TextRead read)
    {
        if (read.Token != _attachedToken) return;
        _seq = read.Seq;
        _hasGeometry = read.HasGeometry;
        Session.CaretOffset = read.Caret;
        if (!Session.IsRunning) Session.Start(read.Text);
        else Session.UpdateText(read.Text);
        RequestMeasure();
    }

    // ---- state ----------------------------------------------------------

    private void OnStateChanged()
    {
        var st = Session.State;
        _widget!.SetState(st.State, st.IssueCount);
        if (st.State == OverlayState.Hidden)
        {
            _widget.Hide();
            _overlay!.Clear();
            HideTransient();
        }
        else
        {
            PositionWidget();
        }
        UpdateTray();
    }

    private void OnSuggestionsChanged()
    {
        if (_card!.SuggestionId is { } open && Session.Find(open) == null) _card.HideCard();
        if (_teaser!.SuggestionId is { } t && Session.Find(t) == null) _teaser.HideTeaser();
        RequestMeasure();
    }

    // ---- geometry -------------------------------------------------------

    private async void RequestMeasure()
    {
        if (_attachedToken == 0 || _watcher == null)
        {
            _overlay?.Clear();
            return;
        }
        if (_measuring)
        {
            _measureAgain = true;
            return;
        }
        _measuring = true;
        try
        {
            do
            {
                _measureAgain = false;
                long token = _attachedToken, seq = _seq;
                var items = Session.Visible.ToList();
                Measurement? m = null;
                if (_hasGeometry && items.Count > 0)
                    m = await _watcher.MeasureAsync(token, seq, items);
                if (token != _attachedToken) break;
                _measurement = m;
                _fieldBounds = m?.Field ?? await _watcher.FieldBoundsAsync(token);
                if (token != _attachedToken) break;
                Render();
                PositionWidget();
            } while (_measureAgain);
        }
        catch (Exception e) when (e is System.Runtime.InteropServices.COMException or InvalidOperationException)
        {
            // The field went away mid-measure; the next focus event recovers.
        }
        finally
        {
            _measuring = false;
        }
    }

    private void Render()
    {
        if (_measurement == null || _fieldBounds == null)
        {
            _overlay!.Clear();
            return;
        }
        var byId = new Dictionary<string, PlacedSuggestion>(StringComparer.Ordinal);
        foreach (var v in Session.Visible) byId.TryAdd(v.Id, v);
        var items = new List<UnderlineItem>();
        foreach (var line in _measurement.Items)
            if (byId.TryGetValue(line.Id, out var s))
                items.Add(new UnderlineItem(s.Id, s.Suggestion.Category, line.Rects));
        _overlay!.Render(_fieldBounds.Value, items, _hoverId);
    }

    private void PositionWidget()
    {
        if (_widget == null || _rule == null || _fieldBounds is not { } field || _widget.IsDragging) return;
        if (Session.State.State == OverlayState.Hidden) return;
        var (work, scale) = NativeMethods.MonitorAt((int)(field.X + field.Width / 2), (int)(field.Y + field.Height / 2));
        var workBox = new Box(work.Left, work.Top, work.Right - work.Left, work.Bottom - work.Top);
        _settings.WidgetNudges.TryGetValue(AppRules.NormaliseProcess(_candidate?.Descriptor.ProcessName ?? ""), out var nudge);
        double size = FieldWidget.SizeDip * scale;
        var (x, y) = WidgetPlacement.Place(field, size, _rule, nudge, workBox, scale);
        bool wasVisible = _widget.IsVisible;
        _widget.ShowQuietly();
        _widget.PlacePhysical(x, y, size, size, keepZOrder: wasVisible);
    }

    private void HookLocation(int pid)
    {
        Unhook();
        _winEventProc ??= OnWinEvent;
        uint flags = NativeMethods.WINEVENT_OUTOFCONTEXT | NativeMethods.WINEVENT_SKIPOWNPROCESS;
        _locationHook = NativeMethods.SetWinEventHook(NativeMethods.EVENT_OBJECT_LOCATIONCHANGE, NativeMethods.EVENT_OBJECT_LOCATIONCHANGE,
            IntPtr.Zero, _winEventProc, (uint)pid, 0, flags);
        _systemHook = NativeMethods.SetWinEventHook(NativeMethods.EVENT_SYSTEM_MOVESIZEEND, NativeMethods.EVENT_SYSTEM_SCROLLINGEND,
            IntPtr.Zero, _winEventProc, (uint)pid, 0, flags);
    }

    private void Unhook()
    {
        if (_locationHook != IntPtr.Zero) NativeMethods.UnhookWinEvent(_locationHook);
        if (_systemHook != IntPtr.Zero) NativeMethods.UnhookWinEvent(_systemHook);
        _locationHook = _systemHook = IntPtr.Zero;
    }

    private void OnWinEvent(IntPtr hook, uint eventType, IntPtr hwnd, int idObject, int idChild, uint thread, uint time)
    {
        // Scrolling, moving and resizing the host: measure again shortly (coalesced).
        if (_attachedToken != 0 && _measureSoon is { IsEnabled: false }) _measureSoon.Start();
    }

    // ---- hover, teaser, card ---------------------------------------------

    private void OnHoverTick()
    {
        if (_teaser == null || _card == null || _overlay == null) return;
        var now = DateTime.UtcNow;
        if (_measurement == null || !_overlay.IsVisible)
        {
            if (_teaser.IsVisible) _teaser.HideTeaser();
            return;
        }
        NativeMethods.GetCursorPos(out var p);
        if (_teaser.ContainsPhysical(p.X, p.Y) || _card.ContainsPhysical(p.X, p.Y))
        {
            _awaySince = now;
            return;
        }
        var (hit, line) = HitTest(p.X, p.Y);
        if (hit != _hoverId)
        {
            _hoverId = hit;
            _hoverSince = now;
            _overlay.SetHovered(hit);
        }
        if (hit != null)
        {
            _awaySince = now;
            if (now - _hoverSince >= HoverDelay && _teaser.SuggestionId != hit && !_card.IsVisible && Session.Find(hit) is { } s)
            {
                var (work, _) = NativeMethods.MonitorAt(p.X, p.Y);
                _teaser.ShowFor(s, line.X, line.Bottom, work.Bottom);
            }
        }
        else if (_teaser.IsVisible && now - _awaySince > LeaveDelay)
        {
            _teaser.HideTeaser();
        }
    }

    private (string? Id, Box Line) HitTest(int x, int y)
    {
        if (_measurement == null) return (null, default);
        foreach (var item in _measurement.Items)
            foreach (var line in item.Rects)
                if (x >= line.X && x < line.Right && y >= line.Y - 2 && y < line.Bottom + 3)
                    return (item.Id, line);
        return (null, default);
    }

    private void OpenCard(string id)
    {
        var list = Session.Visible;
        int index = -1;
        for (int i = 0; i < list.Count; i++) if (list[i].Id == id) { index = i; break; }
        if (index < 0) return;
        _teaser!.HideTeaser();

        Box anchor = default;
        var line = _measurement?.Items.FirstOrDefault(m => m.Id == id)?.Rects.FirstOrDefault();
        if (line is { } l) anchor = l;
        else if (_fieldBounds is { } f) anchor = new Box(f.X + 12, f.Bottom - 40, 1, 1);
        else
        {
            NativeMethods.GetCursorPos(out var p);
            anchor = new Box(p.X, p.Y, 1, 1);
        }
        var (work, scale) = NativeMethods.MonitorAt((int)anchor.X, (int)anchor.Y);
        _card!.ShowFor(list[index], index, list.Count, anchor.X, anchor.Bottom + 8 * scale,
            (work.Left, work.Top, work.Right, work.Bottom));
    }

    private void Step(int delta)
    {
        var list = Session.Visible;
        if (list.Count == 0 || _card?.SuggestionId is not { } current) return;
        int index = 0;
        for (int i = 0; i < list.Count; i++) if (list[i].Id == current) { index = i; break; }
        OpenCard(list[((index + delta) % list.Count + list.Count) % list.Count].Id);
    }

    private void Dismiss(string id)
    {
        var list = Session.Visible;
        int index = 0;
        for (int i = 0; i < list.Count; i++) if (list[i].Id == id) { index = i; break; }
        Session.Dismiss(id);
        var after = Session.Visible;
        if (after.Count == 0) _card!.HideCard();
        else OpenCard(after[Math.Min(index, after.Count - 1)].Id);
    }

    private async void Accept(string id, string replacement)
    {
        var s = Session.Find(id);
        if (s == null || _watcher == null)
        {
            _card!.ShowStatus("This suggestion is out of date.");
            return;
        }
        var paragraph = Session.Snapshot.ParagraphAt(s.Range.Start);
        if (paragraph == null) return;
        _card!.ShowStatus("Changing…");
        var result = await _watcher.WriteBackAsync(new WriteRequest(_attachedToken, s, replacement, paragraph.Text, paragraph.Start));
        if (result.Kind == WriteResultKind.Applied) _card.HideCard();
        else _card.ShowStatus(result.Message);
    }

    private void HideTransient()
    {
        _teaser?.HideTeaser();
        _card?.HideCard();
        if (_tip?.IsVisible == true) _tip.Hide();
    }

    // ---- widget ---------------------------------------------------------

    private void OnWidgetClicked()
    {
        var st = Session.State;
        if (st.State == OverlayState.Offline)
        {
            Session.RetryNow();
            ShowWidgetTip("Trying again…");
            return;
        }
        if (Session.Visible.Count > 0)
        {
            OpenCard(Session.Visible[0].Id);
            return;
        }
        ShowWidgetTip(st.State == OverlayState.Checking ? "Checking…" : "No suggestions here.");
    }

    private void OnWidgetDragged(double dxPx, double dyPx)
    {
        string key = AppRules.NormaliseProcess(_candidate?.Descriptor.ProcessName ?? "");
        if (key.Length == 0) return;
        double scale = _widget!.DeviceScale;
        _settings.WidgetNudges.TryGetValue(key, out var old);
        _settings.WidgetNudges[key] = new WidgetNudge((old?.Dx ?? 0) + dxPx / scale, (old?.Dy ?? 0) + dyPx / scale);
        Save();
        PositionWidget();
    }

    private void OnWidgetHovered(bool over)
    {
        if (!over)
        {
            if (!_tipTimer!.IsEnabled) _tip?.Hide();
            return;
        }
        if (!_settings.DragTipShown)
        {
            // Taught once, when it becomes relevant: the first time the pointer is on the button.
            _settings.DragTipShown = true;
            Save();
            ShowWidgetTip("You can drag this button if it covers your text.", sticky: true);
            return;
        }
        var st = Session.State;
        if (st.State is OverlayState.Partial or OverlayState.Offline && st.Detail != null)
            ShowWidgetTip(st.Detail);
        else
            ShowWidgetTip(TrayIcon.StateText(Status()));
    }

    private void ShowWidgetTip(string text, bool sticky = false)
    {
        if (_widget == null || _tip == null || !_widget.IsVisible) return;
        NativeMethods.GetWindowRect(_widget.Handle, out var r);
        var (work, scale) = NativeMethods.MonitorAt(r.Left, r.Top);
        _tip.ShowAt(text, Math.Max(work.Left, r.Left - 220 * scale), r.Bottom + 6 * scale);
        var (w, h) = _tip.PhysicalSize();
        double x = Math.Min(Math.Max(work.Left, r.Right - w), work.Right - w);
        double y = r.Bottom + 6 * scale + h > work.Bottom ? r.Top - h - 6 * scale : r.Bottom + 6 * scale;
        _tip.PlacePhysical(x, y);
        _tipTimer!.Stop();
        if (sticky) _tipTimer.Start();
    }

    // ---- settings and menu -----------------------------------------------

    private string? CurrentProcess() =>
        _candidate is { } c && !string.IsNullOrEmpty(c.Descriptor.ProcessName) ? c.Descriptor.ProcessName : null;

    private void ChangeSettings(Action<OverlaySettings> change)
    {
        change(_settings);
        Save();
        Evaluate();
    }

    private void ChangeEngine(Action<OverlaySettings> change)
    {
        change(_settings);
        Save();
        _engine.Configure(_settings, Version);
        Session.RecheckAll();
        UpdateTray();
    }

    private void AskHostedAddress()
    {
        var dialog = new EngineAddressDialog(_theme, _settings.HostedUrl);
        if (dialog.ShowDialog() == true && dialog.Address != null)
            ChangeEngine(s =>
            {
                s.HostedUrl = dialog.Address;
                s.Engine = EngineChoice.Hosted;
            });
    }

    private void Save()
    {
        try { SettingsStore.Save(_settingsPath, _settings); }
        catch (Exception e) when (e is System.IO.IOException or UnauthorizedAccessException) { }
    }

    private void OnPauseTick()
    {
        if (_settings.PausedUntil is { } until && DateTimeOffset.UtcNow >= until)
        {
            _settings.ResumeEverywhere();
            Save();
            _watcher?.Refresh();
        }
        UpdateTray();
    }

    private TrayStatus Status()
    {
        var st = Session.State;
        string? process = _rule is { Enabled: true } ? CurrentProcess() : null;
        string? label = _rule is { IsDefault: false } ? _rule.Label : process;
        return new TrayStatus(st.State, st.IssueCount, st.Detail,
            _settings.IsPausedEverywhere(DateTimeOffset.UtcNow), _settings.PausedUntil,
            label, process, process != null && _settings.IsAppPaused(process),
            _settings.Engine, _settings.HostedUrl, _settings.ShowPreferences, _theme.IsDark);
    }

    private void UpdateTray()
    {
        if (_tray == null || _session == null) return;
        _tray.Update(Status());
    }

    private void OnThemeChanged()
    {
        HideTransient();
        _overlay?.ThemeChanged();
        _widget?.ThemeChanged();
        UpdateTray();
    }

    public void Dispose()
    {
        _hoverTimer?.Stop();
        _remeasureTimer?.Stop();
        _measureSoon?.Stop();
        _pauseTimer?.Stop();
        _tipTimer?.Stop();
        Unhook();
        _watcher?.Dispose();
        _session?.Dispose();
        _tray?.Dispose();
        _engine.Dispose();
        _theme.Dispose();
        foreach (Window? w in new Window?[] { _overlay, _widget, _teaser, _card, _tip }) w?.Close();
    }
}
