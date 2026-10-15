import AppKit
import ApplicationServices
import ResearchlyOverlayCore

@MainActor
protocol FocusTrackerDelegate: AnyObject {
    /// The focused element changed (nil: nothing focused, or another app).
    func focusDidChange(to element: AXUIElement?, in app: NSRunningApplication?)
    /// The watched field's text changed.
    func fieldValueDidChange()
    /// The watched field's selection changed.
    func fieldSelectionDidChange()
    /// The watched field went away.
    func fieldWasDestroyed()
    /// A window of the frontmost app moved or resized.
    func windowGeometryDidChange()
    /// Regular tick while a field is watched: for scrolling (which has no
    /// notification) and covered-window checks.
    func geometryTick()
    /// Regular tick for apps whose notifications are unreliable.
    func pollTick()
}

/// Follows the frontmost app and its focused element with an AXObserver,
/// and the watched field's value and selection. Polls when told to.
@MainActor
final class FocusTracker {
    weak var delegate: FocusTrackerDelegate?

    private(set) var app: NSRunningApplication?
    private(set) var appElement: AXUIElement?
    private(set) var field: AXUIElement?
    private var observer: AXObserver?
    private var workspaceTokens: [NSObjectProtocol] = []
    private var geometryTimer: Timer?
    private var pollTimer: Timer?
    private var enhancedApps: Set<pid_t> = []

    /// Attribute to set on each app element so it exposes its full tree,
    /// chosen per app by the caller (apps-mac.json).
    var enhancementFor: (NSRunningApplication) -> String? = { _ in nil }

    func start() {
        // A busy host must not freeze the overlay for long.
        _ = AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(), 0.5)
        let center = NSWorkspace.shared.notificationCenter
        workspaceTokens.append(center.addObserver(
            forName: NSWorkspace.didActivateApplicationNotification, object: nil, queue: .main
        ) { [weak self] note in
            let app = note.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication
            MainActor.assumeIsolated { self?.attach(to: app) }
        })
        workspaceTokens.append(center.addObserver(
            forName: NSWorkspace.didTerminateApplicationNotification, object: nil, queue: .main
        ) { [weak self] note in
            let app = note.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication
            MainActor.assumeIsolated {
                guard let self = self, let app = app else { return }
                self.enhancedApps.remove(app.processIdentifier)
                if app.processIdentifier == self.app?.processIdentifier { self.attach(to: nil) }
            }
        })
        attach(to: NSWorkspace.shared.frontmostApplication)
    }

    func stop() {
        let center = NSWorkspace.shared.notificationCenter
        workspaceTokens.forEach { center.removeObserver($0) }
        workspaceTokens.removeAll()
        attach(to: nil)
    }

    /// Re-reads the focused element (after a pause ends, or settings change).
    func refresh() {
        attach(to: NSWorkspace.shared.frontmostApplication)
    }

    // MARK: App

    private func attach(to newApp: NSRunningApplication?) {
        unwatchField()
        if let obs = observer {
            CFRunLoopRemoveSource(CFRunLoopGetMain(), AXObserverGetRunLoopSource(obs), .commonModes)
        }
        observer = nil
        appElement = nil
        app = nil

        guard let newApp = newApp, newApp.processIdentifier != getpid() else {
            delegate?.focusDidChange(to: nil, in: nil)
            return
        }
        app = newApp
        let pid = newApp.processIdentifier
        let element = AXUIElementCreateApplication(pid)
        appElement = element

        if let attribute = enhancementFor(newApp), !enhancedApps.contains(pid) {
            AX.set(element, attribute, kCFBooleanTrue)
            enhancedApps.insert(pid)
        }

        var created: AXObserver?
        if AXObserverCreate(pid, focusTrackerCallback, &created) == .success, let obs = created {
            observer = obs
            CFRunLoopAddSource(CFRunLoopGetMain(), AXObserverGetRunLoopSource(obs), .commonModes)
            let refcon = Unmanaged.passUnretained(self).toOpaque()
            for name in [AX.focusedUIElementChanged, AX.focusedWindowChanged, AX.windowMoved, AX.windowResized] {
                _ = AXObserverAddNotification(obs, element, name as CFString, refcon)
            }
        }
        focusedElementChanged()
    }

    private func focusedElementChanged() {
        guard let appElement = appElement else { return }
        let focused = AX.element(appElement, AX.focusedUIElement)
            ?? AX.element(AXUIElementCreateSystemWide(), AX.focusedUIElement)
        if let f = focused, let current = field, CFEqual(f, current) { return }
        delegate?.focusDidChange(to: focused, in: app)
    }

    // MARK: Field

    /// Starts following one field's value and selection. Returns false if
    /// the app sends no notifications for it (the caller should poll).
    @discardableResult
    func watch(_ element: AXUIElement, poll: Bool) -> Bool {
        unwatchField()
        field = element
        var notified = false
        if let obs = observer {
            let refcon = Unmanaged.passUnretained(self).toOpaque()
            for name in [AX.valueChanged, AX.selectedTextChanged, AX.elementDestroyed] {
                let err = AXObserverAddNotification(obs, element, name as CFString, refcon)
                if name == AX.valueChanged { notified = (err == .success || err == .notificationAlreadyRegistered) }
            }
        }
        geometryTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.delegate?.geometryTick() }
        }
        if poll || !notified {
            pollTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
                MainActor.assumeIsolated { self?.delegate?.pollTick() }
            }
        }
        return notified
    }

    func unwatchField() {
        if let obs = observer, let f = field {
            for name in [AX.valueChanged, AX.selectedTextChanged, AX.elementDestroyed] {
                _ = AXObserverRemoveNotification(obs, f, name as CFString)
            }
        }
        field = nil
        geometryTimer?.invalidate()
        geometryTimer = nil
        pollTimer?.invalidate()
        pollTimer = nil
    }

    // MARK: Notifications

    fileprivate func handle(_ notification: String, element: AXUIElement) {
        switch notification {
        case AX.focusedUIElementChanged, AX.focusedWindowChanged:
            focusedElementChanged()
        case AX.valueChanged:
            if let f = field, CFEqual(f, element) { delegate?.fieldValueDidChange() }
        case AX.selectedTextChanged:
            if let f = field, CFEqual(f, element) { delegate?.fieldSelectionDidChange() }
        case AX.elementDestroyed:
            if let f = field, CFEqual(f, element) {
                unwatchField()
                delegate?.fieldWasDestroyed()
            }
        case AX.windowMoved, AX.windowResized:
            delegate?.windowGeometryDidChange()
        default:
            break
        }
    }
}

/// The AXObserver callback. Runs on the main run loop (the observer's
/// source is added there), so hopping onto the main actor is safe.
private let focusTrackerCallback: AXObserverCallback = { _, element, notification, refcon in
    guard let refcon = refcon else { return }
    let name = notification as String
    let tracker = Unmanaged<FocusTracker>.fromOpaque(refcon).takeUnretainedValue()
    MainActor.assumeIsolated {
        tracker.handle(name, element: element)
    }
}
