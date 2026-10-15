using System;
using System.Globalization;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;
using Researchly.Overlay.Core.State;
using Researchly.Overlay.Core.Tokens;
using Researchly.Overlay.Native;
using Researchly.Overlay.Platform;

namespace Researchly.Overlay.Ui;

/// <summary>
/// The field widget: a small round mark pinned to a corner of the focused
/// field (docs/inline-review-design.md section 1, item 3, and section 3). Each
/// of the six states has its own shape, not just a colour: a turning ring
/// (checking; still under reduced motion), a count badge (issues), a tick
/// (clear), a warning sign (partial), a crossed-out mark (offline), and
/// nothing at all (hidden). The writer can drag it; a click opens the card.
/// Never activated.
/// </summary>
internal sealed class FieldWidget : NonActivatingWindow
{
    public const double SizeDip = 26;
    private const double DragThresholdPx = 4;

    private readonly WidgetGlyph _glyph;
    private bool _pressed;
    private bool _dragging;
    private NativeMethods.POINT _pressCursor;
    private NativeMethods.RECT _pressWindow;

    public FieldWidget(Theme theme) : base(clickThrough: false)
    {
        Title = "Researchly";
        Width = SizeDip;
        Height = SizeDip;
        _glyph = new WidgetGlyph(theme);
        Content = _glyph;
        Cursor = Cursors.Hand;
        MouseLeftButtonDown += OnDown;
        MouseMove += OnMove;
        MouseLeftButtonUp += OnUp;
        MouseEnter += (_, _) => Hovered?.Invoke(true);
        MouseLeave += (_, _) => Hovered?.Invoke(false);
    }

    public event Action? Clicked;
    /// <summary>The writer finished dragging; the offset moved, in physical pixels.</summary>
    public event Action<double, double>? Dragged;
    public event Action<bool>? Hovered;

    public bool IsDragging => _dragging;

    public void SetState(OverlayState state, int count) => _glyph.Set(state, count);

    public void ThemeChanged() => _glyph.InvalidateVisual();

    private void OnDown(object sender, MouseButtonEventArgs e)
    {
        _pressed = true;
        _dragging = false;
        NativeMethods.GetCursorPos(out _pressCursor);
        NativeMethods.GetWindowRect(Handle, out _pressWindow);
        CaptureMouse();
        e.Handled = true;
    }

    private void OnMove(object sender, MouseEventArgs e)
    {
        if (!_pressed) return;
        NativeMethods.GetCursorPos(out var p);
        double dx = p.X - _pressCursor.X, dy = p.Y - _pressCursor.Y;
        if (!_dragging && Math.Abs(dx) < DragThresholdPx && Math.Abs(dy) < DragThresholdPx) return;
        _dragging = true;
        PlacePhysical(_pressWindow.Left + dx, _pressWindow.Top + dy);
    }

    private void OnUp(object sender, MouseButtonEventArgs e)
    {
        if (!_pressed) return;
        _pressed = false;
        ReleaseMouseCapture();
        if (_dragging)
        {
            NativeMethods.GetCursorPos(out var p);
            _dragging = false;
            Dragged?.Invoke(p.X - _pressCursor.X, p.Y - _pressCursor.Y);
        }
        else
        {
            Clicked?.Invoke();
        }
        e.Handled = true;
    }
}

internal sealed class WidgetGlyph : FrameworkElement
{
    private readonly Theme _theme;
    private readonly DispatcherTimer _spin;
    private OverlayState _state = OverlayState.Hidden;
    private int _count;
    private double _angle;

    public WidgetGlyph(Theme theme)
    {
        _theme = theme;
        _spin = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(60) };
        _spin.Tick += (_, _) =>
        {
            _angle = (_angle + 24) % 360;
            InvalidateVisual();
        };
    }

    public void Set(OverlayState state, int count)
    {
        _state = state;
        _count = count;
        if (state == OverlayState.Checking && !Theme.ReducedMotion) _spin.Start(); else _spin.Stop();
        InvalidateVisual();
    }

    protected override void OnRender(DrawingContext dc)
    {
        if (_state == OverlayState.Hidden) return;
        double size = Math.Min(ActualWidth, ActualHeight);
        if (size <= 0) size = FieldWidget.SizeDip;
        var c = new Point(size / 2, size / 2);
        double r = size / 2 - 2;
        var accent = _theme.Brush(DesignTokens.WidgetColour(_state, _theme.IsDark));
        var surface = _theme.SurfaceBrush;
        var ring = new Pen(accent, 2);
        ring.Freeze();

        // A surface disc behind every state keeps the mark legible over any text.
        dc.DrawEllipse(surface, new Pen(_theme.LineBrush, 1), c, r, r);

        switch (_state)
        {
            case OverlayState.Checking:
                DrawArc(dc, ring, c, r - 3, _angle, 270);
                break;
            case OverlayState.Issues:
                dc.DrawEllipse(accent, null, c, r - 1, r - 1);
                DrawCount(dc, c, _count, surface);
                break;
            case OverlayState.Clear:
                dc.DrawEllipse(null, ring, c, r - 2, r - 2);
                var tick = new StreamGeometry();
                using (var g = tick.Open())
                {
                    g.BeginFigure(new Point(c.X - 4.5, c.Y + 0.5), false, false);
                    g.LineTo(new Point(c.X - 1.2, c.Y + 3.8), true, true);
                    g.LineTo(new Point(c.X + 5, c.Y - 3.5), true, true);
                }
                tick.Freeze();
                dc.DrawGeometry(null, Thick(accent, 2.2), tick);
                break;
            case OverlayState.Partial:
                dc.DrawEllipse(null, ring, c, r - 2, r - 2);
                if (_count > 0) DrawCount(dc, c, _count, _theme.InkBrush);
                DrawWarning(dc, new Point(size - 6.5, size - 6.5), accent, surface);
                break;
            case OverlayState.Offline:
                dc.DrawEllipse(null, ring, c, r - 2, r - 2);
                dc.DrawLine(Thick(accent, 2.2), new Point(c.X - 5.5, c.Y + 5.5), new Point(c.X + 5.5, c.Y - 5.5));
                break;
        }
    }

    private static Pen Thick(Brush b, double t)
    {
        var p = new Pen(b, t) { StartLineCap = PenLineCap.Round, EndLineCap = PenLineCap.Round, LineJoin = PenLineJoin.Round };
        p.Freeze();
        return p;
    }

    private void DrawCount(DrawingContext dc, Point c, int count, Brush brush)
    {
        string text = count > 99 ? "99+" : count.ToString(CultureInfo.InvariantCulture);
        var ft = new FormattedText(text, CultureInfo.InvariantCulture, FlowDirection.LeftToRight,
            new Typeface(Parts.Sans, FontStyles.Normal, FontWeights.Bold, FontStretches.Normal),
            text.Length > 2 ? 8.5 : 11, brush, VisualTreeHelper.GetDpi(this).PixelsPerDip);
        dc.DrawText(ft, new Point(c.X - ft.Width / 2, c.Y - ft.Height / 2));
    }

    private static void DrawWarning(DrawingContext dc, Point centre, Brush fill, Brush mark)
    {
        var tri = new StreamGeometry();
        using (var g = tri.Open())
        {
            g.BeginFigure(new Point(centre.X, centre.Y - 5), true, true);
            g.LineTo(new Point(centre.X + 5.5, centre.Y + 4.5), true, true);
            g.LineTo(new Point(centre.X - 5.5, centre.Y + 4.5), true, true);
        }
        tri.Freeze();
        dc.DrawGeometry(fill, null, tri);
        dc.DrawLine(Thick(mark, 1.4), new Point(centre.X, centre.Y - 2), new Point(centre.X, centre.Y + 1.2));
        dc.DrawEllipse(mark, null, new Point(centre.X, centre.Y + 3), 0.8, 0.8);
    }

    private static void DrawArc(DrawingContext dc, Pen pen, Point c, double r, double startDeg, double sweepDeg)
    {
        double a0 = startDeg * Math.PI / 180, a1 = (startDeg + sweepDeg) * Math.PI / 180;
        var p0 = new Point(c.X + r * Math.Cos(a0), c.Y + r * Math.Sin(a0));
        var p1 = new Point(c.X + r * Math.Cos(a1), c.Y + r * Math.Sin(a1));
        var arc = new StreamGeometry();
        using (var g = arc.Open())
        {
            g.BeginFigure(p0, false, false);
            g.ArcTo(p1, new Size(r, r), 0, sweepDeg > 180, SweepDirection.Clockwise, true, true);
        }
        arc.Freeze();
        dc.DrawGeometry(null, pen, arc);
    }
}
