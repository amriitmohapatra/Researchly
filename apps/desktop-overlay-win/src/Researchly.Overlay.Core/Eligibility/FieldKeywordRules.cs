using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace Researchly.Overlay.Core.Eligibility;

/// <summary>A keyword from the blocklist that matched a field's label, and its language.</summary>
public sealed record BlockedTerm(string Language, string Term);

/// <summary>
/// The field keyword blocklist, read from <c>packages/desktop-rules/fields.json</c>
/// (shared with the Mac client). Matching is case-insensitive. Latin-script
/// terms match on word boundaries after identifiers are split into words
/// (<c>txtPassword</c>, <c>user_name</c>, <c>sign-in</c>); scripts listed in
/// <c>scripts_matched_as_substrings</c> match anywhere, because they do not put
/// spaces between words.
/// </summary>
public sealed class FieldKeywordRules
{
    private readonly List<(string Language, string Term, string Normalised, bool Substring)> _terms;

    private FieldKeywordRules(bool neverSecure, int minChars, int maxChars,
        IReadOnlyDictionary<string, IReadOnlyList<string>> keywords, IReadOnlyCollection<string> substringLanguages)
    {
        NeverSecureFields = neverSecure;
        MinFieldCharacters = minChars;
        MaxFieldCharacters = maxChars;
        Keywords = keywords;
        SubstringLanguages = substringLanguages;
        _terms = new();
        foreach (var (lang, terms) in keywords)
        {
            bool substring = substringLanguages.Contains(lang);
            foreach (var term in terms)
            {
                string norm = substring ? NormaliseSubstring(term) : NormaliseWords(term);
                if (norm.Length > 0) _terms.Add((lang, term, norm, substring));
            }
        }
    }

    public bool NeverSecureFields { get; }
    public int MinFieldCharacters { get; }
    public int MaxFieldCharacters { get; }
    public IReadOnlyDictionary<string, IReadOnlyList<string>> Keywords { get; }
    public IReadOnlyCollection<string> SubstringLanguages { get; }

    public static FieldKeywordRules Load(string path) => Parse(File.ReadAllText(path, Encoding.UTF8));

    public static FieldKeywordRules Parse(string json)
    {
        using var doc = JsonDocument.Parse(json, new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true });
        var root = doc.RootElement;
        bool neverSecure = !root.TryGetProperty("never_secure_fields", out var ns) || ns.ValueKind != JsonValueKind.False;
        int min = root.TryGetProperty("min_field_characters", out var mn) && mn.TryGetInt32(out var mnv) ? mnv : 1;
        int max = root.TryGetProperty("max_field_characters", out var mx) && mx.TryGetInt32(out var mxv) ? mxv : 1_000_000;

        var keywords = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
        if (root.TryGetProperty("keywords", out var kw) && kw.ValueKind == JsonValueKind.Object)
        {
            foreach (var lang in kw.EnumerateObject())
            {
                if (lang.Value.ValueKind != JsonValueKind.Array) continue;
                keywords[lang.Name] = lang.Value.EnumerateArray()
                    .Where(e => e.ValueKind == JsonValueKind.String)
                    .Select(e => e.GetString()!)
                    .ToList();
            }
        }

        var substring = new HashSet<string>(StringComparer.Ordinal);
        if (root.TryGetProperty("scripts_matched_as_substrings", out var sub) && sub.ValueKind == JsonValueKind.Array)
            foreach (var e in sub.EnumerateArray())
                if (e.ValueKind == JsonValueKind.String) substring.Add(e.GetString()!);

        if (keywords.Count == 0)
            throw new InvalidDataException("fields.json has no keywords; refusing to run without a blocklist.");
        return new FieldKeywordRules(neverSecure, min, max, keywords, substring);
    }

    /// <summary>The first blocklisted term found in any of <paramref name="texts"/>, or null.</summary>
    public BlockedTerm? FindBlockedTerm(IEnumerable<string?> texts)
    {
        foreach (var text in texts)
        {
            if (string.IsNullOrWhiteSpace(text)) continue;
            string words = NormaliseWords(text);
            string plain = NormaliseSubstring(text);
            foreach (var (lang, term, norm, isSubstring) in _terms)
            {
                bool hit = isSubstring
                    ? plain.Contains(norm, StringComparison.Ordinal)
                    : ContainsWord(words, norm);
                if (hit) return new BlockedTerm(lang, term);
            }
        }
        return null;
    }

    public BlockedTerm? FindBlockedTerm(params string?[] texts) => FindBlockedTerm((IEnumerable<string?>)texts);

    /// <summary>NFC, lower case (invariant), typographic apostrophes folded.</summary>
    internal static string NormaliseSubstring(string text) =>
        text.Normalize(NormalizationForm.FormC).ToLowerInvariant().Replace((char)0x2019, '\'').Replace((char)0x02BC, '\'');

    /// <summary>
    /// Splits identifiers into words: a space goes between a lower-case letter and
    /// an upper-case one (txtPassword), and runs of separators (_ - . : / \ | and
    /// white space) become one space. Then NFC and lower case.
    /// </summary>
    internal static string NormaliseWords(string text)
    {
        text = text.Normalize(NormalizationForm.FormC);
        var sb = new StringBuilder(text.Length + 8);
        bool pendingSpace = false;
        char prev = '\0';
        foreach (char c in text)
        {
            bool separator = char.IsWhiteSpace(c) || c is '_' or '-' or '.' or ':' or '/' or '\\' or '|' or (char)0x2010 or (char)0x2011 or (char)0x2013;
            if (separator)
            {
                pendingSpace = sb.Length > 0;
                prev = c;
                continue;
            }
            if (char.IsLower(prev) && char.IsUpper(c)) pendingSpace = sb.Length > 0;
            if (pendingSpace) { sb.Append(' '); pendingSpace = false; }
            sb.Append(c);
            prev = c;
        }
        return NormaliseSubstring(sb.ToString());
    }

    /// <summary>True when <paramref name="term"/> occurs in <paramref name="text"/> with no letter directly before or after it.</summary>
    internal static bool ContainsWord(string text, string term)
    {
        int from = 0;
        while (from <= text.Length - term.Length)
        {
            int i = text.IndexOf(term, from, StringComparison.Ordinal);
            if (i < 0) return false;
            bool startOk = i == 0 || !char.IsLetter(text[i - 1]);
            int end = i + term.Length;
            bool endOk = end == text.Length || !char.IsLetter(text[end]);
            // A combining mark after the term continues the word.
            if (endOk && end < text.Length && char.GetUnicodeCategory(text[end]) == System.Globalization.UnicodeCategory.NonSpacingMark)
                endOk = false;
            if (startOk && endOk) return true;
            from = i + 1;
        }
        return false;
    }
}
