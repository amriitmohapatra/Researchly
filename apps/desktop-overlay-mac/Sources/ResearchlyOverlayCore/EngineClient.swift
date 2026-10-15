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
    /// Too many checks (429): wait at least `retryAfter` seconds, when the
    /// engine said how long.
    case rateLimited(retryAfter: TimeInterval?)
    /// The engine refused this request as it was (400, 401, 403, 413, 422):
    /// sending it again would be refused again, so it is not retried until
    /// the writer edits. `code` is the engine's error code
    /// (`invalid_request`, `sign_in_required`, …), never document text.
    case rejected(status: Int, code: String?)
    /// Any other error status (404 from an engine without the live check,
    /// 5xx): retried with backoff.
    case refused(status: Int, message: String?)
    /// The answer was not a live-check reply.
    case malformed
    /// The reply was for another revision than the one sent.
    case revisionMismatch(sent: Int, received: Int)

    /// Statuses that mean "this request will never succeed as it is".
    static let rejectedStatuses: Set<Int> = [400, 401, 403, 413, 422]

    /// Whether a later identical request could succeed, so a retry with
    /// backoff makes sense.
    public var isRetryable: Bool {
        if case .rejected = self { return false }
        return true
    }

    /// "Can’t check right now" plus a next step, in the writer's words.
    public var userMessage: String {
        switch self {
        case .unreachable:
            return "Can’t reach the engine. Check your connection, or choose another engine in the menu bar."
        case .rateLimited:
            return "The engine is busy. Researchly will try again shortly."
        case .rejected(let status, let code):
            if code == "sign_in_required" {
                return "This engine checks only a little text at a time without an account. Choose This computer in the menu bar, or check a shorter passage."
            }
            if status == 413 || code == "payload_too_large" {
                return "This text is too long to check as you type. Researchly will try again after your next edit."
            }
            if status == 401 || status == 403 {
                return "The engine refused the request. Check the engine address in the menu bar."
            }
            return "The engine couldn’t check this text as it was sent. Researchly will try again after your next edit; if this keeps happening, update the engine or this app."
        case .refused(let status, let message):
            if status == 404 { return "This engine doesn’t offer live checks yet. Update it, or choose another engine." }
            if let m = message, !m.isEmpty { return "The engine couldn’t check this: \(m)" }
            return "The engine couldn’t check this right now (error \(status))."
        case .malformed, .revisionMismatch:
            return "The engine’s answer wasn’t understood. Try updating the engine or this app."
        }
    }
}

/// What came back over HTTP: the status, the body, and the headers the
/// client acts on (names in lower case).
public struct HTTPReply: Equatable {
    public var status: Int
    public var body: Data
    public var headers: [String: String]

    public init(status: Int, body: Data, headers: [String: String] = [:]) {
        self.status = status
        self.body = body
        self.headers = Dictionary(headers.map { ($0.key.lowercased(), $0.value) }, uniquingKeysWith: { a, _ in a })
    }
}

/// One HTTP POST. Abstracted so tests never touch the network.
public protocol HTTPTransport {
    func post(_ url: URL, body: Data, headers: [String: String], timeout: TimeInterval,
              completion: @escaping (Result<HTTPReply, Error>) -> Void)
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
                     completion: @escaping (Result<HTTPReply, Error>) -> Void) {
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: timeout)
        request.httpMethod = "POST"
        request.httpBody = body
        for (k, v) in headers { request.setValue(v, forHTTPHeaderField: k) }
        session.dataTask(with: request) { data, response, error in
            if let error = error { completion(.failure(error)); return }
            let http = response as? HTTPURLResponse
            var replyHeaders: [String: String] = [:]
            if let retry = http?.value(forHTTPHeaderField: "Retry-After") { replyHeaders["retry-after"] = retry }
            completion(.success(HTTPReply(status: http?.statusCode ?? 0, body: data ?? Data(), headers: replyHeaders)))
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
    public static func interpret(_ result: Result<HTTPReply, Error>,
                                 sentRevision: Int) -> Result<CheckResponse, EngineError> {
        switch result {
        case .failure(let error):
            return .failure(.unreachable(String(describing: type(of: error))))
        case .success(let reply):
            guard (200..<300).contains(reply.status) else {
                if reply.status == 429 {
                    return .failure(.rateLimited(retryAfter: retryAfter(reply.headers["retry-after"])))
                }
                if EngineError.rejectedStatuses.contains(reply.status) {
                    return .failure(.rejected(status: reply.status, code: errorCode(in: reply.body)))
                }
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

    /// Retry-After in seconds (the engine sends whole seconds; an HTTP date
    /// is not used by it and is ignored).
    static func retryAfter(_ value: String?) -> TimeInterval? {
        guard let v = value?.trimmingCharacters(in: .whitespaces), let seconds = Double(v),
              seconds.isFinite, seconds >= 0 else { return nil }
        return seconds
    }

    /// The engine's error envelope is `{"error": {"code", "message", "request_id"}}`.
    static func errorCode(in body: Data) -> String? {
        guard let json = try? JSONDecoder().decode(JSONValue.self, from: body),
              let code = json["error"]?["code"]?.stringValue, code.count <= 64 else { return nil }
        return code
    }

    /// The envelope's message (FastAPI's own is `{"detail": "..."}`). Only
    /// short messages are shown.
    static func errorMessage(in body: Data) -> String? {
        guard let json = try? JSONDecoder().decode(JSONValue.self, from: body) else { return nil }
        let message = json["error"]?["message"]?.stringValue ?? json["detail"]?.stringValue
        guard let m = message, m.count <= 200 else { return nil }
        return m
    }
}
