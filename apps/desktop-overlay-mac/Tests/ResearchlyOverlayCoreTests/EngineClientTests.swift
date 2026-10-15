import XCTest
@testable import ResearchlyOverlayCore

final class EngineClientTests: XCTestCase {
    func testFullResponseDecodes() throws {
        let r = try JSONDecoder().decode(CheckResponse.self, from: Repo.fixture("check-response-full.json"))
        XCTAssertEqual(r.revision, 7)
        XCTAssertEqual(r.paragraphs.map { $0.id }, ["p1", "p2"])
        let s = r.paragraphs[0].suggestions
        XCTAssertEqual(s.count, 2)
        XCTAssertEqual(s[0].id, "S100:0:4:3f2a")
        XCTAssertEqual(s[0].ruleID, "S100")
        XCTAssertEqual(s[0].category, .correction)
        XCTAssertTrue(s[0].critical)
        XCTAssertEqual(s[0].replacements, ["Their", "There"])
        XCTAssertEqual(s[0].plain, "This word may be misspelt.")
        XCTAssertEqual(s[0].fixSafety, "review")
        XCTAssertEqual(s[1].category, .convention)
        XCTAssertFalse(s[1].critical)
        XCTAssertEqual(s[1].fixSafety, "safe")
        XCTAssertTrue(r.health.degraded)
        XCTAssertEqual(r.health.downTiers, ["Grammar"])
        XCTAssertEqual(r.health.detail, "Try again in a minute.")
        XCTAssertEqual(r.state, "issues")
    }

    func testMinimalResponseIsToleratedAndBadItemsSkipped() throws {
        let r = try JSONDecoder().decode(CheckResponse.self, from: Repo.fixture("check-response-minimal.json"))
        XCTAssertNil(r.revision)
        XCTAssertEqual(r.paragraphs.map { $0.id }, ["p9", "p10"])   // the item without an id is skipped
        let s = r.paragraphs[0].suggestions
        XCTAssertEqual(s.count, 3)                                    // "three" is not an offset
        XCTAssertEqual(s[0].replacements, ["shorter"])                // a single `replacement` is accepted
        XCTAssertEqual(s[0].message, "")
        XCTAssertEqual(s[0].fixSafety, "review")
        XCTAssertFalse(s[0].critical)
        XCTAssertEqual(s[0].id, "improvement:3-8")                    // a fallback id when none is sent
        XCTAssertEqual(s[1].category, .other("newfangled"))
        XCTAssertEqual(Tokens.category(s[1].category).name, "Suggestion")
        XCTAssertEqual(s[2].category, .improvement)                   // missing category
        XCTAssertTrue(r.paragraphs[1].suggestions.isEmpty)
        XCTAssertFalse(r.health.degraded)
    }

    func testHealthShapes() {
        let partial = HealthSummary(json: nil, state: "partial")
        XCTAssertTrue(partial.degraded)
        XCTAssertEqual(partial.reason, "Part of the check is unavailable right now.")
        let list = try! JSONDecoder().decode(JSONValue.self, from: Data(#"[{"label":"Spelling","ok":false}]"#.utf8))
        XCTAssertEqual(HealthSummary(json: list, state: nil).downTiers, ["Spelling"])
        let ok = try! JSONDecoder().decode(JSONValue.self, from: Data(#"{"status":"ok","tiers":[{"label":"Parser","ok":true}]}"#.utf8))
        XCTAssertFalse(HealthSummary(json: ok, state: nil).degraded)
        XCTAssertNil(HealthSummary.ok.reason)
    }

    func testRequestEncodingMatchesTheContract() throws {
        let req = CheckRequest(revision: 3,
                               paragraphs: [ParagraphPayload(id: "p1", text: "Résumé \u{1F44D}", heading: "Methods"),
                                            ParagraphPayload(id: "p2", text: "Plain.")],
                               options: CheckOptions(showPreferences: false))
        let json = try JSONSerialization.jsonObject(with: JSONEncoder().encode(req)) as! [String: Any]
        XCTAssertEqual(json["revision"] as? Int, 3)
        let ps = json["paragraphs"] as! [[String: Any]]
        XCTAssertEqual(ps[0]["id"] as? String, "p1")
        XCTAssertEqual(ps[0]["text"] as? String, "Résumé \u{1F44D}")
        XCTAssertEqual(ps[0]["heading"] as? String, "Methods")
        XCTAssertNil(ps[1]["heading"])            // optional keys are omitted, not null
        XCTAssertNil(ps[1]["style"])
        let options = json["options"] as! [String: Any]
        XCTAssertEqual(options["show_preferences"] as? Bool, false)
        XCTAssertNil(options["spelling"])
    }

    func testInterpretErrors() throws {
        struct Boom: Error {}
        XCTAssertEqual(EngineClient.interpret(.failure(Boom()), sentRevision: 1), .failure(.unreachable("Boom")))
        let body = try Repo.fixture("error-response.json")
        let refused = EngineClient.interpret(.success((status: 429, body: body)), sentRevision: 1)
        XCTAssertEqual(refused, .failure(.refused(status: 429, message: "Too many requests. Try again shortly.")))
        XCTAssertEqual(EngineClient.interpret(.success((status: 200, body: Data("<html>".utf8))), sentRevision: 1),
                       .failure(.malformed))
        let ok = EngineClient.interpret(.success((status: 200, body: try Repo.fixture("check-response-full.json"))),
                                        sentRevision: 7)
        XCTAssertEqual(try ok.get().paragraphs.count, 2)
        let noEcho = EngineClient.interpret(.success((status: 200, body: try Repo.fixture("check-response-minimal.json"))),
                                            sentRevision: 7)
        XCTAssertNoThrow(try noEcho.get())          // a missing echo is accepted
    }

    func testErrorMessagesForTheWriter() {
        XCTAssertTrue(EngineError.unreachable("x").userMessage.contains("Can’t reach the engine"))
        XCTAssertTrue(EngineError.refused(status: 404, message: nil).userMessage.contains("doesn’t offer live checks"))
        XCTAssertTrue(EngineError.refused(status: 429, message: nil).userMessage.contains("busy"))
    }

    func testEngineChoiceURLs() {
        XCTAssertEqual(EngineChoice.thisComputer.checkURL.absoluteString, "http://127.0.0.1:3517/v1/check-paragraphs")
        let hosted = EngineChoice.validatedHostedURL(" https://engine.example.org/ ")!
        XCTAssertEqual(EngineChoice.hosted(hosted).checkURL.absoluteString, "https://engine.example.org/v1/check-paragraphs")
        XCTAssertNil(EngineChoice.validatedHostedURL("http://engine.example.org"))   // never plain HTTP over a network
        XCTAssertNotNil(EngineChoice.validatedHostedURL("http://localhost:8080"))
        XCTAssertNil(EngineChoice.validatedHostedURL("not a url"))
        XCTAssertNil(EngineChoice.validatedHostedURL("ftp://engine.example.org"))
    }

    func testClientSendsNoOriginAndUsesTheTransport() {
        final class Recorder: HTTPTransport {
            var url: URL?
            var headers: [String: String] = [:]
            var body = Data()
            func post(_ url: URL, body: Data, headers: [String: String], timeout: TimeInterval,
                      completion: @escaping (Result<(status: Int, body: Data), Error>) -> Void) {
                self.url = url
                self.headers = headers
                self.body = body
                completion(.success((status: 200, body: Data(#"{"revision": 1, "paragraphs": [{"id": "p1", "suggestions": []}]}"#.utf8))))
            }
        }
        let rec = Recorder()
        let client = EngineClient(choice: .thisComputer, transport: rec)
        var got: Result<CheckResponse, EngineError>?
        client.check(CheckRequest(revision: 1, paragraphs: [ParagraphPayload(id: "p1", text: "x")], options: CheckOptions())) {
            got = $0
        }
        XCTAssertEqual(rec.url?.path, "/v1/check-paragraphs")
        XCTAssertNil(rec.headers["Origin"])
        XCTAssertEqual(rec.headers["Content-Type"], "application/json")
        XCTAssertEqual(try got?.get().paragraphs.first?.id, "p1")
    }
}

final class GeometryTests: XCTestCase {
    func testFlipToAppKitSpace() {
        let r = OverlayGeometry.flip(CGRect(x: 100, y: 50, width: 40, height: 20), primaryHeight: 1000)
        XCTAssertEqual(r, CGRect(x: 100, y: 930, width: 40, height: 20))
        // A display above the primary one has negative AX y.
        let above = OverlayGeometry.flip(CGRect(x: 0, y: -300, width: 10, height: 10), primaryHeight: 1000)
        XCTAssertEqual(above.origin.y, 1290)
    }

    func testSplitByLines() {
        let lines = [UTF16Range(location: 0, length: 40), UTF16Range(location: 40, length: 40), UTF16Range(location: 80, length: 30)]
        XCTAssertEqual(OverlayGeometry.split(UTF16Range(location: 35, length: 50), byLines: lines),
                       [UTF16Range(location: 35, length: 5), UTF16Range(location: 40, length: 40), UTF16Range(location: 80, length: 5)])
        XCTAssertEqual(OverlayGeometry.split(UTF16Range(location: 3, length: 4), byLines: []), [UTF16Range(location: 3, length: 4)])
    }

    func testCharacterRectsGroupIntoLines() {
        let chars = [CGRect(x: 10, y: 100, width: 7, height: 16), CGRect(x: 17, y: 100, width: 7, height: 16),
                     CGRect(x: 24, y: 101, width: 7, height: 15),
                     CGRect(x: 10, y: 118, width: 7, height: 16), CGRect(x: 17, y: 118, width: 7, height: 16),
                     CGRect(x: 0, y: 0, width: 0, height: 0)]
        let lines = OverlayGeometry.lineRects(fromCharacterRects: chars)
        XCTAssertEqual(lines.count, 2)
        XCTAssertEqual(lines[0].minX, 10)
        XCTAssertEqual(lines[0].maxX, 31)
        XCTAssertEqual(lines[1].maxX, 24)
    }

    func testClipDropsScrolledAwayLines() {
        let visible = CGRect(x: 0, y: 100, width: 300, height: 200)
        let clipped = OverlayGeometry.clip([CGRect(x: 10, y: 50, width: 50, height: 16),
                                            CGRect(x: 10, y: 120, width: 400, height: 16),
                                            CGRect(x: 10, y: 295, width: 50, height: 16)], to: visible)
        XCTAssertEqual(clipped, [CGRect(x: 10, y: 120, width: 290, height: 16), CGRect(x: 10, y: 295, width: 50, height: 5)])
    }

    func testUsableRects() {
        XCTAssertTrue(OverlayGeometry.isUsable(CGRect(x: 5, y: 5, width: 10, height: 14)))
        XCTAssertFalse(OverlayGeometry.isUsable(CGRect(x: 5, y: 5, width: 0, height: 14)))
        XCTAssertFalse(OverlayGeometry.isUsable(CGRect(x: 5, y: 5, width: 10, height: 900)))
        XCTAssertFalse(OverlayGeometry.isUsable(CGRect(x: 0, y: 0, width: 10, height: 14)))
        XCTAssertFalse(OverlayGeometry.isUsable(CGRect(x: CGFloat.nan, y: 5, width: 10, height: 14)))
    }

    func testWidgetOriginPerCornerAndDrag() {
        let field = CGRect(x: 100, y: 100, width: 400, height: 300)
        let size = CGSize(width: 24, height: 24)
        let br = OverlayGeometry.widgetOrigin(field: field, widget: size, placement: WidgetPlacement(corner: .bottomRight, offsetX: 6, offsetY: 6))
        XCTAssertEqual(br, CGPoint(x: 470, y: 370))
        let tl = OverlayGeometry.widgetOrigin(field: field, widget: size, placement: WidgetPlacement(corner: .topLeft, offsetX: 4, offsetY: 2))
        XCTAssertEqual(tl, CGPoint(x: 104, y: 102))
        let forbidden = WidgetPlacement(corner: .bottomRight, offsetX: 6, offsetY: 6, forbiddenCorners: [.bottomRight])
        XCTAssertEqual(OverlayGeometry.widgetOrigin(field: field, widget: size, placement: forbidden), CGPoint(x: 106, y: 370))
        let dragged = OverlayGeometry.widgetOrigin(field: field, widget: size, placement: WidgetPlacement(),
                                                   userOffset: CGPoint(x: -100, y: -50))
        XCTAssertEqual(dragged, CGPoint(x: 370, y: 320))
        let far = OverlayGeometry.widgetOrigin(field: field, widget: size, placement: WidgetPlacement(),
                                               userOffset: CGPoint(x: 5000, y: 5000))
        XCTAssertEqual(far, CGPoint(x: 488, y: 388))          // clamped: at most half outside
    }

    func testWavePointsStayNearTheBaseline() {
        let pts = OverlayGeometry.wavePoints(from: 10, to: 40, baseline: 5)
        XCTAssertEqual(pts.first?.x, 10)
        XCTAssertEqual(pts.last?.x, 40)
        XCTAssertTrue(pts.allSatisfy { abs($0.y - 5) <= 1.5001 })
        XCTAssertTrue(OverlayGeometry.wavePoints(from: 5, to: 5, baseline: 0).isEmpty)
    }

    func testHitTest() {
        let rects = [CGRect(x: 10, y: 10, width: 30, height: 4)]
        XCTAssertTrue(OverlayGeometry.hitTest(CGPoint(x: 20, y: 12), rects: rects))
        XCTAssertTrue(OverlayGeometry.hitTest(CGPoint(x: 20, y: 15.5), rects: rects))
        XCTAssertFalse(OverlayGeometry.hitTest(CGPoint(x: 20, y: 30), rects: rects))
    }
}

final class TokenTests: XCTestCase {
    func testEveryCategoryHasADistinctPatternAndIcon() {
        let cats: [Category] = [.correction, .improvement, .convention, .preference]
        let styles = cats.map { Tokens.category($0) }
        XCTAssertEqual(Set(styles.map { $0.pattern }).count, 4)
        XCTAssertEqual(Set(styles.map { $0.symbol }).count, 4)
        XCTAssertEqual(styles.map { $0.pattern }, [.solid, .dashed, .dotted, .wavyDotted])
        XCTAssertEqual(styles.map { $0.name }, ["Correction", "Improvement", "Convention", "Preference"])
    }

    func testCategoryTextIsReadableInBothThemes() {
        for c in [Category.correction, .improvement, .convention, .preference] {
            let ink = Tokens.category(c).ink
            XCTAssertGreaterThanOrEqual(ink.light.contrast(with: Tokens.surfaceLight), 4.5, "\(c) light")
            XCTAssertGreaterThanOrEqual(ink.dark.contrast(with: Tokens.surfaceDark), 4.5, "\(c) dark")
            let line = Tokens.category(c).line
            XCTAssertGreaterThanOrEqual(line.light.contrast(with: Tokens.surfaceLight), 2.5, "\(c) underline light")
            XCTAssertGreaterThanOrEqual(line.dark.contrast(with: Tokens.surfaceDark), 3.0, "\(c) underline dark")
        }
    }
}
