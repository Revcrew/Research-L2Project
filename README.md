# L2 Deathwatch

By **Alexander Khlystun** — a QA engineer with an AI focus from Lviv, Ukraine.
I test AI tools instead of trusting them, and I apply the same rule to crypto
news: a headline is not a decision, and a plan is not a shutdown.

## What it does

An hourly monitor for official announcements that a public L2 (rollup)
network is shutting down, built from public sources only:

- Google News RSS queries for L2 shutdowns, plus CoinDesk, Cointelegraph
  and Decrypt feeds.
- A watchlist of ~40 public L2 networks (`watchlist.json`: name, blog, X handle).
- Persistent dedupe: each announcement is alerted once, across restarts.
- Telegram alerts (see "Secrets" below). No alert without a news item —
  price-only alerts are OFF.

## Classification

| Class | Meaning |
|---|---|
| `CRITICAL_CONFIRMED` | Official decision to shut the network down |
| `MEDIA` | Reported, not officially confirmed |
| `WARNING` | A plan or proposal, not a decision |
| `INFO` | Background only, not alerted |

Rules that prevent false alarms:

- A plan is not a decision. The reference case is Scroll (08.09.2026):
  "not a formal proposal or vote" → WARNING, not CRITICAL.
- A testnet, bridge or single-market shutdown is not a network shutdown.
- The key separator for token impact is the **token's fate**, not the
  shutdown alone. Precedents: Blast (announced 02.10.2026, token died with
  the network), Lisk (L2 stops 31.10.2026, token lives), Nillion (sunset
  from 15.10.2026, token lives), Sophon and Kroma (token migrates).

## What it does NOT do

**No trading of any kind — real or paper — in this repo.** Monitoring and
alerts only.

## Secrets

Copy `config.example.json` to `config.json` and fill in your own Telegram
chat IDs. The bot token is read from the `TELEGRAM_BOT_TOKEN` environment
variable and is never committed. This public version of `tg_send.py` uses
the plain Telegram Bot API; it contains no private credentials and no
account tokens.

## Run

```bash
cp config.example.json config.json   # fill in your own chat IDs
export TELEGRAM_BOT_TOKEN="your-bot-token"
python3 monitor.py    # collects, dedupes, writes candidates.json
python3 tg_send.py "test message"
```

Run `monitor.py` hourly (cron or systemd). Classification of new candidates
in `candidates.json` against the rules above is a human/agent step before
any alert is sent for a new event.
