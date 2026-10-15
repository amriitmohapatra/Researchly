using System;
using System.Linq;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Session;
using Researchly.Overlay.Core.State;
using Researchly.Overlay.Core.Timing;
using Xunit;

namespace Researchly.Overlay.Core.Tests;

public class StateMachineTests
{
    [Fact]
    public void Follows_the_documented_transitions()
    {
        var m = new StateMachine();
        Assert.Equal(OverlayState.Hidden, m.State);
        m.Edited();                                   // not on a field: stays hidden
        Assert.Equal(OverlayState.Hidden, m.State);
        m.FieldEntered();
        Assert.Equal(OverlayState.Checking, m.State);
        m.ReplyReceived(3, partial: false);
        Assert.Equal(OverlayState.Issues, m.State);
        Assert.Equal(3, m.IssueCount);
        m.Edited();
        Assert.Equal(OverlayState.Checking, m.State);
        m.ReplyReceived(0, partial: false);
        Assert.Equal(OverlayState.Clear, m.State);
        m.ReplyReceived(1, partial: true, "Grammar is unavailable right now.");
        Assert.Equal(OverlayState.Partial, m.State);
        Assert.Equal("Grammar is unavailable right now.", m.Detail);
        m.RequestFailed("Can't check right now.");
        Assert.Equal(OverlayState.Offline, m.State);
        m.Edited();                                   // offline until a retry succeeds
        Assert.Equal(OverlayState.Offline, m.State);
        m.Hide();
        Assert.Equal(OverlayState.Hidden, m.State);
        m.RequestFailed("late failure");              // hidden ignores late news
        Assert.Equal(OverlayState.Hidden, m.State);
    }

    [Fact]
    public void Count_changes_move_between_issues_and_clear()
    {
        var m = new StateMachine();
        m.FieldEntered();
        m.ReplyReceived(1, false);
        m.CountChanged(0);
        Assert.Equal(OverlayState.Clear, m.State);
    }

    [Fact]
    public void Raises_changed_events()
    {
        var m = new StateMachine();
        int events = 0;
        m.Changed += (_, _) => events++;
        m.FieldEntered();
        m.FieldEntered();          // no change, no event
        m.ReplyReceived(0, false);
        Assert.Equal(2, events);
    }
}

public class RetryBackoffTests
{
    [Fact]
    public void Waits_2_4_8_16_30_then_every_30_seconds_and_resets()
    {
        var b = new RetryBackoff();
        var seconds = Enumerable.Range(0, 8).Select(_ => b.Next().TotalSeconds).ToArray();
        Assert.Equal(new double[] { 2, 4, 8, 16, 30, 30, 30, 30 }, seconds);
        b.Reset();
        Assert.Equal(2, b.Peek().TotalSeconds);
        Assert.Equal(2, b.Next().TotalSeconds);
    }
}

public class DebouncerTests
{
    [Fact]
    public void Fires_once_after_a_quiet_period_and_restarts_on_each_poke()
    {
        var clock = new ManualScheduler();
        int fired = 0;
        var d = new Debouncer(clock, TimeSpan.FromMilliseconds(1500), () => fired++);
        d.Poke();
        clock.Advance(TimeSpan.FromMilliseconds(1400));
        d.Poke();
        clock.Advance(TimeSpan.FromMilliseconds(1400));
        Assert.Equal(0, fired);
        clock.Advance(TimeSpan.FromMilliseconds(100));
        Assert.Equal(1, fired);
        clock.AdvanceSeconds(10);
        Assert.Equal(1, fired);
        Assert.False(d.IsPending);
    }

    [Fact]
    public void Flush_runs_now_and_cancel_drops_the_wait()
    {
        var clock = new ManualScheduler();
        int fired = 0;
        var d = new Debouncer(clock, Debouncer.DefaultDelay, () => fired++);
        d.Flush();                 // nothing pending: nothing runs
        Assert.Equal(0, fired);
        d.Poke();
        d.Flush();
        Assert.Equal(1, fired);
        d.Poke();
        d.Cancel();
        clock.AdvanceSeconds(5);
        Assert.Equal(1, fired);
        Assert.Equal(TimeSpan.FromMilliseconds(1500), Debouncer.DefaultDelay);
    }
}

public class LiveCheckSessionTests
{
    private readonly ManualScheduler _clock = new();
    private readonly FakeEngine _engine = new();
    private readonly LiveCheckSession _session;

    public LiveCheckSessionTests()
    {
        _session = new LiveCheckSession(_engine, _clock, () => new CheckOptionsPayload());
    }

    private const string Doc = "Introduction\nWe measured teh rate.\nMethods\nSamples were taken weekly.";

    [Fact]
    public void Start_checks_straight_away_without_headings_or_blank_paragraphs()
    {
        _session.Start("Introduction\n\nWe measured teh rate.\nMethods\nSamples were taken weekly.");
        Assert.Single(_engine.Calls);
        var sent = _engine.Last.Request.Paragraphs;
        Assert.Equal(new[] { "We measured teh rate.", "Samples were taken weekly." }, sent.Select(p => p.Text));
        Assert.Equal(new[] { "Introduction", "Methods" }, sent.Select(p => p.Heading));
        Assert.Equal(OverlayState.Checking, _session.State.State);
        Assert.Equal(1, _engine.Last.Request.Revision);
    }

    [Fact]
    public void A_reply_places_suggestions_on_the_field_text()
    {
        _session.Start(Doc);
        _engine.AnswerFlagging(_engine.Last, "teh", replacement: "the");
        Assert.Equal(OverlayState.Issues, _session.State.State);
        var s = Assert.Single(_session.Visible);
        Assert.Equal("teh", s.FlaggedText);
        Assert.Equal("teh", Doc.Substring(s.Range.Start, s.Range.Length));
        Assert.Equal(new[] { "the" }, s.Suggestion.Replacements);
        Assert.Equal(1, _session.State.IssueCount);
    }

    [Fact]
    public void Waits_for_the_typing_pause_and_sends_only_changed_paragraphs()
    {
        _session.Start(Doc);
        _engine.AnswerClear(_engine.Last);
        Assert.Equal(OverlayState.Clear, _session.State.State);

        _session.UpdateText(Doc.Replace("weekly", "weekly and"));
        Assert.Equal(OverlayState.Checking, _session.State.State);
        _clock.Advance(TimeSpan.FromMilliseconds(1000));
        _session.UpdateText(Doc.Replace("weekly", "weekly and monthly"));
        _clock.Advance(TimeSpan.FromMilliseconds(1499));
        Assert.Single(_engine.Calls);                      // still typing
        _clock.Advance(TimeSpan.FromMilliseconds(1));
        Assert.Equal(2, _engine.Calls.Count);
        var p = Assert.Single(_engine.Last.Request.Paragraphs);
        Assert.Equal("Samples were taken weekly and monthly.", p.Text);
        Assert.Equal("Methods", p.Heading);
        Assert.Equal(2, _engine.Last.Request.Revision);
    }

    [Fact]
    public void Paragraph_ids_are_stable_across_edits()
    {
        _session.Start(Doc);
        string id = _engine.Last.Request.Paragraphs[1].Id;
        _engine.AnswerClear(_engine.Last);
        _session.UpdateText(Doc.Replace("weekly", "daily"));
        _clock.AdvanceSeconds(1.5);
        Assert.Equal(id, Assert.Single(_engine.Last.Request.Paragraphs).Id);
    }

    [Fact]
    public void A_reply_that_arrives_after_an_edit_is_dropped()
    {
        _session.Start(Doc);
        var first = _engine.Last;
        _session.UpdateText(Doc.Replace("rate", "rates"));        // edit while the check is in flight
        _engine.AnswerFlagging(first, "teh");
        Assert.Equal(1, _session.StaleRepliesDropped);
        Assert.Empty(_session.Visible);                            // stale findings never shown
        Assert.Equal(OverlayState.Checking, _session.State.State);

        _clock.AdvanceSeconds(1.5);
        var second = _engine.Last;
        Assert.NotSame(first, second);
        Assert.Contains(second.Request.Paragraphs, p => p.Text == "We measured teh rates.");
        _engine.AnswerFlagging(second, "teh");
        Assert.Single(_session.Visible);
        Assert.Equal(OverlayState.Issues, _session.State.State);
    }

    [Fact]
    public void An_older_request_is_cancelled_when_a_newer_one_goes_out()
    {
        _session.Start(Doc);
        var first = _engine.Last;
        _session.UpdateText(Doc + " More.");
        _clock.AdvanceSeconds(1.5);
        Assert.True(first.Token.IsCancellationRequested);
        Assert.Equal(2, _engine.Calls.Count);
    }

    [Fact]
    public void A_reply_echoing_another_revision_is_dropped()
    {
        _session.Start(Doc);
        var call = _engine.Last;
        _engine.AnswerJson(call, """{"revision": 99, "paragraphs": []}""");
        Assert.Equal(1, _session.StaleRepliesDropped);
        Assert.Equal(OverlayState.Checking, _session.State.State);
    }

    [Fact]
    public void Offline_retries_at_2_4_8_16_30_then_30_seconds_and_recovers()
    {
        _session.Start(Doc);
        var delays = new System.Collections.Generic.List<double>();
        for (int i = 0; i < 6; i++)
        {
            _engine.Fail(_engine.Last);
            Assert.Equal(OverlayState.Offline, _session.State.State);
            Assert.StartsWith("Can", _session.State.Detail);
            var due = _session.NextRetryAt!.Value - _clock.Now;
            delays.Add(due.TotalSeconds);
            int before = _engine.Calls.Count;
            _clock.Advance(due - TimeSpan.FromMilliseconds(1));
            Assert.Equal(before, _engine.Calls.Count);      // not yet
            _clock.Advance(TimeSpan.FromMilliseconds(1));
            Assert.Equal(before + 1, _engine.Calls.Count);  // retried
        }
        Assert.Equal(new double[] { 2, 4, 8, 16, 30, 30 }, delays);

        _engine.AnswerFlagging(_engine.Last, "teh");
        Assert.Equal(OverlayState.Issues, _session.State.State);
        Assert.Null(_session.NextRetryAt);

        // The backoff starts again from 2 s after a success.
        _session.UpdateText(Doc.Replace("weekly", "daily"));
        _clock.AdvanceSeconds(1.5);
        _engine.Fail(_engine.Last);
        Assert.Equal(2, (_session.NextRetryAt!.Value - _clock.Now).TotalSeconds);
    }

    [Fact]
    public void Edits_while_offline_wait_for_the_scheduled_retry()
    {
        _session.Start(Doc);
        _engine.Fail(_engine.Last);
        _session.UpdateText(Doc.Replace("weekly", "daily"));
        _clock.AdvanceSeconds(1.5);                     // the debounce fires, but a retry is scheduled
        Assert.Single(_engine.Calls);
        Assert.Equal(OverlayState.Offline, _session.State.State);
        _clock.AdvanceSeconds(0.5);                     // 2 s after the failure
        Assert.Equal(2, _engine.Calls.Count);
        Assert.Contains(_engine.Last.Request.Paragraphs, p => p.Text.Contains("daily", StringComparison.Ordinal));
    }

    [Fact]
    public void Changing_the_engine_while_offline_checks_at_once()
    {
        _session.Start(Doc);
        _engine.Fail(_engine.Last);
        Assert.NotNull(_session.NextRetryAt);
        _session.RecheckAll();                          // the writer chose another engine
        Assert.Equal(2, _engine.Calls.Count);
        Assert.Null(_session.NextRetryAt);
        _engine.AnswerClear(_engine.Last);
        Assert.Equal(OverlayState.Clear, _session.State.State);
    }

    [Fact]
    public void Retry_after_from_a_busy_engine_is_honoured()
    {
        _session.Start(Doc);
        _engine.Fail(_engine.Last, "rate_limited", TimeSpan.FromSeconds(20));
        Assert.Equal(20, (_session.NextRetryAt!.Value - _clock.Now).TotalSeconds);
        Assert.Contains("busy", _session.State.Detail);
    }

    [Fact]
    public void A_degraded_engine_gives_the_partial_state()
    {
        _session.Start(Doc);
        var call = _engine.Last;
        _engine.AnswerJson(call, $$$"""
            {"revision": {{{call.Request.Revision}}}, "paragraphs": [],
             "health": {"status": "degraded", "tiers": [{"tier": "grammar", "label": "Grammar", "ok": false, "state": "error"}]}}
            """);
        Assert.Equal(OverlayState.Partial, _session.State.State);
        Assert.Equal("Grammar is unavailable right now.", _session.State.Detail);
    }

    [Fact]
    public void Editing_an_earlier_paragraph_keeps_later_underlines_aligned()
    {
        _session.Start(Doc);
        _engine.AnswerFlagging(_engine.Last, "weekly", "improvement");
        var before = Assert.Single(_session.Visible);

        string edited = Doc.Replace("We measured", "We carefully measured");
        _session.UpdateText(edited);
        var after = Assert.Single(_session.Visible);           // shown while the edited paragraph is re-checked
        Assert.Equal(before.Range.Start + "carefully ".Length, after.Range.Start);
        Assert.Equal("weekly", edited.Substring(after.Range.Start, after.Range.Length));
    }

    [Fact]
    public void Typing_inside_a_flagged_word_removes_its_underline_at_once()
    {
        _session.Start(Doc);
        _engine.AnswerFlagging(_engine.Last, "teh");
        Assert.Single(_session.Visible);
        _session.UpdateText(Doc.Replace("teh", "tehx"));
        Assert.Empty(_session.Visible);
        Assert.Equal(OverlayState.Checking, _session.State.State);
    }

    [Fact]
    public void Editing_elsewhere_in_the_paragraph_moves_the_underline()
    {
        _session.Start(Doc);
        _engine.AnswerFlagging(_engine.Last, "teh");
        string edited = Doc.Replace("We measured", "We then measured");
        _session.UpdateText(edited);
        var s = Assert.Single(_session.Visible);
        Assert.Equal("teh", edited.Substring(s.Range.Start, s.Range.Length));
    }

    [Fact]
    public void Preferences_are_hidden_until_switched_on()
    {
        _session.Start(Doc);
        _engine.AnswerFlagging(_engine.Last, "weekly", "preference");
        Assert.Empty(_session.Visible);
        Assert.Equal(OverlayState.Clear, _session.State.State);

        _session.SetShowPreferences(true);
        Assert.Single(_session.Visible);
        Assert.Equal(2, _engine.Calls.Count);                  // asked again with the new option
    }

    [Fact]
    public void Not_an_issue_hides_the_suggestion_and_updates_the_count()
    {
        _session.Start(Doc);
        _engine.AnswerFlagging(_engine.Last, "teh");
        var s = Assert.Single(_session.Visible);
        _session.Dismiss(s.Id);
        Assert.Empty(_session.Visible);
        Assert.Equal(OverlayState.Clear, _session.State.State);
    }

    [Fact]
    public void Stop_hides_forgets_the_text_and_ignores_late_replies()
    {
        _session.Start(Doc);
        var call = _engine.Last;
        _session.Stop();
        Assert.Equal(OverlayState.Hidden, _session.State.State);
        Assert.Equal("", _session.Snapshot.Text);
        Assert.True(call.Token.IsCancellationRequested);
        _session.UpdateText("ignored");
        Assert.Single(_engine.Calls);
    }

    [Fact]
    public void Long_fields_go_in_batches_and_the_state_settles_after_the_last()
    {
        string text = string.Join("\n", Enumerable.Range(1, 95).Select(i => $"Sentence number {i} is here."));
        _session.Start(text);
        Assert.Equal(LiveCheckSession.MaxParagraphsPerRequest, _engine.Last.Request.Paragraphs.Count);
        _engine.AnswerClear(_engine.Last);
        Assert.Equal(OverlayState.Checking, _session.State.State);
        _clock.Advance(TimeSpan.Zero);
        Assert.Equal(2, _engine.Calls.Count);
        _engine.AnswerClear(_engine.Last);
        _clock.Advance(TimeSpan.Zero);
        Assert.Equal(3, _engine.Calls.Count);
        Assert.Equal(15, _engine.Last.Request.Paragraphs.Count);
        _engine.AnswerClear(_engine.Last);
        Assert.Equal(OverlayState.Clear, _session.State.State);
        Assert.Equal(new long[] { 1, 2, 3 }, _engine.Calls.Select(c => c.Request.Revision));
    }

    [Fact]
    public void Paragraphs_near_the_caret_are_checked_first()
    {
        string text = string.Join("\n", Enumerable.Range(1, 60).Select(i => $"Line {i}."));
        _session.CaretOffset = text.Length;                  // at the end
        _session.Start(text);
        Assert.Contains(_engine.Last.Request.Paragraphs, p => p.Text == "Line 60.");
        Assert.DoesNotContain(_engine.Last.Request.Paragraphs, p => p.Text == "Line 1.");
    }

    [Fact]
    public void A_new_heading_sends_the_paragraphs_below_it_again()
    {
        string text = "We sampled weekly.\nWe fitted a model.";
        _session.Start(text);
        _engine.AnswerClear(_engine.Last);
        _session.UpdateText("Methods\n" + text);
        _clock.AdvanceSeconds(1.5);
        var sent = _engine.Last.Request.Paragraphs;
        Assert.Equal(2, sent.Count);
        Assert.All(sent, p => Assert.Equal("Methods", p.Heading));
    }

    [Fact]
    public void Deleting_a_paragraph_settles_without_a_request()
    {
        _session.Start(Doc);
        _engine.AnswerFlagging(_engine.Last, "teh");
        _session.UpdateText("Introduction\nMethods\nSamples were taken weekly.");
        Assert.Single(_engine.Calls);
        Assert.Empty(_session.Visible);
        Assert.Equal(OverlayState.Clear, _session.State.State);
    }

    [Fact]
    public void Unchanged_text_does_nothing()
    {
        _session.Start(Doc);
        _engine.AnswerClear(_engine.Last);
        _session.UpdateText(Doc);
        _clock.AdvanceSeconds(5);
        Assert.Single(_engine.Calls);
        Assert.Equal(OverlayState.Clear, _session.State.State);
    }
}
