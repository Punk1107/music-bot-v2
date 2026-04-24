# 🎵 Music Bot V2

A professional, production-ready Discord music bot built in Python. Refactored from the ground up with a clean modular architecture, a rich dashboard-style UI, and enterprise-grade stability patterns.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 🎵 YouTube Playback | URL or search keywords; smart autocomplete from guild history |
| 🎤 Spotify Support | Track, album, full playlist → parallel-resolved to YouTube |
| 📋 Smart Queue | Persistent to SQLite, paginated & interactive dropdown management |
| 🔁 Loop Modes | Off → Track → Queue (cycles via button or command) |
| 🎛 18 Audio Effects | Bass Boost, Nightcore, Vaporwave, Treble Boost, Vocal Boost, Karaoke, Vibrato, Tremolo, Chorus, Reverb, Echo, Distortion, Mono, Stereo Enhance, Compressor, Limiter, Noise Gate, 8D Audio |
| 🔊 Volume Control | 0–200% via `/volume` command or ±10% live buttons on Now Playing |
| 🎮 Interactive UI | Now Playing buttons, Queue dropdown, Search select — all edit-in-place |
| 🎨 Dynamic Accent Colors | Dominant color auto-extracted from each track's thumbnail (zero dependencies — pure Python PNG/JPEG decoder) |
| 📊 Statistics | Per-guild play history, per-user stats, live bot performance metrics |
| 🛡 Multi-layer Content Filter | Pattern + domain + TLD + Content-Type checks; blocks NSFW, gambling, piracy; supports Thai keywords |
| 💤 Idle Auto-disconnect | Configurable timeout; sends bilingual (EN/TH) farewell message |
| 🔄 Self-healing Voice | Exponential-backoff reconnect (2s → 4s → 8s, up to 3 attempts) |
| 🔁 Auto-skip on Error | Up to 5 broken tracks skipped automatically before stopping |
| 🔍 Search History Autocomplete | `/play` autocomplete powered by per-guild SQLite search history |
| 📝 Structured Logging | Coloured console + rotating full log + error-only log |
| 🌐 Bilingual Error Messages | All error embeds include English + Thai subtitles |
| 💾 Queue Persistence | Queues auto-saved every 5 minutes and on graceful shutdown |
| 🌐 Keep-alive Webserver | Optional Flask server for Render / Railway / UptimeRobot hosting |

---

## 📁 Project Structure

```
Music Bot V2/
├── main.py                  # MusicBot class, event handlers, background tasks
├── config.py                # All settings loaded from .env + logging setup
├── webserver.py             # Optional Flask keep-alive server (port 8080)
├── requirements.txt
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
│   └── validator.py         # 4-stage URL safety pipeline + search-text sanitisation
│
├── models/                  # Plain data types
│   ├── track.py             # Track dataclass with JSON serialisation
│   ├── server_config.py     # Per-guild settings dataclass with JSON serialisation
│   └── enums.py             # LoopMode, AudioEffect (18 effects), AudioQuality (4 levels)
│
└── utils/                   # Pure helpers
    ├── embeds.py            # All Discord embed factories (Now Playing, Queue, Search, Help…)
    ├── views.py             # MusicControlView, QueueView, SearchSelectView
    ├── color_thief.py       # Async dominant-color extractor (no Pillow); TTL cache + stampede guard
    ├── formatters.py        # fmt_duration, progress_bar, fmt_views, truncate, ordinal
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
| Title | Hyperlinked track title + channel name |
| Thumbnail | Track artwork (right-side thumbnail) |
| Row 1 | ⏱ Duration · 👁 View count · 📋 Queue size + remaining time |
| Row 2 | 👤 Requested by · 🔁 Loop badge · 🎚 Audio quality |
| Row 3 | 🔊 Volume bar (`▮▮▮▮▮▯▯▯▯▯ 75%`) + active effects list |
| Progress | `▓▓▓▓▓░░░░░░░░░░░░░░░  1:23 / 3:45` (auto-updates every 7 s) |
| Accent color | Extracted live from the track thumbnail (vibrant pixel algorithm) |

### Playback Control Buttons
Attached to every Now Playing message — all edits happen in-place, no extra messages:

**Row 0 — Core Controls**

| Button | Behaviour |
|--------|-----------|
| ⏸ Pause / ▶ Resume | Toggles; button label and style update live |
| ⏭ Skip (N) | Skips track; badge shows how many remain in queue |
| 🔁 / 🔂 Loop | Cycles Off → Track → Queue; button turns green when active |
| 🔀 Shuffle | Shuffles queue and refreshes the Now Playing embed in-place |
| ⏹ Stop | Stops playback, clears queue, disconnects, disables all buttons |

**Row 1 — Volume**

| Button | Behaviour |
|--------|-----------|
| 🔉 Vol -10% | Lowers volume by 10%; rebuilds Now Playing embed in-place |
| 🔊 Vol +10% | Raises volume by 10%; rebuilds Now Playing embed in-place |

> Both Skip (disabled when nothing is playing) and Shuffle (disabled with < 2 tracks) are dynamically enabled/disabled based on real-time player state.

### Interactive Queue View (`/queue`)
A single message with live navigation and track management:

**Row 0 — Navigation**

| Button | Action |
|--------|--------|
| ◀ Prev | Go to previous page |
| 📄 N/M | Page indicator (disabled — display only) |
| Next ▶ | Go to next page |
| 🔄 Refresh | Re-read the live queue without re-sending |

**Row 1 — Track Select Dropdown**

- Dropdown lists up to 10 tracks on the current page
- Selecting a track reveals three action buttons (Row 2):

| Button | Action |
|--------|--------|
| 🗑️ Remove | Remove the track; queue refreshes automatically |
| ⬆️ Move to Top | Move to position #1; view jumps to page 1 |
| ✖ Cancel | Dismiss without action |

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
4. Supports: single tracks, albums, and full paginated playlists
5. Resolves up to **5 tracks in parallel** via `asyncio.Semaphore`

### Keep-alive Webserver
For hosting platforms that require an active HTTP endpoint (Render, Railway, UptimeRobot):
1. Uncomment `flask>=3.0.0` in `requirements.txt` and run `pip install flask`
2. Exposes `GET /` and `GET /health` on `PORT` (default `8080`)
3. Runs in a background daemon thread — zero impact on bot performance

### Cookies (Age-restricted / Sign-in Required Videos)
Place a `cookies.txt` file (Netscape format, exported from your browser) in the project root. yt-dlp automatically picks it up for all operations.

---

## 📋 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | — | **Required.** Bot token from Discord Developer Portal |
| `APP_ID` | — | Application ID for slash command registration |
| `SPOTIFY_CLIENT_ID` | — | Spotify API client ID (optional) |
| `SPOTIFY_CLIENT_SECRET` | — | Spotify API client secret (optional) |
| `DATABASE_PATH` | `data/musicbot.db` | Path to the SQLite database file |
| `MAX_QUEUE_SIZE` | `100` | Maximum tracks allowed per guild queue |
| `MAX_USER_QUEUE` | `15` | Maximum tracks a single user can have in the queue |
| `MAX_TRACK_LENGTH` | `10800` | Maximum track length in seconds (default 3 h) |
| `IDLE_TIMEOUT` | `300` | Seconds of inactivity before auto-disconnect (5 min) |
| `HISTORY_DAYS` | `30` | Days of play history retained per guild |
| `EXTRA_BANNED_DOMAINS` | — | Comma-separated extra domains to block |
| `PORT` | `8080` | Keep-alive webserver port |

---

## 🗄 Database Schema

The SQLite database (`data/musicbot.db`) uses **WAL mode** for concurrent read performance. Tables:

| Table | Purpose |
|-------|---------|
| `queue` | Persisted queue tracks per guild (position-ordered) |
| `history` | Play history with skip/complete status and duration played |
| `server_configs` | Per-guild configuration JSON (upserted on save) |
| `user_stats` | Per-(user, guild) track count and total listening time |
| `search_history` | Recent search queries per guild powering `/play` autocomplete (max 200/guild) |

---

## 🏗 Architecture & Design Notes

### Async-first Throughout
All I/O is non-blocking: `aiosqlite` for the database, `aiohttp` for thumbnail fetching and content-type sniffing, `asyncio.run_in_executor` for yt-dlp's blocking calls. No `time.sleep` or blocking file I/O anywhere in the hot path.

### Persistent Database Connection
A single `aiosqlite` connection is opened at startup and held for the bot's lifetime. All access is serialised through an `asyncio.Lock` — eliminates the per-query open/close overhead.

### GuildPlayer — Lock-protected State
Every queue mutation (`enqueue`, `dequeue`, `remove`, `shuffle`, `move`, `clear`) acquires `GuildPlayer.queue_lock`. This prevents race conditions when multiple users press control buttons simultaneously.

### Two-tier yt-dlp Cache
- **URL metadata cache**: raw yt-dlp dict, TTL 300 s, max 50 entries
- **Search result cache**: fully parsed `Track` list, TTL 300 s, max 100 entries — cache hits return instantly with no re-parsing

### Dynamic Accent Colors (Zero Dependencies)
`utils/color_thief.py` fetches the track thumbnail via the shared `aiohttp.ClientSession`, decodes PNG (IHDR + IDAT chunks) or JPEG (scan-segment sampling) entirely in pure Python, picks the most vibrant pixel (highest saturation × value in HSV space), and caches the result for 1 hour per URL. Concurrent requests for the same URL are collapsed into one fetch via an `asyncio.Event` stampede guard.

### Self-healing Voice Reconnect
When `_play_next` detects a missing voice client, it calls `_try_reconnect()` which retries up to `RECONNECT_ATTEMPTS` times (default 3) with exponential backoff: 2 s → 4 s → 8 s. On total failure it sends a bilingual error embed to the text channel.

### Auto-skip on Broken Tracks
`_play_next` tracks a `skip_depth` counter. Consecutive broken tracks are auto-skipped up to `SKIP_ERROR_LIMIT` (default 5). Each skip sends a bilingual `notify_playback_error` embed classifying the failure (copyright, private, age-restricted, rate-limited, timeout, network, or unknown).

### Progress Bar Background Task
A per-guild `asyncio.Task` edits the Now Playing message every `PROGRESS_BAR_UPDATE_INTERVAL` seconds (default 7 s). It cancels itself on skip/stop and handles `discord.NotFound` gracefully (message deleted by user). The task is always cancelled before a new track starts to avoid stale updates.

### Background Tasks in `main.py`
| Task | Interval | Purpose |
|------|----------|---------|
| `_idle_checker` | Every 30 s | Auto-disconnect guilds idle ≥ `IDLE_TIMEOUT`; cancels progress task and deletes Now Playing message first |
| `_queue_saver` | Every 5 min | Persist all non-empty in-memory queues to SQLite |

### Content Filter Pipeline (`core/validator.py`)
Incoming URLs pass through four stages in order:
1. **Pattern check** — word-boundary regex for NSFW / gambling / piracy keywords (including Thai)
2. **Provider whitelist** — allow YouTube and Spotify domains immediately
3. **Audio extension** — allow direct audio file URLs (`.mp3`, `.flac`, `.opus`, etc.)
4. **Content-Type sniff** — async HEAD request with 5 s timeout; result cached for 300 s

### Rate Limiter
Per-(guild, user) sliding-window limiter: max **20 requests per 60 seconds**. Configured in `config.py` constants (not env-vars) for simplicity.

### Graceful Shutdown
On `SIGINT` / `SIGTERM`, the bot:
1. Sets `_shutdown = True` to stop new tasks being scheduled
2. Persists all active queues to SQLite
3. Closes the shared `aiohttp.ClientSession`
4. Closes the persistent `aiosqlite` connection
5. Calls `discord.py`'s `super().close()`

---

## 📄 License
MIT License — free for personal and educational use.  
Please respect YouTube's Terms of Service and applicable copyright laws.
