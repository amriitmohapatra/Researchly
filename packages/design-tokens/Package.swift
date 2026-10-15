// swift-tools-version:5.9
//
// The generated Swift tokens (dist/ResearchlyTokens.swift, from tokens.json
// by scripts/build.mjs) as a Swift package, so the macOS overlay
// (apps/desktop-overlay-mac) compiles the generated file itself, never a
// copy: its Package.swift depends on this folder by path. Foundation only;
// builds on Linux too. Do not add sources here: regenerate dist/ instead.
import PackageDescription

let package = Package(
    name: "ResearchlyDesignTokens",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "ResearchlyDesignTokens", targets: ["ResearchlyDesignTokens"]),
    ],
    targets: [
        .target(
            name: "ResearchlyDesignTokens",
            path: "dist",
            exclude: ["tokens.css", "tokens.ts", "ResearchlyTokens.cs"],
            sources: ["ResearchlyTokens.swift"]
        ),
    ]
)
