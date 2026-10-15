import XCTest
@testable import ResearchlyOverlayCore

final class EligibilityTests: XCTestCase {
    var gate: EligibilityGate!

    override func setUpWithError() throws {
        let fields = try FieldRules.load(from: Repo.fieldsJSON)
        let apps = try AppRules.load(from: Repo.appsJSON)
        gate = EligibilityGate(fieldRules: fields, appRules: apps)
    }

    func field(_ labels: [String] = [], ids: [String] = [], app: String = "com.apple.TextEdit",
               role: String = "AXTextArea", count: Int? = 120) -> FieldDescriptor {
        FieldDescriptor(bundleID: app, role: role, labels: labels, identifiers: ids, characterCount: count)
    }

    func assertBlocked(_ label: String, _ file: StaticString = #filePath, _ line: UInt = #line) {
        XCTAssertNotNil(gate.blockedTerm(inLabel: label), "expected “\(label)” to be refused", file: file, line: line)
        XCTAssertFalse(gate.evaluate(field([label])).isEligible, file: file, line: line)
    }

    func assertAllowed(_ label: String, _ file: StaticString = #filePath, _ line: UInt = #line) {
        XCTAssertNil(gate.blockedTerm(inLabel: label), "“\(label)” should be allowed", file: file, line: line)
        XCTAssertTrue(gate.evaluate(field([label])).isEligible, file: file, line: line)
    }

    // MARK: The shared field rules, all eight languages

    func testTheRealRulesFileLoads() throws {
        XCTAssertEqual(gate.fieldRules.version, 1)
        XCTAssertEqual(Set(gate.fieldRules.keywords.keys), ["en", "fr", "de", "es", "pt", "zh", "hi", "ms"])
        XCTAssertTrue(gate.fieldRules.neverSecureFields)
    }

    func testEnglish() {
        assertBlocked("Password")
        assertBlocked("Enter your PIN")
        assertBlocked("Card number")
        assertBlocked("One-time code")
        assertBlocked("Sign in to continue")
        assertBlocked("Search")
        assertBlocked("Date of birth (DD/MM/YYYY)")
        assertAllowed("Abstract")
        assertAllowed("Research notes")          // "search" only as a whole word
        assertAllowed("Pinned summary")          // "pin" only as a whole word
        assertAllowed("Message body")
        assertAllowed("Methods")
    }

    func testFrench() {
        assertBlocked("Mot de passe")
        assertBlocked("Nom d’utilisateur")
        assertBlocked("Nom d'utilisateur")
        assertBlocked("Numéro de carte")
        assertBlocked("Numero de carte")          // accents optional
        assertBlocked("Téléphone portable")
        assertAllowed("Résumé de l’article")
    }

    func testGerman() {
        assertBlocked("Passwort")
        assertBlocked("Kennwort wiederholen")
        assertBlocked("PIN-Code")
        assertBlocked("Benutzername")
        assertBlocked("Geburtsdatum")
        assertAllowed("Zusammenfassung")
    }

    func testSpanish() {
        assertBlocked("Contraseña")
        assertBlocked("CONTRASENA")
        assertBlocked("Iniciar sesión")
        assertBlocked("Número de tarjeta")
        assertBlocked("Fecha de nacimiento")
        assertAllowed("Resumen del estudio")
    }

    func testPortuguese() {
        assertBlocked("Senha")
        assertBlocked("Nome de usuário")
        assertBlocked("Código de verificação")
        assertBlocked("Data de nascimento")
        assertAllowed("Resumo do artigo")
    }

    func testChineseMatchesAsSubstring() {
        assertBlocked("请输入密码")
        assertBlocked("手机号码")
        assertBlocked("验证码：")
        assertBlocked("用户名或邮箱")
        assertAllowed("研究摘要")
        assertAllowed("讨论")
    }

    func testHindiMatchesAsSubstring() {
        assertBlocked("अपना पासवर्ड डालें")
        assertBlocked("उपयोगकर्ता नाम")
        assertBlocked("जन्म तिथि")
        assertAllowed("सारांश")
    }

    func testMalay() {
        assertBlocked("Kata laluan")
        assertBlocked("Nombor kad")
        assertBlocked("Log masuk")
        assertBlocked("Cari")
        assertAllowed("Ringkasan kajian")
        assertAllowed("Caring for patients")     // "cari" only as a whole word
    }

    // MARK: Identifiers, ancestors, secure fields, roles, length

    func testCompoundIdentifiers() {
        XCTAssertEqual(gate.blockedTerm(inIdentifier: "newPasswordField"), "password")
        XCTAssertNotNil(gate.blockedTerm(inIdentifier: "txtusername"))
        XCTAssertNotNil(gate.blockedTerm(inIdentifier: "login_form_email"))
        XCTAssertNil(gate.blockedTerm(inIdentifier: "researchNotes"))
        XCTAssertNil(gate.blockedTerm(inIdentifier: "_NS:142"))
        XCTAssertFalse(gate.evaluate(field(ids: ["user-password-input"])).isEligible)
    }

    func testAncestorFormNamesCount() {
        var f = field()
        f.ancestorNames = ["Log in"]
        XCTAssertEqual(gate.evaluate(f), .ineligible(.blockedTerm("log in")))
    }

    func testSecureFieldsAreNeverEligible() {
        var f = field()
        f.isSecure = true
        XCTAssertEqual(gate.evaluate(f), .ineligible(.secureField))
        var g = field(role: "AXTextField")
        g.subrole = "AXSecureTextField"
        XCTAssertEqual(gate.evaluate(g), .ineligible(.secureField))
    }

    func testSearchSubroleAndUnsupportedRoles() {
        var f = field()
        f.subrole = "AXSearchField"
        XCTAssertFalse(gate.evaluate(f).isEligible)
        XCTAssertEqual(gate.evaluate(field(role: "AXTextField")), .ineligible(.unsupportedRole("AXTextField")))
        XCTAssertEqual(gate.evaluate(field(role: "AXButton")), .ineligible(.unsupportedRole("AXButton")))
        var ro = field()
        ro.isEditable = false
        XCTAssertEqual(gate.evaluate(ro), .ineligible(.notEditable))
    }

    func testLengthLimits() {
        XCTAssertEqual(gate.evaluate(field(count: 0)), .ineligible(.tooShort))
        XCTAssertEqual(gate.evaluate(field(count: 1_000_001)), .ineligible(.tooLong))
        XCTAssertTrue(gate.evaluate(field(count: nil)).isEligible)   // not read yet
        XCTAssertTrue(IneligibleReason.tooShort.dependsOnLength)
    }

    // MARK: Per-app rules

    func testDisabledApps() {
        for app in ["com.apple.Terminal", "com.googlecode.iterm2", "com.microsoft.VSCode",
                    "com.apple.dt.Xcode", "com.1password.1password", "com.apple.keychainaccess"] {
            let decision = gate.evaluate(field(app: app))
            guard case .ineligible(.appDisabled) = decision else {
                return XCTFail("\(app) should be disabled, got \(decision)")
            }
        }
    }

    func testEnabledAppsAndTheirRules() {
        for app in ["com.microsoft.Word", "com.apple.iWork.Pages", "com.apple.TextEdit", "com.apple.mail",
                    "com.apple.Notes", "com.apple.Safari", "com.google.Chrome", "org.mozilla.firefox",
                    "company.thebrowser.Browser", "com.tinyspeck.slackmacgap"] {
            XCTAssertTrue(gate.evaluate(field(app: app)).isEligible, app)
        }
        let apps = gate.appRules
        XCTAssertEqual(apps.rule(for: "com.google.Chrome").enhancedAccessibility, "AXEnhancedUserInterface")
        XCTAssertEqual(apps.rule(for: "com.tinyspeck.slackmacgap").enhancedAccessibility, "AXManualAccessibility")
        XCTAssertTrue(apps.rule(for: "com.tinyspeck.slackmacgap").isLowPriority)
        XCTAssertTrue(apps.rule(for: "com.microsoft.Word").needsPolling)
        XCTAssertEqual(apps.rule(for: "com.microsoft.Word").writeBack, [.accessibility, .paste, .typing])
        XCTAssertEqual(apps.rule(for: "org.mozilla.firefox").writeBack, [.paste, .typing])
        XCTAssertTrue(apps.rule(for: "com.apple.mail").roles.contains("AXWebArea"))
        XCTAssertFalse(apps.rule(for: "com.apple.TextEdit").roles.contains("AXWebArea"))
    }

    func testUnknownAppsGetDefaultsAndWildcardsMatch() {
        let apps = gate.appRules
        let unknown = apps.rule(for: "com.example.Writer")
        XCTAssertEqual(unknown, apps.defaults)
        XCTAssertTrue(unknown.enabled)
        XCTAssertEqual(unknown.writeBack, [.accessibility, .typing, .paste])
        XCTAssertFalse(apps.rule(for: "com.1password.browser-helper").enabled)   // "com.1password.*"
        XCTAssertEqual(apps.rule(for: nil), apps.defaults)
        XCTAssertFalse(apps.rule(for: "COM.APPLE.TERMINAL").enabled)              // case-insensitive
    }

    func testWidgetPlacementAndForbiddenCorners() {
        let slack = gate.appRules.rule(for: "com.tinyspeck.slackmacgap").widget
        XCTAssertEqual(slack.effectiveCorner, .topRight)
        let p = WidgetPlacement(corner: .bottomRight, forbiddenCorners: [.bottomRight, .bottomLeft])
        XCTAssertEqual(p.effectiveCorner, .topRight)
        let word = gate.appRules.rule(for: "com.microsoft.Word").widget
        XCTAssertEqual(word.offsetX, 22)
        XCTAssertEqual(word.offsetY, 10)
    }

    func testEntriesInheritDefaults() throws {
        let json = """
        {"defaults": {"roles": ["AXTextArea", "AXTextField"], "needs_polling": true},
         "apps": [{"bundle_ids": ["a.b"], "enabled": false}, {"bundle_ids": ["c.d"], "needs_polling": false}]}
        """
        let rules = try JSONDecoder().decode(AppRules.self, from: Data(json.utf8))
        XCTAssertEqual(rules.defaults.roles, ["AXTextArea", "AXTextField"])
        XCTAssertFalse(rules.rule(for: "a.b").enabled)
        XCTAssertTrue(rules.rule(for: "a.b").needsPolling)
        XCTAssertFalse(rules.rule(for: "c.d").needsPolling)
        XCTAssertEqual(rules.rule(for: "c.d").writeBack, [.accessibility, .typing, .paste])
    }

    func testRulesLocatorFindsTheCheckoutCopy() {
        let found = RulesLocator.findInCheckout(RulesLocator.fieldsFile, from: Repo.testsDir)
        XCTAssertEqual(found?.standardizedFileURL.path, Repo.fieldsJSON.standardizedFileURL.path)
    }
}
