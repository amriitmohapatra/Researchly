import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Where the text goes: the hosted engine the writer named, or the engine on
/// this computer. Nothing else ever receives it.
public enum EngineChoice: Equatable {
    case thisComputer
    case hosted(URL)

    public static let localURL = URL(string: "http://127.0.0.1:3517")!

    public var baseURL: URL {
        switch self {
        case .thisComputer: return EngineChoice.localURL
        case .hosted(let url): return url
        }
    }

    /// A hosted engine must use HTTPS; plain HTTP is accepted only for this
    /// computer (loopback), so text never crosses a network unencrypted.
    public static func validatedHostedURL(_ raw: String) -> URL? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed), let scheme = url.scheme?.lowercased(),
              let host = url.host, !host.isEmpty else { return nil }
        if scheme == "https" { return url }
        if scheme == "http", ["127.0.0.1", "localhost", "::1"].contains(host.lowercased()) { return url }
        return nil
    }

    /// `{base}/v1/check-paragraphs`, whatever trailing slash the base has.
    public var checkURL: URL {
        var base = baseURL.absoluteString
        while base.hasSuffix("/") { base.removeLast() }
        return URL(string: base + "/v1/check-paragraphs")!
    }
}

public enum EngineError: Error, Equatable {
    /// No answer: no network, nothing listening, a timeout.
    case unreachable(String)
    /// The engine answered with an error status.
    case refused(status: Int, message: String?)
    /// The answer was not a live-check reply.
    case malformed
    /// The reply was for another revision than the one sent.
    case revisionMismatch(sent: Int, received: Int)

    /// "Can’t check right now" plus a next step, in the writer's words.
    public var userMessage: String {
        switch self {
        case .unreachable:
            return "Can’t reach the engine. Check your connection, or choose another engine in the menu bar."
        case .refused(let status, let message):
            if status == 429 { return "The engine is busy. Researchly will try again shortly." }
            if status == 404 { return "This engine doesn’t offer live checks yet. Update it, or choose another engine." }
            if status == 401 || status == 403 { return "The engine refused the request. Check the engine address in the menu bar." }
            if let m = message, !m.isEmpty { return "The engine couldn’t check this: \(m)" }
            return "The engine couldn’t check this right now (error \(status))."
        case .malformed, .revisionMismatch:
            return "The engine’s answer wasn’t understood. Try updating the engine or this app."
        }
    }
}

/// One HTTP POST. Abstracted so tests never touch the network.
public protocol HTTPTransport {
    func post(_ url: URL, body: Data, headers: [String: String], timeout: TimeInterval,
              completion: @escaping (Result<(status: Int, body: Data), Error>) -> Void)
}

/// URLSession without caches, cookies or credential storage: the request
/// carries document text and nothing about it may be kept on disk.
public final class URLSessionTransport: HTTPTransport {
    private let session: URLSession

    public init() {
        let config = URLSessionConfiguration.ephemeral
        config.urlCache = nil
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.httpCookieStorage = nil
        config.httpShouldSetCookies = false
        config.urlCredentialStorage = nil
        session = URLSession(configuration: config)
    }

    public func post(_ url: URL, body: Data, headers: [String: String], timeout: TimeInterval,
                     completion: @escaping (Result<(status: Int, body: Data), Error>) -> Void) {
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: timeout)
        request.httpMethod = "POST"
        request.httpBody = body
        for (k, v) in headers { request.setValue(v, forHTTPHeaderField: k) }
        session.dataTask(with: request) { data, response, error in
            if let error = error { completion(.failure(error)); return }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            completion(.success((status: status, body: data ?? Data())))
        }.resume()
    }
}

/// Anything that can run a live check (the engine client, or a test fake).
public protocol EngineChecking: AnyObject {
    func check(_ request: CheckRequest, completion: @escaping (Result<CheckResponse, EngineError>) -> Void)
}

/// The client for `POST {engine}/v1/check-paragraphs` (design note §5).
/// It sends no `Origin` header (native clients are allowed without one)
/// and logs nothing.
public final class EngineClient: EngineChecking {
    public var choice: EngineChoice
    public var timeout: TimeInterval
    private let transport: HTTPTransport
    private let userAgent: String

    public init(choice: EngineChoice, transport: HTTPTransport = URLSessionTransport(),
                timeout: TimeInterval = 15, userAgent: String = "ResearchlyOverlay/0.1 (macOS)") {
        self.choice = choice
        self.transport = transport
        self.timeout = timeout
        self.userAgent = userAgent
    }

    public func check(_ request: CheckRequest, completion: @escaping (Result<CheckResponse, EngineError>) -> Void) {
        let body: Data
        do { body = try JSONEncoder().encode(request) } catch { completion(.failure(.malformed)); return }
        let headers = [
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": userAgent,
        ]
        let sent = request.revision
        transport.post(choice.checkURL, body: body, headers: headers, timeout: timeout) { result in
            completion(EngineClient.interpret(result, sentRevision: sent))
        }
    }

    /// Maps a transport result to a reply or an error. Public for tests.
    public static func interpret(_ result: Result<(status: Int, body: Data), Error>,
                                 sentRevision: Int) -> Result<CheckResponse, EngineError> {
        switch result {
        case .failure(let error):
            return .failure(.unreachable(String(describing: type(of: error))))
        case .success(let reply):
            guard (200..<300).contains(reply.status) else {
                return .failure(.refused(status: reply.status, message: errorMessage(in: reply.body)))
            }
            guard let response = try? JSONDecoder().decode(CheckResponse.self, from: reply.body) else {
                return .failure(.malformed)
            }
            if let echoed = response.revision, echoed != sentRevision {
                return .failure(.revisionMismatch(sent: sentRevision, received: echoed))
            }
            return .success(response)
        }
    }

    /// The engine's error envelope is `{"error": {"code", "message"}}`;
    /// FastAPI's own is `{"detail": "..."}`. Only short messages are shown.
    static func errorMessage(in body: Data) -> String? {
        guard let json = try? JSONDecoder().decode(JSONValue.self, from: body) else { return nil }
        let message = json["error"]?["message"]?.stringValue ?? json["detail"]?.stringValue
        guard let m = message, m.count <= 200 else { return nil }
        return m
    }
}
