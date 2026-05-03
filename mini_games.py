"""
Mini-Games Arena System
Runs challenge functions in a dedicated channel separate from main trivia

All imports from discordbot are done lazily inside functions to ensure
the bot's event loop is active when accessing bot objects.
"""

import sys
import random
import asyncio


# Game name to function name mapping (strings, not actual functions)
# Names match the display names shown in game intro messages (without punctuation)
GAME_NAMES = [
    "poster blitz", "movie mayhem", "missing link", "famous peeps", "magic eye", "okranimal",
    "the riddler", "word nerd", "flag fest", "lyriq", "polyglottery", "prose and cons",
    "sign language", "elementary", "jigsawed", "borderline", "faceoff", "rushmore",
    "wordle war", "list battle", "ranker lists", "musiq", "myopic mystery", "microscopic mystery",
    "fusion challenge", "tally", "xxxx", "checkmate", "wall street", "spotlight",
    "hear here", "who says", "lets talk", "feud blitz", "okrace",
    "jock talk", "30 for 30", "okra says"
]

def resolve_game_name(game_name: str):
    if not game_name:
        return None
    lower_name = game_name.lower()
    for name in GAME_NAMES:
        if name.lower() == lower_name:
            return name
    return None


def _get_game_function(game_name: str):
    """
    Get the actual game function from discordbot.
    Import challenge functions lazily to avoid circular dependency.
    """
    # Lazy import of challenge functions (only when needed, in async context)
    from discordbot import (
        ask_poster_challenge,
        ask_movie_scenes_challenge,
        ask_missing_link,
        ask_ranker_people_challenge,
        ask_magic_challenge,
        ask_animal_challenge,
        ask_riddle_challenge,
        ask_dictionary_challenge,
        ask_flags_challenge,
        ask_lyric_challenge,
        ask_polyglottery_challenge,
        ask_book_challenge,
        ask_math_challenge,
        ask_element_challenge,
        ask_jigsaw_challenge,
        ask_border_challenge,
        ask_faceoff_challenge,
        ask_president_challenge,
        ask_wordle_challenge,
        ask_list_question,
        ask_ranker_list_question,
        ask_music_challenge,
        ask_myopic_challenge,
        ask_microscopic_challenge,
        ask_fusion_challenge,
        ask_tally_challenge,
        ask_currency_challenge,
        ask_chess_challenge,
        ask_stock_challenge,
        ask_search_challenge,
        ask_soundfx_challenge,
        ask_audio_music_challenge,
        ask_audio_question_challenge,
        ask_feud_question,
        ask_okrace_challenge,
        ask_sports_logos_challenge,
        ask_rapidfire_challenge,
        ask_okra_says_challenge
    )

    game_function_map = {
        "poster blitz": ask_poster_challenge,
        "movie mayhem": ask_movie_scenes_challenge,
        "missing link": ask_missing_link,
        "famous peeps": ask_ranker_people_challenge,
        "magic eye": ask_magic_challenge,
        "okranimal": ask_animal_challenge,
        "the riddler": ask_riddle_challenge,
        "word nerd": ask_dictionary_challenge,
        "flag fest": ask_flags_challenge,
        "lyriq": ask_lyric_challenge,
        "polyglottery": ask_polyglottery_challenge,
        "prose & cons": ask_book_challenge,
        "sign language": ask_math_challenge,
        "elementary": ask_element_challenge,
        "jigsawed": ask_jigsaw_challenge,
        "borderline": ask_border_challenge,
        "faceoff": ask_faceoff_challenge,
        "rushmore": ask_president_challenge,
        "wordle war": ask_wordle_challenge,
        "list battle": ask_list_question,
        "ranker lists": ask_ranker_list_question,
        "musiq": ask_music_challenge,
        "myopic mystery": ask_myopic_challenge,
        "microscopic mystery": ask_microscopic_challenge,
        "fusion challenge": ask_fusion_challenge,
        "tally": ask_tally_challenge,
        "xxxx": ask_currency_challenge,
        "checkmate": ask_chess_challenge,
        "wall street": ask_stock_challenge,
        "spotlight": ask_search_challenge,
        "hear here": ask_soundfx_challenge,
        "who says": ask_audio_music_challenge,
        "lets talk": ask_audio_question_challenge,
        "feud blitz": ask_feud_question,
        "okrace": ask_okrace_challenge,
        "jock talk": ask_sports_logos_challenge,
        "30 for 30": ask_rapidfire_challenge,
        "okra says": ask_okra_says_challenge
    }

    return game_function_map.get(game_name.lower())


async def run_mini_game(bot, game_name: str, player_name: str, player_id: int,
                        num: int = 1, channel_override=None):
    """
    Run a single mini-game in the Mini-Game Arena channel

    Args:
        bot: The Discord bot instance (passed from command)
        game_name: Name of the game (e.g., "poster blitz", "flag fest", "feud blitz")
        player_name: Display name of the player
        player_id: Discord user ID
        num: Number of questions/rounds
        channel_override: Optional channel to use instead of config

    Returns:
        winner_id or None
    """
    # Import only what we need (bot is passed as parameter)
    import discordbot
    from discordbot import (
        game_channel,
        game_voice_channel_id,
        game_bot_instance,
        game_bot,
        MINI_GAME_ARENA_CHANNEL_ID,
        MINI_GAME_ARENA_VOICE_CHANNEL_ID,
        safe_send,
    )

    # Get arena channel - use override if provided, otherwise from config
    if channel_override:
        arena_channel = channel_override
    else:
        arena_channel = bot.get_channel(MINI_GAME_ARENA_CHANNEL_ID)

    if not arena_channel:
        print(f"❌ Arena channel {MINI_GAME_ARENA_CHANNEL_ID} not found")
        return None

    # Set context for this game
    game_channel.set(arena_channel)
    game_bot.set(bot)
    # Also set module-level variables (needed because ContextVar doesn't propagate to Discord.py events)
    discordbot._active_game_bot = bot
    discordbot._active_game_channel = arena_channel

    # Set voice channel ID from configuration (if provided)
    if MINI_GAME_ARENA_VOICE_CHANNEL_ID:
        game_voice_channel_id.set(MINI_GAME_ARENA_VOICE_CHANNEL_ID)

    # For audio games, use the mini-game audio bot if available (to avoid voice conflicts).
    # Use sys.modules to get the live instance — discordbot.mini_game_audio_bot may point to
    # a dead instance created during the circular simply_trivia -> discordbot import.
    audio_games = ["hear here", "who says", "lets talk"]
    live_audio_bot = sys.modules.get('__mini_game_audio_bot__') or discordbot.mini_game_audio_bot
    if game_name.lower() in audio_games and live_audio_bot:
        print(f"🎵 Using mini-game audio bot for {game_name}")
        game_bot_instance.set(live_audio_bot)

    # Get the game function
    game_fn = _get_game_function(game_name)
    if not game_fn:
        print(f"❌ Game '{game_name}' not found")
        await safe_send(arena_channel, f"❌ Game '{game_name}' not found. Available games: {', '.join(GAME_NAMES)}")
        return None

    # Run the game with context set
    try:
        # Special handling for feud which has different signature
        if game_name.lower() == "feud blitz":
            result = await game_fn(player_name, "cooperative", player_id)
        else:
            result = await game_fn(player_name, player_id, num=num)

        return result
    except Exception as e:
        print(f"❌ Error running game '{game_name}': {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Clean up: reset module-level variables
        discordbot._active_game_bot = None
        discordbot._active_game_channel = None


async def run_random_mini_game(bot, player_name: str, player_id: int, channel_override=None):
    """Run a random mini-game"""
    game_name = random.choice(GAME_NAMES)
    print(f"🎲 Selected random game: {game_name}")
    return await run_mini_game(bot, game_name, player_name, player_id, channel_override=channel_override)


async def run_mini_game_chaos(bot, player_name: str, player_id: int, num_games: int = 5, channel_override=None):
    """
    Run multiple random mini-games (chaos mode) in the arena

    Similar to ask_chaos_challenge but runs in Mini-Game Arena channel
    """
    # Import only what we need (bot is passed as parameter)
    import discordbot
    from discordbot import (
        game_channel,
        game_voice_channel_id,
        game_bot_instance,
        game_bot,
        MINI_GAME_ARENA_CHANNEL_ID,
        MINI_GAME_ARENA_VOICE_CHANNEL_ID,
        ask_chaos_challenge,
    )

    # Get arena channel - use override if provided, otherwise from config
    if channel_override:
        arena_channel = channel_override
    else:
        arena_channel = bot.get_channel(MINI_GAME_ARENA_CHANNEL_ID)

    if not arena_channel:
        print(f"❌ Arena channel {MINI_GAME_ARENA_CHANNEL_ID} not found")
        return None

    # Set context
    game_channel.set(arena_channel)
    game_bot.set(bot)
    # Also set module-level variables (needed because ContextVar doesn't propagate to Discord.py events)
    discordbot._active_game_bot = bot
    discordbot._active_game_channel = arena_channel

    # Set voice channel ID from configuration (if provided)
    if MINI_GAME_ARENA_VOICE_CHANNEL_ID:
        game_voice_channel_id.set(MINI_GAME_ARENA_VOICE_CHANNEL_ID)

    # Use mini-game audio bot if available (chaos mode may include audio challenges)
    live_audio_bot = sys.modules.get('__mini_game_audio_bot__') or discordbot.mini_game_audio_bot
    if live_audio_bot:
        print(f"🎵 Using mini-game audio bot for chaos mode")
        game_bot_instance.set(live_audio_bot)

    # Call the regular chaos challenge - it will use the context!
    try:
        result = await ask_chaos_challenge(player_name, player_id, num_games)
        return result
    finally:
        # Clean up: reset module-level variables
        discordbot._active_game_bot = None
        discordbot._active_game_channel = None
