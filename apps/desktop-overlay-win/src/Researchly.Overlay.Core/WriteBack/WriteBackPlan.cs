using System;
using Researchly.Overlay.Core.Session;
using Researchly.Overlay.Core.Text;

namespace Researchly.Overlay.Core.WriteBack;

/// <summary>What happened after one write-back attempt.</summary>
public enum WriteBackOutcome
{
    /// <summary>The field now holds exactly the expected text.</summary>
    Applied,
    /// <summary>The field did not change: the next method may be tried.</summary>
    NoChange,
    /// <summary>The field changed, but not as expected: stop, never try again on top of it.</summary>
    Unexpected,
}

/// <summary>
/// The pure part of writing an accepted revision back (docs/inline-review-design.md
/// section 6, step 8). Before writing, the flagged text must still be where the
/// suggestion says; after writing, the result is compared with the expected text.
/// A method that left the text unchanged lets the next method run; any other
/// difference stops, so a revision is never typed twice.
/// </summary>
public static class WriteBackPlan
{
    /// <summary>
    /// True when <paramref name="currentText"/> still holds the flagged text at the
    /// suggestion's range (the writer may have typed since the underline was drawn).
    /// </summary>
    public static bool StillApplies(string currentText, PlacedSuggestion suggestion) =>
        Utf16.IsValidRange(currentText, suggestion.Range.Start, suggestion.Range.End)
        && string.CompareOrdinal(currentText, suggestion.Range.Start, suggestion.FlaggedText, 0, suggestion.FlaggedText.Length) == 0
        && suggestion.FlaggedText.Length == suggestion.Range.Length;

    /// <summary>The field text after the revision.</summary>
    public static string Expected(string currentText, PlacedSuggestion suggestion, string replacement) =>
        Utf16.Splice(currentText, suggestion.Range, replacement);

    /// <summary>Classifies an attempt from the text before and after it.</summary>
    /// <param name="before">The field text just before the attempt.</param>
    /// <param name="after">The field text just after it.</param>
    /// <param name="expected">What the field should hold.</param>
    public static WriteBackOutcome Classify(string before, string after, string expected)
    {
        if (string.Equals(after, expected, StringComparison.Ordinal)) return WriteBackOutcome.Applied;
        // Some hosts normalise line breaks on write (CR LF to CR); compare without them.
        if (string.Equals(StripBreaks(after), StripBreaks(expected), StringComparison.Ordinal)) return WriteBackOutcome.Applied;
        if (string.Equals(after, before, StringComparison.Ordinal)) return WriteBackOutcome.NoChange;
        return WriteBackOutcome.Unexpected;
    }

    /// <summary>
    /// Classifies an attempt when only the paragraphs on screen are read (a long
    /// document can scroll while a range is selected, so whole-text comparison
    /// would mislead). Applied when some paragraph now reads as expected and the
    /// original paragraph is gone; NoChange when the original is still there and
    /// the expected one is not; anything else is Unexpected.
    /// </summary>
    /// <param name="paragraphBefore">The paragraph holding the suggestion, before the attempt.</param>
    /// <param name="paragraphExpected">That paragraph with the revision applied.</param>
    /// <param name="afterText">The text read after the attempt.</param>
    public static WriteBackOutcome ClassifyParagraph(string paragraphBefore, string paragraphExpected, string afterText)
    {
        bool hasExpected = false, hasBefore = false;
        foreach (var p in TextSnapshot.Create(afterText).Paragraphs)
        {
            if (string.Equals(p.Text, paragraphExpected, StringComparison.Ordinal)) hasExpected = true;
            if (string.Equals(p.Text, paragraphBefore, StringComparison.Ordinal)) hasBefore = true;
        }
        if (hasExpected && !hasBefore) return WriteBackOutcome.Applied;
        if (hasBefore && !hasExpected) return WriteBackOutcome.NoChange;
        return WriteBackOutcome.Unexpected;
    }

    private static string StripBreaks(string s) => s.Replace("\r\n", "\n").Replace('\r', '\n');
}
