using System;
using System.Collections.Generic;
using System.IO;
using Researchly.Overlay.Core.Settings;

namespace Researchly.Overlay.Core.Eligibility;

/// <summary>
/// What the shell could learn about the focused field from UI Automation.
/// Read on focus, kept in memory, never written anywhere.
/// </summary>
public sealed record FieldDescriptor
{
    /// <summary>The executable, e.g. "notepad.exe".</summary>
    public string ProcessName { get; init; } = "";
    public bool IsPassword { get; init; }
    public bool IsReadOnly { get; init; }
    /// <summary>True when the element can hold editable text (an edit or document with a text or value pattern).</summary>
    public bool IsTextField { get; init; }
    public string? Name { get; init; }
    public string? AutomationId { get; init; }
    public string? HelpText { get; init; }
    public string? Placeholder { get; init; }
    public string? LabeledByName { get; init; }
    public string? AriaRole { get; init; }
    /// <summary>Names of enclosing forms (web forms, dialogs marked as forms), nearest first.</summary>
    public IReadOnlyList<string> FormNames { get; init; } = Array.Empty<string>();
    /// <summary>Text length when known; null when the shell reads only the visible part.</summary>
    public int? TextLength { get; init; }

    /// <summary>The label-like strings matched against the keyword blocklist.</summary>
    public IEnumerable<string?> LabelTexts()
    {
        yield return Name;
        yield return AutomationId;
        yield return HelpText;
        yield return Placeholder;
        yield return LabeledByName;
        // The ARIA role "searchbox" is one word; split it so the "search" term applies.
        yield return string.Equals(AriaRole, "searchbox", StringComparison.OrdinalIgnoreCase) ? "search box" : AriaRole;
        foreach (var f in FormNames) yield return f;
    }
}

/// <summary>Why the client will or will not appear on a field.</summary>
public enum EligibilityReason
{
    Eligible,
    PausedEverywhere,
    AppRuleOff,
    AppPaused,
    SecureField,
    ReadOnly,
    NotATextField,
    BlockedLabel,
    TooLong,
}

public sealed record Eligibility(EligibilityReason Reason, AppRule App, BlockedTerm? Term = null)
{
    public bool IsEligible => Reason == EligibilityReason.Eligible;
}

/// <summary>
/// The restraint gate (docs/inline-review-design.md section 1, item 2): the
/// client checks eligibility before appearing anywhere. Order matters only for
/// the reason reported; any one failure keeps the client away.
/// </summary>
public sealed class EligibilityGate
{
    public EligibilityGate(FieldKeywordRules fields, AppRules apps)
    {
        Fields = fields;
        Apps = apps;
    }

    public FieldKeywordRules Fields { get; }
    public AppRules Apps { get; }

    /// <summary>Loads both rule files from <paramref name="rulesDirectory"/> (fields.json, apps-windows.json).</summary>
    public static EligibilityGate Load(string rulesDirectory) =>
        new(FieldKeywordRules.Load(Path.Combine(rulesDirectory, "fields.json")),
            AppRules.Load(Path.Combine(rulesDirectory, "apps-windows.json")));

    public Eligibility Evaluate(FieldDescriptor field, OverlaySettings settings, DateTimeOffset now)
    {
        var app = Apps.For(field.ProcessName);
        if (settings.IsPausedEverywhere(now)) return new(EligibilityReason.PausedEverywhere, app);
        if (!app.Enabled) return new(EligibilityReason.AppRuleOff, app);
        if (settings.IsAppPaused(field.ProcessName)) return new(EligibilityReason.AppPaused, app);
        // A secure field is never read, whatever the rules file says
        // (never_secure_fields is documentation, not a switch).
        if (field.IsPassword) return new(EligibilityReason.SecureField, app);
        if (!field.IsTextField) return new(EligibilityReason.NotATextField, app);
        if (field.IsReadOnly) return new(EligibilityReason.ReadOnly, app);
        var term = Fields.FindBlockedTerm(field.LabelTexts());
        if (term != null) return new(EligibilityReason.BlockedLabel, app, term);
        if (field.TextLength is int len && len > Fields.MaxFieldCharacters && app.TextSource == TextSource.Document)
            return new(EligibilityReason.TooLong, app);
        return new(EligibilityReason.Eligible, app);
    }
}

/// <summary>Finds the rules folder copied next to the running assembly.</summary>
public static class RulesLocator
{
    /// <summary>
    /// <c>rules\</c> beside the executable (where the build copies it); when that is
    /// missing (running from a source checkout), walks up to <c>packages/desktop-rules</c>.
    /// </summary>
    public static string Find(string? startDirectory = null)
    {
        string start = startDirectory ?? AppContext.BaseDirectory;
        string beside = Path.Combine(start, "rules");
        if (File.Exists(Path.Combine(beside, "fields.json"))) return beside;
        var dir = new DirectoryInfo(start);
        while (dir != null)
        {
            string candidate = Path.Combine(dir.FullName, "packages", "desktop-rules");
            if (File.Exists(Path.Combine(candidate, "fields.json"))) return candidate;
            dir = dir.Parent;
        }
        throw new FileNotFoundException("Researchly's rules folder (fields.json, apps-windows.json) was not found next to the program.");
    }
}
