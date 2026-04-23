# 🎵 Music Bot V2

A professional, production-ready Discord music bot built in Python — refactored from the ground up with a clean modular architecture.

## ✨ Features

| Feature | Details |
|---------|---------|
| 🎵 YouTube Playback | URL or search keywords |
| 🎤 Spotify Support | Track, album, playlist → converted to YouTube |
| 📋 Smart Queue | Persistent across restarts, paginated display |
| 🔁 Loop Modes | Off / Track / Queue |
| 🎛 Audio Effects | 18 effects: Bass Boost, Nightcore, 8D, Reverb, Echo… |
| 🔊 Volume Control | 0–200% |
| 🎮 Interactive UI | Buttons & dropdowns |
| 📊 Statistics | Play history, user stats, bot performance |
| 🛡 Content Filter | Blocks NSFW, gambling, and piracy domains |
| 💤 Auto-disconnect | Leaves after idle timeout |
| 📝 Logging | Rotating coloured logs to console + file |

---

## 📁 Project Structure

```
Music Bot V2/
├── main.py                  # Entry point & bot class
├── config.py                # Configuration & logging setup
├── webserver.py             # Optional keep-alive HTTP server
├── requirements.txt
├── .env.example
│
├── cogs/                    # Slash command groups
│   ├── music.py             # /join /leave /play /search /pause /resume /skip /stop
│   ├── queue_cog.py         # /queue /shuffle /clear /loop /remove /move
│   ├── effects.py           # /volume /effects /effects_clear /effects_list
│   └── info.py              # /nowplaying /history /help /stats
│
├── core/                    # Business logic
│   ├── database.py          # Async SQLite (aiosqlite)
│   ├── youtube.py           # yt-dlp wrapper with caching
│   ├── spotify.py           # Spotify → YouTube conversion
│   ├── audio.py             # FFmpeg argument builder
│   ├── player.py            # Per-guild player state
│   └── validator.py         # URL safety validation
│
├── models/                  # Data models
│   ├── track.py             # Track dataclass
│   ├── server_config.py     # Per-guild config dataclass
│   └── enums.py             # LoopMode, AudioEffect, AudioQuality
│
└── utils/                   # Helpers
    ├── embeds.py            # Discord embed builders
    ├── views.py             # UI Views (buttons, dropdowns, pagination)
    ├── formatters.py        # Duration, progress bar, number formatting
    └── rate_limiter.py      # Per-user sliding-window rate limiter
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) installed and in your PATH

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your Discord Bot Token and App ID
```

### 4. Run the bot
```bash
python main.py
```

---

## 🤖 Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application → **Bot** section → create bot → copy token
3. Enable **Message Content Intent** and **Server Members Intent**
4. Generate invite URL with these permissions:
   - Connect, Speak (Voice)
   - Send Messages, Embed Links, Use Slash Commands, View Channels

---

## 🎛 Commands

### Playback
| Command | Description |
|---------|-------------|
| `/join` | Join your voice channel |
| `/leave` | Leave and clear queue |
| `/play <query>` | YouTube URL, Spotify URL, or search keywords |
| `/search <query>` | Search and pick from a dropdown list |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/skip` | Skip current track |
| `/stop` | Stop and clear queue |

### Queue
| Command | Description |
|---------|-------------|
| `/queue [page]` | Show queue (paginated) |
| `/shuffle` | Shuffle the queue |
| `/clear` | Clear entire queue |
| `/loop` | Cycle loop: Off → Track → Queue |
| `/remove <pos>` | Remove track at position |
| `/move <from> <to>` | Move track to a different position |

### Audio
| Command | Description |
|---------|-------------|
| `/volume <0-200>` | Set playback volume |
| `/effects <effect>` | Toggle an audio effect (with autocomplete) |
| `/effects_clear` | Disable all active effects |
| `/effects_list` | List all effects and their status |

### Info
| Command | Description |
|---------|-------------|
| `/nowplaying` | Show current track with progress bar |
| `/history` | Recent play history |
| `/help` | All commands |
| `/stats` | Bot performance statistics |

---

## 🔧 Optional Features

### Spotify
1. Create an app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Add `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` to `.env`
3. Uncomment `spotipy>=2.23.0` in `requirements.txt` and `pip install spotipy`

### Keep-alive Webserver (Render / Railway / UptimeRobot)
1. Uncomment `flask>=3.0.0` in `requirements.txt` and `pip install flask`
2. The server starts automatically on `PORT` (default 8080)

### Cookies (Age-restricted videos)
Place a `cookies.txt` file (Netscape format, exported from your browser) in the bot root directory. yt-dlp will pick it up automatically.

---

## 📋 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | — | **Required.** Bot token |
| `APP_ID` | — | Application ID (for slash command registration) |
| `SPOTIFY_CLIENT_ID` | — | Spotify API key |
| `SPOTIFY_CLIENT_SECRET` | — | Spotify API secret |
| `DATABASE_PATH` | `data/musicbot.db` | SQLite database file path |
| `MAX_QUEUE_SIZE` | `100` | Max tracks per queue |
| `MAX_USER_QUEUE` | `15` | Max tracks per user in queue |
| `MAX_TRACK_LENGTH` | `10800` | Max track length in seconds (3h) |
| `IDLE_TIMEOUT` | `300` | Seconds before auto-disconnect (5min) |
| `HISTORY_DAYS` | `30` | Days to keep play history |
| `EXTRA_BANNED_DOMAINS` | — | Comma-separated extra banned domains |
| `PORT` | `8080` | Keep-alive webserver port |

---

## 📄 License
MIT License — free for personal and educational use.
Please respect YouTube's Terms of Service and copyright laws.
