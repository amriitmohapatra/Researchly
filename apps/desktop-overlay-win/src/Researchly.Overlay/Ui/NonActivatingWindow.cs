using System;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using Researchly.Overlay.Native;

namespace Researchly.Overlay.Ui;

/// <summary>
/// The base of every Researchly window that sits over another app: borderless,
/// transparent, topmost, out of the taskbar and Alt-Tab, and never activated,
/// so the caret, undo history and shortcuts stay with the host
/// (docs/inline-review-design.md section 1, item 4). Positions are set in
/// physical pixels, which is what UI Automation reports.
/// </summary>
internal class NonActivatingWindow : Window
{
    private readonly bool _clickThrough;

    protected NonActivatingWindow(bool clickThrough)
    {
        _clickThrough = clickThrough;
        WindowStyle = WindowStyle.None;
        AllowsTransparency = true;
        Background = Brushes.Transparent;
        ShowInTaskbar = false;
        ShowActivated = false;
        Topmost = true;
        ResizeMode = ResizeMode.NoResize;
        Focusable = false;
        SnapsToDevicePixels = true;
        UseLayoutRounding = true;
        // Created off screen; every show is followed by an explicit placement.
        WindowStartupLocation = WindowStartupLocation.Manual;
        Left = -32000;
        Top = -32000;
        SourceInitialized += OnSourceInitialized;
    }

    public IntPtr Handle { get; private set; }

    /// <summary>Device pixels per DIP for the monitor the window is on.</summary>
    public double DeviceScale => VisualTreeHelper.GetDpi(this).DpiScaleX;

    /// <summary>Raised after the window moved to a monitor with another DPI.</summary>
    public event Action? DpiMoved;

    protected override void OnDpiChanged(DpiScale oldDpi, DpiScale newDpi)
    {
        base.OnDpiChanged(oldDpi, newDpi);
        DpiMoved?.Invoke();
    }

    private void OnSourceInitialized(object? sender, EventArgs e)
    {
        Handle = new WindowInteropHelper(this).Handle;
        long ex = NativeMethods.GetWindowLong(Handle, NativeMethods.GWL_EXSTYLE);
        ex |= NativeMethods.WS_EX_NOACTIVATE | NativeMethods.WS_EX_TOOLWINDOW | NativeMethods.WS_EX_TOPMOST;
        if (_clickThrough) ex |= NativeMethods.WS_EX_TRANSPARENT | NativeMethods.WS_EX_LAYERED;
        NativeMethods.SetWindowLong(Handle, NativeMethods.GWL_EXSTYLE, ex);
        HwndSource.FromHwnd(Handle)?.AddHook(WndProc);
    }

    private static IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg == NativeMethods.WM_MOUSEACTIVATE)
        {
            handled = true;
            return new IntPtr(NativeMethods.MA_NOACTIVATE);
        }
        return IntPtr.Zero;
    }

    /// <summary>Creates the window handle (and applies the styles) without showing it.</summary>
    public void EnsureHandle()
    {
        if (Handle == IntPtr.Zero) new WindowInteropHelper(this).EnsureHandle();
    }

    /// <summary>Shows the window without activating it.</summary>
    public void ShowQuietly()
    {
        EnsureHandle();
        if (!IsVisible) Show();
    }

    /// <summary>
    /// Moves (and optionally sizes) the window in physical screen pixels, inactive.
    /// It is raised to the top of the topmost band unless <paramref name="keepZOrder"/>
    /// is set (used for frequent re-placements, so the card stays above the underlines).
    /// </summary>
    public void PlacePhysical(double x, double y, double width = 0, double height = 0, bool keepZOrder = false)
    {
        EnsureHandle();
        uint flags = NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_NOOWNERZORDER;
        if (width <= 0 || height <= 0) flags |= NativeMethods.SWP_NOSIZE;
        if (keepZOrder) flags |= NativeMethods.SWP_NOZORDER;
        NativeMethods.SetWindowPos(Handle, NativeMethods.HWND_TOPMOST,
            (int)Math.Round(x), (int)Math.Round(y), (int)Math.Round(width), (int)Math.Round(height), flags);
    }

    /// <summary>True when the point (physical pixels) is over this visible window.</summary>
    public bool ContainsPhysical(int x, int y)
    {
        if (!IsVisible || Handle == IntPtr.Zero) return false;
        if (!NativeMethods.GetWindowRect(Handle, out var r)) return false;
        return x >= r.Left && x < r.Right && y >= r.Top && y < r.Bottom;
    }

    /// <summary>The window's size in physical pixels.</summary>
    public (int Width, int Height) PhysicalSize()
    {
        if (Handle == IntPtr.Zero || !NativeMethods.GetWindowRect(Handle, out var r))
            return ((int)Math.Round(ActualWidth * DeviceScale), (int)Math.Round(ActualHeight * DeviceScale));
        return (r.Right - r.Left, r.Bottom - r.Top);
    }
}
