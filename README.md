# 🎬 Telegram Video Extractor Bot

A production-ready Telegram bot that extracts MP4 / video URLs from `.txt` files and downloads them directly to your chat. Designed to run as a **Render.com web service**.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 Smart URL parsing | Detects `.mp4`, `.m4v`, `.webm`, `.mkv`, CDN links, and more |
| ⬇️ Parallel downloads | Up to 3 concurrent downloads per request |
| 📊 Progress bars | Live download progress in chat |
| 🔢 Pick mode | Select specific videos from large lists |
| 📋 List mode | Get a clean numbered URL list |
| 🔄 Auto retry | 3 retries with exponential back-off |
| 📦 Large file handling | Files >50 MB: sends direct link instead |
| 🩺 Health endpoint | `/health` for Render uptime monitoring |
| 🪵 Rotating logs | 5 MB rotating log files |
| 🌐 Webhook mode | Production webhook on Render |
| 🔄 Polling mode | Automatic fallback for local dev |

---

## 🚀 Quick Start

### 1. Create a Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow prompts
3. Copy your **API token**

---

### 2. Deploy to Render

1. Fork / upload this project to a GitHub repo
2. Go to [render.com](https://render.com) → **New → Web Service**
3. Connect your GitHub repo
4. Set **Build Command**: `pip install -r requirements.txt`
5. Set **Start Command**: `python bot.py`
6. Add **Environment Variables**:

| Variable | Value |
|---|---|
| `BOT_TOKEN` | Your Telegram bot token |
| `WEBHOOK_URL` | Your Render service URL (e.g. `https://your-app.onrender.com`) |
| `PORT` | `10000` |
| `MAX_WORKERS` | `4` |

7. Click **Deploy**

---

### 3. Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set env vars
export BOT_TOKEN="your_token_here"
# Leave WEBHOOK_URL unset → bot uses polling mode automatically

# Run
python bot.py
```

---

## 📁 Project Structure

```
telegram-video-bot/
├── bot.py                   # Entry point – builds & runs the Application
├── requirements.txt
├── render.yaml              # Render deployment config
├── sample_urls.txt          # Example .txt file for testing
│
├── handlers/
│   ├── command_handler.py   # /start /help /status /cancel
│   ├── file_handler.py      # Handles .txt uploads, parses URLs
│   └── callback_handler.py  # Inline keyboard: dl_all, list, pick, paging
│
└── utils/
    ├── url_parser.py        # Regex URL extraction & video detection
    ├── downloader.py        # Async downloader with progress + retry
    ├── queue_manager.py     # Concurrency + per-user job tracking
    ├── file_utils.py        # File save / cleanup helpers
    ├── health_server.py     # /health HTTP server for Render
    └── logger.py            # Rotating file + console logger
```

---

## 🤖 Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message + quick-action buttons |
| `/help` | Full usage guide |
| `/status` | View active/queued download jobs |
| `/cancel` | Cancel all your active jobs |

### Uploading a file

Just **send any `.txt` file** to the bot. It will:
1. Parse all video URLs
2. Show a preview of found links
3. Offer actions: **Download All**, **List Only**, or **Pick Numbers**

---

## 📝 Supported `.txt` Format

```
# This is a comment (ignored)
# Blank lines are ignored

https://example.com/video.mp4
https://cdn.example.com/media/clip.mp4?token=abc
https://d2q79iu.cloudfront.net/stream/show.mp4
```

**Supported formats**: `.mp4` `.m4v` `.mov` `.avi` `.mkv` `.webm` `.flv` `.ts` `.m3u8`  
CDN domains (CloudFront, Akamai, Fastly, etc.) are auto-detected even without file extensions.

---

## ⚙️ Configuration

| Env Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *(required)* | Telegram bot token |
| `WEBHOOK_URL` | *(empty = polling)* | Your public HTTPS URL |
| `PORT` | `10000` | HTTP port for webhook + health check |
| `MAX_WORKERS` | `4` | Max concurrent download jobs globally |

---

## 🛠 Render Free Plan Notes

- **Spin-down**: Free services sleep after 15 min of inactivity. The first message after sleep has ~30 s delay.
- **Upgrade to Starter** ($7/mo) for always-on.
- The `/health` endpoint prevents Render from flagging the service as unresponsive.

---

## 📜 License

MIT
