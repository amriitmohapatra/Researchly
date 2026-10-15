using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Timing;

namespace Researchly.Overlay.Core.Tests;

/// <summary>A fake clock: timers fire only when the test advances time.</summary>
public sealed class ManualScheduler : IScheduler
{
    private sealed class Entry : IDisposable
    {
        public DateTimeOffset Due;
        public Action Action = () => { };
        public bool Cancelled;
        public long Order;
        public void Dispose() => Cancelled = true;
    }

    private readonly List<Entry> _entries = new();
    private long _order;

    public ManualScheduler(DateTimeOffset? start = null) => Now = start ?? new DateTimeOffset(2026, 10, 15, 9, 0, 0, TimeSpan.Zero);

    public DateTimeOffset Now { get; private set; }

    public IDisposable Schedule(TimeSpan delay, Action action)
    {
        var e = new Entry { Due = Now + (delay < TimeSpan.Zero ? TimeSpan.Zero : delay), Action = action, Order = _order++ };
        _entries.Add(e);
        return e;
    }

    /// <summary>Pending (not cancelled) timers.</summary>
    public int Pending => _entries.Count(e => !e.Cancelled);

    /// <summary>The delay until the next pending timer, from now.</summary>
    public TimeSpan? NextDue
    {
        get
        {
            var next = _entries.Where(e => !e.Cancelled).OrderBy(e => e.Due).ThenBy(e => e.Order).FirstOrDefault();
            return next == null ? null : next.Due - Now;
        }
    }

    /// <summary>Moves time forward, firing due timers in order (including ones they schedule).</summary>
    public void Advance(TimeSpan by)
    {
        var target = Now + by;
        while (true)
        {
            var next = _entries.Where(e => !e.Cancelled && e.Due <= target).OrderBy(e => e.Due).ThenBy(e => e.Order).FirstOrDefault();
            if (next == null) break;
            _entries.Remove(next);
            Now = next.Due;
            next.Action();
        }
        Now = target;
        _entries.RemoveAll(e => e.Cancelled);
    }

    public void AdvanceSeconds(double seconds) => Advance(TimeSpan.FromSeconds(seconds));
}

/// <summary>
/// A fake engine. Each request waits until the test answers it, so tests can
/// interleave edits and replies; answers complete synchronously on the test thread.
/// </summary>
public sealed class FakeEngine : IEngineClient
{
    public sealed class Call
    {
        public required CheckParagraphsRequest Request { get; init; }
        public required TaskCompletionSource<CheckReply> Reply { get; init; }
        public CancellationToken Token { get; init; }
        public bool Answered => Reply.Task.IsCompleted;
    }

    public List<Call> Calls { get; } = new();

    public Call Last => Calls[^1];

    public Task<CheckReply> CheckAsync(CheckParagraphsRequest request, CancellationToken cancellationToken)
    {
        // Copy the request: the session must not rely on it after sending.
        var copy = new CheckParagraphsRequest
        {
            Revision = request.Revision,
            Options = request.Options,
            Paragraphs = request.Paragraphs.Select(p => new ParagraphPayload { Id = p.Id, Text = p.Text, Heading = p.Heading, Style = p.Style }).ToList(),
        };
        var tcs = new TaskCompletionSource<CheckReply>();
        cancellationToken.Register(() => tcs.TrySetCanceled(cancellationToken));
        Calls.Add(new Call { Request = copy, Reply = tcs, Token = cancellationToken });
        return tcs.Task;
    }

    /// <summary>Answers a call with a JSON body, decoded exactly as the HTTP client would.</summary>
    public void AnswerJson(Call call, string json) => call.Reply.SetResult(ReplyDecoder.Decode(json, call.Request));

    /// <summary>Answers with no suggestions for every paragraph, echoing the revision.</summary>
    public void AnswerClear(Call call, string? state = null)
    {
        var paragraphs = string.Join(",", call.Request.Paragraphs.Select(p => $"{{\"id\":\"{p.Id}\",\"suggestions\":[]}}"));
        AnswerJson(call, $"{{\"revision\":{call.Request.Revision},\"paragraphs\":[{paragraphs}]" + (state != null ? $",\"state\":\"{state}\"" : "") + "}");
    }

    /// <summary>Answers with one suggestion on the first occurrence of <paramref name="flagged"/> in each paragraph that contains it.</summary>
    public void AnswerFlagging(Call call, string flagged, string category = "correction", string? replacement = null)
    {
        var parts = new List<string>();
        foreach (var p in call.Request.Paragraphs)
        {
            int at = p.Text.IndexOf(flagged, StringComparison.Ordinal);
            string suggestions = at < 0 ? "" :
                $"{{\"id\":\"s-{p.Id}-{at}\",\"begin\":{at},\"end\":{at + flagged.Length},\"category\":\"{category}\",\"message\":\"Synthetic message.\",\"replacements\":[{(replacement == null ? "" : "\"" + replacement + "\"")}]}}";
            parts.Add($"{{\"id\":\"{p.Id}\",\"suggestions\":[{suggestions}]}}");
        }
        AnswerJson(call, $"{{\"revision\":{call.Request.Revision},\"paragraphs\":[{string.Join(",", parts)}]}}");
    }

    public void Fail(Call call, string code = "unreachable", TimeSpan? retryAfter = null) =>
        call.Reply.SetException(new EngineException(code, "synthetic failure", retryAfter: retryAfter));
}

public static class Fixtures
{
    public static string Read(string name) => File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Fixtures", name));

    public static string RulesDirectory => Path.Combine(AppContext.BaseDirectory, "rules");
}
