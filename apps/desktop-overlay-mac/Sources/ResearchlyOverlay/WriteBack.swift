import AppKit
import ApplicationServices
import ResearchlyOverlayCore

/// Writes an accepted revision back into the host field, only when the
/// writer clicks Accept (design note §1.4, §6 step 8). Tries the app's
/// methods in order (apps-mac.json): Accessibility, then typing, then
/// pasting. Each one goes through the host's own editing, so the host's
/// undo (Cmd-Z) takes the change back.
@MainActor
final class WriteBack {
    enum Outcome: Equatable {
        case applied(WriteBackMethod)
        /// The field no longer says what the suggestion was about.
        case textChanged
        /// Something changed, but not as expected: the writer should look.
        case uncertain
        /// No method worked; nothing was changed.
        case failed
    }

    private var pasteboardRestore: Timer?

    func apply(replacement: String, range: UTF16Range, expected: String, in element: AXUIElement,
               methods: [WriteBackMethod], completion: @escaping (Outcome) -> Void) {
        guard let before = FieldReader.text(element),
              UTF16Text.substring(before, range) == expected,
              let after = UTF16Text.replacing(before, range, with: replacement) else {
            completion(.textChanged)
            return
        }
        attempt(methods[...], replacement: replacement, range: range, before: before, after: after,
                element: element, completion: completion)
    }

    private func attempt(_ methods: ArraySlice<WriteBackMethod>, replacement: String, range: UTF16Range,
                         before: String, after: String, element: AXUIElement,
                         completion: @escaping (Outcome) -> Void) {
        guard let method = methods.first else { completion(.failed); return }
        let rest = methods.dropFirst()
        let next = { [weak self] in
            self?.attempt(rest, replacement: replacement, range: range, before: before, after: after,
                          element: element, completion: completion)
        }
        // Verify by reading the field again: exactly the expected text means
        // done; unchanged means try the next method; anything else means
        // stop (another attempt could apply the change twice).
        let verify = {
            let now = FieldReader.text(element)
            if now == after { completion(.applied(method)) }
            else if now == before { next() }
            else { completion(.uncertain) }
        }

        switch method {
        case .accessibility:
            guard AX.setSelectedRange(element, range),
                  AX.set(element, AX.selectedText, replacement as CFString) else { next(); return }
            // Web views apply the change a moment later; reading at once
            // could see the old text and apply it a second time.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { MainActor.assumeIsolated { verify() } }
        case .typing:
            guard select(range, in: element) else { next(); return }
            if replacement.isEmpty { postKey(0x33) } else { type(replacement) }   // 0x33: Delete
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { MainActor.assumeIsolated { verify() } }
        case .paste:
            guard select(range, in: element), let pid = AX.pid(element) else { next(); return }
            if replacement.isEmpty { postKey(0x33) } else { paste(replacement, pid: pid) }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { MainActor.assumeIsolated { verify() } }
        }
    }

    /// Selects the range and checks the host took the selection.
    private func select(_ range: UTF16Range, in element: AXUIElement) -> Bool {
        guard AX.setSelectedRange(element, range) else { return false }
        return FieldReader.selection(element) == range
    }

    // MARK: Typing

    /// Types text as keyboard events carrying Unicode strings, in chunks
    /// that never split a character.
    private func type(_ text: String) {
        let source = CGEventSource(stateID: .combinedSessionState)
        var chunk: [UniChar] = []
        func flush() {
            guard !chunk.isEmpty else { return }
            for down in [true, false] {
                guard let e = CGEvent(keyboardEventSource: source, virtualKey: 0, keyDown: down) else { continue }
                e.flags = []
                e.keyboardSetUnicodeString(stringLength: chunk.count, unicodeString: chunk)
                e.post(tap: .cghidEventTap)
            }
            chunk.removeAll()
        }
        for ch in text {
            let units = Array(ch.utf16)
            if chunk.count + units.count > 20 { flush() }
            chunk += units
        }
        flush()
    }

    private func postKey(_ keyCode: CGKeyCode, flags: CGEventFlags = []) {
        let source = CGEventSource(stateID: .combinedSessionState)
        for down in [true, false] {
            guard let e = CGEvent(keyboardEventSource: source, virtualKey: keyCode, keyDown: down) else { continue }
            e.flags = flags
            e.post(tap: .cghidEventTap)
        }
    }

    // MARK: Pasting

    /// Puts the text on the pasteboard (marked transient and concealed, so
    /// clipboard managers skip it), pastes through the host's Edit > Paste
    /// menu item (found by its Cmd-V shortcut, whatever the language), and
    /// puts the writer's pasteboard back afterwards.
    private func paste(_ text: String, pid: pid_t) {
        let pb = NSPasteboard.general
        let saved = Self.snapshot(pb)
        pb.clearContents()
        let item = NSPasteboardItem()
        item.setString(text, forType: .string)
        item.setString("", forType: NSPasteboard.PasteboardType("org.nspasteboard.TransientType"))
        item.setString("", forType: NSPasteboard.PasteboardType("org.nspasteboard.ConcealedType"))
        pb.writeObjects([item])
        let ours = pb.changeCount

        if let menuItem = Self.pasteMenuItem(pid: pid) {
            AX.press(menuItem)
        } else {
            postKey(0x09, flags: .maskCommand)   // the V key position; layout-dependent, hence the fallback order
        }

        pasteboardRestore?.invalidate()
        pasteboardRestore = Timer.scheduledTimer(withTimeInterval: 0.8, repeats: false) { _ in
            MainActor.assumeIsolated {
                // Only if nothing else used the pasteboard meanwhile.
                guard pb.changeCount == ours else { return }
                pb.clearContents()
                if !saved.isEmpty { pb.writeObjects(saved) }
            }
        }
    }

    private static func snapshot(_ pb: NSPasteboard) -> [NSPasteboardItem] {
        (pb.pasteboardItems ?? []).map { original in
            let copy = NSPasteboardItem()
            for type in original.types {
                if let data = original.data(forType: type) { copy.setData(data, forType: type) }
            }
            return copy
        }
    }

    /// The enabled menu item whose shortcut is Cmd-V (no other modifiers).
    static func pasteMenuItem(pid: pid_t) -> AXUIElement? {
        let app = AXUIElementCreateApplication(pid)
        guard let bar = AX.element(app, AX.menuBar) else { return nil }
        for top in AX.elements(bar, AX.children) {
            for menu in AX.elements(top, AX.children) {
                for item in AX.elements(menu, AX.children) {
                    guard AX.string(item, AX.menuItemCmdChar)?.uppercased() == "V",
                          (AX.int(item, AX.menuItemCmdModifiers) ?? -1) == 0,
                          AX.bool(item, AX.enabled) ?? true else { continue }
                    return item
                }
            }
        }
        return nil
    }
}
