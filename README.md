# 🎵 Music Bot V3 (Enterprise Edition)

A professional, production-ready Discord music bot built in Python. Refactored from the ground up with a clean modular architecture, a rich dashboard-style UI, and enterprise-grade stability patterns.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 🎵 **YouTube Playback** | URL or search keywords; smart autocomplete from guild search history. |
| 🎤 **Spotify Support** | Track, album, full playlist → parallel-resolved to YouTube via `asyncio.Semaphore` (up to 5 concurrently). |
| 📋 **Smart Queue** | Persistent to SQLite, paginated & interactive dropdown management. |
| 🔁 **Loop Modes** | Cycle between `Off`, `Track`, and `Queue` via button or command. |
| 🎛 **18 Audio Effects** | Bass Boost, Nightcore, Vaporwave, Treble Boost, Vocal Boost, Karaoke, Vibrato, Tremolo, Chorus, Reverb, Echo, Distortion, Mono, Stereo Enhance, Compressor, Limiter, Noise Gate, 8D Audio. |
| 🔊 **Volume Control** | 0–200% via `/volume` command or ±10% live buttons on Now Playing. |
| 🎮 **Interactive UI** | Now Playing buttons (dynamic skip counts, disabled states), Queue dropdown, Search select — edit-in-place without chat spam. |
| 🎨 **Dynamic Accent Colors** | Dominant color auto-extracted from each track's thumbnail (zero dependencies — pure Python PNG/JPEG decoder). |
| 📊 **Statistics** | Per-guild play history, per-user stats, live bot performance metrics. |
| 🛡 **Content Filter** | 8-stage pipeline (Patterns, Domains, TLDs, Provider Whitelist, Async Content-Type Sniffing, etc.); blocks NSFW, gambling, piracy. |
| 💤 **Idle Auto-disconnect** | Configurable timeout; sends bilingual (EN/TH) farewell message. |
| 🔄 **Self-healing Voice** | Exponential-backoff reconnect (2s → 4s → 8s, up to 3 attempts) for unexpected drops. |
| ⏩ **Auto-skip on Error** | Up to 5 broken tracks skipped automatically before stopping. |
| 🔍 **Search Autocomplete** | `/play` autocomplete powered by per-guild SQLite search history. |
| 📝 **Structured Logging** | Coloured console + rotating full log + error-only log. |
| 🌐 **Bilingual Errors** | Comprehensive classification (Copyright, Age-Restricted, Rate Limits, etc.) with English + Thai subtitles. |
| 💾 **Queue Persistence** | Queues auto-saved every 5 minutes and on graceful shutdown. |
| 🌐 **Keep-alive Webserver**| Optional Flask server for Render / Railway / UptimeRobot hosting. |

---

## 📁 Project Structure

```text
Music Bot V3/
├── main.py                  # MusicBot class, event handlers, background tasks
├── config.py                # All settings loaded from .env + logging setup
├── webserver.py             # Optional Flask keep-alive server (port 8080)
├── requirements.txt         # Production dependencies
├── .env                     # Your secrets (not committed)
│
├── cogs/                    # Discord slash-command groups
│   ├── music.py             # /join /leave /play /search /pause /resume /skip /stop
│   ├── queue_cog.py         # /queue /shuffle /clear /loop /remove /move
│   ├── effects.py           # /volume /effects /effects_clear /effects_list
│   └── info.py              # /nowplaying /history /help /stats
│
├── core/                    # Business logic (no Discord imports)
│   ├── database.py          # Async SQLite via aiosqlite (persistent connection, WAL mode)
│   ├── youtube.py           # yt-dlp wrapper; separate LRU caches for metadata & search
│   ├── spotify.py           # Spotify → YouTube query converter (graceful no-op if unavailable)
│   ├── audio.py             # FFmpeg filter-chain builder for effects + quality + volume
│   ├── player.py            # GuildPlayer — all queue ops locked with asyncio.Lock
│   └── validator.py         # 8-stage URL safety pipeline + search-text sanitisation
│
├── models/                  # Plain data types
│   ├── track.py             # Track dataclass with JSON serialisation
│   ├── server_config.py     # Per-guild settings dataclass with JSON serialisation
│   └── enums.py             # LoopMode, AudioEffect (18 effects), AudioQuality (4 levels)
│
├── tests/                   # Test suite
│   ├── test_circuit_breaker.py
│   ├── test_embeds.py
│   ├── test_player.py
│   └── test_validator.py
│
└── utils/                   # Pure helpers
    ├── embeds.py            # Discord embed factories (Dashboard UI, dynamic colors)
    ├── views.py             # Interactive UIs: MusicControlView, QueueView, SearchSelectView
    ├── color_thief.py       # Async dominant-color extractor (no Pillow); TTL cache + stampede guard
    ├── formatters.py        # String and time formatting helpers
    ├── rate_limiter.py      # Sliding-window per-(guild, user) rate limiter
    └── error_handler.py     # Bilingual error classification, playback/command error embeds
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python **3.10+**
- [FFmpeg](https://ffmpeg.org/download.html) installed and on your `PATH`

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Fill in DISCORD_TOKEN and APP_ID at minimum
```

### 4. Run the bot
```bash
python main.py
```

Slash commands are synced globally on every startup. The database file is created automatically at `data/musicbot.db`.

---

## 🤖 Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. **New Application** → **Bot** section → **Add Bot** → copy the token
3. Enable the following **Privileged Gateway Intents**:
   - **Server Members Intent**
   - **Message Content Intent**
   - **Voice State Intent**
4. Under **OAuth2 → URL Generator**, select:
   - Scopes: `bot`, `applications.commands`
   - Bot permissions: `Connect`, `Speak`, `Send Messages`, `Embed Links`, `Use Slash Commands`, `View Channels`
5. Open the generated URL to invite the bot to your server

---

## 🎛 Commands

### Playback
| Command | Description |
|---------|-------------|
| `/join` | Join your current voice channel |
| `/leave` | Disconnect and clear the queue |
| `/play <query>` | YouTube URL, Spotify URL, YouTube playlist, or search keywords |
| `/search <query>` | Search YouTube and choose from a dropdown (up to 10 results) |
| `/pause` | Pause playback |
| `/resume` | Resume paused playback |
| `/skip` | Skip the current track |
| `/stop` | Stop playback, clear queue, and disconnect |

### Queue Management
| Command | Description |
|---------|-------------|
| `/queue [page]` | Show paginated queue with interactive track management dropdown |
| `/shuffle` | Shuffle all queued tracks |
| `/clear` | Clear the entire queue (also wipes DB) |
| `/loop` | Cycle loop mode: Off → Track → Queue |
| `/remove <position>` | Remove a track at a 1-based position |
| `/move <from> <to>` | Atomically move a track between positions |

### Audio
| Command | Description |
|---------|-------------|
| `/volume <0-200>` | Set playback volume; applies to the current source immediately |
| `/effects <effect>` | Toggle one of 18 audio effects (with autocomplete) |
| `/effects_clear` | Disable all active audio effects |
| `/effects_list` | Show all 18 effects with enabled/disabled status |

### Info
| Command | Description |
|---------|-------------|
| `/nowplaying` | Show the current track with live progress bar |
| `/history [limit]` | Show up to 20 recently played tracks (default 10) |
| `/help` | Full command reference embed |
| `/stats` | Live bot stats: uptime, memory, CPU, guild count, voice connections |

---

## 🎨 UI & Interactive Controls

### Now Playing Dashboard
Every new track sends a rich embed with:

| Field | Content |
|-------|---------|
| **Title** | Hyperlinked track title + channel name |
| **Thumbnail** | Track artwork (right-side thumbnail) |
| **Row 1** | ⏱ Duration · 👁 View count · 📋 Queue size + remaining time |
| **Row 2** | 👤 Requested by · 🔁 Loop badge · 🎚 Audio quality |
| **Row 3** | 🔊 Volume bar (`▮▮▮▮▮▯▯▯▯▯ 75%`) + active effects list |
| **Progress** | `▓▓▓▓▓░░░░░░░░░░░░░░░  1:23 / 3:45` (auto-updates every 7 s) |
| **Accent Color** | Extracted live from the track thumbnail (vibrant pixel algorithm) |

### Playback Control Buttons
Attached to every Now Playing message — all edits happen in-place, no extra messages:

**Row 0 — Core Controls**
- ⏸ **Pause** / ▶ **Resume**: Toggles; button label and style update live
- ⏭ **Skip**: Skips track; badge shows live queue count, e.g., `Skip (3)`
- 🔁 **Loop**: Cycles Off → Track → Queue; button turns green when active
- 🔀 **Shuffle**: Shuffles queue and refreshes the embed in-place
- ⏹ **Stop**: Stops playback, clears queue, disconnects, disables all buttons

**Row 1 — Volume**
- 🔉 **Vol -10%**: Lowers volume by 10%; rebuilds Now Playing embed in-place
- 🔊 **Vol +10%**: Raises volume by 10%; rebuilds Now Playing embed in-place

### Interactive Queue View (`/queue`)
A single message with live navigation and track management:

**Row 0 — Navigation**
- ◀ **Prev**: Go to previous page
- 📄 **N/M**: Page indicator (disabled — display only)
- **Next** ▶: Go to next page
- 🔄 **Refresh**: Re-read the live queue without re-sending

**Row 1 — Track Select Dropdown**
- Dropdown lists up to 10 tracks on the current page
- Selecting a track reveals action buttons: 🗑️ **Remove**, ⬆️ **Move to Top**, ✖ **Cancel**

### Search Results (`/search`)
- Sends a numbered embed with up to 10 results
- A select dropdown lets the user pick one track to enqueue
- Times out after 30 seconds if no selection is made

---

## 🎵 Audio Effects (18 Total)

| Effect | Command Value | Description |
|--------|--------------|-------------|
| 🔊 Bass Boost | `bassboost` | Heavy bass enhancement with dynamic normalisation |
| ⚡ Nightcore | `nightcore` | Speed + pitch raised (1.25×) |
| 🌊 Vaporwave | `vaporwave` | Speed + pitch lowered (0.8×) |
| 🎵 Treble Boost | `trebleboost` | High-frequency emphasis |
| 🎤 Vocal Boost | `vocalboost` | Boosts 300–3000 Hz vocal range |
| 🎙️ Karaoke | `karaoke` | Centre-channel cancellation |
| 〰️ Vibrato | `vibrato` | Pitch modulation at 6.5 Hz |
| 🎶 Tremolo | `tremolo` | Volume modulation at 8.8 Hz |
| 🎼 Chorus | `chorus` | Chorus effect with 55 ms delay |
| 🏛️ Reverb | `reverb` | Long hall echo (1000 ms) |
| 📣 Echo | `echo` | Short bounce echo (60 ms) |
| 🎸 Distortion | `distortion` | FFT-based distortion |
| 📻 Mono | `mono` | Downmix stereo to mono |
| 🔈 Stereo Enhance | `stereo` | Widen stereo field (2.5×) |
| 📊 Compressor | `compressor` | Dynamic range compression |
| 🚧 Limiter | `limiter` | Hard output limiter at 0.8 dB |
| 🚪 Noise Gate | `noisegate` | Suppress low-level background noise |
| 🎧 8D Audio | `8d` | Rotating spatial audio effect |

> All effects are implemented as FFmpeg `-af` filter chains. Multiple effects can be stacked. A `dynaudnorm` normalisation pass is always appended. Changes apply from the **next track**.

---

## 🔧 Optional Features

### Spotify Integration
1. Create an app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Add to `.env`:
   ```
   SPOTIFY_CLIENT_ID=your_id
   SPOTIFY_CLIENT_SECRET=your_secret
   ```
3. Uncomment `spotipy>=2.23.0` in `requirements.txt` and run `pip install spotipy`
4. Resolves single tracks, albums, and full paginated playlists up to **5 tracks in parallel**.

### Keep-alive Webserver
For hosting platforms that require an active HTTP endpoint (Render, Railway, UptimeRobot):
1. Uncomment `flask>=3.0.0` in `requirements.txt` and run `pip install flask`
2. Exposes `GET /` and `GET /health` on `PORT` (default `8080`)
3. Runs in a background daemon thread — zero impact on bot performance.

### Cookies (Age-restricted Videos)
Place a `cookies.txt` file (Netscape format) in the project root. `yt-dlp` automatically picks it up to bypass age restrictions.

---

## 📋 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | — | **Required.** Bot token from Discord |
| `APP_ID` | — | Application ID for slash commands |
| `SPOTIFY_CLIENT_ID` | — | Spotify API client ID |
| `SPOTIFY_CLIENT_SECRET` | — | Spotify API client secret |
| `DATABASE_PATH` | `data/musicbot.db` | Path to the SQLite database file |
| `MAX_QUEUE_SIZE` | `100` | Maximum tracks allowed per guild queue |
| `MAX_USER_QUEUE` | `15` | Maximum tracks a single user can enqueue |
| `MAX_TRACK_LENGTH` | `10800` | Maximum track length in seconds (default 3 h) |
| `IDLE_TIMEOUT` | `300` | Seconds of inactivity before auto-disconnect |
| `HISTORY_DAYS` | `30` | Days of play history retained per guild |
| `EXTRA_BANNED_DOMAINS` | — | Comma-separated extra domains to block |
| `PORT` | `8080` | Keep-alive webserver port |

---

## 🏗 Architecture & Design Notes

### Async-first Throughout
All I/O is non-blocking: `aiosqlite` for the database, `aiohttp` for thumbnail fetching and content-type sniffing, `asyncio.run_in_executor` for `yt-dlp`'s blocking calls. No `time.sleep` or blocking file I/O anywhere in the hot path.

### Persistent Database Connection
A single `aiosqlite` connection is opened at startup and held for the bot's lifetime. All access is serialised through an `asyncio.Lock`, eliminating the per-call open/close overhead that caused O(N) connection churn. We combine history logging and user stats updates into a single transaction per track. Uses **WAL mode** for concurrent read performance.

### Lock-protected GuildPlayer
Every queue mutation (`enqueue`, `dequeue`, `remove`, `shuffle`, `move`, `clear`) acquires `GuildPlayer.queue_lock` asynchronously. This prevents race conditions when multiple users press control buttons simultaneously.

### Circuit Breakers & Two-tier yt-dlp Cache
- **Exponential Backoff**: `yt-dlp` calls use true exponential backoff (e.g. 1s, 2s, 4s) to survive transient network issues.
- **URL metadata cache**: raw yt-dlp dict, TTL 300 s, max 50 entries.
- **Search result cache**: fully parsed `Track` list, TTL 300 s, max 100 entries — cache hits return instantly with zero re-parsing.

### Dynamic Accent Colors
`utils/color_thief.py` fetches the thumbnail, decodes PNG or JPEG entirely in **pure Python**, picks the most vibrant pixel, and caches the result for 1 hour per URL. Concurrent requests are collapsed via an `asyncio.Event` stampede guard.

### Self-healing Voice Reconnect
When `_play_next` detects a missing voice client, it calls `_try_reconnect()` which retries up to 3 times with exponential backoff: 2s → 4s → 8s. On total failure, it sends a bilingual error embed to the text channel.

### Background Tasks
- **`_idle_checker` (30s)**: Disconnects idle guilds, cancels progress tasks, and deletes Now Playing messages.
- **`_queue_saver` (5m)**: Persists all in-memory queues to SQLite.
- **Progress Bar Task (7s)**: Live-updates the Now Playing message. Handles deletions gracefully.

### Content Filter Pipeline (`core/validator.py`)
An 8-stage pipeline ensuring URL safety:
1. **Pattern check** — Regex for NSFW/gambling/piracy keywords (EN/TH).
2. **Domain & TLD blacklists** — Blocks known bad domains and TLDs.
3. **Extra banned domains** — Configurable via environment variables.
4. **Provider whitelist** — Allows YouTube/Spotify domains immediately.
5. **Audio extension** — Allows direct audio URLs (`.mp3`, `.flac`, etc.).
6. **Content-Type sniff** — Async `HEAD` request (cached 300s).
7. **Search query sanitisation**.

### Bilingual Error Classification
A robust `error_handler.py` system dynamically categorizes errors (e.g. Copyright, Age-Restricted, Rate Limited, Network) and provides beautiful, bilingual (English/Thai) embeds so users know exactly why a track failed.

---

## 📄 License
MIT License — free for personal and educational use.  
Please respect YouTube's Terms of Service and applicable copyright laws.
