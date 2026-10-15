import AppKit
import ApplicationServices
import ResearchlyOverlayCore

/// The focused field the overlay is attached to.
struct ActiveField {
    let element: AXUIElement
    let app: NSRunningApplication
    let rule: AppRule

    var bundleID: String? { app.bundleIdentifier }
    var pid: pid_t { app.processIdentifier }
    var appName: String { app.localizedName ?? rule.name }
}

/// What the menu bar shows.
struct OverlayStatus: Equatable {
    var state: OverlayState
    var count: Int
    var detail: String?
    var appName: String?
    var paused: Bool
}

/// Ties the loop together (design note §6): capture → gate → wait → check
/// → measure → draw → hover → write back. One field at a time.
@MainActor
final class OverlayController: FocusTrackerDelegate, FieldWidgetDelegate {
    let settings: Settings
    let gate: EligibilityGate
    var onStatus: ((OverlayStatus) -> Void)?

    private let tracker = FocusTracker()
    private let underlines = UnderlineOverlay()
    private let widget = FieldWidget()
    private let teaser = TeaserPanel()
    private let card = CardPanel()
    private let writeBack = WriteBack()

    private var field: ActiveField?
    /// A field refused only for its length (empty): watched, so typing in
    /// it can make it eligible.
    private var waitingField: ActiveField?
    private var session: LiveCheckSession?
    private var client: EngineClient?
    private(set) var lastDecision: (FieldDescriptor, EligibilityDecision)?

    /// Line rectangles per suggestion id, AX space, from the last layout.
    private var hitRects: [String: [CGRect]] = [:]
    private var layoutSignature = ""
    private var hoverID: String?
    private var hoverTimer: Timer?
    private var hideTimer: Timer?
    private var monitors: [Any] = []
    private var observers: [NSObjectProtocol] = []
    private var pauseTimer: Timer?
    private var lastStatus: OverlayStatus?
    private var menuTargets: [ActionTarget] = []
    private var wasPausedEverywhere = false

    init(settings: Settings, gate: EligibilityGate) {
        self.settings = settings
        self.gate = gate
        tracker.delegate = self
        tracker.enhancementFor = { [gate] app in gate.appRules.rule(for: app.bundleIdentifier).enhancedAccessibility }
        widget.delegate = self
        teaser.onOpen = { [weak self] id in self?.openCard(id) }
        card.onAction = { [weak self] id, action in self?.cardAction(id, action) }
    }

    // MARK: Lifecycle

    func start() {
        wasPausedEverywhere = settings.pause.isPausedEverywhere(now: Date())
        tracker.start()
        if let m = NSEvent.addGlobalMonitorForEvents(matching: [.mouseMoved, .leftMouseDown], handler: { [weak self] event in
            let type = event.type
            MainActor.assumeIsolated { self?.globalMouse(type) }
        }) { monitors.append(m) }
        let nc = NotificationCenter.default
        observers.append(nc.addObserver(forName: NSApplication.didChangeScreenParametersNotification,
                                        object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.relayout(force: true) }
        })
        observers.append(NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.activeSpaceDidChangeNotification, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.relayout(force: true) }
        })
        // A timed pause ends by itself: look again every half minute.
        pauseTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.pauseTick() }
        }
        publishStatus()
    }

    func stop() {
        tracker.stop()
        monitors.forEach { NSEvent.removeMonitor($0) }
        monitors.removeAll()
        observers.forEach { NotificationCenter.default.removeObserver($0) }
        observers.removeAll()
        pauseTimer?.invalidate()
        endField()
    }

    /// Settings changed (engine, preferences, pause): start again from the
    /// focused element.
    func restart() {
        endField()
        tracker.refresh()
    }

    var currentAppName: String? { field?.appName ?? waitingField?.appName ?? tracker.app?.localizedName }
    var currentBundleID: String? { field?.bundleID ?? waitingField?.bundleID ?? tracker.app?.bundleIdentifier }

    // MARK: Focus

    func focusDidChange(to element: AXUIElement?, in app: NSRunningApplication?) {
        endField()
        guard let element = element, let app = app else { return }
        let now = Date()
        if settings.pause.isPaused(bundleID: app.bundleIdentifier, now: now) { publishStatus(); return }

        var descriptor = FieldReader.describe(element, bundleID: app.bundleIdentifier)
        var decision = gate.evaluate(descriptor)
        if decision.isEligible {
            // Only now is the field asked for anything about its contents.
            descriptor.characterCount = FieldReader.characterCount(element)
                ?? FieldReader.text(element)?.utf16.count
            decision = gate.evaluate(descriptor)
        }
        lastDecision = (descriptor, decision)
        let rule = gate.appRules.rule(for: app.bundleIdentifier)
        switch decision {
        case .eligible(let rule):
            beginField(ActiveField(element: element, app: app, rule: rule))
        case .ineligible(let reason) where reason.dependsOnLength:
            let waiting = ActiveField(element: element, app: app, rule: rule)
            waitingField = waiting
            tracker.watch(element, poll: rule.needsPolling)
            publishStatus()
        case .ineligible:
            publishStatus()
        }
    }

    private func beginField(_ f: ActiveField) {
        field = f
        waitingField = nil
        let client = EngineClient(choice: settings.engine)
        self.client = client
        let session = LiveCheckSession(
            client: client, scheduler: MainQueueScheduler(),
            configuration: .forApp(f.rule, options: settings.checkOptions))
        session.onUpdate = { [weak self] in self?.sessionDidUpdate() }
        self.session = session
        tracker.watch(f.element, poll: f.rule.needsPolling)
        session.begin(text: FieldReader.text(f.element) ?? "",
                      caret: FieldReader.selection(f.element)?.location,
                      visible: FieldReader.visibleCharacters(f.element))
        if !settings.dragTipShown {
            settings.dragTipShown = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { [weak self] in
                MainActor.assumeIsolated {
                    guard let self = self, self.widget.isVisible else { return }
                    self.widget.showDragTip()
                }
            }
        }
    }

    /// Leaves the field: everything about it is forgotten.
    func endField() {
        session?.onUpdate = nil
        session?.end()
        session = nil
        client = nil
        field = nil
        waitingField = nil
        tracker.unwatchField()
        hitRects = [:]
        layoutSignature = ""
        hoverID = nil
        hoverTimer?.invalidate()
        hideTimer?.invalidate()
        underlines.hide()
        widget.hide()
        teaser.hide()
        card.hide()
        publishStatus()
    }

    // MARK: Tracker events

    func fieldValueDidChange() {
        if let waiting = waitingField {
            // An empty field may have become checkable.
            let count = FieldReader.characterCount(waiting.element) ?? 0
            if count >= gate.fieldRules.minFieldCharacters, count <= gate.fieldRules.maxFieldCharacters {
                beginField(ActiveField(element: waiting.element, app: waiting.app, rule: waiting.rule))
            }
            return
        }
        guard let f = field, let session = session else { return }
        guard let text = FieldReader.text(f.element) else { return }
        if text.utf16.count > gate.fieldRules.maxFieldCharacters { endField(); return }
        if card.isVisible { card.hide() }
        teaser.hide()
        session.textDidChange(text, caret: FieldReader.selection(f.element)?.location,
                              visible: FieldReader.visibleCharacters(f.element))
    }

    func fieldSelectionDidChange() {
        guard let f = field, let session = session else { return }
        session.focusDidMove(caret: FieldReader.selection(f.element)?.location,
                             visible: FieldReader.visibleCharacters(f.element))
    }

    func fieldWasDestroyed() { endField() }

    func windowGeometryDidChange() { relayout(force: true) }

    func geometryTick() { relayout(force: false) }

    func pollTick() {
        if waitingField != nil { fieldValueDidChange(); return }
        guard let f = field, let session = session else { return }
        // Cheap first: the length. Then the text, which catches same-length edits.
        if let text = FieldReader.text(f.element), text != session.text { fieldValueDidChange() }
    }

    private func pauseTick() {
        let now = Date()
        let everywhere = settings.pause.isPausedEverywhere(now: now)
        if everywhere, field != nil { endField() }
        if wasPausedEverywhere, !everywhere { tracker.refresh() }   // the timed pause is over
        wasPausedEverywhere = everywhere
        publishStatus()
    }

    // MARK: Session → screen

    private func sessionDidUpdate() {
        relayout(force: false)
        publishStatus()
    }

    /// Measures and draws. Cheap when nothing moved: a signature of the
    /// geometry and the suggestions decides whether to measure again.
    func relayout(force: Bool) {
        guard let f = field, let session = session else { return }
        guard NSWorkspace.shared.frontmostApplication?.processIdentifier == f.pid,
              let visible = FieldReader.visibleFrame(f.element) else {
            hideOverlays()
            return
        }
        if WindowStacking.isCovered(visible, hostPID: f.pid) {
            hideOverlays()
            return
        }
        let dark = Appearance.isDark
        let suggestions = session.visibleSuggestions
        let visibleChars = FieldReader.visibleCharacters(f.element)
        let signature = [
            "\(AX.frame(f.element).map { "\($0)" } ?? "-")", "\(visible)", "\(visibleChars.map { "\($0)" } ?? "-")", "\(dark)", "\(session.state)",
            suggestions.map { "\($0.id)@\($0.range)" }.joined(separator: ","),
            "\(Appearance.primaryHeight)",
            // Text before a suggestion can reflow its line without moving its offsets.
            "\(session.text.hashValue)",
        ].joined(separator: "|")
        if !force, signature == layoutSignature, widget.isVisible || session.state == .hidden { return }
        layoutSignature = signature

        // Measure each suggestion in view, one rectangle per line, clipped.
        let length = session.text.utf16.count
        var rects: [String: [CGRect]] = [:]
        for s in suggestions {
            if let vc = visibleChars, !s.range.intersects(vc), !vc.contains(s.range.location) { continue }
            let lines = OverlayGeometry.clip(TextGeometry.lineRects(for: s.range, in: f.element, textLength: length),
                                             to: visible)
            if !lines.isEmpty { rects[s.id] = lines }
        }
        hitRects = rects

        let screenFrame = Appearance.toScreen(visible)
        let marks: [UnderlineMark] = suggestions.compactMap { s in
            guard let lines = rects[s.id] else { return nil }
            let local = lines.map { r -> CGRect in
                let sr = Appearance.toScreen(r)
                return sr.offsetBy(dx: -screenFrame.minX, dy: -screenFrame.minY)
            }
            return UnderlineMark(id: s.id, category: s.category, rects: local)
        }
        underlines.show(over: screenFrame, marks: marks, highlighted: teaser.suggestionID ?? card.suggestionID, dark: dark)

        let origin = OverlayGeometry.widgetOrigin(field: visible, widget: FieldWidget.size,
                                                  placement: f.rule.widget,
                                                  userOffset: settings.widgetOffset(for: f.bundleID))
        widget.show(atAX: origin, state: session.state, count: suggestions.count, detail: session.statusDetail)
    }

    private func hideOverlays() {
        layoutSignature = ""
        underlines.hide()
        widget.hide()
        teaser.hide()
        if card.isVisible { card.hide() }
    }

    // MARK: Mouse

    private func globalMouse(_ type: NSEvent.EventType) {
        guard field != nil else { return }
        let screenPoint = NSEvent.mouseLocation
        let ax = Appearance.toAX(screenPoint)
        let hit = hitRects.first { OverlayGeometry.hitTest(ax, rects: $0.value, slop: 3) }?.key

        if type == .leftMouseDown {
            if card.isVisible, !card.screenFrame.contains(screenPoint) { card.hide() }
            if let id = hit {
                // The host gets the click too (its caret moves there); the
                // card opens beside it.
                openCard(id)
            }
            return
        }

        // Mouse moved.
        if teaser.isVisible, teaser.screenFrame.insetBy(dx: -6, dy: -6).contains(screenPoint) {
            hideTimer?.invalidate()
            return
        }
        if hit != hoverID {
            hoverID = hit
            hoverTimer?.invalidate()
            if let id = hit {
                hideTimer?.invalidate()
                hoverTimer = Timer.scheduledTimer(withTimeInterval: 0.3, repeats: false) { [weak self] _ in
                    MainActor.assumeIsolated { self?.showTeaser(id) }
                }
            }
        }
        // Off every underline and off the teaser: let the teaser go after a
        // moment. (Moves over the teaser itself reach no global monitor, so
        // the timer looks at where the mouse is when it fires.)
        if hit == nil, teaser.isVisible, teaser.suggestionID != nil, !(hideTimer?.isValid ?? false) {
            hideTimer = Timer.scheduledTimer(withTimeInterval: 0.35, repeats: false) { [weak self] _ in
                MainActor.assumeIsolated {
                    guard let self = self else { return }
                    if !self.teaser.screenFrame.insetBy(dx: -6, dy: -6).contains(NSEvent.mouseLocation) {
                        self.teaser.hide()
                        self.relayout(force: true)
                    }
                }
            }
        }
    }

    private func anchor(for id: String) -> CGRect? {
        guard let rects = hitRects[id], let first = rects.first else { return nil }
        return Appearance.toScreen(rects.dropFirst().reduce(first) { $0.union($1) })
    }

    private func showTeaser(_ id: String) {
        guard !card.isVisible, let s = session?.suggestion(withID: id), let a = anchor(for: id) else { return }
        teaser.show(s, near: a)
        relayout(force: true)   // tint the hovered range
    }

    private func openCard(_ id: String, note: String? = nil) {
        guard let s = session?.suggestion(withID: id), let a = anchor(for: id) else { return }
        teaser.hide()
        card.show(s, near: a, note: note)
        relayout(force: true)
    }

    private func cardAction(_ id: String, _ action: CardAction) {
        switch action {
        case .close:
            card.hide()
            relayout(force: true)
        case .dismiss:
            card.hide()
            session?.dismiss(id)
        case .accept(let replacement):
            guard let f = field, let s = session?.suggestion(withID: id) else { card.hide(); return }
            writeBack.apply(replacement: replacement, range: s.range, expected: s.flaggedText,
                            in: f.element, methods: f.rule.writeBack) { [weak self] outcome in
                guard let self = self else { return }
                switch outcome {
                case .applied:
                    self.card.hide()
                    self.fieldValueDidChange()
                case .textChanged:
                    self.openCard(id, note: "The text here has changed. Researchly will check it again after a pause.")
                case .uncertain:
                    self.card.hide()
                    self.fieldValueDidChange()
                    self.showStatusNote("Please check the change", "The text changed, but not exactly as expected. Cmd-Z in the app undoes it.")
                case .failed:
                    self.openCard(id, note: "This app didn’t accept the change. You can type it yourself: “\(replacement)”.")
                }
            }
        }
    }

    private func showStatusNote(_ title: String, _ detail: String) {
        teaser.showStatus(title: title, detail: detail, near: widget.screenFrame)
        hideTimer?.invalidate()
        hideTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: false) { [weak self] _ in
            MainActor.assumeIsolated { self?.teaser.hide() }
        }
    }

    // MARK: Widget

    func widgetClicked(_ widget: FieldWidget, view: NSView) {
        guard let session = session else { return }
        let menu = NSMenu()
        menu.autoenablesItems = false
        let list = session.visibleSuggestions
        let header = NSMenuItem(title: list.isEmpty ? session.state.title
                                                    : "\(list.count) suggestion\(list.count == 1 ? "" : "s")",
                                action: nil, keyEquivalent: "")
        header.isEnabled = false
        menu.addItem(header)
        var targets: [ActionTarget] = []
        for s in list.prefix(12) {
            let style = Tokens.category(s.category)
            let text = s.suggestion.message.isEmpty ? s.flaggedText : s.suggestion.message
            let item = NSMenuItem(title: "\(style.name): \(text)", action: #selector(ActionTarget.fire(_:)), keyEquivalent: "")
            item.image = Appearance.symbol(style.symbol, label: style.name)
            let id = s.id
            let t = ActionTarget { [weak self] in self?.openCard(id) }
            item.target = t
            targets.append(t)
            menu.addItem(item)
        }
        if let detail = session.statusDetail {
            menu.addItem(.separator())
            let d = NSMenuItem(title: detail, action: nil, keyEquivalent: "")
            d.isEnabled = false
            menu.addItem(d)
        }
        menu.addItem(.separator())
        let name = field?.appName ?? "this app"
        let pauseApp = NSMenuItem(title: "Pause in \(name)", action: #selector(ActionTarget.fire(_:)), keyEquivalent: "")
        let t1 = ActionTarget { [weak self] in self?.pauseCurrentApp() }
        pauseApp.target = t1
        targets.append(t1)
        menu.addItem(pauseApp)
        let pauseHour = NSMenuItem(title: "Pause for 1 hour", action: #selector(ActionTarget.fire(_:)), keyEquivalent: "")
        let t2 = ActionTarget { [weak self] in self?.pause(for: 3600) }
        pauseHour.target = t2
        targets.append(t2)
        menu.addItem(pauseHour)
        // NSMenuItem holds its target weakly: keep them alive while the menu is open.
        menuTargets = targets
        menu.popUp(positioning: nil, at: NSPoint(x: 0, y: view.bounds.height + 4), in: view)
    }

    func widgetDragged(by offset: CGPoint) {
        let previous = settings.widgetOffset(for: field?.bundleID) ?? .zero
        settings.setWidgetOffset(CGPoint(x: previous.x + offset.x, y: previous.y + offset.y), for: field?.bundleID)
        relayout(force: true)
    }

    func widgetHover(_ inside: Bool) {
        guard let session = session else { return }
        if inside, let detail = session.statusDetail, session.state == .offline || session.state == .partial {
            teaser.showStatus(title: session.state.title, detail: detail, near: widget.screenFrame)
        } else if !inside, teaser.suggestionID == nil {
            teaser.hide()
        }
    }

    // MARK: Pause

    func pause(for seconds: TimeInterval) {
        var p = settings.pause
        p.pause(for: seconds, now: Date())
        settings.pause = p
        wasPausedEverywhere = true
        endField()
    }

    func pauseUntilTomorrow() {
        var p = settings.pause
        p.pauseUntilTomorrow(now: Date())
        settings.pause = p
        wasPausedEverywhere = true
        endField()
    }

    func pauseCurrentApp() {
        guard let id = currentBundleID else { return }
        var p = settings.pause
        p.toggle(app: id)
        settings.pause = p
        restart()
    }

    func resume() {
        var p = settings.pause
        p.resume()
        settings.pause = p
        wasPausedEverywhere = false
        restart()
    }

    // MARK: Status

    private func publishStatus() {
        let paused = settings.pause.isPaused(bundleID: currentBundleID, now: Date())
        let status = OverlayStatus(
            state: session?.state ?? .hidden,
            count: session?.visibleSuggestions.count ?? 0,
            detail: session?.statusDetail,
            appName: currentAppName,
            paused: paused)
        if status != lastStatus {
            lastStatus = status
            onStatus?(status)
        }
    }
}

/// Is the field hidden behind another app's window? Window bounds from the
/// window server use the same top-left space as Accessibility. Needs no
/// screen-recording permission: only owners, layers, alpha and bounds are
/// read, never window titles or contents.
enum WindowStacking {
    static func isCovered(_ fieldRect: CGRect, hostPID: pid_t) -> Bool {
        guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
                as? [[String: Any]] else { return false }
        let me = getpid()
        for info in list {   // front to back
            guard let pid = info[kCGWindowOwnerPID as String] as? Int32,
                  let boundsDict = info[kCGWindowBounds as String] as? NSDictionary,
                  let bounds = CGRect(dictionaryRepresentation: boundsDict as CFDictionary),
                  bounds.intersects(fieldRect) else { continue }
            let layer = info[kCGWindowLayer as String] as? Int ?? 0
            let alpha = info[kCGWindowAlpha as String] as? Double ?? 1
            if pid == me || alpha < 0.05 { continue }
            // The first of the host's own windows over the field is the
            // field's window (or the host's own popover on it): not covered.
            if pid == hostPID { return false }
            // System chrome (menu bar, Dock, screen-wide layers) is ignored.
            if layer < 0 || layer >= 20 { continue }
            return true
        }
        return false
    }
}
