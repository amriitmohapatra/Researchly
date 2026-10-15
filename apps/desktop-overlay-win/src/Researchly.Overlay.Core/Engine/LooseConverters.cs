using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Researchly.Overlay.Core.Engine;

// Tolerant readers: a field of an unexpected type becomes null rather than
// failing the whole reply. The client presents what it can and drops the rest.

internal static class Loose
{
    public static string? ReadString(ref Utf8JsonReader reader)
    {
        switch (reader.TokenType)
        {
            case JsonTokenType.String: return reader.GetString();
            case JsonTokenType.Number:
                return reader.TryGetInt64(out var l) ? l.ToString(CultureInfo.InvariantCulture)
                    : reader.GetDouble().ToString(CultureInfo.InvariantCulture);
            case JsonTokenType.True: return "true";
            case JsonTokenType.False: return "false";
            case JsonTokenType.Null: return null;
            case JsonTokenType.StartObject:
            {
                // An object such as { "label": "...", "url": "..." }: take a readable field.
                using var doc = JsonDocument.ParseValue(ref reader);
                foreach (var key in new[] { "label", "title", "text", "name", "value" })
                    if (doc.RootElement.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String)
                        return v.GetString();
                return null;
            }
            default:
                reader.Skip();
                return null;
        }
    }
}

internal sealed class LooseStringConverter : JsonConverter<string?>
{
    public override bool HandleNull => true;
    public override string? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) =>
        Loose.ReadString(ref reader);
    public override void Write(Utf8JsonWriter writer, string? value, JsonSerializerOptions options)
    {
        if (value == null) writer.WriteNullValue(); else writer.WriteStringValue(value);
    }
}

internal sealed class LooseIntConverter : JsonConverter<int?>
{
    public override bool HandleNull => true;
    public override int? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.Number)
            return reader.TryGetInt32(out var i) ? i : null;
        var s = Loose.ReadString(ref reader);
        return int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out var p) ? p : null;
    }
    public override void Write(Utf8JsonWriter writer, int? value, JsonSerializerOptions options)
    {
        if (value is int v) writer.WriteNumberValue(v); else writer.WriteNullValue();
    }
}

internal sealed class LooseLongConverter : JsonConverter<long?>
{
    public override bool HandleNull => true;
    public override long? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.Number)
            return reader.TryGetInt64(out var i) ? i : null;
        var s = Loose.ReadString(ref reader);
        return long.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out var p) ? p : null;
    }
    public override void Write(Utf8JsonWriter writer, long? value, JsonSerializerOptions options)
    {
        if (value is long v) writer.WriteNumberValue(v); else writer.WriteNullValue();
    }
}

internal sealed class LooseBoolConverter : JsonConverter<bool?>
{
    public override bool HandleNull => true;
    public override bool? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        switch (reader.TokenType)
        {
            case JsonTokenType.True: return true;
            case JsonTokenType.False: return false;
            case JsonTokenType.Number: return reader.TryGetInt64(out var l) ? l != 0 : null;
            default:
                var s = Loose.ReadString(ref reader);
                return bool.TryParse(s, out var b) ? b : null;
        }
    }
    public override void Write(Utf8JsonWriter writer, bool? value, JsonSerializerOptions options)
    {
        if (value is bool v) writer.WriteBooleanValue(v); else writer.WriteNullValue();
    }
}

/// <summary>A list of objects where an element that is not an object (a string, a number, null) is skipped.</summary>
internal sealed class LooseObjectListConverter<T> : JsonConverter<List<T?>?> where T : class
{
    public override bool HandleNull => true;
    public override List<T?>? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType != JsonTokenType.StartArray)
        {
            reader.Skip();
            return null;
        }
        var list = new List<T?>();
        while (reader.Read() && reader.TokenType != JsonTokenType.EndArray)
        {
            if (reader.TokenType == JsonTokenType.StartObject)
                list.Add(JsonSerializer.Deserialize<T>(ref reader, options));
            else
                reader.Skip();
        }
        return list;
    }
    public override void Write(Utf8JsonWriter writer, List<T?>? value, JsonSerializerOptions options) =>
        JsonSerializer.Serialize(writer, value, options);
}

/// <summary>A list of strings, or of objects with a "text"/"value" field, or a single string.</summary>
internal sealed class LooseStringListConverter : JsonConverter<List<string>?>
{
    public override bool HandleNull => true;
    public override List<string>? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.Null) return null;
        if (reader.TokenType != JsonTokenType.StartArray)
        {
            var single = Loose.ReadString(ref reader);
            return single == null ? null : new List<string> { single };
        }
        var list = new List<string>();
        while (reader.Read() && reader.TokenType != JsonTokenType.EndArray)
        {
            var s = Loose.ReadString(ref reader);
            if (s != null) list.Add(s);
        }
        return list;
    }
    public override void Write(Utf8JsonWriter writer, List<string>? value, JsonSerializerOptions options)
    {
        if (value == null) { writer.WriteNullValue(); return; }
        writer.WriteStartArray();
        foreach (var s in value) writer.WriteStringValue(s);
        writer.WriteEndArray();
    }
}
