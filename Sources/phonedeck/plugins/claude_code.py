#!/usr/bin/env python3
"""Running Claude Code sessions on this Mac: folder, working or idle, model, context size, last prompt.

Claude Code keeps one ~/.claude/sessions/<pid>.json per running session and a transcript per
conversation in ~/.claude/projects/. Read-only; nothing leaves the Mac except to your phone.
"""
import glob, json, os, re

OUT = {"type": "sessions", "id": "claude-code", "name": "Claude Code", "color": "#D97757"}
HOME = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def alive(pid):
    try: os.kill(int(pid), 0); return True
    except (OSError, ValueError, TypeError): return False


def short_model(m):
    if not m or m.startswith("<"): return None
    parts = m.replace("claude-", "").split("-")
    words = [p for p in parts if not p.isdigit() or len(p) < 3]
    name = words[0].capitalize() if words else m
    nums = [p for p in words[1:] if p.isdigit()]
    return name + (" " + ".".join(nums) if nums else "")


def prompt_text(m):
    """The human prompt in a transcript line, or None (tool results, meta lines, commands)."""
    if m.get("type") != "user" or m.get("isMeta") or m.get("isSidechain") or m.get("isCompactSummary"): return None
    c = (m.get("message") or {}).get("content")
    text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in (c or []) if isinstance(x, dict) and x.get("type") == "text")
    # Messages relayed by tools arrive wrapped in tags (<hc from=...>, <pasted_content ...>): keep the words.
    text = re.sub(r"<(system-reminder|task-notification|artifact-content-[a-z-]+|command-[a-z-]+|local-command-[a-z-]+)>.*?</\1>", " ", text, flags=re.S)
    text = " ".join(re.sub(r"</?[a-zA-Z][\w-]*[^>]*>", " ", text).split())
    if not text or text.startswith(("[", "Caveat:", "This session is being continued")): return None
    return text[:90]


def transcript_info(sid):
    files = glob.glob(os.path.join(HOME, "projects", "*", sid + ".jsonl"))
    info = {"tokens": None, "model": None, "title": None}
    if not files: return info
    with open(files[0], "rb") as f:
        f.seek(0, 2); end = f.tell(); pos = end; carry = b""; scanned = 0
        # Read backwards in 1 MB chunks: usage and model sit near the end, the last prompt can be
        # further back behind long tool output. Stop after 12 MB.
        while pos > 0 and scanned < 12 * 1024 * 1024:
            step = min(1024 * 1024, pos); pos -= step; scanned += step
            f.seek(pos); chunk = f.read(step) + carry
            lines = chunk.split(b"\n")
            carry = lines[0] if pos > 0 else b""
            for raw in reversed(lines[1:] if pos > 0 else lines):
                line = raw.decode("utf-8", "ignore")
                if info["tokens"] is None and '"compact_boundary"' in line: info["tokens"] = 0
                if '"type":"assistant"' not in line and '"type":"user"' not in line: continue
                if info["tokens"] is not None and info["model"] and '"type":"assistant"' in line: continue
                try: m = json.loads(line)
                except ValueError: continue
                msg = m.get("message") or {}
                if m.get("type") == "assistant" and not m.get("isSidechain"):
                    if msg.get("usage") and info["tokens"] is None:
                        u = msg["usage"]
                        info["tokens"] = (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
                    if not info["model"]: info["model"] = short_model(msg.get("model"))
                elif not info["title"]:
                    info["title"] = prompt_text(m)
                if info["tokens"] is not None and info["model"] and info["title"]: return info
    return info


def main():
    files = glob.glob(os.path.join(HOME, "sessions", "*.json"))
    if not os.path.isdir(os.path.join(HOME, "sessions")):
        return {**OUT, "available": False, "setup": "Install Claude Code."}
    sessions = []
    for path in files:
        try: s = json.load(open(path))
        except Exception: continue
        if not alive(s.get("pid")) or not s.get("sessionId"): continue
        t = transcript_info(s["sessionId"])
        st = s.get("status") or "idle"
        sessions.append({
            "id": s["sessionId"], "pid": s.get("pid"), "cwd": s.get("cwd"),
            "group": os.path.basename(s.get("cwd") or "") or "~",
            "title": t["title"] or s.get("name") or "New session",
            "status": {"busy": "working", "idle": "idle"}.get(st, st),
            "model": t["model"], "tokens": t["tokens"],
            "app": "Claude Code" + (" (background)" if s.get("kind") == "bg" else ""),
            "startedAt": s.get("startedAt"), "updatedAt": s.get("updatedAt") or s.get("statusUpdatedAt"),
        })
    sessions.sort(key=lambda x: -(x.get("updatedAt") or 0))
    return {**OUT, "available": True, "sessions": sessions}


print(json.dumps(main()))
