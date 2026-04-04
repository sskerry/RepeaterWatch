#!/usr/bin/env python3
"""setup_auth.py — Manage RepeaterWatch password
Usage:
    sudo -u meshcoremon /opt/RepeaterWatch/venv/bin/python3 setup_auth.py
    sudo -u meshcoremon /opt/RepeaterWatch/venv/bin/python3 setup_auth.py --clear
"""
import argparse, getpass, os, sys

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

def upsert(lines, key, value):
    found = False; out = []
    for l in lines:
        if l.startswith(f"{key}="):
            out.append(f"{key}={value}\n"); found = True
        else:
            out.append(l)
    if not found: out.append(f"{key}={value}\n")
    return out

def main():
    try: import bcrypt
    except ImportError:
        print("[ERROR] bcrypt not installed. Run: venv/bin/pip install bcrypt>=4.0"); sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Disable login")
    args = parser.parse_args()
    lines = open(ENV_PATH).readlines()
    kv = {l.split("=",1)[0].strip(): l.split("=",1)[1].strip() for l in lines if "=" in l and not l.startswith("#")}

    if args.clear:
        lines = upsert(upsert(lines,"MESHCORE_PASSWORD",""),"MESHCORE_PASSWORD_HASH","")
        open(ENV_PATH,"w").writelines(lines)
        print("[OK] Password cleared — login disabled"); return

    has_hash = bool(kv.get("MESHCORE_PASSWORD_HASH",""))
    has_plain = bool(kv.get("MESHCORE_PASSWORD",""))
    print(f"[INFO] Current: {'bcrypt hash' if has_hash else 'plaintext' if has_plain else 'no password'}")

    while True:
        pw = getpass.getpass("\nNew password (blank to cancel): ")
        if not pw: print("Cancelled."); return
        if len(pw) < 8: print("Min 8 characters."); continue
        if pw == getpass.getpass("Confirm: "): break
        print("No match — try again.")

    hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt(12)).decode()
    lines = upsert(upsert(lines,"MESHCORE_PASSWORD_HASH",hashed),"MESHCORE_PASSWORD","")
    open(ENV_PATH,"w").writelines(lines)
    print("[OK] Password set (bcrypt)")
    print("     Restart: sudo systemctl restart RepeaterWatch")

if __name__ == "__main__": main()
