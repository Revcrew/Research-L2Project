#!/usr/bin/env python3
"""Send a Telegram alert via the plain Telegram Bot API.

Public version: the bot token comes ONLY from the TELEGRAM_BOT_TOKEN
environment variable, chat IDs ONLY from config.json (copy
config.example.json to config.json and fill in your own IDs).
No token or chat ID is committed to this repo.

Usage: python3 tg_send.py "message text"
Exit 0 on ok, 1 on failure.
"""
import json
import os
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('usage: tg_send.py "message"', file=sys.stderr)
        sys.exit(1)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN is not set", file=sys.stderr)
        sys.exit(1)
    try:
        with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"config.json unreadable: {e}", file=sys.stderr)
        sys.exit(1)
    chat_ids = [str(c) for c in (cfg.get("chat_ids") or []) if c]
    if not chat_ids:
        print("no chat_ids in config.json — message not sent", file=sys.stderr)
        sys.exit(1)
    ok = True
    for chat_id in chat_ids:
        body = json.dumps(
            {"chat_id": chat_id, "text": sys.argv[1], "parse_mode": "HTML"}
        ).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"sent to {chat_id}: {r.status}")
        except Exception as e:
            print(f"send to {chat_id} failed: {e}", file=sys.stderr)
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
