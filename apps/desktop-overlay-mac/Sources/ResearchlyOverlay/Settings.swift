import AppKit
import ResearchlyOverlayCore

/// The overlay's settings, in UserDefaults only. No document text, no
/// suggestion text and no history is ever written here (design note §2).
@MainActor
final class Settings {
    private let defaults: UserDefaults

    private enum Key {
        static let engineMode = "engine.mode"            // "local" | "hosted"
        static let hostedURL = "engine.hostedURL"
        static let showPreferences = "check.showPreferences"
        static let pausedUntil = "pause.until"
        static let pausedApps = "pause.apps"
        static let widgetOffsets = "widget.offsets"      // bundle id → [dx, dy]
        static let dragTipShown = "widget.dragTipShown"
        static let onboardingDone = "onboarding.done"
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    // MARK: Engine

    var engine: EngineChoice {
        get {
            if defaults.string(forKey: Key.engineMode) == "hosted",
               let raw = defaults.string(forKey: Key.hostedURL),
               let url = EngineChoice.validatedHostedURL(raw) {
                return .hosted(url)
            }
            return .thisComputer
        }
        set {
            switch newValue {
            case .thisComputer:
                defaults.set("local", forKey: Key.engineMode)
            case .hosted(let url):
                defaults.set("hosted", forKey: Key.engineMode)
                defaults.set(url.absoluteString, forKey: Key.hostedURL)
            }
        }
    }

    /// The last hosted address entered, even while "This computer" is chosen.
    var lastHostedURL: String? { defaults.string(forKey: Key.hostedURL) }

    var showPreferences: Bool {
        get { defaults.bool(forKey: Key.showPreferences) }
        set { defaults.set(newValue, forKey: Key.showPreferences) }
    }

    var checkOptions: CheckOptions { CheckOptions(showPreferences: showPreferences) }

    // MARK: Pause

    var pause: PauseState {
        get {
            PauseState(until: defaults.object(forKey: Key.pausedUntil) as? Date,
                       pausedApps: Set(defaults.stringArray(forKey: Key.pausedApps) ?? []))
        }
        set {
            if let until = newValue.until { defaults.set(until, forKey: Key.pausedUntil) }
            else { defaults.removeObject(forKey: Key.pausedUntil) }
            defaults.set(Array(newValue.pausedApps).sorted(), forKey: Key.pausedApps)
        }
    }

    // MARK: Widget

    /// The writer's drag for an app, as an AX-space displacement.
    func widgetOffset(for bundleID: String?) -> CGPoint? {
        guard let id = bundleID,
              let all = defaults.dictionary(forKey: Key.widgetOffsets),
              let pair = all[id] as? [Double], pair.count == 2 else { return nil }
        return CGPoint(x: pair[0], y: pair[1])
    }

    func setWidgetOffset(_ offset: CGPoint?, for bundleID: String?) {
        guard let id = bundleID else { return }
        var all = defaults.dictionary(forKey: Key.widgetOffsets) ?? [:]
        if let o = offset { all[id] = [Double(o.x), Double(o.y)] } else { all.removeValue(forKey: id) }
        defaults.set(all, forKey: Key.widgetOffsets)
    }

    var dragTipShown: Bool {
        get { defaults.bool(forKey: Key.dragTipShown) }
        set { defaults.set(newValue, forKey: Key.dragTipShown) }
    }

    var onboardingDone: Bool {
        get { defaults.bool(forKey: Key.onboardingDone) }
        set { defaults.set(newValue, forKey: Key.onboardingDone) }
    }
}
