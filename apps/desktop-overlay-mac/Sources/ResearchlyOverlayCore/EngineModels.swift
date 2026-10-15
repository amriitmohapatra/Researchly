import Foundation

/// The four suggestion types (CLAUDE.md #3). A Convention is never painted
/// as an error; Preferences stay hidden unless the writer switches them on.
/// An unknown value from a newer engine is kept, not rejected.
public enum Category: Hashable, Codable, CustomStringConvertible {
    case correction, improvement, convention, preference
    case other(String)

    public init(rawValue: String) {
        switch rawValue.lowercased() {
        case "correction": self = .correction
        case "improvement": self = .improvement
        case "convention": self = .convention
        case "preference": self = .preference
        default: self = .other(rawValue)
        }
    }

    public var rawValue: String {
        switch self {
        case .correction: return "correction"
        case .improvement: return "improvement"
        case .convention: return "convention"
        case .preference: return "preference"
        case .other(let raw): return raw
        }
    }

    public init(from decoder: Decoder) throws {
        self.init(rawValue: try decoder.singleValueContainer().decode(String.self))
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        try c.encode(rawValue)
    }

    public var description: String { rawValue }
}

// MARK: - Request

/// One paragraph sent for a live check.
public struct ParagraphPayload: Codable, Equatable {
    public var id: String
    public var text: String
    /// A paragraph style name, when the host exposes one.
    public var style: String?
    /// The text of the nearest heading above, so advice stays section-aware.
    public var heading: String?

    public init(id: String, text: String, style: String? = nil, heading: String? = nil) {
        self.id = id
        self.text = text
        self.style = style
        self.heading = heading
    }

    private enum CodingKeys: String, CodingKey { case id, text, style, heading }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id, forKey: .id)
        try c.encode(text, forKey: .text)
        try c.encodeIfPresent(style, forKey: .style)
        try c.encodeIfPresent(heading, forKey: .heading)
    }
}

/// The usual check options (a subset of the engine's `AnalyzeOptions`).
/// Omitted values mean "the engine's default".
public struct CheckOptions: Codable, Equatable {
    public var showPreferences: Bool
    public var spelling: String?

    public init(showPreferences: Bool = false, spelling: String? = nil) {
        self.showPreferences = showPreferences
        self.spelling = spelling
    }

    private enum CodingKeys: String, CodingKey {
        case showPreferences = "show_preferences"
        case spelling
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(showPreferences, forKey: .showPreferences)
        try c.encodeIfPresent(spelling, forKey: .spelling)
    }
}

/// The engine's limits for one live check (services/engine schemas.py
/// `MAX_LIVE_*`; packages/contract). A request over them is refused with
/// 422, so the client never sends one.
public enum LiveLimits {
    public static let maxParagraphs = 50
    /// Characters (Unicode scalars, as the engine counts) of all the
    /// paragraphs together, and so of any one paragraph.
    public static let maxCharacters = 20_000
    public static let maxHeadingCharacters = 300

    /// Characters as the engine counts them (code points, not UTF-16 units).
    public static func characters(_ text: String) -> Int { text.unicodeScalars.count }
}

/// `POST /v1/check-paragraphs` request (design note §5).
public struct CheckRequest: Codable, Equatable {
    public var revision: Int
    public var paragraphs: [ParagraphPayload]
    public var options: CheckOptions

    public init(revision: Int, paragraphs: [ParagraphPayload], options: CheckOptions) {
        self.revision = revision
        self.paragraphs = paragraphs
        self.options = options
    }
}

// MARK: - Response (decoded tolerantly)

/// One suggestion of a live-check reply, as `POST /v1/check-paragraphs`
/// sends it (services/engine schemas.py `LiveSuggestion`; the shared
/// fixtures in packages/contract/fixtures/check-paragraphs). `begin`/`end`
/// are UTF-16 offsets within the paragraph and `text` is the flagged words
/// at that range. Only `begin` and `end` are required; every other field
/// has a default and unknown fields are ignored, so a newer or older
/// engine does not break this client.
public struct LiveSuggestion: Decodable, Equatable {
    /// Opaque and stable (16 hex digits from the engine).
    public var id: String
    public var begin: Int
    public var end: Int
    public var category: Category
    public var critical: Bool
    public var message: String
    public var plain: String
    public var why: String
    public var source: String
    public var replacements: [String]
    /// The section the advice assumed ("methods", "unknown", …).
    public var section: String
    public var fixSafety: String
    /// For actions and tests only: never shown to the writer.
    public var ruleID: String?
    /// The rule's internal name ("doubled-word"): a code too, never shown.
    public var ruleName: String?
    /// spelling | grammar | gec | craft | lens
    public var tier: String?
    /// The flagged words. When present, a suggestion is placed only if the
    /// paragraph still says exactly this at `begin..<end`, and a revision is
    /// written back only if the field still does.
    public var text: String
    /// The Learn card (`GET /v1/learn/{id}`), when there is one.
    public var learnRef: String?

    public init(id: String, begin: Int, end: Int, category: Category, critical: Bool? = nil,
                message: String = "", plain: String = "", why: String = "", source: String = "",
                replacements: [String] = [], section: String = "", fixSafety: String = "review",
                ruleID: String? = nil, ruleName: String? = nil, tier: String? = nil,
                text: String = "", learnRef: String? = nil) {
        self.id = id
        self.begin = begin
        self.end = end
        self.category = category
        self.critical = critical ?? (category == .correction)
        self.message = message
        self.plain = plain
        self.why = why
        self.source = source
        self.replacements = replacements
        self.section = section
        self.fixSafety = fixSafety
        self.ruleID = ruleID
        self.ruleName = ruleName
        self.tier = tier
        self.text = text
        self.learnRef = learnRef
    }

    private enum CodingKeys: String, CodingKey {
        case id, begin, end, category, critical, message, plain, why, source
        case replacements, replacement, section, tier, text
        case fixSafety = "fix_safety"
        case ruleID = "rule_id"
        case ruleName = "rule_name"
        case learnRef = "learn_ref"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let begin = try c.decode(Int.self, forKey: .begin)
        let end = try c.decode(Int.self, forKey: .end)
        let category = c.lenient(Category.self, .category) ?? .improvement
        var replacements = c.lenient([String].self, .replacements) ?? []
        if replacements.isEmpty, let single = c.lenient(String.self, .replacement) {
            replacements = [single]
        }
        let ruleID = c.lenient(String.self, .ruleID)
        let fallbackID = "\(ruleID ?? category.rawValue):\(begin)-\(end)"
        self.init(
            id: c.lenient(String.self, .id) ?? fallbackID,
            begin: begin,
            end: end,
            category: category,
            critical: c.lenient(Bool.self, .critical),
            message: c.lenient(String.self, .message) ?? "",
            plain: c.lenient(String.self, .plain) ?? "",
            why: c.lenient(String.self, .why) ?? "",
            source: c.lenient(String.self, .source) ?? "",
            replacements: replacements,
            section: c.lenient(String.self, .section) ?? "",
            fixSafety: c.lenient(String.self, .fixSafety) ?? "review",
            ruleID: ruleID,
            ruleName: c.lenient(String.self, .ruleName),
            tier: c.lenient(String.self, .tier),
            text: c.lenient(String.self, .text) ?? "",
            learnRef: c.lenient(String.self, .learnRef)
        )
    }

    /// The section as the writer reads it ("Methods"), or nil when the
    /// advice assumed none ("unknown", "body"), as on the website's cards.
    public var sectionLabel: String? { SectionNames.label(section) }
}

/// Section ids the engine sends, in the writer's words (the website's
/// `sectionLabel`, apps/web/lib/categories.ts).
public enum SectionNames {
    static let names: [String: String] = [
        "abstract": "Abstract", "introduction": "Introduction", "methods": "Methods",
        "results": "Results", "limitations": "Limitations", "discussion": "Discussion",
        "conclusion": "Conclusion", "appendix": "Appendix",
    ]

    public static func label(_ section: String) -> String? {
        let s = section.trimmingCharacters(in: .whitespaces)
        if s.isEmpty || s == "unknown" || s == "body" { return nil }
        if let known = names[s] { return known }
        return s.prefix(1).uppercased() + s.dropFirst()
    }
}

extension KeyedDecodingContainer {
    /// The value if present and well-typed; nil if absent, null or malformed.
    func lenient<T: Decodable>(_ type: T.Type, _ key: Key) -> T? {
        (try? decodeIfPresent(type, forKey: key)) ?? nil
    }
}

/// Decodes an element if it can, else nil: one malformed suggestion must not
/// cost the writer every other underline in the reply.
struct Lossy<T: Decodable>: Decodable {
    let value: T?
    init(from decoder: Decoder) throws {
        value = try? T(from: decoder)
    }
}

public struct ParagraphResult: Decodable, Equatable {
    public var id: String
    /// The section the paragraph was checked as ("" from an engine that
    /// does not say).
    public var section: String
    public var suggestions: [LiveSuggestion]

    public init(id: String, section: String = "", suggestions: [LiveSuggestion]) {
        self.id = id
        self.section = section
        self.suggestions = suggestions
    }

    private enum CodingKeys: String, CodingKey { case id, section, suggestions }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        section = c.lenient(String.self, .section) ?? ""
        let items = (try? c.decodeIfPresent([Lossy<LiveSuggestion>].self, forKey: .suggestions)) ?? nil
        suggestions = (items ?? []).compactMap { $0.value }
    }
}

/// Any JSON value. Used for `health`, whose shape the client only inspects.
public indirect enum JSONValue: Decodable, Equatable {
    case null
    case bool(Bool)
    case number(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let b = try? c.decode(Bool.self) { self = .bool(b) }
        else if let n = try? c.decode(Double.self) { self = .number(n) }
        else if let s = try? c.decode(String.self) { self = .string(s) }
        else if let a = try? c.decode([JSONValue].self) { self = .array(a) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }

    public subscript(key: String) -> JSONValue? {
        if case .object(let o) = self { return o[key] }
        return nil
    }

    public var stringValue: String? {
        if case .string(let s) = self { return s }
        return nil
    }

    public var boolValue: Bool? {
        if case .bool(let b) = self { return b }
        return nil
    }

    public var arrayValue: [JSONValue]? {
        if case .array(let a) = self { return a }
        return nil
    }
}

/// One entry of `health`: `{tier, label, ok, state, detail, remedy}`.
public struct TierHealth: Equatable {
    public var tier: String
    public var label: String
    public var ok: Bool
    /// ready | missing | disabled | error | unstarted
    public var state: String
    public var detail: String
    public var remedy: String

    public init(tier: String, label: String, ok: Bool, state: String, detail: String = "", remedy: String = "") {
        self.tier = tier
        self.label = label
        self.ok = ok
        self.state = state
        self.detail = detail
        self.remedy = remedy
    }

    init?(json: JSONValue) {
        guard case .object = json else { return nil }
        let tier = json["tier"]?.stringValue ?? ""
        self.init(tier: tier,
                  label: json["label"]?.stringValue ?? (tier.isEmpty ? "A check" : tier),
                  ok: json["ok"]?.boolValue ?? true,
                  state: json["state"]?.stringValue ?? "",
                  detail: json["detail"]?.stringValue ?? "",
                  remedy: json["remedy"]?.stringValue ?? "")
    }

    /// Not contributing, and not by choice: an outage the writer must be
    /// told about. A tier switched off (`disabled`) is not one, nor the
    /// opt-in learned tier without a model (as the engine's own
    /// `is_degraded`, services/engine engine_adapter.py).
    public var isOutage: Bool {
        if ok || state == "disabled" { return false }
        if tier == "gec", state == "missing" { return false }
        return true
    }
}

/// What the client needs from `health` and `state`: is a tier down, and why.
public struct HealthSummary: Equatable {
    public var degraded: Bool
    /// Labels of tiers that are down, e.g. "Grammar".
    public var downTiers: [String]
    /// The first remedy or detail the engine offered for them, if any.
    public var detail: String?

    public static let ok = HealthSummary(degraded: false, downTiers: [], detail: nil)

    /// Reads `health` as the engine sends it (a list of tiers) or as the
    /// health route does (`{status, tiers}`). The reply's `state` decides
    /// when present: "partial" is degraded, "ok" is not, whatever the
    /// tiers say. Without it, a tier that is down and not switched off
    /// makes the reply degraded.
    public init(json: JSONValue?, state: String?) {
        var tiers: [TierHealth] = []
        var statusDegraded = false
        if let json = json {
            if let list = json.arrayValue { tiers = list.compactMap(TierHealth.init(json:)) }
            if let list = json["tiers"]?.arrayValue { tiers = list.compactMap(TierHealth.init(json:)) }
            if json["status"]?.stringValue == "degraded" { statusDegraded = true }
        }
        let down = tiers.filter { $0.isOutage }
        downTiers = down.map { $0.label }
        detail = down.lazy.compactMap { t -> String? in
            if !t.remedy.isEmpty { return t.remedy }
            return t.detail.isEmpty ? nil : t.detail
        }.first
        switch state {
        case "partial": degraded = true
        case "ok": degraded = false
        default: degraded = statusDegraded || !down.isEmpty
        }
        if !degraded {
            downTiers = []
            detail = nil
        }
    }

    public init(degraded: Bool, downTiers: [String], detail: String?) {
        self.degraded = degraded
        self.downTiers = downTiers
        self.detail = detail
    }

    /// One line for the widget's hover text.
    public var reason: String? {
        guard degraded else { return nil }
        if downTiers.isEmpty { return "Part of the check is unavailable right now." }
        let names = downTiers.joined(separator: ", ")
        if let d = detail { return "\(names) unavailable right now. \(d)" }
        return "\(names) unavailable right now."
    }
}

/// `POST /v1/check-paragraphs` response: `{schema_version, revision,
/// paragraphs, state, health, hidden_preferences, signed_in,
/// assessed_rules, ruleset, elapsed_ms}`. Only `paragraphs` is required.
public struct CheckResponse: Decodable, Equatable {
    public var revision: Int?
    public var paragraphs: [ParagraphResult]
    public var health: HealthSummary
    /// "ok" or "partial" (nil from an engine that does not say).
    public var state: String?
    public var schemaVersion: String?
    /// Preference-type findings held back because they are hidden.
    public var hiddenPreferences: Int
    public var signedIn: Bool
    public var ruleset: String?

    public init(revision: Int?, paragraphs: [ParagraphResult], health: HealthSummary = .ok,
                state: String? = nil, schemaVersion: String? = nil, hiddenPreferences: Int = 0,
                signedIn: Bool = false, ruleset: String? = nil) {
        self.revision = revision
        self.paragraphs = paragraphs
        self.health = health
        self.state = state
        self.schemaVersion = schemaVersion
        self.hiddenPreferences = hiddenPreferences
        self.signedIn = signedIn
        self.ruleset = ruleset
    }

    private enum CodingKeys: String, CodingKey {
        case revision, paragraphs, health, state, ruleset
        case schemaVersion = "schema_version"
        case hiddenPreferences = "hidden_preferences"
        case signedIn = "signed_in"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        revision = c.lenient(Int.self, .revision)
        let items = try c.decode([Lossy<ParagraphResult>].self, forKey: .paragraphs)
        paragraphs = items.compactMap { $0.value }
        state = c.lenient(String.self, .state)
        health = HealthSummary(json: c.lenient(JSONValue.self, .health), state: state)
        schemaVersion = c.lenient(String.self, .schemaVersion)
        hiddenPreferences = max(0, c.lenient(Int.self, .hiddenPreferences) ?? 0)
        signedIn = c.lenient(Bool.self, .signedIn) ?? false
        ruleset = c.lenient(String.self, .ruleset)
    }
}
