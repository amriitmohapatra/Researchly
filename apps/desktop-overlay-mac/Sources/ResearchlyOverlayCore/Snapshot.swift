import Foundation

/// The text of one field at one moment, split into paragraphs. Held in
/// memory only, for as long as the field has focus (design note §2:
/// overlay clients keep nothing on disk but settings).
public struct TextSnapshot: Equatable {
    public let text: String
    public let paragraphs: [Paragraph]
    public let utf16Length: Int

    public init(_ text: String) {
        self.text = text
        self.paragraphs = ParagraphSplitter.split(text)
        self.utf16Length = text.utf16.count
    }

    /// The paragraph containing a UTF-16 offset (an offset on a separator
    /// belongs to the paragraph before it).
    public func paragraphIndex(containing offset: Int) -> Int? {
        guard !paragraphs.isEmpty else { return nil }
        var lo = 0
        var hi = paragraphs.count - 1
        while lo < hi {
            let mid = (lo + hi + 1) / 2
            if paragraphs[mid].range.location <= offset { lo = mid } else { hi = mid - 1 }
        }
        return lo
    }
}

/// Which paragraphs survived an edit unchanged, and which are new.
///
/// Typing changes one paragraph; pasting or deleting changes a run. The
/// common head and tail are matched first, then a longest-common-subsequence
/// pass over the middle (bounded, so a wholesale replacement of a long
/// document stays cheap: past the bound, the middle counts as changed).
public struct ParagraphDiff: Equatable {
    public struct Match: Equatable {
        public let old: Int
        public let new: Int
    }

    public var matches: [Match]
    /// Indices in the new list with no unchanged counterpart.
    public var inserted: [Int]
    /// Indices in the old list that did not survive.
    public var removed: [Int]

    public static let lcsCellLimit = 250_000

    public static func between(_ old: [String], _ new: [String]) -> ParagraphDiff {
        var head = 0
        while head < old.count, head < new.count, old[head] == new[head] { head += 1 }
        var tail = 0
        while tail < old.count - head, tail < new.count - head,
              old[old.count - 1 - tail] == new[new.count - 1 - tail] { tail += 1 }

        var matches: [Match] = (0..<head).map { Match(old: $0, new: $0) }
        let oldMid = Array(old[head..<(old.count - tail)])
        let newMid = Array(new[head..<(new.count - tail)])

        var midMatches: [Match] = []
        if !oldMid.isEmpty, !newMid.isEmpty, oldMid.count * newMid.count <= lcsCellLimit {
            midMatches = lcs(oldMid, newMid).map { Match(old: $0.old + head, new: $0.new + head) }
        }
        matches += midMatches
        matches += (0..<tail).map { Match(old: old.count - tail + $0, new: new.count - tail + $0) }

        let matchedOld = Set(matches.map { $0.old })
        let matchedNew = Set(matches.map { $0.new })
        return ParagraphDiff(
            matches: matches,
            inserted: (0..<new.count).filter { !matchedNew.contains($0) },
            removed: (0..<old.count).filter { !matchedOld.contains($0) }
        )
    }

    private static func lcs(_ a: [String], _ b: [String]) -> [Match] {
        let n = a.count, m = b.count
        // table[i][j] = LCS length of a[i...] and b[j...]
        var table = Array(repeating: Array(repeating: 0, count: m + 1), count: n + 1)
        for i in stride(from: n - 1, through: 0, by: -1) {
            for j in stride(from: m - 1, through: 0, by: -1) {
                table[i][j] = a[i] == b[j] ? table[i + 1][j + 1] + 1 : max(table[i + 1][j], table[i][j + 1])
            }
        }
        var out: [Match] = []
        var i = 0, j = 0
        while i < n, j < m {
            if a[i] == b[j] {
                out.append(Match(old: i, new: j)); i += 1; j += 1
            } else if table[i + 1][j] >= table[i][j + 1] {
                i += 1
            } else {
                j += 1
            }
        }
        return out
    }
}
