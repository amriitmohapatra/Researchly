import AppKit
import QuartzCore
import ResearchlyOverlayCore

/// One suggestion's marks: its category and the line rectangles it covers,
/// in the overlay view's coordinates (y up).
struct UnderlineMark {
    let id: String
    let category: Category
    let rects: [CGRect]
}

/// The transparent, click-through window over the focused field's visible
/// area. It only draws; the mouse goes straight through to the host.
@MainActor
final class UnderlineOverlay {
    private let panel = NonActivatingPanel(level: .overlay, clickThrough: true)
    private let view = UnderlineView()

    init() {
        panel.contentView = view
    }

    /// Places the overlay over `screenFrame` (AppKit space) and draws.
    func show(over screenFrame: CGRect, marks: [UnderlineMark], highlighted: String?, dark: Bool) {
        if panel.frame != screenFrame { panel.setFrame(screenFrame, display: false) }
        view.frame = CGRect(origin: .zero, size: screenFrame.size)
        view.render(marks, highlighted: highlighted, dark: dark)
        panel.show()
    }

    func hide() {
        view.render([], highlighted: nil, dark: false)
        panel.hide()
    }

    var screenFrame: CGRect { panel.frame }
}

final class UnderlineView: NSView {
    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        layer?.masksToBounds = true
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override var isFlipped: Bool { false }

    // Never take a click: the window ignores the mouse, and so does the view.
    override func hitTest(_ point: NSPoint) -> NSView? { nil }

    func render(_ marks: [UnderlineMark], highlighted: String?, dark: Bool) {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layer?.sublayers?.forEach { $0.removeFromSuperlayer() }

        if let id = highlighted, let mark = marks.first(where: { $0.id == id }) {
            let tint = CAShapeLayer()
            let path = CGMutablePath()
            for r in mark.rects { path.addRect(r) }
            tint.path = path
            tint.fillColor = Self.tintColor(for: mark.category, dark: dark)
            layer?.addSublayer(tint)
        }

        // One shape layer per category: they share colour and pattern.
        var byCategory: [String: (Category, CGMutablePath)] = [:]
        for mark in marks {
            let style = Tokens.category(mark.category)
            let key = mark.category.rawValue
            let path = byCategory[key]?.1 ?? CGMutablePath()
            for r in mark.rects {
                let baseline = r.minY + 1.5
                switch style.pattern {
                case .wavyDotted:
                    let points = OverlayGeometry.wavePoints(from: r.minX, to: r.maxX, baseline: baseline + 1)
                    if let first = points.first {
                        path.move(to: first)
                        for p in points.dropFirst() { path.addLine(to: p) }
                    }
                default:
                    path.move(to: CGPoint(x: r.minX, y: baseline))
                    path.addLine(to: CGPoint(x: r.maxX, y: baseline))
                }
            }
            byCategory[key] = (mark.category, path)
        }
        for (_, entry) in byCategory.sorted(by: { $0.key < $1.key }) {
            let style = Tokens.category(entry.0)
            let shape = CAShapeLayer()
            shape.path = entry.1
            shape.fillColor = nil
            shape.strokeColor = style.line.cgColor(dark: dark)
            shape.lineWidth = CGFloat(Tokens.underlineWidth)
            switch style.pattern {
            case .solid:
                shape.lineCap = .butt
            case .dashed:
                shape.lineDashPattern = [4, 2.5]
                shape.lineCap = .butt
            case .dotted, .wavyDotted:
                // Zero-length dashes with round caps draw as dots.
                shape.lineDashPattern = [0.01, 3.5]
                shape.lineCap = .round
                shape.lineWidth = CGFloat(Tokens.underlineWidth) + 0.4
            }
            layer?.addSublayer(shape)
        }
        CATransaction.commit()
    }

    /// The category tint at a strength that leaves the text readable.
    static func tintColor(for category: Category, dark: Bool) -> CGColor {
        let c = Tokens.category(category).tint.resolve(dark: dark)
        let alpha = dark ? c.alpha : 0.55
        return CGColor(srgbRed: CGFloat(c.red), green: CGFloat(c.green), blue: CGFloat(c.blue), alpha: CGFloat(alpha))
    }
}
