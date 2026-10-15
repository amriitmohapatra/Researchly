using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;
using Researchly.Overlay.Core.Settings;
using Researchly.Overlay.Core.State;
using Researchly.Overlay.Core.Tokens;
using Rgba = Researchly.Design.Rgba;
using Researchly.Overlay.Native;

namespace Researchly.Overlay.Tray;

/// <summary>What the menu needs to know to draw itself.</summary>
internal sealed record TrayStatus(OverlayState State, int Count, string? Detail, bool PausedEverywhere, DateTimeOffset? PausedUntil,
    string? CurrentAppLabel, string? CurrentProcess, bool CurrentAppPaused, EngineChoice Engine, string? HostedUrl, bool ShowPreferences, bool Dark);

/// <summary>
/// The notification-area icon and its menu: state, pause (1 hour, until
/// tomorrow, for this app), engine choice (hosted or "This computer"),
/// Preferences on or off, retry, privacy, quit.
/// </summary>
internal sealed class TrayIcon : IDisposable
{
    private readonly NotifyIcon _icon;
    private readonly ContextMenuStrip _menu;
    private IntPtr _hIcon;
    private TrayStatus? _status;

    public TrayIcon()
    {
        _menu = new ContextMenuStrip { ShowImageMargin = false, ShowCheckMargin = true };
        _menu.Opening += (_, _) => Rebuild();
        _icon = new NotifyIcon { Text = "Researchly", ContextMenuStrip = _menu, Visible = true };
        _icon.MouseUp += (_, e) =>
        {
            if (e.Button == MouseButtons.Left) LeftClicked?.Invoke();
        };
    }

    public event Action? PauseHour;
    public event Action? PauseTomorrow;
    public event Action? PauseApp;
    public event Action? Resume;
    public event Action? ResumeApp;
    public event Action? UseThisComputer;
    public event Action? UseHosted;
    public event Action? SetHostedAddress;
    public event Action? TogglePreferences;
    public event Action? RetryNow;
    public event Action? ShowPrivacy;
    public event Action? Quit;
    public event Action? LeftClicked;

    public void Update(TrayStatus status)
    {
        _status = status;
        _icon.Text = Truncate("Researchly: " + StateText(status), 63);
        SetIcon(status);
    }

    public static string StateText(TrayStatus s)
    {
        if (s.PausedEverywhere) return s.PausedUntil is { } until ? $"Paused until {until.ToLocalTime():HH:mm}" : "Paused";
        if (s.CurrentAppPaused) return $"Paused in {s.CurrentAppLabel}";
        return s.State switch
        {
            OverlayState.Hidden => "Ready",
            OverlayState.Checking => "Checking",
            OverlayState.Issues => s.Count == 1 ? "1 suggestion" : $"{s.Count} suggestions",
            OverlayState.Clear => "No suggestions",
            OverlayState.Partial => "Some checks unavailable",
            OverlayState.Offline => "Can’t check right now",
            _ => "",
        };
    }

    private void Rebuild()
    {
        var s = _status;
        _menu.Items.Clear();
        if (s == null) return;

        _menu.Items.Add(new ToolStripMenuItem("Researchly: " + StateText(s)) { Enabled = false });
        if ((s.State is OverlayState.Partial or OverlayState.Offline) && !string.IsNullOrEmpty(s.Detail))
            _menu.Items.Add(new ToolStripMenuItem(Truncate(s.Detail!, 90)) { Enabled = false });
        if (s.State == OverlayState.Offline)
            _menu.Items.Add(Item("Try again now", () => RetryNow?.Invoke()));
        _menu.Items.Add(new ToolStripSeparator());

        if (s.PausedEverywhere)
        {
            _menu.Items.Add(Item("Resume", () => Resume?.Invoke()));
        }
        else
        {
            _menu.Items.Add(Item("Pause for 1 hour", () => PauseHour?.Invoke()));
            _menu.Items.Add(Item("Pause until tomorrow", () => PauseTomorrow?.Invoke()));
        }
        if (!string.IsNullOrEmpty(s.CurrentProcess))
        {
            string app = string.IsNullOrEmpty(s.CurrentAppLabel) ? s.CurrentProcess! : s.CurrentAppLabel!;
            _menu.Items.Add(s.CurrentAppPaused
                ? Item($"Resume in {app}", () => ResumeApp?.Invoke())
                : Item($"Pause in {app}", () => PauseApp?.Invoke()));
        }
        _menu.Items.Add(new ToolStripSeparator());

        var engine = new ToolStripMenuItem("Engine");
        engine.DropDownItems.Add(Item("This computer (" + OverlaySettings.LocalEngineUrl.Replace("http://", "") + ")",
            () => UseThisComputer?.Invoke(), s.Engine == EngineChoice.ThisComputer));
        string hostedLabel = Uri.TryCreate(s.HostedUrl, UriKind.Absolute, out var hosted)
            ? "Hosted (" + Truncate(hosted.Host, 40) + ")"
            : "Hosted (no address yet)";
        engine.DropDownItems.Add(Item(hostedLabel, () => UseHosted?.Invoke(), s.Engine == EngineChoice.Hosted));
        engine.DropDownItems.Add(Item("Set hosted address…", () => SetHostedAddress?.Invoke()));
        _menu.Items.Add(engine);
        _menu.Items.Add(Item("Show Preferences", () => TogglePreferences?.Invoke(), s.ShowPreferences));
        _menu.Items.Add(new ToolStripSeparator());
        _menu.Items.Add(Item("Privacy…", () => ShowPrivacy?.Invoke()));
        _menu.Items.Add(Item("Quit Researchly", () => Quit?.Invoke()));
    }

    private static ToolStripMenuItem Item(string text, Action onClick, bool isChecked = false)
    {
        var item = new ToolStripMenuItem(text) { Checked = isChecked };
        item.Click += (_, _) => onClick();
        return item;
    }

    /// <summary>Draws the icon for the state: a disc in the state's colour with the same shapes as the widget.</summary>
    private void SetIcon(TrayStatus s)
    {
        const int size = 32;
        using var bmp = new Bitmap(size, size);
        using (var g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Color.Transparent);
            bool paused = s.PausedEverywhere || s.CurrentAppPaused;
            var accent = ToColor(Looks.WidgetColour(paused ? OverlayState.Offline : s.State, s.Dark));
            using var pen = new Pen(accent, 3.5f) { StartCap = LineCap.Round, EndCap = LineCap.Round };
            using var brush = new SolidBrush(accent);
            var disc = new Rectangle(3, 3, size - 7, size - 7);
            if (paused)
            {
                g.DrawEllipse(pen, disc);
                g.FillRectangle(brush, 11, 10, 3, 12);
                g.FillRectangle(brush, 18, 10, 3, 12);
            }
            else
            {
                switch (s.State)
                {
                    case OverlayState.Offline:
                        g.DrawEllipse(pen, disc);
                        g.DrawLine(pen, 10, 22, 22, 10);
                        break;
                    case OverlayState.Partial:
                        g.DrawEllipse(pen, disc);
                        g.FillPolygon(brush, new[] { new Point(16, 8), new Point(24, 23), new Point(8, 23) });
                        break;
                    case OverlayState.Issues:
                        g.FillEllipse(brush, disc);
                        break;
                    case OverlayState.Clear:
                        g.DrawEllipse(pen, disc);
                        g.DrawLines(pen, new[] { new Point(10, 16), new Point(14, 21), new Point(22, 11) });
                        break;
                    default: // hidden (ready) and checking
                        g.DrawEllipse(pen, disc);
                        break;
                }
            }
        }
        IntPtr h = bmp.GetHicon();
        var old = _hIcon;
        _icon.Icon = Icon.FromHandle(h);
        _hIcon = h;
        if (old != IntPtr.Zero) NativeMethods.DestroyIcon(old);
    }

    private static Color ToColor(Rgba c) => Color.FromArgb(c.A, c.R, c.G, c.B);

    private static string Truncate(string s, int max) => s.Length <= max ? s : s.Substring(0, max - 1) + "…";

    public void Dispose()
    {
        _icon.Visible = false;
        _icon.Dispose();
        _menu.Dispose();
        if (_hIcon != IntPtr.Zero) NativeMethods.DestroyIcon(_hIcon);
    }
}
