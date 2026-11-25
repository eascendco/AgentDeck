#!/usr/bin/env python3
"""ElevenLabs credits this billing period. Key: Keychain item "elevenlabs" or ELEVENLABS_API_KEY."""
import json, os, subprocess, urllib.request

OUT = {"type": "credits", "id": "elevenlabs", "name": "ElevenLabs", "color": "#B0B0B0"}


def key():
    try:
        k = subprocess.run(["security", "find-generic-password", "-s", "elevenlabs", "-w"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception: k = ""
    return k or os.environ.get("ELEVENLABS_API_KEY", "")


def main():
    k = key()
    if not k:
        return {**OUT, "available": False, "setup": 'security add-generic-password -s elevenlabs -a "$USER" -w <your key>'}
    req = urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": k})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=15))
    except Exception as e:
        return {**OUT, "available": True, "error": "ElevenLabs: " + str(e)[:120]}
    used, limit = d.get("character_count"), d.get("character_limit")
    if used is None or not limit:
        return {**OUT, "available": True, "error": "No credits in ElevenLabs' reply."}
    return {**OUT, "available": True, "credits": {"left": limit - used, "total": limit, "unit": "credits",
                                                  "resetsAt": d.get("next_character_count_reset_unix")}}


print(json.dumps(main()))
