import AppKit
import ResearchlyDesignTokens
import ResearchlyOverlayCore

// The generated tokens (packages/design-tokens) give every colour as a
// light/dark pair, and an `nsColor` that follows the appearance by itself.
// Core Animation layers need a CGColor resolved for the current appearance.
extension ResearchlyTokens.RGBA {
    var cgColor: CGColor {
        CGColor(srgbRed: CGFloat(red), green: CGFloat(green), blue: CGFloat(blue), alpha: CGFloat(alpha))
    }
}

extension ResearchlyTokens.ColorPair {
    func cgColor(dark: Bool) -> CGColor { resolve(dark: dark).cgColor }
}

@MainActor
enum Appearance {
    static var isDark: Bool {
        NSApp.effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
    }

    static var reduceMotion: Bool {
        NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
    }

    /// Height of the primary display: AX space flips around it.
    static var primaryHeight: CGFloat {
        NSScreen.screens.first?.frame.maxY ?? 0
    }

    static func toScreen(_ axRect: CGRect) -> CGRect {
        OverlayGeometry.flip(axRect, primaryHeight: primaryHeight)
    }

    static func toAX(_ screenPoint: CGPoint) -> CGPoint {
        CGPoint(x: screenPoint.x, y: primaryHeight - screenPoint.y)
    }

    static func symbol(_ name: String, label: String) -> NSImage? {
        NSImage(systemSymbolName: name, accessibilityDescription: label)
    }
}

/// A panel that never becomes key or main: the host keeps the caret, its
/// undo history and its shortcuts (design note §1.4).
class NonActivatingPanel: NSPanel {
    init(level: NSWindow.Level, clickThrough: Bool) {
        super.init(contentRect: NSRect(x: 0, y: 0, width: 10, height: 10),
                   styleMask: [.borderless, .nonactivatingPanel],
                   backing: .buffered, defer: true)
        isFloatingPanel = true
        self.level = level
        hidesOnDeactivate = false
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        isReleasedWhenClosed = false
        ignoresMouseEvents = clickThrough
        becomesKeyOnlyIfNeeded = true
        animationBehavior = .none
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }

    func show() {
        if !isVisible { orderFrontRegardless() }
    }

    func hide() {
        if isVisible { orderOut(nil) }
    }
}

extension NSWindow.Level {
    /// Above ordinary and floating windows of the host.
    static let overlay = NSWindow.Level(rawValue: NSWindow.Level.floating.rawValue + 1)
    /// Teasers and cards sit above the underlines and the widget.
    static let overlayCard = NSWindow.Level(rawValue: NSWindow.Level.floating.rawValue + 2)
}

/// A button that acts on the first click even though its window is never
/// key and its app never active.
final class FirstClickButton: NSButton {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

/// Holds a closure as an Objective-C target for buttons and menu items.
final class ActionTarget: NSObject {
    private let block: () -> Void
    init(_ block: @escaping () -> Void) { self.block = block }
    @objc func fire(_ sender: Any?) { block() }
}
