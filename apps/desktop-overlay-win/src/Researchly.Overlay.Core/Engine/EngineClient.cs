using System;
using System.Collections.Generic;
using System.Globalization;
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
            401 or 403 => "refused",
            404 => "not_found",
            >= 500 => "engine_error",
            _ => "refused",
        };
        string message = status switch
        {
            429 => "The engine is busy; trying again shortly.",
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
        int dropped = 0;
        foreach (var pr in dto.Paragraphs ?? new List<ParagraphResultDto?>())
        {
            if (pr?.Id == null || !sent.TryGetValue(pr.Id, out var text)) { dropped += pr?.Suggestions?.Count ?? 0; continue; }
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

        var (partial, detail) = ReadHealth(dto);
        return new CheckReply(dto.Revision, byParagraph, partial, detail, dropped);
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
            replacements, s.Section, s.FixSafety, s.RuleId);
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
    /// Partial when the reply's state says so, or its health says so. Health may be
    /// the service's { status, tiers: [...] } (status "degraded" means a tier the
    /// service is configured to run is down) or a bare list of tiers, where a tier
    /// with ok = false counts unless its state is "disabled" (switched off on purpose).
    /// </summary>
    private static (bool Partial, string? Detail) ReadHealth(CheckParagraphsResponseDto dto)
    {
        bool partial = string.Equals(dto.State, "partial", StringComparison.OrdinalIgnoreCase);
        var h = dto.Health;
        JsonElement tiers = default;
        bool hasStatus = false;
        if (h.ValueKind == JsonValueKind.Object)
        {
            if (h.TryGetProperty("status", out var st) && st.ValueKind == JsonValueKind.String)
            {
                hasStatus = true;
                if (string.Equals(st.GetString(), "degraded", StringComparison.OrdinalIgnoreCase)) partial = true;
            }
            if (h.TryGetProperty("tiers", out var t)) tiers = t;
        }
        else if (h.ValueKind == JsonValueKind.Array)
        {
            tiers = h;
        }

        string? detail = null;
        if (tiers.ValueKind == JsonValueKind.Array)
        {
            foreach (var tier in tiers.EnumerateArray())
            {
                if (tier.ValueKind != JsonValueKind.Object) continue;
                bool down = tier.TryGetProperty("ok", out var ok) && ok.ValueKind == JsonValueKind.False;
                bool disabled = tier.TryGetProperty("state", out var s) && s.ValueKind == JsonValueKind.String
                                && string.Equals(s.GetString(), "disabled", StringComparison.OrdinalIgnoreCase);
                if (!down || disabled) continue;
                if (!hasStatus) partial = true;
                if (detail == null)
                {
                    string label = tier.TryGetProperty("label", out var l) && l.ValueKind == JsonValueKind.String ? l.GetString()!
                        : tier.TryGetProperty("tier", out var n) && n.ValueKind == JsonValueKind.String ? n.GetString()! : "A check";
                    detail = $"{label} is unavailable right now.";
                }
            }
        }
        if (!partial) return (false, null);
        return (true, detail ?? "Some checks are unavailable right now.");
    }
}
