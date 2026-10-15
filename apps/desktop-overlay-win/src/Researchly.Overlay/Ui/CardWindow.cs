using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Researchly.Overlay.Core.Session;
using Researchly.Overlay.Platform;

namespace Researchly.Overlay.Ui;

/// <summary>
/// The full card (docs/inline-review-design.md section 2): what was noticed,
/// the explanation in plain words, the why, and its named source (CLAUDE.md
/// rule 6), with Accept and "Not an issue". Arrows step through every
/// suggestion in the field, which makes the card the list too. Never activated:
/// the buttons work by mouse while the writer's app keeps the keyboard.
/// </summary>
internal sealed class CardWindow : NonActivatingWindow
{
    private readonly Theme _theme;
    private TextBlock? _status;

    public CardWindow(Theme theme) : base(clickThrough: false)
    {
        _theme = theme;
        Title = "Researchly card";
        SizeToContent = SizeToContent.WidthAndHeight;
    }

    public string? SuggestionId { get; private set; }

    public event Action<string, string>? AcceptRequested;   // suggestion id, replacement
    public event Action<string>? DismissRequested;          // "Not an issue"
    public event Action<int>? StepRequested;                // -1 previous, +1 next
    public event Action? CloseRequested;

    /// <summary>Shows the card for <paramref name="s"/> near a physical point.</summary>
    public void ShowFor(PlacedSuggestion s, int index, int count, double x, double y, (double Left, double Top, double Right, double Bottom) work)
    {
        SuggestionId = s.Id;
        var sug = s.Suggestion;
        var stack = new StackPanel { Width = 360 };

        var header = new DockPanel { LastChildFill = true };
        var close = Parts.Button(_theme, "Close", primary: false, () => CloseRequested?.Invoke());
        close.Margin = new Thickness(6, 0, 0, 0);
        DockPanel.SetDock(close, Dock.Right);
        header.Children.Add(close);
        if (count > 1)
        {
            var nav = new StackPanel { Orientation = Orientation.Horizontal, VerticalAlignment = VerticalAlignment.Center };
            nav.Children.Add(Parts.Button(_theme, "Previous", false, () => StepRequested?.Invoke(-1)));
            nav.Children.Add(new TextBlock { Text = $"{index + 1} of {count}", FontFamily = Parts.Sans, FontSize = 12, Foreground = _theme.InkSecondaryBrush, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 6, 0) });
            nav.Children.Add(Parts.Button(_theme, "Next", false, () => StepRequested?.Invoke(+1)));
            DockPanel.SetDock(nav, Dock.Right);
            header.Children.Add(nav);
        }
        header.Children.Add(Parts.CategoryHeader(_theme, sug.Category, sug.SectionLabel));
        stack.Children.Add(header);

        // The flagged words, in the writer's serif.
        stack.Children.Add(new TextBlock
        {
            Text = "“" + Trim(s.FlaggedText, 120) + "”",
            FontFamily = Parts.Serif,
            FontSize = 14,
            Foreground = _theme.InkSecondaryBrush,
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 8, 0, 0),
        });
        stack.Children.Add(Parts.Text(_theme, sug.Message, 13.5, weight: FontWeights.SemiBold));
        if (!string.IsNullOrWhiteSpace(sug.Plain)) stack.Children.Add(Parts.Text(_theme, sug.Plain, 13));
        if (!string.IsNullOrWhiteSpace(sug.Why))
        {
            stack.Children.Add(Label("Why"));
            stack.Children.Add(Parts.Text(_theme, sug.Why, 12.5));
        }
        if (!string.IsNullOrWhiteSpace(sug.Source))
        {
            stack.Children.Add(Label("Source"));
            stack.Children.Add(Parts.Text(_theme, sug.Source, 12.5, secondary: true));
        }

        var actions = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
        bool first = true;
        foreach (var r in Limit(sug.Replacements, 3))
        {
            string replacement = r;
            string label = replacement.Length == 0 ? "Delete" : "Accept: " + Trim(replacement, 40);
            var button = Parts.Button(_theme, label, first, () => AcceptRequested?.Invoke(s.Id, replacement), sug.Category);
            button.Margin = new Thickness(0, 0, 6, 6);
            actions.Children.Add(button);
            first = false;
        }
        var dismiss = Parts.Button(_theme, "Not an issue", false, () => DismissRequested?.Invoke(s.Id));
        dismiss.Margin = new Thickness(0, 0, 6, 6);
        actions.Children.Add(dismiss);
        stack.Children.Add(actions);

        _status = Parts.Text(_theme, "", 12, secondary: true);
        _status.Visibility = Visibility.Collapsed;
        stack.Children.Add(_status);

        Content = Parts.Panel(_theme, stack, _theme.Rail(sug.Category));
        ShowQuietly();
        UpdateLayout();

        // Keep the card on screen.
        var (w, h) = PhysicalSize();
        double px = Math.Min(Math.Max(x, work.Left), work.Right - w);
        double py = y + h > work.Bottom ? Math.Max(work.Top, y - h - 40 * DeviceScale) : y;
        PlacePhysical(px, py);
    }

    public void ShowStatus(string text)
    {
        if (_status == null) return;
        _status.Text = text;
        _status.Visibility = string.IsNullOrEmpty(text) ? Visibility.Collapsed : Visibility.Visible;
    }

    public void HideCard()
    {
        SuggestionId = null;
        if (IsVisible) Hide();
    }

    private TextBlock Label(string text) => new()
    {
        Text = text,
        FontFamily = Parts.Sans,
        FontSize = 11.5,
        FontWeight = FontWeights.SemiBold,
        Foreground = _theme.InkSecondaryBrush,
        Margin = new Thickness(0, 10, 0, 0),
    };

    private static string Trim(string s, int max) => s.Length <= max ? s : s.Substring(0, max - 1) + "…";

    private static IEnumerable<string> Limit(IReadOnlyList<string> list, int max)
    {
        for (int i = 0; i < list.Count && i < max; i++) yield return list[i];
    }
}
