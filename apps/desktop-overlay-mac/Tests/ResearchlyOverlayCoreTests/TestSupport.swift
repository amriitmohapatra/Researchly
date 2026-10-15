import Foundation
import XCTest
@testable import ResearchlyOverlayCore

/// Paths in the checkout, found from this file's location.
enum Repo {
    static let testsDir = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
    static let fixtures = testsDir.appendingPathComponent("Fixtures")
    static let root = testsDir.appendingPathComponent("../../../../").standardizedFileURL
    static let fieldsJSON = root.appendingPathComponent("packages/desktop-rules/fields.json")
    static let appsJSON = root.appendingPathComponent("packages/desktop-rules/apps-mac.json")

    static func fixture(_ name: String) throws -> Data {
        try Data(contentsOf: fixtures.appendingPathComponent(name))
    }
}

/// A scheduler whose clock moves only when a test says so.
final class ManualScheduler: OverlayScheduler {
    private final class Job: Cancellable {
        let due: TimeInterval
        let seq: Int
        let work: () -> Void
        var cancelled = false
        init(due: TimeInterval, seq: Int, work: @escaping () -> Void) {
            self.due = due
            self.seq = seq
            self.work = work
        }
        func cancel() { cancelled = true }
    }

    private(set) var elapsed: TimeInterval = 0
    private var jobs: [Job] = []
    private var seq = 0
    private let start = Date(timeIntervalSince1970: 1_800_000_000)

    var now: Date { start.addingTimeInterval(elapsed) }

    @discardableResult
    func schedule(after delay: TimeInterval, _ work: @escaping () -> Void) -> Cancellable {
        seq += 1
        let job = Job(due: elapsed + delay, seq: seq, work: work)
        jobs.append(job)
        return job
    }

    func deliver(_ work: @escaping () -> Void) {
        schedule(after: 0, work)
        runDue()
    }

    /// Delays of the jobs still waiting, relative to now.
    var pendingDelays: [TimeInterval] {
        jobs.filter { !$0.cancelled }.map { $0.due - elapsed }.sorted()
    }

    func advance(by seconds: TimeInterval) {
        let target = elapsed + seconds
        while let next = jobs.filter({ !$0.cancelled && $0.due <= target })
            .min(by: { ($0.due, $0.seq) < ($1.due, $1.seq) }) {
            elapsed = max(elapsed, next.due)
            jobs.removeAll { $0 === next }
            next.work()
        }
        elapsed = target
        jobs.removeAll { $0.cancelled }
    }

    func runDue() { advance(by: 0) }
}

/// An engine that records requests and answers when told to.
final class FakeEngine: EngineChecking {
    struct Call {
        let request: CheckRequest
        let completion: (Result<CheckResponse, EngineError>) -> Void
    }

    private(set) var calls: [Call] = []
    var requests: [CheckRequest] { calls.map { $0.request } }

    func check(_ request: CheckRequest, completion: @escaping (Result<CheckResponse, EngineError>) -> Void) {
        calls.append(Call(request: request, completion: completion))
    }

    /// Answers call `index` with the given suggestions per paragraph id
    /// (absent ids get none).
    func reply(_ index: Int, suggestions: [String: [LiveSuggestion]] = [:],
               health: HealthSummary = .ok, revision: Int? = nil) {
        let call = calls[index]
        let results = call.request.paragraphs.map {
            ParagraphResult(id: $0.id, suggestions: suggestions[$0.id] ?? [])
        }
        call.completion(.success(CheckResponse(revision: revision ?? call.request.revision,
                                               paragraphs: results, health: health)))
    }

    func fail(_ index: Int, _ error: EngineError = .unreachable("offline")) {
        calls[index].completion(.failure(error))
    }
}

func suggestion(_ id: String, _ begin: Int, _ end: Int, _ category: Category = .correction,
                replacements: [String] = []) -> LiveSuggestion {
    LiveSuggestion(id: id, begin: begin, end: end, category: category,
                   message: "msg", replacements: replacements)
}
