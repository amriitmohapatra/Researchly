using System;
using System.Globalization;

namespace Researchly.Overlay.Core.Text;

/// <summary>A half-open range [Start, End) of UTF-16 code units.</summary>
public readonly record struct TextRange16(int Start, int End)
{
    public int Length => End - Start;
    public bool IsEmpty => End <= Start;

    /// <summary>True when the two ranges share at least one code unit.</summary>
    public bool Overlaps(TextRange16 other) => Start < other.End && other.Start < End;

    public bool Contains(int offset) => offset >= Start && offset < End;

    public TextRange16 Offset(int by) => new(Start + by, End + by);

    public override string ToString() => $"[{Start},{End})";
}

/// <summary>
/// One contiguous edit: <see cref="RemovedLength"/> code units at
/// <see cref="Start"/> were replaced by <see cref="InsertedLength"/> new ones.
/// </summary>
public readonly record struct TextEdit(int Start, int RemovedLength, int InsertedLength)
{
    public static readonly TextEdit None = new(0, 0, 0);
    public int Delta => InsertedLength - RemovedLength;
    public bool IsNone => RemovedLength == 0 && InsertedLength == 0;
    public int RemovedEnd => Start + RemovedLength;
}

/// <summary>
/// UTF-16 range arithmetic. Every offset in the live-check contract is a
/// UTF-16 code unit offset (docs/inline-review-design.md section 5), which
/// is what C# strings, UI Automation and the browser all count in. These
/// helpers keep ranges from splitting a surrogate pair, and, where a range
/// is shown to the writer, from splitting a user-perceived character
/// (a base letter and its combining marks, an emoji sequence).
/// </summary>
public static class Utf16
{
    /// <summary>True when <paramref name="offset"/> falls between the two halves of a surrogate pair.</summary>
    public static bool SplitsSurrogatePair(string text, int offset) =>
        offset > 0 && offset < text.Length
        && char.IsHighSurrogate(text[offset - 1]) && char.IsLowSurrogate(text[offset]);

    /// <summary>
    /// True when [begin, end) is a valid, non-empty range of <paramref name="text"/>
    /// whose ends do not split a surrogate pair.
    /// </summary>
    public static bool IsValidRange(string text, int begin, int end) =>
        begin >= 0 && end <= text.Length && begin < end
        && !SplitsSurrogatePair(text, begin) && !SplitsSurrogatePair(text, end);

    /// <summary>Validates an engine-supplied range; see <see cref="IsValidRange"/>.</summary>
    public static bool TryRange(string text, int begin, int end, out TextRange16 range)
    {
        if (IsValidRange(text, begin, end))
        {
            range = new TextRange16(begin, end);
            return true;
        }
        range = default;
        return false;
    }

    /// <summary>Clamps an offset into [0, length] and moves it back off the middle of a surrogate pair.</summary>
    public static int Clamp(string text, int offset)
    {
        offset = Math.Clamp(offset, 0, text.Length);
        return SplitsSurrogatePair(text, offset) ? offset - 1 : offset;
    }

    /// <summary>True when <paramref name="offset"/> is a boundary between user-perceived characters.</summary>
    public static bool IsGraphemeBoundary(string text, int offset)
    {
        if (offset <= 0 || offset >= text.Length)
            return offset == 0 || offset == text.Length;
        int i = 0;
        while (i < offset)
            i += Math.Max(1, StringInfo.GetNextTextElementLength(text, i));
        return i == offset;
    }

    /// <summary>The largest grapheme boundary at or before <paramref name="offset"/>.</summary>
    public static int SnapToGraphemeStart(string text, int offset)
    {
        offset = Math.Clamp(offset, 0, text.Length);
        int last = 0, i = 0;
        while (i < text.Length)
        {
            int next = i + Math.Max(1, StringInfo.GetNextTextElementLength(text, i));
            if (next > offset) break;
            last = next;
            i = next;
        }
        return offset == text.Length ? text.Length : last;
    }

    /// <summary>The smallest grapheme boundary at or after <paramref name="offset"/>.</summary>
    public static int SnapToGraphemeEnd(string text, int offset)
    {
        offset = Math.Clamp(offset, 0, text.Length);
        int i = 0;
        while (i < offset)
            i += Math.Max(1, StringInfo.GetNextTextElementLength(text, i));
        return Math.Min(i, text.Length);
    }

    /// <summary>Widens a range so that neither end splits a user-perceived character.</summary>
    public static TextRange16 ExpandToGraphemes(string text, TextRange16 range) =>
        new(SnapToGraphemeStart(text, range.Start), SnapToGraphemeEnd(text, range.End));

    /// <summary>
    /// The single edit that turns <paramref name="before"/> into <paramref name="after"/>:
    /// the common prefix and suffix are kept, and the middle is the edit. Both ends
    /// of the edit sit on grapheme boundaries in both strings, so adding a combining
    /// accent to a letter counts as an edit of that letter.
    /// </summary>
    public static TextEdit ComputeEdit(string before, string after)
    {
        if (string.Equals(before, after, StringComparison.Ordinal)) return TextEdit.None;
        int max = Math.Min(before.Length, after.Length);
        int prefix = 0;
        while (prefix < max && before[prefix] == after[prefix]) prefix++;
        while (prefix > 0 && !(IsGraphemeBoundary(before, prefix) && IsGraphemeBoundary(after, prefix)))
            prefix--;

        int suffix = 0;
        int maxSuffix = max - prefix;
        while (suffix < maxSuffix && before[before.Length - 1 - suffix] == after[after.Length - 1 - suffix])
            suffix++;
        while (suffix > 0 && !(IsGraphemeBoundary(before, before.Length - suffix)
                               && IsGraphemeBoundary(after, after.Length - suffix)))
            suffix--;

        return new TextEdit(prefix, before.Length - prefix - suffix, after.Length - prefix - suffix);
    }

    /// <summary>
    /// Moves a range through an edit. A range wholly before the edit stays; a range
    /// wholly after it shifts by the edit's length change; a range that the edit
    /// touches, including one the edit merely abuts, is no longer trustworthy and
    /// comes back null (typing a letter onto the end of a flagged word changes the word).
    /// </summary>
    public static TextRange16? ShiftThroughEdit(TextRange16 range, TextEdit edit)
    {
        if (edit.IsNone) return range;
        if (range.End < edit.Start) return range;
        if (range.Start > edit.RemovedEnd) return range.Offset(edit.Delta);
        return null;
    }

    /// <summary>
    /// Which occurrence of <paramref name="needle"/> starts at <paramref name="at"/>,
    /// counting non-overlapping ordinal matches from the start of
    /// <paramref name="haystack"/> (the way a host's find-next walks text).
    /// Returns -1 when that scan never lands on <paramref name="at"/>.
    /// </summary>
    public static int OccurrenceIndex(string haystack, string needle, int at)
    {
        if (string.IsNullOrEmpty(needle)) return -1;
        int index = 0, from = 0;
        while (from <= haystack.Length - needle.Length)
        {
            int found = haystack.IndexOf(needle, from, StringComparison.Ordinal);
            if (found < 0 || found > at) return -1;
            if (found == at) return index;
            index++;
            from = found + needle.Length;
        }
        return -1;
    }

    /// <summary>The text of a range, or null when the range does not fit the text.</summary>
    public static string? Slice(string text, TextRange16 range) =>
        range.Start >= 0 && range.End <= text.Length && range.Start <= range.End
            ? text.Substring(range.Start, range.Length)
            : null;

    /// <summary>
    /// Replaces a range. Callers validate the range first; an invalid one throws,
    /// because writing a wrong splice back into the writer's text is never acceptable.
    /// </summary>
    public static string Splice(string text, TextRange16 range, string replacement)
    {
        if (range.Start < 0 || range.End > text.Length || range.Start > range.End)
            throw new ArgumentOutOfRangeException(nameof(range));
        return string.Concat(text.AsSpan(0, range.Start), replacement, text.AsSpan(range.End));
    }
}
