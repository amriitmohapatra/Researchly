using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shapes;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Tokens;
using System.Collections.Generic;
using Researchly.Overlay.Platform;

namespace Researchly.Overlay.Ui;

/// <summary>Small building blocks shared by the teaser, the card and the tips.</summary>
internal static class Parts
{
    // Sans for the coach and the controls; serif for the writer's words (the revision),
    // as on the website.
    public static readonly FontFamily Sans = new("Segoe UI Variable Text, Segoe UI");
    public static readonly FontFamily Serif = new("Cambria, Georgia, Palatino Linotype, serif");

    /// <summary>A rounded panel in the surface colour with a hairline border.</summary>
    public static Border Panel(Theme theme, UIElement child, Brush? rail = null) => new()
    {
        Background = theme.SurfaceBrush,
        BorderBrush = theme.LineBrush,
        BorderThickness = new Thickness(1),
        CornerRadius = new CornerRadius(8),
        Padding = new Thickness(0),
        Child = rail == null
            ? new Border { Padding = new Thickness(12, 10, 12, 10), Child = child }
            : new Border
            {
                BorderBrush = rail,
                BorderThickness = new Thickness(4, 0, 0, 0),
                CornerRadius = new CornerRadius(8, 0, 0, 8),
                Padding = new Thickness(12, 10, 12, 12),
                Child = child,
            },
        SnapsToDevicePixels = true,
    };

    // The website's icon shapes (apps/web/components/CategoryIcon.tsx) as path data on a
    // 16 x 16 grid, keyed by the generated tokens' icon names; circles are two arcs.
    private static readonly Dictionary<string, string> IconPaths = new(StringComparer.Ordinal)
    {
        ["circle-cross"] = "M1.5,8 A6.5,6.5 0 1 1 14.5,8 A6.5,6.5 0 1 1 1.5,8 Z M5.5,5.5 L10.5,10.5 M10.5,5.5 L5.5,10.5",
        ["arrow-up"] = "M8,13 L8,3.5 M4,7.5 L8,3.5 L12,7.5",
        ["open-book"] = "M8,4.5 C6.6,3.4 4.6,3 2,3 L2,12.5 C4.6,12.5 6.6,12.9 8,14 C9.4,12.9 11.4,12.5 14,12.5 L14,3 C11.4,3 9.4,3.4 8,4.5 Z M8,4.5 L8,14",
        ["sliders"] = "M2.5,5 L4.1,5 M7.9,5 L13.5,5 M2.5,11 L8.6,11 M12.4,11 L13.5,11 M4.1,5 A1.9,1.9 0 1 1 7.9,5 A1.9,1.9 0 1 1 4.1,5 Z M8.6,11 A1.9,1.9 0 1 1 12.4,11 A1.9,1.9 0 1 1 8.6,11 Z",
    };

    /// <summary>The path data for a token icon name (an unknown one is drawn as the Improvement arrow).</summary>
    public static string IconPath(string icon) => IconPaths.TryGetValue(icon, out var d) ? d : IconPaths["arrow-up"];

    /// <summary>
    /// The category's icon and name (colour is never the only cue), and the section the advice
    /// assumed when there is one ("Methods"), as on the website's cards. Rule ids and internal
    /// rule names are never shown.
    /// </summary>
    public static StackPanel CategoryHeader(Theme theme, Category category, string? section = null)
    {
        var look = Looks.For(category);
        var icon = new Path
        {
            Data = Geometry.Parse(IconPath(look.Icon)),
            Stroke = theme.Ink(category),
            StrokeThickness = 1.5,
            StrokeStartLineCap = PenLineCap.Round,
            StrokeEndLineCap = PenLineCap.Round,
            StrokeLineJoin = PenLineJoin.Round,
            Width = 16,
            Height = 16,
            Stretch = Stretch.None,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, 6, 0),
        };
        var name = new TextBlock
        {
            Text = look.Label,
            FontFamily = Sans,
            FontSize = 12.5,
            FontWeight = FontWeights.SemiBold,
            Foreground = theme.Ink(category),
            VerticalAlignment = VerticalAlignment.Center,
        };
        var panel = new StackPanel { Orientation = Orientation.Horizontal };
        panel.Children.Add(icon);
        panel.Children.Add(name);
        if (section != null)
        {
            var sectionText = new TextBlock
            {
                Text = "· " + section,
                FontFamily = Sans,
                FontSize = 12.5,
                Foreground = theme.InkSecondaryBrush,
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(6, 0, 0, 0),
            };
            System.Windows.Automation.AutomationProperties.SetName(sectionText, "Section: " + section);
            panel.Children.Add(sectionText);
        }
        return panel;
    }

    public static TextBlock Text(Theme theme, string text, double size = 13, bool secondary = false, FontWeight? weight = null, FontFamily? family = null) => new()
    {
        Text = text,
        TextWrapping = TextWrapping.Wrap,
        FontFamily = family ?? Sans,
        FontSize = size,
        FontWeight = weight ?? FontWeights.Normal,
        Foreground = secondary ? theme.InkSecondaryBrush : theme.InkBrush,
        Margin = new Thickness(0, 4, 0, 0),
    };

    /// <summary>A flat button that never takes keyboard focus (the host keeps it).</summary>
    public static Button Button(Theme theme, string label, bool primary, Action onClick, Category? category = null)
    {
        var fg = primary ? theme.SurfaceBrush : theme.InkBrush;
        // The category's ink colour (not its line colour) keeps button text above 4.5:1.
        var bg = primary ? (category is { } c ? theme.Ink(c) : theme.FocusBrush) : Brushes.Transparent;
        var border = new FrameworkElementFactory(typeof(Border));
        border.SetValue(Border.BackgroundProperty, bg);
        border.SetValue(Border.BorderBrushProperty, primary ? bg : theme.LineBrush);
        border.SetValue(Border.BorderThicknessProperty, new Thickness(1));
        border.SetValue(Border.CornerRadiusProperty, new CornerRadius(6));
        border.SetValue(Border.PaddingProperty, new Thickness(10, 4, 10, 5));
        var content = new FrameworkElementFactory(typeof(ContentPresenter));
        content.SetValue(ContentPresenter.HorizontalAlignmentProperty, HorizontalAlignment.Center);
        content.SetValue(ContentPresenter.VerticalAlignmentProperty, VerticalAlignment.Center);
        border.AppendChild(content);

        var b = new Button
        {
            Content = new TextBlock { Text = label, FontFamily = Sans, FontSize = 12.5, Foreground = fg, FontWeight = primary ? FontWeights.SemiBold : FontWeights.Normal },
            Template = new ControlTemplate(typeof(Button)) { VisualTree = border },
            Focusable = false,
            IsTabStop = false,
            Cursor = Cursors.Hand,
            Margin = new Thickness(0, 0, 6, 0),
        };
        b.Click += (_, _) => onClick();
        return b;
    }
}

/// <summary>A small, non-activating text bubble: state details and the one-time drag tip.</summary>
internal sealed class TipWindow : NonActivatingWindow
{
    private readonly Theme _theme;

    public TipWindow(Theme theme) : base(clickThrough: true)
    {
        _theme = theme;
        Title = "Researchly tip";
        SizeToContent = SizeToContent.WidthAndHeight;
    }

    /// <summary>Shows <paramref name="text"/> with its top-left corner at a physical point.</summary>
    public void ShowAt(string text, double x, double y)
    {
        var block = Parts.Text(_theme, text, 12.5);
        block.Margin = new Thickness(0);
        block.MaxWidth = 300;
        Content = Parts.Panel(_theme, block);
        ShowQuietly();
        UpdateLayout();
        PlacePhysical(x, y);
    }
}
