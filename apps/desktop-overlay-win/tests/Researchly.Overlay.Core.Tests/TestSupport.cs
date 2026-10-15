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

    public void Fail(Call call, string code = "unreachable", TimeSpan? retryAfter = null, int? status = null) =>
        call.Reply.SetException(new EngineException(code, "synthetic failure", status, retryAfter));

    /// <summary>Completes a call with what the HTTP client produced for a recorded exchange.</summary>
    public void Complete(Call call, Task<CheckReply> outcome)
    {
        if (outcome.IsFaulted) call.Reply.SetException(outcome.Exception!.InnerException!);
        else call.Reply.SetResult(outcome.Result);
    }
}

public static class Fixtures
{
    public static string Read(string name) => File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Fixtures", name));

    /// <summary>
    /// One exchange of packages/contract/fixtures/check-paragraphs (made by the engine service,
    /// shared with the macOS client): the request a client sent, the status, the headers it acts
    /// on and the body the engine answered.
    /// </summary>
    public static SharedExchange Shared(string name) =>
        new(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Shared", name + ".json")));

    public static string RulesDirectory => Path.Combine(AppContext.BaseDirectory, "rules");
}

public sealed class SharedExchange
{
    public SharedExchange(string json)
    {
        using var doc = System.Text.Json.JsonDocument.Parse(json);
        var root = doc.RootElement;
        RequestJson = root.GetProperty("request").GetRawText();
        Request = System.Text.Json.JsonSerializer.Deserialize<CheckParagraphsRequest>(RequestJson)!;
        Status = root.GetProperty("status").GetInt32();
        foreach (var h in root.GetProperty("headers").EnumerateObject()) Headers[h.Name] = h.Value.GetString() ?? "";
        ResponseJson = root.GetProperty("response").GetRawText();
    }

    public string RequestJson { get; }
    public CheckParagraphsRequest Request { get; }
    public int Status { get; }
    public Dictionary<string, string> Headers { get; } = new(StringComparer.OrdinalIgnoreCase);
    public string ResponseJson { get; }

    public string Text(string id) => Request.Paragraphs.Single(p => p.Id == id).Text;

    /// <summary>What the real HTTP client makes of the recorded answer to this request (or to another one).</summary>
    public async Task<CheckReply> ThroughClientAsync(CheckParagraphsRequest? request = null)
    {
        using var client = new HttpEngineClient("http://127.0.0.1:3517", new ReplayHandler(this));
        return await client.CheckAsync(request ?? Request, CancellationToken.None);
    }

    private sealed class ReplayHandler : System.Net.Http.HttpMessageHandler
    {
        private readonly SharedExchange _x;
        public ReplayHandler(SharedExchange x) => _x = x;

        protected override Task<System.Net.Http.HttpResponseMessage> SendAsync(System.Net.Http.HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var r = new System.Net.Http.HttpResponseMessage((System.Net.HttpStatusCode)_x.Status)
            {
                Content = new System.Net.Http.StringContent(_x.ResponseJson, System.Text.Encoding.UTF8, "application/json"),
            };
            foreach (var (k, v) in _x.Headers) r.Headers.TryAddWithoutValidation(k, v);
            return Task.FromResult(r);
        }
    }
}
