"""One-off script: create a #game-options reference channel documenting every
gameplay/question toggle, mirroring #how-to-play's category and permissions.

Must be run once per environment, with the matching bot token:

    ENVIRONMENT=stage discord_token=<stage bot token> python scripts/create_game_options_channel.py
    ENVIRONMENT=prod discord_token=<prod bot token> python scripts/create_game_options_channel.py

Safe to delete after running once in both environments.
"""
import os
import discord

ENVIRONMENT = os.environ.get("ENVIRONMENT", "prod")

GUILD_IDS = {"prod": 1367682586079395902, "stage": 1375328358573015050}
HOW_TO_PLAY_CHANNEL_IDS = {"prod": 1411551000065609939, "stage": 1423894911908057118}

GUILD_ID = GUILD_IDS[ENVIRONMENT]
HOW_TO_PLAY_CHANNEL_ID = HOW_TO_PLAY_CHANNEL_IDS[ENVIRONMENT]

GAMEPLAY_OPTIONS_MESSAGE_1 = """🎮⚙️ **Gameplay Options** (1/2)
Set by replying after you win a round, or toggle mid-round with #[command] (except Golf). Lasts for the rest of that round only.

⏱️⏳ **<3-15>** — Time (s) between questions. How long the pause is after an answer is revealed before the next question starts (default 5s).

🔥🤘 **Yolo** — No scores until the end. The scoreboard is hidden after each question (shown alphabetically, scores masked as ####) — full ranked standings only reveal on the round's last question. Scores are still tracked normally throughout.

🙈🚫 **Blind** — No answers shown. The correct answer isn't revealed after each question.

🚩🔨 **Marx** — No recognizing answers. The ⬆️ reaction that marks the winning message is skipped. Combined with Blind, the whole reveal (including the winner's name) is skipped when nobody else answered.

📷❌ **Blank** — No image questions. Rendered-image questions show as plain text instead, and photo-based trivia questions are excluded from the round entirely.

👻🎃 **Ghost** — All responses vanish. Every player's answer is deleted from the channel right after it's scored. Start a message with . , or ~ to keep it from being deleted.

🫥🕶️ **Cloak** — Your responses vanish. Same as Ghost, but only for whoever activated it — everyone else's answers stay visible.
.
"""

GAMEPLAY_OPTIONS_MESSAGE_2 = """🎮⚙️ **Gameplay Options** (2/2)

🧢🎤 **Sniper** — One answer per player. Your first message on a question is your only attempt — right or wrong — even on questions that normally allow retries.

🏆⚡ **Blitz** — One winner per question. Only the first correct answer scores points; everyone who answers correctly after that gets zero for that question.

🤓🔍 **Poindexter** — Stricter answers. Typo tolerance, sounds-like matching, and partial/keyword-only answers are all turned off for free-text questions. Numeric, multiple-choice, and math answers are unaffected.

⛳📉 **Golf** — Slowest answers win. Points and the speed bonus both flip — the slowest correct answer scores highest instead of the fastest.

🔐🛡️ **Glyph** — Add anti-Google defenses. Question text gets some letters swapped for visually-identical lookalike characters — reads the same to you, but can't be pasted into a search engine.

🕹️ Toggle mid-round with #[command]
⛳ Golf can't be toggled mid-round
.
"""

QUESTION_OPTIONS_MESSAGE = """📝🔀 **Question Options**
Set only by replying after you win a round — these can't be toggled mid-round, and last for the rest of that round only.

🇺🇸🗽 **Freedom** — No multiple choice. Removes the dedicated multiple-choice question pool from the round.

⛓️🔐 **Bondage** — More multiple choice. Reserves most of the round's remaining questions for multiple choice.

🧮❌ **Greg** — No math questions. Guarantees zero math questions (normally there's up to a 50/50 chance of one).

🟦❌ **Xela** — No Jeopardy questions. Removes Jeopardy-style clues from the round.

📰❌ **Cross** — No Crossword clues. Removes Crossword-style clues from the round.

📰✋ **Word** — More Crossword clues. Adds more Crossword-style clues to the round.

🟦✋ **Alex** — More Jeopardy questions. Adds more Jeopardy-style clues to the round.

🤓📝 **Nerd** — Add SAT questions. Adds SAT-style Math/Verbal/Grammar questions to the round.

🎖🥒 **Dicktator** — Choose the categories. Each question, you'll get a numbered list of category titles to pick from — reply with a number within 10s, or it defaults to the first option.

🏁⏭️ **x** — I'm Done / Skip. Skip setting any options for this round.
.
"""

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    try:
        guild = client.get_guild(GUILD_ID)
        if guild is None:
            print(f"❌ Guild {GUILD_ID} not found (bot not in that server?)")
            return

        how_to_play = await client.fetch_channel(HOW_TO_PLAY_CHANNEL_ID)

        channel = await guild.create_text_channel(
            name="game-options",
            category=how_to_play.category,
            overwrites=how_to_play.overwrites,
            position=how_to_play.position + 1,
            reason="Add game-options reference channel",
        )

        await channel.send(GAMEPLAY_OPTIONS_MESSAGE_1)
        await channel.send(GAMEPLAY_OPTIONS_MESSAGE_2)
        await channel.send(QUESTION_OPTIONS_MESSAGE)

        print(f"✅ Created #{channel.name} ({ENVIRONMENT}): https://discord.com/channels/{GUILD_ID}/{channel.id}")
    finally:
        await client.close()


client.run(os.environ["discord_token"])
