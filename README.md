# WP Notify Bot

[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot_API-26A5E4.svg)](https://core.telegram.org/bots/api)
[![WordPress](https://img.shields.io/badge/WordPress.org-API-21759B.svg)](https://api.wordpress.org/core/version-check/1.7/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docs.docker.com/compose/)
[![Version](https://img.shields.io/badge/Version-1.0.2-green.svg)](#changelog)

Local Docker Telegram bot that watches official WordPress core releases (not a site you host) and notifies subscribers. Updates come from the WordPress.org version-check API. Plugin-vulnerability feeds and OpenRouter summaries are reserved as interfaces; they are not wired in this release.

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
| `OPENROUTER_API_KEY` | Reserved; not used yet |
| `OPENROUTER_MODEL` | Reserved; not used yet |

## Stack

- Python 3.12
- python-telegram-bot (long polling and JobQueue)
- httpx
- aiosqlite
- Docker Compose
- GNU Make

## Project Structure

```text
wp-notify-bot/
├── src/wp_notify_bot/
│   ├── __main__.py                 # process entry
│   ├── config.py                   # env settings
│   ├── models.py                   # NormalizedItem
│   ├── bot/handlers.py             # /start /stop /status /check
│   ├── pipeline/run.py             # fetch → seen → summarize → fan-out
│   ├── sources/                    # WordPress core + registry for future feeds
│   ├── storage/db.py               # subscribers and seen_items
│   ├── summarizer/                 # passthrough now; OpenRouter stub later
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

### 1.0.2

- **FIX**: `/status` stores the newest core release version, not the last item in the poll list

### 1.0.1

- **NEW**: Telegram command menu (`/start`, `/stop`, `/status`, `/check`) registered on bot startup

### 1.0.0

- **NEW**: Docker Telegram bot with `/start` / `/stop` subscriptions in SQLite
- **NEW**: WordPress.org core version-check polling and release notifications
- **NEW**: `Makefile` targets; bare `make` equals `make help`
- **TECHNICAL**: Source, summarizer, and notifier interfaces for later vulnerability feeds and OpenRouter
