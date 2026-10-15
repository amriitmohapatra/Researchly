using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Researchly.Overlay.Core.Session;
using Researchly.Overlay.Platform;

namespace Researchly.Overlay.Ui;

/// <summary>
/// The hover teaser (docs/inline-review-design.md section 2): the category,
/// what was noticed, and the revision if there is one. A click opens the
/// full card. Never activated.
/// </summary>
internal sealed class TeaserWindow : NonActivatingWindow
{
    private readonly Theme _theme;

    public TeaserWindow(Theme theme) : base(clickThrough: false)
    {
        _theme = theme;
        Title = "Researchly suggestion";
        SizeToContent = SizeToContent.WidthAndHeight;
        Cursor = Cursors.Hand;
        MouseLeftButtonUp += (_, _) => { if (SuggestionId != null) Clicked?.Invoke(SuggestionId); };
    }

    public string? SuggestionId { get; private set; }

    public event Action<string>? Clicked;

    /// <summary>Shows the teaser for <paramref name="s"/> just below a line (physical pixels).</summary>
    public void ShowFor(PlacedSuggestion s, double lineLeft, double lineBottom, double screenBottom)
    {
        SuggestionId = s.Id;
        var stack = new StackPanel { MaxWidth = 340 };
        stack.Children.Add(Parts.CategoryHeader(_theme, s.Suggestion.Category, s.Suggestion.SectionLabel));
        stack.Children.Add(Parts.Text(_theme, s.Suggestion.Message, 13));
        if (s.Suggestion.Replacements.Count > 0)
        {
            var revision = new TextBlock { Margin = new Thickness(0, 6, 0, 0), TextWrapping = TextWrapping.Wrap };
            revision.Inlines.Add(new System.Windows.Documents.Run("Revise to ") { Foreground = _theme.InkSecondaryBrush, FontFamily = Parts.Sans, FontSize = 12.5 });
            revision.Inlines.Add(new System.Windows.Documents.Run(s.Suggestion.Replacements[0]) { Foreground = _theme.InkBrush, FontFamily = Parts.Serif, FontSize = 14 });
            stack.Children.Add(revision);
        }
        stack.Children.Add(Parts.Text(_theme, "Click for the reason and the source.", 11.5, secondary: true));
        Content = Parts.Panel(_theme, stack, _theme.Line(s.Suggestion.Category));

        ShowQuietly();
        UpdateLayout();
        var (_, h) = PhysicalSize();
        double gap = 6 * DeviceScale;
        double y = lineBottom + gap;
        if (y + h > screenBottom) y = lineBottom - h - gap * 4; // flip above the line near the bottom of the screen
        PlacePhysical(lineLeft, y);
    }

    public void HideTeaser()
    {
        SuggestionId = null;
        if (IsVisible) Hide();
    }
}
