using System;
using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Tokens;

namespace Researchly.Overlay.Platform;

/// <summary>
/// Follows the Windows app theme (Settings, Personalisation, Colours, "Choose
/// your default app mode") and high contrast, and turns design tokens into
/// frozen WPF brushes.
/// </summary>
internal sealed class Theme : IDisposable
{
    private const string PersonalizeKey = @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize";

    public Theme()
    {
        Read();
        SystemEvents.UserPreferenceChanged += OnPreferenceChanged;
    }

    public bool IsDark { get; private set; }
    public bool IsHighContrast { get; private set; }

    public event Action? Changed;

    private void OnPreferenceChanged(object sender, UserPreferenceChangedEventArgs e)
    {
        if (e.Category is UserPreferenceCategory.General or UserPreferenceCategory.Color or UserPreferenceCategory.Accessibility or UserPreferenceCategory.VisualStyle)
        {
            bool dark = IsDark, hc = IsHighContrast;
            Read();
            if (dark != IsDark || hc != IsHighContrast)
                Application.Current?.Dispatcher.BeginInvoke(new Action(() => Changed?.Invoke()));
        }
    }

    private void Read()
    {
        IsHighContrast = SystemParameters.HighContrast;
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(PersonalizeKey);
            IsDark = key?.GetValue("AppsUseLightTheme") is int light && light == 0;
        }
        catch (Exception e) when (e is System.Security.SecurityException or UnauthorizedAccessException)
        {
            IsDark = false;
        }
    }

    /// <summary>True when animations should be kept still (Windows "Animation effects" off).</summary>
    public static bool ReducedMotion => !SystemParameters.ClientAreaAnimation;

    public SurfaceColours Surface => DesignTokens.Surface(IsDark);

    public Brush Brush(Rgba c) => Frozen(c);

    /// <summary>The underline colour for a category; in high contrast, the system's highlight colour.</summary>
    public Brush Line(Category category) =>
        IsHighContrast ? SystemColors.HighlightBrush : Frozen(DesignTokens.For(category).For(IsDark).Line);

    public Brush Ink(Category category) =>
        IsHighContrast ? SystemColors.WindowTextBrush : Frozen(DesignTokens.For(category).For(IsDark).Ink);

    public Brush Tint(Category category) =>
        IsHighContrast ? SystemColors.WindowBrush : Frozen(DesignTokens.For(category).For(IsDark).Tint);

    public Brush SurfaceBrush => IsHighContrast ? SystemColors.WindowBrush : Frozen(Surface.Surface);
    public Brush InkBrush => IsHighContrast ? SystemColors.WindowTextBrush : Frozen(Surface.Ink);
    public Brush InkSecondaryBrush => IsHighContrast ? SystemColors.GrayTextBrush : Frozen(Surface.InkSecondary);
    public Brush LineBrush => IsHighContrast ? SystemColors.WindowTextBrush : Frozen(Surface.Line);
    public Brush FocusBrush => IsHighContrast ? SystemColors.HighlightBrush : Frozen(Surface.Focus);

    public static Color ToColor(Rgba c) => Color.FromArgb(c.A, c.R, c.G, c.B);

    private static SolidColorBrush Frozen(Rgba c)
    {
        var b = new SolidColorBrush(ToColor(c));
        b.Freeze();
        return b;
    }

    public void Dispose() => SystemEvents.UserPreferenceChanged -= OnPreferenceChanged;
}
