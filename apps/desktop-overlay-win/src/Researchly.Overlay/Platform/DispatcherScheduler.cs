using System;
using System.Windows.Threading;
using Researchly.Overlay.Core.Timing;

namespace Researchly.Overlay.Platform;

/// <summary>Timers on the WPF dispatcher, so the core's callbacks run on the UI thread.</summary>
internal sealed class DispatcherScheduler : IScheduler
{
    private readonly Dispatcher _dispatcher;

    public DispatcherScheduler(Dispatcher dispatcher) => _dispatcher = dispatcher;

    public DateTimeOffset Now => DateTimeOffset.UtcNow;

    public IDisposable Schedule(TimeSpan delay, Action action)
    {
        var timer = new DispatcherTimer(DispatcherPriority.Normal, _dispatcher)
        {
            Interval = delay < TimeSpan.FromMilliseconds(1) ? TimeSpan.FromMilliseconds(1) : delay,
        };
        var handle = new Handle(timer);
        timer.Tick += (_, _) =>
        {
            timer.Stop();
            if (!handle.Cancelled) action();
        };
        timer.Start();
        return handle;
    }

    private sealed class Handle : IDisposable
    {
        private readonly DispatcherTimer _timer;
        public Handle(DispatcherTimer timer) => _timer = timer;
        public bool Cancelled { get; private set; }
        public void Dispose()
        {
            Cancelled = true;
            _timer.Stop();
        }
    }
}
