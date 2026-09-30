# WP Notify Bot

[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot_API-26A5E4.svg)](https://core.telegram.org/bots/api)
[![WordPress](https://img.shields.io/badge/WordPress.org-API-21759B.svg)](https://api.wordpress.org/core/version-check/1.7/)
[![Wordfence](https://img.shields.io/badge/Wordfence-Intelligence_v3-1E3A8A.svg)](https://www.wordfence.com/api/intelligence/v3/vulnerabilities/production)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docs.docker.com/compose/)
[![Version](https://img.shields.io/badge/Version-1.0.6-green.svg)](#changelog)

Local Docker Telegram bot that notifies subscribers about official WordPress core releases and about serious WordPress core and plugin vulnerabilities. Core releases come from the WordPress.org version-check API, with a short Russian summary of the official release announcement. Vulnerabilities come from the Wordfence Intelligence v3 production feed (CVSS 7.0 and above). Both summaries use OpenRouter (`openai/gpt-6-luna`). The bot does not scan a site you host. The first successful feed read marks the current archive as seen and sends nothing.

## Requirements

- Docker with Compose
- GNU Make
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Get the project from Git

Clone the repository:

```bash
git clone https://github.com/MrBrims/wp-notify-bot.git
cd wp-notify-bot
cp .env.example .env
```

`.env` is gitignored. Put `TELEGRAM_BOT_TOKEN` in `.env` before the first `make up`. SQLite lives in `data/` (also gitignored except `.gitkeep`).

To update an existing checkout:

```bash
git pull
```

`git pull` does not rebuild images. After changes to `Dockerfile` or `requirements.txt`, run `make rebuild`.

## Quick start

```bash
cp .env.example .env          # 1. copy env if you have not already
# edit .env: TELEGRAM_BOT_TOKEN=...
make up                       # 2. build and start in the background
```

Open the bot in Telegram and send `/start` to subscribe. Optional: set `TELEGRAM_ALLOWED_USER_IDS` to a comma-separated list of Telegram user ids so only those accounts can use the bot.

## Bot commands

| Command | Action |
| --- | --- |
| `/start` | Subscribe the current chat |
| `/stop` | Unsubscribe the current chat |
| `/status` | Last known core version and last check time |
| `/check` | Run an extra poll immediately |
| `/simulate` | Send this chat a preview of the current core release and one serious vulnerability |

Scheduled polling uses `POLL_INTERVAL_SECONDS` (default 3600). The bot uses long polling; no public webhook URL is required.

## Commands

```bash
make                 # same as make help
make help            # list targets
make build           # build the image
make up              # start in the background
make start           # alias for up
make rebuild         # build and start
make down            # stop and remove the container
make stop            # alias for down
make restart         # restart the running container
make logs            # follow logs
make ps              # container status
make status          # alias for ps
make test            # pytest inside the image
```

Copy `.env` from `.env.example` before `make up`. Restart after changing env values (`make down` then `make up`, or `make restart` if only the running process should reload after a rebuild).

## Configuration

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather (required) |
| `TELEGRAM_ALLOWED_USER_IDS` | Optional comma-separated Telegram user ids; empty means anyone who can message the bot may subscribe |
| `POLL_INTERVAL_SECONDS` | Interval between WordPress.org checks (minimum 60, default 3600) |
| `DATABASE_PATH` | SQLite path in the container (default `/app/data/bot.db`) |
| `WORDPRESS_API_URL` | Core version-check endpoint |
| `OPENROUTER_API_KEY` | OpenRouter key used to summarize vulnerability alerts and WordPress core release announcements. Empty: both alerts still go out with their facts and links, without the two-sentence summary |
| `OPENROUTER_MODEL` | OpenRouter model (default `openai/gpt-6-luna`) |
| `WORDFENCE_API_KEY` | Free Wordfence Intelligence key from the account Integrations page. Empty: vulnerability polling stays off and core releases continue |
| `WORDFENCE_API_URL` | Production feed URL (default `https://www.wordfence.com/api/intelligence/v3/vulnerabilities/production`) |
| `VULN_MIN_CVSS` | Minimum CVSS score for core and plugin alerts (default `7.0`). Records rated High or Critical with no numeric score are included. Themes and informational records are skipped. There is no daily cap |
| `VULN_FEED_CACHE_SECONDS` | How long the downloaded feed file in `data/` is reused (default `21600`) |

## Stack

- Python 3.12
- python-telegram-bot (long polling and JobQueue)
- httpx
- aiosqlite
- Wordfence Intelligence API
- OpenRouter
- Docker Compose
- GNU Make

## Project Structure

```text
wp-notify-bot/
├── src/wp_notify_bot/
│   ├── __main__.py                 # process entry
│   ├── config.py                   # env settings
│   ├── models.py                   # NormalizedItem
│   ├── bot/handlers.py             # /start /stop /status /check /simulate
│   ├── pipeline/run.py             # fetch → seen → summarize → fan-out
│   ├── pipeline/simulate.py        # preview of a core release and a vulnerability for /simulate
│   ├── sources/                    # WordPress core, release announcements, Wordfence feed
│   ├── storage/db.py               # subscribers and seen_items
│   ├── summarizer/                 # OpenRouter summaries for releases and vulnerabilities
│   └── notify/telegram.py          # Telegram send + per-chat errors
├── tests/                          # API fixture and SQLite tests
├── data/                           # SQLite volume on the host (gitignored)
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

Host `./data` is mounted at `/app/data` in the container.

## Changelog

### 1.0.6

- **NEW**: `/simulate` sends this chat a preview of the current core release and one serious vulnerability, built from the live version-check API, the Wordfence feed, and the same OpenRouter summaries as real alerts. Subscribers and SQLite are unchanged. The command uses the same access list as the other commands; `TELEGRAM_ADMIN_USER_IDS` is no longer read

### 1.0.5

- **NEW**: OpenRouter (`openai/gpt-6-luna`) adds a two-sentence Russian summary of the official WordPress.org News announcement to core release alerts; PHP, MySQL, and download links stay in the template. If the key, announcement, or model is missing, the release alert still goes out without the summary

### 1.0.4

- **NEW**: Wordfence Intelligence v3 production feed notifies subscribers about WordPress core and plugin vulnerabilities with CVSS 7.0 or higher; the first read marks the current archive as seen and sends nothing
- **NEW**: OpenRouter (`openai/gpt-6-luna`) writes a two-sentence Russian summary; CVSS, CVE, affected versions, the fixed version, and the link stay in the message template
- **NEW**: `/status` shows when the vulnerability feed was last read

### 1.0.3

- **NEW**: Admin-only `/simulate` sends a fake WordPress core release to the admin chat; subscribers and SQLite are unchanged
- **FIX**: `/simulate` follows `TELEGRAM_ALLOWED_USER_IDS` the same way as the other commands

### 1.0.2

- **FIX**: `/status` stores the newest core release version, not the last item in the poll list

### 1.0.1

- **NEW**: Telegram command menu (`/start`, `/stop`, `/status`, `/check`) registered on bot startup

### 1.0.0

- **NEW**: Docker Telegram bot with `/start` / `/stop` subscriptions in SQLite
- **NEW**: WordPress.org core version-check polling and release notifications
- **NEW**: `Makefile` targets; bare `make` equals `make help`
- **TECHNICAL**: Source, summarizer, and notifier interfaces for later vulnerability feeds and OpenRouter
