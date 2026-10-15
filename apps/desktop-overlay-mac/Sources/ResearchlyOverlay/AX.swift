import AppKit
import ApplicationServices
import ResearchlyOverlayCore

/// Thin, typed access to the Accessibility API. Attribute names are the
/// public string constants of `AXAttributeConstants.h`, written out so the
/// code reads the same as Apple's documentation.
enum AX {
    // Attributes
    static let role = "AXRole"
    static let subrole = "AXSubrole"
    static let roleDescription = "AXRoleDescription"
    static let title = "AXTitle"
    static let description = "AXDescription"
    static let help = "AXHelp"
    static let placeholder = "AXPlaceholderValue"
    static let identifier = "AXIdentifier"
    static let domIdentifier = "AXDOMIdentifier"
    static let domClassList = "AXDOMClassList"
    static let titleUIElement = "AXTitleUIElement"
    static let value = "AXValue"
    static let numberOfCharacters = "AXNumberOfCharacters"
    static let selectedText = "AXSelectedText"
    static let selectedTextRange = "AXSelectedTextRange"
    static let visibleCharacterRange = "AXVisibleCharacterRange"
    static let positionAttribute = "AXPosition"
    static let sizeAttribute = "AXSize"
    static let parent = "AXParent"
    static let children = "AXChildren"
    static let window = "AXWindow"
    static let focusedUIElement = "AXFocusedUIElement"
    static let focusedWindow = "AXFocusedWindow"
    static let menuBar = "AXMenuBar"
    static let enabled = "AXEnabled"
    static let menuItemCmdChar = "AXMenuItemCmdChar"
    static let menuItemCmdModifiers = "AXMenuItemCmdModifiers"
    static let enhancedUserInterface = "AXEnhancedUserInterface"
    static let manualAccessibility = "AXManualAccessibility"

    // Parameterized attributes
    static let boundsForRange = "AXBoundsForRange"
    static let lineForIndex = "AXLineForIndex"
    static let rangeForLine = "AXRangeForLine"
    static let stringForRange = "AXStringForRange"

    // Notifications
    static let focusedUIElementChanged = "AXFocusedUIElementChanged"
    static let valueChanged = "AXValueChanged"
    static let selectedTextChanged = "AXSelectedTextChanged"
    static let elementDestroyed = "AXUIElementDestroyed"
    static let windowMoved = "AXWindowMoved"
    static let windowResized = "AXWindowResized"
    static let focusedWindowChanged = "AXFocusedWindowChanged"

    // Actions and subroles
    static let pressAction = "AXPress"
    static let secureTextFieldSubrole = "AXSecureTextField"

    // MARK: Reading

    static func raw(_ el: AXUIElement, _ name: String) -> CFTypeRef? {
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(el, name as CFString, &value) == .success else { return nil }
        return value
    }

    static func string(_ el: AXUIElement, _ name: String) -> String? {
        raw(el, name) as? String
    }

    static func strings(_ el: AXUIElement, _ name: String) -> [String] {
        if let list = raw(el, name) as? [String] { return list }
        if let one = raw(el, name) as? String { return [one] }
        return []
    }

    static func int(_ el: AXUIElement, _ name: String) -> Int? {
        (raw(el, name) as? NSNumber)?.intValue
    }

    static func bool(_ el: AXUIElement, _ name: String) -> Bool? {
        (raw(el, name) as? NSNumber)?.boolValue
    }

    static func element(_ el: AXUIElement, _ name: String) -> AXUIElement? {
        guard let v = raw(el, name), CFGetTypeID(v) == AXUIElementGetTypeID() else { return nil }
        return (v as! AXUIElement)
    }

    static func elements(_ el: AXUIElement, _ name: String) -> [AXUIElement] {
        guard let v = raw(el, name), CFGetTypeID(v) == CFArrayGetTypeID() else { return [] }
        let array = v as! [AnyObject]
        return array.compactMap { item in
            CFGetTypeID(item) == AXUIElementGetTypeID() ? (item as! AXUIElement) : nil
        }
    }

    static func axValue(_ v: CFTypeRef?) -> AXValue? {
        guard let v = v, CFGetTypeID(v) == AXValueGetTypeID() else { return nil }
        return (v as! AXValue)
    }

    static func point(_ el: AXUIElement, _ name: String) -> CGPoint? {
        guard let v = axValue(raw(el, name)) else { return nil }
        var p = CGPoint.zero
        return AXValueGetValue(v, .cgPoint, &p) ? p : nil
    }

    static func size(_ el: AXUIElement, _ name: String) -> CGSize? {
        guard let v = axValue(raw(el, name)) else { return nil }
        var s = CGSize.zero
        return AXValueGetValue(v, .cgSize, &s) ? s : nil
    }

    static func range(_ el: AXUIElement, _ name: String) -> UTF16Range? {
        guard let v = axValue(raw(el, name)) else { return nil }
        var r = CFRange(location: 0, length: 0)
        guard AXValueGetValue(v, .cfRange, &r), r.location >= 0, r.length >= 0 else { return nil }
        return UTF16Range(location: r.location, length: r.length)
    }

    /// The element's frame in AX space (top-left origin, y down).
    static func frame(_ el: AXUIElement) -> CGRect? {
        guard let p = point(el, positionAttribute), let s = size(el, sizeAttribute) else { return nil }
        return CGRect(origin: p, size: s)
    }

    static func isSettable(_ el: AXUIElement, _ name: String) -> Bool {
        var settable = DarwinBoolean(false)
        guard AXUIElementIsAttributeSettable(el, name as CFString, &settable) == .success else { return false }
        return settable.boolValue
    }

    static func pid(_ el: AXUIElement) -> pid_t? {
        var pid: pid_t = 0
        return AXUIElementGetPid(el, &pid) == .success ? pid : nil
    }

    // MARK: Parameterized

    static func parameterized(_ el: AXUIElement, _ name: String, _ parameter: CFTypeRef) -> CFTypeRef? {
        var value: CFTypeRef?
        guard AXUIElementCopyParameterizedAttributeValue(el, name as CFString, parameter, &value) == .success else {
            return nil
        }
        return value
    }

    static func rangeValue(_ r: UTF16Range) -> AXValue? {
        var cf = CFRange(location: r.location, length: r.length)
        return AXValueCreate(.cfRange, &cf)
    }

    static func bounds(_ el: AXUIElement, for r: UTF16Range) -> CGRect? {
        guard let param = rangeValue(r), let v = axValue(parameterized(el, boundsForRange, param)) else { return nil }
        var rect = CGRect.zero
        return AXValueGetValue(v, .cgRect, &rect) ? rect : nil
    }

    static func line(_ el: AXUIElement, forIndex index: Int) -> Int? {
        (parameterized(el, lineForIndex, NSNumber(value: index)) as? NSNumber)?.intValue
    }

    static func range(_ el: AXUIElement, forLine line: Int) -> UTF16Range? {
        guard let v = axValue(parameterized(el, rangeForLine, NSNumber(value: line))) else { return nil }
        var r = CFRange(location: 0, length: 0)
        guard AXValueGetValue(v, .cfRange, &r), r.location >= 0, r.length >= 0 else { return nil }
        return UTF16Range(location: r.location, length: r.length)
    }

    static func string(_ el: AXUIElement, for r: UTF16Range) -> String? {
        guard let param = rangeValue(r) else { return nil }
        return parameterized(el, stringForRange, param) as? String
    }

    // MARK: Writing

    @discardableResult
    static func set(_ el: AXUIElement, _ name: String, _ value: CFTypeRef) -> Bool {
        AXUIElementSetAttributeValue(el, name as CFString, value) == .success
    }

    @discardableResult
    static func setSelectedRange(_ el: AXUIElement, _ r: UTF16Range) -> Bool {
        guard let v = rangeValue(r) else { return false }
        return set(el, selectedTextRange, v)
    }

    @discardableResult
    static func press(_ el: AXUIElement) -> Bool {
        AXUIElementPerformAction(el, pressAction as CFString) == .success
    }

    // MARK: Trust

    static var isTrusted: Bool { AXIsProcessTrusted() }

    /// Shows the system's Accessibility prompt (only after onboarding has
    /// explained why it is needed).
    @discardableResult
    static func requestTrust() -> Bool {
        // The value of kAXTrustedCheckOptionPrompt.
        return AXIsProcessTrustedWithOptions(["AXTrustedCheckOptionPrompt": true] as CFDictionary)
    }

    static let settingsURL = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!
}
