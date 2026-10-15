using System;
using System.Collections.Generic;
using System.Linq;
using Researchly.Overlay.Core.Text;
using Xunit;

namespace Researchly.Overlay.Core.Tests;

public class Utf16Tests
{
    // Built from code points so the source file stays plain ASCII.
    private static readonly string Emoji = char.ConvertFromUtf32(0x1F9EA);          // a test-tube emoji: two UTF-16 units
    private static readonly string CombiningAcute = ((char)0x0301).ToString();       // combines with the letter before it
    private static readonly string Cafe = "cafe" + CombiningAcute;                    // "café" written as e + combining mark

    [Fact]
    public void Surrogate_pair_counts_as_two_code_units()
    {
        string s = "a" + Emoji + "b";
        Assert.Equal(4, s.Length);
        Assert.True(Utf16.SplitsSurrogatePair(s, 2));
        Assert.False(Utf16.SplitsSurrogatePair(s, 1));
        Assert.False(Utf16.SplitsSurrogatePair(s, 3));
    }

    [Fact]
    public void Range_that_splits_a_surrogate_pair_is_invalid()
    {
        string s = "x " + Emoji + " y";
        Assert.True(Utf16.IsValidRange(s, 2, 4));     // the whole emoji
        Assert.False(Utf16.IsValidRange(s, 2, 3));    // half of it
        Assert.False(Utf16.IsValidRange(s, 3, 6));    // starts inside it
        Assert.False(Utf16.IsValidRange(s, 0, 0));    // empty
        Assert.False(Utf16.IsValidRange(s, -1, 2));
        Assert.False(Utf16.IsValidRange(s, 0, s.Length + 1));
        Assert.True(Utf16.TryRange(s, 0, s.Length, out var all));
        Assert.Equal(new TextRange16(0, s.Length), all);
    }

    [Fact]
    public void Clamp_moves_off_the_middle_of_a_pair()
    {
        string s = "a" + Emoji;
        Assert.Equal(1, Utf16.Clamp(s, 2));
        Assert.Equal(s.Length, Utf16.Clamp(s, 99));
        Assert.Equal(0, Utf16.Clamp(s, -5));
    }

    [Fact]
    public void Grapheme_boundaries_respect_combining_marks()
    {
        // c a f e + U+0301 : the last two code units are one user-perceived character.
        Assert.Equal(5, Cafe.Length);
        Assert.False(Utf16.IsGraphemeBoundary(Cafe, 4));
        Assert.True(Utf16.IsGraphemeBoundary(Cafe, 3));
        Assert.Equal(3, Utf16.SnapToGraphemeStart(Cafe, 4));
        Assert.Equal(5, Utf16.SnapToGraphemeEnd(Cafe, 4));
        Assert.Equal(new TextRange16(0, 5), Utf16.ExpandToGraphemes(Cafe, new TextRange16(0, 4)));
    }

    [Fact]
    public void Grapheme_boundaries_keep_emoji_whole()
    {
        string s = "ok" + Emoji;
        Assert.False(Utf16.IsGraphemeBoundary(s, 3));
        Assert.Equal(2, Utf16.SnapToGraphemeStart(s, 3));
        Assert.Equal(4, Utf16.SnapToGraphemeEnd(s, 3));
    }

    [Fact]
    public void ComputeEdit_finds_a_single_insertion()
    {
        var e = Utf16.ComputeEdit("the cat sat", "the black cat sat");
        Assert.Equal(new TextEdit(4, 0, 6), e);
        Assert.Equal(6, e.Delta);
    }

    [Fact]
    public void ComputeEdit_of_equal_strings_is_none()
    {
        Assert.True(Utf16.ComputeEdit("same", "same").IsNone);
    }

    [Fact]
    public void ComputeEdit_treats_an_added_combining_mark_as_an_edit_of_the_letter()
    {
        var e = Utf16.ComputeEdit("cafe", Cafe);
        // The edit starts at the "e", not after it: the "e" became "e" + mark.
        Assert.Equal(3, e.Start);
        Assert.Equal(1, e.RemovedLength);
        Assert.Equal(2, e.InsertedLength);
    }

    [Fact]
    public void ComputeEdit_never_splits_a_surrogate_pair()
    {
        // Two different emoji share their high surrogate.
        string a = "x" + char.ConvertFromUtf32(0x1F600) + "y";
        string b = "x" + char.ConvertFromUtf32(0x1F601) + "y";
        Assert.Equal(a[1], b[1]);
        var e = Utf16.ComputeEdit(a, b);
        Assert.Equal(new TextEdit(1, 2, 2), e);
    }

    [Theory]
    [InlineData(0, 3, 10, 0, 2, 0, 3)]     // before the edit: unchanged
    [InlineData(20, 25, 10, 0, 2, 22, 27)]  // after an insertion: shifted
    [InlineData(20, 25, 10, 5, 0, 15, 20)]  // after a deletion: shifted back
    public void ShiftThroughEdit_moves_untouched_ranges(int s, int e, int at, int removed, int inserted, int s2, int e2)
    {
        var moved = Utf16.ShiftThroughEdit(new TextRange16(s, e), new TextEdit(at, removed, inserted));
        Assert.Equal(new TextRange16(s2, e2), moved);
    }

    [Theory]
    [InlineData(8, 12, 10, 1, 1)]   // overlap
    [InlineData(8, 10, 10, 0, 1)]   // insertion right after the range (typing onto the word)
    [InlineData(10, 14, 10, 0, 1)]  // insertion right before it
    [InlineData(5, 20, 10, 2, 0)]   // deletion inside it
    public void ShiftThroughEdit_drops_ranges_the_edit_touches(int s, int e, int at, int removed, int inserted)
    {
        Assert.Null(Utf16.ShiftThroughEdit(new TextRange16(s, e), new TextEdit(at, removed, inserted)));
    }

    [Fact]
    public void OccurrenceIndex_counts_non_overlapping_matches()
    {
        string s = "data are; the data were; data";
        Assert.Equal(0, Utf16.OccurrenceIndex(s, "data", 0));
        Assert.Equal(1, Utf16.OccurrenceIndex(s, "data", 14));
        Assert.Equal(2, Utf16.OccurrenceIndex(s, "data", 25));
        Assert.Equal(-1, Utf16.OccurrenceIndex(s, "data", 3));
        Assert.Equal(-1, Utf16.OccurrenceIndex("aaa", "aa", 1));
    }

    [Fact]
    public void Splice_replaces_a_range_with_surrogates_intact()
    {
        string s = "a " + Emoji + " teh end";
        int at = s.IndexOf("teh", StringComparison.Ordinal);
        string r = Utf16.Splice(s, new TextRange16(at, at + 3), "the");
        Assert.Equal("a " + Emoji + " the end", r);
        Assert.Throws<ArgumentOutOfRangeException>(() => Utf16.Splice(s, new TextRange16(0, 99), "x"));
    }
}

public class TextSnapshotTests
{
    private static readonly string ParagraphSeparator = ((char)0x2029).ToString();
    private static readonly string LineSeparator = ((char)0x2028).ToString();

    [Fact]
    public void Splits_on_every_paragraph_break_with_offsets()
    {
        string text = "One.\r\nTwo.\rThree.\nFour." + ParagraphSeparator + "Five.";
        var snap = TextSnapshot.Create(text);
        Assert.Equal(new[] { "One.", "Two.", "Three.", "Four.", "Five." }, snap.Paragraphs.Select(p => p.Text));
        foreach (var p in snap.Paragraphs)
            Assert.Equal(p.Text, text.Substring(p.Start, p.Text.Length));
        Assert.Equal(6, snap.Paragraphs[1].Start);
    }

    [Fact]
    public void Line_breaks_inside_a_paragraph_stay_in_it()
    {
        string text = "Line one\vline two" + LineSeparator + "line three\nNext";
        var snap = TextSnapshot.Create(text);
        Assert.Equal(2, snap.Paragraphs.Count);
        Assert.Contains("\v", snap.Paragraphs[0].Text);
    }

    [Fact]
    public void Empty_text_has_one_blank_paragraph_and_trailing_break_adds_one()
    {
        Assert.Single(TextSnapshot.Create("").Paragraphs);
        var snap = TextSnapshot.Create("Hello\n");
        Assert.Equal(2, snap.Paragraphs.Count);
        Assert.True(snap.Paragraphs[1].IsBlank);
    }

    [Fact]
    public void Styles_attach_by_index()
    {
        var snap = TextSnapshot.Create("Methods\nWe sampled.", new string?[] { "heading 1" });
        Assert.Equal("heading 1", snap.Paragraphs[0].Style);
        Assert.Null(snap.Paragraphs[1].Style);
    }

    [Fact]
    public void ParagraphAt_finds_the_paragraph()
    {
        var snap = TextSnapshot.Create("ab\ncd\nef");
        Assert.Equal(1, snap.ParagraphAt(3)!.Index);
        Assert.Equal(1, snap.ParagraphAt(5)!.Index); // end of "cd"
        Assert.Equal(2, snap.ParagraphAt(8)!.Index);
        Assert.Null(snap.ParagraphAt(9));
    }
}

public class ParagraphDiffTests
{
    private static int _counter;
    private static string NewId() => "n" + (++_counter);

    private static List<(string, string)> Prev(params string[] texts) =>
        texts.Select((t, i) => ("old" + i, t)).ToList();

    [Fact]
    public void Identical_text_keeps_every_id_unchanged()
    {
        var d = ParagraphDiff.Diff(Prev("A.", "B.", "C."), TextSnapshot.Create("A.\nB.\nC."), NewId);
        Assert.Equal(new[] { "old0", "old1", "old2" }, d.Paragraphs.Select(p => p.Id));
        Assert.All(d.Paragraphs, p => Assert.Equal(ParagraphChange.Unchanged, p.Change));
        Assert.False(d.HasChanges);
    }

    [Fact]
    public void Editing_a_paragraph_keeps_its_id_and_marks_it_changed()
    {
        var d = ParagraphDiff.Diff(Prev("A.", "B.", "C."), TextSnapshot.Create("A.\nB, edited.\nC."), NewId);
        Assert.Equal("old1", d.Paragraphs[1].Id);
        Assert.Equal(ParagraphChange.Changed, d.Paragraphs[1].Change);
        Assert.Equal("B.", d.Paragraphs[1].PreviousText);
        Assert.Equal(ParagraphChange.Unchanged, d.Paragraphs[0].Change);
        Assert.Equal(ParagraphChange.Unchanged, d.Paragraphs[2].Change);
        Assert.True(d.HasChanges);
    }

    [Fact]
    public void Inserting_a_paragraph_gives_it_a_new_id()
    {
        var d = ParagraphDiff.Diff(Prev("A.", "C."), TextSnapshot.Create("A.\nB.\nC."), NewId);
        Assert.Equal("old0", d.Paragraphs[0].Id);
        Assert.Equal(ParagraphChange.Added, d.Paragraphs[1].Change);
        Assert.StartsWith("n", d.Paragraphs[1].Id);
        Assert.Equal("old1", d.Paragraphs[2].Id);
        Assert.Empty(d.RemovedIds);
    }

    [Fact]
    public void Deleting_a_paragraph_reports_its_id()
    {
        var d = ParagraphDiff.Diff(Prev("A.", "B.", "C."), TextSnapshot.Create("A.\nC."), NewId);
        Assert.Equal(new[] { "old0", "old2" }, d.Paragraphs.Select(p => p.Id));
        Assert.Equal(new[] { "old1" }, d.RemovedIds);
    }

    [Fact]
    public void Moved_paragraph_keeps_its_id_through_the_common_subsequence()
    {
        var d = ParagraphDiff.Diff(Prev("A.", "B.", "C.", "D."), TextSnapshot.Create("A.\nC.\nB.\nD."), NewId);
        // One of B/C is matched by text; the other pairs as an edit or is re-added.
        Assert.Equal("old0", d.Paragraphs[0].Id);
        Assert.Equal("old3", d.Paragraphs[3].Id);
        var unchanged = d.Paragraphs.Count(p => p.Change == ParagraphChange.Unchanged);
        Assert.Equal(3, unchanged);
        Assert.Equal(4, d.Paragraphs.Select(p => p.Id).Distinct().Count());
    }

    [Fact]
    public void Splitting_a_paragraph_keeps_the_first_id()
    {
        var d = ParagraphDiff.Diff(Prev("Intro.", "First half. Second half.", "End."),
            TextSnapshot.Create("Intro.\nFirst half.\nSecond half.\nEnd."), NewId);
        Assert.Equal("old1", d.Paragraphs[1].Id);
        Assert.Equal(ParagraphChange.Changed, d.Paragraphs[1].Change);
        Assert.Equal(ParagraphChange.Added, d.Paragraphs[2].Change);
        Assert.Equal("old2", d.Paragraphs[3].Id);
    }

    [Fact]
    public void Blank_paragraphs_never_anchor_the_match()
    {
        var d = ParagraphDiff.Diff(Prev("A.", "", "B."), TextSnapshot.Create("A.\nX.\n\nB."), NewId);
        Assert.Equal("old0", d.Paragraphs[0].Id);
        Assert.Equal("old2", d.Paragraphs[3].Id);
        Assert.Equal(4, d.Paragraphs.Count);
    }
}

public class HeadingDetectorTests
{
    [Theory]
    [InlineData("Methods")]
    [InlineData("2. Methods")]
    [InlineData("2.1 Results")]
    [InlineData("Materials and methods")]
    [InlineData("DISCUSSION")]
    [InlineData("## Study design")]
    [InlineData("Conclusions:")]
    public void Recognises_section_headings(string text)
    {
        Assert.True(HeadingDetector.IsHeading(new Paragraph(0, 0, text)));
    }

    [Theory]
    [InlineData("We used the methods described earlier.")]
    [InlineData("Results were similar across sites.")]
    [InlineData("")]
    public void Ordinary_sentences_are_not_headings(string text)
    {
        Assert.False(HeadingDetector.IsHeading(new Paragraph(0, 0, text)));
    }

    [Fact]
    public void Style_marks_a_heading()
    {
        Assert.True(HeadingDetector.IsHeading(new Paragraph(0, 0, "Model fitting", "heading 2")));
        Assert.True(HeadingDetector.IsHeading(new Paragraph(0, 0, "A study", "title")));
    }

    [Fact]
    public void Each_paragraph_gets_the_nearest_heading_above()
    {
        var snap = TextSnapshot.Create("Preamble.\nMethods\nWe sampled.\nWe fitted.\n# Results\nIt worked.");
        var h = HeadingDetector.NearestHeadings(snap.Paragraphs);
        Assert.Null(h[0]);
        Assert.Null(h[1]);
        Assert.Equal("Methods", h[2]);
        Assert.Equal("Methods", h[3]);
        Assert.Equal("Methods", h[4]);
        Assert.Equal("Results", h[5]);
    }
}
