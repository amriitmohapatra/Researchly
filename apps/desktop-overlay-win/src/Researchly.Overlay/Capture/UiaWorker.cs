using System;
using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using Interop.UIAutomationClient;

namespace Researchly.Overlay.Capture;

/// <summary>
/// One background thread in the multithreaded apartment that makes every UI
/// Automation call. UI Automation recommends keeping client calls off the UI
/// thread: a slow or hung host app then never freezes Researchly's windows.
/// </summary>
internal sealed class UiaWorker : IDisposable
{
    private readonly BlockingCollection<Action> _queue = new();
    private readonly Thread _thread;

    public UiaWorker()
    {
        _thread = new Thread(Loop) { IsBackground = true, Name = "Researchly UI Automation" };
        _thread.SetApartmentState(ApartmentState.MTA);
        _thread.Start();
    }

    public bool IsWorkerThread => Thread.CurrentThread == _thread;

    public void Post(Action action)
    {
        try { _queue.Add(action); }
        catch (InvalidOperationException) { /* shutting down */ }
    }

    public Task<T> Run<T>(Func<T> func)
    {
        var tcs = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
        Post(() =>
        {
            try { tcs.SetResult(func()); }
            catch (Exception e) { tcs.SetException(e); }
        });
        return tcs.Task;
    }

    private void Loop()
    {
        foreach (var action in _queue.GetConsumingEnumerable())
        {
            try { action(); }
            catch (COMException) { /* the element went away mid-call; the next event recovers */ }
            catch (Exception e)
            {
                // Never let one failed call end the worker (and with it, the app).
                // Only the type is reported: messages can quote input.
                System.Diagnostics.Debug.WriteLine("Researchly UI Automation worker: " + e.GetType().FullName);
            }
        }
    }

    public void Dispose()
    {
        _queue.CompleteAdding();
        _thread.Join(TimeSpan.FromSeconds(2));
    }
}

/// <summary>Receives focus changes from UI Automation (on its own threads) and hands them on.</summary>
[ComVisible(true)]
public sealed class FocusChangedHandler : IUIAutomationFocusChangedEventHandler
{
    private readonly Action<IUIAutomationElement> _onFocus;
    internal FocusChangedHandler(Action<IUIAutomationElement> onFocus) => _onFocus = onFocus;
    public void HandleFocusChangedEvent(IUIAutomationElement sender) => _onFocus(sender);
}

/// <summary>Receives automation events (text changed, selection changed) for the watched field.</summary>
[ComVisible(true)]
public sealed class AutomationEventHandler : IUIAutomationEventHandler
{
    private readonly Action<int> _onEvent;
    internal AutomationEventHandler(Action<int> onEvent) => _onEvent = onEvent;
    public void HandleAutomationEvent(IUIAutomationElement sender, int eventId) => _onEvent(eventId);
}

/// <summary>Receives property changes (the value) for the watched field.</summary>
[ComVisible(true)]
public sealed class PropertyChangedHandler : IUIAutomationPropertyChangedEventHandler
{
    private readonly Action<int> _onChange;
    internal PropertyChangedHandler(Action<int> onChange) => _onChange = onChange;
    public void HandlePropertyChangedEvent(IUIAutomationElement sender, int propertyId, object newValue) => _onChange(propertyId);
}
