using System;
using System.Diagnostics;
using System.Threading;
using System.Windows;

namespace Researchly.Overlay;

/// <summary>
/// Researchly for Windows: underlines and cards over the text field you are
/// writing in. Lives in the notification area; has no main window.
/// </summary>
internal static class Program
{
    [STAThread]
    private static int Main()
    {
        using var single = new Mutex(initiallyOwned: true, @"Local\Researchly.Overlay", out bool first);
        if (!first) return 0; // already running: its icon is in the notification area

        System.Windows.Forms.Application.EnableVisualStyles();
        var app = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };

        // Keep running after an unexpected error in a handler. Only the error's
        // type is reported (to an attached debugger): messages can quote input.
        app.DispatcherUnhandledException += (_, e) =>
        {
            Debug.WriteLine("Researchly: unhandled " + e.Exception.GetType().FullName);
            e.Handled = true;
        };

        var controller = new OverlayController(app.Dispatcher);
        app.Startup += (_, _) => controller.Start();
        app.Exit += (_, _) => controller.Dispose();
        app.Run();
        return 0;
    }
}
