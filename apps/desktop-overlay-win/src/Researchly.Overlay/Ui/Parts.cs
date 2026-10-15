using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shapes;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Tokens;
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

    /// <summary>The category's icon and name: colour is never the only cue.</summary>
    public static StackPanel CategoryHeader(Theme theme, Category category)
    {
        var style = DesignTokens.For(category);
        var icon = new Path
        {
            Data = Geometry.Parse(style.IconPath),
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
            Text = style.Name,
            FontFamily = Sans,
            FontSize = 12.5,
            FontWeight = FontWeights.SemiBold,
            Foreground = theme.Ink(category),
            VerticalAlignment = VerticalAlignment.Center,
        };
        var panel = new StackPanel { Orientation = Orientation.Horizontal };
        panel.Children.Add(icon);
        panel.Children.Add(name);
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
