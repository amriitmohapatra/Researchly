using System;
using System.Collections.Generic;
using Researchly.Overlay.Core.Eligibility;
using Researchly.Overlay.Core.Settings;

namespace Researchly.Overlay.Core.Placement;

/// <summary>A rectangle in one coordinate space (the shell decides which: physical pixels or DIPs).</summary>
public readonly record struct Box(double X, double Y, double Width, double Height)
{
    public double Right => X + Width;
    public double Bottom => Y + Height;
    public bool IsEmpty => Width <= 0 || Height <= 0;

    public Box Intersect(Box other)
    {
        double x = Math.Max(X, other.X), y = Math.Max(Y, other.Y);
        double r = Math.Min(Right, other.Right), b = Math.Min(Bottom, other.Bottom);
        return r <= x || b <= y ? new Box(x, y, 0, 0) : new Box(x, y, r - x, b - y);
    }

    public bool Contains(double px, double py) => px >= X && px < Right && py >= Y && py < Bottom;

    public Box Scale(double factor) => new(X * factor, Y * factor, Width * factor, Height * factor);
}

/// <summary>
/// Where the field widget goes (docs/inline-review-design.md section 1, item 3):
/// pinned to a corner of the focused field, inset by the app rule's offset,
/// never in a corner the rule forbids, moved by the writer's drag, and kept
/// inside the visible work area.
/// </summary>
public static class WidgetPlacement
{
    private static readonly Corner[] Preference = { Corner.BottomRight, Corner.TopRight, Corner.BottomLeft, Corner.TopLeft };

    /// <summary>The rule's corner, or the first allowed one in a fixed order when the rule's is forbidden.</summary>
    public static Corner ChooseCorner(AppRule rule)
    {
        if (!Contains(rule.ForbiddenCorners, rule.WidgetCorner)) return rule.WidgetCorner;
        foreach (var c in Preference)
            if (!Contains(rule.ForbiddenCorners, c)) return c;
        return rule.WidgetCorner; // every corner forbidden: a data error; keep the rule's choice
    }

    /// <summary>
    /// The widget's top-left corner. All inputs are in the same units (DIPs, or
    /// physical pixels with <paramref name="scale"/> = DPI / 96 applied to the offsets).
    /// </summary>
    /// <param name="field">The field's bounds.</param>
    /// <param name="widgetSize">The widget's width and height.</param>
    /// <param name="rule">The app rule.</param>
    /// <param name="nudge">The writer's drag for this app, in DIPs; null when never dragged.</param>
    /// <param name="workArea">The monitor's work area; the widget is kept inside it.</param>
    /// <param name="scale">Multiplies the DIP offsets and nudge (1 when everything is in DIPs).</param>
    public static (double X, double Y) Place(Box field, double widgetSize, AppRule rule, WidgetNudge? nudge, Box workArea, double scale = 1.0)
    {
        var corner = ChooseCorner(rule);
        double ox = rule.WidgetOffsetX * scale, oy = rule.WidgetOffsetY * scale;
        // A field too small for the inset puts the widget just outside it, on the same side.
        bool narrow = field.Width < widgetSize + 2 * ox;
        bool shallow = field.Height < widgetSize + 2 * oy;

        double x = corner is Corner.TopLeft or Corner.BottomLeft
            ? (narrow ? field.X - widgetSize - 2 * scale : field.X + ox)
            : (narrow ? field.Right + 2 * scale : field.Right - ox - widgetSize);
        double y = corner is Corner.TopLeft or Corner.TopRight
            ? field.Y + oy
            : field.Bottom - oy - widgetSize;
        if (shallow)
            y = field.Y + Math.Max(0, (field.Height - widgetSize) / 2);

        if (nudge != null)
        {
            x += nudge.Dx * scale;
            y += nudge.Dy * scale;
        }

        if (!workArea.IsEmpty)
        {
            x = Math.Clamp(x, workArea.X, Math.Max(workArea.X, workArea.Right - widgetSize));
            y = Math.Clamp(y, workArea.Y, Math.Max(workArea.Y, workArea.Bottom - widgetSize));
        }
        return (x, y);
    }

    private static bool Contains(IReadOnlyList<Corner> list, Corner c)
    {
        foreach (var x in list) if (x == c) return true;
        return false;
    }
}
