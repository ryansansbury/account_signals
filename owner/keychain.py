"""The owner's machine only. Read one API key from the macOS Keychain and never print it.

config/models.json names the items to try in order, saved by owner/keys.sh. A failure reports the Keychain's own
reason, such as an item that isn't there or access that was denied, and never the key. The recorder imports this only for a real run, never for the stand-in or a test.
"""
import subprocess


def key_for(items, run=subprocess.run):
    items = [items] if isinstance(items, str) else list(items)
    reasons = []
    for item in items:
        done = run(["security", "find-generic-password", "-s", item, "-w"], capture_output=True, text=True)
        key = (done.stdout or "").strip()
        if done.returncode == 0 and len(key) >= 20:
            return key
        reason = (done.stderr or "").strip().splitlines()[-1:] or ["no key"]
        reasons.append(f"{item}: {reason[0][:120].rstrip('.')}")
    raise SystemExit("No API key found. Tried " + "; ".join(reasons) + ". Run bash owner/keys.sh check to see which "
                     "items exist, then bash owner/keys.sh anthropic (or openai) to save one.")
