import AppKit

// A background app (LSUIElement): a menu-bar item and overlay panels, no
// Dock icon, never the active app while the writer types.
MainActor.assumeIsolated {
    let app = NSApplication.shared
    let delegate = AppDelegate()
    app.delegate = delegate
    _ = app.setActivationPolicy(.accessory)
    withExtendedLifetime(delegate) {
        app.run()
    }
}
