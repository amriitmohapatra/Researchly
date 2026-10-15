import XCTest
@testable import ResearchlyOverlayCore

final class ParagraphDiffTests: XCTestCase {
    func testTypingInOneParagraphChangesOnlyThatParagraph() {
        let d = ParagraphDiff.between(["A", "B", "C"], ["A", "B2", "C"])
        XCTAssertEqual(d.matches, [.init(old: 0, new: 0), .init(old: 2, new: 2)])
        XCTAssertEqual(d.inserted, [1])
        XCTAssertEqual(d.removed, [1])
    }

    func testInsertedParagraphShiftsTheRest() {
        let d = ParagraphDiff.between(["A", "B", "C"], ["A", "new", "B", "C"])
        XCTAssertEqual(d.inserted, [1])
        XCTAssertEqual(d.removed, [])
        XCTAssertTrue(d.matches.contains(.init(old: 1, new: 2)))
        XCTAssertTrue(d.matches.contains(.init(old: 2, new: 3)))
    }

    func testDeletedAndMovedParagraphs() {
        let d = ParagraphDiff.between(["A", "B", "C", "D"], ["A", "C", "X", "D"])
        XCTAssertEqual(d.removed, [1])
        XCTAssertEqual(d.inserted, [2])
        XCTAssertTrue(d.matches.contains(.init(old: 2, new: 1)))
    }

    func testIdenticalAndEmpty() {
        XCTAssertEqual(ParagraphDiff.between(["A"], ["A"]).inserted, [])
        XCTAssertEqual(ParagraphDiff.between([], ["A", "B"]).inserted, [0, 1])
        XCTAssertEqual(ParagraphDiff.between(["A", "B"], []).removed, [0, 1])
    }

    func testHugeRewriteFallsBackToAllChanged() {
        let old = (0..<600).map { "old \($0)" }
        let new = (0..<600).map { "new \($0)" }
        let d = ParagraphDiff.between(old, new)
        XCTAssertEqual(d.inserted.count, 600)
        XCTAssertTrue(d.matches.isEmpty)
    }
}

final class ParagraphLedgerTests: XCTestCase {
    func testNewParagraphsArePendingAndBlankOrHeadingsSkipped() {
        var l = ParagraphLedger()
        l.update("Methods\n\nWe sampled forty sites.\n## Results\nRates rose.")
        XCTAssertEqual(l.paragraphs.map { $0.status }, [.skipped, .skipped, .pending, .skipped, .pending])
        XCTAssertEqual(l.paragraphs[2].heading, "Methods")
        XCTAssertEqual(l.paragraphs[4].heading, "Results")
    }

    func testUnchangedParagraphsKeepIdsAndSuggestionsMoveWithText() {
        var l = ParagraphLedger()
        l.update("First line here.\nSecond line here.")
        let ids = l.paragraphs.map { $0.id }
        l.markInFlight(ids, revision: 1)
        l.apply([ParagraphResult(id: ids[1], suggestions: [suggestion("s1", 0, 6)])], revision: 1)
        XCTAssertEqual(l.allSuggestions.first?.range, UTF16Range(location: 17, length: 6))
        XCTAssertEqual(l.allSuggestions.first?.flaggedText, "Second")

        // Edit the first paragraph (adds 4 units): the second keeps its id,
        // status and suggestion, shifted by 4; the first is pending again.
        l.update("First line here too.\nSecond line here.")
        XCTAssertEqual(l.paragraphs[1].id, ids[1])
        XCTAssertNotEqual(l.paragraphs[0].id, ids[0])
        XCTAssertEqual(l.paragraphs[0].status, .pending)
        XCTAssertEqual(l.paragraphs[1].status, .checked)
        XCTAssertEqual(l.allSuggestions.first?.range, UTF16Range(location: 21, length: 6))
    }

    func testReplyForAnEditedParagraphIsDropped() {
        var l = ParagraphLedger()
        l.update("Alpha beta.")
        let oldID = l.paragraphs[0].id
        l.markInFlight([oldID], revision: 3)
        l.update("Alpha beta gamma.")          // edited while in flight
        let applied = l.apply([ParagraphResult(id: oldID, suggestions: [suggestion("x", 0, 5)])], revision: 3)
        XCTAssertEqual(applied, 0)
        XCTAssertTrue(l.allSuggestions.isEmpty)
        XCTAssertEqual(l.paragraphs[0].status, .pending)
    }

    func testOutOfRangeOrSplittingSuggestionsAreDiscarded() {
        var l = ParagraphLedger()
        l.update("Hi \u{1F44D} there")
        let id = l.paragraphs[0].id
        l.markInFlight([id], revision: 1)
        l.apply([ParagraphResult(id: id, suggestions: [
            suggestion("ok", 6, 11),
            suggestion("past-end", 6, 40),
            suggestion("mid-pair", 4, 6),
            suggestion("backwards", 5, 2),
        ])], revision: 1)
        XCTAssertEqual(l.allSuggestions.map { $0.id }, ["ok"])
        XCTAssertEqual(l.allSuggestions[0].flaggedText, "there")
    }

    func testRenamingTheHeadingRechecksTheSection() {
        var l = ParagraphLedger()
        l.update("Methods\nWe used a survey.")
        let id = l.paragraphs[1].id
        l.markInFlight([id], revision: 1)
        l.apply([ParagraphResult(id: id, suggestions: [])], revision: 1)
        XCTAssertEqual(l.paragraphs[1].status, .checked)
        l.update("Discussion\nWe used a survey.")
        XCTAssertEqual(l.paragraphs[1].id, id)
        XCTAssertEqual(l.paragraphs[1].heading, "Discussion")
        XCTAssertEqual(l.paragraphs[1].status, .pending)
    }

    func testBatchPrefersVisibleThenCaretAndRespectsLimits() {
        var l = ParagraphLedger()
        let text = (0..<10).map { "Paragraph number \($0) is here." }.joined(separator: "\n")
        l.update(text)
        let p7 = l.paragraphs[7]
        let batch = l.nextBatch(caret: p7.range.location, visible: l.paragraphs[2].range, maxCount: 3, maxCharacters: 10_000)
        XCTAssertEqual(batch.map { $0.id }, [l.paragraphs[2].id, l.paragraphs[7].id, l.paragraphs[6].id])
        let small = l.nextBatch(caret: 0, visible: nil, maxCount: 10, maxCharacters: 60)
        XCTAssertEqual(small.count, 2)
    }

    func testRevertInFlightMakesParagraphsPendingAgain() {
        var l = ParagraphLedger()
        l.update("One.\nTwo.")
        l.markInFlight(l.paragraphs.map { $0.id }, revision: 5)
        XCTAssertTrue(l.hasPendingOrInFlight)
        XCTAssertFalse(l.hasPending)
        l.revertInFlight(revision: 5)
        XCTAssertTrue(l.hasPending)
    }

    func testHeadingDetector() {
        XCTAssertEqual(HeadingDetector.headingText("2.1 Methods"), "Methods")
        XCTAssertEqual(HeadingDetector.headingText("# Introduction"), "Introduction")
        XCTAssertEqual(HeadingDetector.headingText("RESULTS"), "RESULTS")
        XCTAssertEqual(HeadingDetector.headingText("Materials & Methods:"), "Materials & Methods")
        XCTAssertEqual(HeadingDetector.headingText("Chapter 3 Transmission dynamics"), "Chapter 3 Transmission dynamics")
        XCTAssertNil(HeadingDetector.headingText("The methods were standard."))
        XCTAssertNil(HeadingDetector.headingText("#hashtag"))
        XCTAssertNil(HeadingDetector.headingText(""))
    }
}
