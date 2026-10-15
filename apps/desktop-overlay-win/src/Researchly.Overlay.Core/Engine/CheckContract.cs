using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Researchly.Overlay.Core.Engine;

// The live-check contract as the engine serves it (services/engine
// schemas.py; real exchanges in packages/contract/fixtures/check-paragraphs,
// which the tests decode):
//   POST {engine}/v1/check-paragraphs
//   request  { revision, paragraphs: [{ id, text, style?, heading? }], options }
//   response { schema_version, revision, paragraphs: [{ id, section, suggestions: [...] }],
//              state: "ok" | "partial", health: [{ tier, label, ok, state, detail, remedy }],
//              hidden_preferences, signed_in, assessed_rules, ruleset, elapsed_ms }
//   suggestion { id, rule_id, rule_name, category, critical, tier, begin, end, text,
//                section, message, plain, why, source, learn_ref, replacements, fix_safety }
// Offsets are UTF-16 code units within the paragraph. Decoding is tolerant:
// unknown fields are ignored and a malformed suggestion is dropped, not fatal.

/// <summary>The engine's limits for one live check (services/engine MAX_LIVE_*): a request over them is refused with 422.</summary>
public static class LiveLimits
{
    public const int MaxParagraphs = 50;
    /// <summary>Characters (code points, as the engine counts) of all paragraphs together, and so of any one.</summary>
    public const int MaxCharacters = 20_000;
    public const int MaxHeadingCharacters = 300;

    /// <summary>Characters as the engine counts them: code points, not UTF-16 units.</summary>
    public static int Characters(string text)
    {
        int n = 0;
        for (int i = 0; i < text.Length; i++)
        {
            if (char.IsHighSurrogate(text[i]) && i + 1 < text.Length && char.IsLowSurrogate(text[i + 1])) i++;
            n++;
        }
        return n;
    }
}

/// <summary>One paragraph sent for checking.</summary>
public sealed class ParagraphPayload
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("text")] public string Text { get; set; } = "";
    [JsonPropertyName("style")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public string? Style { get; set; }
    [JsonPropertyName("heading")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public string? Heading { get; set; }
}

/// <summary>The usual check options. Only set fields are sent.</summary>
public sealed class CheckOptionsPayload
{
    [JsonPropertyName("show_preferences")] public bool ShowPreferences { get; set; }
    [JsonPropertyName("spelling")][JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] public string? Spelling { get; set; }
}

public sealed class CheckParagraphsRequest
{
    [JsonPropertyName("revision")] public long Revision { get; set; }
    [JsonPropertyName("paragraphs")] public List<ParagraphPayload> Paragraphs { get; set; } = new();
    [JsonPropertyName("options")] public CheckOptionsPayload Options { get; set; } = new();
}

/// <summary>A suggestion as the engine sends it (all fields optional on the wire).</summary>
public sealed class SuggestionDto
{
    [JsonPropertyName("id")][JsonConverter(typeof(LooseStringConverter))] public string? Id { get; set; }
    [JsonPropertyName("begin")][JsonConverter(typeof(LooseIntConverter))] public int? Begin { get; set; }
    [JsonPropertyName("end")][JsonConverter(typeof(LooseIntConverter))] public int? End { get; set; }
    [JsonPropertyName("category")][JsonConverter(typeof(LooseStringConverter))] public string? Category { get; set; }
    [JsonPropertyName("critical")][JsonConverter(typeof(LooseBoolConverter))] public bool? Critical { get; set; }
    [JsonPropertyName("message")][JsonConverter(typeof(LooseStringConverter))] public string? Message { get; set; }
    [JsonPropertyName("plain")][JsonConverter(typeof(LooseStringConverter))] public string? Plain { get; set; }
    [JsonPropertyName("why")][JsonConverter(typeof(LooseStringConverter))] public string? Why { get; set; }
    [JsonPropertyName("source")][JsonConverter(typeof(LooseStringConverter))] public string? Source { get; set; }
    [JsonPropertyName("replacements")][JsonConverter(typeof(LooseStringListConverter))] public List<string>? Replacements { get; set; }
    /// <summary>The full check's single-replacement field, accepted when <see cref="Replacements"/> is absent.</summary>
    [JsonPropertyName("replacement")][JsonConverter(typeof(LooseStringConverter))] public string? Replacement { get; set; }
    [JsonPropertyName("section")][JsonConverter(typeof(LooseStringConverter))] public string? Section { get; set; }
    [JsonPropertyName("fix_safety")][JsonConverter(typeof(LooseStringConverter))] public string? FixSafety { get; set; }
    [JsonPropertyName("rule_id")][JsonConverter(typeof(LooseStringConverter))] public string? RuleId { get; set; }
    [JsonPropertyName("rule_name")][JsonConverter(typeof(LooseStringConverter))] public string? RuleName { get; set; }
    /// <summary>The flagged text, when the engine echoes it; used to double-check the range.</summary>
    [JsonPropertyName("text")][JsonConverter(typeof(LooseStringConverter))] public string? Text { get; set; }
    [JsonPropertyName("tier")][JsonConverter(typeof(LooseStringConverter))] public string? Tier { get; set; }
    [JsonPropertyName("learn_ref")][JsonConverter(typeof(LooseStringConverter))] public string? LearnRef { get; set; }
}

public sealed class ParagraphResultDto
{
    [JsonPropertyName("id")][JsonConverter(typeof(LooseStringConverter))] public string? Id { get; set; }
    [JsonPropertyName("section")][JsonConverter(typeof(LooseStringConverter))] public string? Section { get; set; }
    [JsonPropertyName("suggestions")][JsonConverter(typeof(LooseObjectListConverter<SuggestionDto>))] public List<SuggestionDto?>? Suggestions { get; set; }
}

public sealed class CheckParagraphsResponseDto
{
    [JsonPropertyName("revision")][JsonConverter(typeof(LooseLongConverter))] public long? Revision { get; set; }
    [JsonPropertyName("paragraphs")][JsonConverter(typeof(LooseObjectListConverter<ParagraphResultDto>))] public List<ParagraphResultDto?>? Paragraphs { get; set; }
    /// <summary>Kept raw: the engine's list of tiers (or the health route's { status, tiers }).</summary>
    [JsonPropertyName("health")] public JsonElement Health { get; set; }
    [JsonPropertyName("state")][JsonConverter(typeof(LooseStringConverter))] public string? State { get; set; }
    [JsonPropertyName("schema_version")][JsonConverter(typeof(LooseStringConverter))] public string? SchemaVersion { get; set; }
    [JsonPropertyName("hidden_preferences")][JsonConverter(typeof(LooseIntConverter))] public int? HiddenPreferences { get; set; }
    [JsonPropertyName("signed_in")][JsonConverter(typeof(LooseBoolConverter))] public bool? SignedIn { get; set; }
    [JsonPropertyName("ruleset")][JsonConverter(typeof(LooseStringConverter))] public string? Ruleset { get; set; }
}

/// <summary>The four suggestion types (CLAUDE.md rule 3).</summary>
public enum Category { Correction, Improvement, Convention, Preference }

/// <summary>A decoded, validated suggestion, relative to its paragraph.</summary>
/// <remarks>
/// <c>Text</c> is the flagged words: the engine's <c>text</c>, checked against the paragraph that was
/// sent. The suggestion is shown, and a revision written back, only while the paragraph still says
/// exactly this at its range. <c>RuleId</c> is for actions and tests only, and <c>RuleName</c> (for
/// example "doubled-word") is a code too: neither is ever shown to the writer.
/// </remarks>
public sealed record Suggestion(
    string Id,
    string ParagraphId,
    int Begin,
    int End,
    Category Category,
    bool Critical,
    string Message,
    string Plain,
    string Why,
    string Source,
    IReadOnlyList<string> Replacements,
    string? Section,
    string? FixSafety,
    string? RuleId,
    string Text = "",
    string? RuleName = null,
    string? Tier = null,
    string? LearnRef = null)
{
    public int Length => End - Begin;

    /// <summary>The section as the writer reads it ("Methods"), or null when the advice assumed none, as on the website's cards.</summary>
    public string? SectionLabel => SectionNames.Label(Section);
}

/// <summary>Section ids the engine sends, in the writer's words (the website's sectionLabel).</summary>
public static class SectionNames
{
    private static readonly Dictionary<string, string> Names = new(StringComparer.Ordinal)
    {
        ["abstract"] = "Abstract", ["introduction"] = "Introduction", ["methods"] = "Methods",
        ["results"] = "Results", ["limitations"] = "Limitations", ["discussion"] = "Discussion",
        ["conclusion"] = "Conclusion", ["appendix"] = "Appendix",
    };

    public static string? Label(string? section)
    {
        string s = section?.Trim() ?? "";
        if (s.Length == 0 || s == "unknown" || s == "body") return null;
        return Names.TryGetValue(s, out var known) ? known : char.ToUpperInvariant(s[0]) + s.Substring(1);
    }
}

/// <summary>One entry of the reply's health: { tier, label, ok, state, detail, remedy }.</summary>
public sealed record TierHealth(string Tier, string Label, bool Ok, string State, string Detail, string Remedy)
{
    /// <summary>
    /// Not contributing, and not by choice: an outage the writer is told about. A tier switched off
    /// ("disabled") is not one, nor the opt-in learned tier without a model, as the engine's own is_degraded.
    /// </summary>
    public bool IsOutage => !Ok && State != "disabled" && !(Tier == "gec" && State == "missing");
}

/// <summary>A decoded reply.</summary>
public sealed record CheckReply(
    long? Revision,
    IReadOnlyDictionary<string, IReadOnlyList<Suggestion>> ByParagraph,
    bool Partial,
    string? PartialDetail,
    int DroppedSuggestions)
{
    /// <summary>The section each paragraph was checked as, by paragraph id.</summary>
    public IReadOnlyDictionary<string, string> Sections { get; init; } = new Dictionary<string, string>();
    public IReadOnlyList<TierHealth> Tiers { get; init; } = Array.Empty<TierHealth>();
    /// <summary>"ok" or "partial"; null from an engine that does not say.</summary>
    public string? State { get; init; }
    public string? SchemaVersion { get; init; }
    public int HiddenPreferences { get; init; }
    public bool SignedIn { get; init; }
    public string? Ruleset { get; init; }
}
