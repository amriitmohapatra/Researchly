using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows;
using Researchly.Overlay.Native;

namespace Researchly.Overlay.Capture;

/// <summary>
/// Synthesised keyboard input for write-back. Text is sent as Unicode
/// characters (KEYEVENTF_UNICODE), so the keyboard layout does not matter and
/// the host records an ordinary edit it can undo.
/// </summary>
internal static class Input
{
    private const int Chunk = 32;
    private const ushort VK_DELETE = 0x2E;

    public static bool TypeText(string text)
    {
        if (text.Length == 0) return PressDelete();
        var inputs = new List<NativeMethods.INPUT>(Chunk * 2);
        for (int i = 0; i < text.Length; i++)
        {
            ushort unit = text[i];
            inputs.Add(Key(0, unit, NativeMethods.KEYEVENTF_UNICODE));
            inputs.Add(Key(0, unit, NativeMethods.KEYEVENTF_UNICODE | NativeMethods.KEYEVENTF_KEYUP));
            if (inputs.Count >= Chunk * 2)
            {
                if (!Send(inputs)) return false;
                inputs.Clear();
                Thread.Sleep(5);
            }
        }
        return inputs.Count == 0 || Send(inputs);
    }

    public static bool PressDelete() => Send(new List<NativeMethods.INPUT>
    {
        Key(VK_DELETE, 0, 0),
        Key(VK_DELETE, 0, NativeMethods.KEYEVENTF_KEYUP),
    });

    public static bool PressCtrlV() => Send(new List<NativeMethods.INPUT>
    {
        Key(NativeMethods.VK_CONTROL, 0, 0),
        Key(NativeMethods.VK_V, 0, 0),
        Key(NativeMethods.VK_V, 0, NativeMethods.KEYEVENTF_KEYUP),
        Key(NativeMethods.VK_CONTROL, 0, NativeMethods.KEYEVENTF_KEYUP),
    });

    private static NativeMethods.INPUT Key(ushort vk, ushort scan, uint flags) => new()
    {
        type = NativeMethods.INPUT_KEYBOARD,
        U = new NativeMethods.InputUnion
        {
            ki = new NativeMethods.KEYBDINPUT { wVk = vk, wScan = scan, dwFlags = flags, time = 0, dwExtraInfo = IntPtr.Zero },
        },
    };

    private static bool Send(List<NativeMethods.INPUT> inputs)
    {
        var array = inputs.ToArray();
        uint sent = NativeMethods.SendInput((uint)array.Length, array, Marshal.SizeOf<NativeMethods.INPUT>());
        return sent == array.Length;
    }
}

/// <summary>
/// Saves the clipboard, puts a revision on it for one paste, and puts the
/// writer's clipboard back. The revision is marked so Windows keeps it out of
/// clipboard history and cloud clipboard sync. Runs on the UI (STA) thread.
/// </summary>
internal sealed class ClipboardGuard
{
    // Registered clipboard formats documented by Microsoft for clipboard history and cloud sync.
    private const string ExcludeFromMonitoring = "ExcludeClipboardContentFromMonitorProcessing";
    private const string CanIncludeInHistory = "CanIncludeInClipboardHistory";
    private const string CanUploadToCloud = "CanUploadToCloudClipboard";

    private readonly List<(string Format, object Data)> _saved = new();
    private bool _wasEmpty;

    private ClipboardGuard() { }

    public static ClipboardGuard Take()
    {
        var g = new ClipboardGuard();
        Retry(() =>
        {
            var data = Clipboard.GetDataObject();
            if (data == null) { g._wasEmpty = true; return; }
            foreach (var format in data.GetFormats(false))
            {
                try
                {
                    var value = data.GetData(format, false);
                    if (value != null) g._saved.Add((format, value));
                }
                catch (COMException) { }
                catch (OutOfMemoryException) { }
                catch (ExternalException) { }
            }
            g._wasEmpty = g._saved.Count == 0;
        });
        return g;
    }

    public bool SetPrivateText(string text)
    {
        var obj = new DataObject();
        obj.SetData(DataFormats.UnicodeText, text);
        obj.SetData(ExcludeFromMonitoring, Zero());
        obj.SetData(CanIncludeInHistory, Zero());
        obj.SetData(CanUploadToCloud, Zero());
        return Retry(() => Clipboard.SetDataObject(obj, copy: false));
    }

    public void Restore()
    {
        Retry(() =>
        {
            if (_wasEmpty)
            {
                Clipboard.Clear();
                return;
            }
            var obj = new DataObject();
            foreach (var (format, data) in _saved)
            {
                try { obj.SetData(format, data); }
                catch (COMException) { }
                catch (ArgumentException) { }
            }
            Clipboard.SetDataObject(obj, copy: true);
        });
    }

    private static MemoryStream Zero() => new(new byte[] { 0, 0, 0, 0 });

    private static bool Retry(Action action)
    {
        for (int i = 0; i < 5; i++)
        {
            try
            {
                action();
                return true;
            }
            catch (COMException)
            {
                Thread.Sleep(30); // another app has the clipboard open
            }
            catch (ExternalException)
            {
                Thread.Sleep(30);
            }
        }
        return false;
    }
}
