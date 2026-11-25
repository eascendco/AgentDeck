#!/usr/bin/env python3
"""OpenRouter credit balance. Key: macOS Keychain item "openrouter" or OPENROUTER_API_KEY."""
import json, os, subprocess, urllib.request

OUT = {"type": "credits", "id": "openrouter", "name": "OpenRouter", "color": "#6467F2"}


def key():
    try:
        k = subprocess.run(["security", "find-generic-password", "-s", "openrouter", "-w"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception: k = ""
    return k or os.environ.get("OPENROUTER_API_KEY", "")


def main():
    k = key()
    if not k:
        return {**OUT, "available": False, "setup": 'security add-generic-password -s openrouter -a "$USER" -w <your key>'}
    req = urllib.request.Request("https://openrouter.ai/api/v1/credits", headers={"Authorization": "Bearer " + k})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=15)).get("data") or {}
    except Exception as e:
        return {**OUT, "available": True, "error": "OpenRouter: " + str(e)[:120]}
    total, used = float(d.get("total_credits") or 0), float(d.get("total_usage") or 0)
    return {**OUT, "available": True, "credits": {"left": round(total - used, 2), "total": round(total, 2), "unit": "$"}}


print(json.dumps(main()))
