# ✦ Maple Leaf — A Discord Bot for Genshin Impact & Honkai: Star Rail

[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.3%2B-5865F2?logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![Tests](https://img.shields.io/badge/tests-unittest-brightgreen)](tests/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Maple Leaf** is a Python Discord bot focused on **Genshin Impact** and **Honkai: Star Rail**.
It features a layered architecture, Pillow-rendered profile/character cards, and a **background
automation layer** (daily check-in, gift codes, Mimo tasks, web events) with **encrypted cookies**.

> 🇻🇳 Bản tiếng Việt: [`README.md`](README.md)

> ⚠️ **Language note:** the bot's user-facing interface (slash commands, embeds, messages) is in
> **Vietnamese**. The codebase and documentation are written with Vietnamese comments. This English
> README is provided for international users; the bot UI itself is not translated yet.

---

## ✨ Features

### 🎮 Profile & characters
- **`/profile`** — player profile card (Adventure Rank, World Level, Achievements / Trailblaze Level).
- **`/characters`** — browse the full character showcase with pagination.
- **`/build`** — character build guides (weapons, artifacts, stats, teams) with **autocomplete**.
- **`/search`** — quick lookup for characters, elements and paths.

### ⚙️ Background automation (`/auto`)
- **Daily HoYoLAB check-in** for every opted-in account.
- **Automatic gift code redemption** — scans multiple code sources and redeems for your accounts.
- **Mimo tasks** and **Accompany check-in**.
- **Web event notifications** for both games.
- **Log in once** — tokens are auto-renewed via `stoken` every 12 hours, no more cookie pasting.
- `/auto status`, `/auto toggle`, `/auto login`, `/auto session_add`, `/auto verify`, `/auto run`, `/auto history`.

### 🔐 Security
- HoYoLAB cookies are **encrypted with Fernet (symmetric)** before being stored.
- Raw cookies are never logged or shown in Discord.
- Users can opt in/out and **revoke their session** at any time.
- Read [`SECURITY.md`](SECURITY.md) before deploying publicly.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

## ☁️ Deploy 24/7 to Render (Recommended)

You can deploy the bot to [Render.com](https://render.com) for **24/7 free hosting** in just a few clicks:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

1. Click the **Deploy to Render** button above (or create a Blueprint from your GitHub repository on Render Dashboard).
2. Enter your **`DISCORD_TOKEN`**.
3. The bot comes with a built-in **Health Check Server** (`/healthz` on port `10000`), which Render detects and runs immediately.
4. 👉 See the step-by-step guide on how to keep the bot alive 24/7 with UptimeRobot: [`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md).

---

## 🚀 Quick start on PC

### Requirements
- **Python 3.12+** ([Download from python.org](https://www.python.org/downloads/))
- A Discord bot (create one at the [Discord Developer Portal](https://discord.com/developers/applications))
- **Both privileged intents enabled**: `SERVER MEMBERS` and `MESSAGE CONTENT`.

### Option 1 — 1-Click Automated (Easiest)

After downloading or cloning the repo:

- **On Windows**: Simply double-click **`run.bat`** in the root directory.
  *(It will automatically create the virtual environment `.venv`, install all dependencies, create `.env`, and prompt you to enter your token).*
- **On Linux / macOS**: Run:
  ```bash
  bash run.sh
  ```

### Option 2 — Manual command line

```bash
git clone https://github.com/Mod3r3d/Maple-Leaf.git
cd Maple-Leaf

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Open `.env` and set at least `DISCORD_TOKEN`:
```env
DISCORD_TOKEN=your_bot_token_here
```

Run the bot:
```bash
python -m app.main
```

---

## 🐳 Docker


```bash
cp .env.example .env      # then fill in DISCORD_TOKEN
docker compose up -d --build
docker compose logs -f
```

---

## 🎁 Gift codes not working?

This is the most common issue. In short: the redemption API requires a `cookie_token` (valid for
only ~2 hours), and for the bot to **auto-renew** it the cookie must contain a **`stoken`** — which
is **not** present in browser cookies.

👉 Full guide (Vietnamese): [`docs/HUONG_DAN_LAY_STOKEN.md`](docs/HUONG_DAN_LAY_STOKEN.md)

Quick path:

```bash
.venv/Scripts/python.exe scripts/get_full_cookie.py
```

The script auto-detects your Discord user ID when the database has only one user
(use `--discord-user-id <ID>` otherwise). Then run `/auto verify` in Discord to confirm.

---

## 🧪 Tests

```bash
python -m unittest discover tests -v
```

CI runs the test suite on Windows and Linux for every push/PR (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

---

## 📁 Project structure

```text
Maple-Leaf/
├── app/
│   ├── main.py              # Entrypoint
│   ├── config.py            # Settings (pydantic-settings)
│   ├── bot/                 # Discord client, error handler, lifecycle
│   ├── automation/          # Background automation layer
│   │   ├── manager.py       #   async APScheduler
│   │   ├── client.py        #   genshin.py adapter (redeem, check-in)
│   │   ├── notifications.py #   DM/channel notifications
│   │   ├── tasks/           #   Checkin, Giftcode, Mimo, Accompany, WebEvent
│   │   └── providers/       #   HoYoLAB API, gift code sources, Mimo
│   ├── commands/            # Slash command groups
│   ├── services/            # Business logic (incl. redeem_service.py)
│   ├── games/               # Game abstraction layer
│   │   ├── genshin/         #   provider, models, build data
│   │   └── hsr/             #   provider, models, JSON data
│   ├── db/                  # aiosqlite: database.py, models/, repositories/ (see app/db/README.md)
│   ├── integrations/        # Enka.Network client + TTL cache
│   ├── render/              # Pillow card rendering
│   ├── security/            # Fernet encryption
│   ├── ui/                  # Views, Modals, Buttons, Selects
│   └── utils/               # Localization, validators, rate limiting
├── deploy/postgres/         # PostgreSQL deployment (OPTIONAL, experimental)
├── data/                    # Runtime data (not committed)
├── docs/                    # Documentation (see docs/README.md)
├── scripts/                 # setup.sh/.bat, get_full_cookie.py
├── tests/                   # Unit tests (unittest)
├── .env.example
├── Dockerfile / docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🛠️ Troubleshooting

| Symptom | Cause & fix |
|---|---|
| Bot stays offline | `DISCORD_TOKEN` missing, or privileged intents not enabled |
| Slash commands not showing | Wait a few minutes for Discord to sync, or re-invite the bot |
| `/auto` says no account | Run `/account add` first |
| Gift code fails (`AUTH_REQUIRED`) | Cookie lacks `stoken` → see the [stoken guide](docs/HUONG_DAN_LAY_STOKEN.md) |
| Card images have broken fonts | Install a Vietnamese-capable system font (Docker image includes one) |

---

## 🤝 Contributing

Contributions are welcome! Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a PR.
See [`CHANGELOG.md`](CHANGELOG.md) for the change history.

---

## 🙏 Credits

- [genshin.py](https://github.com/seriaati/genshin.py) — HoYoLAB API client.
- [Enka.Network](https://enka.network/) — Genshin character data.
- [hoyo-codes.seria.moe](https://hoyo-codes.seria.moe/) — gift code source.
- [hoyo-buddy](https://github.com/seriaati/hoyo-buddy) — inspiration for the redemption flow and token handling.
- [Mar-7th/StarRailRes](https://github.com/Mar-7th/StarRailRes) — Star Rail assets.

---

## ⚠️ Disclaimer

This project is **not affiliated with, endorsed by, or sponsored by HoYoverse**. It is a community
tool that uses your own account cookies. Use it at your own risk and always comply with HoYoverse's
Terms of Service.

---

## 📄 License

Released under the **MIT License** — see the [`LICENSE`](LICENSE) file.
You are free to use, copy, modify and distribute it, as long as you keep the copyright notice.
