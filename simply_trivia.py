"""
Simply Trivia - Continuous trivia mode
Asks questions from trivia_questions collection continuously
Tracks first-to-answer and streaks
"""

import asyncio
import discord
from datetime import datetime, timezone

# Storage for active game state
active_question = None
first_answer_time = None
first_answerer = None
additional_answerers = []


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


async def load_streak(db, user_id):
    """
    Load user's current streak from MongoDB

    Args:
        db: MongoDB database instance
        user_id: Discord user ID

    Returns:
        Current streak count (0 if not found)
    """
    collection = db["simply_trivia_streaks"]
    doc = await collection.find_one({"user_id": user_id})

    if doc:
        return doc.get("streak", 0)
    return 0


async def update_streak(db, user_id, user_name, correct):
    """
    Update streak (increment if correct, reset if wrong)

    Args:
        db: MongoDB database instance
        user_id: Discord user ID
        user_name: Discord user display name
        correct: True if answer was correct, False otherwise

    Returns:
        Updated streak count
    """
    collection = db["simply_trivia_streaks"]

    if correct:
        # Increment streak
        result = await collection.find_one_and_update(
            {"user_id": user_id},
            {
                "$inc": {"streak": 1},
                "$set": {"user_name": user_name, "updated_at": datetime.now(timezone.utc)}
            },
            upsert=True,
            return_document=True
        )
        return result["streak"]
    else:
        # Reset streak
        await collection.update_one(
            {"user_id": user_id},
            {"$set": {"streak": 0, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        return 0


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

    # Check if answer is correct against any valid answer
    for correct_answer in active_question["answers"]:
        if fuzzy_match_func(
            message.content,
            correct_answer,
            active_question.get("category", ""),
            active_question.get("url", "")
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

    while True:
        try:
            # Get next question
            question = await get_trivia_question(db)
            if not question:
                print("⚠️ No questions available, waiting 10 seconds...")
                await asyncio.sleep(10)
                continue

            # Set up tracking for this question
            global active_question, first_answerer, first_answer_time, additional_answerers
            active_question = question
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
                                                   question.get("category", ""), question.get("url", "")):
                                    await msg.add_reaction("✅")
                                    reacted_users.add(msg.author.id)
                                    break

                            # Stop if we've reacted to everyone
                            if len(reacted_users) == len(users_to_react):
                                break
                except Exception as e:
                    print(f"❌ Failed to react to answerers: {e}")

                # Someone got it - update first answerer's streak
                streak = await update_streak(
                    db,
                    first_answerer.id,
                    first_answerer.display_name,
                    correct=True
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
                # No one got it - reset all active streaks
                try:
                    collection = db["simply_trivia_streaks"]
                    # Reset all users with active streaks (streak > 0) back to 0
                    await collection.update_many(
                        {"streak": {"$gt": 0}},
                        {"$set": {"streak": 0, "updated_at": datetime.now(timezone.utc)}}
                    )
                except Exception as e:
                    print(f"❌ Failed to reset streaks: {e}")

                answer_text = f"**Answer:** {main_answer}"
                embed = discord.Embed(description=answer_text, color=discord.Color.red())

            await channel.send(embed=embed)

            # Store question ID to avoid repeating
            if question.get("_id"):
                await store_question_ids_in_mongo([question["_id"]], "general")

            # Clear active question (no delay - immediately start next question)
            active_question = None

        except Exception as e:
            print(f"❌ Error in Simply Trivia loop: {e}")
            import traceback
            traceback.print_exc()
            # Wait before retrying
            await asyncio.sleep(5)
