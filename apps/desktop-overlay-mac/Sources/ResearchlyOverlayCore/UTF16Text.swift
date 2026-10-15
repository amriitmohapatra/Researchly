import Foundation

/// A half-open range in UTF-16 code units: `[location, location + length)`.
///
/// Everything the overlay exchanges counts in UTF-16: macOS Accessibility
/// (`CFRange` over `NSString`), the live-check contract (design note §5) and
/// Windows UI Automation. Swift `String` indices are never stored.
public struct UTF16Range: Hashable, Codable, CustomStringConvertible {
    public var location: Int
    public var length: Int

    public init(location: Int, length: Int) {
        precondition(location >= 0 && length >= 0, "UTF16Range must not be negative")
        self.location = location
        self.length = length
    }

    public init(begin: Int, end: Int) {
        self.init(location: begin, length: max(0, end - begin))
    }

    public var end: Int { location + length }
    public var isEmpty: Bool { length == 0 }

    public func shifted(by delta: Int) -> UTF16Range {
        UTF16Range(location: max(0, location + delta), length: length)
    }

    public func contains(_ offset: Int) -> Bool {
        offset >= location && offset < end
    }

    /// True when the ranges share at least one code unit. An empty range
    /// intersects a range that strictly contains its position.
    public func intersects(_ other: UTF16Range) -> Bool {
        if isEmpty { return other.location < location && location < other.end }
        if other.isEmpty { return location < other.location && other.location < end }
        return location < other.end && other.location < end
    }

    public func intersection(_ other: UTF16Range) -> UTF16Range? {
        let lo = max(location, other.location)
        let hi = min(end, other.end)
        return hi > lo ? UTF16Range(begin: lo, end: hi) : nil
    }

    /// The range limited to `[0, total)`; nil if nothing is left.
    public func clamped(toLength total: Int) -> UTF16Range? {
        let lo = min(max(0, location), total)
        let hi = min(max(0, end), total)
        return hi > lo ? UTF16Range(begin: lo, end: hi) : nil
    }

    public var description: String { "[\(location), \(end))" }
}

/// UTF-16 helpers on `String`, safe at surrogate pairs and grapheme clusters.
public enum UTF16Text {
    public static func length(_ s: String) -> Int { s.utf16.count }

    /// True if `offset` does not fall between the two halves of a surrogate
    /// pair. Offsets 0 and `length` are boundaries.
    public static func isScalarBoundary(_ s: String, _ offset: Int) -> Bool {
        let u = s.utf16
        guard offset >= 0, offset <= u.count else { return false }
        if offset == 0 || offset == u.count { return true }
        let i = u.index(u.startIndex, offsetBy: offset)
        return !UTF16.isTrailSurrogate(u[i])
    }

    /// The substring for a UTF-16 range, or nil when the range is out of
    /// bounds or would split a surrogate pair.
    public static func substring(_ s: String, _ r: UTF16Range) -> String? {
        let u = s.utf16
        guard r.location >= 0, r.end <= u.count,
              isScalarBoundary(s, r.location), isScalarBoundary(s, r.end) else { return nil }
        let a = u.index(u.startIndex, offsetBy: r.location)
        let b = u.index(a, offsetBy: r.length)
        guard let lo = a.samePosition(in: s.unicodeScalars),
              let hi = b.samePosition(in: s.unicodeScalars) else { return nil }
        return String(s.unicodeScalars[lo..<hi])
    }

    /// `s` with the UTF-16 range replaced, or nil if the range is invalid.
    public static func replacing(_ s: String, _ r: UTF16Range, with replacement: String) -> String? {
        guard let head = substring(s, UTF16Range(begin: 0, end: r.location)),
              let tail = substring(s, UTF16Range(begin: r.end, end: length(s))) else { return nil }
        return head + replacement + tail
    }

    /// UTF-16 offsets at which grapheme clusters (user-perceived characters)
    /// begin, plus the end offset. "e" + U+0301 is one cluster of 2 units; a
    /// flag emoji is one cluster of 4 units.
    public static func graphemeBoundaries(_ s: String) -> [Int] {
        var result: [Int] = [0]
        result.reserveCapacity(s.count + 1)
        var offset = 0
        for ch in s {
            offset += ch.utf16.count
            result.append(offset)
        }
        return result
    }

    /// Widen a range so it never cuts through a grapheme cluster: an
    /// underline that ends between a letter and its accent would be drawn
    /// under half a glyph, and a replacement there would orphan the mark.
    public static func snappedToGraphemes(_ s: String, _ r: UTF16Range) -> UTF16Range? {
        guard let clamped = r.clamped(toLength: length(s)) else { return nil }
        let bounds = graphemeBoundaries(s)
        var lo = 0
        var hi = bounds.last ?? 0
        for b in bounds {
            if b <= clamped.location { lo = b }
            if b >= clamped.end { hi = b; break }
        }
        return hi > lo ? UTF16Range(begin: lo, end: hi) : nil
    }
}

/// One paragraph of a field's text.
public struct Paragraph: Equatable {
    /// Position among all paragraphs of the snapshot (blank ones included).
    public let index: Int
    /// The paragraph's text range, excluding its separator.
    public let range: UTF16Range
    public let text: String

    public var isBlank: Bool {
        text.unicodeScalars.allSatisfy { CharacterSet.whitespacesAndNewlines.contains($0) }
    }
}

/// Splits text into paragraphs at hard breaks: LF, CR, CRLF and U+2029
/// (paragraph separator). U+2028 (line separator) and U+000B (a manual line
/// break in some word processors) stay inside the paragraph.
public enum ParagraphSplitter {
    public static func split(_ text: String) -> [Paragraph] {
        var paragraphs: [Paragraph] = []
        var start = 0
        var offset = 0
        var startIndex = text.utf16.startIndex
        let u = text.utf16
        var i = u.startIndex

        func emit(endIndex: String.UTF16View.Index, endOffset: Int) {
            let piece = String(u[startIndex..<endIndex]) ?? ""
            paragraphs.append(Paragraph(index: paragraphs.count,
                                        range: UTF16Range(begin: start, end: endOffset),
                                        text: piece))
        }

        while i != u.endIndex {
            let unit = u[i]
            if unit == 0x0A || unit == 0x0D || unit == 0x2029 {
                emit(endIndex: i, endOffset: offset)
                var next = u.index(after: i)
                var width = 1
                if unit == 0x0D, next != u.endIndex, u[next] == 0x0A {
                    next = u.index(after: next)
                    width = 2
                }
                offset += width
                i = next
                start = offset
                startIndex = i
                continue
            }
            offset += 1
            i = u.index(after: i)
        }
        emit(endIndex: u.endIndex, endOffset: offset)
        return paragraphs
    }
}
