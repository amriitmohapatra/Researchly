import AppKit
import ApplicationServices
import ResearchlyOverlayCore

/// Reads what the gate needs, and then (only for an eligible field) the
/// text, selection and geometry. Nothing read here is logged or stored.
enum FieldReader {
    /// The descriptor for the gate. Reads labels and identifiers, never the
    /// field's value: a password field is refused before its text is touched.
    static func describe(_ el: AXUIElement, bundleID: String?) -> FieldDescriptor {
        let role = AX.string(el, AX.role) ?? ""
        let subrole = AX.string(el, AX.subrole)
        let secure = subrole == AX.secureTextFieldSubrole || role == AX.secureTextFieldSubrole
        var labels: [String] = []
        var identifiers: [String] = []
        var ancestors: [String] = []
        if !secure {
            for name in [AX.title, AX.description, AX.placeholder, AX.help] {
                if let s = AX.string(el, name), !s.isEmpty { labels.append(s) }
            }
            if let labelElement = AX.element(el, AX.titleUIElement) {
                for name in [AX.value, AX.title, AX.description] {
                    if let s = AX.string(labelElement, name), !s.isEmpty, s.count <= 200 { labels.append(s) }
                }
            }
            if let id = AX.string(el, AX.identifier), !id.isEmpty { identifiers.append(id) }
            if let id = AX.string(el, AX.domIdentifier), !id.isEmpty { identifiers.append(id) }
            identifiers += AX.strings(el, AX.domClassList)
            ancestors = formNames(above: el)
        }
        return FieldDescriptor(
            bundleID: bundleID, role: role, subrole: subrole, isSecure: secure,
            isEditable: isEditable(el, role: role), labels: labels, identifiers: identifiers,
            ancestorNames: ancestors, characterCount: nil)
    }

    /// Names of enclosing forms and search regions (a few levels up). Window
    /// titles are not included: a document called "Login notes" is still a
    /// document.
    static func formNames(above el: AXUIElement) -> [String] {
        var names: [String] = []
        var current = AX.element(el, AX.parent)
        var depth = 0
        while let node = current, depth < 8 {
            let role = AX.string(node, AX.role) ?? ""
            if role == "AXWindow" || role == "AXApplication" { break }
            let subrole = AX.string(node, AX.subrole) ?? ""
            let roleDescription = (AX.string(node, AX.roleDescription) ?? "").lowercased()
            let isForm = subrole == "AXLandmarkSearch" || subrole == "AXSearchField"
                || roleDescription == "form" || roleDescription == "search"
                || (AX.string(node, "AXDOMRole") ?? "").lowercased() == "form"
            if isForm {
                if subrole == "AXLandmarkSearch" || roleDescription == "search" { names.append("search") }
                for name in [AX.title, AX.description, AX.identifier, AX.domIdentifier] {
                    if let s = AX.string(node, name), !s.isEmpty, s.count <= 200 { names.append(s) }
                }
            }
            current = AX.element(node, AX.parent)
            depth += 1
        }
        return names
    }

    static func isEditable(_ el: AXUIElement, role: String) -> Bool {
        if AX.isSettable(el, AX.value) || AX.isSettable(el, AX.selectedText) { return true }
        // Some web text areas report neither but take a selection and keep
        // an "AXEditableAncestor"; a read-only page does not.
        if role == "AXTextArea", AX.element(el, "AXEditableAncestor") != nil { return true }
        return false
    }

    static func characterCount(_ el: AXUIElement) -> Int? {
        AX.int(el, AX.numberOfCharacters)
    }

    /// The field's text. Falls back to asking for the whole range when the
    /// value is not a string (some web areas).
    static func text(_ el: AXUIElement) -> String? {
        if let s = AX.string(el, AX.value) { return s }
        if let n = characterCount(el), n >= 0 {
            return AX.string(el, for: UTF16Range(location: 0, length: n))
        }
        return nil
    }

    static func selection(_ el: AXUIElement) -> UTF16Range? {
        AX.range(el, AX.selectedTextRange)
    }

    static func visibleCharacters(_ el: AXUIElement) -> UTF16Range? {
        AX.range(el, AX.visibleCharacterRange)
    }

    /// The part of the field actually on screen (AX space): the field's
    /// frame, cut to its scroll area and its window.
    static func visibleFrame(_ el: AXUIElement) -> CGRect? {
        guard var frame = AX.frame(el), frame.width > 0, frame.height > 0 else { return nil }
        var current = AX.element(el, AX.parent)
        var depth = 0
        while let node = current, depth < 10 {
            let role = AX.string(node, AX.role) ?? ""
            if role == "AXScrollArea" || role == "AXWindow" {
                if let f = AX.frame(node), f.width > 0, f.height > 0 {
                    frame = frame.intersection(f)
                    if frame.isNull || frame.width <= 0 || frame.height <= 0 { return nil }
                }
            }
            if role == "AXWindow" || role == "AXApplication" { break }
            current = AX.element(node, AX.parent)
            depth += 1
        }
        return frame
    }
}

/// Measures where a text range sits on screen, one rectangle per line.
enum TextGeometry {
    /// Rectangles (AX space) for `range`, one per visual line. Uses the
    /// host's line ranges when it reports them; otherwise measures single
    /// characters and groups them into lines.
    static func lineRects(for range: UTF16Range, in el: AXUIElement, textLength: Int) -> [CGRect] {
        var r = range
        if r.isEmpty {
            // An insertion point (a missing comma): mark the character before it.
            guard textLength > 0 else { return [] }
            r = UTF16Range(location: max(0, min(r.location, textLength) - 1), length: 1)
        }
        guard let clamped = r.clamped(toLength: textLength) else { return [] }
        r = clamped

        if let first = AX.line(el, forIndex: r.location),
           let last = AX.line(el, forIndex: max(r.location, r.end - 1)) {
            if first == last {
                return AX.bounds(el, for: r).map { [$0] }?.filter { OverlayGeometry.isUsable($0) } ?? []
            }
            if last > first, last - first <= 60 {
                var lines: [UTF16Range] = []
                for line in first...last {
                    if let lr = AX.range(el, forLine: line) { lines.append(lr) }
                }
                if !lines.isEmpty {
                    return OverlayGeometry.split(r, byLines: lines)
                        .compactMap { AX.bounds(el, for: trimmedOfLineBreak($0, in: el)) }
                        .filter { OverlayGeometry.isUsable($0) }
                }
            }
        }

        // No line information: one box if it is one line high, else measure
        // characters (bounded) and group them.
        guard let whole = AX.bounds(el, for: r) else { return [] }
        let firstChar = AX.bounds(el, for: UTF16Range(location: r.location, length: 1))
        let lineHeight = firstChar?.height ?? whole.height
        if OverlayGeometry.isUsable(whole), whole.height <= lineHeight * 1.6 { return [whole] }
        guard r.length <= 400 else { return [] }
        var chars: [CGRect] = []
        for i in r.location..<r.end {
            if let c = AX.bounds(el, for: UTF16Range(location: i, length: 1)) { chars.append(c) }
        }
        return OverlayGeometry.lineRects(fromCharacterRects: chars)
    }

    /// A line's piece without its trailing line break (whose box is often
    /// the rest of the line's width).
    private static func trimmedOfLineBreak(_ piece: UTF16Range, in el: AXUIElement) -> UTF16Range {
        guard piece.length > 1, let last = AX.string(el, for: UTF16Range(location: piece.end - 1, length: 1)),
              last == "\n" || last == "\r" || last == "\u{2028}" || last == "\u{2029}" else { return piece }
        return UTF16Range(location: piece.location, length: piece.length - 1)
    }
}
