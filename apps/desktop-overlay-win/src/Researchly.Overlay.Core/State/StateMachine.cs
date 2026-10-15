using System;

namespace Researchly.Overlay.Core.State;

/// <summary>
/// The six states every Researchly surface shares (docs/inline-review-design.md section 3).
/// </summary>
public enum OverlayState
{
    /// <summary>Not eligible here, or paused by the writer. Nothing is shown.</summary>
    Hidden,
    /// <summary>A check is in flight (or waiting for the typing pause) for the current text.</summary>
    Checking,
    /// <summary>Visible suggestions exist.</summary>
    Issues,
    /// <summary>Checked; nothing to show.</summary>
    Clear,
    /// <summary>Checked, but a tier was down (for example grammar).</summary>
    Partial,
    /// <summary>The engine cannot be reached or refused the request.</summary>
    Offline,
}

/// <summary>
/// Retry timing while offline: 2, 4, 8, 16 and 30 seconds, then every 30 seconds
/// (the generated tokens' RetrySeconds, shared by every surface). Any success resets it.
/// </summary>
public sealed class RetryBackoff
{
    private static readonly TimeSpan[] Steps =
        System.Linq.Enumerable.ToArray(System.Linq.Enumerable.Select(
            Researchly.Design.ResearchlyTokens.RetrySeconds, TimeSpan.FromSeconds));

    public int Attempt { get; private set; }

    /// <summary>The wait before the next retry; advances the attempt count.</summary>
    public TimeSpan Next()
    {
        var delay = Steps[Math.Min(Attempt, Steps.Length - 1)];
        Attempt++;
        return delay;
    }

    /// <summary>The wait <see cref="Next"/> would return, without advancing.</summary>
    public TimeSpan Peek() => Steps[Math.Min(Attempt, Steps.Length - 1)];

    public void Reset() => Attempt = 0;
}

/// <summary>
/// The state machine. Transitions (section 3): an edit goes to checking; a
/// reply goes to issues, clear or partial; a failure goes to offline; any
/// success leaves offline; leaving the field or pausing goes to hidden.
/// </summary>
public sealed class StateMachine
{
    public OverlayState State { get; private set; } = OverlayState.Hidden;

    /// <summary>Visible suggestion count after the last reply.</summary>
    public int IssueCount { get; private set; }

    /// <summary>Short, text-free reason for Partial or Offline (shown on hover); null otherwise.</summary>
    public string? Detail { get; private set; }

    public event Action<OverlayState, OverlayState>? Changed;

    /// <summary>The field gained focus and passed the gate, or the writer resumed.</summary>
    public void FieldEntered() => Set(OverlayState.Checking, null);

    /// <summary>The text changed: a check will follow after the pause.</summary>
    public void Edited()
    {
        if (State == OverlayState.Hidden) return; // not on an eligible field
        // Offline stays offline until a retry succeeds; the edit is checked then.
        if (State == OverlayState.Offline) return;
        Set(OverlayState.Checking, null);
    }

    /// <summary>A request went out.</summary>
    public void RequestSent()
    {
        if (State == OverlayState.Hidden) return;
        if (State == OverlayState.Offline) return; // a retry: keep saying offline until it succeeds
        Set(OverlayState.Checking, null);
    }

    /// <summary>A current (not stale) reply arrived.</summary>
    public void ReplyReceived(int visibleIssues, bool partial, string? partialDetail = null)
    {
        if (State == OverlayState.Hidden) return;
        IssueCount = Math.Max(0, visibleIssues);
        if (partial) Set(OverlayState.Partial, partialDetail ?? "Some checks are unavailable right now.");
        else Set(IssueCount > 0 ? OverlayState.Issues : OverlayState.Clear, null);
    }

    /// <summary>The visible count changed without a new reply (an accept or a dismissal).</summary>
    public void CountChanged(int visibleIssues)
    {
        IssueCount = Math.Max(0, visibleIssues);
        if (State is OverlayState.Issues or OverlayState.Clear)
            Set(IssueCount > 0 ? OverlayState.Issues : OverlayState.Clear, null);
        else
            Changed?.Invoke(State, State);
    }

    /// <summary>The engine could not be reached, or refused.</summary>
    public void RequestFailed(string detail)
    {
        if (State == OverlayState.Hidden) return;
        Set(OverlayState.Offline, detail);
    }

    /// <summary>Focus left the field, the field became ineligible, or the writer paused.</summary>
    public void Hide()
    {
        IssueCount = 0;
        Set(OverlayState.Hidden, null);
    }

    private void Set(OverlayState next, string? detail)
    {
        var previous = State;
        State = next;
        Detail = detail;
        if (previous != next || next is OverlayState.Partial or OverlayState.Offline)
            Changed?.Invoke(previous, next);
    }
}
