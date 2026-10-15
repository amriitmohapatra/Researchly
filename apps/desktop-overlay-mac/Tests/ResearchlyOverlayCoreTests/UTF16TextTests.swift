import XCTest
@testable import ResearchlyOverlayCore

final class UTF16TextTests: XCTestCase {
    // "é" written as e + U+0301 (2 units), a thumbs-up with a skin tone
    // (4 units, one grapheme), a flag (4 units), and a CJK character (1 unit).
    let combining = "Cafe\u{0301} au lait"
    let emoji = "Good \u{1F44D}\u{1F3FD} work"
    let flag = "Data from \u{1F1F8}\u{1F1EC} only"

    func testLengthsCountUTF16Units() {
        XCTAssertEqual(UTF16Text.length("abc"), 3)
        XCTAssertEqual(UTF16Text.length(combining), 13)
        XCTAssertEqual(UTF16Text.length("\u{1F44D}"), 2)
        XCTAssertEqual(UTF16Text.length(emoji), 5 + 4 + 5)
        XCTAssertEqual(UTF16Text.length("研究"), 2)
    }

    func testSubstringAfterEmojiUsesUTF16Offsets() {
        // "work" starts after "Good " (5) + emoji (4) + space (1) = 10.
        XCTAssertEqual(UTF16Text.substring(emoji, UTF16Range(location: 10, length: 4)), "work")
        XCTAssertEqual(UTF16Text.substring(emoji, UTF16Range(location: 5, length: 4)), "\u{1F44D}\u{1F3FD}")
    }

    func testSubstringRefusesToSplitASurrogatePair() {
        XCTAssertNil(UTF16Text.substring(emoji, UTF16Range(location: 6, length: 2)))
        XCTAssertFalse(UTF16Text.isScalarBoundary(emoji, 6))
        XCTAssertTrue(UTF16Text.isScalarBoundary(emoji, 7))
        XCTAssertNil(UTF16Text.substring(emoji, UTF16Range(location: 10, length: 99)))
    }

    func testSnapToGraphemesWidensAcrossCombiningMarks() {
        // [0, 4) ends between "e" and its accent: widened to include it.
        let snapped = UTF16Text.snappedToGraphemes(combining, UTF16Range(location: 0, length: 4))
        XCTAssertEqual(snapped, UTF16Range(location: 0, length: 5))
        XCTAssertEqual(UTF16Text.substring(combining, snapped!), "Cafe\u{0301}")
        // A range inside a flag (between its two regional indicators) covers the flag.
        let inside = UTF16Text.snappedToGraphemes(flag, UTF16Range(location: 12, length: 1))
        XCTAssertEqual(inside, UTF16Range(location: 10, length: 4))
    }

    func testReplacingKeepsSurroundingText() {
        XCTAssertEqual(UTF16Text.replacing(emoji, UTF16Range(location: 10, length: 4), with: "effort"),
                       "Good \u{1F44D}\u{1F3FD} effort")
        XCTAssertEqual(UTF16Text.replacing(combining, UTF16Range(location: 0, length: 5), with: "Tea"),
                       "Tea au lait")
        XCTAssertNil(UTF16Text.replacing(emoji, UTF16Range(location: 6, length: 1), with: "x"))
    }

    func testRangeArithmetic() {
        let r = UTF16Range(location: 5, length: 5)
        XCTAssertEqual(r.end, 10)
        XCTAssertTrue(r.intersects(UTF16Range(location: 9, length: 3)))
        XCTAssertFalse(r.intersects(UTF16Range(location: 10, length: 3)))
        XCTAssertEqual(r.intersection(UTF16Range(location: 8, length: 10)), UTF16Range(location: 8, length: 2))
        XCTAssertNil(r.intersection(UTF16Range(location: 0, length: 5)))
        XCTAssertEqual(r.shifted(by: -3), UTF16Range(location: 2, length: 5))
        XCTAssertEqual(r.clamped(toLength: 7), UTF16Range(location: 5, length: 2))
        XCTAssertNil(r.clamped(toLength: 5))
        XCTAssertEqual(UTF16Range(begin: 4, end: 2).length, 0)
    }

    func testParagraphSplittingOnEveryHardBreak() {
        let text = "One\nTwo\r\nThree\rFour\u{2029}Five\u{2028}still five\u{000B}too"
        let ps = ParagraphSplitter.split(text)
        XCTAssertEqual(ps.map { $0.text }, ["One", "Two", "Three", "Four", "Five\u{2028}still five\u{000B}too"])
        XCTAssertEqual(ps.map { $0.range.location }, [0, 4, 9, 15, 20])
        for p in ps {
            XCTAssertEqual(UTF16Text.substring(text, p.range), p.text)
        }
    }

    func testParagraphOffsetsAfterEmojiAndBlankLines() {
        let text = "\u{1F44D} first\n\nsecond \u{1F1F8}\u{1F1EC}\n"
        let ps = ParagraphSplitter.split(text)
        XCTAssertEqual(ps.count, 4)
        XCTAssertEqual(ps[0].range, UTF16Range(location: 0, length: 8))
        XCTAssertTrue(ps[1].isBlank)
        XCTAssertEqual(ps[2].range.location, 10)
        XCTAssertEqual(ps[2].text, "second \u{1F1F8}\u{1F1EC}")
        XCTAssertTrue(ps[3].isBlank)
        XCTAssertEqual(ps[3].range, UTF16Range(location: 22, length: 0))
    }

    func testEmptyTextIsOneBlankParagraph() {
        let ps = ParagraphSplitter.split("")
        XCTAssertEqual(ps.count, 1)
        XCTAssertTrue(ps[0].isBlank)
    }

    func testSnapshotFindsParagraphOfOffset() {
        let s = TextSnapshot("ab\ncd\n\nef")
        XCTAssertEqual(s.paragraphIndex(containing: 0), 0)
        XCTAssertEqual(s.paragraphIndex(containing: 2), 0)   // on the separator
        XCTAssertEqual(s.paragraphIndex(containing: 3), 1)
        XCTAssertEqual(s.paragraphIndex(containing: 7), 3)
        XCTAssertEqual(s.paragraphIndex(containing: 99), 3)
    }
}
