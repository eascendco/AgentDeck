#!/usr/bin/env python3
"""Codex plan limits, from the rate-limit snapshot Codex writes into its own session logs.

Codex records `rate_limits` (primary = 5-hour window, secondary = weekly) with each turn in
~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl. This reads the newest one. No network, no key.
The numbers are as of your last Codex turn.
"""
import glob, json, os, time

OUT = {"type": "quota", "id": "codex", "name": "Codex", "color": "#10A37F"}
HOME = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")


def tail_lines(path, size=400000):
    with open(path, "rb") as f:
        f.seek(0, 2); n = f.tell(); f.seek(max(0, n - size))
        return f.read().decode("utf-8", "ignore").splitlines()


def window(w, label, default_secs, at):
    if not isinstance(w, dict) or w.get("used_percent") is None: return None
    secs = int(w.get("window_minutes") or 0) * 60 or default_secs
    reset = w.get("resets_at")
    if reset is None and w.get("resets_in_seconds") is not None: reset = at + float(w["resets_in_seconds"])
    if reset is not None and reset < time.time(): return {"label": label, "used": 0, "resetsAt": None, "windowSeconds": secs}
    return {"label": label, "used": w["used_percent"], "resetsAt": reset, "windowSeconds": secs}


def main():
    files = sorted(glob.glob(os.path.join(HOME, "sessions", "*", "*", "*", "rollout-*.jsonl")), key=os.path.getmtime, reverse=True)
    if not files:
        return {**OUT, "available": False, "setup": "Install Codex and run it once; limits appear after your first turn."}
    for path in files[:5]:
        at = os.path.getmtime(path)
        for line in reversed(tail_lines(path)):
            if '"rate_limits"' not in line: continue
            try: m = json.loads(line)
            except ValueError: continue
            p = m.get("payload") or m.get("msg") or {}
            rl = p.get("rate_limits") or (p.get("info") or {}).get("rate_limits")
            if not rl: continue
            ws = [w for w in (window(rl.get("primary"), "5 h", 5 * 3600, at), window(rl.get("secondary"), "Week", 7 * 86400, at)) if w]
            if ws: return {**OUT, "available": True, "windows": ws, "asOf": at}
    return {**OUT, "available": True, "error": "No limits in recent Codex sessions yet."}


print(json.dumps(main()))
