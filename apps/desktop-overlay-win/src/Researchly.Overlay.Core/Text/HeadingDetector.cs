using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace Researchly.Overlay.Core.Text;

/// <summary>
/// Finds headings so each paragraph can be sent with the nearest heading above
/// it; that keeps advice section-aware (passive voice is fine in Methods)
/// without sending the whole document. A heading is a paragraph whose host
/// style says so, a Markdown heading, or a short line that is a usual section
/// name of a research paper, optionally numbered.
/// </summary>
public static class HeadingDetector
{
    private static readonly Regex SectionName = new(
        @"^(?:\d+(?:\.\d+)*\.?\s+)?(?:abstract|summary|introduction|background|methods?|materials and methods|methods and materials|methodology|results|results and discussion|findings|discussion|conclusions?|limitations|strengths and limitations|implications|future work|references|acknowledge?ments)\s*:?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private static readonly Regex MarkdownHeading = new(
        @"^#{1,6}\s+\S", RegexOptions.CultureInvariant | RegexOptions.Compiled);

    /// <summary>True when the paragraph reads as a heading.</summary>
    public static bool IsHeading(Paragraph paragraph)
    {
        if (paragraph.Style is { } style
            && (style.Contains("heading", StringComparison.OrdinalIgnoreCase)
                || style.Equals("title", StringComparison.OrdinalIgnoreCase)))
            return true;
        string t = paragraph.Text.Trim();
        if (t.Length == 0 || t.Length > 80) return false;
        if (MarkdownHeading.IsMatch(t)) return true;
        return SectionName.IsMatch(t);
    }

    /// <summary>A heading's text without Markdown markers.</summary>
    public static string HeadingText(Paragraph paragraph)
    {
        string t = paragraph.Text.Trim();
        return t.StartsWith('#') ? t.TrimStart('#').Trim() : t;
    }

    /// <summary>For each paragraph, the text of the nearest heading above it (null when none).</summary>
    public static IReadOnlyList<string?> NearestHeadings(IReadOnlyList<Paragraph> paragraphs)
    {
        var result = new string?[paragraphs.Count];
        string? current = null;
        for (int i = 0; i < paragraphs.Count; i++)
        {
            result[i] = current;
            if (IsHeading(paragraphs[i])) current = HeadingText(paragraphs[i]);
        }
        return result;
    }
}
