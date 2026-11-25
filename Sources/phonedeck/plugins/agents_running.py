#!/usr/bin/env python3
"""Codex, OpenCode, Gemini CLI, Grok CLI, Cursor agent and Antigravity sessions running on this Mac.

These tools don't publish a live session list, so this finds their running processes and the
folder each runs in. Status is "running" (they don't say whether they're working or waiting).
Add a tool by adding a line to TOOLS: program name -> label.
"""
import json, os, subprocess

OUT = {"type": "sessions", "id": "agents", "name": "Other agents", "color": "#8E8E93"}
TOOLS = {"codex": "Codex", "opencode": "OpenCode", "gemini": "Gemini CLI", "grok": "Grok CLI",
         "cursor-agent": "Cursor agent", "antigravity": "Antigravity", "aider": "Aider", "goose": "Goose", "amp": "Amp"}


def cwd_of(pid):
    try:
        out = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True, timeout=5).stdout
        for l in out.splitlines():
            if l.startswith("n"): return l[1:]
    except Exception: pass
    return None


def main():
    ps = subprocess.run(["ps", "-axo", "pid=,ppid=,lstart=,command="], capture_output=True, text=True).stdout
    rows, pids = [], set()
    for line in ps.splitlines():
        parts = line.split(None, 7)
        if len(parts) < 8: continue
        pid, ppid, cmd = int(parts[0]), int(parts[1]), parts[7]
        argv0 = cmd.split()[0]
        prog = os.path.basename(argv0)
        # node-based CLIs show up as `node /path/to/bin/codex ...`
        if prog in ("node", "bun") and len(cmd.split()) > 1: prog = os.path.basename(cmd.split()[1])
        if prog in TOOLS and " app-server" not in cmd and " mcp" not in cmd:
            rows.append((pid, ppid, prog, " ".join(parts[2:7]))); pids.add(pid)
    sessions = []
    for pid, ppid, prog, started in rows:
        if ppid in pids: continue          # a helper process of a session already listed
        cwd = cwd_of(pid)
        sessions.append({"id": "%s-%d" % (prog, pid), "pid": pid, "cwd": cwd, "app": TOOLS[prog],
                         "group": os.path.basename(cwd or "") or "~", "title": TOOLS[prog] + " in " + (os.path.basename(cwd or "") or "~"),
                         "status": "running", "started": started})
    return {**OUT, "available": True, "sessions": sessions}


print(json.dumps(main()))
