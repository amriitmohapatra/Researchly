using System;
using System.Threading;

namespace Researchly.Overlay.Core.Timing;

/// <summary>
/// Time and timers, behind an interface so tests drive them with a fake clock.
/// Callbacks run on the scheduler's own context: the shell's implementation
/// runs them on the UI thread, which is the only thread the session touches.
/// </summary>
public interface IScheduler
{
    DateTimeOffset Now { get; }

    /// <summary>Runs <paramref name="action"/> once after <paramref name="delay"/>; dispose the result to cancel.</summary>
    IDisposable Schedule(TimeSpan delay, Action action);
}

/// <summary>
/// Runs an action once input has been quiet for <see cref="Delay"/>: each
/// <see cref="Poke"/> restarts the wait (docs/inline-review-design.md
/// section 1, item 8: wait for the pause).
/// </summary>
public sealed class Debouncer : IDisposable
{
    public static readonly TimeSpan DefaultDelay = TimeSpan.FromMilliseconds(1500);

    private readonly IScheduler _scheduler;
    private readonly Action _action;
    private IDisposable? _pending;

    public Debouncer(IScheduler scheduler, TimeSpan delay, Action action)
    {
        _scheduler = scheduler;
        Delay = delay;
        _action = action;
    }

    public TimeSpan Delay { get; }
    public bool IsPending => _pending != null;

    /// <summary>Starts or restarts the quiet-period wait.</summary>
    public void Poke()
    {
        _pending?.Dispose();
        IDisposable? me = null;
        me = _scheduler.Schedule(Delay, () =>
        {
            if (!ReferenceEquals(_pending, me)) return; // superseded
            _pending = null;
            _action();
        });
        _pending = me;
    }

    /// <summary>Runs the action now if a wait is pending.</summary>
    public void Flush()
    {
        if (_pending == null) return;
        Cancel();
        _action();
    }

    public void Cancel()
    {
        _pending?.Dispose();
        _pending = null;
    }

    public void Dispose() => Cancel();
}

/// <summary>A thread-pool scheduler on the system clock (callbacks run on pool threads).</summary>
public sealed class SystemScheduler : IScheduler
{
    public DateTimeOffset Now => DateTimeOffset.UtcNow;

    public IDisposable Schedule(TimeSpan delay, Action action)
    {
        var timer = new Timer(_ => action(), null, Timeout.Infinite, Timeout.Infinite);
        timer.Change(delay < TimeSpan.Zero ? TimeSpan.Zero : delay, Timeout.InfiniteTimeSpan);
        return timer;
    }
}
