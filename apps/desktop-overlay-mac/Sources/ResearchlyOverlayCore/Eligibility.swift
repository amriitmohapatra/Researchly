import Foundation

// MARK: - fields.json (shared with the Windows client; schema owned there)

/// `packages/desktop-rules/fields.json`: the keyword blocklist and limits
/// every overlay client honours before reading a field.
public struct FieldRules: Decodable, Equatable {
    public var version: Int
    public var neverSecureFields: Bool
    /// Language code → terms.
    public var keywords: [String: [String]]
    /// Languages whose terms match as substrings (no word spaces in the script).
    public var scriptsMatchedAsSubstrings: [String]
    public var minFieldCharacters: Int
    public var maxFieldCharacters: Int

    private enum CodingKeys: String, CodingKey {
        case version
        case neverSecureFields = "never_secure_fields"
        case keywords
        case scriptsMatchedAsSubstrings = "scripts_matched_as_substrings"
        case minFieldCharacters = "min_field_characters"
        case maxFieldCharacters = "max_field_characters"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        version = c.lenient(Int.self, .version) ?? 1
        // Secure fields are refused whatever the file says; the key exists
        // so the file documents it.
        neverSecureFields = c.lenient(Bool.self, .neverSecureFields) ?? true
        keywords = try c.decode([String: [String]].self, forKey: .keywords)
        scriptsMatchedAsSubstrings = c.lenient([String].self, .scriptsMatchedAsSubstrings) ?? []
        minFieldCharacters = c.lenient(Int.self, .minFieldCharacters) ?? 1
        maxFieldCharacters = c.lenient(Int.self, .maxFieldCharacters) ?? 1_000_000
    }

    public static func load(from url: URL) throws -> FieldRules {
        try JSONDecoder().decode(FieldRules.self, from: Data(contentsOf: url))
    }
}

// MARK: - apps-mac.json (this client's per-app rules)

public enum WidgetCorner: String, Codable, CaseIterable {
    case topLeft = "top-left"
    case topRight = "top-right"
    case bottomLeft = "bottom-left"
    case bottomRight = "bottom-right"
}

public enum WriteBackMethod: String, Codable, CaseIterable {
    /// Select the range and set the selected text through Accessibility.
    case accessibility
    /// Select the range, then type the replacement as keyboard events.
    case typing
    /// Select the range, then paste the replacement (pasteboard restored).
    case paste
}

/// Where the field widget sits. Offsets are points inward from the corner.
public struct WidgetPlacement: Codable, Equatable {
    public var corner: WidgetCorner
    public var offsetX: Double
    public var offsetY: Double
    /// Corners where the host draws its own controls.
    public var forbiddenCorners: [WidgetCorner]

    public init(corner: WidgetCorner = .bottomRight, offsetX: Double = 6, offsetY: Double = 6,
                forbiddenCorners: [WidgetCorner] = []) {
        self.corner = corner
        self.offsetX = offsetX
        self.offsetY = offsetY
        self.forbiddenCorners = forbiddenCorners
    }

    private enum CodingKeys: String, CodingKey {
        case corner, offset
        case forbiddenCorners = "forbidden_corners"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        corner = try c.decodeIfPresent(WidgetCorner.self, forKey: .corner) ?? .bottomRight
        let offset = try c.decodeIfPresent([Double].self, forKey: .offset) ?? [6, 6]
        offsetX = offset.first ?? 6
        offsetY = offset.count > 1 ? offset[1] : offsetX
        forbiddenCorners = try c.decodeIfPresent([WidgetCorner].self, forKey: .forbiddenCorners) ?? []
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(corner, forKey: .corner)
        try c.encode([offsetX, offsetY], forKey: .offset)
        try c.encode(forbiddenCorners, forKey: .forbiddenCorners)
    }

    /// The corner actually used: the preferred one unless forbidden, else the
    /// first allowed in a fixed order (stable across releases, §1.9).
    public var effectiveCorner: WidgetCorner {
        if !forbiddenCorners.contains(corner) { return corner }
        let order: [WidgetCorner] = [.bottomRight, .bottomLeft, .topRight, .topLeft]
        return order.first { !forbiddenCorners.contains($0) } ?? corner
    }
}

/// A fully resolved per-app rule (defaults merged with the app's entry).
public struct AppRule: Equatable {
    public var name: String
    public var bundleIDs: [String]
    public var enabled: Bool
    /// "normal" or "low": a low-priority app is checked, with fewer
    /// paragraphs per request and a longer pause.
    public var priority: String
    /// Accessibility roles the client attaches to in this app.
    public var roles: [String]
    public var widget: WidgetPlacement
    public var writeBack: [WriteBackMethod]
    /// The app's notifications are unreliable: poll the field as well.
    public var needsPolling: Bool
    /// An attribute to set on the app element so it builds its full
    /// accessibility tree ("AXEnhancedUserInterface" for browsers,
    /// "AXManualAccessibility" for Electron apps), or nil.
    public var enhancedAccessibility: String?
    public var note: String?

    public var isLowPriority: Bool { priority == "low" }
}

/// One entry in apps-mac.json; every key but `bundle_ids` is optional and
/// falls back to `defaults`.
struct AppRuleEntry: Decodable {
    var name: String?
    var bundleIDs: [String]?
    var enabled: Bool?
    var priority: String?
    var roles: [String]?
    var widget: WidgetPlacement?
    var writeBack: [WriteBackMethod]?
    var needsPolling: Bool?
    var enhancedAccessibility: String?
    var note: String?

    private enum CodingKeys: String, CodingKey {
        case name
        case bundleIDs = "bundle_ids"
        case enabled, priority, roles, widget
        case writeBack = "write_back"
        case needsPolling = "needs_polling"
        case enhancedAccessibility = "enhanced_accessibility"
        case note
    }

    func merged(over base: AppRule) -> AppRule {
        AppRule(
            name: name ?? base.name,
            bundleIDs: bundleIDs ?? base.bundleIDs,
            enabled: enabled ?? base.enabled,
            priority: priority ?? base.priority,
            roles: roles ?? base.roles,
            widget: widget ?? base.widget,
            writeBack: writeBack ?? base.writeBack,
            needsPolling: needsPolling ?? base.needsPolling,
            enhancedAccessibility: enhancedAccessibility ?? base.enhancedAccessibility,
            note: note ?? base.note
        )
    }
}

/// `packages/desktop-rules/apps-mac.json`.
public struct AppRules: Decodable {
    public var version: Int
    public var defaults: AppRule
    public var apps: [AppRule]

    public static let builtInDefaults = AppRule(
        name: "Any other app", bundleIDs: [], enabled: true, priority: "normal",
        roles: ["AXTextArea"], widget: WidgetPlacement(),
        writeBack: [.accessibility, .typing, .paste], needsPolling: false,
        enhancedAccessibility: nil, note: nil)

    private enum CodingKeys: String, CodingKey { case version, defaults, apps }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        version = c.lenient(Int.self, .version) ?? 1
        let base = try c.decodeIfPresent(AppRuleEntry.self, forKey: .defaults)?
            .merged(over: AppRules.builtInDefaults) ?? AppRules.builtInDefaults
        defaults = base
        apps = try c.decodeIfPresent([AppRuleEntry].self, forKey: .apps)?
            .map { $0.merged(over: base) } ?? []
    }

    public init(defaults: AppRule = AppRules.builtInDefaults, apps: [AppRule] = []) {
        self.version = 1
        self.defaults = defaults
        self.apps = apps
    }

    public static func load(from url: URL) throws -> AppRules {
        try JSONDecoder().decode(AppRules.self, from: Data(contentsOf: url))
    }

    /// The rule for a bundle id: an exact match first, then the longest
    /// `prefix.*` pattern, then the defaults.
    public func rule(for bundleID: String?) -> AppRule {
        guard let id = bundleID?.lowercased(), !id.isEmpty else { return defaults }
        var best: (AppRule, Int)?
        for app in apps {
            for pattern in app.bundleIDs.map({ $0.lowercased() }) {
                if pattern == id { return app }
                if pattern.hasSuffix(".*") {
                    let prefix = String(pattern.dropLast(1))   // keep the dot
                    if id.hasPrefix(prefix), prefix.count > (best?.1 ?? -1) { best = (app, prefix.count) }
                }
            }
        }
        return best?.0 ?? defaults
    }
}

// MARK: - The gate

/// What the shell knows about a focused element, read without reading its
/// text. `characterCount` is nil until the static checks have passed (the
/// shell never asks a refused field for anything more).
public struct FieldDescriptor: Equatable {
    public var bundleID: String?
    public var role: String
    public var subrole: String?
    public var isSecure: Bool
    public var isEditable: Bool
    /// Title, description, placeholder, help, the linked label's text.
    public var labels: [String]
    /// Identifiers: AXIdentifier, DOM id and class names.
    public var identifiers: [String]
    /// Names of enclosing forms or search regions.
    public var ancestorNames: [String]
    public var characterCount: Int?

    public init(bundleID: String?, role: String, subrole: String? = nil, isSecure: Bool = false,
                isEditable: Bool = true, labels: [String] = [], identifiers: [String] = [],
                ancestorNames: [String] = [], characterCount: Int? = nil) {
        self.bundleID = bundleID
        self.role = role
        self.subrole = subrole
        self.isSecure = isSecure
        self.isEditable = isEditable
        self.labels = labels
        self.identifiers = identifiers
        self.ancestorNames = ancestorNames
        self.characterCount = characterCount
    }
}

public enum IneligibleReason: Equatable, CustomStringConvertible {
    case appDisabled(String)
    case secureField
    case notEditable
    case unsupportedRole(String)
    case blockedTerm(String)
    case tooShort
    case tooLong

    public var description: String {
        switch self {
        case .appDisabled(let app): return "Researchly is off in \(app)."
        case .secureField: return "Password fields are never read."
        case .notEditable: return "This text can’t be edited."
        case .unsupportedRole(let role): return "This kind of field (\(role)) isn’t supported here."
        case .blockedTerm(let term): return "The field’s label suggests private information (“\(term)”)."
        case .tooShort: return "The field is empty."
        case .tooLong: return "The text is too long to check live."
        }
    }

    /// Reasons that can change while the field keeps focus.
    public var dependsOnLength: Bool {
        self == .tooShort || self == .tooLong
    }
}

public enum EligibilityDecision: Equatable {
    case eligible(AppRule)
    case ineligible(IneligibleReason)

    public var isEligible: Bool {
        if case .eligible = self { return true }
        return false
    }
}

public struct EligibilityGate {
    public let fieldRules: FieldRules
    public let appRules: AppRules

    private let wordTerms: [(term: String, tokens: [String], compact: String)]
    private let substringTerms: [(term: String, folded: String)]

    /// Terms this long (letters only) also match inside compound
    /// identifiers such as `newPasswordField` or `txtusername`. Shorter ones
    /// would match innocently ("search" in "research").
    public static let compoundMinimumLength = 8

    public init(fieldRules: FieldRules, appRules: AppRules) {
        self.fieldRules = fieldRules
        self.appRules = appRules
        let substringLanguages = Set(fieldRules.scriptsMatchedAsSubstrings)
        var words: [(String, [String], String)] = []
        var subs: [(String, String)] = []
        for (language, terms) in fieldRules.keywords.sorted(by: { $0.key < $1.key }) {
            for term in terms {
                if substringLanguages.contains(language) {
                    subs.append((term, EligibilityGate.foldScript(term)))
                } else {
                    let tokens = EligibilityGate.tokens(term)
                    if !tokens.isEmpty { words.append((term, tokens, tokens.joined())) }
                }
            }
        }
        wordTerms = words
        substringTerms = subs
    }

    /// Static checks plus, when `characterCount` is known, the length limits.
    public func evaluate(_ field: FieldDescriptor) -> EligibilityDecision {
        let rule = appRules.rule(for: field.bundleID)
        if !rule.enabled { return .ineligible(.appDisabled(rule.name)) }
        if field.isSecure || field.subrole == "AXSecureTextField" || field.role == "AXSecureTextField" {
            return .ineligible(.secureField)
        }
        if !rule.roles.contains(field.role) { return .ineligible(.unsupportedRole(field.role)) }
        if field.subrole == "AXSearchField" { return .ineligible(.blockedTerm("search")) }
        if !field.isEditable { return .ineligible(.notEditable) }
        for label in field.labels + field.ancestorNames {
            if let term = blockedTerm(inLabel: label) { return .ineligible(.blockedTerm(term)) }
        }
        for identifier in field.identifiers {
            if let term = blockedTerm(inIdentifier: identifier) { return .ineligible(.blockedTerm(term)) }
        }
        if let count = field.characterCount {
            if count < fieldRules.minFieldCharacters { return .ineligible(.tooShort) }
            if count > fieldRules.maxFieldCharacters { return .ineligible(.tooLong) }
        }
        return .eligible(rule)
    }

    /// The first blocklisted term in a human-readable label, if any.
    public func blockedTerm(inLabel label: String) -> String? {
        let labelTokens = EligibilityGate.tokens(label)
        for entry in wordTerms where EligibilityGate.containsRun(labelTokens, entry.tokens) {
            return entry.term
        }
        let folded = EligibilityGate.foldScript(label)
        for entry in substringTerms where !entry.folded.isEmpty && folded.contains(entry.folded) {
            return entry.term
        }
        return nil
    }

    /// Like `blockedTerm(inLabel:)`, and long terms also match inside
    /// compound identifiers (`loginPasswordInput`, `txtusername`).
    public func blockedTerm(inIdentifier identifier: String) -> String? {
        if let term = blockedTerm(inLabel: identifier) { return term }
        let compact = EligibilityGate.tokens(identifier).joined()
        for entry in wordTerms where entry.compact.count >= EligibilityGate.compoundMinimumLength
            && compact.contains(entry.compact) {
            return entry.term
        }
        return nil
    }

    // MARK: Normalisation

    /// Lower-case, diacritic-free word tokens. camelCase and digits-to-
    /// letters transitions split words, so `userNameField` reads as
    /// "user name field"; every non-alphanumeric character is a break, so
    /// "sign-in", "sign_in" and "sign in" read alike.
    public static func tokens(_ s: String) -> [String] {
        var words: [String] = []
        var current = ""
        var previousWasLower = false
        for scalar in s.unicodeScalars {
            let isAlnum = CharacterSet.alphanumerics.contains(scalar)
            if !isAlnum {
                if !current.isEmpty { words.append(current); current = "" }
                previousWasLower = false
                continue
            }
            let isUpper = CharacterSet.uppercaseLetters.contains(scalar)
            if isUpper && previousWasLower && !current.isEmpty {
                words.append(current)
                current = ""
            }
            current.unicodeScalars.append(scalar)
            previousWasLower = CharacterSet.lowercaseLetters.contains(scalar)
        }
        if !current.isEmpty { words.append(current) }
        return words.map(foldLatin).filter { !$0.isEmpty }
    }

    static func foldLatin(_ s: String) -> String {
        s.folding(options: [.caseInsensitive, .diacriticInsensitive, .widthInsensitive], locale: nil)
            .lowercased()
    }

    /// Case-fold only: diacritic folding would strip Devanagari vowel signs.
    static func foldScript(_ s: String) -> String {
        s.lowercased()
    }

    static func containsRun(_ haystack: [String], _ needle: [String]) -> Bool {
        guard !needle.isEmpty, haystack.count >= needle.count else { return false }
        for start in 0...(haystack.count - needle.count)
            where haystack[start] == needle[0] && Array(haystack[start..<(start + needle.count)]) == needle {
            return true
        }
        return false
    }
}

// MARK: - Finding the rules files

public enum RulesLocator {
    public static let fieldsFile = "fields.json"
    public static let appsFile = "apps-mac.json"

    /// Looks for `packages/desktop-rules/<name>` in `start` and each of its
    /// parents (for `swift run` from a checkout; the built app reads its
    /// Resources folder instead).
    public static func findInCheckout(_ name: String, from start: URL) -> URL? {
        var dir = start.standardizedFileURL
        for _ in 0..<12 {
            let candidate = dir.appendingPathComponent("packages/desktop-rules/\(name)")
            if FileManager.default.fileExists(atPath: candidate.path) { return candidate }
            let parent = dir.deletingLastPathComponent()
            if parent.path == dir.path { break }
            dir = parent
        }
        return nil
    }
}
