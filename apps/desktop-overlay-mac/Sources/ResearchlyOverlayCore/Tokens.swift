import Foundation

// TEMPORARY: replace with the file generated from
// packages/design-tokens/tokens.json (PLAN S4d R2) once it exists. Until
// then these values follow the website's category palette in
// apps/web/app/globals.css (Okabe & Ito derived; light and dark), so the Mac
// client and the website already speak the same visual language. The shape
// of this API (Tokens.category(_:), .widget…) is what the generated file
// should provide.

/// An sRGB colour with alpha, components 0...1.
public struct RGBA: Equatable {
    public let red: Double
    public let green: Double
    public let blue: Double
    public let alpha: Double

    public init(hex: UInt32, alpha: Double = 1) {
        red = Double((hex >> 16) & 0xFF) / 255
        green = Double((hex >> 8) & 0xFF) / 255
        blue = Double(hex & 0xFF) / 255
        self.alpha = alpha
    }

    /// WCAG relative luminance.
    public var luminance: Double {
        func lin(_ c: Double) -> Double { c <= 0.03928 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4) }
        return 0.2126 * lin(red) + 0.7152 * lin(green) + 0.0722 * lin(blue)
    }

    /// WCAG contrast ratio against another opaque colour.
    public func contrast(with other: RGBA) -> Double {
        let a = luminance, b = other.luminance
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)
    }
}

/// A colour with its light and dark appearance.
public struct ThemedColor: Equatable {
    public let light: RGBA
    public let dark: RGBA

    public init(_ light: RGBA, _ dark: RGBA) {
        self.light = light
        self.dark = dark
    }

    public func resolve(dark isDark: Bool) -> RGBA { isDark ? dark : light }
}

/// How an underline is drawn, so colour is never the only cue (§4).
public enum UnderlinePattern: String, CaseIterable {
    case solid, dashed, dotted, wavyDotted
}

public struct CategoryStyle: Equatable {
    public let name: String
    /// An SF Symbols name; the shapes match the website's category icons
    /// (circle with a cross, upward arrow, open book, sliders).
    public let symbol: String
    public let pattern: UnderlinePattern
    /// Underline and rail colour.
    public let line: ThemedColor
    /// Text in the category's colour (names in cards and teasers).
    public let ink: ThemedColor
    /// Background tint behind a hovered range.
    public let tint: ThemedColor
}

public enum Tokens {
    public static let underlineWidth: Double = 2
    public static let surfaceLight = RGBA(hex: 0xFFFFFF)
    public static let surfaceDark = RGBA(hex: 0x1B1E23)

    public static func category(_ c: Category) -> CategoryStyle {
        switch c {
        case .correction:
            return CategoryStyle(
                name: "Correction", symbol: "xmark.circle", pattern: .solid,
                line: ThemedColor(RGBA(hex: 0xD55E00), RGBA(hex: 0xF08A4B)),
                ink: ThemedColor(RGBA(hex: 0x9E3B00), RGBA(hex: 0xFFA070)),
                tint: ThemedColor(RGBA(hex: 0xFBE4D6), RGBA(hex: 0xD55E00, alpha: 0.26)))
        case .improvement, .other:
            return CategoryStyle(
                name: c == .improvement ? "Improvement" : "Suggestion", symbol: "arrow.up", pattern: .dashed,
                line: ThemedColor(RGBA(hex: 0x0072B2), RGBA(hex: 0x56B4E9)),
                ink: ThemedColor(RGBA(hex: 0x005A8F), RGBA(hex: 0x86C8F2)),
                tint: ThemedColor(RGBA(hex: 0xDCEBF6), RGBA(hex: 0x0072B2, alpha: 0.32)))
        case .convention:
            return CategoryStyle(
                name: "Convention", symbol: "book", pattern: .dotted,
                line: ThemedColor(RGBA(hex: 0x009E73), RGBA(hex: 0x3CC196)),
                ink: ThemedColor(RGBA(hex: 0x00694D), RGBA(hex: 0x66D4B0)),
                tint: ThemedColor(RGBA(hex: 0xD6EFE5), RGBA(hex: 0x009E73, alpha: 0.26)))
        case .preference:
            return CategoryStyle(
                name: "Preference", symbol: "slider.horizontal.3", pattern: .wavyDotted,
                line: ThemedColor(RGBA(hex: 0xCC79A7), RGBA(hex: 0xD88BB8)),
                ink: ThemedColor(RGBA(hex: 0x8A3A69), RGBA(hex: 0xEAA8CD)),
                tint: ThemedColor(RGBA(hex: 0xF6E2ED), RGBA(hex: 0xCC79A7, alpha: 0.26)))
        }
    }

    // Widget (the website's navy accent and its dark counterpart).
    public static let widgetRing = ThemedColor(RGBA(hex: 0x26344D), RGBA(hex: 0xB8C8E6))
    public static let widgetBadge = ThemedColor(RGBA(hex: 0x26344D), RGBA(hex: 0xB8C8E6))
    public static let widgetBadgeText = ThemedColor(RGBA(hex: 0xFFFFFF), RGBA(hex: 0x10141C))
    public static let widgetSurface = ThemedColor(RGBA(hex: 0xFFFFFF), RGBA(hex: 0x23272E))
    public static let warning = ThemedColor(RGBA(hex: 0xA15C00), RGBA(hex: 0xF0C05A))
    public static let offline = ThemedColor(RGBA(hex: 0x6B717A), RGBA(hex: 0x9AA0AA))
    public static let focus = ThemedColor(RGBA(hex: 0x1F5FBF), RGBA(hex: 0x8AB4FF))
}
