import Foundation

/// Recognises a heading in plain text, so each paragraph can be sent with
/// the nearest heading above it (advice stays section-aware, CLAUDE.md #4).
/// Deliberately narrow: Markdown headings, and short lines that are a
/// research-paper section name, optionally numbered. Anything else is a
/// paragraph and gets checked.
public enum HeadingDetector {
    static let sectionNames: Set<String> = [
        "abstract", "summary", "introduction", "background", "literature review", "related work",
        "aims", "objectives", "aims and objectives", "hypotheses",
        "methods", "method", "methodology", "materials and methods", "methods and materials",
        "study design", "data", "data and methods", "statistical analysis", "analysis",
        "results", "findings", "results and discussion", "discussion", "limitations",
        "strengths and limitations", "conclusion", "conclusions", "implications",
        "future work", "recommendations", "acknowledgements", "acknowledgments",
        "references", "bibliography", "appendix", "supplementary material",
        "supplementary information", "declarations", "funding", "ethics",
    ]

    /// The heading's text without Markdown marks or numbering, or nil if the
    /// paragraph is not a heading.
    public static func headingText(_ paragraph: String) -> String? {
        let trimmed = paragraph.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty, trimmed.utf16.count <= 120 else { return nil }
        if trimmed.hasPrefix("#") {
            let body = trimmed.drop(while: { $0 == "#" })
            let hashes = trimmed.count - body.count
            if hashes <= 6, body.first == " " {
                let text = body.trimmingCharacters(in: .whitespaces)
                return text.isEmpty ? nil : text
            }
            return nil
        }
        var text = trimmed
        // "2.", "2.1", "2.1.3", "IV.", "A." numbering
        if let match = text.range(of: #"^(\d+(\.\d+)*\.?|[IVXLC]+\.|[A-Z]\.)\s+"#, options: .regularExpression) {
            text = String(text[match.upperBound...])
        }
        if text.hasSuffix(":") { text.removeLast() }
        let key = text.trimmingCharacters(in: .whitespaces).lowercased()
            .replacingOccurrences(of: "&", with: "and")
        if sectionNames.contains(key) { return text.trimmingCharacters(in: .whitespaces) }
        if key.range(of: #"^(chapter|section|appendix)\s+[0-9ivxlc]+\b"#, options: .regularExpression) != nil,
           key.split(separator: " ").count <= 10, !key.hasSuffix(".") {
            return text.trimmingCharacters(in: .whitespaces)
        }
        return nil
    }
}

/// A paragraph as the live check sees it.
public struct TrackedParagraph: Equatable {
    public enum Status: Equatable {
        /// Waiting to be checked.
        case pending
        /// Sent with this revision; no reply yet.
        case inFlight(Int)
        /// Checked; `suggestions` are current for `text`.
        case checked
        /// Never sent: blank, or a heading.
        case skipped
    }

    /// Stable while the paragraph's text is unchanged; a changed paragraph
    /// gets a new id, so a reply about its old text can never land on it.
    public let id: String
    public let text: String
    public var range: UTF16Range
    public var heading: String?
    public var isHeading: Bool
    public var status: Status
    /// The heading the paragraph was sent with (its section when checked).
    public var checkedHeading: String?
    public var suggestions: [PlacedSuggestion]
}

/// A suggestion placed in the field: its range counts from the start of the
/// field's text, and `flaggedText` is what it covered when it arrived (a
/// write-back first checks that the field still says that).
public struct PlacedSuggestion: Equatable {
    public let suggestion: LiveSuggestion
    public let paragraphID: String
    /// Range within the paragraph (UTF-16).
    public let localRange: UTF16Range
    /// Range within the whole field (UTF-16).
    public var range: UTF16Range
    public let flaggedText: String

    public var id: String { suggestion.id }
    public var category: Category { suggestion.category }
}

/// Every paragraph of the focused field with its check status and results.
public struct ParagraphLedger {
    public private(set) var snapshot = TextSnapshot("")
    public private(set) var paragraphs: [TrackedParagraph] = []
    private var nextID = 1
    private let idPrefix: String

    public init(idPrefix: String = "p") {
        self.idPrefix = idPrefix
    }

    /// Takes a new snapshot. Paragraphs whose text is unchanged keep their
    /// id, status and suggestions (moved to their new offsets); changed and
    /// new ones become pending. Returns true if anything changed.
    @discardableResult
    public mutating func update(_ text: String) -> Bool {
        if text == snapshot.text, !paragraphs.isEmpty { return false }
        let next = TextSnapshot(text)
        let diff = ParagraphDiff.between(paragraphs.map { $0.text }, next.paragraphs.map { $0.text })
        var carried: [Int: TrackedParagraph] = [:]
        for m in diff.matches { carried[m.new] = paragraphs[m.old] }

        var result: [TrackedParagraph] = []
        result.reserveCapacity(next.paragraphs.count)
        var currentHeading: String?
        for p in next.paragraphs {
            let headingText = HeadingDetector.headingText(p.text)
            let isHeading = headingText != nil
            if var old = carried[p.index] {
                let delta = p.range.location - old.range.location
                old.range = p.range
                old.heading = currentHeading
                old.isHeading = isHeading
                old.suggestions = old.suggestions.map { s in
                    var moved = s
                    moved.range = s.range.shifted(by: delta)
                    return moved
                }
                if old.status != .pending, old.status != .skipped, old.checkedHeading != currentHeading {
                    // Same words under a different section: the advice may differ.
                    old.status = .pending
                    old.suggestions = []
                }
                if isHeading || p.isBlank {
                    old.status = .skipped
                    old.suggestions = []
                }
                result.append(old)
            } else {
                let id = "\(idPrefix)\(nextID)"
                nextID += 1
                result.append(TrackedParagraph(
                    id: id, text: p.text, range: p.range, heading: currentHeading,
                    isHeading: isHeading, status: (isHeading || p.isBlank) ? .skipped : .pending,
                    checkedHeading: nil, suggestions: []))
            }
            if let h = headingText { currentHeading = h }
        }
        paragraphs = result
        snapshot = next
        return true
    }

    public var hasPending: Bool {
        paragraphs.contains { $0.status == .pending }
    }

    public var hasPendingOrInFlight: Bool {
        paragraphs.contains {
            if case .inFlight = $0.status { return true }
            return $0.status == .pending
        }
    }

    /// The next batch to send: visible paragraphs first, then the nearest to
    /// the caret; at most `maxCount` paragraphs and about `maxCharacters`
    /// UTF-16 units (a single longer paragraph is still sent on its own).
    public func nextBatch(caret: Int?, visible: UTF16Range?, maxCount: Int, maxCharacters: Int) -> [TrackedParagraph] {
        let pending = paragraphs.enumerated().filter { $0.element.status == .pending }
        guard !pending.isEmpty else { return [] }
        let caretIndex = caret.flatMap { snapshot.paragraphIndex(containing: $0) } ?? 0
        let ordered = pending.sorted { a, b in
            let av = visible.map { a.element.range.intersects($0) || $0.contains(a.element.range.location) } ?? false
            let bv = visible.map { b.element.range.intersects($0) || $0.contains(b.element.range.location) } ?? false
            if av != bv { return av }
            let da = abs(a.offset - caretIndex), db = abs(b.offset - caretIndex)
            if da != db { return da < db }
            return a.offset < b.offset
        }
        var batch: [TrackedParagraph] = []
        var characters = 0
        for (_, p) in ordered {
            if batch.count >= maxCount { break }
            let size = p.range.length
            if !batch.isEmpty, characters + size > maxCharacters { continue }
            batch.append(p)
            characters += size
        }
        return batch
    }

    public mutating func markInFlight(_ ids: [String], revision: Int) {
        let set = Set(ids)
        for i in paragraphs.indices where set.contains(paragraphs[i].id) && paragraphs[i].status == .pending {
            paragraphs[i].status = .inFlight(revision)
            paragraphs[i].checkedHeading = paragraphs[i].heading
        }
    }

    /// A request failed or was dropped: its paragraphs wait again.
    public mutating func revertInFlight(revision: Int) {
        for i in paragraphs.indices where paragraphs[i].status == .inFlight(revision) {
            paragraphs[i].status = .pending
        }
    }

    /// Applies a reply. Only paragraphs still in flight under `revision`
    /// take results: a paragraph edited since was given a new id, so stale
    /// advice about its old words is dropped. Paragraphs of the request that
    /// the reply leaves out count as checked with nothing to show.
    /// Suggestions whose range does not fit the paragraph are discarded.
    /// Returns how many paragraphs took results.
    @discardableResult
    public mutating func apply(_ results: [ParagraphResult], revision: Int) -> Int {
        var byID: [String: ParagraphResult] = [:]
        for r in results { byID[r.id] = r }
        var applied = 0
        for i in paragraphs.indices where paragraphs[i].status == .inFlight(revision) {
            let p = paragraphs[i]
            let incoming = byID[p.id]?.suggestions ?? []
            paragraphs[i].suggestions = incoming.compactMap { ParagraphLedger.place($0, in: p) }
            paragraphs[i].status = .checked
            applied += 1
        }
        return applied
    }

    static func place(_ s: LiveSuggestion, in p: TrackedParagraph) -> PlacedSuggestion? {
        guard s.begin >= 0, s.end >= s.begin, s.end <= p.text.utf16.count,
              UTF16Text.isScalarBoundary(p.text, s.begin), UTF16Text.isScalarBoundary(p.text, s.end) else {
            return nil
        }
        var local = UTF16Range(begin: s.begin, end: s.end)
        if !local.isEmpty, let snapped = UTF16Text.snappedToGraphemes(p.text, local) { local = snapped }
        guard let flagged = UTF16Text.substring(p.text, local) else { return nil }
        return PlacedSuggestion(suggestion: s, paragraphID: p.id, localRange: local,
                                range: local.shifted(by: p.range.location), flaggedText: flagged)
    }

    public var allSuggestions: [PlacedSuggestion] {
        paragraphs.flatMap { $0.suggestions }
    }
}
