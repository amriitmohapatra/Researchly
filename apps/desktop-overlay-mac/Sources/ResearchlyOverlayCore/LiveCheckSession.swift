import Foundation

/// The live-check loop for one focused field (design note §6, steps 3–4):
/// wait for a pause, send the changed paragraphs with a revision, drop
/// stale replies, retry with backoff, and derive the six states.
///
/// Platform-neutral and single-threaded: every method is called on the
/// scheduler's queue (the main queue in the app), and replies are brought
/// back to it with `scheduler.deliver`. The text lives in memory only, for
/// as long as the session does.
public final class LiveCheckSession {
    public struct Configuration: Equatable {
        public var debounce: TimeInterval
        public var maxParagraphsPerRequest: Int
        public var maxCharactersPerRequest: Int
        public var options: CheckOptions

        public init(debounce: TimeInterval = 1.5, maxParagraphsPerRequest: Int = 20,
                    maxCharactersPerRequest: Int = 20_000, options: CheckOptions = CheckOptions()) {
            self.debounce = debounce
            self.maxParagraphsPerRequest = maxParagraphsPerRequest
            self.maxCharactersPerRequest = maxCharactersPerRequest
            self.options = options
        }

        /// A low-priority app (apps-mac.json) waits longer and sends less.
        public static func forApp(_ rule: AppRule, options: CheckOptions) -> Configuration {
            rule.isLowPriority
                ? Configuration(debounce: 2.5, maxParagraphsPerRequest: 5, maxCharactersPerRequest: 8_000, options: options)
                : Configuration(options: options)
        }
    }

    public let configuration: Configuration
    /// Called after any change of state or of the visible suggestions.
    public var onUpdate: (() -> Void)?

    public private(set) var state: OverlayState = .hidden
    public private(set) var health: HealthSummary = .ok
    public private(set) var lastError: EngineError?
    public private(set) var ledger = ParagraphLedger()

    private let client: EngineChecking
    private let scheduler: OverlayScheduler
    private var debouncer: Debouncer!
    private var revisions = RevisionTracker()
    private var backoff = RetryBackoff()
    private var retry: Cancellable?
    private var active = false
    private var offline = false
    private var dismissed: Set<String> = []
    private var caret: Int?
    private var visible: UTF16Range?
    /// Bumped by `end()`, so callbacks of an ended session do nothing.
    private var generation = 0

    public init(client: EngineChecking, scheduler: OverlayScheduler, configuration: Configuration = Configuration()) {
        self.client = client
        self.scheduler = scheduler
        self.configuration = configuration
        self.debouncer = Debouncer(delay: configuration.debounce, scheduler: scheduler) { [weak self] in
            self?.sendNext()
        }
    }

    // MARK: Inputs from the shell

    /// The field gained focus (and passed the gate): check at once.
    public func begin(text: String, caret: Int? = nil, visible: UTF16Range? = nil) {
        active = true
        self.caret = caret
        self.visible = visible
        ledger.update(text)
        recompute()
        sendNext()
    }

    /// The field's text changed (an AX notification or a poll). Underlines
    /// in unchanged paragraphs move with their text; those in changed ones
    /// disappear until the writer pauses and the paragraph is re-checked.
    public func textDidChange(_ text: String, caret: Int? = nil, visible: UTF16Range? = nil) {
        guard active else { return }
        if let c = caret { self.caret = c }
        if let v = visible { self.visible = v }
        guard ledger.update(text) else { return }
        if ledger.hasPending { debouncer.poke() }
        recompute()
    }

    /// The caret or the visible range moved (no text change).
    public func focusDidMove(caret: Int?, visible: UTF16Range?) {
        self.caret = caret
        self.visible = visible
    }

    /// Focus left the field, or the writer paused: forget everything.
    public func end() {
        generation += 1
        active = false
        debouncer.cancel()
        retry?.cancel()
        retry = nil
        revisions.abandon()
        ledger = ParagraphLedger()
        dismissed = []
        offline = false
        recompute()
    }

    /// "Not an issue": hidden for the rest of this session (memory only).
    public func dismiss(_ suggestionID: String) {
        dismissed.insert(suggestionID)
        recompute()
    }

    // MARK: Outputs

    public var isActive: Bool { active }
    public var text: String { ledger.snapshot.text }

    /// Suggestions to draw: not dismissed, and Preferences only if asked for.
    public var visibleSuggestions: [PlacedSuggestion] {
        ledger.allSuggestions.filter { s in
            !dismissed.contains(s.id) && (configuration.options.showPreferences || s.category != .preference)
        }
    }

    public func suggestion(withID id: String) -> PlacedSuggestion? {
        visibleSuggestions.first { $0.id == id }
    }

    /// The hover text for the widget: what the state means and what to do.
    public var statusDetail: String? {
        switch state {
        case .offline: return lastError?.userMessage ?? EngineError.unreachable("").userMessage
        case .partial, .issues: return health.reason
        default: return nil
        }
    }

    // MARK: The loop

    private func sendNext() {
        guard active else { return }
        if revisions.isAwaiting { return }   // the reply will call back here
        let batch = ledger.nextBatch(caret: caret, visible: visible,
                                     maxCount: configuration.maxParagraphsPerRequest,
                                     maxCharacters: configuration.maxCharactersPerRequest)
        guard !batch.isEmpty else { recompute(); return }
        retry?.cancel()
        retry = nil
        let revision = revisions.issue()
        ledger.markInFlight(batch.map { $0.id }, revision: revision)
        let request = CheckRequest(
            revision: revision,
            paragraphs: batch.map { ParagraphPayload(id: $0.id, text: $0.text, heading: $0.heading) },
            options: configuration.options)
        let generation = self.generation
        recompute()
        client.check(request) { [weak self] result in
            guard let self = self else { return }
            self.scheduler.deliver { [weak self] in
                self?.handle(result, revision: revision, generation: generation)
            }
        }
    }

    private func handle(_ result: Result<CheckResponse, EngineError>, revision: Int, generation: Int) {
        // A reply for an ended session, or for a request no longer awaited,
        // is stale: drop it.
        guard generation == self.generation, revisions.accept(revision) else { return }
        switch result {
        case .success(let response):
            offline = false
            lastError = nil
            backoff.reset()
            health = response.health
            ledger.apply(response.paragraphs, revision: revision)
            // More to send: go on at once, unless the writer is typing.
            if ledger.hasPending, !debouncer.isPending { sendNext(); return }
        case .failure(let error):
            ledger.revertInFlight(revision: revision)
            offline = true
            lastError = error
            let delay = backoff.nextDelay()
            retry?.cancel()
            retry = scheduler.schedule(after: delay) { [weak self] in
                guard let self = self, generation == self.generation else { return }
                self.retry = nil
                self.sendNext()
            }
        }
        recompute()
    }

    private func recompute() {
        let inputs = StateInputs(
            active: active,
            offline: offline,
            pending: ledger.hasPendingOrInFlight,
            visibleCount: visibleSuggestions.count,
            degraded: health.degraded)
        state = StateMachine.state(for: inputs)
        onUpdate?()
    }

    /// The retry delay that will follow the next failure (for tests and the
    /// widget's hover text).
    public var failuresSoFar: Int { backoff.failures }
}
