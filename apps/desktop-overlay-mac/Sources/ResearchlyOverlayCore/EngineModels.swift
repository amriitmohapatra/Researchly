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

/// One suggestion of a live-check reply. `begin`/`end` are UTF-16 offsets
/// within the paragraph. Only `begin`, `end` and a category are required;
/// every other field has a default, and unknown fields are ignored, so a
/// newer engine does not break an older client.
public struct LiveSuggestion: Decodable, Equatable {
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
    public var section: String
    public var fixSafety: String
    public var ruleID: String?

    public init(id: String, begin: Int, end: Int, category: Category, critical: Bool? = nil,
                message: String = "", plain: String = "", why: String = "", source: String = "",
                replacements: [String] = [], section: String = "", fixSafety: String = "review",
                ruleID: String? = nil) {
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
    }

    private enum CodingKeys: String, CodingKey {
        case id, begin, end, category, critical, message, plain, why, source
        case replacements, replacement, section
        case fixSafety = "fix_safety"
        case ruleID = "rule_id"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let begin = try c.decode(Int.self, forKey: .begin)
        let end = try c.decode(Int.self, forKey: .end)
        let category = try c.decodeIfPresent(Category.self, forKey: .category) ?? .improvement
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
            ruleID: ruleID
        )
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
    public var suggestions: [LiveSuggestion]

    public init(id: String, suggestions: [LiveSuggestion]) {
        self.id = id
        self.suggestions = suggestions
    }

    private enum CodingKeys: String, CodingKey { case id, suggestions }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
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

/// What the client needs from `health`: is a tier down, and why.
public struct HealthSummary: Equatable {
    public var degraded: Bool
    /// Labels of tiers that are not contributing, e.g. "Grammar".
    public var downTiers: [String]
    /// The first remedy or detail the engine offered, if any.
    public var detail: String?

    public static let ok = HealthSummary(degraded: false, downTiers: [], detail: nil)

    /// Accepts the engine's `HealthResponse` object (`status`, `tiers`), a
    /// bare array of tiers, or anything else (treated as healthy).
    public init(json: JSONValue?, state: String?) {
        var tiers: [JSONValue] = []
        var statusDegraded = false
        if let json = json {
            if let list = json.arrayValue { tiers = list }
            if let list = json["tiers"]?.arrayValue { tiers = list }
            if json["status"]?.stringValue == "degraded" { statusDegraded = true }
            if json["ok"]?.boolValue == false { statusDegraded = true }
        }
        var down: [String] = []
        var detail: String?
        for tier in tiers where tier["ok"]?.boolValue == false {
            let label = tier["label"]?.stringValue ?? tier["tier"]?.stringValue ?? "A check"
            down.append(label)
            if detail == nil {
                let remedy = tier["remedy"]?.stringValue ?? ""
                let text = tier["detail"]?.stringValue ?? ""
                detail = !remedy.isEmpty ? remedy : (!text.isEmpty ? text : nil)
            }
        }
        self.downTiers = down
        self.detail = detail
        self.degraded = statusDegraded || !down.isEmpty || state == "partial"
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
        return "\(downTiers.joined(separator: ", ")) unavailable right now."
    }
}

/// `POST /v1/check-paragraphs` response (design note §5).
public struct CheckResponse: Decodable, Equatable {
    public var revision: Int?
    public var paragraphs: [ParagraphResult]
    public var health: HealthSummary
    public var state: String?

    public init(revision: Int?, paragraphs: [ParagraphResult], health: HealthSummary = .ok, state: String? = nil) {
        self.revision = revision
        self.paragraphs = paragraphs
        self.health = health
        self.state = state
    }

    private enum CodingKeys: String, CodingKey { case revision, paragraphs, health, state }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        revision = c.lenient(Int.self, .revision)
        let items = try c.decode([Lossy<ParagraphResult>].self, forKey: .paragraphs)
        paragraphs = items.compactMap { $0.value }
        state = c.lenient(String.self, .state)
        let healthJSON = c.lenient(JSONValue.self, .health)
        health = HealthSummary(json: healthJSON, state: state)
    }
}
