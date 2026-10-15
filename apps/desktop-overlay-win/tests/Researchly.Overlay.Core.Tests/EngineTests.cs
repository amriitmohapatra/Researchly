using System;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Researchly.Overlay.Core.Engine;
using Xunit;

namespace Researchly.Overlay.Core.Tests;

public class ReplyDecoderTests
{
    private static CheckParagraphsRequest Request(params (string Id, string Text)[] paragraphs) => new()
    {
        Revision = 7,
        Paragraphs = paragraphs.Select(p => new ParagraphPayload { Id = p.Id, Text = p.Text }).ToList(),
    };

    private static readonly CheckParagraphsRequest Basic = Request(
        ("p1", "The data was collected in teh field."),
        ("p2", "We think this is very novel."));

    [Fact]
    public void Decodes_the_documented_shape()
    {
        var reply = ReplyDecoder.Decode(Fixtures.Read("reply-basic.json"), Basic);
        Assert.Equal(7, reply.Revision);
        Assert.False(reply.Partial);                   // a disabled tier is not an outage
        Assert.Equal(0, reply.DroppedSuggestions);

        var p1 = reply.ByParagraph["p1"];
        Assert.Equal(2, p1.Count);
        Assert.Equal("sug-agree-1", p1[0].Id);           // sorted by position
        var spell = p1[1];
        Assert.Equal(Category.Correction, spell.Category);
        Assert.True(spell.Critical);
        Assert.Equal("teh", Basic.Paragraphs[0].Text.Substring(spell.Begin, spell.Length));
        Assert.Equal(new[] { "the" }, spell.Replacements);
        Assert.Equal("This word looks misspelt.", spell.Plain);
        Assert.Equal("Researchly test fixture", spell.Source);
        Assert.Equal("safe", spell.FixSafety);
        Assert.Equal("methods", spell.Section);

        var pref = Assert.Single(reply.ByParagraph["p2"]);
        Assert.Equal(Category.Preference, pref.Category);
        Assert.Equal("very novel", Basic.Paragraphs[1].Text.Substring(pref.Begin, pref.Length));
        Assert.Empty(pref.Replacements);
    }

    [Fact]
    public void Tolerates_unknown_fields_loose_types_and_older_field_names()
    {
        var reply = ReplyDecoder.Decode(Fixtures.Read("reply-tolerant.json"), Basic);
        Assert.Equal(7, reply.Revision);
        var p1 = reply.ByParagraph["p1"];
        Assert.Equal(2, p1.Count);

        var improvement = p1[0];
        Assert.Equal("single-replacement", improvement.Id);
        Assert.Equal(Category.Improvement, improvement.Category);
        Assert.False(improvement.Critical);
        Assert.Equal(new[] { "facts" }, improvement.Replacements);

        var correction = p1[1];
        Assert.Equal("42", correction.Id);
        Assert.Equal(Category.Correction, correction.Category);
        Assert.True(correction.Critical);              // missing: true for corrections
        Assert.Equal("Researchly test fixture", correction.Source);
        Assert.Equal(new[] { "the", "tea", "ten" }, correction.Replacements);

        Assert.Empty(reply.ByParagraph["p2"]);
        Assert.True(reply.Partial);                    // a bare tier list with a tier down
        Assert.Equal("Grammar is unavailable right now.", reply.PartialDetail);
    }

    [Fact]
    public void Drops_every_invalid_suggestion_and_keeps_the_valid_one()
    {
        string text = "Results " + char.ConvertFromUtf32(0x1F9EA) + " here.";
        var request = Request(("p1", text));
        var reply = ReplyDecoder.Decode(Fixtures.Read("reply-invalid.json"), request);
        var kept = Assert.Single(reply.ByParagraph["p1"]);
        Assert.Equal("ok", kept.Id);
        Assert.Equal(11, reply.DroppedSuggestions);
        Assert.False(reply.ByParagraph.ContainsKey("not-sent"));
    }

    [Fact]
    public void Offsets_are_utf16_code_units_after_emoji_and_combining_marks()
    {
        string text = "Results " + char.ConvertFromUtf32(0x1F9EA) + " show teh in cafe" + (char)0x0301 + "s.";
        var request = Request(("p1", text));
        var reply = ReplyDecoder.Decode(Fixtures.Read("reply-utf16.json"), request);
        var list = reply.ByParagraph["p1"];
        Assert.Equal(2, list.Count);
        Assert.Equal("teh", text.Substring(list[0].Begin, list[0].Length));
        Assert.Equal("cafe" + (char)0x0301 + "s", text.Substring(list[1].Begin, list[1].Length));
        // In code points (as Python counts) "teh" would start at 15, not 16.
        Assert.Equal(16, list[0].Begin);
    }

    [Fact]
    public void A_replacement_equal_to_the_flagged_text_is_removed()
    {
        var request = Request(("p1", "abc def"));
        var reply = ReplyDecoder.Decode("""
            {"revision":1,"paragraphs":[{"id":"p1","suggestions":[{"id":"x","begin":0,"end":3,"category":"improvement","message":"m","replacements":["abc","xyz"]}]}]}
            """, request);
        Assert.Equal(new[] { "xyz" }, reply.ByParagraph["p1"][0].Replacements);
    }

    [Fact]
    public void Garbage_is_a_bad_reply_not_a_crash()
    {
        var e = Assert.Throws<EngineException>(() => ReplyDecoder.Decode("<html>proxy error</html>", Basic));
        Assert.Equal("bad_reply", e.Code);
        Assert.Equal("bad_reply", Assert.Throws<EngineException>(() => ReplyDecoder.Decode("null", Basic)).Code);
    }

    [Fact]
    public void Degraded_status_marks_the_reply_partial()
    {
        var reply = ReplyDecoder.Decode("""
            {"revision":7,"paragraphs":[],"health":{"status":"degraded","tiers":[{"tier":"spelling","ok":false,"state":"error"}]}}
            """, Basic);
        Assert.True(reply.Partial);
        Assert.Equal("spelling is unavailable right now.", reply.PartialDetail);
        Assert.True(ReplyDecoder.Decode("""{"revision":7,"paragraphs":[],"state":"partial"}""", Basic).Partial);
    }

    [Fact]
    public void Missing_ids_get_a_stable_fallback()
    {
        var request = Request(("p1", "abc def"));
        var reply = ReplyDecoder.Decode("""
            {"paragraphs":[{"id":"p1","suggestions":[{"rule_id":"G101","begin":4,"end":7,"category":"improvement","message":"m"}]}]}
            """, request);
        Assert.Null(reply.Revision);
        Assert.Equal("G101:p1:4:7", reply.ByParagraph["p1"][0].Id);
    }
}

public class HttpEngineClientTests
{
    private sealed class Handler : HttpMessageHandler
    {
        public HttpRequestMessage? Request;
        public string? Body;
        public Func<HttpRequestMessage, HttpResponseMessage> Respond = _ => new HttpResponseMessage(HttpStatusCode.OK);

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Request = request;
            Body = request.Content == null ? null : await request.Content.ReadAsStringAsync(cancellationToken);
            return Respond(request);
        }
    }

    private static HttpResponseMessage Json(HttpStatusCode code, string json) =>
        new(code) { Content = new StringContent(json, Encoding.UTF8, "application/json") };

    private static CheckParagraphsRequest Sample() => new()
    {
        Revision = 12,
        Paragraphs = { new ParagraphPayload { Id = "p1", Text = "Synthetic sentence for the test.", Heading = "Methods" } },
        Options = new CheckOptionsPayload { ShowPreferences = false },
    };

    [Fact]
    public async Task Posts_the_contract_shape_without_an_origin_header()
    {
        var h = new Handler { Respond = _ => Json(HttpStatusCode.OK, """{"revision":12,"paragraphs":[{"id":"p1","suggestions":[]}],"state":"clear"}""") };
        using var client = new HttpEngineClient("https://engine.example.invalid/", h);
        var reply = await client.CheckAsync(Sample(), CancellationToken.None);

        Assert.Equal(12, reply.Revision);
        Assert.Equal(HttpMethod.Post, h.Request!.Method);
        Assert.Equal("https://engine.example.invalid/v1/check-paragraphs", h.Request.RequestUri!.ToString());
        Assert.False(h.Request.Headers.Contains("Origin"));
        Assert.Null(h.Request.Headers.Authorization);
        Assert.Equal("application/json", h.Request.Content!.Headers.ContentType!.MediaType);
        Assert.Contains("Researchly-Overlay-Windows", h.Request.Headers.UserAgent.ToString());

        using var doc = JsonDocument.Parse(h.Body!);
        var root = doc.RootElement;
        Assert.Equal(12, root.GetProperty("revision").GetInt64());
        var p = root.GetProperty("paragraphs")[0];
        Assert.Equal("p1", p.GetProperty("id").GetString());
        Assert.Equal("Methods", p.GetProperty("heading").GetString());
        Assert.False(p.TryGetProperty("style", out _));            // null fields are not sent
        Assert.False(root.GetProperty("options").GetProperty("show_preferences").GetBoolean());
        Assert.False(root.GetProperty("options").TryGetProperty("spelling", out _));
    }

    [Fact]
    public async Task Sends_a_bearer_token_when_signed_in()
    {
        var h = new Handler { Respond = _ => Json(HttpStatusCode.OK, """{"revision":12,"paragraphs":[]}""") };
        using var client = new HttpEngineClient("https://engine.example.invalid", h) { AccessToken = "synthetic-token" };
        await client.CheckAsync(Sample(), CancellationToken.None);
        Assert.Equal("Bearer", h.Request!.Headers.Authorization!.Scheme);
    }

    [Theory]
    [InlineData(HttpStatusCode.NotFound, "not_found")]
    [InlineData(HttpStatusCode.Unauthorized, "refused")]
    [InlineData(HttpStatusCode.InternalServerError, "engine_error")]
    public async Task Http_errors_become_engine_errors(HttpStatusCode status, string code)
    {
        var h = new Handler { Respond = _ => Json(status, "not json") };
        using var client = new HttpEngineClient("http://127.0.0.1:3517", h);
        var e = await Assert.ThrowsAsync<EngineException>(() => client.CheckAsync(Sample(), CancellationToken.None));
        Assert.Equal(code, e.Code);
        Assert.Equal((int)status, e.HttpStatus);
    }

    [Fact]
    public async Task Rate_limits_carry_the_engines_code_and_retry_after()
    {
        var h = new Handler
        {
            Respond = _ =>
            {
                var r = Json((HttpStatusCode)429, """{"error":{"code":"rate_limited","message":"slow down","request_id":"r1"}}""");
                r.Headers.RetryAfter = new System.Net.Http.Headers.RetryConditionHeaderValue(TimeSpan.FromSeconds(7));
                return r;
            },
        };
        using var client = new HttpEngineClient("http://127.0.0.1:3517", h);
        var e = await Assert.ThrowsAsync<EngineException>(() => client.CheckAsync(Sample(), CancellationToken.None));
        Assert.Equal("rate_limited", e.Code);
        Assert.Equal(TimeSpan.FromSeconds(7), e.RetryAfter);
        Assert.DoesNotContain("slow down", e.Message);   // our words, not the server's
    }

    [Fact]
    public async Task Network_failures_become_unreachable()
    {
        var h = new Handler { Respond = _ => throw new HttpRequestException("connection refused") };
        using var client = new HttpEngineClient("http://127.0.0.1:3517", h);
        var e = await Assert.ThrowsAsync<EngineException>(() => client.CheckAsync(Sample(), CancellationToken.None));
        Assert.Equal("unreachable", e.Code);
    }

    [Fact]
    public async Task Cancellation_is_not_reported_as_a_failure()
    {
        var h = new Handler { Respond = _ => throw new TaskCanceledException() };
        using var client = new HttpEngineClient("http://127.0.0.1:3517", h);
        using var cts = new CancellationTokenSource();
        cts.Cancel();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => client.CheckAsync(Sample(), cts.Token));
    }
}
