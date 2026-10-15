import Foundation
import XCTest
@testable import ResearchlyOverlayCore

/// The client against real replies of `POST /v1/check-paragraphs`
/// (packages/contract/fixtures/check-paragraphs, made by the engine
/// service and compared with it in services/engine; the Windows client
/// decodes the same files).
final class SharedFixtureTests: XCTestCase {
    func testTheOKReplyDecodesFully() throws {
        let fx = try SharedExchange("ok")
        let r = try fx.interpreted.get()
        XCTAssertEqual(r.revision, 41)
        XCTAssertEqual(r.schemaVersion, "1")
        XCTAssertEqual(r.state, "ok")
        XCTAssertEqual(r.paragraphs.map { $0.id }, ["p1", "p2", "p3", "p4"])
        XCTAssertEqual(r.paragraphs.map { $0.section }, ["results", "methods", "discussion", "unknown"])
        XCTAssertFalse(r.signedIn)
        XCTAssertEqual(r.hiddenPreferences, 0)
        XCTAssertNotNil(r.ruleset)
        let p1 = r.paragraphs[0].suggestions
        XCTAssertGreaterThanOrEqual(p1.count, 2)
        for s in p1 {
            XCTAssertEqual(s.id.count, 16)
            XCTAssertTrue(s.id.allSatisfy { $0.isHexDigit })
            XCTAssertFalse(s.text.isEmpty)
            XCTAssertFalse(s.message.isEmpty)
            XCTAssertFalse(s.plain.isEmpty)
            XCTAssertFalse(s.why.isEmpty)
            XCTAssertFalse(s.source.isEmpty)
            XCTAssertNotNil(s.ruleID)
            XCTAssertNotNil(s.ruleName)
            XCTAssertNotNil(s.tier)
            XCTAssertEqual(s.critical, s.category == .correction)
            XCTAssertEqual(s.section, "results")
            XCTAssertEqual(s.sectionLabel, "Results")
        }
        let doubled = try XCTUnwrap(p1.first { $0.ruleID == "W207" })
        XCTAssertEqual(doubled.text, "the the")
        XCTAssertEqual(doubled.replacements, ["the"])
        XCTAssertEqual(doubled.fixSafety, "safe")
        XCTAssertEqual(doubled.learnRef, "spelling-and-grammar")
        XCTAssertTrue(r.paragraphs[1].suggestions.isEmpty)       // passive in Methods: never flagged
        XCTAssertFalse(r.paragraphs[2].suggestions.isEmpty)      // the same words in Discussion
        XCTAssertTrue(r.paragraphs[3].suggestions.isEmpty)
    }

    func testOffsetsAreUTF16AndTheFlaggedWordsAreThere() throws {
        let fx = try SharedExchange("ok")
        let r = try fx.interpreted.get()
        let text = fx.text(of: "p1")
        XCTAssertTrue(text.unicodeScalars.contains { $0.value > 0xFFFF })   // astral characters first
        for s in r.paragraphs[0].suggestions {
            XCTAssertEqual(UTF16Text.substring(text, UTF16Range(begin: s.begin, end: s.end)), s.text)
        }
        // Placed in the field: the ledger checks `text` and keeps it as the
        // words a write-back must find again.
        var ledger = ParagraphLedger()
        ledger.update("Results\n" + text)
        let id = ledger.paragraphs[1].id
        ledger.markInFlight([id], revision: 1)
        ledger.apply([ParagraphResult(id: id, section: "results", suggestions: r.paragraphs[0].suggestions)],
                     revision: 1)
        let placed = ledger.allSuggestions
        XCTAssertEqual(placed.count, r.paragraphs[0].suggestions.count)
        let offset = "Results\n".utf16.count
        for p in placed {
            XCTAssertEqual(p.flaggedText, p.suggestion.text)
            XCTAssertEqual(UTF16Text.substring(ledger.snapshot.text, p.range), p.suggestion.text)
            XCTAssertEqual(p.range.location, p.suggestion.begin + offset)
        }
    }

    func testASuggestionWhoseWordsAreNotThereIsDropped() throws {
        let fx = try SharedExchange("ok")
        var s = try fx.interpreted.get().paragraphs[0].suggestions[0]
        s.begin += 1
        s.end += 1                                  // same length, wrong place
        var ledger = ParagraphLedger()
        ledger.update(fx.text(of: "p1"))
        let id = ledger.paragraphs[0].id
        ledger.markInFlight([id], revision: 1)
        ledger.apply([ParagraphResult(id: id, suggestions: [s])], revision: 1)
        XCTAssertTrue(ledger.allSuggestions.isEmpty)
    }

    func testDisabledAndMissingOptionalTiersAreNotAnOutage() throws {
        for name in ["ok", "clear"] {
            let r = try SharedExchange(name).interpreted.get()
            XCTAssertFalse(r.health.degraded, name)
            XCTAssertNil(r.health.reason, name)
        }
        // Even without `state`, the tiers alone say the same.
        let ok = try SharedExchange("ok")
        let json = try JSONSerialization.jsonObject(with: ok.response) as! [String: Any]
        let tiers = try JSONDecoder().decode(JSONValue.self,
                                             from: JSONSerialization.data(withJSONObject: json["health"]!))
        XCTAssertFalse(HealthSummary(json: tiers, state: nil).degraded)
    }

    func testTheClearReplyGivesTheClearState() throws {
        let fx = try SharedExchange("clear")
        let reply = try fx.interpreted.get()
        XCTAssertEqual(reply.paragraphs.first?.section, "unknown")
        let (session, engine) = makeSession()
        session.begin(text: fx.text(of: "only"))
        engine.respond(0, .success(rekeyed(reply, to: engine.requests[0])))
        XCTAssertEqual(session.state, .clear)
        XCTAssertNil(session.statusDetail)
    }

    func testThePartialReplyNamesTheTierThatIsDown() throws {
        let fx = try SharedExchange("partial")
        let reply = try fx.interpreted.get()
        XCTAssertEqual(reply.state, "partial")
        XCTAssertTrue(reply.health.degraded)
        XCTAssertEqual(reply.health.downTiers, ["Grammar"])
        XCTAssertFalse(reply.paragraphs[0].suggestions.isEmpty)     // the tiers that ran still count
        let (session, engine) = makeSession()
        session.begin(text: fx.text(of: "s.1"))
        engine.respond(0, .success(rekeyed(reply, to: engine.requests[0])))
        XCTAssertEqual(session.state, .issues)                       // the count wins…
        XCTAssertTrue(session.statusDetail?.contains("Grammar unavailable") ?? false)   // …and says what is missing
    }

    func testA422IsShownAndNotRetriedUntilAnEdit() throws {
        let fx = try SharedExchange("invalid-422")
        let result = fx.interpreted
        XCTAssertEqual(result, .failure(.rejected(status: 422, code: "invalid_request")))
        let (session, engine, scheduler) = makeSessionWithScheduler()
        session.begin(text: "We fitted a renewal model to weekly case counts.")
        engine.respond(0, result)
        XCTAssertEqual(session.state, .offline)
        XCTAssertTrue(session.statusDetail?.contains("after your next edit") ?? false)
        XCTAssertTrue(scheduler.pendingDelays.isEmpty)              // no retry loop
        scheduler.advance(by: 120)
        XCTAssertEqual(engine.calls.count, 1)
        // An edit gives the paragraph a new id and it is checked again.
        session.textDidChange("We fitted a renewal model to daily case counts.")
        scheduler.advance(by: 1.5)
        XCTAssertEqual(engine.calls.count, 2)
        engine.reply(1)
        XCTAssertEqual(session.state, .clear)
    }

    func testARejectedParagraphStaysUncheckedButTheOthersGoOn() throws {
        let (session, engine, scheduler) = makeSessionWithScheduler()
        session.begin(text: "First paragraph.\nSecond paragraph.")
        engine.respond(0, .failure(.rejected(status: 422, code: "invalid_request")))
        session.textDidChange("First paragraph.\nSecond paragraph.\nA third one.")
        scheduler.advance(by: 1.5)
        XCTAssertEqual(engine.requests[1].paragraphs.map { $0.text }, ["A third one."])
        engine.reply(1)
        XCTAssertEqual(session.state, .partial)
        XCTAssertTrue(session.statusDetail?.contains("2 paragraphs couldn’t be checked") ?? false)
    }

    func testA429WaitsAsLongAsTheEngineSays() throws {
        let fx = try SharedExchange("rate-limited-429")
        let result = fx.interpreted
        guard case .failure(.rateLimited(let wait?)) = result else { return XCTFail("\(result)") }
        XCTAssertEqual(wait, Double(fx.headers["retry-after"]!))
        let (session, engine, scheduler) = makeSessionWithScheduler()
        session.begin(text: "We fitted a renewal model to weekly case counts.")
        engine.respond(0, result)
        XCTAssertEqual(session.state, .offline)
        XCTAssertEqual(scheduler.pendingDelays, [min(wait, 120)])   // not the usual 2 s
        scheduler.advance(by: min(wait, 120))
        XCTAssertEqual(engine.calls.count, 2)
    }

    func testTheRequestIsWhatTheEngineAccepted() throws {
        let fx = try SharedExchange("ok")
        let sent = CheckRequest(
            revision: fx.revision,
            paragraphs: fx.paragraphs.map {
                ParagraphPayload(id: $0["id"] as! String, text: $0["text"] as! String,
                                 heading: $0["heading"] as? String)
            },
            options: CheckOptions(showPreferences: false))
        let encoded = try JSONSerialization.jsonObject(with: JSONEncoder().encode(sent)) as! NSDictionary
        XCTAssertEqual(encoded, fx.request as NSDictionary)
    }

    func testRequestsStayInsideTheEnginesLimits() {
        var ledger = ParagraphLedger()
        let long = String(repeating: "word ", count: 4_100)          // 20,500 characters
        let short = (0..<80).map { "Paragraph \($0) is short." }
        ledger.update(([long] + short).joined(separator: "\n"))
        XCTAssertEqual(ledger.paragraphs[0].status, .tooLong)
        let batch = ledger.nextBatch(caret: 0, visible: nil, maxCount: 500, maxCharacters: 1_000_000)
        XCTAssertLessThanOrEqual(batch.count, LiveLimits.maxParagraphs)
        XCTAssertLessThanOrEqual(batch.map { LiveLimits.characters($0.text) }.reduce(0, +), LiveLimits.maxCharacters)
        XCTAssertFalse(batch.contains { $0.id == ledger.paragraphs[0].id })
        XCTAssertEqual(ledger.uncheckable.tooLong, 1)
    }

    // MARK: helpers

    private func makeSession() -> (LiveCheckSession, FakeEngine) {
        let (s, e, _) = makeSessionWithScheduler()
        return (s, e)
    }

    private func makeSessionWithScheduler() -> (LiveCheckSession, FakeEngine, ManualScheduler) {
        let scheduler = ManualScheduler()
        let engine = FakeEngine()
        return (LiveCheckSession(client: engine, scheduler: scheduler), engine, scheduler)
    }

    /// The fixture's reply, addressed to the ids this session sent.
    private func rekeyed(_ reply: CheckResponse, to request: CheckRequest) -> CheckResponse {
        var out = reply
        out.revision = request.revision
        out.paragraphs = zip(reply.paragraphs, request.paragraphs).map { result, sent in
            ParagraphResult(id: sent.id, section: result.section, suggestions: result.suggestions)
        }
        return out
    }
}
