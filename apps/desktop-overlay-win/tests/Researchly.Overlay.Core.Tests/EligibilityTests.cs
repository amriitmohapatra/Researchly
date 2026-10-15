using System;
using System.IO;
using System.Linq;
using Researchly.Overlay.Core.Eligibility;
using Researchly.Overlay.Core.Placement;
using Researchly.Overlay.Core.Settings;
using Xunit;

namespace Researchly.Overlay.Core.Tests;

public class FieldKeywordTests
{
    private static readonly FieldKeywordRules Rules = FieldKeywordRules.Load(Path.Combine(Fixtures.RulesDirectory, "fields.json"));

    [Fact]
    public void Shared_rules_file_is_copied_next_to_the_tests_and_has_all_eight_languages()
    {
        Assert.Equal(new[] { "de", "en", "es", "fr", "hi", "ms", "pt", "zh" }, Rules.Keywords.Keys.OrderBy(k => k, StringComparer.Ordinal));
        Assert.True(Rules.NeverSecureFields);
        Assert.Contains("zh", Rules.SubstringLanguages);
        Assert.Contains("hi", Rules.SubstringLanguages);
    }

    [Theory]
    // English, including identifiers split into words
    [InlineData("Password", "en")]
    [InlineData("txtPassword", "en")]
    [InlineData("user_name", "en")]
    [InlineData("Sign-in email", "en")]
    [InlineData("Enter your PIN", "en")]
    [InlineData("Card number", "en")]
    [InlineData("searchbox", null)]          // one word: not the term "search" on its own
    [InlineData("Search", "en")]
    [InlineData("One-time code", "en")]
    // French, with a typographic apostrophe
    [InlineData("Mot de passe", "fr")]
    [InlineData("Nom d'utilisateur", "fr")]
    // German
    [InlineData("Kennwort", "de")]
    [InlineData("Benutzername", "de")]
    // Spanish
    [InlineData("Contraseña", "es")]
    [InlineData("Fecha de nacimiento", "es")]
    // Portuguese
    [InlineData("Senha", "pt")]
    [InlineData("Número do cartão", "pt")]
    // Chinese (matched as a substring)
    [InlineData("请输入密码", "zh")]
    [InlineData("手机号码", "zh")]
    // Hindi (matched as a substring)
    [InlineData("पासवर्ड दर्ज करें", "hi")]
    [InlineData("उपयोगकर्ता नाम", "hi")]
    // Malay
    [InlineData("Kata laluan", "ms")]
    [InlineData("Nombor kad", "ms")]
    public void Blocklisted_labels_are_found_in_every_language(string label, string? language)
    {
        var hit = Rules.FindBlockedTerm(label);
        if (language == null) Assert.Null(hit);
        else
        {
            Assert.NotNull(hit);
            Assert.Equal(language, hit!.Language);
        }
    }

    [Fact]
    public void Typographic_apostrophe_matches_the_plain_one()
    {
        string label = "Nom d" + (char)0x2019 + "utilisateur";
        Assert.Equal("fr", Rules.FindBlockedTerm(label)!.Language);
    }

    [Theory]
    [InlineData("Research notes")]          // "search" inside a word
    [InlineData("Spinner speed")]           // "pin" inside a word
    [InlineData("Opinion piece")]
    [InlineData("Abstract")]
    [InlineData("Message body")]
    [InlineData("Discussion")]
    [InlineData("Commentaire")]             // French: comment
    [InlineData("Zusammenfassung")]         // German: summary
    [InlineData("Resumen")]                 // Spanish: summary
    [InlineData("Comentário")]              // Portuguese: comment
    [InlineData("摘要")]                    // Chinese: abstract
    [InlineData("टिप्पणी")]                  // Hindi: comment
    [InlineData("Ringkasan")]               // Malay: summary
    [InlineData("")]
    public void Ordinary_writing_fields_are_not_blocked(string label)
    {
        Assert.Null(Rules.FindBlockedTerm(label));
    }

    [Fact]
    public void Identifier_splitting_and_word_boundaries()
    {
        Assert.Equal("txt password", FieldKeywordRules.NormaliseWords("txtPassword"));
        Assert.Equal("sign in form", FieldKeywordRules.NormaliseWords("sign-in_form"));
        Assert.True(FieldKeywordRules.ContainsWord("enter pin1", "pin"));
        Assert.False(FieldKeywordRules.ContainsWord("spinning", "pin"));
    }

    [Fact]
    public void A_rules_file_without_keywords_is_refused()
    {
        Assert.Throws<InvalidDataException>(() => FieldKeywordRules.Parse("{\"keywords\":{}}"));
    }
}

public class AppRuleTests
{
    private static readonly AppRules Apps = AppRules.Load(Path.Combine(Fixtures.RulesDirectory, "apps-windows.json"));

    [Theory]
    [InlineData("WINWORD.EXE")]
    [InlineData("notepad.exe")]
    [InlineData("wordpad.exe")]
    [InlineData("OUTLOOK.EXE")]
    [InlineData("msedge.exe")]
    [InlineData("chrome.exe")]
    [InlineData("firefox.exe")]
    [InlineData("ms-teams.exe")]
    [InlineData("Teams.exe")]
    [InlineData("slack.exe")]
    public void Writing_apps_are_enabled(string process)
    {
        var rule = Apps.For(process);
        Assert.False(rule.IsDefault);
        Assert.True(rule.Enabled);
        Assert.NotEmpty(rule.WriteBack);
    }

    [Theory]
    [InlineData("WindowsTerminal.exe")]
    [InlineData("cmd.exe")]
    [InlineData("powershell.exe")]
    [InlineData("pwsh.exe")]
    [InlineData("Code.exe")]
    [InlineData("devenv.exe")]
    [InlineData("KeePass.exe")]
    [InlineData("1Password.exe")]
    public void Terminals_code_editors_and_password_managers_are_off(string process)
    {
        var rule = Apps.For(process);
        Assert.False(rule.Enabled);
        Assert.False(string.IsNullOrWhiteSpace(rule.Reason));
    }

    [Fact]
    public void Process_names_match_without_case_or_extension()
    {
        Assert.Equal("Microsoft Word", Apps.For("winword").Label);
        Assert.Equal("Microsoft Word", Apps.For("WinWord.exe").Label);
        Assert.Equal("Notepad", Apps.For("Notepad").Label);
    }

    [Fact]
    public void Unknown_apps_get_the_defaults_and_are_on()
    {
        var rule = Apps.For("SomeEditor.exe");
        Assert.True(rule.IsDefault);
        Assert.True(rule.Enabled);
        Assert.Equal(TextSource.Document, rule.TextSource);
        Assert.Equal(new[] { WriteBackMethod.SelectAndType, WriteBackMethod.SelectAndPaste }, rule.WriteBack);
    }

    [Fact]
    public void Word_reads_the_visible_paragraphs_and_polls()
    {
        var word = Apps.For("WINWORD.EXE");
        Assert.Equal(TextSource.Visible, word.TextSource);
        Assert.True(word.PollingNeeded);
        Assert.Contains(Corner.TopRight, word.ForbiddenCorners);
    }

    [Fact]
    public void Only_native_editors_trust_their_document_element()
    {
        Assert.True(Apps.For("WINWORD.EXE").EditableDocuments);
        Assert.True(Apps.For("notepad.exe").EditableDocuments);
        Assert.False(Apps.For("chrome.exe").EditableDocuments);   // a web page is a document too
        Assert.False(Apps.For("msedge.exe").EditableDocuments);
        Assert.False(Apps.For("SomeEditor.exe").EditableDocuments);
    }

    [Fact]
    public void No_app_writes_back_with_value_set_first()
    {
        foreach (var app in Apps.Apps.Where(a => a.Enabled))
            Assert.NotEqual(WriteBackMethod.ValueSet, app.WriteBack[0]);
    }

    [Fact]
    public void App_rows_override_defaults_field_by_field()
    {
        var rules = AppRules.Parse("""
            { "defaults": { "widget": { "corner": "bottom-right", "offset_x": 5, "offset_y": 6 }, "polling": { "needed": false, "interval_ms": 900 } },
              "apps": [ { "process": "x.exe", "widget": { "corner": "top-left" }, "polling": { "needed": true } } ] }
            """);
        var x = rules.For("x.exe");
        Assert.Equal(Corner.TopLeft, x.WidgetCorner);
        Assert.Equal(5, x.WidgetOffsetX);
        Assert.True(x.PollingNeeded);
        Assert.Equal(900, x.PollIntervalMs);
    }

    [Fact]
    public void Unknown_values_in_the_rules_file_fail_loudly()
    {
        Assert.Throws<InvalidDataException>(() => AppRules.Parse("""{ "apps": [ { "process": "x.exe", "widget": { "corner": "middle" } } ] }"""));
        Assert.Throws<InvalidDataException>(() => AppRules.Parse("""{ "apps": [ { "process": "x.exe", "write_back": ["telepathy"] } ] }"""));
        Assert.Throws<InvalidDataException>(() => AppRules.Parse("""{ "apps": [ { "label": "no process" } ] }"""));
    }
}

public class EligibilityGateTests
{
    private static readonly EligibilityGate Gate = EligibilityGate.Load(Fixtures.RulesDirectory);
    private static readonly DateTimeOffset Now = new(2026, 10, 15, 9, 0, 0, TimeSpan.Zero);

    private static FieldDescriptor Field(string process = "notepad.exe", string? name = "Text editor") => new()
    {
        ProcessName = process,
        IsTextField = true,
        Name = name,
        TextLength = 120,
    };

    [Fact]
    public void An_ordinary_text_field_is_eligible()
    {
        Assert.True(Gate.Evaluate(Field(), new OverlaySettings(), Now).IsEligible);
    }

    [Fact]
    public void Password_fields_are_never_eligible()
    {
        var e = Gate.Evaluate(Field() with { IsPassword = true, Name = "Notes" }, new OverlaySettings(), Now);
        Assert.Equal(EligibilityReason.SecureField, e.Reason);
    }

    [Fact]
    public void Blocklisted_label_placeholder_or_form_name_keeps_the_client_away()
    {
        var s = new OverlaySettings();
        Assert.Equal(EligibilityReason.BlockedLabel, Gate.Evaluate(Field("chrome.exe", "Comment") with { Placeholder = "Enter your email or phone" }, s, Now).Reason);
        Assert.Equal(EligibilityReason.BlockedLabel, Gate.Evaluate(Field("chrome.exe", "Name") with { FormNames = new[] { "Sign in" } }, s, Now).Reason);
        Assert.Equal(EligibilityReason.BlockedLabel, Gate.Evaluate(Field("msedge.exe", "Address and search bar"), s, Now).Reason);
        Assert.Equal(EligibilityReason.BlockedLabel, Gate.Evaluate(Field("chrome.exe", "q") with { AriaRole = "search" }, s, Now).Reason);
        Assert.Equal(EligibilityReason.BlockedLabel, Gate.Evaluate(Field("chrome.exe", "q") with { AriaRole = "searchbox" }, s, Now).Reason);
        Assert.True(Gate.Evaluate(Field("chrome.exe", "Write a comment") with { AriaRole = "textbox" }, s, Now).IsEligible);
        Assert.Equal(EligibilityReason.BlockedLabel, Gate.Evaluate(Field("chrome.exe", null) with { LabeledByName = "Kennwort" }, s, Now).Reason);
    }

    [Fact]
    public void Read_only_and_non_text_elements_are_not_eligible()
    {
        var s = new OverlaySettings();
        Assert.Equal(EligibilityReason.ReadOnly, Gate.Evaluate(Field() with { IsReadOnly = true }, s, Now).Reason);
        Assert.Equal(EligibilityReason.NotATextField, Gate.Evaluate(Field() with { IsTextField = false }, s, Now).Reason);
    }

    [Fact]
    public void Disabled_apps_are_not_eligible()
    {
        Assert.Equal(EligibilityReason.AppRuleOff, Gate.Evaluate(Field("WindowsTerminal.exe"), new OverlaySettings(), Now).Reason);
        Assert.Equal(EligibilityReason.AppRuleOff, Gate.Evaluate(Field("Code.exe"), new OverlaySettings(), Now).Reason);
    }

    [Fact]
    public void Pausing_everywhere_or_for_an_app_hides_the_client()
    {
        var s = new OverlaySettings();
        s.PauseForOneHour(Now);
        Assert.Equal(EligibilityReason.PausedEverywhere, Gate.Evaluate(Field(), s, Now.AddMinutes(59)).Reason);
        Assert.True(Gate.Evaluate(Field(), s, Now.AddMinutes(61)).IsEligible);

        var a = new OverlaySettings();
        a.PauseApp("NOTEPAD.EXE");
        Assert.Equal(EligibilityReason.AppPaused, Gate.Evaluate(Field("notepad.exe"), a, Now).Reason);
        Assert.True(Gate.Evaluate(Field("WINWORD.EXE"), a, Now).IsEligible);
        a.ResumeApp("notepad");
        Assert.True(Gate.Evaluate(Field("notepad.exe"), a, Now).IsEligible);
    }

    [Fact]
    public void Huge_fields_are_skipped_unless_the_app_reads_only_the_visible_part()
    {
        var s = new OverlaySettings();
        Assert.Equal(EligibilityReason.TooLong, Gate.Evaluate(Field() with { TextLength = 2_000_000 }, s, Now).Reason);
        Assert.True(Gate.Evaluate(Field("WINWORD.EXE", "Page 1 content") with { TextLength = 2_000_000 }, s, Now).IsEligible);
        Assert.True(Gate.Evaluate(Field("WINWORD.EXE", "Page 1 content") with { TextLength = null }, s, Now).IsEligible);
    }
}

public class WidgetPlacementTests
{
    private static readonly Box Screen = new(0, 0, 1920, 1080);

    [Fact]
    public void Pins_to_the_rule_corner_with_its_inset()
    {
        var rule = new AppRule { WidgetCorner = Corner.BottomRight, WidgetOffsetX = 10, WidgetOffsetY = 8 };
        var (x, y) = WidgetPlacement.Place(new Box(100, 100, 600, 400), 24, rule, null, Screen);
        Assert.Equal(100 + 600 - 10 - 24, x);
        Assert.Equal(100 + 400 - 8 - 24, y);
    }

    [Fact]
    public void A_forbidden_corner_falls_back_to_the_next_allowed_one()
    {
        var rule = new AppRule { WidgetCorner = Corner.BottomRight, ForbiddenCorners = new[] { Corner.BottomRight } };
        Assert.Equal(Corner.TopRight, WidgetPlacement.ChooseCorner(rule));
        var all = new AppRule { WidgetCorner = Corner.TopLeft, ForbiddenCorners = new[] { Corner.TopLeft, Corner.BottomRight, Corner.TopRight } };
        Assert.Equal(Corner.BottomLeft, WidgetPlacement.ChooseCorner(all));
    }

    [Fact]
    public void The_writers_drag_and_the_dpi_scale_apply()
    {
        var rule = new AppRule { WidgetCorner = Corner.TopLeft, WidgetOffsetX = 10, WidgetOffsetY = 10 };
        var (x, y) = WidgetPlacement.Place(new Box(200, 200, 800, 600), 48, rule, new WidgetNudge(5, -5), Screen, scale: 2.0);
        Assert.Equal(200 + 20 + 10, x);
        Assert.Equal(200 + 20 - 10, y);
    }

    [Fact]
    public void Stays_inside_the_work_area()
    {
        var rule = new AppRule { WidgetCorner = Corner.BottomRight, WidgetOffsetX = 10, WidgetOffsetY = 8 };
        var (x, y) = WidgetPlacement.Place(new Box(1800, 1000, 400, 300), 24, rule, null, Screen);
        Assert.True(x <= 1920 - 24);
        Assert.True(y <= 1080 - 24);
    }

    [Fact]
    public void A_one_line_field_centres_the_widget_vertically()
    {
        var rule = new AppRule { WidgetCorner = Corner.BottomRight, WidgetOffsetX = 6, WidgetOffsetY = 8 };
        var (_, y) = WidgetPlacement.Place(new Box(100, 100, 400, 30), 24, rule, null, Screen);
        Assert.Equal(103, y);
    }
}
