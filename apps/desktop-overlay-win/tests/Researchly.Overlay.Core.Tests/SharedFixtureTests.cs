using System;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading.Tasks;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Session;
using Researchly.Overlay.Core.State;
using Researchly.Overlay.Core.Text;
using Xunit;

namespace Researchly.Overlay.Core.Tests;

/// <summary>
/// The client against real replies of POST /v1/check-paragraphs
/// (packages/contract/fixtures/check-paragraphs, made by the engine service and
/// compared with it in services/engine; the macOS client decodes the same files).
/// </summary>
public class SharedFixtureTests
{
    private readonly ManualScheduler _clock = new();
    private readonly FakeEngine _engine = new();
    private readonly LiveCheckSession _session;

    public SharedFixtureTests()
    {
        _session = new LiveCheckSession(_engine, _clock, () => new CheckOptionsPayload());
    }

    [Fact]
    public async Task The_ok_reply_decodes_fully_through_the_http_client()
    {
        var fx = Fixtures.Shared("ok");
        var reply = await fx.ThroughClientAsync();
        Assert.Equal(41, reply.Revision);
        Assert.Equal("1", reply.SchemaVersion);
        Assert.Equal("ok", reply.State);
        Assert.False(reply.SignedIn);
        Assert.Equal(0, reply.HiddenPreferences);
        Assert.NotNull(reply.Ruleset);
        Assert.Equal(0, reply.DroppedSuggestions);
        Assert.Equal(new[] { "results", "methods", "discussion", "unknown" },
            new[] { "p1", "p2", "p3", "p4" }.Select(id => reply.Sections[id]));
        var p1 = reply.ByParagraph["p1"];
        Assert.True(p1.Count >= 2);
        string text = fx.Text("p1");
        foreach (var s in p1)
        {
            Assert.Equal(16, s.Id.Length);
            Assert.True(s.Id.All(Uri.IsHexDigit));
            Assert.Equal(text.Substring(s.Begin, s.End - s.Begin), s.Text);
            Assert.False(string.IsNullOrEmpty(s.Plain));
            Assert.False(string.IsNullOrEmpty(s.Why));
            Assert.False(string.IsNullOrEmpty(s.Source));
            Assert.NotNull(s.RuleId);
            Assert.NotNull(s.RuleName);
            Assert.NotNull(s.Tier);
            Assert.Equal(s.Category == Category.Correction, s.Critical);
            Assert.Equal("Results", s.SectionLabel);
        }
        var doubled = p1.Single(s => s.RuleId == "W207");
        Assert.Equal("the the", doubled.Text);
        Assert.Equal(new[] { "the" }, doubled.Replacements);
        Assert.Equal("safe", doubled.FixSafety);
        Assert.Equal("spelling-and-grammar", doubled.LearnRef);
        Assert.Empty(reply.ByParagraph["p2"]);       // passive in Methods: never flagged
        Assert.NotEmpty(reply.ByParagraph["p3"]);    // the same words in Discussion
        Assert.Empty(reply.ByParagraph["p4"]);
    }

    [Fact]
    public async Task Offsets_are_utf16_after_astral_characters()
    {
        var fx = Fixtures.Shared("ok");
        var reply = await fx.ThroughClientAsync();
        string text = fx.Text("p1");
        Assert.Contains(text, char.IsSurrogate);
        foreach (var s in reply.ByParagraph["p1"])
            Assert.True(Utf16.IsValidRange(text, s.Begin, s.End));
    }

    [Fact]
    public void A_suggestion_whose_words_are_not_there_is_dropped()
    {
        var fx = Fixtures.Shared("ok");
        var body = JsonNode.Parse(fx.ResponseJson)!;
        var first = body["paragraphs"]![0]!["suggestions"]![0]!;
        first["begin"] = first["begin"]!.GetValue<int>() + 1;    // same length, wrong place
        first["end"] = first["end"]!.GetValue<int>() + 1;
        var reply = ReplyDecoder.Decode(body.ToJsonString(), fx.Request);
        Assert.Equal(1, reply.DroppedSuggestions);
        Assert.DoesNotContain(reply.ByParagraph["p1"], s => s.Id == first["id"]!.GetValue<string>());
    }

    [Fact]
    public async Task Disabled_and_missing_optional_tiers_are_not_an_outage()
    {
        foreach (var name in new[] { "ok", "clear" })
        {
            var reply = await Fixtures.Shared(name).ThroughClientAsync();
            Assert.False(reply.Partial, name);
            Assert.Null(reply.PartialDetail);
            Assert.Contains(reply.Tiers, t => t.State == "disabled" || t.State == "missing");
            Assert.DoesNotContain(reply.Tiers, t => t.IsOutage);
        }
        // Without `state`, the tiers alone say the same.
        var body = JsonNode.Parse(Fixtures.Shared("ok").ResponseJson)!.AsObject();
        body.Remove("state");
        Assert.False(ReplyDecoder.Decode(body.ToJsonString(), Fixtures.Shared("ok").Request).Partial);
    }

    [Fact]
    public async Task The_partial_reply_names_the_tier_that_is_down()
    {
        var fx = Fixtures.Shared("partial");
        var reply = await fx.ThroughClientAsync();
        Assert.True(reply.Partial);
        Assert.Equal("Grammar is unavailable right now.", reply.PartialDetail);
        Assert.Single(reply.Tiers, t => t.IsOutage);
        Assert.NotEmpty(reply.ByParagraph["s.1"]);   // the tiers that ran still count

        _session.Start(fx.Text("s.1"));
        _engine.AnswerJson(_engine.Last, Rekeyed(fx, _engine.Last.Request));
        Assert.Equal(OverlayState.Partial, _session.State.State);
        Assert.Equal("Grammar is unavailable right now.", _session.State.Detail);
        Assert.NotEmpty(_session.Visible);
    }

    [Fact]
    public void The_clear_reply_gives_the_clear_state()
    {
        var fx = Fixtures.Shared("clear");
        _session.Start(fx.Text("only"));
        _engine.AnswerJson(_engine.Last, Rekeyed(fx, _engine.Last.Request));
        Assert.Equal(OverlayState.Clear, _session.State.State);
        Assert.Null(_session.State.Detail);
    }

    [Fact]
    public async Task A_422_is_shown_and_not_retried_until_an_edit()
    {
        var fx = Fixtures.Shared("invalid-422");
        var e = await Assert.ThrowsAsync<EngineException>(() => fx.ThroughClientAsync());
        Assert.Equal(422, e.HttpStatus);
        Assert.Equal("invalid_request", e.Code);
        Assert.False(e.Retryable);

        _session.Start("We fitted a renewal model to weekly case counts.");
        _engine.Complete(_engine.Last, fx.ThroughClientAsync(_engine.Last.Request));
        Assert.Equal(OverlayState.Offline, _session.State.State);
        Assert.Contains("after your next edit", _session.State.Detail);
        Assert.Equal(0, _clock.Pending);                  // no retry loop
        _clock.AdvanceSeconds(120);
        Assert.Single(_engine.Calls);
        // An edit makes the paragraph worth sending again.
        _session.UpdateText("We fitted a renewal model to daily case counts.");
        _clock.AdvanceSeconds(1.5);
        Assert.Equal(2, _engine.Calls.Count);
        _engine.AnswerClear(_engine.Last);
        Assert.Equal(OverlayState.Clear, _session.State.State);
    }

    [Fact]
    public void A_rejected_paragraph_stays_unchecked_but_the_others_go_on()
    {
        _session.Start("First paragraph here.\nSecond paragraph here.");
        _engine.Fail(_engine.Last, "invalid_request", status: 422);
        Assert.Equal(OverlayState.Offline, _session.State.State);
        _session.UpdateText("First paragraph here.\nSecond paragraph here.\nA third one.");
        _clock.AdvanceSeconds(1.5);
        Assert.Equal(new[] { "A third one." }, _engine.Last.Request.Paragraphs.Select(p => p.Text));
        _engine.AnswerClear(_engine.Last);
        Assert.Equal(OverlayState.Partial, _session.State.State);
        Assert.Contains("2 paragraphs couldn’t be checked", _session.State.Detail);
    }

    [Fact]
    public async Task A_429_waits_as_long_as_the_engine_says()
    {
        var fx = Fixtures.Shared("rate-limited-429");
        var e = await Assert.ThrowsAsync<EngineException>(() => fx.ThroughClientAsync());
        Assert.Equal("rate_limited", e.Code);
        Assert.True(e.Retryable);
        var wait = TimeSpan.FromSeconds(int.Parse(fx.Headers["retry-after"], System.Globalization.CultureInfo.InvariantCulture));
        Assert.Equal(wait, e.RetryAfter);

        _session.Start("We fitted a renewal model to weekly case counts.");
        _engine.Complete(_engine.Last, fx.ThroughClientAsync(_engine.Last.Request));
        Assert.Equal(OverlayState.Offline, _session.State.State);
        Assert.Equal(wait, _clock.NextDue);               // not the usual 2 s
        _clock.Advance(wait);
        Assert.Equal(2, _engine.Calls.Count);
    }

    [Fact]
    public void The_request_is_what_the_engine_accepted()
    {
        var fx = Fixtures.Shared("ok");
        var sent = new CheckParagraphsRequest
        {
            Revision = fx.Request.Revision,
            Paragraphs = fx.Request.Paragraphs.Select(p => new ParagraphPayload { Id = p.Id, Text = p.Text, Heading = p.Heading }).ToList(),
            Options = new CheckOptionsPayload { ShowPreferences = false },
        };
        var encoded = JsonNode.Parse(JsonSerializer.Serialize(sent));
        Assert.True(JsonNode.DeepEquals(JsonNode.Parse(fx.RequestJson), encoded), encoded!.ToJsonString());
    }

    [Fact]
    public void Requests_stay_inside_the_engines_limits()
    {
        string tooLong = string.Concat(Enumerable.Repeat("word ", 4_100));      // 20,500 characters
        var shorts = Enumerable.Range(0, 80).Select(i => $"Paragraph {i} is short.");
        _session.Start(string.Join("\n", new[] { tooLong }.Concat(shorts)));
        while (true)
        {
            var req = _engine.Last.Request;
            Assert.True(req.Paragraphs.Count <= LiveLimits.MaxParagraphs);
            Assert.True(req.Paragraphs.Sum(p => LiveLimits.Characters(p.Text)) <= LiveLimits.MaxCharacters);
            Assert.DoesNotContain(req.Paragraphs, p => p.Text == tooLong);
            int before = _engine.Calls.Count;
            _engine.AnswerClear(_engine.Last);
            _clock.AdvanceSeconds(0);
            if (_engine.Calls.Count == before) break;
        }
        Assert.Equal(OverlayState.Partial, _session.State.State);
        Assert.Contains("too long to check as you type", _session.State.Detail);
        Assert.Equal(4, LiveLimits.Characters("a\U0001F600bé"));    // code points, as the engine counts
    }

    /// <summary>The fixture's reply, addressed to the ids and revision this session sent.</summary>
    private static string Rekeyed(SharedExchange fx, CheckParagraphsRequest sent)
    {
        var body = JsonNode.Parse(fx.ResponseJson)!;
        body["revision"] = sent.Revision;
        var paragraphs = body["paragraphs"]!.AsArray();
        for (int i = 0; i < paragraphs.Count && i < sent.Paragraphs.Count; i++)
            paragraphs[i]!["id"] = sent.Paragraphs[i].Id;
        return body.ToJsonString();
    }
}
