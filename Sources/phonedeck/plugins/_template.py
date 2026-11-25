#!/usr/bin/env python3
"""Template: copy to ~/.phonedeck/plugins/<tool>.py, drop the leading underscore, fill in fetch().

Prints one JSON object. See README.md in this folder for every field.
"""
import json, os, subprocess, urllib.request

OUT = {"type": "quota", "id": "mytool", "name": "My Tool", "color": "#4285F4"}   # or "type": "credits"


def key():
    """Your API key from the macOS Keychain (service "mytool"), else an environment variable."""
    try:
        k = subprocess.run(["security", "find-generic-password", "-s", OUT["id"], "-w"],
                           capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        k = ""
    return k or os.environ.get("MYTOOL_API_KEY", "")


def fetch(k):
    """Ask the tool for usage. Return limit windows (quota) or a balance (credits)."""
    req = urllib.request.Request("https://api.example.com/v1/usage", headers={"Authorization": "Bearer " + k})
    d = json.load(urllib.request.urlopen(req, timeout=15))
    return {"windows": [{"label": "Day", "used": d["percent_used"], "resetsAt": d["resets_at"], "windowSeconds": 86400}]}
    # Credits instead:  return {"credits": {"left": d["balance"], "total": d["limit"], "unit": "$"}}


def main():
    k = key()
    if not k:
        return {**OUT, "available": False, "setup": 'security add-generic-password -s mytool -a "$USER" -w <your key>'}
    try:
        return {**OUT, "available": True, **fetch(k)}
    except Exception as e:
        return {**OUT, "available": True, "error": OUT["name"] + ": " + str(e)[:120]}


print(json.dumps(main()))
