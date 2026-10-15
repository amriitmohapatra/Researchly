using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace Researchly.Overlay.Core.Eligibility;

/// <summary>A corner of a field, where the field widget is pinned.</summary>
public enum Corner { TopLeft, TopRight, BottomLeft, BottomRight }

/// <summary>How an accepted revision is written back into the host.</summary>
public enum WriteBackMethod
{
    /// <summary>Select the range through UI Automation, then type the revision as Unicode key events. Keeps the host's undo.</summary>
    SelectAndType,
    /// <summary>Select the range through UI Automation, paste the revision, restore the clipboard. Keeps the host's undo.</summary>
    SelectAndPaste,
    /// <summary>Replace the whole value through the UI Automation value pattern. Hosts may lose undo; only for apps that list it.</summary>
    ValueSet,
}

/// <summary>Where the field text is read from.</summary>
public enum TextSource
{
    /// <summary>The whole field (most text boxes).</summary>
    Document,
    /// <summary>Only the paragraphs on screen (long documents in a word processor or mail editor).</summary>
    Visible,
}

/// <summary>The settled rule for one app: per-app values over the defaults.</summary>
public sealed record AppRule
{
    public string Label { get; init; } = "";
    public IReadOnlyList<string> Processes { get; init; } = Array.Empty<string>();
    public bool Enabled { get; init; } = true;
    public string? Reason { get; init; }
    public Corner WidgetCorner { get; init; } = Corner.BottomRight;
    /// <summary>Inward offset from the corner, in device-independent pixels (1/96 inch).</summary>
    public double WidgetOffsetX { get; init; } = 8;
    public double WidgetOffsetY { get; init; } = 8;
    public IReadOnlyList<Corner> ForbiddenCorners { get; init; } = Array.Empty<Corner>();
    public IReadOnlyList<WriteBackMethod> WriteBack { get; init; } = new[] { WriteBackMethod.SelectAndType, WriteBackMethod.SelectAndPaste };
    /// <summary>True when the app does not raise reliable text-changed events, so the client polls.</summary>
    public bool PollingNeeded { get; init; }
    public int PollIntervalMs { get; init; } = 1000;
    public TextSource TextSource { get; init; } = TextSource.Document;
    /// <summary>Above this many characters a Document source falls back to Visible.</summary>
    public int DocumentMaxChars { get; init; } = 20_000;
    /// <summary>
    /// True for word processors and editors whose document element is always the
    /// writing surface. Elsewhere (a browser's page) a document counts as a text
    /// field only when the host says it is editable.
    /// </summary>
    public bool EditableDocuments { get; init; }
    /// <summary>True when this rule came from the defaults because no app row matched.</summary>
    public bool IsDefault { get; init; }
}

/// <summary>
/// Per-app rules for Windows, by executable name, read from
/// <c>packages/desktop-rules/apps-windows.json</c>. Adding an app is a row in
/// that file, not a release (docs/inline-review-design.md section 1).
/// </summary>
public sealed class AppRules
{
    private readonly Dictionary<string, AppRule> _byProcess;

    private AppRules(AppRule defaults, IReadOnlyList<AppRule> apps)
    {
        Defaults = defaults;
        Apps = apps;
        _byProcess = new Dictionary<string, AppRule>(StringComparer.OrdinalIgnoreCase);
        foreach (var app in apps)
            foreach (var p in app.Processes)
                _byProcess[NormaliseProcess(p)] = app;
    }

    public AppRule Defaults { get; }
    public IReadOnlyList<AppRule> Apps { get; }

    /// <summary>The rule for a process (case-insensitive, with or without ".exe"); the defaults when no row matches.</summary>
    public AppRule For(string? processName)
    {
        if (!string.IsNullOrWhiteSpace(processName) && _byProcess.TryGetValue(NormaliseProcess(processName), out var rule))
            return rule;
        return Defaults with { IsDefault = true, Label = processName ?? "" };
    }

    /// <summary>"notepad.exe", "Notepad" and "NOTEPAD.EXE" all become "notepad".</summary>
    public static string NormaliseProcess(string name)
    {
        name = name.Trim();
        if (name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)) name = name[..^4];
        return name.ToLowerInvariant();
    }

    public static AppRules Load(string path) => Parse(File.ReadAllText(path, Encoding.UTF8));

    public static AppRules Parse(string json)
    {
        using var doc = JsonDocument.Parse(json, new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true });
        var root = doc.RootElement;
        var defaults = new AppRule();
        if (root.TryGetProperty("defaults", out var d) && d.ValueKind == JsonValueKind.Object)
            defaults = Read(d, defaults);
        var apps = new List<AppRule>();
        if (root.TryGetProperty("apps", out var list) && list.ValueKind == JsonValueKind.Array)
        {
            foreach (var row in list.EnumerateArray())
            {
                var app = Read(row, defaults with { IsDefault = false });
                if (app.Processes.Count == 0)
                    throw new InvalidDataException("apps-windows.json: every app row needs a \"process\" list.");
                apps.Add(app);
            }
        }
        return new AppRules(defaults, apps);
    }

    private static AppRule Read(JsonElement e, AppRule baseRule)
    {
        var r = baseRule;
        if (e.TryGetProperty("label", out var label) && label.ValueKind == JsonValueKind.String)
            r = r with { Label = label.GetString()! };
        if (e.TryGetProperty("process", out var proc))
        {
            var names = proc.ValueKind == JsonValueKind.Array
                ? proc.EnumerateArray().Where(x => x.ValueKind == JsonValueKind.String).Select(x => x.GetString()!).ToList()
                : proc.ValueKind == JsonValueKind.String ? new List<string> { proc.GetString()! } : new List<string>();
            r = r with { Processes = names };
        }
        if (e.TryGetProperty("enabled", out var en) && (en.ValueKind is JsonValueKind.True or JsonValueKind.False))
            r = r with { Enabled = en.GetBoolean() };
        if (e.TryGetProperty("reason", out var reason) && reason.ValueKind == JsonValueKind.String)
            r = r with { Reason = reason.GetString() };
        if (e.TryGetProperty("widget", out var w) && w.ValueKind == JsonValueKind.Object)
        {
            if (w.TryGetProperty("corner", out var c) && c.ValueKind == JsonValueKind.String)
                r = r with { WidgetCorner = ParseCorner(c.GetString()!) };
            if (w.TryGetProperty("offset_x", out var ox) && ox.TryGetDouble(out var oxv))
                r = r with { WidgetOffsetX = oxv };
            if (w.TryGetProperty("offset_y", out var oy) && oy.TryGetDouble(out var oyv))
                r = r with { WidgetOffsetY = oyv };
        }
        if (e.TryGetProperty("forbidden_corners", out var fc) && fc.ValueKind == JsonValueKind.Array)
            r = r with { ForbiddenCorners = fc.EnumerateArray().Select(x => ParseCorner(x.GetString() ?? "")).ToList() };
        if (e.TryGetProperty("write_back", out var wb) && wb.ValueKind == JsonValueKind.Array)
            r = r with { WriteBack = wb.EnumerateArray().Select(x => ParseWriteBack(x.GetString() ?? "")).ToList() };
        if (e.TryGetProperty("polling", out var p) && p.ValueKind == JsonValueKind.Object)
        {
            if (p.TryGetProperty("needed", out var need) && (need.ValueKind is JsonValueKind.True or JsonValueKind.False))
                r = r with { PollingNeeded = need.GetBoolean() };
            if (p.TryGetProperty("interval_ms", out var iv) && iv.TryGetInt32(out var ivv))
                r = r with { PollIntervalMs = Math.Clamp(ivv, 200, 10_000) };
        }
        if (e.TryGetProperty("text_source", out var ts) && ts.ValueKind == JsonValueKind.String)
            r = r with { TextSource = ts.GetString() switch
            {
                "visible" => TextSource.Visible,
                "document" => TextSource.Document,
                var other => throw new InvalidDataException($"apps-windows.json: unknown text_source \"{other}\"."),
            } };
        if (e.TryGetProperty("editable_documents", out var ed) && (ed.ValueKind is JsonValueKind.True or JsonValueKind.False))
            r = r with { EditableDocuments = ed.GetBoolean() };
        if (e.TryGetProperty("document_max_chars", out var dm) && dm.TryGetInt32(out var dmv))
            r = r with { DocumentMaxChars = dmv };
        return r;
    }

    public static Corner ParseCorner(string s) => s switch
    {
        "top-left" => Corner.TopLeft,
        "top-right" => Corner.TopRight,
        "bottom-left" => Corner.BottomLeft,
        "bottom-right" => Corner.BottomRight,
        _ => throw new InvalidDataException($"apps-windows.json: unknown corner \"{s}\"."),
    };

    public static WriteBackMethod ParseWriteBack(string s) => s switch
    {
        "select-type" => WriteBackMethod.SelectAndType,
        "select-paste" => WriteBackMethod.SelectAndPaste,
        "value-set" => WriteBackMethod.ValueSet,
        _ => throw new InvalidDataException($"apps-windows.json: unknown write_back method \"{s}\"."),
    };
}
