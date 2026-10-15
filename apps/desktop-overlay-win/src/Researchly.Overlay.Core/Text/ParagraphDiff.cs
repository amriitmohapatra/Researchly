using System;
using System.Collections.Generic;

namespace Researchly.Overlay.Core.Text;

/// <summary>How a paragraph relates to the previous snapshot.</summary>
public enum ParagraphChange
{
    /// <summary>Same text as a paragraph in the previous snapshot (possibly moved).</summary>
    Unchanged,
    /// <summary>An edited paragraph: keeps the id of the paragraph it replaced.</summary>
    Changed,
    /// <summary>A new paragraph with a fresh id.</summary>
    Added,
}

/// <summary>A paragraph of the current snapshot with its stable id.</summary>
public sealed record TrackedParagraph(string Id, Paragraph Paragraph, ParagraphChange Change, string? PreviousText)
{
    public string Text => Paragraph.Text;
}

/// <summary>The outcome of comparing two snapshots paragraph by paragraph.</summary>
public sealed record DiffResult(IReadOnlyList<TrackedParagraph> Paragraphs, IReadOnlyList<string> RemovedIds)
{
    public bool HasChanges
    {
        get
        {
            if (RemovedIds.Count > 0) return true;
            foreach (var p in Paragraphs)
                if (p.Change != ParagraphChange.Unchanged) return true;
            return false;
        }
    }
}

/// <summary>
/// Gives every paragraph a stable id across edits, so the engine is asked only
/// about paragraphs whose text changed, and replies can be matched back.
/// Unchanged paragraphs are matched by text (common prefix and suffix, then a
/// longest common subsequence over the middle); between matches, edited
/// paragraphs pair up in order and keep their ids.
/// </summary>
public static class ParagraphDiff
{
    /// <summary>Above this many paragraphs in the changed middle, matching falls back to position.</summary>
    public const int MaxLcsCells = 250_000;

    /// <param name="previous">The previous paragraphs, in order, with their ids.</param>
    /// <param name="current">The new snapshot.</param>
    /// <param name="newId">Makes a fresh id for an added paragraph.</param>
    public static DiffResult Diff(IReadOnlyList<(string Id, string Text)> previous, TextSnapshot current, Func<string> newId)
    {
        var now = current.Paragraphs;
        int n = previous.Count, m = now.Count;
        var assigned = new TrackedParagraph?[m];
        var oldUsed = new bool[n];

        int prefix = 0;
        while (prefix < n && prefix < m && previous[prefix].Text == now[prefix].Text)
        {
            assigned[prefix] = new TrackedParagraph(previous[prefix].Id, now[prefix], ParagraphChange.Unchanged, null);
            oldUsed[prefix] = true;
            prefix++;
        }

        int suffix = 0;
        while (suffix < n - prefix && suffix < m - prefix
               && previous[n - 1 - suffix].Text == now[m - 1 - suffix].Text)
        {
            int oi = n - 1 - suffix, ni = m - 1 - suffix;
            assigned[ni] = new TrackedParagraph(previous[oi].Id, now[ni], ParagraphChange.Unchanged, null);
            oldUsed[oi] = true;
            suffix++;
        }

        int oldStart = prefix, oldEnd = n - suffix;   // middle of previous: [oldStart, oldEnd)
        int newStart = prefix, newEnd = m - suffix;   // middle of current:  [newStart, newEnd)

        // Anchors: pairs (old index, new index) of equal text in the middle, in order.
        var anchors = MiddleAnchors(previous, now, oldStart, oldEnd, newStart, newEnd);

        foreach (var (oi, ni) in anchors)
        {
            assigned[ni] = new TrackedParagraph(previous[oi].Id, now[ni], ParagraphChange.Unchanged, null);
            oldUsed[oi] = true;
        }

        // Gaps between anchors: pair positionally as edits, the rest are added/removed.
        int prevOld = oldStart, prevNew = newStart;
        var bounds = new List<(int Old, int New)>(anchors) { (oldEnd, newEnd) };
        foreach (var (anchorOld, anchorNew) in bounds)
        {
            int gapOld = anchorOld - prevOld, gapNew = anchorNew - prevNew;
            int pairs = Math.Min(gapOld, gapNew);
            for (int k = 0; k < pairs; k++)
            {
                int oi = prevOld + k, ni = prevNew + k;
                assigned[ni] = new TrackedParagraph(previous[oi].Id, now[ni], ParagraphChange.Changed, previous[oi].Text);
                oldUsed[oi] = true;
            }
            for (int ni = prevNew + pairs; ni < anchorNew; ni++)
                assigned[ni] = new TrackedParagraph(newId(), now[ni], ParagraphChange.Added, null);
            prevOld = anchorOld + 1;
            prevNew = anchorNew + 1;
        }

        var removed = new List<string>();
        for (int i = 0; i < n; i++)
            if (!oldUsed[i]) removed.Add(previous[i].Id);

        var result = new TrackedParagraph[m];
        for (int i = 0; i < m; i++)
            result[i] = assigned[i] ?? new TrackedParagraph(newId(), now[i], ParagraphChange.Added, null);
        return new DiffResult(result, removed);
    }

    private static List<(int Old, int New)> MiddleAnchors(
        IReadOnlyList<(string Id, string Text)> previous, IReadOnlyList<Paragraph> now,
        int oldStart, int oldEnd, int newStart, int newEnd)
    {
        int a = oldEnd - oldStart, b = newEnd - newStart;
        var anchors = new List<(int, int)>();
        if (a == 0 || b == 0) return anchors;
        if ((long)a * b > MaxLcsCells) return anchors; // positional pairing only

        // Classic LCS table on paragraph text; blank paragraphs never anchor
        // (they are interchangeable and would pin edits to the wrong place).
        var table = new int[a + 1, b + 1];
        for (int i = a - 1; i >= 0; i--)
        {
            for (int j = b - 1; j >= 0; j--)
            {
                string ot = previous[oldStart + i].Text, nt = now[newStart + j].Text;
                table[i, j] = ot == nt && !string.IsNullOrWhiteSpace(nt)
                    ? table[i + 1, j + 1] + 1
                    : Math.Max(table[i + 1, j], table[i, j + 1]);
            }
        }
        int x = 0, y = 0;
        while (x < a && y < b)
        {
            string ot = previous[oldStart + x].Text, nt = now[newStart + y].Text;
            if (ot == nt && !string.IsNullOrWhiteSpace(nt) && table[x, y] == table[x + 1, y + 1] + 1)
            {
                anchors.Add((oldStart + x, newStart + y));
                x++; y++;
            }
            else if (table[x + 1, y] >= table[x, y + 1]) x++;
            else y++;
        }
        return anchors;
    }
}
