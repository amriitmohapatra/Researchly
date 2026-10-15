import XCTest
@testable import ResearchlyOverlayCore

final class StateMachineTests: XCTestCase {
    func testEveryState() {
        XCTAssertEqual(StateMachine.state(for: StateInputs(active: false, offline: true, pending: true)), .hidden)
        XCTAssertEqual(StateMachine.state(for: StateInputs(active: true, offline: true, pending: true)), .offline)
        XCTAssertEqual(StateMachine.state(for: StateInputs(active: true, pending: true, visibleCount: 3)), .checking)
        XCTAssertEqual(StateMachine.state(for: StateInputs(active: true, visibleCount: 3)), .issues)
        XCTAssertEqual(StateMachine.state(for: StateInputs(active: true, visibleCount: 3, degraded: true)), .issues)
        XCTAssertEqual(StateMachine.state(for: StateInputs(active: true, degraded: true)), .partial)
        XCTAssertEqual(StateMachine.state(for: StateInputs(active: true)), .clear)
        XCTAssertEqual(OverlayState.allCases.count, 6)
    }

    func testBackoffSchedule() {
        var b = RetryBackoff()
        XCTAssertEqual((0..<7).map { _ in b.nextDelay() }, [2, 4, 8, 16, 30, 30, 30])
        b.reset()
        XCTAssertEqual(b.nextDelay(), 2)
    }

    func testRevisionTrackerDropsAnythingButTheAwaitedReply() {
        var t = RevisionTracker()
        let r1 = t.issue()
        XCTAssertFalse(t.accept(r1 + 1))
        XCTAssertTrue(t.accept(r1))
        XCTAssertFalse(t.accept(r1))           // once only
        let r2 = t.issue()
        t.abandon()
        XCTAssertFalse(t.accept(r2))
        XCTAssertEqual(t.issue(), r2 + 1)       // revisions only grow
    }

    func testDebouncerWaitsForThePause() {
        let s = ManualScheduler()
        var fired = 0
        let d = Debouncer(delay: 1.5, scheduler: s) { fired += 1 }
        d.poke()
        s.advance(by: 1.0)
        d.poke()                     // still typing: the wait restarts
        s.advance(by: 1.0)
        XCTAssertEqual(fired, 0)
        XCTAssertTrue(d.isPending)
        s.advance(by: 0.5)
        XCTAssertEqual(fired, 1)
        XCTAssertFalse(d.isPending)
        d.poke()
        d.cancel()
        s.advance(by: 5)
        XCTAssertEqual(fired, 1)
    }

    func testPause() {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "Asia/Singapore")!
        let now = cal.date(from: DateComponents(year: 2026, month: 10, day: 15, hour: 21, minute: 30))!
        var p = PauseState()
        XCTAssertFalse(p.isPaused(bundleID: "x", now: now))
        p.pause(for: 3600, now: now)
        XCTAssertTrue(p.isPaused(bundleID: "x", now: now.addingTimeInterval(3599)))
        XCTAssertFalse(p.isPaused(bundleID: "x", now: now.addingTimeInterval(3601)))
        p.pauseUntilTomorrow(now: now, calendar: cal)
        XCTAssertEqual(p.until, cal.date(from: DateComponents(year: 2026, month: 10, day: 16)))
        p.resume()
        p.toggle(app: "com.apple.mail")
        XCTAssertTrue(p.isPaused(bundleID: "com.apple.mail", now: now))
        XCTAssertFalse(p.isPaused(bundleID: "com.apple.Notes", now: now))
        XCTAssertFalse(p.isPausedEverywhere(now: now))
        p.toggle(app: "com.apple.mail")
        XCTAssertFalse(p.isPaused(bundleID: "com.apple.mail", now: now))
        let data = try! JSONEncoder().encode(p)
        XCTAssertEqual(try! JSONDecoder().decode(PauseState.self, from: data), p)
    }
}

final class LiveCheckSessionTests: XCTestCase {
    var scheduler: ManualScheduler!
    var engine: FakeEngine!
    var session: LiveCheckSession!
    var updates = 0

    override func setUp() {
        scheduler = ManualScheduler()
        engine = FakeEngine()
        session = LiveCheckSession(client: engine, scheduler: scheduler)
        updates = 0
        session.onUpdate = { [unowned self] in self.updates += 1 }
    }

    func testFocusChecksAtOnceAndAReplyShowsIssues() {
        session.begin(text: "Ther are results.\nAll fine here.")
        XCTAssertEqual(session.state, .checking)
        XCTAssertEqual(engine.calls.count, 1)
        let req = engine.requests[0]
        XCTAssertEqual(req.revision, 1)
        XCTAssertEqual(req.paragraphs.map { $0.text }, ["Ther are results.", "All fine here."])
        engine.reply(0, suggestions: [req.paragraphs[0].id: [suggestion("s1", 0, 4, replacements: ["There"])]])
        XCTAssertEqual(session.state, .issues)
        XCTAssertEqual(session.visibleSuggestions.count, 1)
        XCTAssertEqual(session.visibleSuggestions[0].flaggedText, "Ther")
        XCTAssertGreaterThan(updates, 0)
    }

    func testCleanReplyIsClearAndDegradedReplyIsPartial() {
        session.begin(text: "Fine.")
        engine.reply(0)
        XCTAssertEqual(session.state, .clear)
        session.textDidChange("Fine again.")
        scheduler.advance(by: 1.5)
        engine.reply(1, health: HealthSummary(degraded: true, downTiers: ["Grammar"], detail: nil))
        XCTAssertEqual(session.state, .partial)
        XCTAssertEqual(session.statusDetail, "Grammar unavailable right now.")
    }

    func testEditsWaitForTheDebounceBeforeSending() {
        session.begin(text: "One.")
        engine.reply(0)
        session.textDidChange("One. Two")
        XCTAssertEqual(session.state, .checking)          // an edit goes to checking
        scheduler.advance(by: 1.0)
        session.textDidChange("One. Two words")
        scheduler.advance(by: 1.4)
        XCTAssertEqual(engine.calls.count, 1)             // still typing
        scheduler.advance(by: 0.1)
        XCTAssertEqual(engine.calls.count, 2)
        XCTAssertEqual(engine.requests[1].paragraphs.map { $0.text }, ["One. Two words"])
        XCTAssertEqual(engine.requests[1].revision, 2)
    }

    func testOnlyChangedParagraphsAreResent() {
        session.begin(text: "Alpha.\nBeta.\nGamma.")
        engine.reply(0)
        session.textDidChange("Alpha.\nBeta, edited.\nGamma.")
        scheduler.advance(by: 1.5)
        XCTAssertEqual(engine.requests[1].paragraphs.map { $0.text }, ["Beta, edited."])
    }

    func testStaleReplyIsDropped() {
        session.begin(text: "Teh first.\nSecond.")
        let firstID = engine.requests[0].paragraphs[0].id
        // The writer edits the first paragraph while the check is in flight.
        session.textDidChange("The first.\nSecond.")
        engine.reply(0, suggestions: [firstID: [suggestion("old", 0, 3)]])
        XCTAssertTrue(session.visibleSuggestions.isEmpty, "advice about old words must not land on new ones")
        XCTAssertEqual(session.state, .checking)
        scheduler.advance(by: 1.5)
        XCTAssertEqual(engine.requests[1].paragraphs.map { $0.text }, ["The first."])
        engine.reply(1)
        XCTAssertEqual(session.state, .clear)
    }

    func testReplyWithAnotherRevisionIsRefusedByTheClient() {
        let result = EngineClient.interpret(.success((status: 200, body: Data(#"{"revision": 9, "paragraphs": []}"#.utf8))),
                                            sentRevision: 4)
        XCTAssertEqual(result, .failure(.revisionMismatch(sent: 4, received: 9)))
    }

    func testReplyAfterEndIsIgnored() {
        session.begin(text: "Some text.")
        session.end()
        XCTAssertEqual(session.state, .hidden)
        engine.reply(0, suggestions: [engine.requests[0].paragraphs[0].id: [suggestion("x", 0, 4)]])
        XCTAssertEqual(session.state, .hidden)
        XCTAssertTrue(session.visibleSuggestions.isEmpty)
    }

    func testOfflineRetriesWithBackoffAndRecovers() {
        session.begin(text: "Hello there.")
        engine.fail(0)
        XCTAssertEqual(session.state, .offline)
        XCTAssertNotNil(session.statusDetail)
        XCTAssertEqual(scheduler.pendingDelays, [2])
        scheduler.advance(by: 2)
        XCTAssertEqual(engine.calls.count, 2)
        engine.fail(1)
        XCTAssertEqual(scheduler.pendingDelays, [4])
        scheduler.advance(by: 4)
        engine.fail(2)
        scheduler.advance(by: 8)
        engine.fail(3)
        scheduler.advance(by: 16)
        engine.fail(4)
        XCTAssertEqual(scheduler.pendingDelays, [30])
        scheduler.advance(by: 30)
        engine.fail(5)
        XCTAssertEqual(scheduler.pendingDelays, [30])
        scheduler.advance(by: 30)
        XCTAssertEqual(session.state, .offline)
        engine.reply(6)                                   // any success leaves offline
        XCTAssertEqual(session.state, .clear)
        XCTAssertEqual(session.failuresSoFar, 0)
        XCTAssertTrue(scheduler.pendingDelays.isEmpty)
    }

    func testAnEditWhileOfflineStaysOfflineAndTriesAfterThePause() {
        session.begin(text: "Hello.")
        engine.fail(0)
        session.textDidChange("Hello again.")
        XCTAssertEqual(session.state, .offline)           // never shows old findings as current
        scheduler.advance(by: 1.5)
        XCTAssertEqual(engine.calls.count, 2)             // the pause sends at once
        XCTAssertEqual(scheduler.pendingDelays, [])       // and replaces the timed retry
        engine.reply(1)
        XCTAssertEqual(session.state, .clear)
    }

    func testDismissedAndPreferenceSuggestionsAreHidden() {
        session.begin(text: "Some words here.")
        let id = engine.requests[0].paragraphs[0].id
        engine.reply(0, suggestions: [id: [suggestion("c", 0, 4), suggestion("p", 5, 10, .preference)]])
        XCTAssertEqual(session.visibleSuggestions.map { $0.id }, ["c"])
        session.dismiss("c")
        XCTAssertTrue(session.visibleSuggestions.isEmpty)
        XCTAssertEqual(session.state, .clear)

        let withPrefs = LiveCheckSession(client: engine, scheduler: scheduler,
                                         configuration: .init(options: CheckOptions(showPreferences: true)))
        withPrefs.begin(text: "Other words.")
        let id2 = engine.requests[1].paragraphs[0].id
        XCTAssertEqual(engine.requests[1].options.showPreferences, true)
        engine.reply(1, suggestions: [id2: [suggestion("p2", 0, 5, .preference)]])
        XCTAssertEqual(withPrefs.visibleSuggestions.map { $0.id }, ["p2"])
    }

    func testLargeDocumentsAreSentInBatchesOneAtATime() {
        let text = (0..<45).map { "Sentence number \($0) of the draft." }.joined(separator: "\n")
        session.begin(text: text)
        XCTAssertEqual(engine.calls.count, 1)
        XCTAssertEqual(engine.requests[0].paragraphs.count, 20)
        engine.reply(0)
        XCTAssertEqual(engine.calls.count, 2)
        XCTAssertEqual(session.state, .checking)
        engine.reply(1)
        engine.reply(2)
        XCTAssertEqual(engine.requests[2].paragraphs.count, 5)
        XCTAssertEqual(session.state, .clear)
        XCTAssertEqual(Set(engine.requests.flatMap { $0.paragraphs.map { $0.id } }).count, 45)
    }

    func testHeadingsTravelWithTheirParagraphs() {
        session.begin(text: "Methods\nWe sampled sites.\n\nDiscussion\nWe sampled sites.")
        let ps = engine.requests[0].paragraphs
        XCTAssertEqual(ps.map { $0.heading }, ["Methods", "Discussion"])
    }

    func testLowPriorityAppsWaitLongerAndSendLess() {
        let rule = AppRules.builtInDefaults
        var low = rule
        low.priority = "low"
        XCTAssertEqual(LiveCheckSession.Configuration.forApp(rule, options: CheckOptions()).debounce, 1.5)
        XCTAssertEqual(LiveCheckSession.Configuration.forApp(low, options: CheckOptions()).debounce, 2.5)
        XCTAssertEqual(LiveCheckSession.Configuration.forApp(low, options: CheckOptions()).maxParagraphsPerRequest, 5)
    }

    func testBlankFieldIsClearWithoutARequest() {
        session.begin(text: "   \n")
        XCTAssertEqual(engine.calls.count, 0)
        XCTAssertEqual(session.state, .clear)
    }
}
