# OkraStrut — Discord Trivia & Games Bot

A feature-rich Discord bot built in Python with continuous trivia, 38 mini-games, a full tournament system, a multi-level escape room, and a self-deploying update mechanism. Runs in production on Heroku with MongoDB, AWS S3, and a suite of third-party APIs.

---

## Features

### Continuous Trivia
The core loop runs trivia, Jeopardy, and crossword questions in a dedicated channel. Tracks per-user streaks, fastest answers, and round winners. Supports a range of game modifiers:

| Mode | Description |
|------|-------------|
| Glyph | Replaces letters with Unicode lookalikes to prevent Googling |
| Blind | Hides answer choices |
| Golf | Fewest correct answers wins |
| Sniper | One guess per question per player |
| Blitz | Rapid-fire round pace |
| Exact | Requires exact string match |
| God | Alternative scoring system |
| Marx | Groucho Marx AI commentary between questions |

### Mini-Game Arena (`/arena`)
38 playable mini-games selectable by name, plus **Random** (picks one at random) and **Chaos** (different random game each round). Games span image identification, audio challenges, word puzzles, geography, chess, finance, and more.

**Usage:**
```
/arena <game_name> [num_rounds]
/arena chaos [num_rounds]
/arena cancel
```

**Examples:**
```
/arena posterblitz 5       — 5 rounds of movie poster identification
/arena checkmate           — Chess puzzles (default rounds)
/arena chaos 10            — 10 rounds, different game each time
/arena random              — One randomly selected game
/arena cancel              — Cancel the current game
```

<details>
<summary>Full game list (38 games)</summary>

| Command Name | Type | Description |
|---|---|---|
| `posterblitz` | Image | Identify movies from posters |
| `moviemayhem` | Image | Identify movies from scenes |
| `missinglink` | Logic | Find the connection between items |
| `famouspeeps` | Ranking | Rank celebrities |
| `magiceye` | Image | 3D stereogram challenges |
| `okranimal` | Image | Animal identification |
| `theriddler` | Text | Riddle questions |
| `wordnerd` | Text | Dictionary definitions |
| `flagfest` | Image | Country flag identification |
| `lyriq` | Text | Song lyric identification |
| `polyglottery` | Language | Translation challenges |
| `proseandcons` | Text | Identify books from excerpts |
| `signlanguage` | Visual | Math/symbol interpretation |
| `elementary` | Image | Chemical element identification |
| `jigsawed` | Image | Jigsaw puzzle challenges |
| `borderline` | Geography | Border/geography challenges |
| `faceoff` | Image | Celebrity face comparison |
| `rushmore` | Ranking | 4-item ranking challenges |
| `wordlewar` | Word | Wordle-style word guessing |
| `musiq` | Music | Music knowledge challenges |
| `myopicmystery` | Image | Blurred image identification |
| `microscopicmystery` | Image | Zoomed-in detail identification |
| `fusionchallenge` | Image | Blended image identification |
| `tally` | Math | Counting/estimation challenges |
| `checkmate` | Chess | Chess puzzle challenges |
| `wallstreet` | Finance | Stock/market challenges |
| `xxxx` | Finance | Currency conversion challenges |
| `okrace` | Speed | Racing-format trivia |
| `spotlight` | Search | Google-style search challenges |
| `hearhere` | Audio | Sound effect identification (voice channel) |
| `whosays` | Audio | Music/audio identification (voice channel) |
| `letstalk` | Audio | Spoken audio challenges (voice channel) |
| `feudblitz` | Social | Family Feud-style game |
| `jocktalk` | Sports | Sports logo identification |
| `30for30` | Speed | 30-question rapid-fire rounds |
| `okrasays` | Interactive | Simon Says variant |
| `random` | Meta | Randomly picks any game |
| `chaos` | Meta | Different random game each round |

</details>

Audio games (`hearhere`, `whosays`, `letstalk`) stream directly into Discord voice channels using a dedicated second bot instance, allowing simultaneous audio and text game sessions.

### Tournament System (`/tournament`)
Full bracket-style tournament manager:
- **Signup phase** → **Points race** (round-robin seeding) → **Semifinals** → **Finals**
- Head-to-head matches with best-of-7 knockout rounds
- Per-channel tournament isolation — multiple tournaments can run across different servers simultaneously
- Persistent leaderboards and all-time win/loss statistics stored in MongoDB
- Live match progress updates in-channel

**Commands:**
```
/tournament start           — Open signup for a new tournament
/tournament status          — View current bracket and standings
/tournament leaderboard     — All-time tournament rankings
/tournament stats           — Your personal win/loss record
/tournament cancel          — Cancel active tournament (admin only)
/tournament test            — Add 4 fake players for testing (admin only)
```

### Okra Hunt Escape Room
A 7-level text adventure escape room built into the bot:
- Each level presents a unique puzzle (text input, emoji reaction, time-based challenge)
- Role-based progression — solving a level grants a Discord role unlocking the next channel
- Leaderboard tracks completion order and progress
- Auto-deletes player messages to prevent spoiler leaks

### Simply Trivia
A continuous, always-on trivia mode running in a dedicated channel:
- First-to-answer tracking with millisecond precision
- Rolling streak tracking and top-100 streak leaderboard
- Updates leaderboard every 5 questions
- Graceful shutdown on deploys — waits for the current round to finish

### Other Systems
- **Bumper King**: Tracks the last user to bump the server on Disboard. Bumper King earns a role and the exclusive `/okrafx` color-change command
- **Question Flagging** (`/flag`): Players flag bad questions for moderator review, stored in an audit collection with context
- **AI Personalities**: Bot can respond in 14 different personas (Shakespeare, Pirate, Noir Detective, Hype Man, Roast Comic, Haiku Poet, and more) powered by GPT

---

## Tech Stack

**Core**
- Python 3.12
- [discord.py](https://discordpy.readthedocs.io/) 2.7.1
- asyncio throughout — all I/O is non-blocking

**Database**
- MongoDB via [Motor](https://motor.readthedocs.io/) (async) and PyMongo (sync)

**APIs & Services**

| Service | Usage |
|---------|-------|
| OpenAI GPT | AI commentary, image descriptions, personality modes |
| AWS S3 + aioboto3 | Audio file hosting, image storage, presigned URL generation |
| Deepgram | Text-to-speech for audio mini-games |
| Google Maps | Location-based question images |
| Google Translate | Translation challenge questions |
| Merriam-Webster | Dictionary and thesaurus definitions |
| OpenWeather | Weather-based questions |
| Reddit API | Community content integration |
| Sentry | Error tracking and monitoring |

**Image Processing**
- Pillow, CairoSVG, NumPy — image generation, SVG rendering, stereogram creation

---

## Architecture

```
discordbot.py          — Main bot: trivia loop, slash commands, event handlers
├── tournament.py      — Tournament manager (round-robin, knockouts, leaderboards)
├── okra_hunt.py       — Escape room engine (7 levels, role progression)
├── mini_games.py      — Arena router + 38 mini-game implementations
├── simply_trivia.py   — Always-on trivia channel handler
├── self_update.py     — GitHub polling + Heroku auto-deploy
└── main.py            — Stereogram image generation utility
```

**Dual bot instance**: A second Discord bot instance runs alongside the main bot, dedicated to audio games. This allows a voice-channel audio game and a text-channel trivia game to run simultaneously without conflicts. The audio bot persists across hot-reloads via `sys.modules`.

**Self-update loop**: After each trivia round, the bot polls the GitHub API for new commits. On detecting a new SHA (tracked in MongoDB), it triggers a Heroku build via the Heroku API, gracefully winds down active game sessions, and waits for the new dyno to replace it — achieving zero-touch deploys.

**Environment separation**: A single codebase serves local development, staging, and production. The `ENVIRONMENT` variable switches the active set of Discord server/channel/role IDs. Credentials are read from environment variables (Heroku config vars in production, `.env` file locally via python-dotenv).

---

## Setup

### Prerequisites
- Python 3.12
- MongoDB instance
- Discord application with two bot tokens (main + audio)
- Heroku account (or compatible hosting)

### Installation

```bash
git clone https://github.com/nikhilodeon2001/discordbot.git
cd discordbot
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your credentials
python discordbot.py
```

### Environment Variables

See [.env.example](.env.example) for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `discord_token` | Main Discord bot token |
| `DISCORD_MINI_GAME_AUDIO_BOT_TOKEN` | Audio bot token (optional) |
| `mongo_db_string` | MongoDB connection string |
| `openai_api_key` | OpenAI API key |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | AWS credentials for S3 |
| `deepgram_api_key` | Deepgram TTS key |
| `ENVIRONMENT` | `stage` or `prod` (controls which server/channel IDs are used) |
| `channel_id` | Main trivia channel ID |
| `SENTRY_DSN` | Sentry error tracking DSN |

### Deployment

The bot runs as a Heroku worker dyno:
```
worker: python discordbot.py
```

The self-update system handles subsequent deploys automatically — push to `main` and the running bot detects the change and redeploys itself at the next round boundary.
