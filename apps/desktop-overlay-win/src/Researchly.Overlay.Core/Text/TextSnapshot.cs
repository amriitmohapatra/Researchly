using System;
using System.Collections.Generic;

namespace Researchly.Overlay.Core.Text;

/// <summary>One paragraph of a field's text.</summary>
/// <param name="Index">Position in the snapshot (0-based).</param>
/// <param name="Start">UTF-16 offset of the paragraph's first code unit in the field text.</param>
/// <param name="Text">The paragraph without its break characters.</param>
/// <param name="Style">The host's paragraph style when the shell could read one (for example "heading 1"), else null.</param>
public sealed record Paragraph(int Index, int Start, string Text, string? Style = null)
{
    public int End => Start + Text.Length;
    public TextRange16 Range => new(Start, End);
    public bool IsBlank => string.IsNullOrWhiteSpace(Text);
}

/// <summary>
/// An immutable copy of a field's text, split into paragraphs with their
/// UTF-16 offsets. Lives in memory only, for as long as the field has focus.
/// </summary>
public sealed class TextSnapshot
{
    private TextSnapshot(string text, IReadOnlyList<Paragraph> paragraphs)
    {
        Text = text;
        Paragraphs = paragraphs;
    }

    public string Text { get; }
    public IReadOnlyList<Paragraph> Paragraphs { get; }

    private const char ParagraphSeparator = (char)0x2029;

    public static readonly TextSnapshot Empty = Create(string.Empty);

    /// <summary>
    /// Splits <paramref name="text"/> into paragraphs. Paragraph breaks are CR LF,
    /// CR, LF, U+2029 (paragraph separator), form feed (a page or section break)
    /// and BEL (the end-of-cell mark some word processors expose). A vertical tab
    /// and U+2028 are line breaks inside a paragraph and stay in its text.
    /// </summary>
    /// <param name="text">The field's text.</param>
    /// <param name="styles">Optional style per paragraph, by index; shorter lists leave the rest unstyled.</param>
    public static TextSnapshot Create(string text, IReadOnlyList<string?>? styles = null)
    {
        text ??= string.Empty;
        var list = new List<Paragraph>();
        int start = 0;
        int i = 0;
        while (i < text.Length)
        {
            char c = text[i];
            int breakLength = 0;
            if (c == '\r') breakLength = i + 1 < text.Length && text[i + 1] == '\n' ? 2 : 1;
            else if (c == '\n' || c == ParagraphSeparator || c == '\f' || c == '\a') breakLength = 1;

            if (breakLength > 0)
            {
                Add(list, text, start, i, styles);
                i += breakLength;
                start = i;
            }
            else
            {
                i++;
            }
        }
        Add(list, text, start, text.Length, styles);
        return new TextSnapshot(text, list);
    }

    private static void Add(List<Paragraph> list, string text, int start, int end, IReadOnlyList<string?>? styles)
    {
        int index = list.Count;
        string? style = styles != null && index < styles.Count ? styles[index] : null;
        list.Add(new Paragraph(index, start, text.Substring(start, end - start), style));
    }

    /// <summary>The paragraph containing <paramref name="offset"/>, or the one ending exactly there; null when out of range.</summary>
    public Paragraph? ParagraphAt(int offset)
    {
        if (offset < 0 || offset > Text.Length) return null;
        // Binary search on start offsets.
        int lo = 0, hi = Paragraphs.Count - 1;
        while (lo < hi)
        {
            int mid = (lo + hi + 1) / 2;
            if (Paragraphs[mid].Start <= offset) lo = mid; else hi = mid - 1;
        }
        var p = Paragraphs[lo];
        return offset <= p.End ? p : null;
    }
}
