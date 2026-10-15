import AppKit
import ResearchlyOverlayCore

/// The menu-bar item: state, pause, engine choice, the Accessibility
/// permission, the field diagnostics, and Quit.
@MainActor
final class StatusMenu: NSObject, NSMenuDelegate {
    private let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let menu = NSMenu()
    private let settings: Settings
    private weak var controller: OverlayController?
    private var status = OverlayStatus(state: .hidden, count: 0, detail: nil, appName: nil, paused: false)
    private var targets: [ActionTarget] = []
    /// Called when the engine or the check options change.
    var onSettingsChanged: (() -> Void)?
    var onShowOnboarding: (() -> Void)?

    init(settings: Settings, controller: OverlayController?) {
        self.settings = settings
        self.controller = controller
        super.init()
        menu.delegate = self
        menu.autoenablesItems = false
        item.menu = menu
        updateButton()
    }

    func attach(_ controller: OverlayController) {
        self.controller = controller
    }

    func update(_ status: OverlayStatus) {
        self.status = status
        updateButton()
    }

    private func updateButton() {
        guard let button = item.button else { return }
        let symbol: String
        switch status.paused ? OverlayState.hidden : status.state {
        case .hidden: symbol = status.paused ? "pause.circle" : "text.cursor"
        case .checking: symbol = "ellipsis.circle"
        case .issues: symbol = "exclamationmark.circle"
        case .clear: symbol = "checkmark.circle"
        case .partial: symbol = "exclamationmark.triangle"
        case .offline: symbol = "wifi.exclamationmark"
        }
        let image = Appearance.symbol(symbol, label: "Researchly")
        image?.isTemplate = true
        button.image = image
        button.imagePosition = .imageLeading
        button.title = status.state == .issues && !status.paused ? " \(status.count)" : ""
        button.toolTip = "Researchly — \(statusLine)"
        button.setAccessibilityLabel("Researchly: \(statusLine)")
    }

    private var statusLine: String {
        if !AX.isTrusted { return "needs Accessibility permission" }
        if status.paused { return "Paused" }
        switch status.state {
        case .hidden: return "Not checking this field"
        case .issues: return "\(status.count) suggestion\(status.count == 1 ? "" : "s")"
        default: return status.state.title
        }
    }

    // MARK: Building the menu each time it opens

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        targets = []

        menu.addItem(disabled("Researchly — \(statusLine)"))
        if let detail = status.detail { menu.addItem(disabled(detail)) }
        menu.addItem(.separator())

        // Pause
        let pause = settings.pause
        let now = Date()
        if let until = pause.until, now < until {
            let f = DateFormatter()
            f.dateStyle = .none
            f.timeStyle = .short
            menu.addItem(disabled("Paused until \(f.string(from: until))"))
            menu.addItem(action("Resume") { [weak self] in self?.controller?.resume() })
        } else {
            menu.addItem(action("Pause for 1 hour") { [weak self] in self?.controller?.pause(for: 3600) })
            menu.addItem(action("Pause until tomorrow") { [weak self] in self?.controller?.pauseUntilTomorrow() })
        }
        if let app = controller?.currentAppName, let id = controller?.currentBundleID {
            let paused = pause.pausedApps.contains(id)
            let entry = action(paused ? "Resume in \(app)" : "Pause in \(app)") { [weak self] in
                self?.controller?.pauseCurrentApp()
            }
            menu.addItem(entry)
        }
        if !pause.pausedApps.isEmpty {
            let sub = NSMenu()
            for id in pause.pausedApps.sorted() {
                sub.addItem(action("Resume in \(id)") { [weak self] in
                    guard let self = self else { return }
                    var p = self.settings.pause
                    p.toggle(app: id)
                    self.settings.pause = p
                    self.onSettingsChanged?()
                })
            }
            let holder = NSMenuItem(title: "Paused apps", action: nil, keyEquivalent: "")
            holder.submenu = sub
            menu.addItem(holder)
        }
        menu.addItem(.separator())

        // Engine
        menu.addItem(disabled("Check with"))
        let engine = settings.engine
        let local = action("This computer (127.0.0.1:3517)") { [weak self] in
            self?.settings.engine = .thisComputer
            self?.onSettingsChanged?()
        }
        local.state = engine == .thisComputer ? .on : .off
        local.indentationLevel = 1
        menu.addItem(local)
        let hostedTitle: String
        if case .hosted(let url) = engine { hostedTitle = "Hosted: \(url.host ?? url.absoluteString)" }
        else if let last = settings.lastHostedURL, let url = URL(string: last) { hostedTitle = "Hosted: \(url.host ?? last)" }
        else { hostedTitle = "Hosted engine…" }
        let hosted = action(hostedTitle) { [weak self] in self?.chooseHosted() }
        if case .hosted = engine { hosted.state = .on }
        hosted.indentationLevel = 1
        menu.addItem(hosted)
        if settings.lastHostedURL != nil {
            let change = action("Change hosted address…") { [weak self] in self?.askForHostedURL() }
            change.indentationLevel = 1
            menu.addItem(change)
        }
        let prefs = action("Show Preference suggestions") { [weak self] in
            guard let self = self else { return }
            self.settings.showPreferences.toggle()
            self.onSettingsChanged?()
        }
        prefs.state = settings.showPreferences ? .on : .off
        menu.addItem(prefs)
        menu.addItem(.separator())

        // Permission
        if AX.isTrusted {
            menu.addItem(disabled("Accessibility: allowed"))
        } else {
            menu.addItem(disabled("Accessibility: not allowed"))
            menu.addItem(action("Open Accessibility settings…") { NSWorkspace.shared.open(AX.settingsURL) })
            menu.addItem(action("Why Researchly needs it…") { [weak self] in self?.onShowOnboarding?() })
        }
        menu.addItem(action("About this field…") { [weak self] in self?.showFieldInfo() })
        menu.addItem(.separator())
        menu.addItem(action("Quit Researchly Overlay") { NSApp.terminate(nil) })
    }

    private func disabled(_ title: String) -> NSMenuItem {
        let i = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        i.isEnabled = false
        return i
    }

    private func action(_ title: String, _ block: @escaping () -> Void) -> NSMenuItem {
        let t = ActionTarget(block)
        targets.append(t)
        let i = NSMenuItem(title: title, action: #selector(ActionTarget.fire(_:)), keyEquivalent: "")
        i.target = t
        i.isEnabled = true
        return i
    }

    // MARK: Engine choice

    private func chooseHosted() {
        if let raw = settings.lastHostedURL, let url = EngineChoice.validatedHostedURL(raw) {
            settings.engine = .hosted(url)
            onSettingsChanged?()
        } else {
            askForHostedURL()
        }
    }

    private func askForHostedURL() {
        NSApp.activate()
        let alert = NSAlert()
        alert.messageText = "Hosted engine address"
        alert.informativeText = "The address of the Researchly engine to check with, starting with https://. The text of the field you are writing in is sent there and nowhere else."
        let input = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 24))
        input.placeholderString = "https://"
        input.stringValue = settings.lastHostedURL ?? ""
        alert.accessoryView = input
        alert.addButton(withTitle: "Use this engine")
        alert.addButton(withTitle: "Cancel")
        alert.window.initialFirstResponder = input
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        guard let url = EngineChoice.validatedHostedURL(input.stringValue) else {
            let bad = NSAlert()
            bad.messageText = "That address can’t be used"
            bad.informativeText = "A hosted engine must start with https:// (plain http is allowed only for this computer)."
            bad.runModal()
            return
        }
        settings.engine = .hosted(url)
        onSettingsChanged?()
    }

    // MARK: Diagnostics (no text)

    private func showFieldInfo() {
        NSApp.activate()
        let alert = NSAlert()
        alert.messageText = "About this field"
        var lines: [String] = []
        if let info = controller?.lastDecision {
            let (d, decision) = info
            lines.append("App: \(d.bundleID ?? "unknown")")
            lines.append("Role: \(d.role)\(d.subrole.map { " / \($0)" } ?? "")")
            lines.append("Editable: \(d.isEditable ? "yes" : "no")")
            switch decision {
            case .eligible(let rule):
                lines.append("Checked: yes (\(rule.name))")
                lines.append("Write-back: \(rule.writeBack.map { $0.rawValue }.joined(separator: " → "))")
            case .ineligible(let reason):
                lines.append("Checked: no. \(reason)")
            }
        } else {
            lines.append("No text field has been focused yet.")
        }
        lines.append("")
        lines.append("This shows only the kind of field, never its text. To add or change an app, edit apps-mac.json (see the README).")
        alert.informativeText = lines.joined(separator: "\n")
        alert.runModal()
    }
}
