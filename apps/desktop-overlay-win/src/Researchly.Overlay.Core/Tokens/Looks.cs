using System;
using System.Collections.Generic;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.State;
using Design = Researchly.Design;

namespace Researchly.Overlay.Core.Tokens;

// The client's view of the generated design tokens
// (packages/design-tokens/dist/ResearchlyTokens.cs, from tokens.json; PLAN
// S4d R2), which the core compiles as they are. Every colour, underline
// pattern, icon name and state word comes from there; this file only maps
// the engine's values onto it and adds the contrast arithmetic the tests use.

/// <summary>Surface colours for the client's own windows (cards, teasers, widget), for one theme.</summary>
public sealed record SurfaceColours(
    Design.Rgba Background, Design.Rgba Surface, Design.Rgba Ink, Design.Rgba InkSecondary,
    Design.Rgba Line, Design.Rgba Focus, Design.Rgba Warning, Design.Rgba Offline);

public static class Looks
{
    /// <summary>The generated look of a category.</summary>
    public static Design.Category For(Category category) =>
        Design.ResearchlyTokens.Categories[Id(category)];

    /// <summary>The generated look of a state (its mark, colour and words).</summary>
    public static Design.StateLook For(OverlayState state) =>
        Design.ResearchlyTokens.States[Id(state)];

    /// <summary>The four categories in the tokens' order (Correction first).</summary>
    public static IReadOnlyList<Category> Categories { get; } =
        new[] { Category.Correction, Category.Improvement, Category.Convention, Category.Preference };

    public static string Id(Category category) => category switch
    {
        Category.Correction => "correction",
        Category.Improvement => "improvement",
        Category.Convention => "convention",
        Category.Preference => "preference",
        _ => "improvement",
    };

    public static string Id(OverlayState state) => state.ToString().ToLowerInvariant();

    /// <summary>The state's words, with the count for Issues ("3 suggestions", "1 suggestion").</summary>
    public static string Label(OverlayState state, int count = 0)
    {
        var look = For(state);
        if (count == 1 && look.LabelOne != null) return look.LabelOne;
        return look.Label.Replace("{n}", count.ToString(System.Globalization.CultureInfo.InvariantCulture), StringComparison.Ordinal);
    }

    /// <summary>The colour the field widget and the tray icon use for a state.</summary>
    public static Design.Rgba WidgetColour(OverlayState state, bool dark) => For(state).Color.Resolve(dark);

    /// <summary>Surfaces, text and lines of one theme.</summary>
    public static SurfaceColours Surface(bool dark)
    {
        return new SurfaceColours(
            Background: Design.ResearchlyTokens.SurfacePage.Resolve(dark),
            Surface: Design.ResearchlyTokens.SurfaceRaised.Resolve(dark),
            Ink: Design.ResearchlyTokens.TextPrimary.Resolve(dark),
            InkSecondary: Design.ResearchlyTokens.TextSecondary.Resolve(dark),
            Line: Design.ResearchlyTokens.LineHairline.Resolve(dark),
            Focus: Design.ResearchlyTokens.FocusStrong.Resolve(dark),
            Warning: Design.ResearchlyTokens.WarningStrong.Resolve(dark),
            Offline: Design.ResearchlyTokens.OfflineStrong.Resolve(dark));
    }

    /// <summary>The colour with another opacity (0 to 1).</summary>
    public static Design.Rgba WithAlpha(this Design.Rgba c, double alpha) =>
        c with { A = (byte)Math.Round(Math.Clamp(alpha, 0, 1) * 255) };

    /// <summary>WCAG relative luminance.</summary>
    public static double Luminance(this Design.Rgba c)
    {
        static double Ch(byte v)
        {
            double s = v / 255.0;
            return s <= 0.03928 ? s / 12.92 : Math.Pow((s + 0.055) / 1.055, 2.4);
        }
        return 0.2126 * Ch(c.R) + 0.7152 * Ch(c.G) + 0.0722 * Ch(c.B);
    }

    /// <summary>WCAG contrast ratio between two opaque colours.</summary>
    public static double Contrast(Design.Rgba a, Design.Rgba b)
    {
        double la = a.Luminance(), lb = b.Luminance();
        return (Math.Max(la, lb) + 0.05) / (Math.Min(la, lb) + 0.05);
    }
}
