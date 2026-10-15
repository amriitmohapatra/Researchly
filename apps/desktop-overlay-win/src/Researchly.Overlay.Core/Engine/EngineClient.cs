using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace Researchly.Overlay.Core.Engine;

/// <summary>Why a check failed. The message never contains document text.</summary>
public sealed class EngineException : Exception
{
    public EngineException(string code, string message, int? httpStatus = null, TimeSpan? retryAfter = null, Exception? inner = null)
        : base(message, inner)
    {
        Code = code;
        HttpStatus = httpStatus;
        RetryAfter = retryAfter;
    }

    /// <summary>"unreachable", "timeout", "rate_limited", "refused", "bad_reply", or the engine's own error code.</summary>
    public string Code { get; }
    public int? HttpStatus { get; }
    public TimeSpan? RetryAfter { get; }

    /// <summary>Statuses meaning "this request will never succeed as it is": not retried until the text changes.</summary>
    public static bool IsRejection(int? status) => status is 400 or 401 or 403 or 413 or 422;

    /// <summary>Whether the same request could succeed later (so a retry with backoff makes sense).</summary>
    public bool Retryable => !IsRejection(HttpStatus);
}

/// <summary>Sends paragraphs to the engine the writer chose.</summary>
public interface IEngineClient
{
    Task<CheckReply> CheckAsync(CheckParagraphsRequest request, CancellationToken cancellationToken);
}

/// <summary>
/// The HTTP client for <c>POST {engine}/v1/check-paragraphs</c>. Sends no
/// Origin header (a native client; CORS is for browsers), no cookies, and an
/// optional bearer token. Holds text only for the duration of the request.
/// </summary>
public sealed class HttpEngineClient : IEngineClient, IDisposable
{
    public static readonly TimeSpan DefaultTimeout = TimeSpan.FromSeconds(10);

    private static readonly JsonSerializerOptions WriteOptions = new() { WriteIndented = false };

    private readonly HttpClient _http;
    private readonly bool _ownsHttp;

    public HttpEngineClient(string baseUrl, HttpMessageHandler? handler = null, TimeSpan? timeout = null, string? userAgentVersion = null)
    {
        BaseUrl = baseUrl.TrimEnd('/');
        _http = handler == null
            ? new HttpClient(new SocketsHttpHandler { UseCookies = false, AllowAutoRedirect = false, PooledConnectionLifetime = TimeSpan.FromMinutes(5) })
            : new HttpClient(handler, disposeHandler: false);
        _ownsHttp = true;
        _http.Timeout = timeout ?? DefaultTimeout;
        _http.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("Researchly-Overlay-Windows", userAgentVersion ?? "0.1"));
        _http.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
    }

    public string BaseUrl { get; }

    /// <summary>Optional "Bearer" token for a signed-in caller; never written to disk by this client.</summary>
    public string? AccessToken { get; set; }

    public async Task<CheckReply> CheckAsync(CheckParagraphsRequest request, CancellationToken cancellationToken)
    {
        byte[] body = JsonSerializer.SerializeToUtf8Bytes(request, WriteOptions);
        using var message = new HttpRequestMessage(HttpMethod.Post, BaseUrl + "/v1/check-paragraphs")
        {
            Content = new ByteArrayContent(body),
        };
        message.Content.Headers.ContentType = new MediaTypeHeaderValue("application/json") { CharSet = "utf-8" };
        if (!string.IsNullOrEmpty(AccessToken))
            message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", AccessToken);

        HttpResponseMessage response;
        try
        {
            response = await _http.SendAsync(message, HttpCompletionOption.ResponseContentRead, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (TaskCanceledException e)
        {
            throw new EngineException("timeout", "The engine did not answer in time.", inner: e);
        }
        catch (HttpRequestException e)
        {
            throw new EngineException("unreachable", "The engine could not be reached.", inner: e);
        }

        using (response)
        {
            string json = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
                throw ErrorFrom(response, json);
            return ReplyDecoder.Decode(json, request);
        }
    }

    private static EngineException ErrorFrom(HttpResponseMessage response, string body)
    {
        int status = (int)response.StatusCode;
        string code = status switch
        {
            429 => "rate_limited",
            422 => "invalid_request",
            413 => "payload_too_large",
            401 or 403 => "refused",
            404 => "not_found",
            >= 500 => "engine_error",
            _ => "refused",
        };
        string message = status switch
        {
            429 => "The engine is busy; trying again shortly.",
            422 or 400 => "The engine could not check this text as it was sent.",
            413 => "This text is too long to check as you type.",
            401 or 403 => "The engine refused the request.",
            404 => "This engine does not offer live checks yet.",
            >= 500 => "The engine had a problem.",
            _ => "The engine refused the request.",
        };
        // The service's error body: { "error": { "code", "message", "request_id" } }.
        // Only the code is used; messages are written by us.
        try
        {
            using var doc = JsonDocument.Parse(body);
            if (doc.RootElement.ValueKind == JsonValueKind.Object
                && doc.RootElement.TryGetProperty("error", out var err)
                && err.ValueKind == JsonValueKind.Object
                && err.TryGetProperty("code", out var c) && c.ValueKind == JsonValueKind.String)
                code = c.GetString() ?? code;
        }
        catch (JsonException) { }

        TimeSpan? retryAfter = null;
        if (response.Headers.RetryAfter is { } ra)
        {
            if (ra.Delta is { } delta) retryAfter = delta;
            else if (ra.Date is { } date) retryAfter = date - DateTimeOffset.UtcNow;
        }
        return new EngineException(code, message, status, retryAfter);
    }

    public void Dispose()
    {
        if (_ownsHttp) _http.Dispose();
    }
}

/// <summary>Turns a reply body into validated suggestions.</summary>
public static class ReplyDecoder
{
    private static readonly JsonSerializerOptions ReadOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        AllowTrailingCommas = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
    };

    /// <summary>
    /// Decodes and validates a reply against the request it answers. A suggestion
    /// is kept only when its paragraph was in the request, its range is a valid,
    /// non-empty UTF-16 range of the text that was sent (not splitting a
    /// surrogate pair), its category is one of the four, and, when the engine
    /// echoes the flagged text, that text matches. Anything else is dropped and
    /// counted.
    /// </summary>
    public static CheckReply Decode(string json, CheckParagraphsRequest request)
    {
        CheckParagraphsResponseDto? dto;
        try
        {
            dto = JsonSerializer.Deserialize<CheckParagraphsResponseDto>(json, ReadOptions);
        }
        catch (JsonException e)
        {
            throw new EngineException("bad_reply", "The engine's reply could not be read.", inner: e);
        }
        if (dto == null) throw new EngineException("bad_reply", "The engine's reply was empty.");

        var sent = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var p in request.Paragraphs) sent[p.Id] = p.Text;

        var byParagraph = new Dictionary<string, IReadOnlyList<Suggestion>>(StringComparer.Ordinal);
        var sections = new Dictionary<string, string>(StringComparer.Ordinal);
        int dropped = 0;
        foreach (var pr in dto.Paragraphs ?? new List<ParagraphResultDto?>())
        {
            if (pr?.Id == null || !sent.TryGetValue(pr.Id, out var text)) { dropped += pr?.Suggestions?.Count ?? 0; continue; }
            if (!string.IsNullOrEmpty(pr.Section)) sections[pr.Id] = pr.Section!;
            var list = new List<Suggestion>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var s in pr.Suggestions ?? new List<SuggestionDto?>())
            {
                var ok = Validate(s, pr.Id, text);
                if (ok == null || !seen.Add(ok.Id)) { dropped++; continue; }
                list.Add(ok);
            }
            list.Sort((a, b) => a.Begin != b.Begin ? a.Begin.CompareTo(b.Begin) : a.End.CompareTo(b.End));
            byParagraph[pr.Id] = list;
        }

        var (partial, detail, tiers) = ReadHealth(dto);
        return new CheckReply(dto.Revision, byParagraph, partial, detail, dropped)
        {
            Sections = sections,
            Tiers = tiers,
            State = dto.State,
            SchemaVersion = dto.SchemaVersion,
            HiddenPreferences = Math.Max(0, dto.HiddenPreferences ?? 0),
            SignedIn = dto.SignedIn ?? false,
            Ruleset = dto.Ruleset,
        };
    }

    private static Suggestion? Validate(SuggestionDto? s, string paragraphId, string text)
    {
        if (s?.Begin is not int begin || s.End is not int end) return null;
        if (!Text.Utf16.IsValidRange(text, begin, end)) return null;
        if (s.Text is { Length: > 0 } echoed && !string.Equals(text.Substring(begin, end - begin), echoed, StringComparison.Ordinal))
            return null;
        if (!TryCategory(s.Category, out var category)) return null;
        string message = s.Message?.Trim() ?? "";
        if (message.Length == 0) return null;
        var replacements = new List<string>();
        if (s.Replacements != null) replacements.AddRange(s.Replacements);
        else if (s.Replacement != null) replacements.Add(s.Replacement);
        // A replacement equal to the flagged text would be a no-op accept.
        string flagged = text.Substring(begin, end - begin);
        replacements.RemoveAll(r => string.Equals(r, flagged, StringComparison.Ordinal));
        string id = string.IsNullOrWhiteSpace(s.Id)
            ? string.Create(CultureInfo.InvariantCulture, $"{s.RuleId ?? "rule"}:{paragraphId}:{begin}:{end}")
            : s.Id!;
        return new Suggestion(
            id, paragraphId, begin, end, category,
            s.Critical ?? category == Category.Correction,
            message, s.Plain?.Trim() ?? "", s.Why?.Trim() ?? "", s.Source?.Trim() ?? "",
            replacements, s.Section, s.FixSafety, s.RuleId,
            Text: flagged, RuleName: s.RuleName, Tier: s.Tier, LearnRef: s.LearnRef);
    }

    public static bool TryCategory(string? value, out Category category)
    {
        switch (value?.Trim().ToLowerInvariant())
        {
            case "correction": category = Category.Correction; return true;
            case "improvement": category = Category.Improvement; return true;
            case "convention": category = Category.Convention; return true;
            case "preference": category = Category.Preference; return true;
            default: category = default; return false;
        }
    }

    /// <summary>
    /// Reads health as the engine sends it (a list of tiers) or as the health route does
    /// ({ status, tiers }). The reply's state decides when present: "partial" is partial and
    /// "ok" is not, whatever the tiers say (a tier switched off, or the learned tier without a
    /// model, is listed with ok = false and is not an outage). Without a state, a tier that is
    /// an outage (<see cref="TierHealth.IsOutage"/>) or a "degraded" status makes it partial.
    /// </summary>
    private static (bool Partial, string? Detail, IReadOnlyList<TierHealth> Tiers) ReadHealth(CheckParagraphsResponseDto dto)
    {
        var h = dto.Health;
        JsonElement list = default;
        bool statusDegraded = false;
        if (h.ValueKind == JsonValueKind.Object)
        {
            if (h.TryGetProperty("status", out var st) && st.ValueKind == JsonValueKind.String
                && string.Equals(st.GetString(), "degraded", StringComparison.OrdinalIgnoreCase))
                statusDegraded = true;
            if (h.TryGetProperty("tiers", out var t)) list = t;
        }
        else if (h.ValueKind == JsonValueKind.Array)
        {
            list = h;
        }

        var tiers = new List<TierHealth>();
        if (list.ValueKind == JsonValueKind.Array)
        {
            foreach (var tier in list.EnumerateArray())
            {
                if (tier.ValueKind != JsonValueKind.Object) continue;
                string Str(string key) => tier.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() ?? "" : "";
                bool ok = !(tier.TryGetProperty("ok", out var o) && o.ValueKind == JsonValueKind.False);
                string name = Str("tier");
                string label = Str("label");
                if (label.Length == 0) label = name.Length > 0 ? name : "A check";
                tiers.Add(new TierHealth(name, label, ok, Str("state").ToLowerInvariant(), Str("detail"), Str("remedy")));
            }
        }

        var down = tiers.Where(t => t.IsOutage).ToList();
        bool partial = dto.State?.Trim().ToLowerInvariant() switch
        {
            "partial" => true,
            "ok" => false,
            _ => statusDegraded || down.Count > 0,
        };
        if (!partial) return (false, null, tiers);
        if (down.Count == 0) return (true, "Some checks are unavailable right now.", tiers);
        string names = string.Join(", ", down.Select(t => t.Label));
        string verb = down.Count == 1 ? "is" : "are";
        return (true, $"{names} {verb} unavailable right now.", tiers);
    }
}
