import Foundation

/// The AI page: plan limits and credits, running agent sessions, and GitHub, all from plugins.
///
/// A plugin is a small script in `plugins/` (shipped) or `~/.phonedeck/plugins/` (yours; a file
/// with the same name replaces the shipped one). It prints one JSON object and exits. Its "type"
/// says what it is: "quota" (limit windows), "credits" (a balance), "sessions" (running agents)
/// or "github". See plugins/README.md for the format. `.py` runs with /usr/bin/python3, `.sh`
/// with /bin/sh, anything else is run directly. Names starting with "_" are skipped (templates).
///
/// Plugins only run while a deck is looking at the AI page (asked in the last 2 minutes):
/// sessions every 10 s, everything else every few minutes. Settings in ~/.phonedeck/ai.json:
///   { "disabled": ["fal"], "refreshMinutes": 5 }
final class AI {
    struct Plugin { let id: String; let url: URL }

    private let queue = DispatchQueue(label: "phonedeck.ai")
    private var results: [String: [String: Any]] = [:]      // plugin id → its last JSON reply
    private var lastRun: [String: Date] = [:]
    private var running: Set<String> = []
    private var lastAsked = Date.distantPast
    private var timer: DispatchSourceTimer?
    private let shippedDir: URL
    private let userDir = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(".phonedeck/plugins")
    private let configFile = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(".phonedeck/ai.json")
    private lazy var env: [String: String] = Self.pluginEnvironment()

    init(shippedDir: URL) {
        self.shippedDir = shippedDir
        let t = DispatchSource.makeTimerSource(queue: queue)
        t.schedule(deadline: .now() + 2, repeating: 5)
        t.setEventHandler { [weak self] in self?.tick() }
        t.resume()
        timer = t
    }

    // MARK: - Settings and discovery

    private var config: (disabled: Set<String>, refresh: TimeInterval) {
        guard let data = try? Data(contentsOf: configFile),
              let j = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return ([], 300) }
        let minutes = (j["refreshMinutes"] as? Double).map { max(1, $0) } ?? 5
        return (Set(j["disabled"] as? [String] ?? []), minutes * 60)
    }

    func plugins() -> [Plugin] {
        var byId: [String: Plugin] = [:]
        for dir in [shippedDir, userDir] {   // later wins: your folder replaces a shipped plugin
            for name in (try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? [] {
                guard !name.hasPrefix("_"), !name.hasPrefix("."), !name.hasSuffix(".md") else { continue }
                let id = (name as NSString).deletingPathExtension
                byId[id] = Plugin(id: id, url: dir.appendingPathComponent(name))
            }
        }
        let off = config.disabled
        return byId.values.filter { !off.contains($0.id) && !off.contains(results[$0.id]?["id"] as? String ?? "") }
            .sorted { $0.id < $1.id }
    }

    // MARK: - Running

    private func tick() {
        guard Date().timeIntervalSince(lastAsked) < 120 else { return }
        let refresh = config.refresh
        for p in plugins() where !running.contains(p.id) {
            let type = results[p.id]?["type"] as? String
            let every: TimeInterval = type == "sessions" ? 10 : type == nil ? 0 : refresh
            if let last = lastRun[p.id], Date().timeIntervalSince(last) < every { continue }
            run(p)
        }
    }

    private func run(_ p: Plugin) {
        running.insert(p.id)
        lastRun[p.id] = Date()
        let env = self.env
        DispatchQueue.global().async {
            let reply = Self.execute(p.url, env: env)
            self.queue.async {
                self.running.remove(p.id)
                var r = reply
                r["plugin"] = p.id
                r["at"] = Date().timeIntervalSince1970 * 1000
                // Keep the last good numbers if a refresh fails, and say so.
                if r["error"] != nil, let old = self.results[p.id], old["error"] == nil, old["type"] as? String == r["type"] as? String {
                    var kept = old; kept["stale"] = r["error"]; self.results[p.id] = kept
                } else {
                    self.results[p.id] = r
                }
            }
        }
    }

    private static func execute(_ url: URL, env: [String: String]) -> [String: Any] {
        let proc = Process()
        switch url.pathExtension {
        case "py": proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3"); proc.arguments = [url.path]
        case "sh": proc.executableURL = URL(fileURLWithPath: "/bin/sh"); proc.arguments = [url.path]
        default: proc.executableURL = url
        }
        proc.environment = env
        proc.currentDirectoryURL = URL(fileURLWithPath: NSHomeDirectory())
        let out = Pipe()
        proc.standardOutput = out
        proc.standardError = FileHandle.nullDevice
        proc.standardInput = FileHandle.nullDevice
        do { try proc.run() } catch { return ["error": "couldn’t start: \(error.localizedDescription)"] }
        let killer = DispatchWorkItem { if proc.isRunning { proc.terminate() } }
        DispatchQueue.global().asyncAfter(deadline: .now() + 30, execute: killer)
        let data = out.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()
        killer.cancel()
        // The last line that parses as a JSON object is the reply (plugins may print noise first).
        let text = String(decoding: data, as: UTF8.self)
        for line in text.split(separator: "\n").reversed() {
            if let d = line.data(using: .utf8), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] { return j }
        }
        return ["error": proc.terminationReason == .uncaughtSignal ? "took longer than 30 s" : "no JSON reply (exit \(proc.terminationStatus))"]
    }

    /// GUI apps get a bare PATH (/usr/bin:/bin...). Plugins need the user's: claude, gh, codex, hc.
    private static func pluginEnvironment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        let home = NSHomeDirectory()
        var paths: [String] = []
        let shell = env["SHELL"] ?? "/bin/zsh"
        let p = Process(); let pipe = Pipe()
        p.executableURL = URL(fileURLWithPath: shell)
        p.arguments = ["-lc", "printf '%s' \"$PATH\""]
        p.standardOutput = pipe; p.standardError = FileHandle.nullDevice; p.standardInput = FileHandle.nullDevice
        if (try? p.run()) != nil {
            let killer = DispatchWorkItem { if p.isRunning { p.terminate() } }
            DispatchQueue.global().asyncAfter(deadline: .now() + 5, execute: killer)
            let s = String(decoding: pipe.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            p.waitUntilExit(); killer.cancel()
            paths = s.split(separator: ":").map(String.init).filter { $0.hasPrefix("/") }
        }
        let extra = ["/opt/homebrew/bin", "/usr/local/bin", home + "/.local/bin", home + "/.claude/local",
                     home + "/.npm-global/bin", home + "/.bun/bin", home + "/.opencode/bin", home + "/.cargo/bin"]
        for e in extra + (env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin").split(separator: ":").map(String.init) where !paths.contains(e) {
            paths.append(e)
        }
        env["PATH"] = paths.joined(separator: ":")
        env["PHONEDECK"] = "1"
        return env
    }

    // MARK: - The reply for the deck

    /// Everything the AI widgets show. Asking also keeps the plugins running for 2 minutes.
    func snapshot() -> [String: Any] {
        return queue.sync {
            let wasIdle = Date().timeIntervalSince(lastAsked) >= 120
            lastAsked = Date()
            if wasIdle { queue.async { self.tick() } }
            return build()
        }
    }

    /// Run every plugin now (the refresh button).
    func refreshAll() {
        queue.async {
            self.lastAsked = Date()
            for p in self.plugins() where !self.running.contains(p.id) { self.run(p) }
        }
    }

    private func build() -> [String: Any] {
        let now = Date().timeIntervalSince1970
        let active = Set(plugins().map { $0.id })
        var quotas: [[String: Any]] = [], setup: [[String: Any]] = [], baseSessions: [[String: Any]] = []
        var enrich: [[String: Any]] = [], github: [String: Any]? = nil, sources: [[String: Any]] = []
        for (id, r) in results.sorted(by: { $0.key < $1.key }) where active.contains(id) {
            let type = r["type"] as? String ?? "?"
            sources.append(["id": r["id"] ?? id, "name": r["name"] ?? id, "type": type,
                            "available": r["available"] as? Bool ?? (r["error"] == nil), "error": r["error"] ?? NSNull()])
            if r["available"] as? Bool == false { setup.append(["name": r["name"] ?? id, "setup": r["setup"] ?? ""]); continue }
            switch type {
            case "quota", "credits":
                var q = r
                q["windows"] = (r["windows"] as? [[String: Any]] ?? []).map { Self.pace($0, now: now) }
                if var c = r["credits"] as? [String: Any] { c["resetsAt"] = Self.epochMS(c["resetsAt"]) ?? NSNull(); q["credits"] = c }
                quotas.append(q)
            case "sessions":
                let list = r["sessions"] as? [[String: Any]] ?? []
                if r["enrich"] as? Bool == true { enrich += list } else { baseSessions += list }
            case "github":
                github = r
            default: break
            }
        }
        quotas.sort { Self.order($0) < Self.order($1) }
        return ["at": now * 1000, "quotas": quotas, "sessions": Self.merge(baseSessions, enrich), "github": github ?? NSNull(),
                "setup": setup, "sources": sources, "loading": results.isEmpty]
    }

    private static func order(_ q: [String: Any]) -> String {
        let rank = ["claude": "0", "codex": "1"][q["id"] as? String ?? ""] ?? (q["type"] as? String == "quota" ? "2" : "3")
        return rank + (q["name"] as? String ?? "")
    }

    /// ISO 8601 string, epoch seconds or epoch milliseconds → epoch ms.
    static func epochMS(_ v: Any?) -> Double? {
        if let n = v as? Double { return n > 1e11 ? n : n * 1000 }
        if let n = v as? Int { return Double(n) > 1e11 ? Double(n) : Double(n) * 1000 }
        guard let s = v as? String, !s.isEmpty else { return nil }
        if let n = Double(s) { return epochMS(n) }
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: s) { return d.timeIntervalSince1970 * 1000 }
        f.formatOptions = [.withInternetDateTime]
        if let d = f.date(from: s) { return d.timeIntervalSince1970 * 1000 }
        // Python's isoformat() gives microseconds (6 digits), which ISO8601DateFormatter rejects.
        let trimmed = s.replacingOccurrences(of: #"(\.\d{3})\d+"#, with: "$1", options: .regularExpression)
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.date(from: trimmed).map { $0.timeIntervalSince1970 * 1000 }
    }

    /// "At this pace": the use rate since the window started, carried forward. fullIn (seconds) is
    /// set only when the limit would be hit before the window resets.
    static func pace(_ w: [String: Any], now: Double) -> [String: Any] {
        var out = w
        let used = (w["used"] as? Double) ?? Double(w["used"] as? Int ?? 0)
        out["used"] = used
        let reset = epochMS(w["resetsAt"]).map { $0 / 1000 }
        out["resetsAt"] = reset.map { $0 * 1000 } ?? NSNull()
        guard let reset = reset, let length = (w["windowSeconds"] as? Double) ?? (w["windowSeconds"] as? Int).map(Double.init), length > 0 else { return out }
        let elapsed = now - (reset - length)
        guard used >= 1, used < 100, elapsed > 300 else { if used >= 100 { out["full"] = true }; return out }
        let toFull = (100 - used) / (used / elapsed)
        if now + toFull < reset { out["fullIn"] = toFull }
        return out
    }

    /// Joins sessions that a manager like Herdr also lists (same process id): its space, tab name and
    /// status win; the agent's own details (model, context, last prompt) stay.
    static func merge(_ base: [[String: Any]], _ extra: [[String: Any]]) -> [[String: Any]] {
        func pid(_ s: [String: Any]) -> Int? { (s["pid"] as? Int) ?? (s["pid"] as? Double).map(Int.init) }
        var byPid: [Int: [String: Any]] = [:]
        for e in extra { if let p = pid(e) { byPid[p] = e } }
        var used = Set<Int>(), out: [[String: Any]] = []
        for var s in base {
            s["task"] = s["title"]
            s["name"] = s["app"] ?? "Agent"
            if let p = pid(s), let e = byPid[p] {
                used.insert(p)
                s["group"] = e["group"]; s["name"] = e["title"]; s["sub"] = e["sub"] ?? false
                if let st = e["status"] as? String, st != "running" { s["status"] = st }
            }
            out.append(s)
        }
        // Managed agents this Mac doesn't otherwise see (another machine, or a tool with no plugin).
        let seen = Set(out.compactMap { pid($0) })
        for e in extra where pid(e).map({ !used.contains($0) && !seen.contains($0) }) ?? true {
            var s = e; s["name"] = e["title"]; s["task"] = NSNull(); out.append(s)
        }
        let rank = ["waiting": 0, "working": 1, "running": 2, "done": 3, "idle": 4]
        return out.sorted {
            let g0 = $0["group"] as? String ?? "", g1 = $1["group"] as? String ?? ""
            if g0 != g1 { return g0.localizedCaseInsensitiveCompare(g1) == .orderedAscending }
            let r0 = rank[$0["status"] as? String ?? ""] ?? 5, r1 = rank[$1["status"] as? String ?? ""] ?? 5
            if r0 != r1 { return r0 < r1 }
            return ($0["name"] as? String ?? "") < ($1["name"] as? String ?? "")
        }
    }
}
