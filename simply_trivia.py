"""
Simply Trivia - Continuous trivia mode
Asks questions from trivia_questions collection continuously
Tracks first-to-answer and streaks
"""

import asyncio
import discord
from datetime import datetime, timezone
from discordbot import update_audit_question

# Configuration
LEADERBOARD_UPDATE_FREQUENCY = 5  # Update leaderboards every N questions
QUESTION_DELAY_SECONDS = 5  # Delay between questions in seconds

# Storage for active game state
active_question = None
first_answer_time = None
first_answerer = None
additional_answerers = []

# Question tracking for #flag functionality (separate from discordbot.py)
simply_current_question = None
simply_previous_question = None

# Leaderboard tracking
questions_count = 0  # Counter for questions asked since bot started


async def get_trivia_question(db):
    """
    Fetch random question from trivia_questions, avoiding recent repeats

    Args:
        db: MongoDB database instance

    Returns:
        Question document or None if no questions available
    """
    # Import from discordbot
    from discordbot import get_recent_question_ids_from_mongo

    # Get recent IDs to avoid
    recent_ids = await get_recent_question_ids_from_mongo("general")

    # Fetch random question from trivia_questions collection
    pipeline = [
        {"$match": {"_id": {"$nin": list(recent_ids)}}},
        {"$sample": {"size": 1}}
    ]
    questions = await db["trivia_questions"].aggregate(pipeline).to_list(1)

    if questions:
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
    Check if a streak qualifies for top 100 and record it if so

    Args:
        db: MongoDB database instance
        user_id: Discord user ID
        user_name: Discord user display name
        streak_count: The streak count to check
    """
    if streak_count == 0:
        return  # Don't record zero streaks

    collection = db["simply_trivia_top_streaks"]

    # Get current count of top streaks
    count = await collection.count_documents({})

    if count < 100:
        # Less than 100 entries, always add
        await collection.insert_one({
            "user_id": user_id,
            "user_name": user_name,
            "streak_count": streak_count,
            "ended_at": datetime.now(timezone.utc)
        })
    else:
        # Find the 100th place streak (smallest in top 100)
        top_100 = await collection.find().sort("streak_count", 1).limit(1).to_list(1)

        if top_100 and streak_count > top_100[0]["streak_count"]:
            # This streak is better than 100th place
            # Insert new record
            await collection.insert_one({
                "user_id": user_id,
                "user_name": user_name,
                "streak_count": streak_count,
                "ended_at": datetime.now(timezone.utc)
            })

            # Remove the now-101st entry (the old 100th place)
            await collection.delete_one({"_id": top_100[0]["_id"]})


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
        self.flag_message = flag_message  # Original message where #flag was typed
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
                "trivia_db": "trivia_questions",
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
        self.flag_message = flag_message  # Original message where #flag was typed
        self.embed_message = None  # Will be set after sending the embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user interacting is the one who typed #flag"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Only the user who typed #flag can use these buttons.",
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
    global active_question, first_answer_time, first_answerer, additional_answerers

    # Ignore if no active question or message is from bot
    if not active_question or message.author.bot:
        return

    # Handle #flag command for reporting questions
    if "#flag" in message.content.strip().lower():
        try:
            await message.add_reaction("🚩")
        except Exception as e:
            print(f"❌ Failed to react with flag emoji: {e}")

        # Build embed showing both current and previous questions
        embed = discord.Embed(
            title="🚩 Which question do you want to flag?",
            description="Select the question you want to flag and provide a reason.",
            color=discord.Color.red()
        )

        # Add current question info
        if simply_current_question:
            current_answer = simply_current_question.get("answers", ["N/A"])
            if isinstance(current_answer, list):
                current_answer = ", ".join(str(a) for a in current_answer)
            embed.add_field(
                name="🟢 CURRENT QUESTION",
                value=f"**Category:** {simply_current_question.get('category', 'N/A')}\n"
                      f"**Question:** {simply_current_question.get('question', 'N/A')}\n"
                      f"**Answer:** {current_answer}",
                inline=False
            )
        else:
            embed.add_field(
                name="🟢 CURRENT QUESTION",
                value="*No current question available*",
                inline=False
            )

        # Add previous question info
        if simply_previous_question:
            previous_answer = simply_previous_question.get("answers", ["N/A"])
            if isinstance(previous_answer, list):
                previous_answer = ", ".join(str(a) for a in previous_answer)
            embed.add_field(
                name="🔴 PREVIOUS QUESTION",
                value=f"**Category:** {simply_previous_question.get('category', 'N/A')}\n"
                      f"**Question:** {simply_previous_question.get('question', 'N/A')}\n"
                      f"**Answer:** {previous_answer}",
                inline=False
            )
        else:
            embed.add_field(
                name="🔴 PREVIOUS QUESTION",
                value="*No previous question available*",
                inline=False
            )

        # Create view with buttons
        view = SimplyTriviaFlagQuestionView(
            current_question=simply_current_question,
            previous_question=simply_previous_question,
            user_id=message.author.id,
            display_name=message.author.display_name,
            flag_message=message
        )

        # Send message with embed and view (visible for 30 seconds)
        try:
            embed_message = await message.channel.send(
                content=f"{message.author.mention}",
                embed=embed,
                view=view,
                delete_after=30  # Auto-delete after 30 seconds
            )
            # Store the embed message reference in the view so modals can delete it
            view.embed_message = embed_message
        except Exception as e:
            print(f"❌ Error sending flag embed: {e}")
            # Fallback to old behavior if embed fails
            if active_question:
                question_data = {
                    "trivia_db": "trivia_questions",
                    "trivia_id": active_question.get("_id")
                }
                await update_audit_question(question_data, message.content.strip(), message.author.display_name)

        return

    # Check if answer is correct against any valid answer
    for correct_answer in active_question["answers"]:
        if fuzzy_match_func(
            message.content,
            correct_answer,
            active_question.get("category", ""),
            active_question.get("url", ""),
            ignore_exact_mode=True
        ):
            current_time = asyncio.get_event_loop().time()

            # First correct answer
            if first_answerer is None:
                first_answerer = message.author
                first_answer_time = current_time
                # Don't react yet - wait until 3s window closes

            # Additional correct answers within 3 seconds
            elif (current_time - first_answer_time) <= 3.0:
                if message.author.id != first_answerer.id:
                    # Avoid duplicates
                    if message.author not in additional_answerers:
                        additional_answerers.append(message.author)
                        # Don't react yet - wait until 3s window closes

            break  # Found a match, stop checking other answers


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

    # Load previous question from MongoDB on startup
    await load_simply_previous_question(db)

    while True:
        try:
            # Get next question
            question = await get_trivia_question(db)
            if not question:
                print("⚠️ No questions available, waiting 10 seconds...")
                await asyncio.sleep(10)
                continue

            # Move current question to previous before setting new question
            global active_question, first_answerer, first_answer_time, additional_answerers
            global simply_current_question, simply_previous_question

            if simply_current_question is not None:
                simply_previous_question = simply_current_question.copy()
                await save_simply_previous_question(db)

            # Set up tracking for this question
            active_question = question
            simply_current_question = question.copy()
            first_answerer = None
            first_answer_time = None
            additional_answerers = []

            # Build question embed
            category = question.get("category", "Trivia")
            question_text = question.get("question", "")

            embed = discord.Embed(
                description=f"**{category}**\n\n{question_text}",
                color=discord.Color.blue()
            )

            # Add image if URL is provided and valid
            url = question.get("url", "")
            if url and url.startswith("http"):
                embed.set_image(url=url)

            # Ask the question
            await channel.send(embed=embed)
            answers = question.get("answers", [])
            main_answer = answers[0] if answers else "Unknown"
            print(f"📝 Asked: {category} - {question_text}")
            print(f"📝 Answer: {answers}")

            # Wait for answers - up to 20 seconds, or 3 seconds after first correct answer
            max_wait_time = 20.0
            start_time = asyncio.get_event_loop().time()
            answer_revealed = False

            while not answer_revealed:
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

            if first_answerer:
                # React to everyone who got it right (first + additional)
                # Find their messages and react to them
                try:
                    # Get recent messages to find correct answerers
                    users_to_react = [first_answerer] + additional_answerers
                    reacted_users = set()

                    async for msg in channel.history(limit=50):
                        if msg.author.id in [user.id for user in users_to_react] and msg.author.id not in reacted_users:
                            # Check if this message contains a correct answer
                            for correct_answer in answers:
                                if fuzzy_match_func(msg.content, correct_answer,
                                                   question.get("category", ""), question.get("url", ""),
                                                   ignore_exact_mode=True):
                                    await msg.add_reaction("✅")
                                    reacted_users.add(msg.author.id)
                                    break

                            # Stop if we've reacted to everyone
                            if len(reacted_users) == len(users_to_react):
                                break
                except Exception as e:
                    print(f"❌ Failed to react to answerers: {e}")

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

                # Record correct answer for stats
                await record_correct_answer(
                    db,
                    first_answerer.id,
                    first_answerer.display_name,
                    question.get("_id")
                )

                answer_text = f"**Answer:** {main_answer}\n\n"
                if streak > 1:
                    answer_text += f"🏆 {first_answerer.mention} got it first! 🔥 Streak: {streak}"
                else:
                    answer_text += f"🏆 {first_answerer.mention} got it first!"

                # Add additional answerers if any
                if additional_answerers:
                    also_got = ", ".join([user.mention for user in additional_answerers])
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

                answer_text = f"**Answer:** {main_answer}"
                embed = discord.Embed(description=answer_text, color=discord.Color.red())

            await channel.send(embed=embed)

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
        color=discord.Color.blue(),
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
        color=discord.Color.blue(),
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
        color=discord.Color.blue(),
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
