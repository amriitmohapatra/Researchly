// swift-tools-version:5.9
//
// Researchly Overlay for macOS (PLAN S4d R7; docs/inline-review-design.md §6).
//
// Two targets:
//   ResearchlyOverlayCore  Foundation only. Text snapshots, UTF-16 ranges,
//                          the eligibility gate, the six states, the engine
//                          client. Builds and tests on Linux too.
//                          Colours, underline patterns and state looks come
//                          from the generated tokens: packages/design-tokens
//                          is a local Swift package (its Package.swift builds
//                          dist/ResearchlyTokens.swift as is), so build from
//                          a full checkout.
//   ResearchlyOverlay      The AppKit shell (Accessibility, overlay windows,
//                          menu bar). macOS only, so it is declared only when
//                          this manifest is evaluated on a Mac.
import PackageDescription

var products: [Product] = [
    .library(name: "ResearchlyOverlayCore", targets: ["ResearchlyOverlayCore"]),
]

let tokens: Target.Dependency = .product(name: "ResearchlyDesignTokens", package: "design-tokens")

var targets: [Target] = [
    .target(
        name: "ResearchlyOverlayCore",
        dependencies: [tokens],
        path: "Sources/ResearchlyOverlayCore"
    ),
    .testTarget(
        name: "ResearchlyOverlayCoreTests",
        dependencies: ["ResearchlyOverlayCore", tokens],
        path: "Tests/ResearchlyOverlayCoreTests",
        exclude: ["Fixtures"]
    ),
]

#if os(macOS)
products.append(.executable(name: "ResearchlyOverlay", targets: ["ResearchlyOverlay"]))
targets.append(
    .executableTarget(
        name: "ResearchlyOverlay",
        dependencies: ["ResearchlyOverlayCore", tokens],
        path: "Sources/ResearchlyOverlay",
        linkerSettings: [
            .linkedFramework("AppKit"),
            .linkedFramework("ApplicationServices"),
            .linkedFramework("QuartzCore"),
        ]
    )
)
#endif

let package = Package(
    name: "ResearchlyOverlay",
    platforms: [.macOS(.v14)],
    products: products,
    dependencies: [.package(path: "../../packages/design-tokens")],
    targets: targets
)
