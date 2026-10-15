using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Media;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Placement;
using Researchly.Overlay.Core.Tokens;
using Researchly.Overlay.Platform;

namespace Researchly.Overlay.Ui;

/// <summary>One suggestion's lines to underline, in physical screen pixels.</summary>
internal sealed record UnderlineItem(string Id, Category Category, IReadOnlyList<Box> Lines);

/// <summary>
/// The underline layer: a transparent, click-through, never-activated window
/// laid exactly over the focused field (docs/inline-review-design.md section 6,
/// step 6). Each suggestion is drawn under its text in its category's colour
/// and pattern (solid, dashed, dotted, wavy-dotted), so colour is never the
/// only cue. The hovered suggestion also gets a light tint.
/// </summary>
internal sealed class OverlayWindow : NonActivatingWindow
{
    private readonly UnderlineLayer _layer;

    public OverlayWindow(Theme theme) : base(clickThrough: true)
    {
        Title = "Researchly underlines";
        Width = 1;
        Height = 1;
        _layer = new UnderlineLayer(theme);
        Content = _layer;
    }

    /// <summary>Draws the items over <paramref name="field"/> (physical pixels).</summary>
    public void Render(Box field, IReadOnlyList<UnderlineItem> items, string? hoveredId)
    {
        if (field.IsEmpty || items.Count == 0)
        {
            Clear();
            return;
        }
        bool wasVisible = IsVisible;
        ShowQuietly();
        PlacePhysical(field.X, field.Y, field.Width, field.Height, keepZOrder: wasVisible);
        _layer.Set(field, items, hoveredId, DeviceScale);
    }

    public void SetHovered(string? id) => _layer.SetHovered(id);

    public void Clear()
    {
        _layer.Set(default, Array.Empty<UnderlineItem>(), null, 1);
        if (IsVisible) Hide();
    }

    public void ThemeChanged() => _layer.InvalidateVisual();
}

internal sealed class UnderlineLayer : FrameworkElement
{
    private readonly Theme _theme;
    private Box _origin;
    private IReadOnlyList<UnderlineItem> _items = Array.Empty<UnderlineItem>();
    private string? _hovered;
    private double _scale = 1;

    public UnderlineLayer(Theme theme)
    {
        _theme = theme;
        IsHitTestVisible = false;
    }

    public void Set(Box origin, IReadOnlyList<UnderlineItem> items, string? hovered, double scale)
    {
        _origin = origin;
        _items = items;
        _hovered = hovered;
        _scale = scale <= 0 ? 1 : scale;
        InvalidateVisual();
    }

    public void SetHovered(string? id)
    {
        if (_hovered == id) return;
        _hovered = id;
        InvalidateVisual();
    }

    protected override void OnRender(DrawingContext dc)
    {
        // Draw the least important first so a Correction's line is on top.
        for (int pass = (int)Category.Preference; pass >= (int)Category.Correction; pass--)
        {
            foreach (var item in _items)
            {
                if ((int)item.Category != pass) continue;
                var style = DesignTokens.For(item.Category);
                var line = _theme.Line(item.Category);
                foreach (var box in item.Lines)
                {
                    // Physical screen pixels -> DIPs inside this window.
                    var r = new Rect((box.X - _origin.X) / _scale, (box.Y - _origin.Y) / _scale, box.Width / _scale, box.Height / _scale);
                    if (r.Width < 1 || r.Height < 1) continue;
                    if (item.Id == _hovered)
                        dc.DrawRectangle(HoverTint(item.Category), null, r);
                    DrawUnderline(dc, style.Pattern, line, r);
                }
            }
        }
    }

    private Brush HoverTint(Category category)
    {
        var tint = DesignTokens.For(category).For(_theme.IsDark).Tint;
        var b = new SolidColorBrush(Theme.ToColor(tint.WithAlpha(_theme.IsDark ? 0.30 : 0.45)));
        b.Freeze();
        return b;
    }

    private static void DrawUnderline(DrawingContext dc, UnderlinePattern pattern, Brush brush, Rect r)
    {
        double y = Math.Round(r.Bottom - 1.5) + 0.5;
        double x0 = r.Left, x1 = r.Right;
        switch (pattern)
        {
            case UnderlinePattern.Solid:
                dc.DrawLine(Pen(brush, 2, null, PenLineCap.Flat), new Point(x0, y), new Point(x1, y));
                break;
            case UnderlinePattern.Dashed:
                // Dash lengths are in units of the pen thickness.
                dc.DrawLine(Pen(brush, 2, new DashStyle(new[] { 2.0, 1.5 }, 0), PenLineCap.Flat), new Point(x0, y), new Point(x1, y));
                break;
            case UnderlinePattern.Dotted:
                dc.DrawLine(Pen(brush, 2, new DashStyle(new[] { 0.0, 2.0 }, 0), PenLineCap.Round), new Point(x0 + 1, y), new Point(x1, y));
                break;
            case UnderlinePattern.WavyDotted:
                for (double x = x0 + 1; x <= x1; x += 3)
                {
                    double dy = Math.Sin((x - x0) / 6.0 * 2 * Math.PI) * 1.2;
                    dc.DrawEllipse(brush, null, new Point(x, y - 0.5 + dy), 0.95, 0.95);
                }
                break;
        }
    }

    private static Pen Pen(Brush brush, double thickness, DashStyle? dash, PenLineCap cap)
    {
        var p = new Pen(brush, thickness) { StartLineCap = cap, EndLineCap = cap, DashCap = cap };
        if (dash != null) p.DashStyle = dash;
        p.Freeze();
        return p;
    }
}
