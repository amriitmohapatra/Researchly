// swift-tools-version:5.9
//
// Researchly Overlay for macOS (PLAN S4d R7; docs/inline-review-design.md §6).
//
// Two targets:
//   ResearchlyOverlayCore  Foundation only. Text snapshots, UTF-16 ranges,
//                          the eligibility gate, the six states, the engine
//                          client. Builds and tests on Linux too.
//   ResearchlyOverlay      The AppKit shell (Accessibility, overlay windows,
//                          menu bar). macOS only, so it is declared only when
//                          this manifest is evaluated on a Mac.
import PackageDescription

var products: [Product] = [
    .library(name: "ResearchlyOverlayCore", targets: ["ResearchlyOverlayCore"]),
]

var targets: [Target] = [
    .target(
        name: "ResearchlyOverlayCore",
        path: "Sources/ResearchlyOverlayCore"
    ),
    .testTarget(
        name: "ResearchlyOverlayCoreTests",
        dependencies: ["ResearchlyOverlayCore"],
        path: "Tests/ResearchlyOverlayCoreTests",
        exclude: ["Fixtures"]
    ),
]

#if os(macOS)
products.append(.executable(name: "ResearchlyOverlay", targets: ["ResearchlyOverlay"]))
targets.append(
    .executableTarget(
        name: "ResearchlyOverlay",
        dependencies: ["ResearchlyOverlayCore"],
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
    targets: targets
)
