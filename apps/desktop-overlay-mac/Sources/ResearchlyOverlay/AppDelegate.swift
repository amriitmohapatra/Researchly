import AppKit
import ResearchlyOverlayCore

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let settings = Settings()
    private var controller: OverlayController?
    private var statusMenu: StatusMenu?
    private let onboarding = OnboardingWindow()
    private var trustTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = StatusMenu(settings: settings, controller: nil)
        statusMenu = menu
        menu.onShowOnboarding = { [weak self] in self?.onboarding.show() }

        let gate: EligibilityGate
        do {
            gate = try RulesLoader.loadGate()
        } catch {
            let alert = NSAlert()
            alert.messageText = "Researchly Overlay can’t start"
            alert.informativeText = "Its rules files (fields.json and apps-mac.json) are missing or unreadable. Rebuild the app with build.sh, which copies them into the app."
            NSApp.activate()
            alert.runModal()
            NSApp.terminate(nil)
            return
        }

        let controller = OverlayController(settings: settings, gate: gate)
        self.controller = controller
        menu.attach(controller)
        controller.onStatus = { [weak menu] status in menu?.update(status) }
        menu.onSettingsChanged = { [weak controller] in controller?.restart() }

        onboarding.onTrusted = { [weak self] in self?.startWhenTrusted() }
        if AX.isTrusted {
            startWhenTrusted()
        } else {
            onboarding.show()
            // Also notice a permission granted from System Settings directly.
            trustTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
                MainActor.assumeIsolated {
                    guard let self = self, AX.isTrusted else { return }
                    self.startWhenTrusted()
                }
            }
        }
    }

    private var started = false

    private func startWhenTrusted() {
        trustTimer?.invalidate()
        trustTimer = nil
        guard !started, let controller = controller else { return }
        started = true
        settings.onboardingDone = true
        controller.start()
    }

    func applicationWillTerminate(_ notification: Notification) {
        controller?.stop()
    }
}

/// Finds the rules: inside the app's Resources (copied by build.sh), or in
/// the checkout when run with `swift run` during development.
enum RulesLoader {
    static func loadGate() throws -> EligibilityGate {
        let fields = try FieldRules.load(from: try locate(RulesLocator.fieldsFile))
        let apps = try AppRules.load(from: try locate(RulesLocator.appsFile))
        return EligibilityGate(fieldRules: fields, appRules: apps)
    }

    struct Missing: Error {}

    static func locate(_ name: String) throws -> URL {
        let base = (name as NSString).deletingPathExtension
        if let url = Bundle.main.url(forResource: base, withExtension: "json") { return url }
        let starts = [
            URL(fileURLWithPath: CommandLine.arguments.first ?? "").deletingLastPathComponent(),
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath),
        ]
        for start in starts {
            if let url = RulesLocator.findInCheckout(name, from: start) { return url }
        }
        throw Missing()
    }
}
