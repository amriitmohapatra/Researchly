using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Researchly.Overlay.Core.Engine;

// The live-check contract, docs/inline-review-design.md section 5:
//   POST {engine}/v1/check-paragraphs
//   request  { revision, paragraphs: [{ id, text, style?, heading? }], options }
//   response { revision, paragraphs: [{ id, suggestions: [...] }], health, state }
// Offsets are UTF-16 code units within the paragraph. Decoding is tolerant:
// unknown fields are ignored and a malformed suggestion is dropped, not fatal.

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
}

public sealed class ParagraphResultDto
{
    [JsonPropertyName("id")][JsonConverter(typeof(LooseStringConverter))] public string? Id { get; set; }
    [JsonPropertyName("suggestions")][JsonConverter(typeof(LooseObjectListConverter<SuggestionDto>))] public List<SuggestionDto?>? Suggestions { get; set; }
}

public sealed class CheckParagraphsResponseDto
{
    [JsonPropertyName("revision")][JsonConverter(typeof(LooseLongConverter))] public long? Revision { get; set; }
    [JsonPropertyName("paragraphs")][JsonConverter(typeof(LooseObjectListConverter<ParagraphResultDto>))] public List<ParagraphResultDto?>? Paragraphs { get; set; }
    /// <summary>Kept raw: the engine's health object (status and tiers) or a list of tiers.</summary>
    [JsonPropertyName("health")] public JsonElement Health { get; set; }
    [JsonPropertyName("state")][JsonConverter(typeof(LooseStringConverter))] public string? State { get; set; }
}

/// <summary>The four suggestion types (CLAUDE.md rule 3).</summary>
public enum Category { Correction, Improvement, Convention, Preference }

/// <summary>A decoded, validated suggestion, relative to its paragraph.</summary>
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
    string? RuleId)
{
    public int Length => End - Begin;
}

/// <summary>A decoded reply.</summary>
public sealed record CheckReply(
    long? Revision,
    IReadOnlyDictionary<string, IReadOnlyList<Suggestion>> ByParagraph,
    bool Partial,
    string? PartialDetail,
    int DroppedSuggestions);
