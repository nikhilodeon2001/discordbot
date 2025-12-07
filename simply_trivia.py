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

            # Clear active question (no delay - immediately start next question)
            active_question = None

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
