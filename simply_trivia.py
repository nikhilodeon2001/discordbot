"""
Simply Trivia - Continuous trivia mode
Asks questions from trivia_questions collection continuously
Tracks first-to-answer and streaks
"""

import asyncio
import time
import discord
from datetime import datetime, timezone
import discordbot
import companion_web
from discordbot import update_audit_question, generate_scrambled_image, scramble_text

# Configuration
LEADERBOARD_UPDATE_FREQUENCY = 5  # Update leaderboards every N questions
QUESTION_DELAY_SECONDS = 5  # Delay between questions in seconds

# Storage for active game state
active_question = None
first_answer_time = None
first_answerer = None
additional_answerers = []
correct_answer_messages = {}  # user_id -> discord.Message, for users who answered correctly via a real Discord message
any_guess_received = False
question_message = None  # the Discord message the current question was sent as (see companion helpers below)

# Question tracking for /flag functionality (shared with discordbot.py)
simply_current_question = None
simply_previous_question = None

# --- Companion web app state (see companion_web.py + discordbot.py's companion hooks) ---
_companion_question_key = None      # time.time() float set at question-open; a change-detection key
_companion_current_revealed = True  # False while simply_current_question is open and unrevealed
_companion_answers = []             # [{"user_id","text","correct"}] -- every raw guess this question, Discord + web
_companion_correct_user_ids = set() # who got this question right (Discord + web)
_companion_web_user_ids = set()     # who answered via the companion app this question, for the 🌐 icon
_companion_flagged_user_ids = set() # one-flag-per-question guard, reset each question
_companion_last_streak = 0          # streak value at the last reveal, read by _companion_scoreboard()
_fuzzy_match_func = None            # captured once so companion callbacks (invoked outside the loop) can reach it


def get_current_question_for_flag():
    """
    Get current question in standard trivia format for /flag command

    Returns:
        Question dict with trivia_* keys, or None if no current question
    """
    if simply_current_question is None:
        return None
    return {
        "trivia_category": simply_current_question.get("category", ""),
        "trivia_question": simply_current_question.get("question", ""),
        "trivia_url": simply_current_question.get("url", ""),
        "trivia_answer_list": simply_current_question.get("answers", []),
        "trivia_db": simply_current_question.get("db", "trivia_questions"),
        "trivia_id": simply_current_question.get("_id"),
        "trivia_message_link": simply_current_question.get("trivia_message_link"),
    }


def get_previous_question_for_flag():
    """
    Get previous question in standard trivia format for /flag command

    Returns:
        Question dict with trivia_* keys, or None if no previous question
    """
    if simply_previous_question is None:
        return None
    return {
        "trivia_category": simply_previous_question.get("category", ""),
        "trivia_question": simply_previous_question.get("question", ""),
        "trivia_url": simply_previous_question.get("url", ""),
        "trivia_answer_list": simply_previous_question.get("answers", []),
        "trivia_db": simply_previous_question.get("db", "trivia_questions"),
        "trivia_id": simply_previous_question.get("_id"),
        "trivia_message_link": simply_previous_question.get("trivia_message_link"),
    }


def is_question_revealed(trivia_id):
    """True if trivia_id isn't Simply Trivia's current still-open question -- i.e. either it's
    an older (already-revealed) question, or the current one but already past reveal. Checked
    live by discordbot.py's get_flag_reveal_context() on every /flag page load, not baked into
    the link at question-post time."""
    if simply_current_question is None or str(simply_current_question.get("_id")) != str(trivia_id):
        return True
    return _companion_current_revealed


# Leaderboard tracking
questions_count = 0  # Counter for questions asked since bot started


async def get_trivia_question(db, collections=None):
    """
    Fetch random question from specified collection(s), avoiding recent repeats

    Args:
        db: MongoDB database instance
        collections: List of collection names to fetch from (defaults to ["trivia_questions"])

    Returns:
        Question document or None if no questions available
    """
    # Import from discordbot
    from discordbot import get_recent_question_ids_from_mongo
    import random

    # Default to trivia_questions if not specified
    if collections is None:
        collections = ["trivia_questions"]

    # Randomly select a collection from the list
    collection_name = random.choice(collections)

    # Map collection names to their question type for recent ID tracking
    collection_to_type = {
        "trivia_questions": "general",
        "jeopardy_questions": "jeopardy",
        "crossword_questions": "crossword"
    }
    question_type = collection_to_type.get(collection_name, "general")

    # Get recent IDs to avoid
    recent_ids = await get_recent_question_ids_from_mongo(question_type)

    # Fetch random question from selected collection
    pipeline = [
        {"$match": {"_id": {"$nin": list(recent_ids)}}},
        {"$sample": {"size": 1}}
    ]
    questions = await db[collection_name].aggregate(pipeline).to_list(1)

    if questions:
        questions[0]["db"] = collection_name  # Track which collection it came from
        return questions[0]
    return None


async def load_simply_previous_question(db):
    """
    Load previous question from MongoDB on startup

    Args:
        db: MongoDB database instance
    """
    global simply_previous_question

    try:
        # Retrieve previous question from MongoDB
        previous_question_retrieved = await db.previous_question_simply_trivia.find_one({"_id": "previous_question"})

        if previous_question_retrieved is not None:
            simply_previous_question = {
                "category": previous_question_retrieved.get("category"),
                "question": previous_question_retrieved.get("question"),
                "url": previous_question_retrieved.get("url"),
                "answers": previous_question_retrieved.get("answers"),
                "_id": previous_question_retrieved.get("question_id")
            }
        else:
            # If not found, set to None
            simply_previous_question = None

        print(f"📝 Loaded simply_trivia previous question from MongoDB")
    except Exception as e:
        print(f"❌ Error loading simply_trivia previous question: {e}")
        simply_previous_question = None


async def save_simply_previous_question(db):
    """
    Save previous question to MongoDB

    Args:
        db: MongoDB database instance
    """
    from discordbot import save_data_to_mongo

    try:
        if simply_previous_question:
            data = {
                "category": simply_previous_question.get("category"),
                "question": simply_previous_question.get("question"),
                "url": simply_previous_question.get("url"),
                "answers": simply_previous_question.get("answers"),
                "question_id": simply_previous_question.get("_id")
            }
            await save_data_to_mongo("previous_question_simply_trivia", "previous_question", data)
    except Exception as e:
        print(f"❌ Error saving simply_trivia previous question: {e}")


async def check_and_record_top_streak(db, user_id, user_name, streak_count):
    """
    Record a completed streak. get_longest_streaks/_24h/_7d each sort and limit
    at read time, so every streak is logged here regardless of size -- pruning at
    write time would silently drop streaks that fall below whatever the all-time
    high-water mark happens to be, making the 24h/7d "recent activity" views miss
    everyday streaks that never had a chance to compete against the all-time record.

    Args:
        db: MongoDB database instance
        user_id: Discord user ID
        user_name: Discord user display name
        streak_count: The streak count to record
    """
    if streak_count == 0:
        return  # Don't record zero streaks

    await db["simply_trivia_top_streaks"].insert_one({
        "user_id": user_id,
        "user_name": user_name,
        "streak_count": streak_count,
        "ended_at": datetime.now(timezone.utc)
    })


async def record_correct_answer(db, user_id, user_name, question_id):
    """
    Record a correct answer to the stats collection

    Args:
        db: MongoDB database instance
        user_id: Discord user ID
        user_name: Discord user display name
        question_id: Question ObjectId that was answered
    """
    collection = db["simply_trivia_stats"]

    await collection.insert_one({
        "user_id": user_id,
        "user_name": user_name,
        "timestamp": datetime.now(timezone.utc),
        "question_id": question_id
    })


class SimplyTriviaFlagReasonModal(discord.ui.Modal, title="Flag Question"):
    """Modal for collecting the reason for flagging a simply_trivia question"""

    reason = discord.ui.TextInput(
        label="Why are you flagging this question?",
        placeholder="Enter your reason here...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self, question, question_type, display_name, flag_message, embed_message):
        super().__init__()
        self.question = question
        self.question_type = question_type  # "current" or "previous"
        self.display_name = display_name
        self.flag_message = flag_message  # Original interaction/message (can be None for slash commands)
        self.embed_message = embed_message  # The embed message to delete after submission

    async def on_submit(self, interaction: discord.Interaction):
        from discordbot import update_audit_question

        try:
            reason_text = self.reason.value

            # Convert simply_trivia question format to audit format
            question_for_audit = {
                "trivia_category": self.question.get("category", ""),
                "trivia_question": self.question.get("question", ""),
                "trivia_url": self.question.get("url", ""),
                "trivia_answer_list": self.question.get("answers", []),
                "trivia_db": self.question.get("db", "trivia_questions"),
                "trivia_id": self.question.get("_id")
            }

            # Call update_audit_question with the selected question, reason, and message context
            await update_audit_question(
                question_for_audit,
                f"[SIMPLY_TRIVIA - {self.question_type.upper()}] {reason_text}",
                self.display_name,
                self.flag_message
            )

            # Delete the embed message after successful submission
            if self.embed_message:
                try:
                    await self.embed_message.delete()
                except:
                    pass  # Ignore if already deleted or can't delete

            await interaction.response.send_message(
                f"✅ Thank you! Your flag for the **{self.question_type}** question has been recorded.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error in SimplyTriviaFlagReasonModal submit: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while recording your flag.",
                ephemeral=True
            )


class SimplyTriviaFlagQuestionView(discord.ui.View):
    """View with buttons to select which question to flag"""

    def __init__(self, current_question, previous_question, user_id, display_name, flag_message):
        super().__init__(timeout=None)  # No timeout - buttons stay active until message is deleted
        self.current_question = current_question
        self.previous_question = previous_question
        self.user_id = user_id
        self.display_name = display_name
        self.flag_message = flag_message  # Original interaction/message (can be None for slash commands)
        self.embed_message = None  # Will be set after sending the embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user interacting is the one who initiated the flag"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Only the user who initiated the flag can use these buttons.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Current Question", style=discord.ButtonStyle.success, emoji="🚩")
    async def flag_current_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to flag the current question"""
        if self.current_question is None:
            await interaction.response.send_message(
                "❌ No current question available to flag.",
                ephemeral=True
            )
            return

        # Show the modal to collect reason
        modal = SimplyTriviaFlagReasonModal(self.current_question, "current", self.display_name, self.flag_message, self.embed_message)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Previous Question", style=discord.ButtonStyle.danger, emoji="⏮️")
    async def flag_previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to flag the previous question"""
        if self.previous_question is None:
            await interaction.response.send_message(
                "❌ No previous question available to flag.",
                ephemeral=True
            )
            return

        # Show the modal to collect reason
        modal = SimplyTriviaFlagReasonModal(self.previous_question, "previous", self.display_name, self.flag_message, self.embed_message)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Button to cancel and close the embed"""
        # Delete the message
        try:
            await interaction.message.delete()
            await interaction.response.send_message(
                "✅ Flag action cancelled.",
                ephemeral=True,
                delete_after=3
            )
        except:
            await interaction.response.send_message(
                "✅ Cancelled.",
                ephemeral=True,
                delete_after=3
            )


# --- Companion web app hooks (see companion_web.py + discordbot.py's build_companion_state and
# friends, which these mirror for Simply Trivia's simpler, round-less, timer-less, streak-based
# game model) ---

def _companion_image_url(url, message):
    """Reuses discordbot's image-resolution logic (handles bot-generated attachments like
    scramble images), passing our own sent message instead of the main game's."""
    return discordbot._companion_image_url(url, message)


def _companion_question_text(q):
    text = q.get("question", "")
    if q.get("url", "").startswith("jeopardy"):
        text = discordbot.jeopardy_html_to_discord(text)
    return text


def build_companion_state(user_id=None):
    """Sanitized live-question state for the companion. No round/modes/timer concepts exist in
    Simply Trivia, so those fields are always empty/absent."""
    if active_question is None:
        return {"phase": "idle"}
    q = active_question
    url = q.get("url", "")
    category = q.get("category", "Trivia")
    answers = q.get("answers", []) or []
    image_url = _companion_image_url(url, question_message)
    question_text = _companion_question_text(q)
    display_question = discordbot._companion_display_question(url, category, question_text, answers, image_url)
    state = {
        "phase": "open",
        "question_key": _companion_question_key,
        "category": category,
        "question": display_question,
        "image_url": image_url,
        "is_multiple_choice": False,
        "choices": [],
        "puzzle_text": None,
        "warning": None,
        "modes": [],
        "round_overview": [],
        "question_number": 0,
    }
    if user_id is not None:
        mine = [a["text"] for a in _companion_answers if a["user_id"] == user_id]
        if mine:
            state["my_answer"] = mine[-1]
        # Free-text, always resubmittable -- Simply Trivia has no one-guess/multiple-choice lock.
        state["already_answered"] = False
    return state


def _companion_scoreboard():
    """Simply Trivia has no points/round scoreboard -- just who got THIS question right, mirroring
    the same {rank, name, score, delta, lightning, via_companion} row shape the companion's
    scoreboardHtml() renders, so the 🌐 app-answer icon still works unchanged."""
    rows = []
    if first_answerer:
        rows.append({
            "rank": "🥇",
            "name": first_answerer.display_name,
            "score": f"🔥 {_companion_last_streak}" if _companion_last_streak > 1 else "",
            "delta": "",
            "lightning": 0,
            "via_companion": first_answerer.id in _companion_web_user_ids,
        })
    for user in additional_answerers:
        rows.append({
            "rank": "✅",
            "name": user.display_name,
            "score": "",
            "delta": "",
            "lightning": 0,
            "via_companion": user.id in _companion_web_user_ids,
        })
    return rows


def build_companion_reveal_state(main_answer):
    """State pushed to phones at the reveal transition."""
    q = active_question or {}
    url = q.get("url", "")
    category = q.get("category", "Trivia")
    answers = q.get("answers", []) or []
    image_url = _companion_image_url(url, question_message)
    return {
        "phase": "revealed",
        "question_key": _companion_question_key,
        "category": category,
        "question": discordbot._companion_display_question(
            url, category, _companion_question_text(q), answers, image_url),
        "image_url": image_url,
        "correct_answer": main_answer,
        "blind": False,
        "scoreboard": _companion_scoreboard(),
        "modes": [],
        "round_overview": [],
        "question_number": 0,
    }


def companion_reveal_extra(user_id):
    """Per-connection reveal personalization: every answer this user submitted this question, and
    whether they got it right (None if they didn't answer)."""
    mine = [a["text"] for a in _companion_answers if a["user_id"] == user_id]
    if not mine:
        return {"my_answers": [], "result": None}
    return {
        "my_answers": mine,
        "result": "correct" if user_id in _companion_correct_user_ids else "incorrect",
    }


def companion_submit_answer(user_id, display_name, text):
    """Inject a phone answer into the same first-to-answer tracking a Discord-typed guess uses."""
    if active_question is None:
        return {"ok": False, "reason": "closed"}
    _companion_web_user_ids.add(user_id)
    _record_guess(_CompanionUser(user_id, display_name), text, _fuzzy_match_func)
    return {"ok": True}


async def companion_submit_flag(user_id, display_name, reasons, detail):
    """Flag whatever `active_question` currently is -- never a client-supplied id. Reuses the same
    shared moderation pipeline and abuse-rate-limit budget the main game's companion flag uses
    (discordbot.py's _get_flag_lock/_count_flags_last_24h/MAX_FLAGS_PER_24H/db.companion_flags),
    tagged with the same [SIMPLY_TRIVIA - CURRENT] prefix the existing Discord-side flag modal
    uses, and source="Web" for attribution."""
    if active_question is None:
        return {"ok": False, "reason": "no_question"}
    if user_id in _companion_flagged_user_ids:
        return {"ok": False, "reason": "already_flagged"}
    async with discordbot._get_flag_lock(user_id):
        if await discordbot._count_flags_last_24h(user_id) >= discordbot.MAX_FLAGS_PER_24H:
            return {"ok": False, "reason": "rate_limited"}
        await discordbot.db.companion_flags.insert_one({"user_id": user_id, "timestamp": datetime.now(timezone.utc)})
    _companion_flagged_user_ids.add(user_id)
    reasons_text = ", ".join(discordbot.FlagReasonModal.REASON_LABELS.get(r, r) for r in reasons)
    reason_text = f"[SIMPLY_TRIVIA - CURRENT] ({reasons_text}) {detail}".strip()
    question_for_audit = get_current_question_for_flag()
    await update_audit_question(question_for_audit, reason_text, display_name, None, user_id=user_id, source="Web")
    return {"ok": True}


class _CompanionUser:
    """Lightweight stand-in for a discord.Member, so a companion (web) answerer can be tracked by
    the same first_answerer/additional_answerers logic and reveal-embed .mention usage as a real
    Discord message author. Never appears in a real Discord message, so it simply won't match
    anything in the channel.history() reaction-scanning loop at reveal time -- expected, not an
    error."""

    def __init__(self, user_id, display_name):
        self.id = user_id
        self.display_name = display_name

    @property
    def mention(self):
        return f"<@{self.id}>"


def _record_guess(user, text, fuzzy_match_func, message=None):
    """Check `text` against active_question's answers; track first/additional correct answerers
    (shared by the Discord on_message path and the companion web-answer path) and every raw guess
    (so the companion can show "my answers" and correct/incorrect on reveal). `message` is the
    real discord.Message for a Discord-typed guess (None for companion/web answers, which have no
    Discord message to react to) and is stashed in correct_answer_messages so reveal-time reactions
    don't need to re-scan channel history. Returns True if the guess matched."""
    global first_answerer, first_answer_time, additional_answerers, any_guess_received

    any_guess_received = True
    matched = False

    for correct_answer in active_question["answers"]:
        if fuzzy_match_func(
            text,
            correct_answer,
            active_question.get("category", ""),
            active_question.get("url", ""),
            ignore_exact_mode=True
        ):
            matched = True
            current_time = asyncio.get_event_loop().time()

            # First correct answer
            if first_answerer is None:
                first_answerer = user
                first_answer_time = current_time
                if message is not None:
                    correct_answer_messages[user.id] = message
                # Don't react yet - wait until 3s window closes

            # Additional correct answers within 3 seconds
            elif (current_time - first_answer_time) <= 3.0:
                if user.id != first_answerer.id:
                    # Avoid duplicates -- compare by id, not object identity: a companion (web)
                    # answerer is a fresh _CompanionUser instance on every submit, unlike a
                    # discord.Member, which discord.py reuses for the same user.
                    if not any(u.id == user.id for u in additional_answerers):
                        additional_answerers.append(user)
                        if message is not None:
                            correct_answer_messages[user.id] = message
                        # Don't react yet - wait until 3s window closes

            break  # Found a match, stop checking other answers

    _companion_answers.append({"user_id": user.id, "text": text, "correct": matched})
    if matched:
        _companion_correct_user_ids.add(user.id)
    return matched


async def handle_answer(message, bot, db, fuzzy_match_func):
    """
    Handle incoming answers in Simply Trivia channel
    Called from discordbot.py on_message event

    Args:
        message: Discord message object
        bot: Discord bot instance
        db: MongoDB database instance
        fuzzy_match_func: Reference to fuzzy_match function from discordbot
    """
    # Ignore if no active question or message is from bot
    if not active_question or message.author.bot:
        return

    _record_guess(message.author, message.content, fuzzy_match_func, message=message)


async def start_simply_trivia(bot, db, channel_id, fuzzy_match_func):
    """
    Main loop for Simply Trivia mode
    Continuously asks trivia questions and tracks first-to-answer streaks

    Args:
        bot: Discord bot instance
        db: MongoDB database instance
        channel_id: SIMPLY_TRIVIA_CHANNEL_ID
        fuzzy_match_func: Reference to fuzzy_match function from discordbot
    """
    from discordbot import store_question_ids_in_mongo

    channel = bot.get_channel(channel_id)

    if not channel:
        print(f"❌ Simply Trivia channel {channel_id} not found!")
        return

    print(f"🎯 Simply Trivia started in channel: {channel.name}")

    global _fuzzy_match_func
    _fuzzy_match_func = fuzzy_match_func

    # Load previous question from MongoDB on startup
    await load_simply_previous_question(db)

    while True:
        try:
            # Check if bot is shutting down for update
            if discordbot.shutdown_initiated:
                print("🔄 Simply Trivia stopping - update detected")
                break

            # Get next question
            question = await get_trivia_question(db)
            if not question:
                print("⚠️ No questions available, waiting 10 seconds...")
                await asyncio.sleep(10)
                continue

            # Move current question to previous before setting new question
            global active_question, first_answerer, first_answer_time, additional_answerers, any_guess_received
            global simply_current_question, simply_previous_question, question_message
            global _companion_question_key, _companion_last_streak, _companion_current_revealed

            if simply_current_question is not None:
                simply_previous_question = simply_current_question.copy()
                await save_simply_previous_question(db)

            # Set up tracking for this question
            active_question = question
            simply_current_question = question.copy()
            first_answerer = None
            first_answer_time = None
            additional_answerers = []
            correct_answer_messages.clear()
            any_guess_received = False
            await discordbot.record_question_asked(question.get("db"), question.get("_id"))

            # Build question embed
            category = question.get("category", "Trivia")
            question_text = question.get("question", "")
            url = question.get("url", "")
            if url.startswith("jeopardy"):
                question_text = discordbot.jeopardy_html_to_discord(question_text)
            answers = question.get("answers", [])
            main_answer = answers[0] if answers else "Unknown"

            # The token never carries the answer -- whether it's safe to show is checked live
            # (discordbot.py's get_flag_reveal_context / simply_trivia.is_question_revealed) every
            # time the /flag page loads, not decided once here at question-post time.
            flag_token = companion_web.make_flag_token(question.get("db", "trivia_questions"), question.get("_id"), category, question_text)
            flag_url = f"{companion_web.get_base_url()}/flag?t={flag_token}"

            embed = discord.Embed(
                description=f"[**{category}**]({flag_url})\n\n{question_text}",
                color=discord.Color(0x146DE8)
            )

            # Handle special URL types
            if url == "scramble":
                # Generate scrambled image
                image_buffer, scrambled_word = generate_scrambled_image(scramble_text(answers[0]))
                file = discord.File(fp=image_buffer, filename="scramble.png")
                embed.set_image(url="attachment://scramble.png")
                question_message = await channel.send(embed=embed, file=file)
            elif url and url.startswith("http"):
                # Regular image URL
                embed.set_image(url=url)
                question_message = await channel.send(embed=embed)
            else:
                # No image
                question_message = await channel.send(embed=embed)
            simply_current_question["trivia_message_link"] = question_message.jump_url

            _companion_question_key = time.time()
            _companion_current_revealed = False
            _companion_answers.clear()
            _companion_correct_user_ids.clear()
            _companion_web_user_ids.clear()
            _companion_flagged_user_ids.clear()
            try:
                companion_web.publish_state(build_companion_state(), game="simply")
            except Exception as e:
                print(f"companion publish (simply, open) failed: {e}")

            print(f"📝 Asked: {category} - {question_text}")
            print(f"📝 Answer: {answers}")

            # Wait for answers - up to 20 seconds, or 3 seconds after first correct answer
            max_wait_time = 20.0
            start_time = asyncio.get_event_loop().time()
            answer_revealed = False

            while not answer_revealed:
                # Check for shutdown during answer wait
                if discordbot.shutdown_initiated:
                    print("🔄 Simply Trivia stopping - update detected during answer wait")
                    return  # Exit the entire function/loop

                await asyncio.sleep(0.1)  # Check every 0.1 seconds
                current_time = asyncio.get_event_loop().time()
                elapsed = current_time - start_time

                if first_answerer:
                    # Someone got it! Wait 3 more seconds from when they answered
                    time_since_first_answer = current_time - first_answer_time
                    if time_since_first_answer >= 3.0:
                        answer_revealed = True
                elif elapsed >= max_wait_time:
                    # 20 seconds elapsed with no correct answer
                    answer_revealed = True

            # Reveal answer
            answers = question.get("answers", [])
            main_answer = answers[0] if answers else "Unknown"
            _companion_current_revealed = True

            if first_answerer:
                # React to everyone who got it right (first + additional), in the order they
                # answered. Their messages were captured directly at guess-time, so this is a
                # plain lookup -- no re-scanning channel history or re-running fuzzy match.
                users_to_react = [first_answerer] + additional_answerers
                for user in users_to_react:
                    msg = correct_answer_messages.get(user.id)
                    if msg is None:
                        continue
                    try:
                        await msg.add_reaction("✅")
                    except Exception as e:
                        print(f"❌ Failed to react to {user.id}'s answer: {e}")

                # Someone got it - update first answerer's streak
                # Get current streak document (single document with _id="current")
                current = await db["simply_trivia_streaks"].find_one({"_id": "current"})

                if current and current.get("user_id") == first_answerer.id:
                    # Same person - increment streak
                    new_streak = current.get("streak", 0) + 1
                else:
                    # Different person - start new streak at 1
                    new_streak = 1
                    # Also check and record previous person's streak if it ended
                    if current and current.get("streak", 0) > 0:
                        await check_and_record_top_streak(
                            db,
                            current["user_id"],
                            current["user_name"],
                            current["streak"]
                        )

                # Update/insert the single document
                await db["simply_trivia_streaks"].update_one(
                    {"_id": "current"},
                    {"$set": {
                        "user_id": first_answerer.id,
                        "user_name": first_answerer.display_name,
                        "streak": new_streak,
                        "updated_at": datetime.now(timezone.utc)
                    }},
                    upsert=True
                )
                streak = new_streak
                _companion_last_streak = streak

                # Record correct answer for stats
                await record_correct_answer(
                    db,
                    first_answerer.id,
                    first_answerer.display_name,
                    question.get("_id")
                )

                await discordbot.record_question_outcome(question.get("db"), question.get("_id"), True, any_guess_received)

                def _mention_with_indicator(user):
                    tag = " 🌐" if user.id in _companion_web_user_ids else ""
                    return f"{user.mention}{tag}"

                answer_text = f"[**Answer:**]({flag_url}) {main_answer}\n\n"
                if streak > 1:
                    answer_text += f"🏆 {_mention_with_indicator(first_answerer)} got it first! 🔥 Streak: {streak}"
                else:
                    answer_text += f"🏆 {_mention_with_indicator(first_answerer)} got it first!"

                # Add additional answerers if any
                if additional_answerers:
                    also_got = ", ".join(_mention_with_indicator(user) for user in additional_answerers)
                    answer_text += f"\n✅ Also got it: {also_got}"

                embed = discord.Embed(description=answer_text, color=discord.Color.green())
            else:
                # No one got it - check and record streak before resetting
                try:
                    # Get current streak holder (single document with _id="current")
                    current = await db["simply_trivia_streaks"].find_one({"_id": "current"})

                    # Check if qualifies for top 100
                    if current and current.get("streak", 0) > 0:
                        await check_and_record_top_streak(
                            db,
                            current["user_id"],
                            current["user_name"],
                            current["streak"]
                        )

                    # Reset to no holder
                    await db["simply_trivia_streaks"].update_one(
                        {"_id": "current"},
                        {"$set": {
                            "user_id": None,
                            "user_name": None,
                            "streak": 0,
                            "updated_at": datetime.now(timezone.utc)
                        }},
                        upsert=True
                    )
                except Exception as e:
                    print(f"❌ Failed to reset streaks: {e}")

                _companion_last_streak = 0

                await discordbot.record_question_outcome(question.get("db"), question.get("_id"), False, any_guess_received)

                answer_text = f"[**Answer:**]({flag_url}) {main_answer}"
                embed = discord.Embed(description=answer_text, color=discord.Color.red())

            await channel.send(embed=embed)

            try:
                companion_web.publish_state(build_companion_reveal_state(main_answer), game="simply")
            except Exception as e:
                print(f"companion publish (simply, reveal) failed: {e}")

            # Store question ID to avoid repeating
            if question.get("_id"):
                await store_question_ids_in_mongo([question["_id"]], "general")

            # Increment question counter and check if leaderboard update needed
            global questions_count
            questions_count += 1
            if questions_count % LEADERBOARD_UPDATE_FREQUENCY == 0:
                await update_leaderboards(bot, db)

            # Clear active question
            active_question = None

            # Wait before asking next question
            await asyncio.sleep(QUESTION_DELAY_SECONDS)

        except Exception as e:
            print(f"❌ Error in Simply Trivia loop: {e}")
            import traceback
            traceback.print_exc()
            # Wait before retrying
            await asyncio.sleep(5)


# Statistics query functions

async def get_longest_streaks(db, limit=100):
    """
    Get the top longest streaks ever recorded

    Args:
        db: MongoDB database instance
        limit: Number of results to return (default 100)

    Returns:
        List of dicts with user_id, user_name, streak_count, ended_at
    """
    collection = db["simply_trivia_top_streaks"]

    # Sort by streak_count descending, limit to requested amount
    results = await collection.find().sort("streak_count", -1).limit(limit).to_list(limit)

    return results


async def get_longest_streaks_24h(db, limit=25):
    """
    Get the top longest streaks that ended in the last 24 hours

    Args:
        db: MongoDB database instance
        limit: Number of results to return (default 25)

    Returns:
        List of dicts with user_id, user_name, streak_count, ended_at
    """
    from datetime import timedelta

    collection = db["simply_trivia_top_streaks"]

    # Calculate 24 hours ago
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=24)

    # Filter by time, sort by streak_count descending
    results = await collection.find(
        {"ended_at": {"$gte": time_threshold}}
    ).sort("streak_count", -1).limit(limit).to_list(limit)

    return results


async def get_longest_streaks_7d(db, limit=25):
    """
    Get the top longest streaks that ended in the last 7 days

    Args:
        db: MongoDB database instance
        limit: Number of results to return (default 25)

    Returns:
        List of dicts with user_id, user_name, streak_count, ended_at
    """
    from datetime import timedelta

    collection = db["simply_trivia_top_streaks"]

    # Calculate 7 days ago
    time_threshold = datetime.now(timezone.utc) - timedelta(days=7)

    # Filter by time, sort by streak_count descending
    results = await collection.find(
        {"ended_at": {"$gte": time_threshold}}
    ).sort("streak_count", -1).limit(limit).to_list(limit)

    return results


async def get_top_users_alltime(db, limit=100):
    """
    Get top users by total correct answers (all time)

    Args:
        db: MongoDB database instance
        limit: Number of results to return (default 100)

    Returns:
        List of dicts with user_id, user_name, total_correct
    """
    collection = db["simply_trivia_stats"]

    # Aggregate: group by user, count answers, sort descending
    pipeline = [
        {
            "$group": {
                "_id": "$user_id",
                "user_name": {"$first": "$user_name"},
                "total_correct": {"$sum": 1}
            }
        },
        {"$sort": {"total_correct": -1}},
        {"$limit": limit}
    ]

    results = await collection.aggregate(pipeline).to_list(limit)

    return results


async def get_top_users_24h(db, limit=100):
    """
    Get top users by correct answers in last 24 hours

    Args:
        db: MongoDB database instance
        limit: Number of results to return (default 100)

    Returns:
        List of dicts with user_id, user_name, total_correct
    """
    from datetime import timedelta

    collection = db["simply_trivia_stats"]

    # Calculate 24 hours ago
    time_threshold = datetime.now(timezone.utc) - timedelta(hours=24)

    # Aggregate: filter by time, group by user, count, sort
    pipeline = [
        {"$match": {"timestamp": {"$gte": time_threshold}}},
        {
            "$group": {
                "_id": "$user_id",
                "user_name": {"$first": "$user_name"},
                "total_correct": {"$sum": 1}
            }
        },
        {"$sort": {"total_correct": -1}},
        {"$limit": limit}
    ]

    results = await collection.aggregate(pipeline).to_list(limit)

    return results


async def get_top_users_7d(db, limit=100):
    """
    Get top users by correct answers in last 7 days

    Args:
        db: MongoDB database instance
        limit: Number of results to return (default 100)

    Returns:
        List of dicts with user_id, user_name, total_correct
    """
    from datetime import timedelta

    collection = db["simply_trivia_stats"]

    # Calculate 7 days ago
    time_threshold = datetime.now(timezone.utc) - timedelta(days=7)

    # Aggregate: filter by time, group by user, count, sort
    pipeline = [
        {"$match": {"timestamp": {"$gte": time_threshold}}},
        {
            "$group": {
                "_id": "$user_id",
                "user_name": {"$first": "$user_name"},
                "total_correct": {"$sum": 1}
            }
        },
        {"$sort": {"total_correct": -1}},
        {"$limit": limit}
    ]

    results = await collection.aggregate(pipeline).to_list(limit)

    return results


# Leaderboard formatting functions

def create_streaks_alltime_embed(all_time):
    """
    Create Discord embed for all-time longest streaks

    Args:
        all_time: List of top streaks all time

    Returns:
        Discord embed for all-time streaks
    """
    embed = discord.Embed(
        title="🏆 Longest Streaks - ALL TIME",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    medals = ["🥇", "🥈", "🥉"]

    description = ""
    for i, entry in enumerate(all_time[:25], 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        user_name = entry.get("user_name", "Unknown")
        streak = entry.get("streak_count", 0)
        description += f"{medal} **{user_name}** - {streak}\n"

    if not description:
        description = "*No streaks recorded yet*"

    embed.description = description
    embed.set_footer(text=f"Updates every {LEADERBOARD_UPDATE_FREQUENCY} questions")

    return embed


def create_streaks_24h_embed(past_24h):
    """
    Create Discord embed for 24-hour longest streaks

    Args:
        past_24h: List of top streaks in last 24 hours

    Returns:
        Discord embed for 24-hour streaks
    """
    embed = discord.Embed(
        title="⏰ Longest Streaks - PAST 24 HOURS",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    medals = ["🥇", "🥈", "🥉"]

    description = ""
    for i, entry in enumerate(past_24h[:25], 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        user_name = entry.get("user_name", "Unknown")
        streak = entry.get("streak_count", 0)
        description += f"{medal} **{user_name}** - {streak}\n"

    if not description:
        description = "*No streaks in the last 24 hours*"

    embed.description = description
    embed.set_footer(text=f"Updates every {LEADERBOARD_UPDATE_FREQUENCY} questions")

    return embed


def create_streaks_7d_embed(past_7d):
    """
    Create Discord embed for 7-day longest streaks

    Args:
        past_7d: List of top streaks in last 7 days

    Returns:
        Discord embed for 7-day streaks
    """
    embed = discord.Embed(
        title="📅 Longest Streaks - PAST 7 DAYS",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    medals = ["🥇", "🥈", "🥉"]

    description = ""
    for i, entry in enumerate(past_7d[:25], 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        user_name = entry.get("user_name", "Unknown")
        streak = entry.get("streak_count", 0)
        description += f"{medal} **{user_name}** - {streak}\n"

    if not description:
        description = "*No streaks in the last 7 days*"

    embed.description = description
    embed.set_footer(text=f"Updates every {LEADERBOARD_UPDATE_FREQUENCY} questions")

    return embed


def create_answers_alltime_embed(all_time):
    """
    Create Discord embed for all-time most correct answers

    Args:
        all_time: List of top users by answers all time

    Returns:
        Discord embed for all-time answers
    """
    embed = discord.Embed(
        title="🏆 Most Correct Answers - ALL TIME",
        color=discord.Color(0x146DE8),
        timestamp=datetime.now(timezone.utc)
    )

    medals = ["🥇", "🥈", "🥉"]

    description = ""
    for i, entry in enumerate(all_time[:25], 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        user_name = entry.get("user_name", "Unknown")
        total = entry.get("total_correct", 0)
        description += f"{medal} **{user_name}** - {total}\n"

    if not description:
        description = "*No answers recorded yet*"

    embed.description = description
    embed.set_footer(text=f"Updates every {LEADERBOARD_UPDATE_FREQUENCY} questions")

    return embed


def create_answers_24h_embed(past_24h):
    """
    Create Discord embed for 24-hour most correct answers

    Args:
        past_24h: List of top users by answers in last 24 hours

    Returns:
        Discord embed for 24-hour answers
    """
    embed = discord.Embed(
        title="⏰ Most Correct Answers - PAST 24 HOURS",
        color=discord.Color(0x146DE8),
        timestamp=datetime.now(timezone.utc)
    )

    medals = ["🥇", "🥈", "🥉"]

    description = ""
    for i, entry in enumerate(past_24h[:25], 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        user_name = entry.get("user_name", "Unknown")
        total = entry.get("total_correct", 0)
        description += f"{medal} **{user_name}** - {total}\n"

    if not description:
        description = "*No answers in the last 24 hours*"

    embed.description = description
    embed.set_footer(text=f"Updates every {LEADERBOARD_UPDATE_FREQUENCY} questions")

    return embed


def create_answers_7d_embed(past_7d):
    """
    Create Discord embed for 7-day most correct answers

    Args:
        past_7d: List of top users by answers in last 7 days

    Returns:
        Discord embed for 7-day answers
    """
    embed = discord.Embed(
        title="📅 Most Correct Answers - PAST 7 DAYS",
        color=discord.Color(0x146DE8),
        timestamp=datetime.now(timezone.utc)
    )

    medals = ["🥇", "🥈", "🥉"]

    description = ""
    for i, entry in enumerate(past_7d[:25], 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        user_name = entry.get("user_name", "Unknown")
        total = entry.get("total_correct", 0)
        description += f"{medal} **{user_name}** - {total}\n"

    if not description:
        description = "*No answers in the last 7 days*"

    embed.description = description
    embed.set_footer(text=f"Updates every {LEADERBOARD_UPDATE_FREQUENCY} questions")

    return embed


async def update_leaderboards(bot, db):
    """
    Update both leaderboards (streaks and answers) in their respective channels
    Posts 3 separate messages per channel (ALL TIME, PAST 24H, PAST 7D)

    Args:
        bot: Discord bot instance
        db: MongoDB database instance
    """
    from discordbot import SIMPLY_STREAKS_CHANNEL_ID, SIMPLY_ANSWERS_CHANNEL_ID

    try:
        # Fetch all data for streaks
        streaks_all_time = await get_longest_streaks(db, limit=25)
        streaks_24h = await get_longest_streaks_24h(db, limit=25)
        streaks_7d = await get_longest_streaks_7d(db, limit=25)

        # Fetch all data for answers
        answers_all_time = await get_top_users_alltime(db, limit=25)
        answers_24h = await get_top_users_24h(db, limit=25)
        answers_7d = await get_top_users_7d(db, limit=25)

        # Create embeds for streaks
        streaks_embeds = [
            create_streaks_alltime_embed(streaks_all_time),
            create_streaks_24h_embed(streaks_24h),
            create_streaks_7d_embed(streaks_7d)
        ]

        # Create embeds for answers
        answers_embeds = [
            create_answers_alltime_embed(answers_all_time),
            create_answers_24h_embed(answers_24h),
            create_answers_7d_embed(answers_7d)
        ]

        # Update streaks channel
        streaks_channel = bot.get_channel(SIMPLY_STREAKS_CHANNEL_ID)
        if streaks_channel:
            try:
                # Get last 3 messages in channel
                messages = []
                async for msg in streaks_channel.history(limit=3):
                    messages.insert(0, msg)  # Insert at beginning to reverse order

                # Check if all 3 messages are from bot
                if len(messages) == 3 and all(m.author == bot.user for m in messages):
                    # Edit existing messages in order
                    await messages[0].edit(embed=streaks_embeds[0])
                    await messages[1].edit(embed=streaks_embeds[1])
                    await messages[2].edit(embed=streaks_embeds[2])
                else:
                    # Post 3 new messages in order
                    await streaks_channel.send(embed=streaks_embeds[0])
                    await streaks_channel.send(embed=streaks_embeds[1])
                    await streaks_channel.send(embed=streaks_embeds[2])
            except Exception as e:
                print(f"❌ Failed to update streaks leaderboard: {e}")
        else:
            print(f"⚠️ Streaks channel {SIMPLY_STREAKS_CHANNEL_ID} not found")

        # Update answers channel
        answers_channel = bot.get_channel(SIMPLY_ANSWERS_CHANNEL_ID)
        if answers_channel:
            try:
                # Get last 3 messages in channel
                messages = []
                async for msg in answers_channel.history(limit=3):
                    messages.insert(0, msg)  # Insert at beginning to reverse order

                # Check if all 3 messages are from bot
                if len(messages) == 3 and all(m.author == bot.user for m in messages):
                    # Edit existing messages in order
                    await messages[0].edit(embed=answers_embeds[0])
                    await messages[1].edit(embed=answers_embeds[1])
                    await messages[2].edit(embed=answers_embeds[2])
                else:
                    # Post 3 new messages in order
                    await answers_channel.send(embed=answers_embeds[0])
                    await answers_channel.send(embed=answers_embeds[1])
                    await answers_channel.send(embed=answers_embeds[2])
            except Exception as e:
                print(f"❌ Failed to update answers leaderboard: {e}")
        else:
            print(f"⚠️ Answers channel {SIMPLY_ANSWERS_CHANNEL_ID} not found")

    except Exception as e:
        print(f"❌ Error updating leaderboards: {e}")
        import traceback
        traceback.print_exc()
