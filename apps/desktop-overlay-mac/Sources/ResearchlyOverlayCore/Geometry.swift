import Foundation

/// Pure geometry for the overlay. Accessibility reports rectangles in
/// "AX space": origin at the top-left of the primary display, y growing
/// downwards. AppKit windows use "screen space": origin at the bottom-left
/// of the primary display, y growing upwards. Everything here is testable
/// without a screen.
public enum OverlayGeometry {
    /// AX space → AppKit screen space. `primaryHeight` is the height of the
    /// primary display (the one with the menu bar: `NSScreen.screens[0]`).
    public static func flip(_ rect: CGRect, primaryHeight: CGFloat) -> CGRect {
        CGRect(x: rect.origin.x, y: primaryHeight - rect.origin.y - rect.size.height,
               width: rect.size.width, height: rect.size.height)
    }

    /// Discards rectangles hosts return for ranges they cannot measure: empty,
    /// non-finite, absurdly tall (a whole-field box), or at the origin.
    public static func isUsable(_ rect: CGRect, maxLineHeight: CGFloat = 200) -> Bool {
        let values = [rect.origin.x, rect.origin.y, rect.size.width, rect.size.height]
        guard values.allSatisfy({ $0.isFinite }) else { return false }
        if rect.size.width <= 0 || rect.size.height <= 0 { return false }
        if rect.size.height > maxLineHeight { return false }
        if rect.origin.x == 0 && rect.origin.y == 0 { return false }
        return true
    }

    /// Splits a range into its pieces on each line, given the ranges of the
    /// lines it spans (from `AXRangeForLine`).
    public static func split(_ range: UTF16Range, byLines lines: [UTF16Range]) -> [UTF16Range] {
        if lines.isEmpty { return range.isEmpty ? [] : [range] }
        return lines.compactMap { $0.intersection(range) }
    }

    /// Groups per-character rectangles into one rectangle per visual line.
    /// The fallback when a host cannot report line ranges: characters whose
    /// vertical centres lie within half a line of each other share a line.
    public static func lineRects(fromCharacterRects rects: [CGRect]) -> [CGRect] {
        var lines: [CGRect] = []
        for r in rects where isUsable(r) {
            if let last = lines.last, abs(last.midY - r.midY) < max(last.height, r.height) / 2,
               r.minX >= last.minX - 1 {
                lines[lines.count - 1] = last.union(r)
            } else {
                lines.append(r)
            }
        }
        return lines
    }

    /// The part of each line rectangle inside the visible area; lines
    /// entirely outside (scrolled away) are dropped.
    public static func clip(_ rects: [CGRect], to visible: CGRect) -> [CGRect] {
        rects.compactMap { r in
            let c = r.intersection(visible)
            return (c.isNull || c.width <= 0 || c.height <= 0) ? nil : c
        }
    }

    /// Points along a wave under `[x0, x1]` at baseline `y` (y-up space),
    /// for the wavy-dotted Preference underline.
    public static func wavePoints(from x0: CGFloat, to x1: CGFloat, baseline y: CGFloat,
                                  amplitude: CGFloat = 1.5, wavelength: CGFloat = 6,
                                  step: CGFloat = 1) -> [CGPoint] {
        guard x1 > x0, wavelength > 0, step > 0 else { return [] }
        var points: [CGPoint] = []
        var x = x0
        while x < x1 {
            let phase = (x - x0) / wavelength * 2 * .pi
            points.append(CGPoint(x: x, y: y + amplitude * sin(phase)))
            x += step
        }
        let phase = (x1 - x0) / wavelength * 2 * .pi
        points.append(CGPoint(x: x1, y: y + amplitude * sin(phase)))
        return points
    }

    /// Where the field widget goes (top-left of the widget, AX space). The
    /// rule's corner and inward offset place it inside the field's visible
    /// frame; a writer's drag is kept as an offset from that spot; the result
    /// never leaves the field by more than half the widget. `userOffset` is
    /// the drag, as a displacement (x right, y down).
    public static func widgetOrigin(field: CGRect, widget: CGSize, placement: WidgetPlacement,
                                    userOffset: CGPoint? = nil) -> CGPoint {
        let corner = placement.effectiveCorner
        let dx = CGFloat(placement.offsetX), dy = CGFloat(placement.offsetY)
        var x: CGFloat
        var y: CGFloat
        switch corner {
        case .topLeft: x = field.minX + dx; y = field.minY + dy
        case .topRight: x = field.maxX - dx - widget.width; y = field.minY + dy
        case .bottomLeft: x = field.minX + dx; y = field.maxY - dy - widget.height
        case .bottomRight: x = field.maxX - dx - widget.width; y = field.maxY - dy - widget.height
        }
        if let off = userOffset {
            x += off.x
            y += off.y
        }
        let slackX = widget.width / 2, slackY = widget.height / 2
        x = min(max(x, field.minX - slackX), field.maxX - widget.width + slackX)
        y = min(max(y, field.minY - slackY), field.maxY - widget.height + slackY)
        return CGPoint(x: x, y: y)
    }

    /// True if `point` lies on any of `rects`, give or take `slop` points
    /// (finds the underline under the mouse; both in the same space).
    public static func hitTest(_ point: CGPoint, rects: [CGRect], slop: CGFloat = 2) -> Bool {
        rects.contains { $0.insetBy(dx: -slop, dy: -slop).contains(point) }
    }
}
