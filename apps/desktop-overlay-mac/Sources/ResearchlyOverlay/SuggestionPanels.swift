import AppKit
import ResearchlyOverlayCore

/// Builds the small rounded, vibrant surfaces the teaser and the card share.
@MainActor
enum PanelChrome {
    static let width: CGFloat = 320
    static let padding: CGFloat = 12

    static func background() -> NSVisualEffectView {
        let v = NSVisualEffectView()
        v.material = .popover
        v.state = .active
        v.blendingMode = .behindWindow
        v.wantsLayer = true
        v.layer?.cornerRadius = 10
        v.layer?.masksToBounds = true
        return v
    }

    static func label(_ text: String, size: CGFloat = 12.5, weight: NSFont.Weight = .regular,
                      color: NSColor = .labelColor, lines: Int = 0) -> NSTextField {
        let l = NSTextField(wrappingLabelWithString: text)
        l.font = .systemFont(ofSize: size, weight: weight)
        l.textColor = color
        l.maximumNumberOfLines = lines
        l.preferredMaxLayoutWidth = width - padding * 2
        l.isSelectable = false
        l.lineBreakMode = lines == 1 ? .byTruncatingTail : .byWordWrapping
        return l
    }

    static func categoryHeader(_ category: Category) -> NSStackView {
        let style = Tokens.category(category)
        let icon = NSImageView()
        icon.image = Appearance.symbol(style.symbol, label: style.name)
        icon.contentTintColor = style.ink.nsColor
        icon.setContentHuggingPriority(.required, for: .horizontal)
        let name = label(style.name, size: 11.5, weight: .semibold, color: style.ink.nsColor, lines: 1)
        let row = NSStackView(views: [icon, name])
        row.orientation = .horizontal
        row.spacing = 5
        row.alignment = .centerY
        return row
    }

    /// A coloured rail on the leading edge, as on the website's cards.
    static func rail(_ category: Category) -> NSView {
        let rail = NSView()
        rail.wantsLayer = true
        rail.layer?.backgroundColor = Tokens.category(category).line.cgColor(dark: Appearance.isDark)
        rail.translatesAutoresizingMaskIntoConstraints = false
        rail.widthAnchor.constraint(equalToConstant: 3).isActive = true
        return rail
    }

    /// Lays `content` out at the fixed width inside a background with a
    /// rail, and sizes `panel` to fit.
    static func install(_ content: NSStackView, category: Category, in panel: NSPanel) {
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = 6
        content.edgeInsets = NSEdgeInsets(top: padding, left: padding, bottom: padding, right: padding)
        content.translatesAutoresizingMaskIntoConstraints = false

        let bg = background()
        let railView = rail(category)
        bg.addSubview(railView)
        bg.addSubview(content)
        NSLayoutConstraint.activate([
            railView.leadingAnchor.constraint(equalTo: bg.leadingAnchor),
            railView.topAnchor.constraint(equalTo: bg.topAnchor),
            railView.bottomAnchor.constraint(equalTo: bg.bottomAnchor),
            content.leadingAnchor.constraint(equalTo: bg.leadingAnchor),
            content.trailingAnchor.constraint(equalTo: bg.trailingAnchor),
            content.topAnchor.constraint(equalTo: bg.topAnchor),
            content.bottomAnchor.constraint(equalTo: bg.bottomAnchor),
            content.widthAnchor.constraint(equalToConstant: width),
        ])
        panel.contentView = bg
        bg.layoutSubtreeIfNeeded()
        panel.setContentSize(bg.fittingSize)
    }

    /// Places a panel just below (or, without room, above) an anchor
    /// rectangle in screen space, kept on the anchor's screen.
    static func place(_ panel: NSPanel, near anchor: CGRect) {
        let size = panel.frame.size
        let screen = NSScreen.screens.first { $0.frame.intersects(anchor) } ?? NSScreen.main
        let bounds = screen?.visibleFrame ?? CGRect(x: 0, y: 0, width: 10_000, height: 10_000)
        var origin = CGPoint(x: anchor.minX, y: anchor.minY - size.height - 6)
        if origin.y < bounds.minY { origin.y = anchor.maxY + 6 }
        origin.x = min(max(origin.x, bounds.minX + 4), bounds.maxX - size.width - 4)
        origin.y = min(max(origin.y, bounds.minY + 4), bounds.maxY - size.height - 4)
        panel.setFrameOrigin(origin)
    }
}

/// The hover teaser: category, what was noticed, and the revision if there
/// is one. A click on it opens the full card.
@MainActor
final class TeaserPanel {
    private let panel = NonActivatingPanel(level: .overlayCard, clickThrough: false)
    private var target: ActionTarget?
    private(set) var suggestionID: String?
    var onOpen: ((String) -> Void)?

    var isVisible: Bool { panel.isVisible }
    var screenFrame: CGRect { panel.frame }

    func show(_ s: PlacedSuggestion, near anchor: CGRect) {
        suggestionID = s.id
        let stack = NSStackView()
        stack.addArrangedSubview(PanelChrome.categoryHeader(s.category))
        let text = s.suggestion.message.isEmpty ? s.suggestion.plain : s.suggestion.message
        if !text.isEmpty { stack.addArrangedSubview(PanelChrome.label(text, size: 13, lines: 3)) }
        if let first = s.suggestion.replacements.first {
            let shown = first.isEmpty ? "Delete “\(s.flaggedText)”" : "→ \(first)"
            stack.addArrangedSubview(PanelChrome.label(shown, size: 13, weight: .semibold, lines: 2))
        }
        let id = s.id
        let more = FirstClickButton(title: "Why and how…", target: nil, action: nil)
        more.bezelStyle = .inline
        let t = ActionTarget { [weak self] in self?.onOpen?(id) }
        more.target = t
        more.action = #selector(ActionTarget.fire(_:))
        target = t
        stack.addArrangedSubview(more)
        PanelChrome.install(stack, category: s.category, in: panel)
        PanelChrome.place(panel, near: anchor)
        panel.show()
    }

    /// The same panel, for the widget's status (offline, partial).
    func showStatus(title: String, detail: String, near anchor: CGRect) {
        suggestionID = nil
        let stack = NSStackView()
        stack.addArrangedSubview(PanelChrome.label(title, size: 12.5, weight: .semibold, lines: 1))
        stack.addArrangedSubview(PanelChrome.label(detail, size: 12, color: .secondaryLabelColor))
        PanelChrome.install(stack, category: .improvement, in: panel)
        PanelChrome.place(panel, near: anchor)
        panel.show()
    }

    func hide() {
        suggestionID = nil
        panel.hide()
    }
}

/// What the writer chose on a card.
enum CardAction {
    case accept(String)
    case dismiss
    case close
}

/// The full card: the plain explanation first, then why and the named
/// source; Accept for each revision, and Not an issue. The card is the lesson.
@MainActor
final class CardPanel {
    private let panel = NonActivatingPanel(level: .overlayCard, clickThrough: false)
    private var targets: [ActionTarget] = []
    private(set) var suggestionID: String?
    var onAction: ((String, CardAction) -> Void)?

    var isVisible: Bool { panel.isVisible }
    var screenFrame: CGRect { panel.frame }

    func show(_ s: PlacedSuggestion, near anchor: CGRect, note: String? = nil) {
        suggestionID = s.id
        targets = []
        let id = s.id
        let stack = NSStackView()

        let header = PanelChrome.categoryHeader(s.category)
        let close = button("Close", style: .inline) { [weak self] in self?.onAction?(id, .close) }
        close.setAccessibilityLabel("Close")
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        let top = NSStackView(views: [header, spacer, close])
        top.orientation = .horizontal
        top.translatesAutoresizingMaskIntoConstraints = false
        top.widthAnchor.constraint(equalToConstant: PanelChrome.width - PanelChrome.padding * 2).isActive = true
        stack.addArrangedSubview(top)

        let sug = s.suggestion
        if !sug.message.isEmpty {
            stack.addArrangedSubview(PanelChrome.label(sug.message, size: 13.5, weight: .semibold))
        }
        if !sug.plain.isEmpty {
            stack.addArrangedSubview(PanelChrome.label(sug.plain, size: 13))
        }
        if !sug.why.isEmpty {
            stack.addArrangedSubview(PanelChrome.label("Why: " + sug.why, size: 12, color: .secondaryLabelColor))
        }
        if !sug.source.isEmpty {
            stack.addArrangedSubview(PanelChrome.label("Source: " + sug.source, size: 11.5, color: .secondaryLabelColor))
        }
        if let note = note {
            stack.addArrangedSubview(PanelChrome.label(note, size: 12, weight: .medium,
                                                       color: Tokens.warning.nsColor))
        }

        var buttons: [NSView] = []
        for replacement in sug.replacements.prefix(3) {
            let title = replacement.isEmpty ? "Delete “\(s.flaggedText)”" : "Accept “\(replacement)”"
            let b = button(title, style: .push) { [weak self] in self?.onAction?(id, .accept(replacement)) }
            buttons.append(b)
        }
        buttons.append(button("Not an issue", style: .push) { [weak self] in self?.onAction?(id, .dismiss) })
        let row = NSStackView(views: buttons)
        row.orientation = .horizontal
        row.spacing = 6
        stack.addArrangedSubview(row)
        if buttons.count > 2 {
            // Long rows wrap: put the revisions on their own line.
            row.orientation = .vertical
            row.alignment = .leading
        }

        PanelChrome.install(stack, category: s.category, in: panel)
        PanelChrome.place(panel, near: anchor)
        panel.show()
    }

    func hide() {
        suggestionID = nil
        targets = []
        panel.hide()
    }

    private func button(_ title: String, style: NSButton.BezelStyle, _ action: @escaping () -> Void) -> NSButton {
        let b = FirstClickButton(title: title, target: nil, action: nil)
        b.bezelStyle = style
        b.controlSize = .regular
        let t = ActionTarget(action)
        b.target = t
        b.action = #selector(ActionTarget.fire(_:))
        targets.append(t)
        return b
    }
}
