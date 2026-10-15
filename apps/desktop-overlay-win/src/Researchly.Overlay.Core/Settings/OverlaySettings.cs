using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Researchly.Overlay.Core.Eligibility;

namespace Researchly.Overlay.Core.Settings;

/// <summary>Which engine checks the text.</summary>
public enum EngineChoice
{
    /// <summary>"This computer": an engine running on this machine (http://127.0.0.1:3517).</summary>
    ThisComputer,
    /// <summary>The hosted Researchly engine at <see cref="OverlaySettings.HostedUrl"/>.</summary>
    Hosted,
}

/// <summary>Where the writer dragged the widget, relative to where the app rule puts it (DIPs).</summary>
public sealed record WidgetNudge(double Dx, double Dy);

/// <summary>
/// Everything the client keeps on disk. Settings only: no document text, no
/// suggestion, no field label is ever written here (CLAUDE.md, rule 2).
/// Stored as JSON at %APPDATA%\Researchly\overlay-settings.json.
/// </summary>
public sealed class OverlaySettings
{
    public const string LocalEngineUrl = "http://127.0.0.1:3517";

    public int Version { get; set; } = 1;
    public EngineChoice Engine { get; set; } = EngineChoice.ThisComputer;
    public string? HostedUrl { get; set; }
    /// <summary>Paused everywhere until this moment (UTC); null when not paused.</summary>
    public DateTimeOffset? PausedUntil { get; set; }
    /// <summary>Apps paused "always", by normalised process name (see <see cref="AppRules.NormaliseProcess"/>).</summary>
    public List<string> PausedApps { get; set; } = new();
    public bool ShowPreferences { get; set; }
    /// <summary>The English spelling to keep to ("us", "uk", ...); null lets the engine decide.</summary>
    public string? Spelling { get; set; }
    public bool DragTipShown { get; set; }
    /// <summary>Per-app widget drag, by normalised process name.</summary>
    public Dictionary<string, WidgetNudge> WidgetNudges { get; set; } = new();

    /// <summary>The engine base URL in use, or null when the hosted choice has no valid address yet.</summary>
    public string? EngineBaseUrl() =>
        Engine == EngineChoice.ThisComputer
            ? LocalEngineUrl
            : EngineEndpoint.TryNormalise(HostedUrl, out var url) ? url : null;

    public bool IsPausedEverywhere(DateTimeOffset now) => PausedUntil is { } until && now < until;

    public bool IsAppPaused(string? process) =>
        !string.IsNullOrWhiteSpace(process)
        && PausedApps.Contains(AppRules.NormaliseProcess(process), StringComparer.OrdinalIgnoreCase);

    /// <summary>Pause for one hour from <paramref name="now"/>.</summary>
    public void PauseForOneHour(DateTimeOffset now) => PausedUntil = now.AddHours(1);

    /// <summary>Pause until the next local midnight after <paramref name="nowLocal"/> (its offset is the local one).</summary>
    public void PauseUntilTomorrow(DateTimeOffset nowLocal)
    {
        var midnight = new DateTimeOffset(nowLocal.Date.AddDays(1), nowLocal.Offset);
        PausedUntil = midnight;
    }

    public void PauseApp(string process)
    {
        string p = AppRules.NormaliseProcess(process);
        if (!PausedApps.Contains(p, StringComparer.OrdinalIgnoreCase)) PausedApps.Add(p);
    }

    public void ResumeApp(string process) =>
        PausedApps.RemoveAll(p => string.Equals(p, AppRules.NormaliseProcess(process), StringComparison.OrdinalIgnoreCase));

    public void ResumeEverywhere() => PausedUntil = null;
}

/// <summary>Validates engine addresses.</summary>
public static class EngineEndpoint
{
    /// <summary>
    /// Trims, drops a trailing slash, and accepts https for any host or plain
    /// http only for this computer (127.0.0.1, ::1, localhost): text never
    /// travels over the network unencrypted.
    /// </summary>
    public static bool TryNormalise(string? input, out string url)
    {
        url = "";
        if (string.IsNullOrWhiteSpace(input)) return false;
        if (!Uri.TryCreate(input.Trim(), UriKind.Absolute, out var uri)) return false;
        if (!string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query) || !string.IsNullOrEmpty(uri.Fragment))
            return false;
        bool loopback = uri.IsLoopback;
        if (uri.Scheme == Uri.UriSchemeHttps || (uri.Scheme == Uri.UriSchemeHttp && loopback))
        {
            url = uri.GetLeftPart(UriPartial.Path).TrimEnd('/');
            return true;
        }
        return false;
    }
}

/// <summary>Reads and writes <see cref="OverlaySettings"/>; a missing or damaged file gives the defaults.</summary>
public static class SettingsStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower) },
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
    };

    /// <summary>%APPDATA%\Researchly\overlay-settings.json (or the platform's equivalent).</summary>
    public static string DefaultPath() =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Researchly", "overlay-settings.json");

    public static OverlaySettings Load(string path)
    {
        try
        {
            if (!File.Exists(path)) return new OverlaySettings();
            var s = JsonSerializer.Deserialize<OverlaySettings>(File.ReadAllText(path, Encoding.UTF8), Options);
            return s ?? new OverlaySettings();
        }
        catch (Exception e) when (e is JsonException or IOException or UnauthorizedAccessException or NotSupportedException)
        {
            return new OverlaySettings();
        }
    }

    public static string Serialise(OverlaySettings settings) => JsonSerializer.Serialize(settings, Options);

    /// <summary>Writes atomically: a temporary file, then a replace.</summary>
    public static void Save(string path, OverlaySettings settings)
    {
        string dir = Path.GetDirectoryName(path)!;
        Directory.CreateDirectory(dir);
        string tmp = path + ".tmp";
        File.WriteAllText(tmp, Serialise(settings), new UTF8Encoding(false));
        File.Move(tmp, path, overwrite: true);
    }
}
