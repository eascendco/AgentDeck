#!/usr/bin/env python3
"""Herdr (herdr.dev) agent tabs: space, tab name and status for every agent it runs.

Only does something if `hc` (herdr-core) is installed. The deck merges these with the Claude
Code sessions by process id, so a Herdr tab shows its space and tab name instead of its folder.
"""
import json, shutil, subprocess

OUT = {"type": "sessions", "id": "herdr", "name": "Herdr", "color": "#22A99A", "enrich": True}
STATUS = {"working": "working", "blocked": "waiting", "done": "done", "idle": "idle"}


def hc(*args):
    r = subprocess.run(["hc", *args], capture_output=True, text=True, timeout=10)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def main():
    if not shutil.which("hc"):
        return {**OUT, "available": False, "setup": "Optional: install Herdr (herdr.dev) to group agents by space."}
    ls = hc("ls", "--json") or {}
    sessions = []
    for t in ls.get("terminals") or []:
        if t.get("state") != "live" or not t.get("agent"): continue
        st = t.get("status"); st = st if isinstance(st, str) else (st or {}).get("state")
        where = t.get("where") or ""
        space, _, tab = where.partition(" / ")
        g = hc("get", "--json", t["address"]) or {}
        fg = g.get("foreground") or {}
        sessions.append({"id": "herdr-" + t["address"], "pid": fg.get("pid"), "cwd": t.get("cwd"),
                         "group": space or "Herdr", "title": (t.get("name") or tab or t["address"]),
                         "sub": bool(t.get("parent")), "status": STATUS.get(st, st or "idle"),
                         "app": {"claude-code": "Claude Code", "opencode": "OpenCode", "codex": "Codex"}.get(t.get("agent"), t.get("agent")),
                         "remote": "/" in t["address"]})
    return {**OUT, "available": True, "sessions": sessions}


print(json.dumps(main()))
