#!/usr/bin/env python3
"""Claude plan limits (5-hour session and weekly), from your own `claude` CLI.

Starts `claude` briefly and sends it the `get_usage` control request; the CLI signs in by itself.
No prompt is sent and no turn starts, so it costs nothing. Reads no credential files.
Approach credit: jmalicki/herdr-mod-ai-usage (MIT), whose collector asks the CLI the same way.
"""
import json, shutil, subprocess, sys, time, select

OUT = {"type": "quota", "id": "claude", "name": "Claude", "color": "#D97757"}
REQ = {"type": "control_request", "request_id": "phonedeck-usage",
       "request": {"subtype": "get_usage", "skip_behaviors": True}}


def ask(cli, extra):
    p = subprocess.Popen([cli, "-p", *extra, "--no-session-persistence", "--input-format", "stream-json",
                          "--output-format", "stream-json", "--verbose"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        p.stdin.write(json.dumps(REQ) + "\n"); p.stdin.flush()
        end = time.time() + 20
        while time.time() < end:
            r, _, _ = select.select([p.stdout], [], [], 0.5)
            if not r:
                if p.poll() is not None: return None
                continue
            line = p.stdout.readline()
            if not line: return None
            try: m = json.loads(line)
            except ValueError: continue
            if m.get("type") == "control_response": return m.get("response") or {}
        return None
    finally:
        p.kill()


def main():
    cli = shutil.which("claude")
    if not cli:
        return {**OUT, "available": False, "setup": "Install Claude Code and sign in with a Pro or Max plan."}
    res = ask(cli, ["--safe-mode"]) or ask(cli, [])
    if res is None:
        return {**OUT, "available": True, "error": "No reply from the claude CLI."}
    if res.get("subtype") != "success":
        return {**OUT, "available": True, "error": str(res.get("error") or "No usage in the reply.")}
    rl = (res.get("response") or {}).get("rate_limits") or {}
    windows = []
    for l in rl.get("limits") or []:
        if l.get("percent") is None: continue
        if l.get("kind") == "session": windows.append({"label": "5 h", "used": l["percent"], "resetsAt": l.get("resets_at"), "windowSeconds": 5 * 3600})
        elif l.get("kind") == "weekly_all": windows.append({"label": "Week", "used": l["percent"], "resetsAt": l.get("resets_at"), "windowSeconds": 7 * 86400})
    if not windows:
        for key, label, secs in (("five_hour", "5 h", 5 * 3600), ("seven_day", "Week", 7 * 86400)):
            w = rl.get(key) or {}
            if w.get("utilization") is not None:
                windows.append({"label": label, "used": w["utilization"], "resetsAt": w.get("resets_at"), "windowSeconds": secs})
    if not windows:
        return {**OUT, "available": True, "error": "No plan limits (API key sign-in has none)."}
    return {**OUT, "available": True, "windows": windows}


print(json.dumps(main()))
