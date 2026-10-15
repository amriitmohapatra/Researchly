import AppKit
import QuartzCore
import ResearchlyDesignTokens
import ResearchlyOverlayCore

@MainActor
protocol FieldWidgetDelegate: AnyObject {
    func widgetClicked(_ widget: FieldWidget, view: NSView)
    /// The writer dragged the widget by (dx, dy) in AX space (y down).
    func widgetDragged(by offset: CGPoint)
    func widgetHover(_ inside: Bool)
}

/// The small mark pinned to the focused field's corner. It shows the six
/// states as shape plus badge (never colour alone), can be dragged, and
/// teaches the drag once.
@MainActor
final class FieldWidget {
    static let size = CGSize(width: 26, height: 26)

    weak var delegate: FieldWidgetDelegate?
    private let panel = NonActivatingPanel(level: .overlay, clickThrough: false)
    private let view = WidgetView(frame: NSRect(origin: .zero, size: FieldWidget.size))
    private let tip = NonActivatingPanel(level: .overlayCard, clickThrough: true)
    private var tipTimer: Timer?

    init() {
        panel.contentView = view
        panel.setContentSize(FieldWidget.size)
        view.owner = self
    }

    var isVisible: Bool { panel.isVisible }
    var screenFrame: CGRect { panel.frame }

    /// Shows the widget with its top-left at `axOrigin` (AX space).
    func show(atAX axOrigin: CGPoint, state: OverlayState, count: Int, detail: String?) {
        let axRect = CGRect(origin: axOrigin, size: FieldWidget.size)
        let screen = Appearance.toScreen(axRect)
        if panel.frame.origin != screen.origin { panel.setFrameOrigin(screen.origin) }
        view.update(state: state, count: count, detail: detail)
        if state == .hidden { hide() } else { panel.show() }
    }

    func hide() {
        panel.hide()
        hideTip()
    }

    // MARK: The one-time tip

    func showDragTip() {
        let label = NSTextField(labelWithString: "Drag to move")
        label.font = .systemFont(ofSize: 11, weight: .medium)
        label.textColor = .labelColor
        label.sizeToFit()
        let padding: CGFloat = 8
        let size = CGSize(width: label.frame.width + padding * 2, height: label.frame.height + padding)
        let background = NSVisualEffectView(frame: NSRect(origin: .zero, size: size))
        background.material = .toolTip
        background.state = .active
        background.wantsLayer = true
        background.layer?.cornerRadius = 6
        background.layer?.masksToBounds = true
        label.frame.origin = CGPoint(x: padding, y: padding / 2)
        background.addSubview(label)
        tip.contentView = background
        tip.setContentSize(size)
        let f = panel.frame
        var origin = CGPoint(x: f.minX - size.width - 6, y: f.midY - size.height / 2)
        if let screen = panel.screen, origin.x < screen.visibleFrame.minX { origin.x = f.maxX + 6 }
        tip.setFrameOrigin(origin)
        tip.show()
        tipTimer?.invalidate()
        tipTimer = Timer.scheduledTimer(withTimeInterval: 4, repeats: false) { [weak self] _ in
            MainActor.assumeIsolated { self?.hideTip() }
        }
    }

    func hideTip() {
        tipTimer?.invalidate()
        tipTimer = nil
        tip.hide()
    }

    // MARK: From the view

    fileprivate func clicked() { delegate?.widgetClicked(self, view: view) }
    fileprivate func dragged(by delta: CGPoint) { delegate?.widgetDragged(by: delta) }
    fileprivate func hover(_ inside: Bool) { delegate?.widgetHover(inside) }

    fileprivate func move(byScreenDelta dx: CGFloat, _ dy: CGFloat) {
        var o = panel.frame.origin
        o.x += dx
        o.y += dy
        panel.setFrameOrigin(o)
        hideTip()
    }
}

final class WidgetView: NSView {
    weak var owner: FieldWidget?
    private var state: OverlayState = .hidden
    private var count = 0
    private let spinner = CAShapeLayer()
    private var dragStart: CGPoint?
    private var dragLast: CGPoint?
    private var dragged = false

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        spinner.frame = bounds
        spinner.fillColor = nil
        spinner.lineWidth = 2
        spinner.lineCap = .round
        let inset = bounds.insetBy(dx: 4, dy: 4)
        spinner.path = CGPath(ellipseIn: inset, transform: nil)
        spinner.strokeStart = 0
        spinner.strokeEnd = 0.7
        spinner.isHidden = true
        layer?.addSublayer(spinner)
        addTrackingArea(NSTrackingArea(rect: .zero,
                                       options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect],
                                       owner: self, userInfo: nil))
        setAccessibilityElement(true)
        setAccessibilityRole(.button)
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    func update(state: OverlayState, count: Int, detail: String?) {
        let changed = state != self.state || count != self.count
        self.state = state
        self.count = count
        toolTip = detail ?? state.look.description
        setAccessibilityLabel("Researchly: \(state.label(count: count))")
        updateSpinner()
        if changed { needsDisplay = true }
    }

    private func updateSpinner() {
        let dark = Appearance.isDark
        spinner.strokeColor = ResearchlyTokens.widgetRing.cgColor(dark: dark)
        let spinning = state == .checking
        spinner.isHidden = !spinning
        if spinning && !Appearance.reduceMotion {
            if spinner.animation(forKey: "spin") == nil {
                let spin = CABasicAnimation(keyPath: "transform.rotation.z")
                spin.fromValue = 0
                spin.toValue = -2 * Double.pi
                spin.duration = 1.1
                spin.repeatCount = .infinity
                spinner.add(spin, forKey: "spin")
            }
        } else {
            spinner.removeAnimation(forKey: "spin")
        }
    }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        updateSpinner()
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        let dark = Appearance.isDark
        let ring = ResearchlyTokens.widgetMark.resolve(dark: dark).nsColor
        let surface = ResearchlyTokens.widgetSurface.resolve(dark: dark).nsColor
        let circle = NSBezierPath(ovalIn: bounds.insetBy(dx: 4, dy: 4))

        surface.setFill()
        circle.fill()

        switch state {
        case .hidden:
            return
        case .checking:
            // The spinner layer draws the ring.
            ResearchlyTokens.widgetRing.resolve(dark: dark).nsColor.withAlphaComponent(0.25).setStroke()
            circle.lineWidth = 2
            circle.stroke()
        case .issues:
            ResearchlyTokens.widgetBadgeBackground.resolve(dark: dark).nsColor.setFill()
            circle.fill()
            let text = count > 99 ? "99+" : "\(count)"
            let attrs: [NSAttributedString.Key: Any] = [
                .font: NSFont.monospacedDigitSystemFont(ofSize: count > 9 ? 9.5 : 11, weight: .bold),
                .foregroundColor: ResearchlyTokens.widgetBadgeText.resolve(dark: dark).nsColor,
            ]
            let s = NSAttributedString(string: text, attributes: attrs)
            let size = s.size()
            s.draw(at: NSPoint(x: bounds.midX - size.width / 2, y: bounds.midY - size.height / 2))
        case .clear:
            ring.setStroke()
            circle.lineWidth = 2
            circle.stroke()
            let tick = NSBezierPath()
            tick.move(to: NSPoint(x: bounds.midX - 4.5, y: bounds.midY))
            tick.line(to: NSPoint(x: bounds.midX - 1.5, y: bounds.midY - 3.5))
            tick.line(to: NSPoint(x: bounds.midX + 4.5, y: bounds.midY + 3.5))
            tick.lineWidth = 2
            tick.lineCapStyle = .round
            tick.lineJoinStyle = .round
            tick.stroke()
        case .partial:
            ring.setStroke()
            circle.lineWidth = 2
            circle.stroke()
            // A small warning triangle with a stroke for the exclamation.
            let warn = ResearchlyTokens.widgetWarning.resolve(dark: dark).nsColor
            let tri = NSBezierPath()
            tri.move(to: NSPoint(x: bounds.midX, y: bounds.midY + 5))
            tri.line(to: NSPoint(x: bounds.midX - 5.5, y: bounds.midY - 4))
            tri.line(to: NSPoint(x: bounds.midX + 5.5, y: bounds.midY - 4))
            tri.close()
            warn.setFill()
            tri.fill()
            let bar = NSBezierPath()
            bar.move(to: NSPoint(x: bounds.midX, y: bounds.midY + 2))
            bar.line(to: NSPoint(x: bounds.midX, y: bounds.midY - 1))
            bar.lineWidth = 1.5
            bar.lineCapStyle = .round
            surface.setStroke()
            bar.stroke()
        case .offline:
            let grey = ResearchlyTokens.widgetOffline.resolve(dark: dark).nsColor
            grey.setStroke()
            circle.lineWidth = 2
            circle.stroke()
            let slash = NSBezierPath()
            slash.move(to: NSPoint(x: bounds.minX + 7, y: bounds.minY + 7))
            slash.line(to: NSPoint(x: bounds.maxX - 7, y: bounds.maxY - 7))
            slash.lineWidth = 2
            slash.lineCapStyle = .round
            slash.stroke()
        }
    }

    // MARK: Mouse: click, drag, hover

    override func mouseDown(with event: NSEvent) {
        dragStart = NSEvent.mouseLocation
        dragLast = dragStart
        dragged = false
    }

    override func mouseDragged(with event: NSEvent) {
        guard let start = dragStart, let last = dragLast else { return }
        let now = NSEvent.mouseLocation
        if !dragged, hypot(now.x - start.x, now.y - start.y) < 3 { return }
        dragged = true
        owner?.move(byScreenDelta: now.x - last.x, now.y - last.y)
        dragLast = now
    }

    override func mouseUp(with event: NSEvent) {
        defer { dragStart = nil; dragLast = nil }
        guard let start = dragStart else { return }
        if dragged {
            let end = NSEvent.mouseLocation
            // Screen y grows upwards; AX y grows downwards.
            owner?.dragged(by: CGPoint(x: end.x - start.x, y: -(end.y - start.y)))
        } else {
            owner?.clicked()
        }
    }

    override func mouseEntered(with event: NSEvent) { owner?.hover(true) }
    override func mouseExited(with event: NSEvent) { owner?.hover(false) }
}
