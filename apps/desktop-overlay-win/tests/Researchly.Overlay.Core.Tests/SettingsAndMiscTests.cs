using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Session;
using Researchly.Overlay.Core.Settings;
using Researchly.Overlay.Core.State;
using Researchly.Overlay.Core.Text;
using Researchly.Overlay.Core.Tokens;
using Researchly.Overlay.Core.WriteBack;
using Xunit;

namespace Researchly.Overlay.Core.Tests;

public class SettingsTests
{
    [Fact]
    public void Round_trips_through_a_file()
    {
        string dir = Path.Combine(Path.GetTempPath(), "researchly-overlay-tests-" + Guid.NewGuid().ToString("N"));
        string path = Path.Combine(dir, "overlay-settings.json");
        try
        {
            var s = new OverlaySettings { Engine = EngineChoice.Hosted, HostedUrl = "https://engine.example.invalid", ShowPreferences = true, DragTipShown = true };
            s.PauseApp("Slack.exe");
            s.WidgetNudges["notepad"] = new WidgetNudge(-12, 4);
            SettingsStore.Save(path, s);
            var back = SettingsStore.Load(path);
            Assert.Equal(EngineChoice.Hosted, back.Engine);
            Assert.Equal("https://engine.example.invalid", back.HostedUrl);
            Assert.True(back.ShowPreferences);
            Assert.True(back.DragTipShown);
            Assert.Equal(new[] { "slack" }, back.PausedApps);
            Assert.Equal(new WidgetNudge(-12, 4), back.WidgetNudges["notepad"]);
            Assert.False(File.Exists(path + ".tmp"));
        }
        finally
        {
            if (Directory.Exists(dir)) Directory.Delete(dir, true);
        }
    }

    [Fact]
    public void A_missing_or_damaged_file_gives_the_defaults()
    {
        string path = Path.Combine(Path.GetTempPath(), "researchly-overlay-missing-" + Guid.NewGuid().ToString("N") + ".json");
        Assert.Equal(EngineChoice.ThisComputer, SettingsStore.Load(path).Engine);
        File.WriteAllText(path, "{ this is not json");
        try { Assert.Equal(EngineChoice.ThisComputer, SettingsStore.Load(path).Engine); }
        finally { File.Delete(path); }
    }

    [Fact]
    public void Settings_hold_only_settings_never_text()
    {
        // A guard for rule 2 (confidential by design): adding a field here is a
        // deliberate act that must update this list after asking whether it could hold text.
        using var doc = JsonDocument.Parse(SettingsStore.Serialise(new OverlaySettings()));
        var keys = doc.RootElement.EnumerateObject().Select(p => p.Name).OrderBy(k => k, StringComparer.Ordinal).ToArray();
        Assert.Equal(new[] { "drag_tip_shown", "engine", "hosted_url", "paused_apps", "paused_until", "show_preferences", "spelling", "version", "widget_nudges" }, keys);
    }

    [Fact]
    public void Pause_until_tomorrow_ends_at_the_next_local_midnight()
    {
        var s = new OverlaySettings();
        var nowLocal = new DateTimeOffset(2026, 10, 15, 22, 30, 0, TimeSpan.FromHours(8));
        s.PauseUntilTomorrow(nowLocal);
        Assert.Equal(new DateTimeOffset(2026, 10, 16, 0, 0, 0, TimeSpan.FromHours(8)), s.PausedUntil);
        Assert.True(s.IsPausedEverywhere(nowLocal.AddHours(1)));
        Assert.False(s.IsPausedEverywhere(nowLocal.AddHours(2)));
        s.PauseForOneHour(nowLocal);
        Assert.Equal(nowLocal.AddHours(1), s.PausedUntil);
        s.ResumeEverywhere();
        Assert.False(s.IsPausedEverywhere(nowLocal));
    }

    [Theory]
    [InlineData("https://engine.example.invalid/", true, "https://engine.example.invalid")]
    [InlineData("  https://engine.example.invalid/api  ", true, "https://engine.example.invalid/api")]
    [InlineData("http://127.0.0.1:3517", true, "http://127.0.0.1:3517")]
    [InlineData("http://localhost:8080/", true, "http://localhost:8080")]
    [InlineData("http://engine.example.invalid", false, "")]       // plain http over the network: refused
    [InlineData("https://user:pw@engine.example.invalid", false, "")]
    [InlineData("https://engine.example.invalid/?x=1", false, "")]
    [InlineData("ftp://engine.example.invalid", false, "")]
    [InlineData("not a url", false, "")]
    [InlineData("", false, "")]
    public void Engine_addresses_are_validated(string input, bool ok, string expected)
    {
        Assert.Equal(ok, EngineEndpoint.TryNormalise(input, out var url));
        Assert.Equal(expected, url);
    }

    [Fact]
    public void This_computer_is_the_default_engine()
    {
        var s = new OverlaySettings();
        Assert.Equal("http://127.0.0.1:3517", s.EngineBaseUrl());
        s.Engine = EngineChoice.Hosted;
        Assert.Null(s.EngineBaseUrl());                  // hosted without an address yet
        s.HostedUrl = "https://engine.example.invalid/";
        Assert.Equal("https://engine.example.invalid", s.EngineBaseUrl());
    }
}

public class WriteBackPlanTests
{
    private static PlacedSuggestion Placed(string text, string flagged)
    {
        int at = text.IndexOf(flagged, StringComparison.Ordinal);
        var s = new Suggestion("id", "p1", at, at + flagged.Length, Category.Correction, true, "m", "", "", "", new[] { "x" }, null, null, null);
        return new PlacedSuggestion(s, new TextRange16(at, at + flagged.Length), flagged, "p1");
    }

    [Fact]
    public void Applies_only_while_the_flagged_text_is_still_there()
    {
        string text = "We measured teh rate.";
        var p = Placed(text, "teh");
        Assert.True(WriteBackPlan.StillApplies(text, p));
        Assert.False(WriteBackPlan.StillApplies("We measured the rate.", p));
        Assert.False(WriteBackPlan.StillApplies("We teh", p));
        Assert.Equal("We measured the rate.", WriteBackPlan.Expected(text, p, "the"));
    }

    [Fact]
    public void Classifies_attempts()
    {
        string before = "We measured teh rate.";
        string expected = "We measured the rate.";
        Assert.Equal(WriteBackOutcome.Applied, WriteBackPlan.Classify(before, expected, expected));
        Assert.Equal(WriteBackOutcome.NoChange, WriteBackPlan.Classify(before, before, expected));
        Assert.Equal(WriteBackOutcome.Unexpected, WriteBackPlan.Classify(before, "We measured thethe rate.", expected));
        Assert.Equal(WriteBackOutcome.Applied, WriteBackPlan.Classify("a\r\nteh", "a\rthe", "a\r\nthe"));
    }

    [Fact]
    public void Classifies_by_paragraph_when_only_the_visible_part_is_read()
    {
        string before = "We measured teh rate.";
        string expected = "We measured the rate.";
        // The view scrolled: other paragraphs came and went, but ours changed as expected.
        Assert.Equal(WriteBackOutcome.Applied, WriteBackPlan.ClassifyParagraph(before, expected, "New above.\r" + expected + "\rBelow."));
        Assert.Equal(WriteBackOutcome.NoChange, WriteBackPlan.ClassifyParagraph(before, expected, "Above.\r" + before));
        Assert.Equal(WriteBackOutcome.Unexpected, WriteBackPlan.ClassifyParagraph(before, expected, "We measured thethe rate."));
    }

    [Fact]
    public void Keeps_surrogate_pairs_around_the_range_intact()
    {
        string emoji = char.ConvertFromUtf32(0x1F9EA);
        string text = emoji + "teh" + emoji;
        var p = Placed(text, "teh");
        Assert.Equal(emoji + "the" + emoji, WriteBackPlan.Expected(text, p, "the"));
    }
}

public class TokenTests
{
    [Fact]
    public void Every_category_has_a_name_icon_pattern_and_light_and_dark_colours()
    {
        Assert.Equal(4, DesignTokens.All.Count);
        Assert.Equal(4, DesignTokens.All.Select(t => t.Pattern).Distinct().Count());
        foreach (var t in DesignTokens.All)
        {
            Assert.False(string.IsNullOrWhiteSpace(t.Name));
            Assert.False(string.IsNullOrWhiteSpace(t.IconPath));
            Assert.NotEqual(t.Light.Line, t.Dark.Line);
            Assert.Same(t, DesignTokens.For(t.Category));
        }
        Assert.Equal(UnderlinePattern.Solid, DesignTokens.Correction.Pattern);
        Assert.Equal(UnderlinePattern.Dashed, DesignTokens.Improvement.Pattern);
        Assert.Equal(UnderlinePattern.Dotted, DesignTokens.Convention.Pattern);
        Assert.Equal(UnderlinePattern.WavyDotted, DesignTokens.Preference.Pattern);
    }

    [Fact]
    public void Colours_meet_contrast_on_their_surfaces()
    {
        foreach (var dark in new[] { false, true })
        {
            var surface = DesignTokens.Surface(dark).Surface;
            foreach (var t in DesignTokens.All)
            {
                Assert.True(Rgba.Contrast(t.For(dark).Line, surface) >= 3.0, $"{t.Name} line, dark={dark}");
                Assert.True(Rgba.Contrast(t.For(dark).Ink, surface) >= 4.5, $"{t.Name} ink, dark={dark}");
            }
            foreach (var state in Enum.GetValues<OverlayState>())
                Assert.True(Rgba.Contrast(DesignTokens.WidgetColour(state, dark), surface) >= 3.0, $"{state}, dark={dark}");
            Assert.True(Rgba.Contrast(DesignTokens.Surface(dark).Ink, surface) >= 4.5);
            Assert.True(Rgba.Contrast(DesignTokens.Surface(dark).InkSecondary, surface) >= 4.5);
        }
    }

    [Fact]
    public void Conventions_are_never_painted_as_errors()
    {
        // CLAUDE.md rule 3: a Convention never looks like a Correction.
        Assert.NotEqual(DesignTokens.Correction.Light.Line, DesignTokens.Convention.Light.Line);
        Assert.NotEqual(DesignTokens.Correction.Pattern, DesignTokens.Convention.Pattern);
    }

    [Fact]
    public void Hex_parsing()
    {
        Assert.Equal(new Rgba(0xd5, 0x5e, 0x00), Rgba.Hex("#d55e00"));
        Assert.Equal("#d55e00", Rgba.Hex("d55e00").ToString());
        Assert.Throws<FormatException>(() => Rgba.Hex("#12"));
    }
}
