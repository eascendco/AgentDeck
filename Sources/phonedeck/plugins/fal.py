#!/usr/bin/env python3
"""fal.ai credit balance. Key: Keychain item "fal" or FAL_KEY (an admin key can read billing)."""
import json, os, subprocess, urllib.request

OUT = {"type": "credits", "id": "fal", "name": "fal", "color": "#E4E4E7"}


def key():
    try:
        k = subprocess.run(["security", "find-generic-password", "-s", "fal", "-w"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception: k = ""
    return k or os.environ.get("FAL_KEY", "")


def main():
    k = key()
    if not k:
        return {**OUT, "available": False, "setup": 'security add-generic-password -s fal -a "$USER" -w <your admin key>'}
    req = urllib.request.Request("https://api.fal.ai/v1/account/billing?expand=credits", headers={"Authorization": "Key " + k})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=15))
    except Exception as e:
        return {**OUT, "available": True, "error": "fal: " + str(e)[:120]}
    left = ((d.get("credits") or {}).get("current_balance"))
    if left is None:
        return {**OUT, "available": True, "error": "No balance in fal's reply."}
    return {**OUT, "available": True, "credits": {"left": round(float(left), 2), "unit": "$"}}


print(json.dumps(main()))
