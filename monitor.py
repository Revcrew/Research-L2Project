#!/usr/bin/env python3
"""L2 Deathwatch — hourly RSS sweep for L2 shutdown announcements.

Reads: Google News RSS (several queries) + crypto media RSS.
Prefilters by closure keywords + L2 context, dedupes by fingerprint,
appends to events.jsonl, writes new candidates to candidates.json,
updates state/health.json per source.

Classification per TZ 3.2 (CRITICAL_CONFIRMED / WARNING / MEDIA / INFO)
is done by the calling agent, not here. This script only collects.
No trading. No writes outside this directory.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(BASE, "state")
os.makedirs(STATE_DIR, exist_ok=True)

SEEN_PATH = os.path.join(STATE_DIR, "seen.json")
HEALTH_PATH = os.path.join(STATE_DIR, "health.json")
EVENTS_PATH = os.path.join(BASE, "events.jsonl")
CANDIDATES_PATH = os.path.join(BASE, "candidates.json")
WATCHLIST_PATH = os.path.join(BASE, "watchlist.json")

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) L2Deathwatch/1.0 research-bot"}

CLOSURE_KW = [
    "shut down", "shutting down", "sunset", "sunsetting", "cease operations",
    "discontinu", "wind down", "winding down", "network closure",
    "close the network", "closes its network", "deprecat", "pull the plug",
    "end of life", "halt operations", "ceasing operations",
]
PLAN_KW = [
    "proposal", "propose", "proposing", "considering", "plan to", "plans to",
    "vote on", "governance", "discussion", "deliberat", "weighing",
]
L2_CTX = [
    "layer 2", "layer-2", "l2 network", "rollup", "zk-rollup", "zk rollup",
    "optimistic rollup", "ethereum scaling",
]
EXCLUDE_KW = ["testnet", "devnet"]  # TZ 3.2: testnet closure != mainnet closure

NEWS_QUERIES = [
    "Ethereum layer 2 shutdown",
    "crypto L2 network sunset announcement",
    "rollup \"cease operations\" OR \"shutting down\"",
    "blockchain network discontinuation announcement",
]
MEDIA_RSS = [
    ("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("cointelegraph", "https://cointelegraph.com/rss"),
    ("decrypt", "https://decrypt.co/feed"),
]


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_rss(raw):
    items = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return items
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        desc = (it.findtext("description") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        # Google News wraps real URL oddly; take as-is
        if title and link:
            items.append({"title": title, "url": link, "summary": desc, "published": pub})
    return items


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def fingerprint(title, url):
    dom = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    return hashlib.sha1((norm(title) + "|" + dom).encode()).hexdigest()[:16]


def load_watchlist_names():
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            wl = json.load(f)
        return [n["name"].lower() for n in wl.get("networks", [])]
    except Exception:
        return []


def matches(item, wl_names):
    text = norm(item["title"] + " " + item["summary"])
    if any(k in text for k in EXCLUDE_KW):
        return None
    closure = [k for k in CLOSURE_KW if k in text]
    if not closure:
        return None
    ctx = [k for k in L2_CTX if k in text]
    named = [n for n in wl_names if n and n in text]
    if not ctx and not named:
        return None
    plan = [k for k in PLAN_KW if k in text]
    return {"closure_kw": closure, "plan_kw": plan, "ctx": ctx, "named": named}


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    wl_names = load_watchlist_names()
    seen = load_json(SEEN_PATH, {})
    health = load_json(HEALTH_PATH, {})

    # prune seen older than 60 days
    cutoff = time.time() - 60 * 86400
    seen = {k: v for k, v in seen.items() if v.get("ts", 0) > cutoff}

    sources = []
    for q in NEWS_QUERIES:
        url = ("https://news.google.com/rss/search?q=" +
               urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en")
        sources.append(("gnews:" + q[:32], url))
    sources += MEDIA_RSS

    matched, new_candidates, errors = [], [], []
    for name, url in sources:
        try:
            raw = fetch(url)
            items = parse_rss(raw)
            health[name] = {"last_ok": now, "items": len(items), "error": None}
        except Exception as e:
            health[name] = {"last_ok": health.get(name, {}).get("last_ok"),
                            "items": 0, "error": type(e).__name__ + ": " + str(e)[:120]}
            errors.append(name)
            continue
        for it in items:
            m = matches(it, wl_names)
            if not m:
                continue
            fp = fingerprint(it["title"], it["url"])
            rec = {
                "fp": fp, "detected_utc": now, "source": name,
                "title": it["title"], "url": it["url"],
                "published": it["published"], "match": m,
            }
            matched.append(rec)
            with open(EVENTS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if fp not in seen:
                new_candidates.append(rec)
                seen[fp] = {"ts": time.time(), "title": it["title"][:120]}

    save_json(SEEN_PATH, seen)
    save_json(HEALTH_PATH, health)
    save_json(CANDIDATES_PATH, {"generated_utc": now, "candidates": new_candidates})

    print(f"sources={len(sources)} errors={len(errors)} "
          f"{','.join(errors) if errors else 'ok'}")
    print(f"matched={len(matched)} new_candidates={len(new_candidates)}")
    for c in new_candidates:
        print(f"  CANDIDATE [{c['fp']}] {c['title'][:110]}")
        print(f"    {c['url'][:160]}")


if __name__ == "__main__":
    main()
