import AppKit

/// Explains why Accessibility is needed before macOS asks for it, then
/// waits for the permission. (There is no Info.plist usage string for
/// Accessibility; this window is where the reason is given.)
@MainActor
final class OnboardingWindow: NSObject, NSWindowDelegate {
    private var window: NSWindow?
    private var timer: Timer?
    private var targets: [ActionTarget] = []
    var onTrusted: (() -> Void)?

    func show() {
        if let w = window {
            NSApp.activate()
            w.makeKeyAndOrderFront(nil)
            return
        }
        let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 480, height: 360),
                         styleMask: [.titled, .closable], backing: .buffered, defer: false)
        w.title = "Researchly Overlay"
        w.isReleasedWhenClosed = false
        w.delegate = self

        let title = NSTextField(labelWithString: "Researchly needs to read the text field you are writing in")
        title.font = .systemFont(ofSize: 15, weight: .semibold)
        title.lineBreakMode = .byWordWrapping
        title.maximumNumberOfLines = 0
        title.preferredMaxLayoutWidth = 420

        let paragraphs = [
            "To underline suggestions where you write, Researchly uses macOS Accessibility. It reads the text of the field that has focus, asks where its words are on screen, and, only when you click Accept, changes the words you chose.",
            "It never reads password fields or fields whose label asks for private details such as a card number, a one-time code or a login. Terminals, password managers and code editors are left alone.",
            "The text goes only to the engine you choose in the menu bar: this computer, or the hosted engine you name. Nothing is stored on this Mac except your settings.",
            "Next, macOS will ask you to allow Researchly Overlay in System Settings → Privacy & Security → Accessibility. Each new build of this app must be allowed again, because it is signed on your Mac rather than by a developer certificate.",
        ]
        var views: [NSView] = [title]
        for p in paragraphs {
            let l = NSTextField(wrappingLabelWithString: p)
            l.font = .systemFont(ofSize: 12.5)
            l.preferredMaxLayoutWidth = 420
            l.isSelectable = false
            views.append(l)
        }

        let allow = NSButton(title: "Continue", target: nil, action: nil)
        allow.bezelStyle = .push
        allow.keyEquivalent = "\r"
        let allowTarget = ActionTarget { [weak self] in self?.requestPermission() }
        allow.target = allowTarget
        allow.action = #selector(ActionTarget.fire(_:))
        let later = NSButton(title: "Not now", target: nil, action: nil)
        later.bezelStyle = .push
        let laterTarget = ActionTarget { [weak self] in self?.window?.close() }
        later.target = laterTarget
        later.action = #selector(ActionTarget.fire(_:))
        targets = [allowTarget, laterTarget]
        let buttons = NSStackView(views: [later, allow])
        buttons.orientation = .horizontal
        buttons.spacing = 8
        views.append(buttons)

        let stack = NSStackView(views: views)
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 12
        stack.edgeInsets = NSEdgeInsets(top: 24, left: 28, bottom: 24, right: 28)
        stack.translatesAutoresizingMaskIntoConstraints = false
        let container = NSView()
        container.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: container.leadingAnchor),
            stack.trailingAnchor.constraint(equalTo: container.trailingAnchor),
            stack.topAnchor.constraint(equalTo: container.topAnchor),
            stack.bottomAnchor.constraint(equalTo: container.bottomAnchor),
            stack.widthAnchor.constraint(equalToConstant: 476),
        ])
        w.contentView = container
        container.layoutSubtreeIfNeeded()
        w.setContentSize(container.fittingSize)
        w.center()
        window = w
        NSApp.activate()
        w.makeKeyAndOrderFront(nil)
    }

    private func requestPermission() {
        AX.requestTrust()
        NSWorkspace.shared.open(AX.settingsURL)
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self = self, AX.isTrusted else { return }
                self.timer?.invalidate()
                self.timer = nil
                self.window?.close()
                self.onTrusted?()
            }
        }
    }

    func windowWillClose(_ notification: Notification) {
        // Keep waiting for the permission even if the window is closed.
    }
}
