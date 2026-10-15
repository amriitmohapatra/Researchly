using System;
using System.Collections.Generic;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.State;

namespace Researchly.Overlay.Core.Tokens;

// REPLACE WHEN GENERATED: docs/inline-review-design.md section 4 makes
// packages/design-tokens/tokens.json the single source, with a generator that
// writes a C# file for this client. That package did not exist when this
// client was written, so these values are copied by hand from the website's
// category colours (apps/web/app/globals.css, Okabe-Ito derived). When the
// generated file lands, delete this class and point the shell at it; the
// shape (per category: line, ink, tint, light and dark; pattern; icon) is
// meant to match.

/// <summary>An sRGB colour with alpha, platform-neutral.</summary>
public readonly record struct Rgba(byte R, byte G, byte B, byte A = 255)
{
    public static Rgba Hex(string hex)
    {
        hex = hex.TrimStart('#');
        if (hex.Length != 6 && hex.Length != 8) throw new FormatException($"Not a colour: #{hex}");
        byte P(int i) => Convert.ToByte(hex.Substring(i, 2), 16);
        return hex.Length == 6 ? new Rgba(P(0), P(2), P(4)) : new Rgba(P(0), P(2), P(4), P(6));
    }

    public Rgba WithAlpha(double alpha) => this with { A = (byte)Math.Round(Math.Clamp(alpha, 0, 1) * 255) };

    /// <summary>WCAG relative luminance.</summary>
    public double Luminance()
    {
        static double Ch(byte c)
        {
            double s = c / 255.0;
            return s <= 0.03928 ? s / 12.92 : Math.Pow((s + 0.055) / 1.055, 2.4);
        }
        return 0.2126 * Ch(R) + 0.7152 * Ch(G) + 0.0722 * Ch(B);
    }

    /// <summary>WCAG contrast ratio between two opaque colours.</summary>
    public static double Contrast(Rgba a, Rgba b)
    {
        double la = a.Luminance(), lb = b.Luminance();
        return (Math.Max(la, lb) + 0.05) / (Math.Min(la, lb) + 0.05);
    }

    public override string ToString() => A == 255 ? $"#{R:x2}{G:x2}{B:x2}" : $"#{R:x2}{G:x2}{B:x2}{A:x2}";
}

/// <summary>How an underline is drawn when colour is not enough (section 4).</summary>
public enum UnderlinePattern { Solid, Dashed, Dotted, WavyDotted }

/// <summary>One theme's colours for a category.</summary>
/// <param name="Line">Underline and rail colour.</param>
/// <param name="Ink">Text colour for the category's name on a card.</param>
/// <param name="Tint">Background tint for highlights and badges.</param>
public sealed record CategoryColours(Rgba Line, Rgba Ink, Rgba Tint);

/// <summary>Everything the client needs to paint a category.</summary>
public sealed record CategoryStyle(
    Category Category,
    string Name,
    string Plural,
    UnderlinePattern Pattern,
    CategoryColours Light,
    CategoryColours Dark,
    string IconPath)
{
    public CategoryColours For(bool dark) => dark ? Dark : Light;
}

/// <summary>Surface colours for the client's own windows (cards, teasers, widget).</summary>
public sealed record SurfaceColours(Rgba Background, Rgba Surface, Rgba Ink, Rgba InkSecondary, Rgba Line, Rgba Focus, Rgba Warning, Rgba Offline);

/// <summary>The design tokens this client uses.</summary>
public static class DesignTokens
{
    // Icon shapes are the website's own (apps/web/components/CategoryIcon.tsx),
    // as path data on a 16 x 16 grid; circles are written as two arcs.
    private const string CorrectionIcon = "M1.5,8 A6.5,6.5 0 1 1 14.5,8 A6.5,6.5 0 1 1 1.5,8 Z M5.5,5.5 L10.5,10.5 M10.5,5.5 L5.5,10.5";
    private const string ImprovementIcon = "M8,13 L8,3.5 M4,7.5 L8,3.5 L12,7.5";
    private const string ConventionIcon = "M8,4.5 C6.6,3.4 4.6,3 2,3 L2,12.5 C4.6,12.5 6.6,12.9 8,14 C9.4,12.9 11.4,12.5 14,12.5 L14,3 C11.4,3 9.4,3.4 8,4.5 Z M8,4.5 L8,14";
    private const string PreferenceIcon = "M2.5,5 L4.1,5 M7.9,5 L13.5,5 M2.5,11 L8.6,11 M12.4,11 L13.5,11 M4.1,5 A1.9,1.9 0 1 1 7.9,5 A1.9,1.9 0 1 1 4.1,5 Z M8.6,11 A1.9,1.9 0 1 1 12.4,11 A1.9,1.9 0 1 1 8.6,11 Z";

    public static readonly CategoryStyle Correction = new(
        Category.Correction, "Correction", "Corrections", UnderlinePattern.Solid,
        Light: new(Rgba.Hex("#d55e00"), Rgba.Hex("#9e3b00"), Rgba.Hex("#fbe4d6")),
        Dark: new(Rgba.Hex("#f08a4b"), Rgba.Hex("#ffa070"), new Rgba(213, 94, 0, 66)),
        CorrectionIcon);

    public static readonly CategoryStyle Improvement = new(
        Category.Improvement, "Improvement", "Improvements", UnderlinePattern.Dashed,
        Light: new(Rgba.Hex("#0072b2"), Rgba.Hex("#005a8f"), Rgba.Hex("#dcebf6")),
        Dark: new(Rgba.Hex("#56b4e9"), Rgba.Hex("#86c8f2"), new Rgba(0, 114, 178, 82)),
        ImprovementIcon);

    public static readonly CategoryStyle Convention = new(
        Category.Convention, "Convention", "Conventions", UnderlinePattern.Dotted,
        Light: new(Rgba.Hex("#009e73"), Rgba.Hex("#00694d"), Rgba.Hex("#d6efe5")),
        Dark: new(Rgba.Hex("#3cc196"), Rgba.Hex("#66d4b0"), new Rgba(0, 158, 115, 66)),
        ConventionIcon);

    public static readonly CategoryStyle Preference = new(
        Category.Preference, "Preference", "Preferences", UnderlinePattern.WavyDotted,
        Light: new(Rgba.Hex("#cc79a7"), Rgba.Hex("#8a3a69"), Rgba.Hex("#f6e2ed")),
        Dark: new(Rgba.Hex("#d88bb8"), Rgba.Hex("#eaa8cd"), new Rgba(204, 121, 167, 66)),
        PreferenceIcon);

    public static readonly IReadOnlyList<CategoryStyle> All = new[] { Correction, Improvement, Convention, Preference };

    public static CategoryStyle For(Category category) => category switch
    {
        Category.Correction => Correction,
        Category.Improvement => Improvement,
        Category.Convention => Convention,
        Category.Preference => Preference,
        _ => Improvement,
    };

    // Surfaces: --bg, --surface, --ink, --ink-2, --line, --focus from globals.css.
    // Warning and offline have no website token yet: warning is Okabe-Ito orange
    // (the palette the categories come from); offline is --line-strong.
    public static readonly SurfaceColours LightSurface = new(
        Background: Rgba.Hex("#f4f5f3"), Surface: Rgba.Hex("#ffffff"), Ink: Rgba.Hex("#1b1f24"),
        InkSecondary: Rgba.Hex("#4a515b"), Line: Rgba.Hex("#d5d9d4"), Focus: Rgba.Hex("#1f5fbf"),
        Warning: Rgba.Hex("#a86a00"), Offline: Rgba.Hex("#858b93"));

    public static readonly SurfaceColours DarkSurface = new(
        Background: Rgba.Hex("#14161a"), Surface: Rgba.Hex("#1b1e23"), Ink: Rgba.Hex("#e9e7e2"),
        InkSecondary: Rgba.Hex("#aeb3bd"), Line: Rgba.Hex("#353a44"), Focus: Rgba.Hex("#8ab4ff"),
        Warning: Rgba.Hex("#e69f00"), Offline: Rgba.Hex("#7d838f"));

    public static SurfaceColours Surface(bool dark) => dark ? DarkSurface : LightSurface;

    /// <summary>The colour the field widget uses for a state.</summary>
    public static Rgba WidgetColour(OverlayState state, bool dark) => state switch
    {
        OverlayState.Partial => Surface(dark).Warning,
        OverlayState.Offline => Surface(dark).Offline,
        _ => Surface(dark).Focus,
    };
}
