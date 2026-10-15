import Foundation

/// The six states every surface shares (design note §3).
public enum OverlayState: String, CaseIterable, Codable {
    /// Not eligible here, or paused by the writer. Nothing is shown.
    case hidden
    /// A check is pending or in flight for the current text.
    case checking
    /// Visible suggestions exist.
    case issues
    /// Checked, nothing to show.
    case clear
    /// Checked, but a tier was down.
    case partial
    /// The engine cannot be reached, or refused.
    case offline

    /// Words for the menu bar and the widget's hover text.
    public var title: String {
        switch self {
        case .hidden: return "Not checking here"
        case .checking: return "Checking…"
        case .issues: return "Suggestions"
        case .clear: return "No suggestions"
        case .partial: return "Checked in part"
        case .offline: return "Can’t check right now"
        }
    }
}

/// What the state depends on, gathered by the live-check session.
public struct StateInputs: Equatable {
    public var active: Bool
    public var offline: Bool
    public var pending: Bool
    public var visibleCount: Int
    public var degraded: Bool

    public init(active: Bool, offline: Bool = false, pending: Bool = false,
                visibleCount: Int = 0, degraded: Bool = false) {
        self.active = active
        self.offline = offline
        self.pending = pending
        self.visibleCount = visibleCount
        self.degraded = degraded
    }
}

public enum StateMachine {
    /// The transitions of design note §3, as one pure function:
    /// - leaving the field or pausing → hidden;
    /// - a failure → offline, until any success;
    /// - an edit (pending text) → checking;
    /// - a reply → issues, partial or clear. When suggestions exist and a
    ///   tier was also down, `issues` wins (the count is what the writer
    ///   acts on) and the widget's hover text names the missing tier.
    public static func state(for inputs: StateInputs) -> OverlayState {
        if !inputs.active { return .hidden }
        if inputs.offline { return .offline }
        if inputs.pending { return .checking }
        if inputs.visibleCount > 0 { return .issues }
        return inputs.degraded ? .partial : .clear
    }
}

/// Retry delays after failures: 2, 4, 8, 16 and 30 s, then every 30 s.
public struct RetryBackoff: Equatable {
    public static let schedule: [TimeInterval] = [2, 4, 8, 16, 30]
    public private(set) var failures = 0

    public init() {}

    /// Records a failure and returns how long to wait before retrying.
    public mutating func nextDelay() -> TimeInterval {
        let delay = RetryBackoff.schedule[min(failures, RetryBackoff.schedule.count - 1)]
        failures += 1
        return delay
    }

    public mutating func reset() { failures = 0 }
}

/// Hands out request revisions and remembers which one is awaited, so a
/// reply to anything else is dropped (§5: "revision is echoed so the client
/// can drop stale replies").
public struct RevisionTracker: Equatable {
    public private(set) var latestIssued = 0
    public private(set) var awaited: Int?

    public init() {}

    public mutating func issue() -> Int {
        latestIssued += 1
        awaited = latestIssued
        return latestIssued
    }

    /// True (and the wait ends) if `revision` is the reply being awaited.
    public mutating func accept(_ revision: Int) -> Bool {
        guard awaited == revision else { return false }
        awaited = nil
        return true
    }

    /// Forget the awaited reply (focus moved on); it will be dropped.
    public mutating func abandon() { awaited = nil }

    public var isAwaiting: Bool { awaited != nil }
}

// MARK: - Scheduling

public protocol Cancellable: AnyObject {
    func cancel()
}

/// Time and the main queue, abstracted so tests can run them by hand.
public protocol OverlayScheduler: AnyObject {
    var now: Date { get }
    /// Run `work` on the scheduler's queue after `delay` seconds.
    @discardableResult
    func schedule(after delay: TimeInterval, _ work: @escaping () -> Void) -> Cancellable
    /// Run `work` on the scheduler's queue as soon as possible (used to bring
    /// network replies back to the main queue).
    func deliver(_ work: @escaping () -> Void)
}

/// The real scheduler: the main dispatch queue.
public final class MainQueueScheduler: OverlayScheduler {
    private final class Token: Cancellable {
        let item: DispatchWorkItem
        init(_ item: DispatchWorkItem) { self.item = item }
        func cancel() { item.cancel() }
    }

    public init() {}

    public var now: Date { Date() }

    @discardableResult
    public func schedule(after delay: TimeInterval, _ work: @escaping () -> Void) -> Cancellable {
        let item = DispatchWorkItem(block: work)
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: item)
        return Token(item)
    }

    public func deliver(_ work: @escaping () -> Void) {
        DispatchQueue.main.async(execute: work)
    }
}

/// Waits for a pause in typing: every `poke()` restarts the wait, and the
/// action runs once the writer has stopped for `delay` seconds (§1.8).
public final class Debouncer {
    public let delay: TimeInterval
    private let scheduler: OverlayScheduler
    private var pending: Cancellable?
    private let action: () -> Void

    public init(delay: TimeInterval = 1.5, scheduler: OverlayScheduler, action: @escaping () -> Void) {
        self.delay = delay
        self.scheduler = scheduler
        self.action = action
    }

    public var isPending: Bool { pending != nil }

    private var generation = 0

    public func poke() {
        pending?.cancel()
        generation += 1
        let mine = generation
        pending = scheduler.schedule(after: delay) { [weak self] in
            guard let self = self, self.generation == mine, self.pending != nil else { return }
            self.pending = nil
            self.action()
        }
    }

    public func cancel() {
        pending?.cancel()
        pending = nil
        generation += 1
    }
}

// MARK: - Pause

/// The writer's pause: for a while, until tomorrow, or always in some apps.
/// Settings only; stored by the shell in UserDefaults.
public struct PauseState: Codable, Equatable {
    public var until: Date?
    public var pausedApps: Set<String>

    public init(until: Date? = nil, pausedApps: Set<String> = []) {
        self.until = until
        self.pausedApps = pausedApps
    }

    public func isPaused(bundleID: String?, now: Date) -> Bool {
        if let until = until, now < until { return true }
        if let id = bundleID, pausedApps.contains(id) { return true }
        return false
    }

    public func isPausedEverywhere(now: Date) -> Bool {
        if let until = until { return now < until }
        return false
    }

    public mutating func pause(for interval: TimeInterval, now: Date) {
        until = now.addingTimeInterval(interval)
    }

    /// Until the start of the next calendar day in `calendar`'s time zone.
    public mutating func pauseUntilTomorrow(now: Date, calendar: Calendar = .current) {
        let today = calendar.startOfDay(for: now)
        until = calendar.date(byAdding: .day, value: 1, to: today)
    }

    public mutating func resume() { until = nil }

    public mutating func toggle(app bundleID: String) {
        if pausedApps.contains(bundleID) { pausedApps.remove(bundleID) } else { pausedApps.insert(bundleID) }
    }
}
