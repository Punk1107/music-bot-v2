# 🎵 Music Bot V2 (Enterprise Edition)

A professional, production-ready Discord music bot built in Python. Engineered from the ground up with a clean modular architecture, a rich dashboard-style UI, and enterprise-grade stability patterns — including circuit breakers, an audio-backend abstraction layer, predictive pre-fetching, and an optional AI NLU pipeline.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 🎵 **YouTube Playback** | URL or search keywords; smart autocomplete from per-guild search history. |
| 🎤 **Spotify Support** | Track, album, full playlist → parallel-resolved to YouTube via `asyncio.Semaphore` (up to 5 concurrently). |
| 📋 **Smart Queue** | Persistent to SQLite, paginated & interactive dropdown management. |
| 🔁 **Loop Modes** | Cycle between `Off`, `Track`, and `Queue` via button or command. |
| 🎛 **18 Audio Effects** | Bass Boost, Nightcore, Vaporwave, Treble Boost, Vocal Boost, Karaoke, Vibrato, Tremolo, Chorus, Reverb, Echo, Distortion, Mono, Stereo Enhance, Compressor, Limiter, Noise Gate, 8D Audio. |
| 🔊 **Volume Control** | 0–200% via `/volume` command or ±10% live buttons on Now Playing. |
| 🎮 **Interactive UI** | Now Playing buttons (dynamic skip counts, disabled states), Queue dropdown, Search select — edit-in-place without chat spam. |
| 🎨 **Dynamic Accent Colors** | Dominant color auto-extracted from each track's thumbnail (zero dependencies — pure Python PNG/JPEG decoder). |
| 📊 **Statistics & Analytics** | Per-guild play history, per-user stats, anonymised analytics table, live bot performance metrics. |
| 🛡 **Content Filter** | 7-stage pipeline (Patterns, Domains, TLDs, Provider Whitelist, Audio Extension, Async Content-Type Sniffing, Search Sanitisation); blocks NSFW, gambling, piracy (EN/TH patterns). |
| 💤 **Idle Auto-disconnect** | Configurable timeout; sends bilingual (EN/TH) farewell message. |
| 🔄 **Self-healing Voice** | Exponential-backoff reconnect (2s → 4s → 8s, up to 3 attempts) for unexpected drops. |
| ⚡ **Circuit Breakers** | YouTube and Spotify API calls guarded by a 3-state circuit breaker (CLOSED/OPEN/HALF-OPEN) — trips after sustained failures to avoid cascading errors. |
| ⏩ **Predictive Pre-fetch** | Next track's CDN stream URL is resolved ~15s before the current track ends, enabling near-gapless transitions. |
| 🔌 **Audio Backend Abstraction** | FFmpeg backend active by default; Lavalink backend stub is included — swap with one config change. |
| 🤖 **AI NLU Pipeline** | Optional LLM-powered intent parser converts free-text chat into bot actions. Supports OpenAI and Anthropic. |
| ⏩ **Auto-skip on Error** | Up to 5 broken tracks skipped automatically before stopping. |
| 🔍 **Search Autocomplete** | `/play` autocomplete powered by per-guild SQLite search history. |
| 📝 **Structured Logging** | Coloured console + rotating full log + error-only log. |
| 🌐 **Bilingual Errors** | Comprehensive classification (Copyright, Age-Restricted, Rate Limits, etc.) with English + Thai subtitles. |
| 💾 **Queue Persistence** | Queues auto-saved every 5 minutes and on graceful shutdown; restored from DB on startup. |
| 🌐 **Keep-alive Webserver** | Built-in `aiohttp.web` server (no Flask) with dashboard, `/health`, `/status`, and `/ready` endpoints — integrates natively with the asyncio event loop. |

---

## 📁 Project Structure

```text
Music Bot V2/
├── main.py                  # MusicBot class, event handlers, background tasks
├── config.py                # All settings loaded from .env + logging setup
├── webserver.py             # Async aiohttp keep-alive server (port 8080)
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
│   ├── youtube.py           # yt-dlp wrapper; LRU caches for metadata & search; pre-fetch
│   ├── spotify.py           # Spotify → YouTube query converter (graceful no-op if unavailable)
│   ├── audio.py             # FFmpeg filter-chain builder for effects + quality + volume
│   ├── audio_backend.py     # AudioBackend ABC; FFmpegBackend (active) + LavalinkBackend (stub)
│   ├── circuit_breaker.py   # 3-state circuit breaker (CLOSED/OPEN/HALF-OPEN) for external APIs
│   ├── nlu.py               # AI NLU pipeline (OpenAI / Anthropic); feature-flagged via NLU_ENABLED
│   ├── player.py            # GuildPlayer — all queue ops locked with asyncio.Lock
│   └── validator.py         # 7-stage URL safety pipeline + search-text sanitisation
│
├── models/                  # Plain data types
│   ├── track.py             # Track dataclass with JSON serialisation + pre-fetch cache fields
│   ├── server_config.py     # Per-guild settings dataclass with JSON serialisation
│   └── enums.py             # LoopMode, AudioEffect (18 effects), AudioQuality (4 levels)
│
├── tests/                   # Test suite
│   ├── test_circuit_breaker.py
│   ├── test_color_thief.py
│   ├── test_database.py
│   ├── test_embeds.py
│   ├── test_error_handler.py
│   ├── test_nlu.py
│   ├── test_player.py
│   ├── test_validator.py
│   ├── test_views.py
│   ├── test_webserver.py
│   ├── test_youtube.py
│   └── unit/                # Deeper unit tests
│       ├── test_core_spotify_audio_backend.py
│       ├── test_external_clients.py
│       ├── test_infrastructure_cache_db.py
│       ├── test_music_cog.py
│       ├── test_music_service.py
│       ├── test_presentation_bot.py
│       ├── test_repositories.py
│       └── test_services_and_remaining_cogs.py
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

Slash commands are synced globally on startup (if `SYNC_COMMANDS=true`). The database file is created automatically at `data/musicbot.db`.

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
3. Install: `pip install spotipy>=2.23.0`
4. Resolves single tracks, albums, and full paginated playlists up to **5 tracks in parallel**.

### Keep-alive Webserver
The built-in `aiohttp.web` server runs natively in the bot's event loop — no separate thread or Flask required. It exposes:

| Endpoint | Description |
|----------|-------------|
| `GET /` | HTML status dashboard with uptime, latency, guilds, active players |
| `GET /health` | Simple `{"status": "ok"}` probe for Docker / UptimeRobot |
| `GET /status` | Full JSON metrics payload |
| `GET /ready` | Readiness probe — 200 if gateway connected, 503 if still starting |

Enabled automatically when `webserver.py` is importable. Port is controlled by the `PORT` environment variable (default `8080`).

### AI NLU Pipeline (Optional)
Converts free-text chat messages into structured bot actions via an LLM:
1. Set `NLU_ENABLED=true` in `.env`
2. Choose a provider: `NLU_PROVIDER=openai` or `NLU_PROVIDER=anthropic`
3. Add the corresponding API key: `OPENAI_API_KEY=sk-...` or `ANTHROPIC_API_KEY=sk-ant-...`
4. Optionally override the model: `NLU_MODEL=gpt-4o-mini` (default)

Supported intent actions: `play`, `skip`, `stop`, `pause`, `resume`, `volume_set`, `loop`, `queue_show`, `unknown`.

### Lavalink Backend (Future)
A Lavalink backend stub is included in `core/audio_backend.py`. To activate:
1. Install: `pip install wavelink>=3.0`
2. Run a Lavalink Java server
3. Set `AUDIO_BACKEND=lavalink` in `.env`
4. Add `LAVALINK_URI` and `LAVALINK_PASSWORD` to `.env`
5. Implement the `NotImplementedError` stubs in `LavalinkBackend`

### Cookies (Age-restricted Videos)
Place a `cookies.txt` file (Netscape format) in the project root. `yt-dlp` automatically picks it up to bypass age restrictions.

---

## 📋 Environment Variables

### Core
| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | — | **Required.** Bot token from Discord |
| `APP_ID` | — | Application ID for slash commands |
| `SYNC_COMMANDS` | `false` | Set `true` to sync slash commands on startup (avoid frequent syncing — causes 429s) |
| `AUTO_RESUME` | `false` | Rejoin voice channels and resume queues after a restart |

### Database & Limits
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `data/musicbot.db` | Path to the SQLite database file |
| `MAX_QUEUE_SIZE` | `100` | Maximum tracks allowed per guild queue |
| `MAX_USER_QUEUE` | `15` | Maximum tracks a single user can enqueue |
| `MAX_TRACK_LENGTH` | `10800` | Maximum track length in seconds (default 3 h) |
| `IDLE_TIMEOUT` | `300` | Seconds of inactivity before auto-disconnect |
| `HISTORY_DAYS` | `30` | Days of play history retained per guild |

### Spotify (Optional)
| Variable | Default | Description |
|----------|---------|-------------|
| `SPOTIFY_CLIENT_ID` | — | Spotify API client ID |
| `SPOTIFY_CLIENT_SECRET` | — | Spotify API client secret |

### Audio & Playback
| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIO_BACKEND` | `ffmpeg` | Audio backend: `"ffmpeg"` or `"lavalink"` |
| `PREFETCH_BEFORE_END` | `15` | Seconds before track end to start pre-fetching next CDN URL |
| `STREAM_URL_TTL` | `14400` | Pre-fetched stream URL cache lifetime in seconds (4 h) |
| `EXTRACT_CONCURRENCY` | `3` | Max simultaneous yt-dlp extractions (prevents CPU spikes) |

### Circuit Breaker
| Variable | Default | Description |
|----------|---------|-------------|
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Consecutive failures before circuit trips to OPEN |
| `CIRCUIT_BREAKER_WINDOW` | `60` | Seconds to stay OPEN before probing with HALF-OPEN |

### NLU (Optional)
| Variable | Default | Description |
|----------|---------|-------------|
| `NLU_ENABLED` | `false` | Enable the AI NLU pipeline |
| `NLU_PROVIDER` | `openai` | LLM provider: `"openai"` or `"anthropic"` |
| `NLU_MODEL` | `gpt-4o-mini` | Model to use (overrides provider default) |
| `NLU_MAX_TOKENS` | `256` | Token cap for NLU responses |
| `OPENAI_API_KEY` | — | Required if `NLU_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | — | Required if `NLU_PROVIDER=anthropic` |

### Developer & Hosting
| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_LOG_CHANNEL_ID` | — | Channel ID to forward full tracebacks for debugging |
| `PORT` | `8080` | Keep-alive webserver port |
| `EXTRA_BANNED_DOMAINS` | — | Comma-separated extra domains to block in validator |

---

## 🏗 Architecture & Design Notes

### Async-first Throughout
All I/O is non-blocking: `aiosqlite` for the database, `aiohttp` for thumbnail fetching and content-type sniffing, `asyncio.run_in_executor` for `yt-dlp`'s blocking calls. No `time.sleep` or blocking file I/O anywhere in the hot path.

### Persistent Database Connection
A single `aiosqlite` connection is opened at startup and held for the bot's lifetime. All access is serialised through an `asyncio.Lock`, eliminating the per-call open/close overhead. History logging and user stats updates are combined into a single transaction per track. Uses **WAL mode** for concurrent read performance.

### Lock-protected GuildPlayer
Every queue mutation (`enqueue`, `dequeue`, `remove`, `shuffle`, `move`, `clear`) acquires `GuildPlayer.queue_lock` asynchronously. This prevents race conditions when multiple users press control buttons simultaneously.

### Circuit Breakers
Both the YouTube and Spotify extractors are wrapped in `CircuitBreaker` instances (`bot.yt_breaker`, `bot.sp_breaker`). After `CIRCUIT_BREAKER_THRESHOLD` consecutive failures the breaker trips to OPEN, immediately returning a "System Busy" embed to users instead of hammering the failing API. It transitions to HALF-OPEN after `CIRCUIT_BREAKER_WINDOW` seconds and resets to CLOSED on the first successful probe.

### Audio Backend Abstraction
`core/audio_backend.py` defines an `AudioBackend` ABC. `FFmpegBackend` (default) wraps `discord.FFmpegPCMAudio`. `LavalinkBackend` is a stub ready for `wavelink` integration. The music cog calls `bot.audio_backend.play()` — swapping the backend requires only one line change in `.env`.

### Predictive Pre-fetch (Two-tier Cache)
- **Stream URL pre-fetch**: ~15 s before the current track ends, a background task resolves the next track's CDN URL and stores it on `track.stream_url_cache` (TTL: 4 h). `get_stream_url()` returns the cached URL instantly — near-gapless transitions.
- **Metadata cache**: raw yt-dlp dict, TTL 300 s, max 50 entries.
- **Search result cache**: fully parsed `Track` list, TTL 300 s, max 100 entries — cache hits return instantly with zero re-parsing.

### Extraction Concurrency Throttle
A module-level `asyncio.Semaphore(EXTRACT_CONCURRENCY)` caps simultaneous heavy yt-dlp extractions (default 3) to prevent CPU spikes and I/O starvation on the event loop during playlist loads.

### Dynamic Accent Colors
`utils/color_thief.py` fetches the thumbnail, decodes PNG or JPEG entirely in **pure Python**, picks the most vibrant pixel, and caches the result for 1 hour per URL. Concurrent requests are collapsed via an `asyncio.Event` stampede guard.

### Self-healing Voice Reconnect
When `_play_next` detects a missing voice client, it calls `_try_reconnect()` which retries up to `RECONNECT_ATTEMPTS` (default 3) times with exponential backoff: 2s → 4s → 8s. On total failure, it sends a bilingual error embed to the text channel.

### Background Tasks
- **`_idle_checker` (30s)**: Disconnects idle guilds, cancels progress tasks, and deletes Now Playing messages.
- **`_queue_saver` (5m)**: Persists all in-memory queues to SQLite.
- **Progress Bar Task (7s)**: Live-updates the Now Playing message. Handles deletions gracefully.

### Content Filter Pipeline (`core/validator.py`)
A 7-stage pipeline ensuring URL and search safety:
1. **Pattern check** — Regex for NSFW/gambling/piracy keywords (EN/TH), with separate word-boundary and substring lists.
2. **Domain blacklist** — Blocks a curated list of known bad domains.
3. **TLD blacklist** — Blocks `.xxx`, `.porn`, `.adult`, `.sex`, `.casino`, `.bet`, `.poker`.
4. **Extra banned domains** — Configurable via `EXTRA_BANNED_DOMAINS` environment variable.
5. **Provider whitelist** — Immediately allows YouTube/Spotify domains.
6. **Audio extension** — Allows direct audio URLs (`.mp3`, `.flac`, `.opus`, etc.).
7. **Content-Type sniff** — Async `HEAD` request (cached 300 s) for unknown URLs.

Search query text is run through the same pattern lists before being sent to the YouTube API.

### AI NLU Pipeline (`core/nlu.py`)
When `NLU_ENABLED=true`, free-text messages are sent to the configured LLM (OpenAI or Anthropic) with a structured system prompt. The response is parsed into an `NLUResult` with an `action` and `params` dict. Fully async, uses the shared `aiohttp.ClientSession`, and gracefully degrades to `None` on any error.

### Bilingual Error Classification
`utils/error_handler.py` dynamically categorises errors (e.g. Copyright, Age-Restricted, Rate Limited, Network) and provides beautiful, bilingual (English/Thai) embeds so users know exactly why a track failed.

### Integrated Async Webserver
`webserver.py` uses `aiohttp.web` — not Flask — so it runs directly in the Discord bot's asyncio event loop with no threads. It includes an error middleware, stats caching (15-second TTL), and a `SO_REUSEADDR` + retry loop to handle Windows TIME_WAIT socket issues on quick restarts.

---

## 📄 License
MIT License — free for personal and educational use.  
Please respect YouTube's Terms of Service and applicable copyright laws.