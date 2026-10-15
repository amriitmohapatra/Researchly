using System.Windows;
using System.Windows.Controls;
using Researchly.Overlay.Core.Settings;
using Researchly.Overlay.Platform;

namespace Researchly.Overlay.Ui;

/// <summary>
/// Asks for the hosted engine's address. The one Researchly window that takes
/// focus, because the writer opened it from the notification-area menu to type.
/// </summary>
internal sealed class EngineAddressDialog : Window
{
    private readonly TextBox _box;
    private readonly TextBlock _error;

    public EngineAddressDialog(Theme theme, string? current)
    {
        Title = "Researchly: hosted engine";
        SizeToContent = SizeToContent.WidthAndHeight;
        ResizeMode = ResizeMode.NoResize;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        Topmost = true;
        Background = theme.SurfaceBrush;

        var stack = new StackPanel { Margin = new Thickness(16), Width = 420 };
        stack.Children.Add(Parts.Text(theme, "The address of the hosted Researchly engine (it starts with https://). Text goes only to the engine you choose, is checked in memory and is not stored.", 12.5));
        _box = new TextBox { Text = current ?? "https://", Margin = new Thickness(0, 10, 0, 0), FontFamily = Parts.Sans, FontSize = 13, Padding = new Thickness(4) };
        stack.Children.Add(_box);
        _error = Parts.Text(theme, "", 12, secondary: true);
        _error.Visibility = Visibility.Collapsed;
        stack.Children.Add(_error);

        var buttons = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 14, 0, 0) };
        var ok = new Button { Content = "Use this engine", IsDefault = true, Padding = new Thickness(12, 4, 12, 4), Margin = new Thickness(0, 0, 8, 0) };
        var cancel = new Button { Content = "Cancel", IsCancel = true, Padding = new Thickness(12, 4, 12, 4) };
        ok.Click += (_, _) =>
        {
            if (EngineEndpoint.TryNormalise(_box.Text, out var url))
            {
                Address = url;
                DialogResult = true;
            }
            else
            {
                _error.Text = "Use an https:// address (plain http is allowed only for this computer).";
                _error.Visibility = Visibility.Visible;
            }
        };
        buttons.Children.Add(ok);
        buttons.Children.Add(cancel);
        stack.Children.Add(buttons);
        Content = stack;
        Loaded += (_, _) => { _box.Focus(); _box.SelectAll(); };
    }

    public string? Address { get; private set; }
}
