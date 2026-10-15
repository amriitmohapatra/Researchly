import Foundation
import ResearchlyDesignTokens

// The client's view of the generated design tokens
// (packages/design-tokens/dist/ResearchlyTokens.swift, from tokens.json;
// PLAN S4d R2). Every colour, underline pattern, icon and state word comes
// from there; this file only maps the engine's values onto it.

extension Category {
    /// The generated look for this category. A category this client does
    /// not know (from a newer engine) is drawn as an Improvement: a
    /// suggestion, never an error.
    public var look: ResearchlyTokens.Category {
        ResearchlyTokens.categories[rawValue] ?? ResearchlyTokens.categories["improvement"]!
    }

    /// The name shown on teasers and cards.
    public var label: String {
        if case .other = self { return "Suggestion" }
        return look.label
    }
}

extension OverlayState {
    /// The generated look for this state (its mark, colour and words).
    public var look: ResearchlyTokens.StateLook {
        ResearchlyTokens.states[rawValue]!
    }

    /// The state's words, with the count for `issues` ("3 suggestions",
    /// "1 suggestion").
    public func label(count: Int) -> String {
        let look = self.look
        if count == 1, let one = look.labelOne { return one }
        return look.label.replacingOccurrences(of: "{n}", with: String(count))
    }
}
