# Initialize all variables
local_mode = False
prod_or_stage = "prod"

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Setup Sentry
sentry_sdk.init(
    dsn="https://REMOVED_SENTRY_KEY@o4507935419400192.ingest.us.sentry.io/4507935424839680",  # Replace with your DSN from Sentry
    integrations=[LoggingIntegration(level=None, event_level='ERROR')]
)

import requests
import json
import random
import importlib
import tracebackewn
import unicodedata
import datetime
from datetime import timezone
import time
import pytz
from motor.motor_asyncio import AsyncIOMotorClient
import difflib
import string
from urllib.parse import urlparse 
from urllib.parse import quote
from urllib.parse import urlencode         
from PIL import Image, ImageDraw, ImageFont, ImageColor
import openai
from openai import AsyncOpenAI
from openai import OpenAIError
import main
import subprocess
import re
from botocore.exceptions import BotoCoreError, ClientError
import aioboto3
import logging
import tempfile
import base64
from collections import Counter, defaultdict
import math
import sys
import signal
from ebooklib import epub
from html.parser import HTMLParser
import warnings
import operator
from itertools import product
import io
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'vendor'))
from word_search_generator import WordSearch
import random
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import cairosvg
import asyncio
import difflib
from metaphone import doublemetaphone
import discord
from discord.ext import commands
import aiohttp
import aiofiles
from discord import Embed, File
from typing import Optional, Tuple
import chess

# Tournament system import
from tournament import setup_tournament_system, active_tournaments

# Okra Hunt escape room import
from okra_hunt import OkraHunt

embed_color_default = discord.Color.green()
embed_color = embed_color_default

from self_update import self_update

async def end_of_round():
    print("Round ended. Checking for updates...")
    try:
        updated = await self_update()
        if not updated:
            print("No update performed, continuing game as usual.")
        return updated
    except Exception as e:
        print(f"Self-update failed: {e}")
        return False

def randomize_embed_color():
    """
    Changes the global embed_color to a random Discord color different from current one.
    Returns the new color for confirmation.
    """
    global embed_color
    
    # All available Discord color methods
    all_colors = [
        discord.Color.teal, discord.Color.dark_teal,
        discord.Color.green, discord.Color.dark_green,
        discord.Color.blue, discord.Color.dark_blue, discord.Color.blurple,
        discord.Color.purple, discord.Color.dark_purple, discord.Color.magenta, 
        discord.Color.dark_magenta, discord.Color.fuchsia,
        discord.Color.red, discord.Color.dark_red,
        discord.Color.orange, discord.Color.dark_orange, discord.Color.gold, discord.Color.dark_gold,
        discord.Color.lighter_grey, discord.Color.light_grey, discord.Color.dark_grey, 
        discord.Color.darker_grey, discord.Color.greyple,
        discord.Color.yellow
    ]
    
    # Filter out current color by comparing hex values
    current_color_value = embed_color.value
    available_colors = [color for color in all_colors if color().value != current_color_value]
    
    # Select random color and update global
    new_color_method = random.choice(available_colors)
    embed_color = new_color_method()
    
    return embed_color

def reset_embed_color():
    global embed_color

    embed_color = embed_color_default
    return embed_color

# Define global variables to store streaks and scores
round_count = 0
scoreboard = {}

# Define a global variable to store round data
round_data = {
    "questions": []  # Collect questions asked with their answers and responses
}

fastest_answers_count = {}
current_longest_answer_streak = {"user": None, "user_id": None, "streak": 0}
current_longest_round_streak = {"user": None, "user_id": None, "streak": 0}

# Store since_token and responses
since_token = None
responses = []
question_asked_start = None  
question_asked_end = None

question_responders = []  # Tracks users who responded during the current question
round_responders = []

# Add this global variable to hold the submission queue
submission_queue = []
max_queue_size = 100  # Number of submissions to accumulate before flushing

# Global variables for bump data
bumped_status = False
bumper_king_id = ""
bumper_king_name = ""
last_bump_time = None



if local_mode == True:
    discord_token = "REMOVED_DISCORD_TOKEN" 
    mongo_db_string = "mongodb+srv://nsharma2:REMOVED_MONGO_PASSWORD@staging.oxez2.mongodb.net/?retryWrites=true&w=majority&appName=staging"
    openai_api_key = "REMOVED_OPENAI_KEY"
    openweather_api_key = "REMOVED_OPENWEATHER_KEY"
    googlemaps_api_key = "REMOVED_GOOGLEMAPS_KEY"
    googletranslate_api_key = "REMOVED_GOOGLETRANSLATE_KEY"
    webster_api_key = "REMOVED_WEBSTER_KEY"
    webster_thes_api_key = "REMOVED_WEBSTER_THES_KEY"
    currency_api_key = "REMOVED_CURRENCY_KEY" 
    channel_id = 1375328414151610458
else:
    discord_token = os.getenv("discord_token")
    mongo_db_string = os.getenv("mongo_db_string")
    openai_api_key = os.getenv("openai_api_key")
    openweather_api_key = os.getenv("openweather_api_key")
    googlemaps_api_key = os.getenv("googlemaps_api_key")
    googletranslate_api_key = os.getenv("googletranslate_api_key")
    webster_api_key = os.getenv("webster_api_key")
    webster_thes_api_key = os.getenv("webster_thes_api_key")
    currency_api_key = os.getenv("currency_api_key")
    channel_id = int(os.getenv("channel_id"))


if prod_or_stage == "stage":
    okrag_id = 591861826690613248  
    OKRAN_GUILD_ID = 1375328358573015050 
    DISBOARD_BOT_ID = 591861826690613248 
    BUMPER_KING_ROLE_ID = 1411103298907275346 
    OKRAN_ROLE_ID = 1409785437979148329 
    OKRAN_ROLE_ID_2 = ""
    TOURNAMENT_GUILD_ID = 1415895468822495342
    TOURNAMENT_PARTICIPANT_ROLE_ID = 1416290287633825903 
    TOURNAMENT_OBSERVER_ROLE_ID = 1416290512310370348 
    HOST_ROLE_ID = 1416587636709134408 
    HUNT_PROGRESS_CHANNEL_ID = 1419172605746741298
    THE_LODGE_CHANNEL_ID = 1419174414263648266
    LEVEL_0_CHANNEL_ID = 1419172497755996302
    LEVEL_1_CHANNEL_ID = 1419175528526512149
    LEVEL_2_CHANNEL_ID = 1419540779155587102
    LEVEL_3_CHANNEL_ID = 1419540643037843476
    LEVEL_4_CHANNEL_ID = 1420239891106627676
    LEVEL_5_CHANNEL_ID = 1422814700755751012
    LEVEL_0_ROLE_ID = 1419169185396953199
    LEVEL_1_ROLE_ID = 1419170662089490464
    LEVEL_2_ROLE_ID = 1419170809699635344
    LEVEL_3_ROLE_ID = 1419170873897779322
    LEVEL_4_ROLE_ID = 1419170916272705556
    LEVEL_5_ROLE_ID = 1419170960967467109
    RULES_CHANNEL_ID = 1420238660342648873
    RULES_MESSAGE_ID = 1420248754862162022
    HUNT_LEADERBOARD_CHANNEL_ID = 1420278277829951518
    HUNT_LEADERBOARD_MESSAGE_ID = 1420281932566237244
    EVERYONE_ROLE_ID = 1375328358573015050
    TRIVIA_VOICE_CHANNEL_ID = 1432952256721850469

elif prod_or_stage == "prod":
    okrag_id = 591861826690613248
    OKRAN_GUILD_ID = 1367682586079395902  # Production
    DISBOARD_BOT_ID = 302050872383242240  # Disboard
    BUMPER_KING_ROLE_ID = 1411057279209570374 # Production
    OKRAN_ROLE_ID = 1408305516131782736 #Prouction
    OKRAN_ROLE_ID_2 = 1429516438141538507
    TOURNAMENT_GUILD_ID = 1416298250729820192 # Production
    TOURNAMENT_PARTICIPANT_ROLE_ID = 1416298356849774612 #Production
    TOURNAMENT_OBSERVER_ROLE_ID = 1416298438915788861 #Production
    HOST_ROLE_ID = 1411059745774764193 # Production
    HUNT_PROGRESS_CHANNEL_ID = 1418471376632938568
    THE_LODGE_CHANNEL_ID = 1419198606308806788
    LEVEL_0_CHANNEL_ID = 1419198737904959508
    LEVEL_1_CHANNEL_ID = 1419198838173995088 
    LEVEL_2_CHANNEL_ID = 1419539602733269103
    LEVEL_3_CHANNEL_ID = 1419540205592903700
    LEVEL_4_CHANNEL_ID = 1420239588110106645
    LEVEL_5_CHANNEL_ID = 1422815006788947968
    LEVEL_0_ROLE_ID = 1418470440036208640
    LEVEL_1_ROLE_ID = 1418468519796019220
    LEVEL_2_ROLE_ID = 1418468900852596796
    LEVEL_3_ROLE_ID = 1418469027894001664
    LEVEL_4_ROLE_ID = 1418469150795366453
    LEVEL_5_ROLE_ID = 1418469212028014603
    RULES_CHANNEL_ID = 1372347624648347649
    RULES_MESSAGE_ID = 1374598920973320313
    HUNT_LEADERBOARD_CHANNEL_ID = 1420277804075061320
    HUNT_LEADERBOARD_MESSAGE_ID = 1420292321370570844
    EVERYONE_ROLE_ID = 1367682586079395902
    TRIVIA_VOICE_CHANNEL_ID = 1432951778244038756




intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
openai_client = AsyncOpenAI(api_key=openai_api_key)
id_limits = {"general": 2000, "mysterybox": 2000, "crossword": 5000, "jeopardy": 5000, "wof": 1500, "list": 20, "feud": 1000, "posters": 2000, "movie_scenes": 5000, "missing_link": 2500, "people": 2500, "ranker_list": 4000, "animal": 2000, "riddle": 2500, "dictionary": 5000, "flags": 800, "lyric": 500, "polyglottery": 80, "book": 80, "element": 100, "jigsaw": 5000, "border": 100, "faceoff": 5000, "president": 80, "wordle": 1400, "myopic": 5000, "fusion": 5000, "microscopic": 5000, "chess": 5000, "stock": 800, "currency": 100, "search": 10, "billboard": 40, "soundfx": 5000}
max_retries = 3
delay_between_retries = 3
first_place_bonus = 0
magic_time = 10
magic_number = 0000
ghost_mode_default = False
ghost_mode = ghost_mode_default
god_mode_default = False
god_mode = god_mode_default
god_mode_points = 5000
god_mode_players = 5
yolo_mode_default = False
yolo_mode = yolo_mode_default
emoji_mode_default = True
emoji_mode = emoji_mode_default
collect_feedback_mode_default = True
collect_feedback_mode = collect_feedback_mode_default
magic_number_correct = False
wf_winner = False
nice_okra = False
creep_okra = False
seductive_okra = False
joke_okra = False
haiku_okra = False
trailer_okra = False
heist_okra = False
horoscope_okra = False
rap_okra = False
shakespeare_okra = False
pirate_okra = False
noir_okra = False
hype_okra = False
roast_okra = False
blind_mode_default = False
blind_mode = blind_mode_default
marx_mode_default = False
marx_mode = marx_mode_default
image_questions_default = True
image_questions = image_questions_default
sniper_mode_default = False
sniper_mode = sniper_mode_default
cloak_mode_default = False
cloak_mode = cloak_mode_default
cloaked_user = None


channel = None


question_categories = [
    "Mystery Box or Boat", "Famous People", "Anatomy", "Characters", "Music", "Art & Literature", 
    "Chemistry", "Geography", "Mathematics", "Physics", "Science & Nature", "Language", "English Grammar", 
    "Astronomy", "Logos", "The World", "Economics & Government", "Toys & Games", "Food & Drinks", "Geology", 
    "Tech & Video Games", "Flags", "Miscellaneous", "Biology", "Superheroes", "Television", "Pop Culture", 
    "History", "Movies", "Religion & Mythology", "Sports & Leisure", "World Culture", "General Knowledge", "Statistics"
]

fixed_letters = ['O', 'K', 'R', 'A']
filler_words = {'a', 'an', 'the', 'of', 'and', 'to', 'in', 'on', 'at', 'with', 'for', 'by'}
categories_to_exclude = []  
collected_responses = []
current_question = None
previous_question = None

ops = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': lambda a, b: a / b if b != 0 else None
}

superscript_map = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"
}

reverse_superscript_map = {v: k for k, v in superscript_map.items()}

warnings.filterwarnings("ignore", message="In the future version we will turn default option ignore_ncx to True.")
warnings.filterwarnings("ignore", message="This search incorrectly ignores the root element, and will be fixed in a future version.")


#async def safe_send(channel, *args, max_retries=3, delay=2, **kwargs):
#    for attempt in range(1, max_retries + 1):
#        try:
#            return await channel.send(*args, **kwargs)
#        except discord.HTTPException as e:
#            print(f"⚠️ Attempt {attempt}: Failed to send message - {e}")
#            if attempt == max_retries:
#                print("❌ Max retries reached. Giving up.")
#                break
#            await asyncio.sleep(delay)
#        except discord.Forbidden:
#            print("❌ Bot does not have permission to send messages to this channel.")
#            break
#        except discord.NotFound:
#            print("❌ Channel not found.")
#            break
#        except Exception as e:
#            print(f"❌ Unexpected error in safe_send: {e}")
#            break


def clean_leading_trailing_junk(text: str) -> str:
    # This regex trims only leading/trailing \n, \r, space, tab, or \u200b
    return re.sub(r'^[\s\u200b]+|[\s\u200b]+$', '', text)



async def safe_send(channel, *args, max_retries=3, delay=2, use_embed=True, image_url=None, file=None, **kwargs):
    if use_embed:
        # Pull out content or first positional arg
        content = kwargs.pop("content", None)
        if not content and args:
            content = str(args[0])
            args = ()

        # Use existing embed or create one
        embed = kwargs.pop("embed", Embed())
        if not isinstance(embed, Embed):
            embed = Embed()
            
        embed.color = embed_color

        # Set description only if not already set
        if content and not embed.description:
            embed.description = clean_leading_trailing_junk(str(content))

        # Handle file-based image attachment
        if file and isinstance(file, File):
            if not image_url and hasattr(file, "filename"):
                image_url = f"attachment://{file.filename}"
            kwargs["file"] = file

        # Attach image to embed
        if image_url:
            embed.set_image(url=image_url)

        # If embed would otherwise be empty, make it valid
        if not embed.description and not embed.image.url:
            embed.description = "\u200b"

        # Inject the processed embed
        kwargs["embed"] = embed

    for attempt in range(1, max_retries + 1):
        try:
            return await channel.send(*args, **kwargs)
        except Exception as e:
            print(f"⚠️ Attempt {attempt}: Failed to send message - {e}")
            if attempt == max_retries:
                print("❌ Max retries reached. Giving up.")
                break
            await asyncio.sleep(delay)

async def get_survey_results():
    survey_collection = db["survey_questions_discord"]
    results = []

    # Find all documents where question_type is "rating-10"
    rating_questions = await survey_collection.find({"question_type": "rating-10"}).to_list(length=None)

    for doc in rating_questions:
        question = doc.get("question", "Unknown Question")
        responses = doc.get("responses", {})
        answer_values = []

        # Go through each user in responses
        for user_response in responses.values():
            answer = user_response.get("answer")
            if isinstance(answer, (int, float)):
                answer_values.append(answer)

        # Calculate average if there are any valid answers
        if answer_values:
            avg_score = round(sum(answer_values) / len(answer_values), 1)
            results.append(f"{question}: {avg_score}")
            print(f"{question}: {avg_score}")

    return results


async def select_intro_image_url():
    # Connect to the collection
    collection = db["intro_image_urls"]

    # Fetch one random document where enabled is True
    result = await collection.aggregate([
            {"$match": {"enabled": True}},
            {"$sample": {"size": 1}}
        ]).to_list(length=1)

    if not result:
        print("No enabled intro image URLs found.")
        return None

    # Return just the URL field
    return result[0].get("url")


def create_family_feud_board_image(total_answers, user_answers, num_of_xs=0):
    # Convert user_answers to a case-insensitive set
    lower_user_answers = {ua.lower() for ua in user_answers}
    n = len(total_answers)

    width = 3600
    height = 800 + (n * 240)
    bg_color = (10, 10, 10)
    gold_color = (255, 215, 0)
    #gold_color = (62, 145, 45)
    box_color = (0, 60, 220)
    #box_color = (97, 51, 47)
    box_outline = (255, 255, 255)
    txt_color = (255, 255, 255)
    circle_color = (0, 0, 150)
    #circle_color = (34, 49, 29)

    # Create the blank image
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Assuming this is at the top of your script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    font_dir = os.path.join(base_dir, "fonts")

    def load_font(font_name, size):
        try:
            font_path = os.path.join(font_dir, font_name)
            return ImageFont.truetype(font_path, size)
        except:
            return ImageFont.load_default()

    # Load fonts
    scoreboard_font = load_font("DejaVuSans.ttf", 80)
    answer_font = load_font("DejaVuSans.ttf", 140)
    circle_font = load_font("DejaVuSans.ttf", 80)

    # 1) Golden Arc
    arc_x1, arc_y1 = 0, 0
    arc_x2, arc_y2 = width, height * 2
    draw.pieslice([arc_x1, arc_y1, arc_x2, arc_y2], start=180, end=360, fill=gold_color)

    # 2) Scoreboard rectangle
    scoreboard_w = 800
    scoreboard_h = 150
    scoreboard_x = (width - scoreboard_w) // 2
    scoreboard_y = 60
    scoreboard_rect = [scoreboard_x, scoreboard_y, scoreboard_x + scoreboard_w, scoreboard_y + scoreboard_h]
    draw.rectangle(scoreboard_rect, fill=(0, 0, 150))

    scoreboard_text = "Okra"
    # measure scoreboard text
    try:
        left, top, right, bottom = draw.textbbox((0, 0), scoreboard_text, font=scoreboard_font)
        txt_w, txt_h = right - left, bottom - top
    except:
        mask = scoreboard_font.getmask(scoreboard_text)
        txt_w, txt_h = mask.size

    sb_text_x = scoreboard_x + (scoreboard_w - txt_w) // 2
    sb_text_y = scoreboard_y + (scoreboard_h - txt_h) // 2
    draw.text((sb_text_x, sb_text_y), scoreboard_text, fill=(255, 255, 255), font=scoreboard_font)

    # 3) Single-column answer boxes
    box_height = 240
    box_width = 2500
    box_spacing = 40
    top_offset = scoreboard_y + scoreboard_h + 160
    left_margin = (width - box_width) // 2

    # -- Download Okra image from URL for unrevealed answers --
    #    We'll fetch it and convert to RGBA for transparency if needed.
    okra_url = "https://triviabotwebsite.s3.us-east-2.amazonaws.com/okra/okra_ff.png"
    okra_icon = None
    try:
        response = requests.get(okra_url, timeout=5)
        response.raise_for_status()
        okra_icon = Image.open(io.BytesIO(response.content)).convert("RGBA")
        # optional: resize if it's too large
        okra_icon = okra_icon.resize((106, 190), resample=Image.LANCZOS)
    except Exception as e:
        print(f"Could not load Okra image from URL: {e}")
        okra_icon = None

    for i, ans in enumerate(total_answers):
        box_x = left_margin
        box_y = top_offset + i*(box_height + box_spacing)

        draw.rectangle(
            [box_x, box_y, box_x + box_width, box_y + box_height],
            fill=box_color,
            outline=box_outline,
            width=8
        )

        # Circle for numbering
        circle_diam = 160
        circle_x1 = box_x - circle_diam//2
        circle_y1 = box_y + (box_height - circle_diam)//2
        circle_x2 = circle_x1 + circle_diam
        circle_y2 = circle_y1 + circle_diam
        draw.ellipse([circle_x1, circle_y1, circle_x2, circle_y2],
                     fill=circle_color, outline=box_outline, width=8)

        number_str = str(i + 1)
        try:
            left, top, right, bottom = draw.textbbox((0, 0), number_str, font=circle_font)
            num_w, num_h = right - left, bottom - top
        except:
            mask = circle_font.getmask(number_str)
            num_w, num_h = mask.size
        
        num_x = circle_x1 + (circle_diam - num_w)//2
        num_y = circle_y1 + (circle_diam - num_h)//2
        draw.text((num_x, num_y), number_str, fill=(255, 255, 255), font=circle_font)

        # Check if user guessed it
        is_revealed = (ans.lower() in lower_user_answers)
        if is_revealed:
            # measure text
            try:
                left, top, right, bottom = draw.textbbox((0, 0), ans, font=answer_font)
                r_w, r_h = right - left, bottom - top
            except:
                mask = answer_font.getmask(ans)
                r_w, r_h = mask.size

            text_x = box_x + (box_width - r_w)//2
            text_y = box_y + (box_height - r_h)//2
            draw.text((text_x, text_y), ans, fill=txt_color, font=answer_font)
        else:
            # If not revealed, paste the okra image (if loaded)
            if okra_icon:
                okra_w, okra_h = okra_icon.size
                okra_x = box_x + (box_width - okra_w)//2
                okra_y = box_y + (box_height - okra_h)//2
                img.paste(okra_icon, (okra_x, okra_y), okra_icon)
            else:
                # fallback: show ??? if no image loaded
                hidden_text = "???"
                try:
                    left, top, right, bottom = draw.textbbox((0, 0), hidden_text, font=answer_font)
                    h_w, h_h = right - left, bottom - top
                except:
                    mask = answer_font.getmask(hidden_text)
                    h_w, h_h = mask.size
                h_text_x = box_x + (box_width - h_w)//2
                h_text_y = box_y + (box_height - h_h)//2
                draw.text((h_text_x, h_text_y), hidden_text, fill=txt_color, font=answer_font)

    # 4) Overlay red X's if num_of_xs > 0
    if num_of_xs > 0:
        x_font = load_font("DejaVuSans.ttf", 800)

        x_text = "X"
        try:
            lx, ty, rx, by = draw.textbbox((0, 0), x_text, font=x_font)
            x_w, x_h = rx - lx, by - ty
        except:
            mask = x_font.getmask(x_text)
            x_w, x_h = mask.size

        total_strikes_width = (num_of_xs - 1) * int(1.2 * x_w) + x_w
        start_x = (width - total_strikes_width)//2
        x_y = (height - x_h) // 2

        for i in range(num_of_xs):
            x_x = start_x + i * int(1.2 * x_w)
            draw.text((x_x, x_y), x_text, font=x_font, fill=(255, 0, 0))

    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    
    return img_buffer


def word_similarity(guess, answer):
    guess = guess.lower().strip()
    answer = answer.lower().strip()

    if not guess or not answer:
        return 0.0

    if guess == answer:
        return 1.0

    seq_similarity = difflib.SequenceMatcher(None, guess, answer).ratio()
    first_letter_bonus = 0.1 if guess[0] == answer[0] else 0
    last_letter_bonus = 0.1 if guess[-1] == answer[-1] else 0

    max_len = max(len(guess), len(answer))
    len_diff = abs(len(guess) - len(answer))
    length_similarity = max(0, 1 - (len_diff / max_len)) * 0.2

    guess_phonetic = doublemetaphone(guess)
    answer_phonetic = doublemetaphone(answer)
    phonetic_match = 0.2 if any(g == a and g != '' for g in guess_phonetic for a in answer_phonetic) else 0

    score = (seq_similarity * 0.5) + first_letter_bonus + last_letter_bonus + length_similarity + phonetic_match
    return round(min(score, 1.0), 3)


async def shuffle_image_pieces(image_url, num_pieces=9, tint_mode="none", tint_colors=None, fixed_tint=None, tint_strength=0.50):
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status != 200:
                raise Exception(f"Failed to download image from {image_url}")
            image_data = await response.read()

    img = Image.open(io.BytesIO(image_data)).convert("RGB")
    width, height = img.size

    grid_size = int(num_pieces ** 0.5)
    if grid_size * grid_size != num_pieces:
        raise ValueError("num_pieces must be a perfect square")

    piece_width = width // grid_size
    piece_height = height // grid_size

    pieces = []
    for i in range(grid_size):
        for j in range(grid_size):
            left = j * piece_width
            upper = i * piece_height
            right = left + piece_width
            lower = upper + piece_height
            piece = img.crop((left, upper, right, lower))
            pieces.append(piece)

    random.shuffle(pieces)

    shuffled_img = Image.new("RGB", (width, height))
    idx = 0
    for i in range(grid_size):
        for j in range(grid_size):
            piece = pieces[idx]

            if tint_mode == "fixed" and fixed_tint:
                overlay = Image.new("RGB", piece.size, fixed_tint)
                piece = Image.blend(piece, overlay, alpha=tint_strength)
            elif tint_mode == "random" and tint_colors:
                random_tint = random.choice(tint_colors)
                overlay = Image.new("RGB", piece.size, random_tint)
                piece = Image.blend(piece, overlay, alpha=tint_strength)

            shuffled_img.paste(piece, (j * piece_width, i * piece_height))
            idx += 1

    image_buffer = io.BytesIO()
    shuffled_img.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    return image_buffer


async def ask_jigsaw_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/jigsaw1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/jigsaw2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/jigsaw3.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/jigsaw4.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/jigsaw5.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/jigsaw6.gif"
    ]
    gif_url = random.choice(gifs)

    await safe_send(channel, content="\u200b\n🧩🌀 **Jigsawed**: Identify the Puzzle\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    await safe_send(channel, f"\u200b\n🪚🔢 **<@{winner_id}>**, how many jigsaw pieces?\n\n👉 **4**, **9**, **16**, **25**, **36**, **49**, **64**, **81**, or **100**\n\u200b")
    try:
        msg = await bot.wait_for("message", timeout=magic_time + 5, check=lambda m: m.author.id == winner_id and m.author != bot.user and m.channel == channel and m.content in {"4", "9", "16", "25", "36", "49", "64", "81", "100"})
        num_pieces = int(msg.content)
        await msg.add_reaction("✅")
    except asyncio.TimeoutError:
        num_pieces = 16
        await safe_send(channel, "\u200b\n⏱️ Time's up! We'll go with **16** pieces.\n\u200b")

    await safe_send(channel, f"\u200b\n💥🤯 Ok...ra! We're going with **{num_pieces}** pieces!\n\u200b")
    await asyncio.sleep(2)

    user_data = {}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("jigsaw")
            collection = db["jigsaw_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 100}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            q = questions[0]

            qid = q["_id"]
            image_url = q["url"]
            answers = q["answers"]
            category = q["category"]
            main_answer = answers[0]

            if qid:
                await store_question_ids_in_mongo([qid], "jigsaw")
            print(answers)

            random_colors = [
                (255, 150, 150),  # light red
                (150, 255, 150),  # light green
                (150, 150, 255),  # light blue
                (255, 255, 150),  # light yellow
                (150, 255, 255),  # light cyan
                (255, 150, 255),  # light magenta / pink
                (255, 200, 150),  # light orange
                (200, 150, 255),  # light purple
                (150, 255, 200),  # light teal / turquoise
                (255, 220, 200),  # peach
                (200, 255, 150),  # light lime
                (220, 200, 255),  # light violet
            ]

            jigsaw_buffer = await shuffle_image_pieces(
                image_url, num_pieces=num_pieces,
                tint_mode="random",
                tint_colors=random_colors,
                fixed_tint=None,
                tint_strength=0.2
            )

            message = f"\u200b\n🗣💬❓ **({round_num}/{num})** Who or what is **THIS**?!?\n\u200b"
            file = discord.File(fp=jigsaw_buffer, filename="jigsaw.png")
            embed = discord.Embed()
            embed.set_image(url="attachment://jigsaw.png")
            await safe_send(channel, content=message, embed=embed, file=file)

            answered = False
            processed_users = set()
            start_time = asyncio.get_event_loop().time()

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 20 and not answered:
                try:
                    timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                    msg = await bot.wait_for("message", timeout=timeout, check=check)
                    guess = normalize_text(msg.content).replace(" ", "")
                    user = msg.author.display_name
                    uid = msg.author.id
                    key = (uid, guess)

                    if key in processed_users:
                        continue
                    processed_users.add(key)

                    for correct in answers:
                        correct_clean = normalize_text(correct).replace(" ", "")
                        if fuzzy_match(guess, correct_clean, category, image_url):
                            await msg.add_reaction("✅")
                            await safe_send(channel, f"\u200b\n✅🎉 **<@{uid}>** got it! **{correct.upper()}**\n\u200b")
                            user_data[uid] = (user, user_data.get(uid, (user, 0))[1] + 1)
                            all_answers = "\n".join(f"{a.upper()}" for a in answers)
                            await safe_send(channel, f"\u200b\n📝🧠 **All Answers**\n{all_answers}\n\u200b\n\u200b")
                            embed = discord.Embed()
                            embed.set_image(url=image_url)
                            await safe_send(channel, embed=embed)
                            answered = True
                            break
                except asyncio.TimeoutError:
                    break

            if not answered:
                all_answers = "\n".join(f"{a.upper()}" for a in answers)
                await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\n📝🧠 Answers:\n{all_answers}\n\u200b")
                embed = discord.Embed()
                embed.set_image(url=image_url)
                await safe_send(channel, embed=embed)

            await asyncio.sleep(5)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(traceback.format_exc())
            await safe_send(channel, "\u200b\n⚠️ Error during round, skipping.\n\u200b")
            continue

        await asyncio.sleep(1)

        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                jigsaw_winner_id, (display_name, final_score) = sorted_users[0]
                return jigsaw_winner_id
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        jigsaw_winner_id, (display_name, final_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return jigsaw_winner_id
    else:
        return None


    



async def ask_faceoff_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    faceoff_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/faceoff1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/faceoff2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/faceoff3.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/faceoff4.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/faceoff5.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/faceoff6.gif"
    ]
    gif_url = random.choice(faceoff_gifs)

    await safe_send(channel, content="\u200b\n🙃🙂 **Face/Off**: 'I want to take his Face..Off'.\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    await safe_send(channel, f"\u200b\n🪚🔢 **<@{winner_id}>**, how many face pieces?\n👉 **4, 9, 16, 25, 36, 49, 64, 81, or 100**\n\u200b")
    try:
        msg = await bot.wait_for("message", timeout=magic_time + 5, check=lambda m: m.author.id == winner_id and m.channel == channel and m.content in {"4", "9", "16", "25", "36", "49", "64", "81", "100"})
        num_pieces = int(msg.content)
        await msg.add_reaction("✅")
    except asyncio.TimeoutError:
        num_pieces = 16
        await safe_send(channel, "\u200b\n😬⏱️ Time's up! We'll go with **16** pieces.\n\u200b")

    await safe_send(channel, f"\u200b\n💥🤯 Ok...ra! We're going with **{num_pieces}** pieces!\n\u200b")
    await asyncio.sleep(2)

    if num > 1:
        await safe_send(channel, f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b")
        await asyncio.sleep(2)

    user_scores = {}

    faceoff_num = 1
    while faceoff_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("faceoff")
            collection = db["faceoff_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 5}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            docs = [doc async for doc in collection.aggregate(pipeline)]
            q = docs[0]

            qid = q["_id"]
            image_url = q["url"]
            answers = q["answers"]
            main_answer = answers[0]
            category = q["category"]
            question_text = q["question"]

            print(answers)

            if qid:
                await store_question_ids_in_mongo([qid], "faceoff")

            buffer = await shuffle_image_pieces(image_url, num_pieces=num_pieces)
            embed = discord.Embed()
            embed.set_image(url="attachment://faceoff.png")
            await safe_send(channel, f"\u200b\n⚠️🚨 Everyone's in!\n\n🗣💬❓ **Face {faceoff_num}** of {num}: Who is **THIS**?!?\n\u200b", embed=embed, file=discord.File(buffer, "faceoff.png"))

            answered = False
            processed = set()
            start_time = asyncio.get_event_loop().time()

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 20 and not answered:
                try:
                    timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                    msg = await bot.wait_for("message", timeout=timeout, check=check)
                    content = normalize_text(msg.content).replace(" ", "")
                    key = (msg.author.id, content)

                    if key in processed:
                        continue
                    processed.add(key)

                    for a in answers:
                        if fuzzy_match(content, normalize_text(a).replace(" ", ""), category, image_url):
                            await msg.add_reaction("✅")
                            await safe_send(channel, f"\u200b\n✅🎉 Correct! **{msg.author.display_name}** got it! **{a.upper()}**\n\u200b")
                            embed = discord.Embed()
                            embed.set_image(url=image_url)
                            await safe_send(channel, embed=embed)
                            uid = msg.author.id
                            user_scores[uid] = (msg.author.display_name, user_scores.get(uid, (msg.author.display_name, 0))[1] + 1)
                            answered = True
                            break
                except asyncio.TimeoutError:
                    break

            if not answered:
                await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\n📝🧠 **{answers[0].upper()}**\n\u200b")
                embed = discord.Embed()
                embed.set_image(url=image_url)
                await safe_send(channel, embed=embed)

            await asyncio.sleep(3)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(traceback.format_exc())
            await safe_send(channel, "\u200b\n⚠️ Error during round, skipping.\n\u200b")
            continue

        faceoff_num += 1

        message = ""

        sorted_scores = sorted(user_scores.items(), key=lambda x: x[1][1], reverse=True)
        
        if num == 1:
            if sorted_scores:
                faceoff_winner_id, (display_name, final_score) = sorted_scores[0]
                return faceoff_winner_id
            else:
                return None

        if sorted_scores:
            if faceoff_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_scores, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)

    if sorted_scores:
        faceoff_winner_id, (display_name, final_score) = sorted_scores[0]
        await safe_send(channel, f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b")
    else:
        await safe_send(channel, "\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b")

    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_scores:
        return faceoff_winner_id
    else:
        return None


def find_word_positions(grid_lines, word):
    """Find all positions where a word appears in the grid (horizontal, vertical, diagonal)"""
    if not grid_lines or not word:
        return []
    
    positions = []
    word = word.upper().replace(' ', '').replace('-', '')
    rows = len(grid_lines)
    cols = len(grid_lines[0].split()) if grid_lines else 0
    
    # Convert grid to 2D array
    grid = []
    for line in grid_lines:
        row = line.split()
        if len(row) == cols:
            grid.append([char.upper() for char in row])
    
    if not grid:
        return positions
    
    # Directions: right, down, diagonal down-right, diagonal down-left, left, up, diagonal up-left, diagonal up-right
    directions = [(0,1), (1,0), (1,1), (1,-1), (0,-1), (-1,0), (-1,-1), (-1,1)]
    
    for row in range(rows):
        for col in range(cols):
            for dr, dc in directions:
                # Check if word fits in this direction
                end_row = row + dr * (len(word) - 1)
                end_col = col + dc * (len(word) - 1)
                
                if 0 <= end_row < rows and 0 <= end_col < cols:
                    # Check if word matches
                    found_word = ""
                    word_positions = []
                    for i in range(len(word)):
                        r = row + dr * i
                        c = col + dc * i
                        found_word += grid[r][c]
                        word_positions.append((r, c))
                    
                    if found_word == word:
                        positions.append(word_positions)
    
    return positions

def create_word_search_image(puzzle_text, found_words=None, is_solution=False, words_list=None):
    """Create a PNG image from word search text using PIL"""
    try:
        
        if found_words is None:
            found_words = set()
        
        # Parse the puzzle text to separate grid and word list
        lines = puzzle_text.strip().split('\n')
        
        # Find the grid section (after the line of dashes)
        grid_start = 0
        for i, line in enumerate(lines):
            if '───' in line or '---' in line:
                grid_start = i + 1
                break
        
        # Extract grid lines (usually lines that have spaces between characters)
        grid_lines = []
        for line in lines[grid_start:]:
            # Grid lines typically have single characters separated by spaces
            if len(line.strip()) > 0 and ' ' in line and len(line.split()) > 10:
                grid_lines.append(line.strip())
            elif len(grid_lines) > 0:  # Stop when we hit the word list
                break
                
        if not grid_lines:
            # Fallback: just use the text as-is
            grid_lines = [line.strip() for line in lines[grid_start:grid_start+20]]
            grid_lines = [line for line in grid_lines if line]
        
        # Create image dimensions
        char_width = 30
        char_height = 35
        grid_width = max(len(line.split()) for line in grid_lines) if grid_lines else 20
        grid_height = len(grid_lines)
        
        # Image dimensions with padding (no title/clues, just grid)
        padding = 50
        # No word list needed for any image
        word_list_height = 0
            
        img_width = grid_width * char_width + padding * 2
        img_height = grid_height * char_height + padding * 2 + word_list_height
        
        # Create image
        img = Image.new('RGB', (img_width, img_height), color='white')
        draw = ImageDraw.Draw(img)
        
        # Try to use Monaco font from fonts directory first, then system fonts
        try:
            font_path = os.path.join(os.path.dirname(__file__), "fonts", "Monaco.ttf")
            font = ImageFont.truetype(font_path, 24)
            print("Monaco from fonts folder")
        except:
            try:
                font = ImageFont.truetype("Monaco", 24)
                print("Monaco system font")
            except:
                try:
                    font = ImageFont.truetype("Courier", 24)
                    print("Courier")
                except:
                    font = ImageFont.load_default()
                    print("Default font")
        
        # Grid starts immediately after padding (no title or clues)
        grid_start_y = padding
        
        # Find positions of all words for highlighting
        found_positions = set()
        unfound_positions = set()
        
        if is_solution and words_list:
            # For solution image: highlight all words
            for word in words_list:
                word_positions = find_word_positions(grid_lines, word)
                for position_list in word_positions:
                    for pos in position_list:
                        if word.upper() in [w.upper() for w in found_words]:
                            found_positions.add(pos)
                        else:
                            unfound_positions.add(pos)
        elif found_words:
            # For regular puzzle: only highlight found words
            for word in found_words:
                word_positions = find_word_positions(grid_lines, word)
                for position_list in word_positions:
                    for pos in position_list:
                        found_positions.add(pos)
        
        # Draw grid
        for row, line in enumerate(grid_lines):
            chars = line.split()
            for col, char in enumerate(chars):
                x = padding + col * char_width
                y = grid_start_y + row * char_height
                
                # Check if this position is part of found or unfound words
                is_found_position = (row, col) in found_positions
                is_unfound_position = (row, col) in unfound_positions
                
                # Color coding
                if is_found_position:
                    char_color = 'black'
                    bg_color = 'lightgreen'
                elif is_unfound_position:
                    char_color = 'black'
                    bg_color = 'lightpink'
                else:
                    char_color = 'black'
                    bg_color = None
                
                # Draw background for found letters
                if bg_color:
                    draw.rectangle([x, y, x+char_width, y+char_height], fill=bg_color)
                
                # Center the text in the cell
                char_text = char.upper()
                # Get text dimensions
                bbox = draw.textbbox((0, 0), char_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                # Calculate centered position
                text_x = x + (char_width - text_width) // 2
                text_y = y + (char_height - text_height) // 2
                
                draw.text((text_x, text_y), char_text, fill=char_color, font=font)
        
        # No word list displayed in images
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"Error creating word search image: {e}")
        # Return a simple text-based fallback
        return create_simple_text_image(puzzle_text)

def create_simple_text_image(text):
    """Fallback function to create a simple text image"""
    try:
        
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("Monaco", 16)
        except:
            font = ImageFont.load_default()
        
        # Split text into lines and draw
        lines = text.split('\n')[:30]  # Limit to 30 lines
        for i, line in enumerate(lines):
            draw.text((10, 10 + i * 20), line[:80], fill='black', font=font)  # Limit line length
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
    except:
        # Ultimate fallback - return empty buffer
        return io.BytesIO()

async def ask_search_challenge(winner, winner_id, num=1):
    global wf_winner
    wf_winner = True
    
    SEARCH_CATEGORIES = [
        "Agreement And Disagreement",
        "Animals",
        "Appearance",
        "Art",
        "Body",
        "Certainty And Doubt",
        "Cinema And Theater",
        "Clothes And Fashion",
        "Colors And Shapes",
        "Decision Suggestion Obligation",
        "Eating Drinking And Serving",
        "Education",
        "Food And Drink Preparation",
        "Food And Drinks",
        "Food Ingredients",
        "Health And Sickness",
        "Hobbies Games",
        "Land Transportation",
        "Literature",
        "Music",
        "Opinion And Argument",
        "Personal Care",
        "Sports",
        "Words Related To Architecture And Construction",
        "Words Related To Home And Garden",
        "Words Related To Linguistics",
        "Words Related To Media And Communication",
        "Words Related To Medical Science",
        "Words Related To Performing Arts"
    ]
    
    search_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/search1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/search2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/search3.gif",
    ]
    gif_url = random.choice(search_gifs)
    
    await safe_send(channel, content="\u200b\n🔍🔤 **Spotlight**: Find the hidden words!\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)
    
    # Category Selection Phase
    categories_text = "\n".join([f"**{i+1}**. {cat}" for i, cat in enumerate(SEARCH_CATEGORIES)])
    category_message = f"\u200b\n📚 **Choose a category:**\n\n{categories_text}\n\nType the **number** of your choice (1-{len(SEARCH_CATEGORIES)})\n\u200b"
    await safe_send(channel, category_message)
    
    selected_category = None
    start_time = asyncio.get_event_loop().time()
    
    def category_check(m):
        return m.channel == channel and m.author != bot.user
    
    while asyncio.get_event_loop().time() - start_time < 30:
        try:
            msg = await bot.wait_for("message", timeout=2, check=category_check)
            content = msg.content.strip()
            
            if content.isdigit():
                choice = int(content)
                if 1 <= choice <= len(SEARCH_CATEGORIES):
                    selected_category = SEARCH_CATEGORIES[choice - 1]
                    await safe_send(channel, f"\u200b\n✅ **Selected Category:** {selected_category}\n\u200b")
                    break
                    
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print(f"Error in category selection: {e}")
            continue
    
    if not selected_category:
        selected_category = random.choice(SEARCH_CATEGORIES)
        await safe_send(channel, f"\u200b\n⏰ **Time's up!** Random category selected: **{selected_category}**\n\u200b")
    
    await asyncio.sleep(2)
    
    # MongoDB document selection
    try:
        collection = db["search_questions"]

        # Get recent IDs to exclude
        recent_search_ids = await get_recent_question_ids_from_mongo("search")
        
        # Build aggregation pipeline
        pipeline = [
            {"$match": {
                "category": selected_category,
                "_id": {"$nin": list(recent_search_ids)}
            }},
            {"$sample": {"size": 10}},
            {"$sample": {"size": 1}}
        ]
        
        documents = [doc async for doc in collection.aggregate(pipeline)]
        
        if not documents:
            # Fallback without recent exclusion
            pipeline = [
                {"$match": {"category": selected_category}},
                {"$sample": {"size": 1}}
            ]
            documents = [doc async for doc in collection.aggregate(pipeline)]
            
        if not documents:
            await safe_send(channel, "\u200b\n❌ **No documents found for this category!**\n\u200b")
            wf_winner = True
            return None
            
        selected_doc = documents[0]
        words_list = selected_doc.get("words", [])
        selected_subcategory = selected_doc.get("subcategory", "Unknown")
        words_id = selected_doc["_id"]

        await safe_send(channel, f"\u200b\n🔸 **Topic:** {selected_subcategory}\n\u200b")
        await asyncio.sleep(3)
        
        if len(words_list) < 5:
            await safe_send(channel, "\u200b\n❌ **Not enough words in this category!**\n\u200b")
            wf_winner = True
            return None
            
        # Log the question ID
        if words_id:
            await store_question_ids_in_mongo([words_id], "search")

        
        
    except Exception as e:
        print(f"Error fetching search document: {e}")
        await safe_send(channel, "\u200b\n❌ **Database error! Please try again.**\n\u200b")
        wf_winner = True
        return None
        
    # Limit words to 15 maximum for reasonable puzzle size
    if len(words_list) > 15:
        words_list = random.sample(words_list, 15)
    
    # Generate word search puzzle
    try:
        
        # Filter and clean words - remove entries with special characters and keep compound words intact
        filtered_words = []
        original_to_formatted = {}  # Map formatted words back to originals
        
        for word in words_list:
            # Skip words with special characters that cause issues
            if any(char in word for char in ['[', ']', '{', '}', '|', '*']):
                continue
            # Skip very short words (less than 3 characters)
            if len(word.replace(' ', '').replace('-', '')) < 3:
                continue
            
            # Format compound words for the word search generator
            # Replace spaces with hyphens and convert to uppercase
            formatted_word = word.replace(' ', '-').upper()
            filtered_words.append(formatted_word)
            original_to_formatted[formatted_word] = word.lower()
        
        # Use filtered words
        words_list = filtered_words
        
        # Create word search with words as space-separated string
        words_string = " ".join(words_list)
        ws = WordSearch(
            words=words_string,
            level=3,
            size=20
        )
        
        # Get puzzle as text
        puzzle_text = str(ws)
        
        # Get the words that were actually placed in the puzzle
        placed_words_formatted = [str(word) for word in ws.placed_words]
        unplaced_words_formatted = [str(word) for word in ws.unplaced_words]
        
        # Create the final words list using original format for placed words
        words_list = []
        formatted_to_original = {}  # Map formatted back to original for game logic
        
        for formatted_word in placed_words_formatted:
            if formatted_word in original_to_formatted:
                original_word = original_to_formatted[formatted_word]
                words_list.append(original_word)
                formatted_to_original[formatted_word] = original_word
        
        # Debug info about placement
        print(f"Placed words ({len(words_list)}): {words_list}")
        if unplaced_words_formatted:
            unplaced_originals = [original_to_formatted.get(word, word) for word in unplaced_words_formatted]
            #print(f"Unplaced words ({len(unplaced_originals)}): {unplaced_originals}")
        
        # Check if we have enough words placed (minimum 3)
        if len(words_list) < 3:
            print(f"Word placement failed - only {len(words_list)} words placed. Trying random document...")
            await safe_send(channel, "\u200b\n⚠️ **Word selection issue detected. Selecting random puzzle...**\n\u200b")
            
            # Try to get a completely random document from any category
            try:
                pipeline = [{"$sample": {"size": 1}}]
                documents = [doc async for doc in collection.aggregate(pipeline)]
                
                if documents:
                    selected_doc = documents[0]
                    words_list_fallback = selected_doc.get("words", [])
                    selected_category = selected_doc.get("category", "Random")
                    selected_subcategory = selected_doc.get("subcategory", "Mixed")
                    
                    # Limit and filter words for fallback
                    if len(words_list_fallback) > 15:
                        words_list_fallback = random.sample(words_list_fallback, 15)
                    
                    # Filter and clean words for fallback
                    filtered_words_fallback = []
                    original_to_formatted_fallback = {}
                    
                    for word in words_list_fallback:
                        if any(char in word for char in ['[', ']', '{', '}', '|', '*']):
                            continue
                        if len(word.replace(' ', '').replace('-', '')) < 3:
                            continue
                        formatted_word = word.replace(' ', '-').upper()
                        filtered_words_fallback.append(formatted_word)
                        original_to_formatted_fallback[formatted_word] = word.lower()
                    
                    # Try fallback word search
                    if filtered_words_fallback:
                        words_string_fallback = " ".join(filtered_words_fallback)
                        ws_fallback = WordSearch(words=words_string_fallback, level=3, size=20)
                        puzzle_text = str(ws_fallback)
                        
                        placed_words_formatted = [str(word) for word in ws_fallback.placed_words]
                        words_list = []
                        formatted_to_original = {}
                        
                        for formatted_word in placed_words_formatted:
                            if formatted_word in original_to_formatted_fallback:
                                original_word = original_to_formatted_fallback[formatted_word]
                                words_list.append(original_word)
                                formatted_to_original[formatted_word] = original_word
                        
                        print(f"Fallback placed words ({len(words_list)}): {words_list}")
                        
                        if len(words_list) < 3:
                            # Still failed, use a hardcoded simple word list
                            words_list = ["cat", "dog", "sun", "moon", "star", "tree", "book", "game"]
                            ws_simple = WordSearch(words=" ".join([w.upper() for w in words_list]), level=1, size=15)
                            puzzle_text = str(ws_simple)
                            selected_category = "Simple Words"
                            selected_subcategory = "Basic"
                            print("Using simple hardcoded word list as final fallback")
                            
            except Exception as fallback_error:
                print(f"Fallback failed: {fallback_error}")
                # Final fallback to simple words
                words_list = ["cat", "dog", "sun", "moon", "star", "tree", "book", "game"]
                ws_simple = WordSearch(words=" ".join([w.upper() for w in words_list]), level=1, size=15)
                puzzle_text = str(ws_simple)
                selected_category = "Simple Words"
                selected_subcategory = "Basic"
                print("Using simple hardcoded word list as emergency fallback")
        
        # Convert text to image using PIL
        puzzle_buffer = create_word_search_image(puzzle_text)
            
    except Exception as e:
        print(f"Error generating word search: {e}")
        await safe_send(channel, "\u200b\n❌ **Failed to generate puzzle! Please try again.**\n\u200b")
        wf_winner = True
        return None
    
    # Game setup
    GAME_DURATION = 45
    user_scores = {}  # {user_id: {"name": display_name, "words": [list of words found]}}
    found_words = set()  # Track which words have been found
    remaining_words = set(word.upper().replace(' ', '').replace('-', '') for word in words_list)
    
    # Send puzzle
    puzzle_buffer.seek(0)
    puzzle_file = discord.File(puzzle_buffer, filename="word_search.png")
    
    embed = discord.Embed(title="🔍 Word Search Challenge", color=0x3498db)
    embed.description = f"**Category:** {selected_category}\n**Subcategory:** {selected_subcategory}\n**Words Found:** 0/{len(words_list)}"
    embed.set_image(url="attachment://word_search.png")
    embed.set_footer(text="🎯 **Game Started!** Start typing words you find!\n\n✨ Messages will erase during game.")
    
    game_message = await safe_send(channel, embed=embed, file=puzzle_file)
    
    # No separate tracking message needed - will update the main game message only
    
    # Game loop
    game_start_time = asyncio.get_event_loop().time()
    last_update_time = game_start_time
    
    def game_check(m):
        return m.channel == channel and m.author != bot.user
    
    while (asyncio.get_event_loop().time() - game_start_time < GAME_DURATION and 
           len(remaining_words) > 0):
        try:
            current_time = asyncio.get_event_loop().time()
            remaining_time = GAME_DURATION - (current_time - game_start_time)
            
            msg = await bot.wait_for("message", timeout=2, check=game_check)
            
            # Delete the user's guess message to keep chat clean
            try:
                await msg.delete()
            except:
                pass
            
            guess = msg.content.strip().upper().replace(' ', '').replace('-', '')
            original_guess = msg.content.strip()  # Keep original format for display
            user_id = msg.author.id
            display_name = msg.author.display_name
            
            # Check if the guess matches any remaining word
            if guess in remaining_words:
                remaining_words.remove(guess)
                found_words.add(guess)
                
                # Update user score
                if user_id not in user_scores:
                    user_scores[user_id] = {"name": display_name, "words": []}
                user_scores[user_id]["words"].append(original_guess)
                
                # Found words info will be added to the main embed below
                
                # Update the original puzzle image when a word is found
                try:
                    # Create updated puzzle with crossed out words
                    found_list = list(found_words)
                    
                    # Generate updated puzzle image showing found words
                    updated_buffer = create_word_search_image(puzzle_text, found_words=found_list)
                    
                    if updated_buffer and len(updated_buffer.getvalue()) > 0:
                        updated_buffer.seek(0)
                        updated_file = discord.File(updated_buffer, filename="word_search.png")
                        
                        # Build the list of found words grouped by user
                        found_entries = []
                        for uid, user_data in user_scores.items():
                            if user_data["words"]:
                                words_list_str = ", ".join(user_data["words"])
                                found_entries.append(f"🎉 **{user_data['name']}** found: {words_list_str}")
                        
                        # Update the original embed with current progress
                        embed_update = discord.Embed(title="🔍 Word Search Challenge", color=0x27ae60 if len(remaining_words) == 0 else 0x3498db)
                        
                        # Create description with found words information
                        description = f"**Category:** {selected_category}\n**Subcategory:** {selected_subcategory}\n**Words Found:** {len(found_words)}/{len(words_list)}"
                        if found_entries:
                            description += "\n\n" + "\n".join(found_entries)
                        
                        embed_update.description = description
                        embed_update.set_image(url="attachment://word_search.png")
                        embed_update.set_footer(text="🎯 Game Started! Start typing words you find!\n\n✨ Messages will erase during game.")
                        
                        # Edit the original game message to show updated progress
                        await game_message.edit(embed=embed_update, attachments=[updated_file])
                    last_update_time = current_time
                except Exception as e:
                    print(f"Error updating puzzle: {e}")
                        
                if len(remaining_words) == 0:
                    break
                    
        except asyncio.TimeoutError:
            # Check for time updates
            current_time = asyncio.get_event_loop().time()
            remaining_time = GAME_DURATION - (current_time - game_start_time)
            
            if current_time - last_update_time > 60:  # Update every minute
                embed_update = discord.Embed(title="🔍 Word Search Status", color=0xf39c12)
                embed_update.add_field(name="Found", value=f"{len(found_words)}/{len(words_list)}", inline=True)
                await safe_send(channel, embed=embed_update)
                last_update_time = current_time
                
            continue
        except Exception as e:
            print(f"Error in game loop: {e}")
            continue
    
    # Game over - show final results
    try:
        # Use the ORIGINAL puzzle text to show solution, not a new random one
        # Convert original puzzle text to solution image
        solution_buffer = create_word_search_image(puzzle_text, found_words=found_words, is_solution=True, words_list=words_list)
            
    except Exception as e:
        print(f"Error generating solution: {e}")
        solution_buffer = None
    
    # Final results
    if len(remaining_words) == 0:
        final_message = "\u200b\n🏆 **PUZZLE COMPLETE!** All words found!\n\u200b"
    else:
        final_message = "\u200b\n⏰ **Time's Up!**\n\u200b"
    
    # Update the main game message one final time
    try:
        # Build final found words list
        found_entries = []
        if user_scores:
            for user_id, user_data in user_scores.items():
                if user_data["words"]:
                    words_list_str = ", ".join(user_data["words"])
                    found_entries.append(f"🎉 **{user_data['name']}** found: {words_list_str}")
        
        # Create final embed
        final_embed = discord.Embed(
            title="🔍 Word Search Challenge", 
            color=0x27ae60 if len(remaining_words) == 0 else 0xe67e22
        )
        
        # Create final description 
        game_status = "🏆 **GAME COMPLETE!**" if len(remaining_words) == 0 else "⏰ **TIME'S UP!**"
        description = f"**Category:** {selected_category}\n**Subcategory:** {selected_subcategory}\n**Words Found:** {len(found_words)}/{len(words_list)} - {game_status}"
        if found_entries:
            description += "\n\n" + "\n".join(found_entries)
        
        final_embed.description = description
        final_embed.set_image(url="attachment://word_search.png")
        final_embed.set_footer(text="🎮 Game Complete! Thanks for playing!")
        
        # Edit the main game message with final status
        await game_message.edit(embed=final_embed)
    except Exception as e:
        print(f"Error updating final game message: {e}")
    
    await safe_send(channel, final_message)
    await asyncio.sleep(2)
    
    # Show scores
    if user_scores:
        sorted_users = sorted(user_scores.items(), key=lambda x: len(x[1]["words"]), reverse=True)
        
        scores_embed = discord.Embed(title="🏆 Final Scores", color=0xffd700)
        
        for i, (user_id, data) in enumerate(sorted_users[:5]):
            name = data["name"]
            word_count = len(data["words"])
            words_found = ", ".join(data["words"])
            
            if i == 0:
                scores_embed.add_field(name=f"🥇 {name}", value=f"{word_count} words: {words_found}", inline=False)
            elif i == 1:
                scores_embed.add_field(name=f"🥈 {name}", value=f"{word_count} words: {words_found}", inline=False)
            elif i == 2:
                scores_embed.add_field(name=f"🥉 {name}", value=f"{word_count} words: {words_found}", inline=False)
            else:
                scores_embed.add_field(name=f"{i+1}. {name}", value=f"{word_count} words: {words_found}", inline=False)
        
        await safe_send(channel, embed=scores_embed)
        
        # Announce the winner
        winner_id, winner_data = sorted_users[0]
        winner_name = winner_data["name"]
        words_found_count = len(winner_data["words"])
        await safe_send(channel, f"\u200b\n🎉🥇 The winner is **{winner_name}** with **{words_found_count}** words found!\n\u200b")
    else:
        await safe_send(channel, "\u200b\n😢 **No words were found!**\n\u200b")
    
    await asyncio.sleep(2)
    
    # Show solution
    if solution_buffer:
        solution_buffer.seek(0)
        solution_file = discord.File(solution_buffer, filename="word_search_solution.png")
        
        solution_embed = discord.Embed(title="📋 Solution", color=0x95a5a6)
        
        # Separate found and not found words
        all_found_words = set()
        for user_data in user_scores.values():
            all_found_words.update(word.lower() for word in user_data["words"])
        
        words_found = [word for word in words_list if word.lower() in all_found_words]
        words_not_found = [word for word in words_list if word.lower() not in all_found_words]
        
        if words_found:
            solution_embed.add_field(name="Words Found", value=", ".join(words_found), inline=False)
        if words_not_found:
            solution_embed.add_field(name="Words Not Found", value=", ".join(words_not_found), inline=False)
        solution_embed.set_image(url="attachment://word_search_solution.png")
        
        await safe_send(channel, embed=solution_embed, file=solution_file)
    else:
        # Just show the word list
        solution_embed = discord.Embed(title="📋 Solution", color=0x95a5a6)
        
        # Separate found and not found words
        all_found_words = set()
        for user_data in user_scores.values():
            all_found_words.update(word.lower() for word in user_data["words"])
        
        words_found = [word for word in words_list if word.lower() in all_found_words]
        words_not_found = [word for word in words_list if word.lower() not in all_found_words]
        
        if words_found:
            solution_embed.add_field(name="Words Found", value=", ".join(words_found), inline=False)
        if words_not_found:
            solution_embed.add_field(name="Words Not Found", value=", ".join(words_not_found), inline=False)
        await safe_send(channel, embed=solution_embed)
    
    # Clean up any temporary files (if any were created)
    try:
        if os.path.exists("test_puzzle.pdf"):
            os.remove("test_puzzle.pdf")
    except:
        pass
    
    wf_winner = True
    await asyncio.sleep(3)
    
    # Return winner (user who found the most words)
    if user_scores:
        winner_id = max(user_scores.items(), key=lambda x: len(x[1]["words"]))[0]
        return winner_id    
    else:
        return None



async def ask_okrace_challenge(winner, winner_id, num=1):
    global wf_winner
    wf_winner = True
    
    # Configuration
    MAX_RACERS = 10
    JOIN_TIMEOUT = 20
    TRACK_LEN = 10
    TARGET_RANGE = (1, 4)
    
    # Competitive step awards: 1st=3, 2nd=2, 3rd=1, rest=0
    
    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/okrace1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/okrace2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/okrace3.gif",
    ]
    gif_url = random.choice(gifs)
    
    await safe_send(channel, content="\u200b\n🏁🥒 **OkRACE**: **O**kra's **K**razy **R**ace **A**dventure!!\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)
    
    # Join Phase
    join_message = await safe_send(channel, f"\u200b\n🚦 **Join the OkRACE!**\n\n**React** with a **unique emoji** to claim your racer!\n\nUp to **{MAX_RACERS}** players get in!\n\u200b")
    
    # Wait for reactions during join phase
    emoji_to_user = {}
    user_to_emoji = {}
    user_names = {}  # Store display names
    
    start_time = asyncio.get_event_loop().time()
    
    def reaction_check(reaction, user):
        return (reaction.message.id == join_message.id and 
                user != bot.user and 
                len(emoji_to_user) < MAX_RACERS)
    
    # Monitor reactions for join period
    while (asyncio.get_event_loop().time() - start_time < JOIN_TIMEOUT and 
           len(emoji_to_user) < MAX_RACERS):
        try:
            timeout_remaining = JOIN_TIMEOUT - (asyncio.get_event_loop().time() - start_time)
            reaction, user = await bot.wait_for('reaction_add', timeout=timeout_remaining, check=reaction_check)
            
            emoji_str = str(reaction.emoji)
            
            # Check if emoji is already taken or user already joined
            if emoji_str not in emoji_to_user and user.id not in user_to_emoji:
                emoji_to_user[emoji_str] = user.id
                user_to_emoji[user.id] = emoji_str
                user_names[user.id] = user.display_name  # Store display name
                
                if len(emoji_to_user) >= MAX_RACERS:
                    break
        except asyncio.TimeoutError:
            break
    
    if len(emoji_to_user) == 0:
        await safe_send(channel, "\u200b\n😢 No one joined the race! Maybe next time.\n\u200b")
        wf_winner = True
        return None
    
    if len(emoji_to_user) == 10:
        user_id = list(emoji_to_user.values())[0]
        user_name = user_names[user_id]
        await safe_send(channel, f"\u200b\n🏃‍♂️ Only **{user_name}** joined! They win by default!\n\u200b")
        wf_winner = True
        return user_id
    
    # Announce final roster
    roster_text = f"\u200b\n🏁 **Final Roster ({len(emoji_to_user)} racers)**\n\n"
    for emoji, user_id in emoji_to_user.items():
        user_name = user_names[user_id]
        roster_text += f"{emoji} **{user_name}**\n"
    roster_text += "\u200b"
    await safe_send(channel, roster_text)
    await asyncio.sleep(2)
    
    # Initialize race state
    positions = {user_id: 0 for user_id in emoji_to_user.values()}
    first_msg_time = {}
    
    round_count = 0
    winners = []
    MAX_ROUNDS = 10
    
    # Race loop
    while not winners and round_count < MAX_ROUNDS:
        round_count += 1
        # Generate random decimal time between 1.0 and 5.0 to the tenth place
        target_time = round(random.uniform(TARGET_RANGE[0], TARGET_RANGE[1]), 1)
        first_msg_time.clear()
        
        await safe_send(channel, f"\u200b\n⏱️ **Round {round_count}**\n\nSend **x**, then **x** again after...\n\n**{target_time}** seconds\n\u200b")
        
        start_round_time = asyncio.get_event_loop().time()
        processed_users = set()
        round_results = {}  # user_id: {"delta": float, "error": float, "name": str}
        
        def message_check(m):
            return (m.channel == channel and 
                    m.author != bot.user and 
                    m.content.strip().lower() == 'x' and 
                    m.author.id in user_to_emoji)
        
        # Wait for messages for 15 seconds
        while asyncio.get_event_loop().time() - start_round_time < 20:
            try:
                timeout_remaining = 15 - (asyncio.get_event_loop().time() - start_round_time)
                msg = await bot.wait_for('message', timeout=timeout_remaining, check=message_check)
                
                user_id = msg.author.id
                current_time = msg.created_at.timestamp()
                
                if user_id not in first_msg_time:
                    # First 'x' message
                    first_msg_time[user_id] = current_time
                elif user_id not in processed_users:
                    # Second 'x' message
                    delta = current_time - first_msg_time[user_id]
                    error = abs(delta - target_time)
                    
                    round_results[user_id] = {
                        "delta": delta,
                        "error": error,
                        "name": msg.author.display_name
                    }
                    processed_users.add(user_id)
                    
            except asyncio.TimeoutError:
                break
        
        # Now rank by accuracy and award steps
        if round_results:
            # Sort by error (lowest error = most accurate)
            sorted_results = sorted(round_results.items(), key=lambda x: x[1]["error"])
            
            for rank, (user_id, result) in enumerate(sorted_results):
                # Award steps based on rank: 1st=3, 2nd=2, 3rd=1, rest=0
                if rank == 0:
                    steps = 3
                elif rank == 1:
                    steps = 2
                elif rank == 2:
                    steps = 1
                else:
                    steps = 0
                
                positions[user_id] = min(positions[user_id] + steps, TRACK_LEN)
                
                emoji = user_to_emoji[user_id]
                rank_text = ["🥇 1st", "🥈 2nd", "🥉 3rd"][rank] if rank < 3 else f"{rank + 1}th"
                await safe_send(channel, f"{emoji} **{result['name']}**: {result['delta']:.2f}s (off by {result['error']:.2f}) → {rank_text} → {steps} steps")
        
        await asyncio.sleep(2)
        
        # Update and display track
        track_display = f"\u200b\n🏁 **OkRACE Track**\n\n"
        for user_id, position in sorted(positions.items(), key=lambda x: x[1], reverse=True):
            emoji = user_to_emoji[user_id]
            user_name = user_names[user_id]
            
            track_line = ""
            for pos in range(TRACK_LEN + 1):
                if pos == position:
                    track_line += emoji
                elif pos == TRACK_LEN:
                    track_line += "🏆"
                else:
                    track_line += "·"
            track_display += f"{track_line} **{user_name}** ({position}/{TRACK_LEN})\n"
        
        track_display += "\u200b"
        await safe_send(channel, track_display)
        
        # Check for winners
        for user_id, position in positions.items():
            if position >= TRACK_LEN:
                winners.append(user_id)
        
        if winners:
            break
            
        await asyncio.sleep(3)
    
    # Announce results
    if winners:
        # Someone reached the finish line
        if len(winners) == 1:
            winner_name = user_names[winners[0]]
            winner_emoji = user_to_emoji[winners[0]]
            await safe_send(channel, f"\u200b\n🎉🏆 **WINNER!**\n\n{winner_emoji} **{winner_name}** wins OkRACE!\n\u200b")
        else:
            winners_text = "\u200b\n🎉🏆 **TIE! Winners:**\n"
            for winner_id in winners:
                winner_name = user_names[winner_id]
                winner_emoji = user_to_emoji[winner_id]
                winners_text += f"{winner_emoji} **{winner_name}**\n"
            winners_text += "\u200b"
            await safe_send(channel, winners_text)
        
        wf_winner = True
        await asyncio.sleep(3)
        return winners[0]  # Return first winner for consistency
    elif round_count >= MAX_ROUNDS:
        # Reached max rounds without a winner - declare closest to finish as winner
        await safe_send(channel, f"\u200b\n⏰ **{MAX_ROUNDS} rounds completed!** Time to crown a winner based on position!\n\u200b")
        
        # Find the player(s) with the highest position
        max_position = max(positions.values())
        leaders = [user_id for user_id, pos in positions.items() if pos == max_position]
        
        if len(leaders) == 1:
            leader_name = user_names[leaders[0]]
            leader_emoji = user_to_emoji[leaders[0]]
            await safe_send(channel, f"\u200b\n🥇🏆 **CLOSEST TO VICTORY!**\n\n{leader_emoji} **{leader_name}** wins with {max_position}/{TRACK_LEN} steps!\n\u200b")
            wf_winner = True
            await asyncio.sleep(3)
            return leaders[0]
        else:
            leaders_text = f"\u200b\n🤝🏆 **TIE FOR THE LEAD!** (All at {max_position}/{TRACK_LEN} steps)\n"
            for leader_id in leaders:
                leader_name = user_names[leader_id]
                leader_emoji = user_to_emoji[leader_id]
                leaders_text += f"{leader_emoji} **{leader_name}**\n"
            leaders_text += "\u200b"
            await safe_send(channel, leaders_text)
            wf_winner = True
            await asyncio.sleep(3)
            return leaders[0]  # Return first leader for consistency
    else:
        # This shouldn't happen, but just in case
        await safe_send(channel, "\u200b\n👎😢 **No winners**. Better luck next time!\n\u200b")
        wf_winner = True
        return None


def get_largest_fitting_font(draw, text, box_width, box_height, font_path, padding=6):
    max_width = box_width - padding
    max_height = box_height - padding

    for size in range(100, 1, -1):  # Try from large to small
        font = ImageFont.truetype(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= max_width and text_h <= max_height:
            return font
    return ImageFont.truetype(font_path, 12)  # fallback


def get_text_color_for_background(rgb_color):
    r, g, b = rgb_color
    brightness = (0.299 * r + 0.587 * g + 0.114 * b)
    return "black" if brightness > 160 else "white"
    

def highlight_element(x, y, width, height, hex_color, blank=True, symbol="", highlight_boxes=None):
    SVG_FILENAME = "periodic_table.svg"
    OKRA_FILENAME = "okra.png"
    CROP_BOX = (0, 0, 920, 530)
    OUTPUT_WIDTH = 1200
    OUTPUT_HEIGHT = 750

    base_dir = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(base_dir, SVG_FILENAME)
    okra_path = os.path.join(base_dir, OKRA_FILENAME)

    temp_png_path = os.path.join(base_dir, "temp_rendered.png")
    cairosvg.svg2png(url=svg_path, write_to=temp_png_path, output_width=OUTPUT_WIDTH, output_height=OUTPUT_HEIGHT)

    table_img = Image.open(temp_png_path).convert("RGB").crop(CROP_BOX)
    table_width, table_height = table_img.size

    total_height = table_height + 100  # Black margin of 100px
    final_img = Image.new('RGB', (table_width, total_height), color=(0, 0, 0))
    final_img.paste(table_img, (0, 100))
    draw = ImageDraw.Draw(final_img)

    cropped_x = x - CROP_BOX[0]
    cropped_y = y - CROP_BOX[1] + 100

    if not hex_color:
        hex_color = "#ffffff"
    else:
        hex_color = f"#{hex_color.lstrip('#')}"
    rgb_color = ImageColor.getrgb(hex_color)

    if highlight_boxes:
        for box in highlight_boxes:
            box_x = box["x"] - CROP_BOX[0]
            box_y = box["y"] - CROP_BOX[1] + 100
            box_w = box["width"]
            box_h = box["height"]
            box_color = f"#{box['color'].lstrip('#')}" if box.get("color") else "#ffffff"
            rgb_box_color = ImageColor.getrgb(box_color)

            draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=rgb_box_color)

            box_brightness = 0.299 * rgb_box_color[0] + 0.587 * rgb_box_color[1] + 0.114 * rgb_box_color[2]
            if box_brightness > 186:
                draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], outline="red", width=2)
    else:
        draw.rectangle([cropped_x, cropped_y, cropped_x + width, cropped_y + height], fill=rgb_color)
        brightness = 0.299 * rgb_color[0] + 0.587 * rgb_color[1] + 0.114 * rgb_color[2]
        if brightness > 186:
            draw.rectangle([cropped_x, cropped_y, cropped_x + width, cropped_y + height], outline="red", width=2)

    if not blank and symbol:
        try:
            font_path = os.path.join(base_dir, "fonts", "DejaVuSans.ttf")
            font = get_largest_fitting_font(draw, symbol, width, height, font_path)
        except:
            font = ImageFont.load_default()

        text_color = "black" if brightness > 186 else "white"
        bbox = font.getbbox(symbol)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = cropped_x + (width - text_w) // 2
        text_y = cropped_y + (height - text_h) // 2 - 4
        draw.text((text_x, text_y), symbol, fill=text_color, font=font)

    # === ADD OKRA IMAGE ===
    try:
        okra_img = Image.open(okra_path).convert("RGBA")
        okra_w, okra_h = okra_img.size

        # Black margin is 100px tall → let's use 90% of that height max
        max_okra_height = int(100 * 0.9)  # 90px

        # Also make sure it's not too wide (optional, can add if needed later)
        max_okra_width = int(table_width * 0.6)  # allow up to 60% table width

        scale_h = max_okra_height / okra_h
        scale_w = max_okra_width / okra_w
        #scale_factor = min(scale_h, scale_w, 1.0)  # don't upscale beyond 1.0
        scale_factor = .35

        new_w = int(okra_w * scale_factor)
        new_h = int(okra_h * scale_factor)

        okra_img = okra_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        okra_x = (table_width - new_w) // 2 - 100
        okra_y = (100 - new_h) // 2 + 80 # perfectly centered vertically
        final_img.paste(okra_img, (okra_x, okra_y), okra_img)
    except Exception as e:
        print(f"Failed to overlay okra.png: {e}")

    image_buffer = io.BytesIO()
    final_img.save(image_buffer, format='PNG')
    image_buffer.seek(0)

    return image_buffer


async def ask_element_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    element_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/element1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/element2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/element3.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/element4.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/element5.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/element6.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/element7.gif"
    ]

    gif_url = random.choice(element_gifs)

    await safe_send(channel, content="\u200b\n\u200b\n💧🔥 **Elementary**: Guess Element Name or Group\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    await safe_send(channel, f"\u200b\n🕹️🚀 **<@{winner_id}>**, select the mode:\n\n🧸 **Normal** or 🧨 **Okrap**.\n\u200b")
    try:
        msg = await bot.wait_for("message", timeout=magic_time + 5, check=lambda m: m.author.id == winner_id and m.author != bot.user and m.channel == channel and m.content.lower() in {"normal", "okrap"})
        game_mode = msg.content.lower()
        await msg.add_reaction("✅")
    except asyncio.TimeoutError:
        game_mode = "normal"

    await safe_send(channel, f"\u200b\n💥🤯 Ok...ra! We're going with **{game_mode.upper()}** baby!\n\u200b")
    await asyncio.sleep(2)

    user_data = {}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            recent_element_ids = await get_recent_question_ids_from_mongo("element")
            element_collection = db["element_questions"]
            pipeline_element = [
                {
                    "$match": {
                        "_id": {"$nin": list(recent_element_ids)},
                        "hypothetical": "No",
                        #"question_type": {"$in": ["multiple-single-answer"]}
                }
                },
                {"$sample": {"size": 5}},  
                {
                    "$group": {  
                        "_id": "$question",
                        "question_doc": {"$first": "$$ROOT"}
                    }
                },
                {"$replaceRoot": {"newRoot": "$question_doc"}},  
                {"$sample": {"size": 1}} 
            ]

            element_questions = [doc async for doc in element_collection.aggregate(pipeline_element)]
            element_question = element_questions[0]
            element_question_type = element_question["question_type"]

            if element_question_type == "single":
                element_name = element_question["name"]
                element_source = element_question["name"]
                element_symbol = element_question["symbol"]
                element_category = element_question["category"]
                element_number = element_question["number"]
                element_period = element_question["period"]
                element_group = element_question["group"]
                element_phase = element_question["phase"]
                element_summary = element_question["phase"]
                element_easy = element_question["easy"]
                element_color = element_question["cpk-hex"]
                element_summary = element_question["summary"]
                element_x = element_question["x"]
                element_y = element_question["y"]
                element_width = element_question["width"]
                element_height = element_question["height"]
                element_bohr_url = element_question["bohr_model_image"]
                
            elif element_question_type == "multiple" or element_question_type == "multiple-single-answer":
                element_group = element_question["element_group"]
                num_of_elements = element_question["num_of_elements"]
                element_answers = element_question["answers"]
                element_coordinate_data = element_question["elements"]

            element_category = "element"
            element_url = ""
            element_question_id = element_question["_id"] 

            if element_question_id:
                await store_question_ids_in_mongo([element_question_id], "element")  # Store it as a list containing a single ID
        
        except Exception as e:
            sentry_sdk.capture_exception(e)
            error_details = traceback.format_exc()
            print(f"Error selecting element questions: {e}\nDetailed traceback:\n{error_details}")
            return None  # Return an empty list in case of failure
        
        if element_question_type == "single":
            
            if game_mode == "normal":
                element_crossword_buffer, element_crossword_string = generate_crossword_image(element_name, prefill=0.3)
                element_image_buffer = highlight_element(element_x, element_y, element_width, element_height, element_color, blank=False, symbol=element_symbol)
            else:
                element_image_buffer = highlight_element(element_x, element_y, element_width, element_height, element_color)
            #element_bohr_mxc, element_bohr_width, element_bohr_height = download_image_from_url(element_bohr_url, False, "okra.png") 

        elif element_question_type == "multiple" or element_question_type == "multiple-single-answer":
            highlight_boxes = [
                {
                    "x": el["x"],
                    "y": el["y"],
                    "width": el["width"],
                    "height": el["height"],
                    "color": f"#{el['cpk-hex']}" if el.get('cpk-hex') else "#ffffff"
                }
                for el in element_coordinate_data
            ]
            if game_mode == "normal":
                element_crossword_buffer, element_crossword_string = generate_crossword_image(element_group, prefill=0.3)
                
            element_image_buffer = highlight_element(0, 0, 0, 0, "#ffffff", blank=True, symbol="", highlight_boxes=highlight_boxes)
        
        if element_question_type == "single":
            correct_answers = [element_name]
            element_answers = None
        elif element_question_type == "multiple":
            correct_answers = [answer for answer in element_answers]
        elif element_question_type == "multiple-single-answer":
            correct_answers = [element_group]
        
        print(correct_answers)
        answered = False

        message = "\u200b\n⚠️🚨 **Everyone's in!**\n"
        if element_question_type == "single":
            message += f"\n🗣💬❓ **({round_num}/{num})** Name this **element**.\n"
        elif element_question_type == "multiple-single-answer":
            message += f"\n🗣💬❓ **({round_num}/{num})** What is this **group of elements** called?\n"
        elif element_question_type == "multiple":
            message += f"\n🗣💬❓ **({round_num}/{num})** Name **one element** in this group: **{element_group.upper()}**\n"
        message += "\n\u200b"
            
        file = discord.File(fp=element_image_buffer, filename="element.png")
        embed = discord.Embed()
        embed.set_image(url="attachment://element.png")
        await safe_send(channel, content=message, embed=embed, file=file)   

        if element_question_type == "single":
            if game_mode == "normal":
                redacted_element_summary = replace_element_references(element_summary, element_name=element_name)
            elif game_mode == "okrap":
                redacted_element_summary = replace_element_references(element_summary, element_name=element_name, element_symbol=element_symbol)
            message = f"\n🔍🧪 {redacted_element_summary}\n"
            await safe_send(channel, message)

        if game_mode == "normal" and (element_question_type == "multiple-single-answer" or element_question_type == "single"):
            file = discord.File(fp=element_crossword_buffer, filename="element.png")
            embed = discord.Embed()
            embed.set_image(url="attachment://element.png")
            await safe_send(channel, embed=embed, file=file)   

        start_time = asyncio.get_event_loop().time()

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 20 and not answered:
            try:
                msg = await bot.wait_for("message", timeout=20 - (asyncio.get_event_loop().time() - start_time), check=check)
                guess = normalize_text(msg.content).replace(" ", "")
                user = msg.author.display_name
                uid = msg.author.id
                for correct in correct_answers:
                    normalized_answer = normalize_text(correct).replace(" ", "")
                    if (((guess == normalized_answer or guess[:-1] == normalized_answer) and game_mode == "okrap") or (fuzzy_match(guess, normalized_answer, element_category, element_url) and game_mode == "normal")):
                        await msg.add_reaction("✅")
                        await safe_send(channel, f"\u200b\n✅🎉 **<@{uid}>** got it! **{correct.upper()}**\n\u200b")
                        user_data[uid] = (user, user_data.get(uid, (user, 0))[1] + 1)
                        message = ""
                        if element_answers:
                            formatted_answers = ", ".join(name.title() for name in element_answers)
                            message += f"\n🗒️📋 Full List\n{formatted_answers}\n"
                            await safe_send(channel, message)
                        answered = True
                        break
            except asyncio.TimeoutError:
                break

        if not answered:
            if element_question_type == "single":
                message = f"\u200b\n❌😢 No one got it.\n\nAnswer: **{element_name.upper()}**\n\u200b"
            if element_question_type == "multiple-single-answer":
                message = f"\u200b\n❌😢 No one got it.\n\nAnswer: **{element_group.upper()}**\n\u200b"
                formatted_answers = ", ".join(name.title() for name in element_answers)
                message += f"\u200b\n🗒️📋 **Full List**\n{formatted_answers}\n\u200b"
            if element_question_type == "multiple":
                formatted_answers = ", ".join(name.title() for name in element_answers)
                message = f"\u200b\n❌😢 No one got it.\n\n**Full List**\n{formatted_answers}\n\u200b"
            await safe_send(channel, message)

        await asyncio.sleep(1)

        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                element_winner_id, (display_name, final_score) = sorted_users[0]
                return element_winner_id
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        await safe_send(channel, message)
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        element_winner_id, (display_name, final_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return element_winner_id
    else:
        return None



def replace_element_references(element_summary, element_name=None, element_symbol=None):
    modified_summary = element_summary

    if element_name:
        name_pattern = re.compile(re.escape(element_name), re.IGNORECASE)
        modified_summary = name_pattern.sub("OKRA", modified_summary)

    if element_symbol:
        symbol_pattern = re.compile(r'\b' + re.escape(element_symbol) + r'\b', re.IGNORECASE)
        modified_summary = symbol_pattern.sub("OKRA", modified_summary)

    return modified_summary


async def collect_words_from_user(winner, winner_id):
    collected_words = []
    timeout = magic_time + 5
    start_time = asyncio.get_event_loop().time()

    def check(m):
        return m.author.id == winner_id and m.channel == channel and m.author != bot.user

    while asyncio.get_event_loop().time() - start_time < timeout and len(collected_words) < 5:
        try:
            remaining = timeout - (asyncio.get_event_loop().time() - start_time)
            message = await bot.wait_for("message", timeout=remaining, check=check)
            words = message.content.strip().split()
            for word in words:
                if len(collected_words) < 5:
                    collected_words.append(word)
                else:
                    break
        except asyncio.TimeoutError:
            break

    return " ".join(collected_words[:5])


async def translate_text(collected_words: str, lang_code: str, google_api_key: str) -> str:
    url = "https://translation.googleapis.com/language/translate/v2"

    params = {
        "q": collected_words,
        "source": "en",
        "target": lang_code,
        "format": "text",
        "key": google_api_key
    }

    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        raise Exception(f"Non-200 response: {response.status}")
                    data = await response.json()
                    return data['data']['translations'][0]['translatedText']
        except Exception as e:
            print(f"[Attempt {attempt}] Translation failed: {e}")
            if attempt == max_retries:
                return collected_words 


async def ask_polyglottery_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/polyglottery1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/polyglottery2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/polyglottery3.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/polyglottery4.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/polyglottery5.gif"
    ]
    gif_url = random.choice(gifs)

    await safe_send(channel, content="\u200b\n\u200b\n🎰🗣️ **PolygLottery**: Guess the Language\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(5)

    # Collect phrase
    await safe_send(channel, f"\u200b\n✍️🌍 **<@{winner_id}>**, give me **3–5 words** to translate...\n\u200b")
    collected_words = await collect_words_from_user(winner, winner_id)

    if len(collected_words.split()) < 3:
        okra_sentences = [
            "Okra stole my left sock.",
            "I dreamt about okra karaoke.",
            "My okra talks to pigeons.",
            "Dancing okra invaded the office.",
            "Okra wears sunglasses at night.",
            "I married an okra magician.",
            "Okra joined a punk band.",
            "That okra moonwalks on command.",
            "Grandma’s okra knows dark secrets.",
            "Okra challenged me to chess.",
            "We adopted an emotional okra.",
            "Okra runs faster than turtles.",
            "Psychic okra told my future.",
            "The okra demanded a crown.",
            "Okra hosts a cooking podcast.",
            "Three okras rode tiny scooters.",
            "Okra eloped with a mushroom.",
            "Okra formed a jazz quartet.",
            "Why is okra wearing lipstick?",
            "That okra smells like Tuesdays."
        ]
        collected_words = random.choice(okra_sentences)
        await safe_send(channel, f"\u200b\n🤖📢 Not enough words, so I'm picking this:\n\n`{collected_words}`\n\u200b")
    else:
        await safe_send(channel, f"\u200b\n💥🤯 Ok...ra we're going with:\n\n`{collected_words}`\n\u200b")

    await asyncio.sleep(2)

    user_data = {}
    
    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("polyglottery")
            collection = db["polyglottery_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}, "enabled": "1"}},
                {"$sample": {"size": 100}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            q = questions[0]

            lang_code = q["language_code"]
            lang_name = q["language_name"]
            qid = q["_id"]

            if qid:
                await store_question_ids_in_mongo([qid], "polyglottery")
            print(lang_name)

            # Translate
            translated_text = await translate_text(collected_words, lang_code, googletranslate_api_key)
            if translated_text.strip().lower() == collected_words.strip().lower():
                await safe_send(channel, "🌐🔄 Translation matches original. Skipping this round.")
                continue

            # Generate image
            image_buffer = generate_text_image(translated_text, 0, 0, 0, 0, 153, 255, True, "okra.png", lang_code)
            file = discord.File(fp=image_buffer, filename="translation.png")
            embed = discord.Embed().set_image(url="attachment://translation.png")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error fetching or translating:\n{traceback.format_exc()}")
            continue

        await safe_send(channel, f"\u200b\n🗣💬❓ **({round_num}/7)** Name this language:\n\u200b", file=file, embed=embed)

        start_time = asyncio.get_event_loop().time()
        answered = False
        processed_users = set()

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 20 and not answered:
            try:
                timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=timeout, check=check)
                content = message.content.strip()
                user = message.author.display_name
                user_id = message.author.id
                key = (user_id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                if fuzzy_match(content, lang_name, "Polyglottery", ""):
                    await message.add_reaction("✅")
                    await safe_send(channel, f"\u200b\n✅🎉 **<@{user_id}>** got it! **{lang_name.upper()}**\n\u200b")
                    if user_id not in user_data:
                        user_data[user_id] = (user, 0)
                    user_data[user_id] = (user, user_data[user_id][1] + 1)
                    answered = True
            except asyncio.TimeoutError:
                break

        if not answered:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{lang_name.upper()}**\n\u200b")

        await asyncio.sleep(1)

        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                polyglottery_winner_id, (display_name, final_score) = sorted_users[0]
                return polyglottery_winner_id
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        polyglottery_winner_id, (display_name, final_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)

    if sorted_users:
        return polyglottery_winner_id
    else:
        return None



async def ask_dictionary_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/wordnerd_nerds.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/wordnerd_urkel.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/wordnerd_simpsons.gif"
    ]
    gif_url = random.choice(gifs)

    await safe_send(channel, content="\u200b\n\u200b\n🤓📚 **Word Nerd**: What Does It Mean?\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(5)

    user_data = {}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("dictionary")
            collection = db["dictionary_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 100}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            q = questions[0]

            word = q["word"]
            redacted_def = re.compile(re.escape(word), re.IGNORECASE).sub("OKRA", q["definition"])
            word_len = len(word)
            first_char = word[0].upper()
            category = "Dictionary"
            url = ""
            qid = q["_id"]

            if qid:
                await store_question_ids_in_mongo([qid], "dictionary")

            print(f"Word {round_num}: {word}")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting dictionary question:\n{traceback.format_exc()}")
            return

        await safe_send(channel, f"\u200b\n🧠❓ **Word {round_num}**/{num}\n")
        await safe_send(channel, f"\u200b\n🔤 **{first_char}** is the first letter\n🔢 **{word_len}** characters\n\n📘📝 **Definition:** {redacted_def}\n\n🟢💨 **GO!**\n\u200b")

        start_time = asyncio.get_event_loop().time()
        answered = False
        closest_guesses = []
        best_guess_per_user = {}

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 20 and not answered:
            try:
                timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=timeout, check=check)
                content = message.content.strip()
                user = message.author.display_name
                user_id = message.author.id
                similarity = word_similarity(content, word)

                if user_id not in best_guess_per_user or similarity > best_guess_per_user[user_id][2]:
                    best_guess_per_user[user_id] = (user, content, similarity)

                if similarity == 1:
                    await message.add_reaction("✅")
                    await safe_send(channel, f"\u200b\n✅🎉 **<@{user_id}>** got it! **{word.upper()}**\n\u200b")
                    user_data[user_id] = (user, user_data.get(user_id, (user, 0))[1] + 1)
                    answered = True
                    break

            except asyncio.TimeoutError:
                break

        if not answered:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{word.upper()}**\n\u200b")
            sorted_closest = sorted(best_guess_per_user.items(), key=lambda x: x[1][1], reverse=True)
            if sorted_closest:
                await asyncio.sleep(2)
                msg = "\n🔍 Top 3 least worst guesses:\n"
                for i, (uid, (display_name, guess, score)) in enumerate(sorted_closest[:3], 1):
                    msg += f"{i}. **{display_name}**: \"{guess}\" — score: {score:.2f}\n\u200b"
                    current_score = user_data.get(uid, (display_name, 0))[1]
                    user_data[uid] = (display_name, current_score + score * 1.0)
                await safe_send(channel, msg)
                #await asyncio.sleep(1)
                #await safe_send(channel, "\n\u200b🥈🤡 50% credit for your 'effort'.\n\u200b")
    
        await asyncio.sleep(1)

        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                winner_user_id, _ = sorted_users[0]
                return winner_user_id
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        winning_user_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return winning_user_id
    else:
        return None


def generate_text_image(question_text, red_value_bk, green_value_bk, blue_value_bk, red_value_f, green_value_f, blue_value_f, add_okra, okra_path, lang_code="en", font_size=60, highlight_missing_operator=False):
    LANGUAGE_FONT_MAP = {
        "ab": "NotoSans-Regular.ttf",
        "ace": "NotoSans-Regular.ttf",
        "ach": "NotoSans-Regular.ttf",
        "af": "NotoSans-Regular.ttf",
        "ak": "NotoSans-Regular.ttf",
        "alz": "NotoSans-Regular.ttf",
        "am": "NotoSansEthiopic-Regular.ttf",
        "ar": "NotoSansArabic-Regular.ttf",
        "as": "NotoSansBengali-Regular.ttf",
        "awa": "NotoSans-Regular.ttf",
        "ay": "NotoSans-Regular.ttf",
        "az": "NotoSans-Regular.ttf",
        "ba": "NotoSans-Regular.ttf",
        "ban": "NotoSans-Regular.ttf",
        "bbc": "NotoSans-Regular.ttf",
        "be": "NotoSans-Regular.ttf",
        "bem": "NotoSans-Regular.ttf",
        "bew": "NotoSans-Regular.ttf",
        "bg": "NotoSans-Regular.ttf",
        "bho": "NotoSans-Regular.ttf",
        "bik": "NotoSans-Regular.ttf",
        "bm": "NotoSans-Regular.ttf",
        "bn": "NotoSansBengali-Regular.ttf",
        "br": "NotoSans-Regular.ttf",
        "bs": "NotoSans-Regular.ttf",
        "bts": "NotoSans-Regular.ttf",
        "btx": "NotoSans-Regular.ttf",
        "bua": "NotoSans-Regular.ttf",
        "ca": "NotoSans-Regular.ttf",
        "ceb": "NotoSans-Regular.ttf",
        "cgg": "NotoSans-Regular.ttf",
        "chm": "NotoSans-Regular.ttf",
        "ckb": "NotoSansArabic-Regular.ttf",
        "cnh": "NotoSans-Regular.ttf",
        "co": "NotoSans-Regular.ttf",
        "crh": "NotoSans-Regular.ttf",
        "crs": "NotoSans-Regular.ttf",
        "cs": "NotoSans-Regular.ttf",
        "cv": "NotoSans-Regular.ttf",
        "cy": "NotoSans-Regular.ttf",
        "da": "NotoSans-Regular.ttf",
        "de": "NotoSans-Regular.ttf",
        "din": "NotoSans-Regular.ttf",
        "doi": "NotoSans-Regular.ttf",
        "dov": "NotoSans-Regular.ttf",
        "dv": "NotoSansThaana-Regular.ttf",
        "dz": "NotoSansTibetan-Regular.ttf",
        "ee": "NotoSans-Regular.ttf",
        "el": "NotoSans-Regular.ttf",
        "en": "NotoSans-Regular.ttf",
        "eo": "NotoSans-Regular.ttf",
        "es": "NotoSans-Regular.ttf",
        "et": "NotoSans-Regular.ttf",
        "eu": "NotoSans-Regular.ttf",
        "fa": "NotoSansArabic-Regular.ttf",
        "ff": "NotoSans-Regular.ttf",
        "fi": "NotoSans-Regular.ttf",
        "fj": "NotoSans-Regular.ttf",
        "fr": "NotoSans-Regular.ttf",
        "fy": "NotoSans-Regular.ttf",
        "ga": "NotoSans-Regular.ttf",
        "gaa": "NotoSans-Regular.ttf",
        "gd": "NotoSans-Regular.ttf",
        "gl": "NotoSans-Regular.ttf",
        "gn": "NotoSans-Regular.ttf",
        "gom": "NotoSans-Regular.ttf",
        "gu": "NotoSansGujarati-Regular.ttf",
        "ha": "NotoSans-Regular.ttf",
        "haw": "NotoSans-Regular.ttf",
        "he": "NotoSansHebrew-Regular.ttf",
        "hi": "NotoSansDevanagari-Regular.ttf",
        "hil": "NotoSans-Regular.ttf",
        "hmn": "NotoSans-Regular.ttf",
        "hr": "NotoSans-Regular.ttf",
        "hrx": "NotoSans-Regular.ttf",
        "ht": "NotoSans-Regular.ttf",
        "hu": "NotoSans-Regular.ttf",
        "hy": "NotoSansArmenian-Regular.ttf",
        "id": "NotoSans-Regular.ttf",
        "ig": "NotoSans-Regular.ttf",
        "ilo": "NotoSans-Regular.ttf",
        "is": "NotoSans-Regular.ttf",
        "it": "NotoSans-Regular.ttf",
        "iw": "NotoSansHebrew-Regular.ttf",
        "ja": "NotoSansCJKjp-Regular.otf",
        "jv": "NotoSans-Regular.ttf",
        "jw": "NotoSans-Regular.ttf",
        "ka": "NotoSansGeorgian-Regular.ttf",
        "kk": "NotoSans-Regular.ttf",
        "km": "NotoSansKhmer-Regular.ttf",
        "kn": "NotoSansKannada-Regular.ttf",
        "ko": "NotoSansCJKkr-Regular.otf",
        "kri": "NotoSans-Regular.ttf",
        "ktu": "NotoSans-Regular.ttf",
        "ku": "NotoSansArabic-Regular.ttf",
        "ky": "NotoSans-Regular.ttf",
        "la": "NotoSans-Regular.ttf",
        "lb": "NotoSans-Regular.ttf",
        "lg": "NotoSans-Regular.ttf",
        "li": "NotoSans-Regular.ttf",
        "lij": "NotoSans-Regular.ttf",
        "lmo": "NotoSans-Regular.ttf",
        "ln": "NotoSans-Regular.ttf",
        "lo": "NotoSansLao-Regular.ttf",
        "lt": "NotoSans-Regular.ttf",
        "ltg": "NotoSans-Regular.ttf",
        "luo": "NotoSans-Regular.ttf",
        "lus": "NotoSans-Regular.ttf",
        "lv": "NotoSans-Regular.ttf",
        "mai": "NotoSansDevanagari-Regular.ttf",
        "mak": "NotoSans-Regular.ttf",
        "mg": "NotoSans-Regular.ttf",
        "mi": "NotoSans-Regular.ttf",
        "min": "NotoSans-Regular.ttf",
        "mk": "NotoSans-Regular.ttf",
        "ml": "NotoSansMalayalam-Regular.ttf",
        "mn": "NotoSans-Regular.ttf",
        "mni-Mtei": "NotoSansMeeteiMayek-Regular.ttf",
        "mr": "NotoSansDevanagari-Regular.ttf",
        "ms": "NotoSans-Regular.ttf",
        "ms-Arab": "NotoSansArabic-Regular.ttf",
        "mt": "NotoSans-Regular.ttf",
        "my": "NotoSansMyanmar-Regular.ttf",
        "ne": "NotoSansDevanagari-Regular.ttf",
        "new": "NotoSansDevanagari-Regular.ttf",
        "nl": "NotoSans-Regular.ttf",
        "no": "NotoSans-Regular.ttf",
        "nr": "NotoSans-Regular.ttf",
        "nso": "NotoSans-Regular.ttf",
        "nus": "NotoSans-Regular.ttf",
        "ny": "NotoSans-Regular.ttf",
        "oc": "NotoSans-Regular.ttf",
        "om": "NotoSans-Regular.ttf",
        "or": "NotoSansOriya-Regular.ttf",
        "pa": "NotoSansGurmukhi-Regular.ttf",
        "pa-Arab": "NotoSansGurmukhi-Regular.ttf",
        "pag": "NotoSans-Regular.ttf",
        "pam": "NotoSans-Regular.ttf",
        "pap": "NotoSans-Regular.ttf",
        "pl": "NotoSans-Regular.ttf",
        "ps": "NotoSansArabic-Regular.ttf",
        "pt": "NotoSans-Regular.ttf",
        "qu": "NotoSans-Regular.ttf",
        "rn": "NotoSans-Regular.ttf",
        "ro": "NotoSans-Regular.ttf",
        "rom": "NotoSans-Regular.ttf",
        "ru": "NotoSans-Regular.ttf",
        "rw": "NotoSans-Regular.ttf",
        "sa": "NotoSansDevanagari-Regular.ttf",
        "scn": "NotoSans-Regular.ttf",
        "sd": "NotoSansArabic-Regular.ttf",
        "sg": "NotoSans-Regular.ttf",
        "shn": "NotoSansMyanmar-Regular.ttf",
        "si": "NotoSansSinhala-Regular.ttf",
        "sk": "NotoSans-Regular.ttf",
        "sl": "NotoSans-Regular.ttf",
        "sm": "NotoSans-Regular.ttf",
        "sn": "NotoSans-Regular.ttf",
        "so": "NotoSans-Regular.ttf",
        "sq": "NotoSans-Regular.ttf",
        "sr": "NotoSans-Regular.ttf",
        "ss": "NotoSans-Regular.ttf",
        "st": "NotoSans-Regular.ttf",
        "su": "NotoSans-Regular.ttf",
        "sv": "NotoSans-Regular.ttf",
        "sw": "NotoSans-Regular.ttf",
        "szl": "NotoSans-Regular.ttf",
        "ta": "NotoSansTamil-Regular.ttf",
        "te": "NotoSansTelugu-Regular.ttf",
        "tet": "NotoSans-Regular.ttf",
        "tg": "NotoSans-Regular.ttf",
        "th": "NotoSansThai-Regular.ttf",
        "ti": "NotoSansEthiopic-Regular.ttf",
        "tk": "NotoSans-Regular.ttf",
        "tl": "NotoSans-Regular.ttf",
        "tn": "NotoSans-Regular.ttf",
        "tr": "NotoSans-Regular.ttf",
        "ts": "NotoSans-Regular.ttf",
        "tt": "NotoSans-Regular.ttf",
        "ug": "NotoSansArabic-Regular.ttf",
        "uk": "NotoSans-Regular.ttf",
        "ur": "NotoSansArabic-Regular.ttf",
        "uz": "NotoSans-Regular.ttf",
        "vi": "NotoSans-Regular.ttf",
        "xh": "NotoSans-Regular.ttf",
        "yi": "NotoSansHebrew-Regular.ttf",
        "yo": "NotoSans-Regular.ttf",
        "yua": "NotoSans-Regular.ttf",
        "yue": "NotoSansCJKtc-Regular.otf",
        "zh": "NotoSansCJKsc-Regular.otf",
        "zh-CN": "NotoSansCJKsc-Regular.otf",
        "zh-TW": "NotoSansCJKtc-Regular.otf",
        "zu": "NotoSans-Regular.ttf",
        "default": "NotoSans-Regular.ttf",
    }

    background_color = (red_value_bk, green_value_bk, blue_value_bk)
    text_color = (red_value_f, green_value_f, blue_value_f)

    img_width, img_height = 800, 600
    font_file = LANGUAGE_FONT_MAP.get(lang_code, LANGUAGE_FONT_MAP["default"])
    font_path = os.path.join(os.path.dirname(__file__), "fonts", font_file)
    #font_size = 60
    img = Image.new('RGB', (img_width, img_height), color=background_color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None

    if highlight_missing_operator:
        # Force black background, white text, red '?'
        background_color = (0, 0, 0)
        text_color = (255, 255, 255)
    
        # Replace all ⬜ (U+2B1C) or placeholders with red '?'
        parts = question_text.split("⬜")
        rendered_parts = []
        for i, part in enumerate(parts):
            rendered_parts.append((part, text_color))
            if i < len(parts) - 1:
                rendered_parts.append((" _ ", (255, 0, 0)))  # red question mark
    
        # Now calculate total dimensions for mixed-color text
        total_width = 0
        max_height = 0
        for text, color in rendered_parts:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            total_width += w
            max_height = max(max_height, h)
    
        text_x = (img_width - total_width) // 2
        text_y = (img_height - max_height) // 2
    
        # Clear and draw styled text
        img = Image.new('RGB', (img_width, img_height), color=background_color)
        draw = ImageDraw.Draw(img)
    
        for text, color in rendered_parts:
            draw.text((text_x, text_y), text, fill=color, font=font)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_x += text_width + 10 
    
    else:
        wrapped_text = "\n".join(draw_text_wrapper(question_text, font, img_width - 40))
        text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = (img_width - text_width) // 2
        text_y = (img_height - text_height) // 2
    
        draw.multiline_text((text_x, text_y), wrapped_text, fill=text_color, font=font, align="center")
    
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)

    return image_buffer


def evaluate_expression(numbers, operators_seq):
    """Evaluate an expression given numbers and a tuple of operators."""
    expression = str(numbers[0])
    for i in range(len(operators_seq)):
        expression += f" {operators_seq[i]} {numbers[i + 1]}"
    try:
        result = eval(expression)
        return result if result == int(result) else None
    except ZeroDivisionError:
        return None
    except Exception:
        return None


def generate_math_puzzle(n):
    """Generate a puzzle with exactly ONE valid operator combo that results in an integer."""
    while True:
        nums = [random.randint(1, 10) for _ in range(n + 1)]
        op_combos = list(product(ops.keys(), repeat=n))
        valid_solutions = []

        for operator_seq in op_combos:
            result = evaluate_expression(nums, operator_seq)
            if result is not None:
                valid_solutions.append((operator_seq, int(result)))

        # Group results by value
        result_to_ops = {}
        for op_seq, res in valid_solutions:
            if res not in result_to_ops:
                result_to_ops[res] = []
            result_to_ops[res].append(op_seq)

        # Find results with exactly one valid operator sequence
        unique_results = [(res, op_seqs[0]) for res, op_seqs in result_to_ops.items() if len(op_seqs) == 1]

        if unique_results:
            selected_result, selected_ops = random.choice(unique_results)
            math_string = " ⬜ ".join(str(num) for num in nums) + f" = {selected_result}"
            operator_string = "".join(selected_ops)

            return {
                "math_string": math_string,
                "answer_string": operator_string
            }


async def ask_math_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/math1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/math2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/math3.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/math5.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/math7.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/math8.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/math9.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/math10.gif"
    ]

    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n\u200b\n➕➖ **Sign Language**: Fill in the Missing Signs\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    await safe_send(channel, f"\u200b\n🔢❓ **<@{winner_id}>**, how many missing signs? **[2 or 3]**\n\u200b")

    user_number = None
    start_time = asyncio.get_event_loop().time()

    def check(m):
        return m.author.id == winner_id and m.channel == channel and m.author != bot.user and m.content.strip() in {"2", "3"}

    while asyncio.get_event_loop().time() - start_time < magic_time + 5:
        try:
            timeout = magic_time + 5 - (asyncio.get_event_loop().time() - start_time)
            msg = await bot.wait_for("message", timeout=timeout, check=check)
            user_number = int(msg.content.strip())
            await msg.add_reaction("🧠")
            break
        except asyncio.TimeoutError:
            break

    if user_number:
        await safe_send(channel, f"\u200b\n💥🤯 Ok...ra! We're going with **{user_number}** missing signs!\n\u200b")
    else:
        user_number = 2
        await safe_send(channel, f"\u200b\n⏱️ Time's up! Defaulting to **2** missing signs!\n\u200b")

    await asyncio.sleep(2)

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    user_data = {}

    round_num = 1
    while round_num <= num:
        puzzle = generate_math_puzzle(user_number)
        math_string = puzzle["math_string"]
        answer_string = puzzle["answer_string"]
        emoji_map = {'+': '➕', '-': '➖', '*': '✖️', '/': '➗'}
        pretty_answer_string = ''.join(emoji_map.get(c, c) for c in answer_string)

        print(f"Puzzle: {math_string} | Answer: {answer_string}")

        image_buffer = generate_text_image(math_string, 0, 0, 0, 255, 255, 255, True, "okra.png", highlight_missing_operator=True)
        file = discord.File(fp=image_buffer, filename="math.png")
        embed = discord.Embed().set_image(url="attachment://math.png")

        prompt = (
            f"\u200b\n⚠️🚨 Everyone's in!\n"
            f"\u200b\n✖️🧠 Equation {round_num}/{num}: Use **[+ - /\\ * x]**\n\u200b"
        )

        await safe_send(channel, content=prompt, file=file, embed=embed)

        start_time = asyncio.get_event_loop().time()
        answered = False
        processed_users = set()

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 20 and not answered:
            try:
                timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                msg = await bot.wait_for("message", timeout=timeout, check=check)
                content = msg.content.strip().replace(" ", "").replace("x", "*").replace("\\", "/").lower()
                user = msg.author.display_name
                user_id = msg.author.id
                key = (user_id, content)

                if key in processed_users:
                    continue
                processed_users.add(key)

                if content == answer_string:
                    await msg.add_reaction("✅")
                    await safe_send(channel, f"\u200b\n✅🎉 **<@{user_id}>** got it! {pretty_answer_string}\n\u200b")
                    if user_id not in user_data:
                        user_data[user_id] = (user, 0)
                    user_data[user_id] = (user, user_data[user_id][1] + 1)
                    answered = True
            except asyncio.TimeoutError:
                break

        if not answered:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{pretty_answer_string}**\n\u200b")

        await asyncio.sleep(1)

        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                math_winner_id, (display_name, final_score) = sorted_users[0]
                return math_winner_id
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        math_winner_id, (display_name, final_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return math_winner_id
    else:
        return None


async def ask_music_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    music_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/music1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/music2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/music3.gif",
    ]

    gif_url = random.choice(music_gifs)
    await safe_send(channel, content="\u200b\n🎼🎵 **MusIQ**: Name the Notes\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    await safe_send(channel, f"\u200b\n✍️🌍 **<@{winner_id}>**, how many **music notes**? [**2** to **7**]\n\u200b")

    user_number = None
    start_time = asyncio.get_event_loop().time()

    def check(m):
        return m.author.id == winner_id and m.channel == channel and m.author != bot.user and m.content.strip() in {"2", "3", "4", "5", "6", "7"}

    while asyncio.get_event_loop().time() - start_time < magic_time + 5:
        try:
            timeout = magic_time + 5 - (asyncio.get_event_loop().time() - start_time)
            msg = await bot.wait_for("message", timeout=timeout, check=check)
            user_number = int(msg.content.strip())
            await msg.add_reaction("🎵")
            break
        except asyncio.TimeoutError:
            break

    if user_number:
        await safe_send(channel, f"\u200b\n💥🤯 Ok...ra! We're going with **{user_number}** music notes!\n\u200b")
    else:
        user_number = 3
        await safe_send(channel, "\u200b\n😬⏱️ Time's up! We're going with **3** music notes!\n\u200b")

    await asyncio.sleep(2)

    if num > 1:
        await safe_send(channel, f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b")
        await asyncio.sleep(3)

    user_data = {}
    music_num = 1

    while music_num <= num:
        music_mxc, music_answer = generate_music_puzzle(user_number)
        print(f"Music Notes: {music_answer}")

        image_file = discord.File(music_mxc, filename="music.png")  # Adjust if needed
        embed = discord.Embed().set_image(url="attachment://music.png")

        message = f"\u200b\n⚠️🚨 Everyone's in!\n\n🎼🔢 **Sequence {music_num}** of {num} (Treble Clef 𝄞)\n\u200b"
        await safe_send(channel, content=message, file=image_file, embed=embed)
        await asyncio.sleep(2)

        start_time = asyncio.get_event_loop().time()
        answered = False
        processed_users = set()

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 20 and not answered:
            try:
                timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                msg = await bot.wait_for("message", timeout=timeout, check=check)
                user = msg.author.display_name
                user_id = msg.author.id
                guess = msg.content.strip().replace(" ", "").replace(",", "").lower()
                correct = music_answer[1].replace(" ", "").replace(",", "").lower()

                key = (user_id, guess)
                if key in processed_users:
                    continue
                processed_users.add(key)

                if guess == correct:
                    await msg.add_reaction("✅")
                    await safe_send(channel, f"\u200b\n✅🎉 Correct! **<@{user_id}>** got it! **{music_answer[1]}**\n\u200b")
                    if user_id not in user_data:
                        user_data[user_id] = (user, 0)
                    user_data[user_id] = (user, user_data[user_id][1] + 1)
                    answered = True
            except asyncio.TimeoutError:
                break

        if not answered:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{music_answer[1]}**\n\u200b")

        await asyncio.sleep(2)
        music_num += 1

        message = ""
        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                music_winner_id, (display_name, final_score) = sorted_users[0]
                return music_winner_id
            else:
                return None

        if sorted_users:
            if music_num > num:
                message += "\u200b\n🏁🏆 **Final Standings**\n"
            else:
                message += "\u200b\n📊🏆 **Current Standings**\n"

        for counter, (_, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"

        if message:
            await safe_send(channel, message)
        await asyncio.sleep(2)

    if sorted_users:
        music_winner_id, (display_name, final_score) = sorted_users[0]
        await safe_send(channel, f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b")
    else:
        await safe_send(channel, f"\u200b\n👎😢 No right answers. **I'm ashamed to call you Okrans**.\n\u200b")

    await asyncio.sleep(3)
    
    if sorted_users:
        return music_winner_id
    else:
        return None



def generate_music_puzzle(number_of_notes):
    # Only notes between E4 and F5 inclusive
    allowed_notes = [
        ("E", 4),
        ("F", 4),
        ("G", 4),
        ("A", 4),
        ("B", 4),
        ("C", 5),
        ("D", 5),
        ("E", 5),
        ("F", 5)
    ]

    selected = random.choices(allowed_notes, k=number_of_notes)

    # First string: include octaves to distinguish high/low
    with_octave = [f"{note}{octave}" for note, octave in selected]

    # Second string: just the note names
    without_octave = [note for note, _ in selected]

    music_note_array = [", ".join(with_octave), ", ".join(without_octave)]

    music_buffer = generate_music_image(music_note_array[0])

    return music_buffer, music_note_array


def generate_music_image(note_string):

    if isinstance(note_string, list):
        notes = [n.strip().upper() for n in note_string]
    else:
        notes = [n.strip().upper() for n in note_string.split(',')]

    num_notes = len(notes)

    # Diatonic scale positions relative to E4
    staff_positions = {
        "E4": 0,  # bottom line
        "F4": 1,
        "G4": 2,
        "A4": 3,
        "B4": 4,
        "C5": 5,
        "D5": 6,
        "E5": 7,
        "F5": 8  # top line
    }

    def get_staff_step(note):
        """Return the number of diatonic steps above E4"""
        return staff_positions.get(note, 0)

    # Drawing parameters
    note_spacing = 90
    staff_line_spacing = 20
    left_margin = 40
    right_margin = 40
    top_margin = 40
    bottom_margin = 40

    img_width = left_margin + right_margin + num_notes * note_spacing
    staff_height = 4 * staff_line_spacing
    e4_y = top_margin + 4 * staff_line_spacing  # E4 is the bottom line
    img_height = top_margin + staff_height + bottom_margin

    # Create image
    img = Image.new("RGB", (img_width, img_height), "white")
    draw = ImageDraw.Draw(img)

    # Draw 5 staff lines
    for i in range(5):
        y = e4_y - i * staff_line_spacing
        draw.line([(left_margin, y), (img_width - right_margin, y)], fill="black", width=2)

    # Draw each note
    for i, note in enumerate(notes):
        step = get_staff_step(note)
        x = left_margin + i * note_spacing + 30
        y = e4_y - step * (staff_line_spacing // 2)

        # Draw note head
        draw.ellipse((x - 10, y - 7, x + 10, y + 7), fill="black")

        # Draw stem upward
        draw.line([(x + 10, y), (x + 10, y - 30)], fill="black", width=2)

    # Export to buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)

    if image_buffer:
        return image_buffer
    else:
        print("❌ Failed to get image buffer.")
        return None



async def ask_lyric_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/lyric1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/lyric2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/lyric3.gif"
    ]
    gif_url = random.choice(gifs)

    await safe_send(channel, content="\u200b\n\u200b\n🎧🎤 **LyrIQ**: Name the Song OR Artist\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    # Get 5 random year documents from MongoDB
    recent_ids = await get_recent_question_ids_from_mongo("billboard")
    billboard_collection = db["billboard_questions"]
    pipeline = [
        {"$match": {"_id": {"$nin": list(recent_ids)}}},
        {"$sample": {"size": 5}}
    ]
    year_docs = [doc async for doc in billboard_collection.aggregate(pipeline)]

    if not year_docs:
        await safe_send(channel, "\u200b\n❌ Unable to get year data. Please try again.\n\u200b")
        return None

    # Present year choices to user
    year_choices_message = f"\u200b\n📅🎵 **<@{winner_id}>**, which year's **Billboard Top 100** shall we revisit?\n\n"
    for i, doc in enumerate(year_docs, start=1):
        year_choices_message += f"{i}. **{doc['year']}**\n"
    year_choices_message += "\u200b"
    await safe_send(channel, year_choices_message)

    # Wait for user selection (10 seconds)
    selected_year_doc = None
    start_time = asyncio.get_event_loop().time()
    processed_messages = set()

    while selected_year_doc is None and (asyncio.get_event_loop().time() - start_time) < 10:
        try:
            remaining_time = 10 - (asyncio.get_event_loop().time() - start_time)
            if remaining_time <= 0:
                break

            msg = await bot.wait_for("message",
                                   timeout=remaining_time,
                                   check=lambda m: (m.author.id == winner_id and
                                                  m.channel == channel and
                                                  m.id not in processed_messages))

            processed_messages.add(msg.id)
            user_input = msg.content.strip()

            # Check if it's a valid choice (1-5 or actual year)
            try:
                choice_num = int(user_input)
                # Check if it's a number 1-5
                if 1 <= choice_num <= len(year_docs):
                    selected_year_doc = year_docs[choice_num - 1]
                    await msg.add_reaction("✅")
                    await safe_send(channel, f"\u200b\n✅ **{selected_year_doc['year']}** - What a year!\n\u200b")
                else:
                    # Check if it matches any of the actual years
                    for doc in year_docs:
                        if doc['year'] == choice_num:
                            selected_year_doc = doc
                            await msg.add_reaction("✅")
                            await safe_send(channel, f"\u200b\n✅ **{selected_year_doc['year']}** - What a year!\n\u200b")
                            break
                    if selected_year_doc is None:
                        await msg.add_reaction("❌")
            except ValueError:
                await msg.add_reaction("❌")

        except asyncio.TimeoutError:
            break

    # If no valid year was received, randomly pick one
    if selected_year_doc is None:
        selected_year_doc = random.choice(year_docs)
        await safe_send(channel, f"\u200b\n😬⏱️ Time's up! Randomly selected **{selected_year_doc['year']}**.\n\u200b")

    # Store the selected year document ID in recent IDs
    await store_question_ids_in_mongo([selected_year_doc["_id"]], "billboard")

    # Ask for portion selection (beginning, middle, or end)
    await safe_send(channel, f"\u200b\n🎯 **<@{winner_id}>**, what section of the song should I lookra at?\n\n1. **Beginning**\n2. **Middle**\n3. **End**\n\u200b")

    selected_portion = None
    start_time = asyncio.get_event_loop().time()
    processed_messages = set()

    while selected_portion is None and (asyncio.get_event_loop().time() - start_time) < 10:
        try:
            remaining_time = 10 - (asyncio.get_event_loop().time() - start_time)
            if remaining_time <= 0:
                break

            msg = await bot.wait_for("message",
                                   timeout=remaining_time,
                                   check=lambda m: (m.author.id == winner_id and
                                                  m.channel == channel and
                                                  m.id not in processed_messages))

            processed_messages.add(msg.id)
            user_input = msg.content.strip()

            # Check if it's a valid choice (1-3) or text
            portion_map = {
                "1": "beginning",
                "2": "middle",
                "3": "end",
                "beginning": "beginning",
                "middle": "middle",
                "end": "end"
            }

            if user_input.lower() in portion_map:
                selected_portion = portion_map[user_input.lower()]
                await msg.add_reaction("✅")
                await safe_send(channel, f"\u200b\n✅ **{selected_portion.capitalize()}** - Let's go!\n\u200b")
            else:
                await msg.add_reaction("❌")

        except asyncio.TimeoutError:
            break

    # If no valid portion was received, randomly pick one
    if selected_portion is None:
        selected_portion = random.choice(["beginning", "middle", "end"])
        await safe_send(channel, f"\u200b\n😬⏱️ Time's up! Randomly selected **{selected_portion}**.\n\u200b")

    await asyncio.sleep(2)

    user_data = {}

    # Pre-fetch and validate songs list before starting the game
    songs = selected_year_doc.get("songs", [])
    if not songs:
        await safe_send(channel, "⚠️ No songs found for this year.")
        return None

    if len(songs) < num:
        await safe_send(channel, f"⚠️ Not enough unique songs in {selected_year_doc.get('year', '?')} (only {len(songs)} available, need {num}).")
        return None

    # Pre-select all unique songs for the entire game to prevent duplicates
    selected_songs = random.sample(songs, num)

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            # Use pre-selected song instead of random.choice to guarantee uniqueness
            song = selected_songs[round_num - 1]

            artist = song.get("artist", "Unknown Artist")
            title = song.get("song", "Unknown Song")
            lyrics = song.get("lyrics", "")
            rank = song.get("rank", "?")
            year = selected_year_doc.get("year", "?")

            # Split lyrics into words
            words = lyrics.split()
            total_words = len(words)

            if total_words < 30:
                await safe_send(channel, "⚠️ Not enough lyrics. Skipping this round.")
                round_num = round_num + 1
                continue

            # Determine word range based on selected portion
            if selected_portion == "beginning":
                # First third of the lyrics
                portion_start = 0
                portion_end = max(30, total_words // 3)
            elif selected_portion == "middle":
                # Middle third of the lyrics
                portion_start = total_words // 3
                portion_end = (2 * total_words) // 3
            else:  # end
                # Last third of the lyrics
                portion_start = (2 * total_words) // 3
                portion_end = total_words

            # Ensure we have enough words in the portion
            portion_length = portion_end - portion_start
            if portion_length < 30:
                portion_start = max(0, total_words - 30)
                portion_end = total_words
                portion_length = portion_end - portion_start

            # Pick two different random starting positions for 10-word segments
            # within the selected portion
            max_start = portion_end - 10
            if max_start <= portion_start:
                line1_start = portion_start
                line2_start = portion_start
            else:
                # Randomly select two different starting positions
                available_positions = list(range(portion_start, max_start + 1))
                if len(available_positions) >= 2:
                    selected_positions = random.sample(available_positions, 2)
                    line1_start = selected_positions[0]
                    line2_start = selected_positions[1]
                else:
                    line1_start = portion_start
                    line2_start = min(portion_start + 10, max_start) if max_start > portion_start else portion_start

            line1_words = words[line1_start:line1_start + 20]
            line2_words = words[line2_start:line2_start + 20]

            line1 = f"\"{' '.join(line1_words)}\""
            line2 = f"\"{' '.join(line2_words)}\""

            print(f"{artist} - {title}")

            image_buffer_1 = generate_text_image(line1, 255, 99, 130, 255, 255, 255, True, "okra.png")
            image_buffer_2 = generate_text_image(line2, 255, 99, 130, 255, 255, 255, True, "okra.png")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error fetching lyric:\n{traceback.format_exc()}")
            continue

        await safe_send(channel, f"\u200b\n🎵 **Song {round_num}/{num}**\n\n📅 Year: {year}\n\n🏆 Rank: #{rank}/100\n\u200b")
        file_1 = discord.File(fp=image_buffer_1, filename="lyric1.png")
        embed_1 = discord.Embed().set_image(url="attachment://lyric1.png")
        file_2 = discord.File(fp=image_buffer_2, filename="lyric2.png")
        embed_2 = discord.Embed().set_image(url="attachment://lyric2.png")

        await asyncio.sleep(3)
        await safe_send(channel, file=file_1, embed=embed_1)
        await asyncio.sleep(1)
        await safe_send(channel, file=file_2, embed=embed_2)

        start_time = asyncio.get_event_loop().time()
        answered = False
        processed_users = set()

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 20 and not answered:
            try:
                timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=timeout, check=check)
                content = message.content.strip()
                user = message.author.display_name
                user_id = message.author.id
                key = (user_id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                for answer in [artist, title]:
                    if fuzzy_match(content, answer, "", ""):
                        await message.add_reaction("✅")
                        await safe_send(channel, f"\u200b\n✅🎉 **<@{user_id}>** got it! **{artist.upper()} - {title.upper()}**\n\u200b")
                        if user_id not in user_data:
                            user_data[user_id] = (user, 0)
                        user_data[user_id] = (user, user_data[user_id][1] + 1)
                        answered = True
                        break

            except asyncio.TimeoutError:
                break

        if not answered:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{artist.upper()} - {title.upper()}**\n\u200b")

        await asyncio.sleep(1)

        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                lyric_winner_id, (display_name, final_score) = sorted_users[0]
                return lyric_winner_id
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        lyric_winner_id, (display_name, final_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return lyric_winner_id
    else:
        return None


class VoiceChannelJoinView(discord.ui.View):
    """View with a green button to join voice channel (shows native Discord join UI)"""

    def __init__(self, voice_channel_id: int, guild_id: int):
        super().__init__(timeout=None)
        self.voice_channel_id = voice_channel_id
        self.guild_id = guild_id

    @discord.ui.button(label="Join Voice", style=discord.ButtonStyle.success, emoji="🎧")
    async def join_voice_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Green button that shows the channel mention - clicking it opens native Discord join UI"""
        try:
            voice_channel = interaction.guild.get_channel(self.voice_channel_id)
            if voice_channel:
                # Send message with channel mention - Discord will render this with the native join UI
                await interaction.response.send_message(
                    f"**Click the channel name below to join:**\n\n{voice_channel.mention}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("❌ Voice channel not found!", ephemeral=True)
        except Exception as e:
            print(f"Error in join voice button: {e}")
            await interaction.response.send_message("❌ An error occurred.", ephemeral=True)


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self):
        return ' '.join(self.text_parts)


def strip_html_tags(html):
    parser = HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def clean_snippet_text(text):
    return re.sub(r'\s+', ' ', text).strip()


async def get_random_epub_snippets(book_epub_url, snippet_length=300, count=2):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(book_epub_url) as response:
                response.raise_for_status()
                content = await response.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        book = epub.read_epub(tmp_path)
        full_text = ""

        for spine_id, _ in book.spine:
            item = book.get_item_with_id(spine_id)
            if item:
                html = item.get_content().decode("utf-8", errors="ignore")
                full_text += " " + strip_html_tags(html)

        if len(full_text.strip()) < 300:
            for item in book.get_items():
                if item.get_type() == epub.EpubHtml:
                    html = item.get_content().decode("utf-8", errors="ignore")
                    full_text += " " + strip_html_tags(html)

        full_text = clean_snippet_text(full_text)
        os.unlink(tmp_path)

        if len(full_text) < snippet_length * count:
            return []

        snippets = []
        min_start = int(0.10 * len(full_text))
        max_start = int(0.90 * len(full_text)) - snippet_length

        for _ in range(count):
            start = random.randint(min_start, max_start)
            while start > 0 and full_text[start - 1].isalnum():
                start -= 1

            end = start + snippet_length
            while end < len(full_text) and full_text[end].isalnum():
                end += 1

            snippet = full_text[start:end].strip()
            snippets.append(f"...{snippet}...")

        return snippets

    except Exception as e:
        print(f"❌ Error extracting snippets: {e}")
        return []


async def ask_book_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/book1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/book2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/book3.gif",
    ]
    gif_url = random.choice(gifs)

    await safe_send(channel, content="\u200b\n\u200b\n📖🕵️‍♂️ **Prose & Cons**: Name the Book OR Author\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    user_data = {}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("book")
            collection = db["book_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}, "enabled": "1"}},
                {"$sample": {"size": 10}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            q = questions[0]

            title = q["title"]
            author = q["author"]
            subjects = q["subjects"]
            epub_url = q["epub_url"]
            qid = q["_id"]

            if qid:
                await store_question_ids_in_mongo([qid], "book")

            print(f"Book: {title} by {author}")

            category_msg = "\u200b\n📚🗂️ **Categories**\n" + "\n".join(f"• {s}" for s in subjects)

            snippets = await get_random_epub_snippets(epub_url)
            snippet_1 = f"\n'{snippets[0]}'\n"
            snippet_2 = f"\n'{snippets[1]}'\n"

            image_1 = generate_text_image(snippet_1, 0, 0, 0, 255, 255, 102, True, "okra.png", "en", 40)
            image_2 = generate_text_image(snippet_2, 0, 0, 0, 255, 255, 102, True, "okra.png", "en", 40)

            file_1 = discord.File(fp=image_1, filename="book1.png")
            embed_1 = discord.Embed().set_image(url="attachment://book1.png")
            file_2 = discord.File(fp=image_2, filename="book2.png")
            embed_2 = discord.Embed().set_image(url="attachment://book2.png")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error fetching book:\n{traceback.format_exc()}")
            continue

        await safe_send(channel, f"\u200b\n📘 **Book {round_num}**/{num}\n\u200b")
        await safe_send(channel, category_msg)
        await asyncio.sleep(2)
        await safe_send(channel, file=file_1, embed=embed_1)
        await safe_send(channel, file=file_2, embed=embed_2)

        start_time = asyncio.get_event_loop().time()
        answered = False
        processed_users = set()

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 20 and not answered:
            try:
                timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=timeout, check=check)
                content = message.content.strip()
                user = message.author.display_name
                user_id = message.author.id
                key = (user_id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                for answer in [title, author]:
                    if fuzzy_match(content, answer, "Book", epub_url):
                        await message.add_reaction("✅")
                        await safe_send(channel, f"\u200b\n✅🎉 **<@{user_id}>** got it!\n\n📚 **{title.upper()}** by **{author.upper()}**\n\u200b")
                        if user_id not in user_data:
                            user_data[user_id] = (user, 0)
                        user_data[user_id] = (user, user_data[user_id][1] + 1)
                        answered = True
                        break
            except asyncio.TimeoutError:
                break

        if not answered:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\n📚 **{title.upper()}** by **{author.upper()}**\n\u200b")

        await asyncio.sleep(1)

        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                book_winner_id, (display_name, final_score) = sorted_users[0]
                return book_winner_id
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)

        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        book_winner_id, (display_name, final_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return book_winner_id
    else:
        return None


async def ask_riddle_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/riddler-carey.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/riddler-vintage.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/riddler-cartoon.gif"
    ]
    gif_url = random.choice(gifs)

    await safe_send(channel, content="\u200b\n\u200b\n🟢🎩 **The Riddler**: Riddle Me This, Riddle Me That\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(5)

    user_data = {}
    
    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("riddle")
            collection = db["riddle_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 100}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            q = questions[0]

            riddle_text = q["question"]
            riddle_answers = q["answers"]
            main_answer = riddle_answers[0]
            category = q["category"]
            url = q["url"]
            qid = q["_id"]

            if qid:
                await store_question_ids_in_mongo([qid], "riddle")

            print(f"Riddle {round_num}: {riddle_text} (Answer: {main_answer})")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting riddle question:\n{traceback.format_exc()}")
            return

        prompt = (
            f"\u200b\n⚠️🚨 **Everyone's in!**\n"
            f"\u200b\n🧠❓ **Riddle {round_num}/{num}**: {riddle_text}\n\u200b"
        )

        await safe_send(channel, prompt)

        start_time = asyncio.get_event_loop().time()
        answered = False
        processed_users = set()

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 20 and not answered:
            try:
                timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=timeout, check=check)
                content = message.content.strip()
                user = message.author.display_name
                user_id = message.author.id
                key = (user_id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                for answer in riddle_answers:
                    if fuzzy_match(content, answer, category, url):
                        await message.add_reaction("✅")
                        await safe_send(channel, f"\u200b\n✅🎉 **<@{user_id}>** got it! **{answer.upper()}**\n\u200b")
                        if user_id not in user_data:
                            user_data[user_id] = (user, 0)
                        user_data[user_id] = (user, user_data[user_id][1] + 1)
                        answered = True
                        break
            except asyncio.TimeoutError:
                break

        if not answered:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{main_answer.upper()}**\n\u200b")

        await asyncio.sleep(1)
                            
        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                riddle_winner_id, (winner_name, winner_score) = sorted_users[0]
                return riddle_winner_id if winner_name is not None else None
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        riddle_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return riddle_winner_id
    else:
        return None
    



async def ask_stock_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/stocks1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/stocks2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/stocks3.gif"
    ]
    gif_url = random.choice(gifs)

    await safe_send(channel, content="\u200b\n\u200b\n🏙️💹 **Wall Street**: Name the Company or Symbol\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(5)

    user_data = {}
    
    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("stock")
            collection = db["stock_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 10}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            q = questions[0]

            stock_symbol = q["symbol"]
            company_name = q["security"]
            industry = q["industry"]
            sub_industry = q["sub_industry"]
            headquarters = q["headquarters"]
            founded_year = q["founded"]
            qid = q["_id"]
            category = "Stocks"
            url = None

            if qid:
                await store_question_ids_in_mongo([qid], "stock")

            print(f"{round_num} Stock Symbol: {stock_symbol}")
            print(f"{round_num} Company {company_name})")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting stock question:\n{traceback.format_exc()}")
            return

        prompt = f"\u200b\n⚠️🚨 **Everyone's in!**\n"
        prompt += f"\u200b\n🧠❓ **Question {round_num}/{num}**: "
        
        game_mode = None
        if random.random() < 0.5:
            prompt += f"What is the **symbol** for **{company_name}**?\n\u200b"
            game_mode = "name_to_symbol"
            accepted_symbols = (
                {norm_symbol(stock_symbol)}
                if isinstance(stock_symbol, str)
                else {norm_symbol(sym) for sym in stock_symbol}  # list/tuple case
            )
            main_trivia_answer = sorted(accepted_symbols)[0]
        else:
            prompt += f"What **company** has the symbol **{stock_symbol}**?\n\u200b"
            game_mode = "symbol_to_name"
            accepted_company_name = norm_name(company_name)
            main_trivia_answer = accepted_company_name
        
        await safe_send(channel, prompt)

        start_time = asyncio.get_event_loop().time()
        answered = False
        processed_users = set()

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 20 and not answered:
            try:
                timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=timeout, check=check)
                content = message.content.strip()
                user = message.author.display_name
                user_id = message.author.id
                key = (user_id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                if game_mode == "name_to_symbol":
                    user_ans = norm_symbol(content)    
                    is_correct = user_ans in accepted_symbols
                else:
                    is_correct = fuzzy_match(norm_name(content), accepted_company_name, category, url)
                    
                if is_correct:   
                    await message.add_reaction("✅")
                    await safe_send(channel, f"\u200b\n✅🎉 **<@{user_id}>** got it! **{main_trivia_answer.upper()}**\n\u200b")
                    if user_id not in user_data:
                        user_data[user_id] = (user, 0)
                    user_data[user_id] = (user, user_data[user_id][1] + 1)
                    answered = True
                    break
            except asyncio.TimeoutError:
                break

        if not answered:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{main_trivia_answer.upper()}**\n\u200b")

        await asyncio.sleep(1)
                            
        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                stock_winner_id, (winner_name, winner_score) = sorted_users[0]
                return stock_winner_id if winner_name is not None else None
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        stock_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return stock_winner_id
    else:
        return None

# Normalize helpers
def norm_symbol(s: str) -> str:
    # strip spaces + common prefixes/suffixes and lowercase
    s = s.strip().lower()
    if s.startswith("$"):
        s = s[1:]
    return "".join(ch for ch in s if ch.isalnum())  # keep letters/digits only

def norm_name(s: str) -> str:
    return " ".join(s.lower().split())  # collapse whitespace



async def ask_border_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    border_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/border1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/border2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/border3.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/border4.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/border5.gif"
    ]

    gif_url = random.choice(border_gifs)

    await safe_send(channel, content="\u200b\n\u200b\n🗺️❓ **Borderline**: Identify the Country\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    await safe_send(channel, f"\u200b\n🕹️🚀 **<@{winner_id}>**, select the mode:\n\n🧸 **Normal** or 🧨 **Okrap**.\n\u200b")
    try:
        msg = await bot.wait_for("message", timeout=magic_time + 5, check=lambda m: m.author.id == winner_id and m.author != bot.user and m.channel == channel and m.content.lower() in {"normal", "okrap"})
        game_mode = msg.content.lower()
        await msg.add_reaction("✅")
    except asyncio.TimeoutError:
        game_mode = "normal"

    await safe_send(channel, f"\u200b\n💥🤯 Ok...ra! We're going with **{game_mode.upper()}** baby!\n\u200b")
    await asyncio.sleep(2)

    user_data = {}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            recent_border_ids = await get_recent_question_ids_from_mongo("border")
            border_collection = db["border_questions"]
            pipeline_border = [
                {"$match": {
                    "_id": {"$nin": list(recent_border_ids)},
                    "neighbours": {"$regex": r"\S"} 
                }},
                {"$sample": {"size": 20}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]

            border_questions = [doc async for doc in border_collection.aggregate(pipeline_border)]
            border_question = border_questions[0]

            border_neighbors = border_question["neighbours"]
            border_country = border_question["country"]
            border_capital = border_question["capital"]
            border_area = border_question["area_km2"]
            border_population = border_question["population"]
            border_continent = border_question["continent"]
            border_iso_code = border_question["iso_code"]
            border_currency = border_question["currency"]
            border_languages = border_question["languages"]
            border_category = "border"
            border_url = ""
            border_question_id = border_question["_id"] 

            if border_question_id:
                await store_question_ids_in_mongo([border_question_id], "border")  # Store it as a list containing a single ID
  
            print(f"Country: {border_country}")
            answered = False
            
            message = f"\u200b\n⚠️🚨 **Everyone's in!**\n"
            message += f"\n🗣💬❓ **Country {round_num}**/{num}\n\u200b"      
            await safe_send(channel, message)
            await asyncio.sleep(2)

            message = f"\u200b\n**Neighbors**: {border_neighbors}"   

            if game_mode == "normal":        
                message += f"\n**Capital**: {border_capital}"
                message += f"\n**Continent**: {border_continent}"
                message += f"\n**ISO Codes**: {border_iso_code}"
            message += "\n\u200b"
               
            await safe_send(channel, message)

            start_time = asyncio.get_event_loop().time()

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 20 and not answered:
                try:
                    msg = await bot.wait_for("message", timeout=20 - (asyncio.get_event_loop().time() - start_time), check=check)
                    guess = normalize_text(msg.content).replace(" ", "")
                    user = msg.author.display_name
                    uid = msg.author.id
                                                
                    if fuzzy_match(guess, border_country, border_category, border_url):
                        await msg.add_reaction("✅")
                        await safe_send(channel, f"\u200b\n✅🎉 **<@{uid}>** got it! **{border_country.upper()}**\n\u200b")
                        user_data[uid] = (user, user_data.get(uid, (user, 0))[1] + 1)
                        answered = True
                        break
                except asyncio.TimeoutError:
                    break

            if not answered:
                message = f"\u200b\n❌😢 No one got it.\n\nAnswer: **{border_country.upper()}**\n\u200b"
                await safe_send(channel, message)
        
        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(traceback.format_exc())
            await safe_send(channel, "\u200b\n⚠️ Error during round, skipping.\n\u200b")
            continue

        await asyncio.sleep(1)

        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                border_winner_id, (display_name, final_score) = sorted_users[0]
                return border_winner_id
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        border_winner_id, (display_name, final_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return border_winner_id
    else:
        return None



async def ask_animal_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/animal1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/animal2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/animal3.gif"
    ]

    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n\u200b\n❓🦓 **OkrAnimal**: Name That Animal!\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    user_correct_answers = {}
    animal_main_url = "https://a-z-animals.com/animals/"
    category = "Animals"

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    animal_num = 1
    while animal_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("animal")
            collection = db["animal_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 100}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            q = questions[0]
            print(q)

            name = q["name"]
            image_url = q["image_url"]
            detail_url = q["animal_url"]
            pattern = re.compile(re.escape(name), re.IGNORECASE)

            fields = {k: pattern.sub("OKRA", q.get(k, "N/A")) for k in ["kingdom", "phylum", "class", "order", "family", "genus", "species"]}

            if q["_id"]:
                await store_question_ids_in_mongo([q["_id"]], "animal")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting animal question:\n{traceback.format_exc()}")
            return

        processed_users = set()

        prompt = (
            f"\n⚠️🚨 **Everyone's in!**\n\u200b"
            f"\u200b\n❓🦓 The **$@!#** is dat?!?\n\n"
            f"👑 **Kingdom**: {fields['kingdom']}\n"
            f"🧩 **Phylum**: {fields['phylum']}\n"
            f"🏫 **Class**: {fields['class']}\n"
            f"🧾 **Order**: {fields['order']}\n"
            f"👨‍👩‍👧 **Family**: {fields['family']}\n"
            f"🔬 **Genus**: {fields['genus']}\n"
            f"🐾 **Species**: {fields['species']}\n\u200b"
        )

        await safe_send(channel, content=prompt, embed=discord.Embed().set_image(url=image_url))

        start_time = asyncio.get_event_loop().time()
        right_answer = False

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 15 and not right_answer:
            try:
                remaining = 15 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=remaining, check=check)
                content = message.content.strip()
                user = message.author.display_name
                user_id = message.author.id
                key = (message.author.id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                if fuzzy_match(content, name, category, detail_url):
                    await message.add_reaction("✅")
                    await safe_send(channel, f"\u200b\n✅🎉 Correct! **<@{user_id}>** got it! **{name.upper()}**\n\n{detail_url}\n\u200b")
                    if user_id not in user_correct_answers:
                            user_correct_answers[user_id] = (user, 0)
                    user_correct_answers[user_id] = (user, user_correct_answers[user_id][1] + 1)
                    right_answer = True
            except asyncio.TimeoutError:
                break

        if not right_answer:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{name.upper()}**\n\n{detail_url}\n\u200b")

        await asyncio.sleep(1)
                            
        animal_num = animal_num + 1
        
        message = ""

        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                animal_winner_id, (winner_name, winner_score) = sorted_users[0]
                return animal_winner_id if winner_name is not None else None
            else:
                return None
            
        if sorted_users:
            if animal_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (uid, (name, score)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{name}**: {score}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        aniaml_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(2)
        
    summary = f"\nSee more cute animals at:\n{animal_main_url}\n\u200b"
    await safe_send(channel, summary)

    await asyncio.sleep(3)

    if sorted_users:
        return animal_winner_id
    else:
        return None


async def ask_ranker_people_challenge(winner, winner_id, num=7):
    global wf_winner

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/ranker1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/ranker2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/ranker3.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/ranker4.gif"
    ]

    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n\u200b\n 👤🌟 **Famous Peeps**: Identify the Greats\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(2)

    await safe_send(channel, f"\u200b\n👤🌟 ID Ranker.com's All Time Greats\n\u200b")
    await asyncio.sleep(5)

    user_correct_answers = {}
    ranker_url = "https://www.ranker.com/crowdranked-list/the-most-influential-people-of-all-time"

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    people_num = 1
    while people_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("people")
            collection = db["ranker_people_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 100}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            question = questions[0]

            answers = question["answers"]
            main_answer = answers[0]
            rank = question["rank"]
            detail_url = question["detail_url"]
            birthplace = question["birthplace"]
            nationality = question["nationality"]
            profession = question["profession"]
            image_url = question["url"]
            nationality = nationality or "Missing"
            profession = profession or "Missing"  
            birthplace = birthplace or "Missing"      

            if question["_id"]:
                await store_question_ids_in_mongo([question["_id"]], "people")
            print(question)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting people question:\n{traceback.format_exc()}")
            return

        processed_users = set()

        prompt = (
            f"\u200b\n⚠️🚨 **Everyone's in!**\n\u200b"
            f"\u200b\n👤🌟 **Person {people_num}** of {num} (Rank #{rank}):  Who dat?!?\n"
            f"\n🌍🏡 Birthplace: **{birthplace}**"
            f"\n🏳️🆔 Nationality: **{nationality}**"
            f"\n💼⚒️ Profession: **{profession}**\n\u200b"
        )


        await safe_send(channel, embed=discord.Embed(description=f"Rank #{rank}").set_image(url=image_url))
        await safe_send(channel, prompt)

        start_time = asyncio.get_event_loop().time()
        right_answer = False

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 15 and not right_answer:
            try:
                remaining = 15 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=remaining, check=check)
                user = message.author.display_name
                user_id = message.author.id
                content = message.content.strip()
                key = (message.author.id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                for answer in answers:
                    if fuzzy_match(content, answer, "Ranker People", image_url):
                        await message.add_reaction("✅")
                        await safe_send(channel, f"\u200b\n✅🎉 Correct! **<@{user_id}>** got it! **{answer.upper()}**")
                        if user_id not in user_correct_answers:
                            user_correct_answers[user_id] = (user, 0)
                        user_correct_answers[user_id] = (user, user_correct_answers[user_id][1] + 1)
                        right_answer = True
                        break
            except asyncio.TimeoutError:
                break

        if not right_answer:
            msg = f"\u200b\n❌😢 No one got it.\n\nAnswer: **{main_answer.upper()}**\n"
            await safe_send(channel, msg)

        detail_url = detail_url if detail_url.startswith("http") else "https://" + detail_url.lstrip("/")

        msg = f"\u200b\n[More info about {main_answer}]({detail_url})\n\u200b"
        await safe_send(channel, msg)

        await asyncio.sleep(1)

        people_num = people_num + 1

        message = ""

        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                people_winner_id, (winner_name, winner_score) = sorted_users[0]
                return people_winner_id if winner_name is not None else None
            else:
                return None
            
        if sorted_users:
            if people_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (uid, (name, score)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{name}**: {score}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        people_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)

    await asyncio.sleep(2)

    ranker_url = ranker_url if ranker_url.startswith("http") else "https://" + detail_url.lstrip("/")
    await safe_send(channel, f"\u200b\n📝 Ranks from Ranker.com\n{ranker_url}\n\u200b")
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return people_winner_id
    else:
        return None
    


async def ask_flags_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/flags_usc.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/flags_cartoon.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/flags_friends.gif"
    ]
    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n\u200b\n🎏🎉 **Flag Fest**: Identify the Banner\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    user_correct_answers = {}
    flag_reference_url = "http://flags.net/"

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    flag_num = 1
    while flag_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("flags")
            collection = db["flags_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 100}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            q = questions[0]

            answer = q["answer"]
            category = q["category"]
            image_url = q["flag_url"]
            detail = q["flag_detail"]
            source_url = q["source_url"]

            if q["_id"]:
                await store_question_ids_in_mongo([q["_id"]], "flags")
            print(q)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting flags question:\n{traceback.format_exc()}")
            return

        processed_users = set()

        if category == "country_region_org":
            prompt = "\u200b\n🌍🏳️ Which **country or international organization** does this flag represent?\n\n✋🔤 *Do NOT abbreviate countries.*\n\u200b"
        elif category == "signal":
            prompt = "\u200b\n🔣🏳️ What **symbol** does this flag represent?\n\u200b"
        else:
            prompt = "\u200b\n🏳️ What does this flag represent?\n\u200b"

        await safe_send(channel, content=prompt, embed=discord.Embed().set_image(url=image_url))

        start_time = asyncio.get_event_loop().time()
        right_answer = False

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 15 and not right_answer:
            try:
                timeout = 15 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=timeout, check=check)
                content = message.content.strip()
                user = message.author.display_name
                user_id = message.author.id
                key = (message.author.id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                if fuzzy_match(content, answer, category, image_url):
                    await message.add_reaction("✅")
                    await safe_send(channel, f"\u200b\n✅🎉 **<@{user_id}>** got it! **{answer.upper()}**\n\n🏴‍☠️📖 {detail}\n👀➡️ {source_url}\n\u200b")
                    if user_id not in user_correct_answers:
                            user_correct_answers[user_id] = (user, 0)
                    user_correct_answers[user_id] = (user, user_correct_answers[user_id][1] + 1)
                    right_answer = True
            except asyncio.TimeoutError:
                break

        if not right_answer:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{answer.upper()}**\n\n🏴‍☠️📖 {detail}\n👀➡️ {source_url}\n\u200b")

        await asyncio.sleep(1)
                            
        flag_num = flag_num + 1
        
        message = ""

        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                flag_winner_id, (winner_name, winner_score) = sorted_users[0]
                return flag_winner_id
            else:
                return None
            
        if sorted_users:
            if flag_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (uid, (name, score)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{name}**: {score}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        flag_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)

    await asyncio.sleep(2)
    
    summary = f"\n👀➡️ See more flags at:\n{flag_reference_url}\n\u200b"
    
    await safe_send(channel, summary)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return flag_winner_id
    else:
        return None
        

async def ask_chaos_challenge(winner, winner_id, num_of_games):
    global wf_winner

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/chaos1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/chaos2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/chaos3.gif"
    ]

    gif_url = random.choice(gifs)

    intro_message = f"\u200b\n🌀🤯 **CHAOS MODE** has begun!\n\u200b"
    await safe_send(channel, content=intro_message, embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(5)

    if num_of_games > 1:
        await safe_send(channel, f"\u200b\n🎲 Picking **{num_of_games}** random mini-games for you maniacs...\n\u200b")
        await asyncio.sleep(3)

    wf_winner = True
    scoreboard = {}

    challenge_functions = [
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
        ask_search_challenge
    ]

    num_of_games = min(num_of_games, len(challenge_functions))
    selected_challenges = random.sample(challenge_functions, k=num_of_games)

    for i, challenge_fn in enumerate(selected_challenges, 1):
        await safe_send(channel, f"\u200b\n🧠 **Mini-Game {i}** of {num_of_games} starting...\n\u200b")
        await asyncio.sleep(1)

        result = await challenge_fn(winner, winner_id, num=1)
        if result:
            print(result)
            # Try to get display name (either from winner if same user, or via Discord lookup)
            if result in scoreboard:
                display_name, current_score = scoreboard[result]
                scoreboard[result] = (display_name, current_score + 1)
            else:
                try:
                    member = channel.guild.get_member(result) or await channel.guild.fetch_member(result)
                    display_name = member.display_name
                except Exception:
                    display_name = f"**{result}**"

                scoreboard[result] = (display_name, 1)

        if scoreboard:
            sorted_scores = sorted(scoreboard.items(), key=lambda x: x[1][1], reverse=True)
            scoreboard_msg = "\u200b\n📊 **Scoreboard**\n\u200b"
            for user_id, (display_name, score) in sorted_scores:
                scoreboard_msg += f"• **{display_name}**: {score} point{'s' if score != 1 else ''}\n"
            await safe_send(channel, scoreboard_msg)
            await asyncio.sleep(2)

    # Final results
    if scoreboard:
        sorted_scores = sorted(scoreboard.items(), key=lambda x: x[1][1], reverse=True)
        top_score = sorted_scores[0][1][1]
        top_winners = [uid for uid, (_, score) in sorted_scores if score == top_score]

        await asyncio.sleep(2)
        if len(top_winners) == 1:
            overall_winner_id = top_winners[0]
            overall_winner_name = scoreboard[overall_winner_id][0]
            message = f"\u200b\n👑 **Overall Winner:** **{overall_winner_name}** with **{top_score}** point{'s' if top_score != 1 else ''}!\n\u200b"
        else:
            message = f"\u200b\n🤝 It's a tie! **Winners:**\n\u200b"
            for tied_winner_id in top_winners:
                winner_name = scoreboard[tied_winner_id][0]
                message += f"• **{winner_name}** ({top_score} pts)\n"
            message += "\u200b"
    else:
        message = "\u200b\n😶 No winners this time... chaos reigns.\n\u200b"

    await safe_send(channel, message)
    await asyncio.sleep(3)



async def ask_soundfx_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    user_data = {}
    voice_client = None  # Initialize at function level for scope accessibility
    sorted_users = []  # Initialize to prevent UnboundLocalError

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/soundfx1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/soundfx2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/soundfx3.gif"
    ]
    gif_url = random.choice(gifs)

    await safe_send(channel, content="\u200b\n👂➡️ **Hear Here 🎧**: Do You Hear What I Hear?\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    
    voice_channel = bot.get_channel(TRIVIA_VOICE_CHANNEL_ID)
    if voice_channel:
        try:
            voice_client = voice_channel.guild.voice_client

            # If connected to a different channel, move to the correct one
            if voice_client and voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
            # If not connected at all, connect with timeout
            elif voice_client is None:
                # Add 30 second timeout for voice connection (discord.py will retry internally)
                voice_client = await asyncio.wait_for(
                    voice_channel.connect(),
                    timeout=30.0
                )
        except asyncio.TimeoutError:
            print("Voice connection timed out after 30 seconds")
            await safe_send(channel, "⚠️ Could not connect to voice channel. Continuing with text-only mode.")
            voice_client = None  # Ensure it's None so audio playback is skipped
        except Exception as e:
            print(f"Voice connection error: {e}")
            await safe_send(channel, "⚠️ Voice connection failed. Continuing with text-only mode.")
            voice_client = None

        # Remind users to join voice channel (only if connected)
        if voice_client:
            # Make voice channel visible to everyone
            try:
                everyone_role = voice_channel.guild.get_role(EVERYONE_ROLE_ID)
                if everyone_role:
                    # Get current permissions or create new ones
                    existing_perms = voice_channel.overwrites_for(everyone_role)
                    # Set view_channel to True, preserving other permissions
                    existing_perms.view_channel = True
                    await voice_channel.set_permissions(everyone_role, overwrite=existing_perms)
                    print(f"✅ Made voice channel visible to @everyone")
            except Exception as e:
                print(f"Error making voice channel visible: {e}")

            voice_embed = discord.Embed(
                title="🎧 Audio Challenge - Join Voice Channel!",
                description=f"**{voice_channel.mention}**",
                color=discord.Color.gold()  # Use gold like tournament for visual prominence
            )

            await safe_send(channel, embed=voice_embed)


    await asyncio.sleep(7)

    if num > 1:
        await safe_send(channel, f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b")
        await asyncio.sleep(3)

    # Pre-fetch all questions with unique topics before the loop
    try:
        recent_ids = await get_recent_question_ids_from_mongo("soundfx")
        collection = db["soundfx_questions"]
        pipeline = [
            {"$match": {"_id": {"$nin": list(recent_ids)}, "enabled": True}},
            {"$sample": {"size": 100}},  # Sample larger pool to ensure enough unique topics
            {"$group": {"_id": "$topic", "question_doc": {"$first": "$$ROOT"}}},  # Group by topic to ensure uniqueness
            {"$replaceRoot": {"newRoot": "$question_doc"}},
            {"$sample": {"size": num}}  # Randomly sample num questions from the unique topics
        ]
        questions = [doc async for doc in collection.aggregate(pipeline)]

        # Store all question IDs upfront
        question_ids = [q["_id"] for q in questions]
        if question_ids:
            await store_question_ids_in_mongo(question_ids, "soundfx")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(traceback.format_exc())
        await safe_send(channel, "\u200b\n⚠️ Error fetching questions. Please try again.\n\u200b")
        return None

    round_num = 1
    for q in questions:
        try:
            url = q["url"]
            topic = q["topic"]
            description = q["description"]
            clip_num = q["clip_num"]
            category = "Sound Fx"

            print(f"{topic}: {description}")


            message = f"\u200b\n🎧➡️ Sound **{round_num}** of **{num}**\n\n👂 What do you hear?\n\u200b"
            await safe_send(channel, message)

            answered = False

            # Play the sound effect in the voice channel (looping)
            audio_task = None
            try:
                if voice_client:
                    # Create a background task to loop the audio
                    async def loop_audio():
                        try:
                            while not answered:
                                if voice_client and not voice_client.is_playing():
                                    if answered:  # Double-check before playing
                                        break
                                    audio_source = discord.FFmpegPCMAudio(url)
                                    voice_client.play(audio_source)
                                    # Wait for audio to finish playing with very frequent checks
                                    while voice_client.is_playing() and not answered:
                                        await asyncio.sleep(0.01)  # Check every 10ms
                                    # Stop immediately if answered during playback
                                    if answered and voice_client.is_playing():
                                        voice_client.stop()
                                        break
                                    # 0.5s delay before repeating (if not answered)
                                    if not answered:
                                        await asyncio.sleep(0.5)
                                else:
                                    await asyncio.sleep(0.01)  # Check every 10ms
                        except Exception as e:
                            print(f"Error in audio loop: {e}")

                    # Start the audio loop task in the background
                    audio_task = asyncio.create_task(loop_audio())
            except Exception as e:
                print(f"Error starting audio: {e}")
            start_time = asyncio.get_event_loop().time()

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 20 and not answered:
                try:
                    timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                    msg = await bot.wait_for("message", timeout=timeout, check=check)
                    guess = msg.content.strip()
                    uid = msg.author.id
                    display = msg.author.display_name

                    # Odd Duck
                    if fuzzy_match(guess, description, category, url):
                        # Set flag first so loop stops immediately
                        answered = True

                        # Force stop voice client immediately
                        if voice_client and voice_client.is_playing():
                            voice_client.stop()

                        # Give the loop a moment to see answered=True and stop
                        await asyncio.sleep(0.05)

                        # Cancel the audio loop task
                        if audio_task and not audio_task.done():
                            audio_task.cancel()
                            try:
                                await audio_task
                            except asyncio.CancelledError:
                                pass

                        await msg.add_reaction("✅")
                        user_data[uid] = (display, user_data.get(uid, (display, 0))[1] + 1)
                        await safe_send(channel, f"\u200b\n✅🎉 **{display}** got it! **{description.upper()}**\n\u200b")
                        break

                except asyncio.TimeoutError:
                    break

            # Stop the audio loop task
            if audio_task and not audio_task.done():
                audio_task.cancel()
                try:
                    await audio_task
                except asyncio.CancelledError:
                    pass

            # Stop any playing audio
            if voice_client and voice_client.is_playing():
                voice_client.stop()

            if not answered:
                await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\n📝🧠 Answer: **{description.upper()}**\n\u200b")


            await asyncio.sleep(5)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(traceback.format_exc())
            await safe_send(channel, "\u200b\n⚠️ Error during round, skipping.\n\u200b")
            continue

        await asyncio.sleep(1)

        round_num += 1

        message = ""
        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                soundfx_winner_id, (display_name, final_score) = sorted_users[0]
                return soundfx_winner_id
            else:
                return None

        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

            for counter, (uid, (name, score)) in enumerate(sorted_users, start=1):
                message += f"{counter}. **{name}**: {score}\n\u200b"

        if message:
            await safe_send(channel, message)
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        soundfx_winner_id, (display_name, final_score) = sorted_users[0]
        await safe_send(channel, f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b")
    else:
        await safe_send(channel, f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b")

    wf_winner = True
    await asyncio.sleep(3)

    # Disconnect from voice channel
    try:
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            print(f"✅ Disconnected from voice channel")
    except Exception as e:
        print(f"Error disconnecting from voice: {e}")

    # Hide voice channel from everyone
    try:
        if voice_channel:
            everyone_role = voice_channel.guild.get_role(EVERYONE_ROLE_ID)
            if everyone_role:
                # Get current permissions
                existing_perms = voice_channel.overwrites_for(everyone_role)
                # Set view_channel to False, preserving other permissions
                existing_perms.view_channel = False
                await voice_channel.set_permissions(everyone_role, overwrite=existing_perms)
                print(f"✅ Hidden voice channel from @everyone")
    except Exception as e:
        print(f"Error hiding voice channel: {e}")

    if sorted_users:
        return soundfx_winner_id
    else:
        return None







async def ask_president_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True

    user_data = {}

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/president1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/president2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/president3.gif"
    ]
    gif_url = random.choice(gifs)

    await safe_send(channel, content="\u200b\n🦅🇺🇸 **Rushmore**: Do You Know the US Presidents?\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    if num > 1:
        await safe_send(channel, f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b")
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("president")
            collection = db["president_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 10}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            q = questions[0]

            qid = q["_id"]
            pres_number = q["number"]
            game_mode = q["type"]
            pres_name = q["name"]
            pres_url = q["url"]
            y1_start = q["year_start_1"]
            y1_end = q["year_end_1"]
            y2_start = q["year_start_2"]
            y2_end = q["year_end_2"]
            category = "Presidents"

            print(f"{pres_name} {y1_start}-{y1_end}")
            
            if qid:
                await store_question_ids_in_mongo([qid], "president")

            main_img = q["url"]
            embed = discord.Embed()
            embed.set_image(url=main_img)

            # Odd Duck Mode
            if game_mode == "odd_duck":
                valid_pairs = []
                for i in range(1, 47):
                    pair = (i, i + 1)
                    if any(n in pair for n in [pres_number - 1, pres_number, pres_number + 1]):
                        continue
                    valid_pairs.append(pair)

                n1, n2 = random.choice(valid_pairs)
                img_urls = [
                    q["url"],
                    f"https://triviabotwebsite.s3.us-east-2.amazonaws.com/presidents/{n1}.jpg",
                    f"https://triviabotwebsite.s3.us-east-2.amazonaws.com/presidents/{n2}.jpg"
                ]
                random.shuffle(img_urls)

            await safe_send(channel, f"\u200b\n⚠️🚨 Everyone's in!\n\u200b\n🦅🇺🇸 President **{round_num}** of **{num}**\n\u200b")
            if game_mode == "years":
                await safe_send(channel, content="\u200b\n📅 Name a **YEAR** during their time in office.\n\u200b")
                await safe_send(channel, embed=embed)
            elif game_mode == "odd_duck":
                await safe_send(channel, content="\u200b\n🦆 Who's the **odd duck**?\n\u200b")
                for img in img_urls:
                    emb = discord.Embed()
                    emb.set_image(url=img)
                    await safe_send(channel, embed=emb)

            answered = False
            processed_users = set()
            start_time = asyncio.get_event_loop().time()

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 20 and not answered:
                try:
                    timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                    msg = await bot.wait_for("message", timeout=timeout, check=check)
                    guess = msg.content.strip()
                    uid = msg.author.id
                    display = msg.author.display_name
                    key = (uid, guess)

                    if key in processed_users:
                        continue
                    processed_users.add(key)

                    # Years mode
                    if game_mode == "years" and guess.isdigit() and len(guess) == 4:
                        year = int(guess)
                        if (int(y1_start) <= year <= int(y1_end)) or (y2_start and int(y2_start) <= year <= int(y2_end)):
                            await msg.add_reaction("✅")
                            user_data[uid] = (display, user_data.get(uid, (display, 0))[1] + 1)
                            desc = f"({y1_start}-{y1_end}, {y2_start}-{y2_end})" if y2_start else f"({y1_start}-{y1_end})"
                            await safe_send(channel, f"\u200b\n✅🎉 **{display}** got it! **{pres_name.upper()}** {desc}\n\u200b")
                            answered = True
                            break

                    # Odd Duck
                    if game_mode == "odd_duck" and fuzzy_match(guess, pres_name, category, pres_url):
                        await msg.add_reaction("✅")
                        user_data[uid] = (display, user_data.get(uid, (display, 0))[1] + 1)
                        desc = f"({y1_start}-{y1_end}, {y2_start}-{y2_end})" if y2_start else f"({y1_start}-{y1_end})"
                        await safe_send(channel, f"\u200b\n✅🎉 **{display}** got it! **{pres_name.upper()}** {desc}\n\u200b")
                        answered = True
                        break

                except asyncio.TimeoutError:
                    break

            if not answered:
                desc = f"({y1_start}-{y1_end}, {y2_start}-{y2_end})" if y2_start else f"({y1_start}-{y1_end})"
                await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\n📝🧠 Answer: **{pres_name.upper()}** {desc}\n\u200b")
                #embed = discord.Embed()
                #embed.set_image(url=main_img)
                #await safe_send(channel, embed=embed)

            await asyncio.sleep(5)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(traceback.format_exc())
            await safe_send(channel, "\u200b\n⚠️ Error during round, skipping.\n\u200b")
            continue

        await asyncio.sleep(1)

        round_num += 1

        message = ""
        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                president_winner_id, (display_name, final_score) = sorted_users[0]
                return president_winner_id
            else:
                return None

        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

            for counter, (uid, (name, score)) in enumerate(sorted_users, start=1):
                message += f"{counter}. **{name}**: {score}\n\u200b"

        if message:
            await safe_send(channel, message)
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        president_winner_id, (display_name, final_score) = sorted_users[0]
        await safe_send(channel, f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b")
    else:
        await safe_send(channel, f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b")

    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return president_winner_id
    else:
        return None




async def ask_poster_challenge(winner, winner_id, num=7):
    global wf_winner

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/poster1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/poster2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/poster3.gif"
    ]

    gif_url = random.choice(gifs)
    
    message = f"\u200b\n\u200b\n 🎥⚡ Poster Blitz\n\u200b"
    await safe_send(channel, content=message, embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(5)

    user_correct_answers = {}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    poster_num = 1
    while poster_num <= num:
        try:
            recent_posters_ids = await get_recent_question_ids_from_mongo("posters")
            posters_collection = db["posters_questions"]
            pipeline_posters = [
                {"$match": {"_id": {"$nin": list(recent_posters_ids)}}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            posters_questions = [doc async for doc in posters_collection.aggregate(pipeline_posters)]
            posters_question = posters_questions[0]
            posters_category = posters_question["category"]
            posters_answers = posters_question["answers"]
            posters_main_answer = posters_answers[0]
            posters_year = posters_question["question"]
            posters_url = posters_question["url"]

            if posters_question["_id"]:
                await store_question_ids_in_mongo([posters_question["_id"]], "posters")
            print(posters_question)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting posters questions:\n{traceback.format_exc()}")
            return

        processed_users = set()

        prompt = (
            f"\u200b\n⚠️🚨 **Everyone's in!**\n"
            f"\n\n🎥🌟 **Poster {poster_num}** of {num}: What **{posters_category.upper()}** is depicted in the poster above?\n"
            f"\n📅💡 Year: **{posters_year}**\n\u200b"
        )
        
        await safe_send(channel, embed=discord.Embed(description=f"**{posters_category.upper()} ({posters_year})**").set_image(url=posters_url))
        await safe_send(channel, prompt)

        start_time = asyncio.get_event_loop().time()
        right_answer = False

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 15 and not right_answer:
            try:
                remaining = 15 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=remaining, check=check)
                user = message.author.display_name
                user_id = message.author.id
                content = message.content.strip()
                key = (message.author.id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                for answer in posters_answers:
                    if fuzzy_match(content, answer, posters_category, posters_url):
                        await message.add_reaction("✅")
                        await safe_send(channel, f"\u200b\n✅🎉 Correct! **<@{user_id}>** got it! **{answer.upper()}**\n\u200b")
                        if user_id not in user_correct_answers:
                            user_correct_answers[user_id] = (user, 0)
                        user_correct_answers[user_id] = (user, user_correct_answers[user_id][1] + 1)
                        right_answer = True
                        
                        break
            except asyncio.TimeoutError:
                break

        if not right_answer:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{posters_main_answer.upper()}**\n\u200b")
        
        await asyncio.sleep(1)
                            
        poster_num = poster_num + 1
        
        message = ""

        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                poster_winner_id, (winner_name, winner_score) = sorted_users[0]
                return poster_winner_id if winner_name is not None else None
            else:
                return None
            
        if sorted_users:
            if poster_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (uid, (name, score)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{name}**: {score}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        poster_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return poster_winner_id
    else:
        return None



def generate_wordle_image(wordle_word, guesses):
    wordle_word = wordle_word.lower()
    word_length = len(wordle_word)
    num_rows = word_length
    box_size = 80
    margin = 10
    font_path = os.path.join(os.path.dirname(__file__), "DejaVuSerif.ttf")
    font_size = 36

    img_width = word_length * (box_size + margin) + margin
    img_height = num_rows * (box_size + margin) + margin

    img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Font not found at {font_path}")
        return None

    for row in range(num_rows):
        guess = guesses[row].lower() if row < len(guesses) else ""
        matched = [False] * word_length

        # First pass: Green squares for correct positions
        for col in range(word_length):
            x0 = margin + col * (box_size + margin)
            y0 = margin + row * (box_size + margin)
            x1 = x0 + box_size
            y1 = y0 + box_size

            fill_color = "white"
            if col < len(guess):
                if guess[col] == wordle_word[col]:
                    fill_color = "#6aaa64"  # green
                    matched[col] = True

            draw.rectangle([x0, y0, x1, y1], fill=fill_color)

        # Second pass: Yellow squares for misplaced letters
        for col in range(word_length):
            if col >= len(guess) or guess[col] == wordle_word[col]:
                continue
            letter = guess[col]
            if letter in wordle_word:
                for i in range(word_length):
                    if wordle_word[i] == letter and not matched[i]:
                        x0 = margin + col * (box_size + margin)
                        y0 = margin + row * (box_size + margin)
                        x1 = x0 + box_size
                        y1 = y0 + box_size
                        draw.rectangle([x0, y0, x1, y1], fill="#c9b458")  # yellow
                        matched[i] = True
                        break

        # Draw letters centered
        for col in range(word_length):
            if col >= len(guess): continue
            letter = guess[col].upper()
            x0 = margin + col * (box_size + margin)
            y0 = margin + row * (box_size + margin)
            text_x = x0 + box_size // 2
            
            text_y = y0 + box_size // 2
            draw.text((text_x, text_y), letter, fill="black", font=font, anchor="mm")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer

def wordle_score(wordle_word, guess):
    wordle_word = wordle_word.lower()
    guess = guess.lower()

    if len(wordle_word) != len(guess):
        raise ValueError("Guess and wordle_word must be the same length")

    score = 0
    used_indices = [False] * len(wordle_word)

    # First pass: exact matches (green)
    for i in range(len(wordle_word)):
        if guess[i] == wordle_word[i]:
            score += 2
            used_indices[i] = True

    # Second pass: partial matches (yellow)
    for i in range(len(wordle_word)):
        if guess[i] != wordle_word[i]:
            for j in range(len(wordle_word)):
                if not used_indices[j] and guess[i] == wordle_word[j]:
                    score += 1
                    used_indices[j] = True
                    break

    return score



async def ask_wordle_challenge(winner, winner_id, num=1):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/wordle1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/wordle2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/wordle3.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/wordle4.gif",
    ]

    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n🟩🟨 **Wordle War**: Our Favorite Word Game\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(5)

    user_correct_answers = {}

    if num > 1:
        await safe_send(channel, f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b")
        await asyncio.sleep(3)

    wordle_num = 1
    while wordle_num <= num:
        try:
            recent_wordle_ids = await get_recent_question_ids_from_mongo("wordle")
            wordle_collection = db["wordle_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_wordle_ids)}}},
                {"$sample": {"size": 50}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in wordle_collection.aggregate(pipeline)]
            q = questions[0]
            word = q["word"]
            wordle_word_length = len(word)
            wordle_guesses = []

            if wordle_word_length == 4:
                valid_words_file = "4letterwords.csv"
            elif wordle_word_length == 5:
                valid_words_file = "5letterwords.csv"
            else:
                valid_words_file = "45letterwords.csv"

            with open(valid_words_file, "r") as f:
                VALID_WORDS = set(line.strip().lower() for line in f)

            if q["_id"]:
                await store_question_ids_in_mongo([q["_id"]], "wordle")

            print(f"Word: {word}")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting wordle questions:\n{traceback.format_exc()}")
            return

        num_of_guesses = wordle_word_length
        guess_num = 1
        right_answer = False
        sorted_users = []

        while guess_num <= num_of_guesses and not right_answer:
            await safe_send(channel, "\u200b\n⚠️🚨 Everyone's in! **One guess per person**!\n\u200b")
            await asyncio.sleep(1)
            await safe_send(channel, f"\u200b\n🟩🟨 Wordle {wordle_num}, Round {guess_num}...\n\u200b")
            await asyncio.sleep(1)

            img_buf = generate_wordle_image(word, wordle_guesses)
            embed = discord.Embed()
            file = discord.File(fp=img_buf, filename="wordle.png")
            embed.set_image(url="attachment://wordle.png")
            await safe_send(channel, embed=embed, file=file)

            start_time = asyncio.get_event_loop().time()
            processed_users = set()
            highest_score = 0
            top_user = None
            top_word = ""

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 20 and not right_answer:
                try:
                    timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                    msg = await bot.wait_for("message", timeout=timeout, check=check)
                    guess = msg.content.strip().lower()
                    user = msg.author.display_name
                    uid = msg.author.id
                    key = (uid, guess)

                    if uid in processed_users:
                        continue

                    if len(guess) != wordle_word_length:
                        continue

                    processed_users.add(uid)

                    if guess not in VALID_WORDS:
                        continue
                    if guess in wordle_guesses:
                        continue

                    score = wordle_score(word, guess)
                    #user_correct_answers[user] = user_correct_answers.get(user, 0) + score

                    prev_display, prev_score = user_correct_answers.get(uid, (user, 0))
                    user_correct_answers[uid] = (prev_display, prev_score + score)
                    
                    if guess == word.lower():
                        wordle_guesses.append(word)
                        img_buf = generate_wordle_image(word, wordle_guesses)
                        embed = discord.Embed()
                        file = discord.File(fp=img_buf, filename="wordle.png")
                        embed.set_image(url="attachment://wordle.png")
                        await safe_send(channel, file=file, embed=embed)
                        await safe_send(channel, f"\u200b\n✅🎉 Correct! **<@{uid}>** got it! **{word.upper()}** ({score})\n\u200b")
                        right_answer = True
                        break
                    else:
                        if score > highest_score:
                            highest_score = score
                            top_user = user
                            top_word = guess

                except asyncio.TimeoutError:
                    break

            if not right_answer and not top_user:
                await safe_send(channel, "\u200b\n❌😢 No (good) attempts...\n\u200b")
                wordle_guesses.append(" " * wordle_word_length)
            elif not right_answer:
                wordle_guesses.append(top_word)
                img_buf = generate_wordle_image(word, wordle_guesses)
                embed = discord.Embed()
                file = discord.File(fp=img_buf, filename="wordle.png")
                embed.set_image(url="attachment://wordle.png")
                await safe_send(channel, file=file, embed=embed)
                await safe_send(channel, f"\u200b\n🟡🎉 **{top_user}** had the closest guess! **{top_word.upper()}** ({highest_score})\n\u200b")

            await asyncio.sleep(2)

            sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

            if sorted_users:
                standings = "\n".join(
                    f"{i+1}. **{display_name}**: {score}" 
                    for i, (user_id, (display_name, score)) in enumerate(sorted_users)
                )
                await safe_send(channel, f"\u200b\n📊🏆 Standings\n{standings}\n\u200b")

            guess_num += 1

        if not right_answer:
            await safe_send(channel, f"\u200b\n❌😢 No one got the Wordle!\n\nAnswer: **{word.upper()}**\n\u200b")
        
        await asyncio.sleep(1)

        wordle_num = wordle_num + 1
        
        message = ""

        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                wordle_winner_id, (winner_name, winner_score) = sorted_users[0]
                return wordle_winner_id
            else:
                return None
            
        #if sorted_users:
        #    if wordle_num > num:
        #        message += "\u200b\n🏁🏆 Final Standings\n\u200b"
        #    else:   
        #        message += "\u200b\n📊🏆 Current Standings\n\u200b"

        #for counter, (user_id, (display_name, score)) in enumerate(sorted_users, start=1):
        #    message += f"{counter}. **{display_name}**: {score}\n"
            
        #if message:
        #    message += "\u200b"
        #    await safe_send(channel, message)
        
        await asyncio.sleep(3)

    #await asyncio.sleep(2)
    if sorted_users:
        wordle_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No points**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return wordle_winner_id
    else:
        return None
    




LIGHT_COLOR = (240, 217, 181)  # light squares
DARK_COLOR  = (181, 136,  99)  # dark squares

# Unicode chess pieces (fallback to letters if font lacks glyphs)
PIECE_UNICODE = {
    chess.PAWN:   ("♟", "♟"),     # Use solid black symbol for both, differentiate by color
    chess.KNIGHT: ("♞", "♞"),
    chess.BISHOP: ("♝", "♝"),
    chess.ROOK:   ("♜", "♜"),
    chess.QUEEN:  ("♛", "♛"),
    chess.KING:   ("♚", "♚"),
}

def _load_font(square_px: int, font_path: Optional[str]) -> Tuple[ImageFont.FreeTypeFont, bool]:
    """Try to load a TTF that supports chess glyphs. Return (font, supports_unicode_glyphs)."""
    size = int(square_px * 0.72)
    candidates = []
    if font_path:
        candidates.append(font_path)
    candidates.extend([
        "DejaVuSans.ttf",
        "NotoSansSymbols-Regular.ttf",
        "NotoSans-Regular.ttf",
        "/Library/Fonts/Arial Unicode.ttf",  # macOS common
        "ArialUnicode.ttf",
        "Symbola.ttf",
    ])
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size), True
        except Exception:
            continue
    # Fallback bitmap font (no proper chess glyphs)
    return ImageFont.load_default(), False

def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, stroke_width: int = 0):
    """Robust text size (works for bitmap or TrueType fonts)."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        return font.getsize(text)
    


def generate_chess_board(
    fen: str,
    move_uci: Optional[str] = None,
    square_px: int = 80,
    margin_px: int = 48,
    draw_coords: bool = True,
    font_path: Optional[str] = None,
    show_color: bool = True,
    hint: bool = False,
) -> tuple[io.BytesIO, Optional[str]]:
    """
    Render a chessboard PNG from FEN, optionally after applying a UCI move.
    Orientation: side-to-move in the FEN is shown at the bottom (w=White bottom, b=Black bottom).
    
    Args:
        show_color: If True, shows "White to Move" or "Black to Move" indicator (default True)
        hint: If True, highlights the origin square green regardless of show_color (default False)
    
    Returns a tuple of (BytesIO pointing at a PNG image, piece hint string or None).
    """
    # Build board and (optionally) apply first move
    board = chess.Board(fen)
    
    # Track move squares for highlighting and generate hint
    move_from_square = None
    move_to_square = None
    hint_square = None
    piece_hint = None

    if move_uci:
        try:
            mv = chess.Move.from_uci(move_uci.strip().lower())
            # Get piece hint before applying the move (regardless of legality)
            piece = board.piece_at(mv.from_square)
            if piece:
                piece_names = {
                    chess.PAWN: "Pawn",
                    chess.KNIGHT: "Knight", 
                    chess.BISHOP: "Bishop",
                    chess.ROOK: "Rook",
                    chess.QUEEN: "Queen",
                    chess.KING: "King"
                }
                piece_name = piece_names.get(piece.piece_type, "Piece")
                color = "White" if piece.color else "Black"
                square_name = chess.square_name(mv.from_square)
                piece_hint = f"Move the {color} {piece_name} ({square_name})"
            
            # Set hint square if hint mode is enabled
            if hint:
                hint_square = mv.from_square
            
            # Apply move and highlight squares only if show_color is False (solution mode)
            if not show_color:
                if mv in board.legal_moves:
                    move_from_square = mv.from_square
                    move_to_square = mv.to_square
                    board.push(mv)
                else:
                    # Still track squares for highlighting even if illegal
                    move_from_square = mv.from_square
                    move_to_square = mv.to_square
        except Exception as e:
            # For debugging - could be removed later
            piece_hint = f"Error parsing move: {str(e)}"

    # Always show from White's perspective (standard chess notation)
    bottom_is_white = True

    # Image geometry - add extra space at bottom for move indicator
    inner = square_px * 8
    coord_margin = (2 * margin_px if draw_coords else 0)
    move_text_height = int(square_px * 0.8)  # Extra space for larger move indicator
    total_width = inner + coord_margin
    total_height = inner + coord_margin + move_text_height
    origin = margin_px if draw_coords else 0

    img = Image.new("RGBA", (total_width, total_height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Coordinates for labels (from the viewing side)
    files_white = "abcdefgh"
    ranks_white = "12345678"
    if bottom_is_white:
        files_row = list(files_white)              # left→right: a..h
        ranks_col = list(reversed(ranks_white))   # top→bottom: 8..1
        file_iter = range(8)                      # files 0..7
        rank_iter = reversed(range(8))            # ranks 7..0 (8..1 at top)
    else:
        # From Black’s perspective, files are h..a left→right, ranks are 1..8 top→bottom
        files_row = list(reversed(files_white))   # left→right: h..a
        ranks_col = list(ranks_white)             # top→bottom: 1..8
        file_iter = reversed(range(8))            # files 7..0
        rank_iter = range(8)                      # ranks 0..7 (1..8 at top)

    # Draw squares
    # We'll map display (x,y) to an actual board square using file/rank mapping above.
    display_rank_indices = list(rank_iter)   # y-axis iteration for drawing
    display_file_indices = list(file_iter)   # x-axis iteration for drawing

    for y, r in enumerate(display_rank_indices):
        for x, f in enumerate(display_file_indices):
            sq = chess.square(f, r)  # Current square being drawn
            
            # Default square color
            color = LIGHT_COLOR if (x + y) % 2 == 0 else DARK_COLOR
            
            # Highlight squares
            if hint_square is not None and sq == hint_square:
                # Hint square - green highlight (takes priority)
                color = (100, 255, 100) if (x + y) % 2 == 0 else (80, 200, 80)
            elif move_from_square is not None and sq == move_from_square:
                # Origin square - red highlight
                color = (255, 100, 100) if (x + y) % 2 == 0 else (200, 80, 80)
            elif move_to_square is not None and sq == move_to_square:
                # Destination square - green highlight
                color = (100, 255, 100) if (x + y) % 2 == 0 else (80, 200, 80)
            
            x0 = origin + x * square_px
            y0 = origin + y * square_px
            x1 = x0 + square_px
            y1 = y0 + square_px
            draw.rectangle([x0, y0, x1, y1], fill=color)

    # Labels (files on bottom/top, ranks on left/right)
    if draw_coords:
        # Create a larger font for coordinates - about 1/3 of square size
        coord_size = max(12, int(square_px * 0.33))
        try:
            coord_font = ImageFont.truetype(os.path.join("fonts", "DejaVuSans.ttf"), size=coord_size)
        except:
            coord_font = ImageFont.load_default()

        # Files (bottom)
        for i, ch in enumerate(files_row):
            tx = origin + i * square_px + square_px // 2
            ty = origin + 8 * square_px + int(margin_px * 0.25)
            w, h = _text_size(draw, ch, coord_font)
            # Draw black background box
            padding = 2
            box_x1 = tx - w // 2 - padding
            box_y1 = ty - padding
            box_x2 = tx + w // 2 + padding
            box_y2 = ty + h + padding
            draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(0, 0, 0))
            draw.text((tx - w // 2, ty), ch, font=coord_font, fill=(255, 255, 255))

        # Files (top)
        for i, ch in enumerate(files_row):
            tx = origin + i * square_px + square_px // 2
            ty = int(margin_px * 0.15)
            w, h = _text_size(draw, ch, coord_font)
            # Draw black background box
            padding = 2
            box_x1 = tx - w // 2 - padding
            box_y1 = ty - padding
            box_x2 = tx + w // 2 + padding
            box_y2 = ty + h + padding
            draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(0, 0, 0))
            draw.text((tx - w // 2, ty), ch, font=coord_font, fill=(255, 255, 255))

        # Ranks (left)
        for i, ch in enumerate(ranks_col):
            tx = int(margin_px * 0.20)
            ty = origin + i * square_px + square_px // 2
            w, h = _text_size(draw, ch, coord_font)
            # Draw black background box
            padding = 2
            box_x1 = tx - padding
            box_y1 = ty - h // 2 - padding
            box_x2 = tx + w + padding
            box_y2 = ty + h // 2 + padding
            draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(0, 0, 0))
            draw.text((tx, ty - h // 2), ch, font=coord_font, fill=(255, 255, 255))

        # Ranks (right)
        for i, ch in enumerate(ranks_col):
            tx = origin + 8 * square_px + int(margin_px * 0.60)
            ty = origin + i * square_px + square_px // 2
            w, h = _text_size(draw, ch, coord_font)
            # Draw black background box
            padding = 2
            box_x1 = tx - w - padding
            box_y1 = ty - h // 2 - padding
            box_x2 = tx + padding
            box_y2 = ty + h // 2 + padding
            draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=(0, 0, 0))
            draw.text((tx - w, ty - h // 2), ch, font=coord_font, fill=(255, 255, 255))

    # Piece font
    piece_font, can_use_unicode = _load_font(square_px, font_path)
    stroke_w = max(1, int(square_px * 0.06))

    # Draw pieces according to viewing orientation
    for y, r in enumerate(display_rank_indices):
        for x, f in enumerate(display_file_indices):
            sq = chess.square(f, r)  # file, rank (0-based)
            piece = board.piece_at(sq)
            if not piece:
                continue

            if can_use_unicode:
                glyph = PIECE_UNICODE[piece.piece_type][0]  # Use same symbol for both colors
                # White pieces: white fill with black stroke; black pieces: black fill with white stroke
                is_white = piece.color
                fill = (255, 255, 255) if is_white else (0, 0, 0)
                stroke = (0, 0, 0) if is_white else (255, 255, 255)
            else:
                # Fallback letter
                glyph = piece.symbol().upper() if piece.color else piece.symbol().lower()
                fill = (0, 0, 0)
                stroke = None

            gx = origin + x * square_px + square_px // 2
            gy = origin + y * square_px + square_px // 2
            tw, th = _text_size(draw, glyph, piece_font, stroke_width=stroke_w if can_use_unicode else 0)
            pos = (gx - tw // 2, gy - th // 2)

            draw.text(
                pos,
                glyph,
                font=piece_font,
                fill=fill,
                stroke_width=(stroke_w if can_use_unicode else 0),
                stroke_fill=stroke if can_use_unicode else None,
                anchor=None,
            )

    # Add move indicator text at the bottom (only if show_color is True)
    if show_color:
        move_text = "White to Move" if board.turn else "Black to Move"
        
        # Use much larger font for move indicator - about half the square size
        move_text_size = max(24, int(square_px * 0.5))
        try:
            move_font = ImageFont.truetype(os.path.join("fonts", "DejaVuSans.ttf"), size=move_text_size)
        except:
            move_font = ImageFont.load_default()
        
        # Position text at bottom center
        text_w, text_h = _text_size(draw, move_text, move_font)
        text_x = (total_width - text_w) // 2
        text_y = total_height - move_text_height + (move_text_height - text_h) // 2
        
        # Draw background box with color matching the side to move
        padding = 12
        box_x1 = text_x - padding
        box_y1 = text_y - padding
        box_x2 = text_x + text_w + padding
        box_y2 = text_y + text_h + padding
        
        if board.turn:  # White's turn
            bg_color = (255, 255, 255)  # White background
            text_color = (0, 0, 0)      # Black text
        else:  # Black's turn
            bg_color = (0, 0, 0)        # Black background
            text_color = (255, 255, 255) # White text
            
        draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=bg_color)
        draw.text((text_x, text_y), move_text, font=move_font, fill=text_color)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf, piece_hint




async def ask_chess_challenge(winner, winner_id, num=5):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/chess1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/chess2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/chess3.gif",
    ]

    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n♟️👑 **Checkmate**: What's Your Move?\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(5)

    user_correct_answers = {}

    # Ask for number of images to fuse
    await safe_send(channel, f"\u200b\n🕹️🚀 **<@{winner_id}>**, select the mode:\n\n🧸 **Normal** or 🧨 **Okrap**.\n\u200b")
    
    chess_mode = None
    try:
        msg = await bot.wait_for("message", timeout=magic_time + 5, check=lambda m: m.author.id == winner_id and m.author != bot.user and m.channel == channel and m.content.lower() in {"normal", "okrap"})
        game_mode = msg.content.lower()
        await msg.add_reaction("✅")
    except asyncio.TimeoutError:
        game_mode = "normal"

    if game_mode == "okrap":
        hint_mode = False
    else:
        hint_mode = True
    
    await safe_send(channel, f"\u200b\n💥🤯 Ok...ra! We're going with **{game_mode.upper()}** baby!\n\u200b")

    if num > 1:
        await safe_send(channel, f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b")
        await asyncio.sleep(3)

    chess_num = 1
    while chess_num <= num:
        try:
            recent_chess_ids = await get_recent_question_ids_from_mongo("chess")
            chess_collection = db["chess_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_chess_ids)}}},
                {"$sample": {"size": 10}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in chess_collection.aggregate(pipeline)]
            q = questions[0]
            starting_board = q["FEN"]
            best_move = q["Moves"]
            chess_url = q["GameUrl"]

            chess_guesses = []

            if q["_id"]:
                await store_question_ids_in_mongo([q["_id"]], "chess")

            print(f"Best Move: {best_move}")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting chess questions:\n{traceback.format_exc()}")
            return

        num_of_guesses = 1
        guess_num = 1
        right_answer = False
        sorted_users = []

        while guess_num <= num_of_guesses and not right_answer:
            await safe_send(channel, "\u200b\n⚠️🚨 Everyone's in!\n\u200b")
            await asyncio.sleep(1)
            await safe_send(channel, f"\u200b\n♟️👑 **Puzzle {chess_num}**: What's the **best** move?\n\u200b")
            await asyncio.sleep(1)

            img_buf, hint = generate_chess_board(starting_board, best_move, show_color=True, hint=hint_mode)
            embed = discord.Embed()
            file = discord.File(fp=img_buf, filename="chess.png")
            embed.set_image(url="attachment://chess.png")
            await safe_send(channel, embed=embed, file=file)
            if game_mode == "normal":
                await safe_send(channel, f"\u200b\n **Hint**: {hint}\u200b\n")
                await asyncio.sleep(2)

            start_time = asyncio.get_event_loop().time()

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 30 and not right_answer:
                try:
                    timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                    msg = await bot.wait_for("message", timeout=timeout, check=check)
                    guess = msg.content.strip().lower().replace(" ", "")
                    user = msg.author.display_name
                    uid = msg.author.id
                    key = (uid, guess)

                    if guess == best_move.lower():
                        await msg.add_reaction("✅")
                        prev_display, prev_score = user_correct_answers.get(uid, (user, 0))
                        user_correct_answers[uid] = (prev_display, prev_score + 1)
                        img_buf, hint = generate_chess_board(starting_board, best_move, show_color=False)
                        embed = discord.Embed()
                        file = discord.File(fp=img_buf, filename="chess.png")
                        embed.set_image(url="attachment://chess.png")
                        await safe_send(channel, file=file, embed=embed)
                        await safe_send(channel, f"\u200b\n✅🎉 Correct! **<@{uid}>** got it! **{best_move.upper()}**\n\u200b")
                        right_answer = True
                        break
                except asyncio.TimeoutError:
                    break

            if not right_answer:
                img_buf, hint = generate_chess_board(starting_board, best_move, show_color=False)
                embed = discord.Embed()
                file = discord.File(fp=img_buf, filename="chess.png")
                embed.set_image(url="attachment://chess.png")
                await safe_send(channel, file=file, embed=embed)
                await safe_send(channel, f"\u200b\n❌😢 No one got the answer!\n\nAnswer: **{best_move.upper()}**\n\u200b")

            await asyncio.sleep(2)

            summary = f"\u200b\nExplore this puzzle:\nhttps://www.lichess.org/{chess_url}\n\u200b"
            await safe_send(channel, summary)

            await asyncio.sleep(2)

            sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

            if sorted_users:
                standings = "\n".join(
                    f"{i+1}. **{display_name}**: {score}" 
                    for i, (user_id, (display_name, score)) in enumerate(sorted_users)
                )
                await safe_send(channel, f"\u200b\n📊🏆 Standings\n{standings}\n\u200b")

            guess_num += 1
        
        await asyncio.sleep(1)

        chess_num = chess_num + 1
        
        message = ""

        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                chess_winner_id, (winner_name, winner_score) = sorted_users[0]
                return chess_winner_id
            else:
                return None
        
        await asyncio.sleep(3)

    #await asyncio.sleep(2)
    if sorted_users:
        chess_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No points**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return chess_winner_id
    else:
        return None



        
        
async def ask_microscopic_challenge(winner, winner_id, num=3):
    global wf_winner
    wf_winner = True

    microscopic_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/microscopic1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/microscopic2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/microscopic3.gif"
    ]

    microscopic_gif_url = random.choice(microscopic_gifs)
    await safe_send(channel, content="\u200b\n🔬🔍 **Microscopic Mystery**: Identify the Magnified Images\n\u200b", embed=discord.Embed().set_image(url=microscopic_gif_url))
    await asyncio.sleep(5)

    user_data = {}  # Track scores: {user_id: (display_name, score)}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    microscopic_num = 1
    while microscopic_num <= num:
        try:
            recent_microscopic_ids = await get_recent_question_ids_from_mongo("microscopic")
            
            microscopic_collection = db["jigsaw_questions"]
            pipeline_microscopic = [
                {
                    "$match": {
                        "_id": {"$nin": list(recent_microscopic_ids)},
                        "question": "caltech"
                    }
                },
                {"$sample": {"size": 10}},
                {"$sample": {"size": 1}}
            ]

            microscopic_questions = list(await microscopic_collection.aggregate(pipeline_microscopic).to_list(length=None))
            microscopic_question = microscopic_questions[0]
            microscopic_image_url = microscopic_question["url"]
            microscopic_answers = microscopic_question["answers"]
            microscopic_main_answer = microscopic_answers[0]
            microscopic_category = microscopic_question["category"]
            microscopic_question_id = microscopic_question["_id"]

            print(f"Answer: {microscopic_answers}")

            if microscopic_question_id:
                await store_question_ids_in_mongo([microscopic_question_id], "microscopic")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            error_details = traceback.format_exc()
            print(f"Error selecting microscopic questions: {e}\nDetailed traceback:\n{error_details}")
            return None

        right_answer = False
        
        # Zoom levels: 5x, 3.5x, 2x
        for zoom_level in [5.0, 3.5, 2.0]:
            if right_answer == True:
                break

            # Create zoomed image (using blur as approximation for zoom)
            microscopic_image_blurred = await blur_image(microscopic_image_url, blur_strength=zoom_level)

            message = f"\u200b\n⚠️🚨 **Everyone's in!**\n"
            message += f"\n🗣💬❓ **Image {microscopic_num}** of {num}: Who or what is THIS?!?\n"
            message += f"\n🔬🔍 Zoom Level: **{zoom_level}x**\n\u200b"

            await safe_send(channel, message)
            await asyncio.sleep(2)

            image_file = discord.File(microscopic_image_blurred, filename="microscopic.png")
            embed = discord.Embed().set_image(url="attachment://microscopic.png")
            await safe_send(channel, content="", file=image_file, embed=embed)

            start_time = asyncio.get_event_loop().time()

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 20 and right_answer == False:
                try:
                    msg = await bot.wait_for("message", timeout=1, check=check)
                    
                    sender_display_name = msg.author.display_name
                    sender_user_id = msg.author.id
                    message_content = msg.content

                    user_guess = normalize_text(message_content).replace(" ", "")

                    for microscopic_answer in microscopic_answers:
                        normalized_answer = normalize_text(microscopic_answer).replace(" ", "")
                        if fuzzy_match(user_guess, normalized_answer, microscopic_category, microscopic_image_url):
                            message = f"\u200b\n✅🎉 Correct! **{sender_display_name}** got it! **{microscopic_answer.upper()}**\n"
                            all_answers_str = "\n".join(f"**{answer.upper()}**" for answer in microscopic_answers)
                            #message += f"\n📝🧠 **All Answers:**\n{all_answers_str}\n\u200b"
                            await safe_send(channel, message)
                            
                            # Show original image
                            embed = discord.Embed().set_image(url=microscopic_image_url)
                            await safe_send(channel, content="", embed=embed)

                            right_answer = True

                            if sender_user_id not in user_data:
                                user_data[sender_user_id] = (sender_display_name, 0)
                            user_data[sender_user_id] = (sender_display_name, user_data[sender_user_id][1] + 1)
                            break

                    if right_answer == True:
                        break

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"Error processing events: {e}")

        if right_answer == False:
            message = f"\u200b\n⏰❌ Time's up! The answer was: **{microscopic_main_answer.upper()}**\n"
            #all_answers_str = "\n".join(f"**{answer.upper()}**" for answer in microscopic_answers)
            #message += f"\n📝🧠 **All Answers:**\n{all_answers_str}\n\u200b"
            await safe_send(channel, message)
            
            # Show original image
            embed = discord.Embed().set_image(url=microscopic_image_url)
            await safe_send(channel, content="", embed=embed)

        microscopic_num += 1
        
        # Show standings after each round (like ask_music_challenge)
        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                microscopic_winner_id, (display_name, final_score) = sorted_users[0]
                return microscopic_winner_id
            else:
                return None

        if sorted_users:
            if microscopic_num > num:
                message = "\u200b\n🏁🏆 **Final Standings**\n"
            else:
                message = "\u200b\n📊🏆 **Current Standings**\n"

            for counter, (_, (display_name, count)) in enumerate(sorted_users, start=1):
                message += f"{counter}. **{display_name}**: {count}\n"

            if message:
                await safe_send(channel, message)
        
        await asyncio.sleep(2)

    # Final winner announcement
    if sorted_users:
        microscopic_winner_id, (display_name, final_score) = sorted_users[0]
        await safe_send(channel, f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b")
    else:
        await safe_send(channel, f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b")

    await asyncio.sleep(3)
    
    if sorted_users:
        return microscopic_winner_id
    else:
        return None

async def ask_fusion_challenge(winner, winner_id, num=3):
    global wf_winner
    wf_winner = True

    fusion_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/fusion1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/fusion2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/fusion3.gif"
    ]
    
    fusion_gif_url = random.choice(fusion_gifs)
    await safe_send(channel, content="\u200b\n🧬☢️ **Fusion Challenge**: Identify the Fused Images\n\u200b", embed=discord.Embed().set_image(url=fusion_gif_url))
    await asyncio.sleep(5)

    user_correct_answers = {}

    # Ask for number of images to fuse
    await safe_send(channel, f"\u200b\n🧬🔢 **<@{winner_id}>**, how many images to fuse together?\n\n👉👉 **2**, **3**, **4**, or **5**\n\u200b")
    
    num_images = None
    try:
        msg = await bot.wait_for("message", timeout=magic_time + 5, check=lambda m: m.author.id == winner_id and m.author != bot.user and m.channel == channel and m.content in {"2", "3", "4", "5"})
        num_images = msg.content
        await msg.add_reaction("✅")
    except asyncio.TimeoutError:
        pass
    
    # Fallback or confirmation
    if num_images:
        message = f"\u200b\n💥🤯 Ok...ra! We're fusing **{num_images}** images together!\n\u200b"
    else:
        message = "\u200b\n😬⏱️ Time's up! We'll fuse **3** images together.\n\u200b"
        num_images = "3"

    await safe_send(channel, message)

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    user_data = {}  # Track cumulative scores: {user_id: (display_name, total_score)}
    
    fusion_num = 1
    while fusion_num <= num:
        try:
            recent_fusion_ids = await get_recent_question_ids_from_mongo("fusion")

            fusion_collection = db["jigsaw_questions"]
            num_images_int = int(num_images)
            
            # Get more images to pick N different ones
            pipeline_fusion = [
                {
                    "$match": {
                        "_id": {"$nin": list(recent_fusion_ids)},
                        "question": "caltech"
                    }
                },
                {"$sample": {"size": num_images_int * 10}},  # Get plenty to pick N different ones
                {"$sample": {"size": num_images_int}}    # Pick N images to fuse
            ]

            fusion_questions = list(await fusion_collection.aggregate(pipeline_fusion).to_list(length=None))
            
            # Store all images, answers, categories, etc.
            fusion_images = []
            fusion_answers_list = []
            fusion_categories = []
            fusion_question_ids = []
            original_image_urls = []
            
            for i, fusion_question in enumerate(fusion_questions):
                fusion_image_url = fusion_question["url"]
                fusion_answers = fusion_question["answers"]
                fusion_category = fusion_question["category"]
                fusion_question_id = fusion_question["_id"]
                
                fusion_images.append(fusion_image_url)
                fusion_answers_list.append(fusion_answers)
                fusion_categories.append(fusion_category)
                fusion_question_ids.append(fusion_question_id)
                original_image_urls.append(fusion_image_url)
                
                print(f"Answer {i+1}: {fusion_answers}")

            if fusion_question_ids:
                await store_question_ids_in_mongo(fusion_question_ids, "fusion")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            error_details = traceback.format_exc()
            print(f"Error selecting fusion questions: {e}\nDetailed traceback:\n{error_details}")
            return None

        # Track which images have been found globally and by whom for this round
        images_found = set()  # Global set of found image indices
        user_round_scores = {}  # Track scores for current round only: {user_id: (display_name, round_score)}
        answer_found_by = {}  # {(image_index, answer): user_name}
        
        # For Discord, we'll show all images in a blended/composite way
        # Since we can't easily blend images in Discord, we'll show them as separate challenges
        for blend_level in [0.9]:  # Only one "blend" level for Discord
            
            if len(images_found) >= num_images_int:  # All images found
                break

            message = f"\u200b\n⚠️🚨 **Everyone's in!**\n"
            message += f"\n🗣💬❓ **Fusion {fusion_num}** of {num}: First to guess each image gets the point\n"
            
            # Show current progress  
            if user_round_scores:
                message += f"\n🏃‍♂️ **Round Progress:**\n"
                for user_id, (display_name, score) in user_round_scores.items():
                    message += f"**{display_name}**: {score}/{num_images} images\n"
                message += f"Images found: {len(images_found)}/{num_images}\n"
            message += "\u200b"

            await safe_send(channel, message)
            await asyncio.sleep(2)

            # Blend only the unfound images together into one fused image
            unfound_images = [fusion_images[i] for i in range(len(fusion_images)) if i not in images_found]
            if unfound_images:
                fused_image_buffer = await blend_multiple_images(unfound_images, blend_ratio=blend_level)
                if fused_image_buffer:
                    remaining_count = len(unfound_images)
                    image_file = discord.File(fused_image_buffer, filename="fused_images.png")
                    embed = discord.Embed(title=f"🧬 {remaining_count} Images Fused Together").set_image(url="attachment://fused_images.png")
                    await safe_send(channel, content="", file=image_file, embed=embed)

            start_time = asyncio.get_event_loop().time()

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 30 and len(images_found) < num_images_int:
                try:
                    msg = await bot.wait_for("message", timeout=1, check=check)
                    
                    sender_display_name = msg.author.display_name
                    sender_user_id = msg.author.id
                    message_content = msg.content

                    user_guess = normalize_text(message_content).replace(" ", "")

                    # Check against all unfound images
                    for i, fusion_answers in enumerate(fusion_answers_list):
                        if i in images_found:  # Skip already found images
                            continue
                            
                        for fusion_answer in fusion_answers:
                            normalized_answer = normalize_text(fusion_answer).replace(" ", "")
                            if fuzzy_match(user_guess, normalized_answer, fusion_categories[i], fusion_images[i]):
                                
                                # Mark this image as found
                                images_found.add(i)
                                answer_found_by[(i, fusion_answer)] = sender_display_name
                                
                                if sender_user_id not in user_round_scores:
                                    user_round_scores[sender_user_id] = (sender_display_name, 0)
                                user_round_scores[sender_user_id] = (sender_display_name, user_round_scores[sender_user_id][1] + 1)
                                
                                remaining_images = num_images_int - len(images_found)
                                message = f"\u200b\n✅🎉 Correct! **{sender_display_name}** got **{fusion_answer.upper()}**! "
                                if remaining_images > 0:
                                    message += f"({remaining_images} more to find)\n\u200b"
                                else:
                                    message += "All images found!\n\u200b"
                                await safe_send(channel, message)
                                break

                    if len(images_found) >= num_images_int:
                        await asyncio.sleep(2)
                        break

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"Error processing events: {e}")

        # Show all images (found and unfound) at the end
        for i in range(num_images_int):
            main_answer = fusion_answers_list[i][0]
            
            # Check if this image was found
            if i in images_found:
                # Find who found it
                found_by = "Unknown"
                for (img_idx, answer), user in answer_found_by.items():
                    if img_idx == i:
                        found_by = user
                        break
                status_text = f"✅ Found by **{found_by}**"
            else:
                status_text = "❌ **Not found**"
            
            # Show image with title format "Image n: MAIN_ANSWER"
            embed = discord.Embed(
                title=f"Image {i+1}: {main_answer.upper()}", 
                description=status_text,
                color=0x00ff00 if i in images_found else 0xff0000
            ).set_image(url=original_image_urls[i])
            await safe_send(channel, content="", embed=embed)
            await asyncio.sleep(2)

        # Add round scores to cumulative scores
        for user_id, (display_name, round_score) in user_round_scores.items():
            if user_id not in user_data:
                user_data[user_id] = (display_name, 0)
            user_data[user_id] = (display_name, user_data[user_id][1] + round_score)

        fusion_num += 1
        
        # Show standings after each round
        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)
        
        if num == 1:
            if sorted_users:
                winner_id, (winner_name, _) = sorted_users[0]
                return winner_id
            else:
                return None
        
        message = ""
        if sorted_users:
            if fusion_num > num:
                message += "\u200b\n🏁🏆 **Final Standings**\n"
            else:
                message += "\u200b\n📊🏆 **Current Standings**\n"

            for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
                message += f"{counter}. **{display_name}**: {count} points\n"
            message += "\u200b"
        
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(2)

    # Final winner announcement and return
    if user_data:
        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)
        winner_id, (winner_name, winner_score) = sorted_users[0]
        await safe_send(channel, f"\u200b\n🎉🥇 The winner is **{winner_name}** with {winner_score} points!\n\u200b")
        await asyncio.sleep(3)
        return winner_id
    else:
        await safe_send(channel, f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b")
        await asyncio.sleep(3)
        return None
    
    
        

async def blend_multiple_images(image_urls, blend_ratio=0.5):
    """
    Blends multiple images together with specified ratio for Discord
    """
    try:
        images = []
        min_width = float('inf')
        min_height = float('inf')
        
        # Download all images and find minimum dimensions
        for image_url in image_urls:
            response = requests.get(image_url)
            if response.status_code != 200:
                raise Exception(f"Failed to download image from {image_url}")
            
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            images.append(image)
            
            min_width = min(min_width, image.size[0])
            min_height = min(min_height, image.size[1])
        
        # Resize all images to the same size
        for i in range(len(images)):
            images[i] = images[i].resize((min_width, min_height), Image.LANCZOS)
        
        # Blend all images together
        if len(images) == 1:
            blended_image = images[0]
        else:
            # Start with first image
            blended_image = images[0]
            
            # Blend each subsequent image
            for i in range(1, len(images)):
                # Equal blending: each image gets equal weight
                alpha = 1.0 / (i + 1)
                blended_image = Image.blend(blended_image, images[i], alpha)
        
        # Resize the final blended image to be larger with fixed width
        target_width = 800  # Fixed horizontal width for better visibility
        current_width, current_height = blended_image.size
        aspect_ratio = current_height / current_width
        target_height = int(target_width * aspect_ratio)
        
        # Resize maintaining aspect ratio
        blended_image = blended_image.resize((target_width, target_height), Image.LANCZOS)
        
        # Save to memory buffer
        image_buffer = io.BytesIO()
        blended_image.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        
        return image_buffer
            
    except Exception as e:
        print(f"Error blending multiple images: {e}")
        return None

async def generate_estimation_puzzle_unique(target_count, target_shape, target_color, available_combinations):
    """
    Generate an image with unique shape/color combinations for Discord
    """
    try:        
        # Image dimensions - increased size for better spacing
        width, height = 1200, 900
        
        # Create white background
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)
        
        # Generate positions for all objects
        all_positions = []
        
        # Function to check if position overlaps with existing ones
        def is_valid_position(x, y, min_distance=20):  # Reduced spacing for more density
            for existing_x, existing_y in all_positions:
                if abs(x - existing_x) < min_distance and abs(y - existing_y) < min_distance:
                    return False
            return True
        
        def draw_shape(x, y, shape, color, size):
            """Draw a shape at given position"""
            if shape == 'circle':
                draw.ellipse([x-size, y-size, x+size, y+size], fill=color)
            elif shape == 'triangle':
                points = [(x, y-size), (x-size, y+size), (x+size, y+size)]
                draw.polygon(points, fill=color)
            elif shape == 'square':
                draw.rectangle([x-size, y-size, x+size, y+size], fill=color)
            elif shape == 'x':
                # Draw X with two lines
                draw.line([(x-size, y-size), (x+size, y+size)], fill=color, width=3)
                draw.line([(x-size, y+size), (x+size, y-size)], fill=color, width=3)
            elif shape == 'diamond':
                points = [(x, y-size), (x+size, y), (x, y+size), (x-size, y)]
                draw.polygon(points, fill=color)
        
        # Place target shapes
        target_positions = []
        attempts = 0
        while len(target_positions) < target_count and attempts < target_count * 10:
            x = random.randint(20, width - 20)
            y = random.randint(20, height - 20)
            
            if is_valid_position(x, y):
                target_positions.append((x, y))
                all_positions.append((x, y))
            attempts += 1
        
        # Draw target shapes
        for x, y in target_positions:
            size = random.randint(8, 15)
            draw_shape(x, y, target_shape, target_color, size)
        
        # Calculate how many of each distractor type to place
        if available_combinations:
            # Distribute distractors evenly among available combinations
            total_distractors = target_count * 2  # Reduced multiplier since we have fewer combinations
            distractors_per_type = total_distractors // len(available_combinations)
            
            # Place each type of distractor
            for shape, color_name, color_rgb in available_combinations:
                distractors_placed = 0
                attempts = 0
                
                while distractors_placed < distractors_per_type and attempts < distractors_per_type * 10:
                    x = random.randint(20, width - 20)
                    y = random.randint(20, height - 20)
                    
                    if is_valid_position(x, y):
                        size = random.randint(6, 12)
                        draw_shape(x, y, shape, color_rgb, size)
                        
                        all_positions.append((x, y))
                        distractors_placed += 1
                    attempts += 1
        
        # Save to memory buffer
        image_buffer = io.BytesIO()
        img.save(image_buffer, format="PNG")
        image_buffer.seek(0)

        return image_buffer
            
    except Exception as e:
        print(f"Error generating estimation puzzle: {e}")
        return None

async def ask_tally_challenge(winner, winner_id, num=3):
    global wf_winner
    wf_winner = True

    user_data = {}  # Track scores: {user_id: (display_name, total_distance, participated_rounds)}
    # participated_rounds is a set of round numbers the user participated in
    round_actual_counts = {}  # Track actual count for each round: {round_number: actual_count}

    estimation_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/tally1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/tally2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/tally3.gif",
    ]

    estimation_gif_url = random.choice(estimation_gifs)
    await safe_send(channel, content="\u200b\n🔢🎯 **Tally**: Estimate the Shapes!**\n\u200b", embed=discord.Embed().set_image(url=estimation_gif_url))
    await asyncio.sleep(3)

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    estimation_num = 1
    while estimation_num <= num:

        # Define available shapes and colors
        shapes = ['circle', 'triangle', 'square', 'x', 'diamond']
        colors = [
            ('red', (255, 0, 0)),
            ('green', (0, 255, 0)),
            ('blue', (0, 0, 255)),
            ('orange', (255, 165, 0)),
            ('purple', (128, 0, 128)),
            ('pink', (255, 192, 203))
        ]
        
        # Create all possible combinations
        all_combinations = []
        for shape in shapes:
            for color_name, color_rgb in colors:
                all_combinations.append((shape, color_name, color_rgb))
        
        # Randomly select target combination
        target_combination = random.choice(all_combinations)
        target_shape, target_color_name, target_color_rgb = target_combination
        
        # Remove target combination and any that share shape or color
        available_combinations = []
        for shape, color_name, color_rgb in all_combinations:
            if shape != target_shape and color_name != target_color_name:
                available_combinations.append((shape, color_name, color_rgb))
        
        # Generate random number of target objects between 50-300
        actual_count = random.randint(50, 300)
        estimation_buffer = await generate_estimation_puzzle_unique(
            actual_count, target_shape, target_color_rgb, available_combinations
        )
        
        print(f"Target: {target_color_name} {target_shape}s, Actual Count: {actual_count}")
        
        user_guesses = {}  # Track each user's first guess {user_name: guess_number}
        exact_winner = None  # Track if someone got it exactly right
            
        message = f"\u200b\n⚠️🚨 **Everyone's in!**\n"
        message += f"\n🔢🎯 **Round {estimation_num}** of {num}: Estimate the **{target_color_name.upper()} {target_shape.upper()}S** only!\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(2)
        
        message = f"\u200b\n⚠️ **One guess per player** - 1st numeric guess counts!\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(2)
        
        if estimation_buffer:
            image_file = discord.File(estimation_buffer, filename="estimation.png")
            embed = discord.Embed().set_image(url="attachment://estimation.png")
            await safe_send(channel, content="", file=image_file, embed=embed)
        await asyncio.sleep(2)

        start_time = asyncio.get_event_loop().time()

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 30:
            try:
                msg = await bot.wait_for("message", timeout=1, check=check)
                
                sender_display_name = msg.author.display_name
                sender_user_id = msg.author.id
                message_content = msg.content
                
                # Skip if user already made a guess
                if sender_user_id in user_guesses:
                    continue
                
                # Extract first number from message
                numbers = re.findall(r'\d+', message_content)
                if numbers:
                    user_guess = int(numbers[0])
                    user_guesses[sender_user_id] = (sender_display_name, user_guess)
                    
                    # Check for exact match
                    if user_guess == actual_count:
                        exact_winner = sender_display_name


            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing events: {e}")

        # Process all guesses normally (exact matches will naturally get 0 distance)
        if user_guesses:
            # Calculate distances from actual count
            user_distances = {}
            for user_id, (display_name, guess) in user_guesses.items():
                distance = abs(guess - actual_count)
                user_distances[user_id] = (display_name, distance)
            
            # Add distance to each user's cumulative score and mark round as participated
            for user_id, (display_name, distance) in user_distances.items():
                if user_id not in user_data:
                    user_data[user_id] = (display_name, 0, set())
                    # Add penalty for all previous rounds this user missed using historic actual counts
                    penalty_for_previous = 0
                    for round_num in range(1, estimation_num):
                        if round_num in round_actual_counts:
                            penalty_for_previous += round_actual_counts[round_num]
                    if penalty_for_previous > 0:
                        user_data[user_id] = (display_name, penalty_for_previous, set())
                
                curr_name, curr_distance, participated_rounds = user_data[user_id]
                participated_rounds.add(estimation_num)
                user_data[user_id] = (curr_name, curr_distance + distance, participated_rounds)
            
            # Sort by distance (closest first) for display
            sorted_results = sorted(user_distances.items(), key=lambda x: x[1][1])
            
            # Show exact winner announcement if there was one
            if exact_winner:
                exact_message = f"\u200b\n🎯💥 BULLSEYE! **{exact_winner}** got it EXACTLY right!\n\u200b"
                #exact_message += f"\n🏆 **{actual_count}** {target_color_name} {target_shape}s - PERFECT!\n\u200b"
                await safe_send(channel, exact_message)
            
            # Show results
            message = f"\u200b\n🎯 Actual count: **{actual_count}** {target_color_name} {target_shape}s\n"
            message += f"\n🏆 **Top 3 Closest Guesses:**\n"
            
            for i, (user_id, (display_name, distance)) in enumerate(sorted_results[:3]):
                _, guess = user_guesses[user_id]
                if i == 0:
                    message += f"🥇 **{display_name}**: {guess} (off by {distance}) - **CLOSEST!**\n"
                elif i == 1:
                    message += f"🥈 **{display_name}**: {guess} (off by {distance})\n"
                elif i == 2:
                    message += f"🥉 **{display_name}**: {guess} (off by {distance})\n"
            message += "\u200b"
            
            await safe_send(channel, message)
            await asyncio.sleep(2)
        else:
            message = f"\u200b\n❌😢 **No guesses received!**\n\nActual count: **{actual_count}** {target_color_name} {target_shape}s\n\u200b"
            await safe_send(channel, message)
    
        await asyncio.sleep(2)
        
        # Store the actual count for this round
        current_round = estimation_num
        round_actual_counts[current_round] = actual_count
        
        estimation_num += 1
        
        # Add actual_count penalty for users who didn't participate in this round
        for user_id, (display_name, total_distance, participated_rounds) in list(user_data.items()):
            # If user didn't participate in the current round, add penalty
            if current_round not in participated_rounds:
                user_data[user_id] = (display_name, total_distance + actual_count, participated_rounds)
                        
        # Sort by lowest cumulative distance (ascending order - lower is better)
        message = ""
        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=False)

        if num == 1:
            if sorted_users:
                tally_winner_id, (display_name, total_distance, participated_rounds) = sorted_users[0]
                return tally_winner_id
            else:
                return None
            
        if sorted_users:
            if estimation_num > num:
                message += "\u200b\n🏁🏆 **Final Standings (Distance)**\n"
            else:   
                message += "\u200b\n📊🏆 **Current Standings (Distance)**\n"

            for counter, (user_id, (display_name, total_distance, participated_rounds)) in enumerate(sorted_users, start=1):
                rounds_count = len(participated_rounds)
                message += f"{counter}. **{display_name}**: {total_distance}\n"
            message += "\u200b"
            
            await safe_send(channel, message)
            await asyncio.sleep(2)
        
    await asyncio.sleep(2)
    
    if sorted_users:
        tally_winner_id, (winner_name, total_distance, participated_rounds) = sorted_users[0]
        rounds_count = len(participated_rounds)
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}** with a total distance of **{total_distance}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No guesses made**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    await asyncio.sleep(3)
    
    if sorted_users:
        return tally_winner_id
    else:
        return None

async def ask_currency_challenge(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True
    currency_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/currency1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/currency2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/currency3.gif",
    ]
    currency_gif_url = random.choice(currency_gifs)
    await safe_send(channel, content="\u200b\n🌍💵 **XXXX**: Four X, Forex, Foriegn Exchange\n\u200b", embed=discord.Embed().set_image(url=currency_gif_url))
    await asyncio.sleep(5)
    
    # Get cached currency data FIRST before asking for user input
    #await safe_send(channel, "\u200b\n🔄 Loading currency data...\n\u200b")
    currency_data = await get_cached_currency_data()
    if not currency_data:
        await safe_send(channel, "\u200b\n❌ Unable to get currency data. Falling back to stock challenge.\n\u200b")
        return await ask_stock_challenge(winner, winner_id, num)
    
    exchange_rates = currency_data.get('exchange_rates', {})
    currency_names = currency_data.get('currency_names', {})
    valid_currencies = list(exchange_rates.keys())
    
    # Show some example currencies
    example_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD']
    available_examples = [curr for curr in example_currencies if curr in valid_currencies][:5]
    examples_text = ', '.join(available_examples)
    
    # Get base currency from user with validation (multiple attempts within 15 seconds)
    await safe_send(channel, f"\u200b\n💵🌍 **<@{winner_id}>**, give me a 3-letter currency code.\n\n💡 **Examples**: {examples_text}\n\u200b")
    
    base_currency = None
    start_time = asyncio.get_event_loop().time()
    processed_messages = set()  # Track processed messages to avoid duplicates
    
    while base_currency is None and (asyncio.get_event_loop().time() - start_time) < 15:
        try:
            remaining_time = 15 - (asyncio.get_event_loop().time() - start_time)
            if remaining_time <= 0:
                break
                
            msg = await bot.wait_for("message", 
                                   timeout=remaining_time, 
                                   check=lambda m: (m.author.id == winner_id and 
                                                  m.channel == channel and 
                                                  m.id not in processed_messages))
            
            processed_messages.add(msg.id)
            user_input = msg.content.strip()
            
            # Check if it's a 3-letter alphabetic code
            if len(user_input) == 3 and user_input.isalpha():
                candidate_currency = user_input.upper()
                
                # Validate against real currency list
                if candidate_currency in valid_currencies:
                    base_currency = candidate_currency
                    currency_display_name = get_currency_name(base_currency, currency_data)
                    await msg.add_reaction("✅")
                    await safe_send(channel, f"\u200b\n✅ **{base_currency}** ({currency_display_name}) - Valid currency!\n\u200b")
                else:
                    await msg.add_reaction("❌")
                    await safe_send(channel, f"\u200b\n❌ **{candidate_currency}** is not valid. Try again!\n\u200b")
                    
        except asyncio.TimeoutError:
            break
    
    # If no valid currency was received, use USD
    if base_currency is None:
        base_currency = "USD"
        await safe_send(channel, "\u200b\n😬⏱️ Time's up! We'll use **USD**.\n\u200b")
    
    # Get amount from user (multiple attempts within 15 seconds)
    await safe_send(channel, f"\u200b\n🔢💵 **<@{winner_id}>**, now give me an integer between 1 and 1000...\n\u200b")
    
    base_amount = None
    start_time = asyncio.get_event_loop().time()
    processed_messages = set()  # Track processed messages to avoid duplicates
    
    while base_amount is None and (asyncio.get_event_loop().time() - start_time) < 15:
        try:
            remaining_time = 15 - (asyncio.get_event_loop().time() - start_time)
            if remaining_time <= 0:
                break
                
            msg = await bot.wait_for("message", 
                                   timeout=remaining_time, 
                                   check=lambda m: (m.author.id == winner_id and 
                                                  m.channel == channel and 
                                                  m.id not in processed_messages))
            
            processed_messages.add(msg.id)
            user_input = msg.content.strip()
            
            # Check if it's a valid integer between 1 and 1000
            try:
                candidate_amount = int(user_input)
                if 1 <= candidate_amount <= 1000:
                    base_amount = candidate_amount
                    await msg.add_reaction("✅")
                else:
                    await msg.add_reaction("❌")
                    await safe_send(channel, f"\u200b\n❌ **{candidate_amount}** must be an integer between 1 and 1000. Try again!\n\u200b")
            except ValueError:
                await msg.add_reaction("❌")
        
                    
        except asyncio.TimeoutError:
            break
    
    # If no valid amount was received, use 1
    if base_amount is None:
        base_amount = 1
        await safe_send(channel, f"\u200b\n😬⏱️ Time's up! We'll use **{base_amount}**.\n\u200b")
    
    # Show final setup
    base_currency_display_name = get_currency_name(base_currency, currency_data)
    message = f"\u200b\n💥🤯 Ok...ra! We're converting **{base_amount} {base_currency}** ({base_currency_display_name})!\n"
    message += f"\n⏰ FX rates refresh hourly!\n\u200b"
    await safe_send(channel, message)
    
    
    await asyncio.sleep(2)
    
    # Calculate rates relative to base currency
    if base_currency == 'USD':
        rates = exchange_rates
    else:
        # Convert from USD rates to base currency rates
        base_rate = exchange_rates.get(base_currency, 1)
        if base_rate == 0:
            await safe_send(channel, "\u200b\n❌ Invalid base currency rate. Falling back to stock challenge.\n\u200b")
            return await ask_stock_challenge(winner, winner_id, num)
        rates = {curr: rate / base_rate for curr, rate in exchange_rates.items()}
    
    # Filter out the base currency and get available currencies
    available_currencies = [curr for curr in rates.keys() if curr != base_currency]
    if len(available_currencies) < num:
        num = len(available_currencies)
    
    user_data = {}  # Track scores: {user_id: (display_name, total_distance, participated_rounds)}
    round_actual_amounts = {}  # Track actual converted amount for each round: {round_number: actual_amount}
    
    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)
    
    currency_round = 1
    while currency_round <= num:
        # Get recent currency codes to avoid
        recent_currency_codes = await get_recent_question_ids_from_mongo("currency")
        
        # Filter out recently used currencies
        filtered_currencies = [curr for curr in available_currencies if curr not in recent_currency_codes]
        
        # If we filtered out too many, fall back to full list
        if len(filtered_currencies) < 3:
            filtered_currencies = available_currencies
            
        # Select random target currency
        target_currency = random.choice(filtered_currencies)
        conversion_rate = rates[target_currency]
        actual_converted_amount = round(base_amount * conversion_rate, 2)
        
        # Store this currency code in recent list
        await store_question_ids_in_mongo([target_currency], "currency")
        
        # Store the actual amount for this round
        round_actual_amounts[currency_round] = actual_converted_amount
        
        # Get currency names for display
        base_currency_name = get_currency_name(base_currency, currency_data)
        target_currency_name = get_currency_name(target_currency, currency_data)
        
        
        message = f"\u200b\n⚠️🚨 **Everyone's in!...One guess per player**\n"
        message += f"\n🗣💬❓ **Round {currency_round}**/{num}\n"
        message += f"\nConvert **{base_amount} {base_currency}** ({base_currency_name}) to **{target_currency}** ({target_currency_name})?\n\u200b"
        
        print(f"{base_amount} {base_currency} ({base_currency_name}) to {target_currency} ({target_currency_name})")
        print(actual_converted_amount)

        await safe_send(channel, message)
        await asyncio.sleep(2)
                
        start_time = asyncio.get_event_loop().time()
        user_guesses = {}  # {user_id: (display_name, guess)}
        processed_users = set()
        
        def check(m):
            return (m.channel == channel and 
                    m.author != bot.user and 
                    m.author.id not in processed_users)
        
        while asyncio.get_event_loop().time() - start_time < 20:
            try:
                timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                if timeout <= 0:
                    break
                msg = await bot.wait_for("message", timeout=timeout, check=check)
                try:
                    guess = float(msg.content.strip().replace(',', ''))
                    if guess < 0:
                        continue
                    user_guesses[msg.author.id] = (msg.author.display_name, guess)
                    processed_users.add(msg.author.id)
                except ValueError:
                    continue
            except asyncio.TimeoutError:
                break
        
        # Process guesses if any were received
        if user_guesses:
            # Calculate distances and find exact winner
            user_distances = {}
            exact_winner = None
            
            for user_id, (display_name, guess) in user_guesses.items():
                distance = abs(guess - actual_converted_amount)
                if distance == 0:
                    exact_winner = display_name
                user_distances[user_id] = (display_name, distance)
                
                # Get user data or create new entry
                curr_name, curr_distance, participated_rounds = user_data.get(user_id, (display_name, 0, set()))
                
                # Add penalty for previous rounds if user didn't participate
                penalty_for_previous = 0
                for round_num in range(1, currency_round):
                    if round_num not in participated_rounds:
                        if round_num in round_actual_amounts:
                            penalty_for_previous += round_actual_amounts[round_num]
                
                # Add the penalties and current round distance
                participated_rounds.add(currency_round)
                user_data[user_id] = (display_name, curr_distance + penalty_for_previous + distance, participated_rounds)
            
            # Sort by distance (closest first) for display
            sorted_results = sorted(user_distances.items(), key=lambda x: x[1][1])
            
            # Show exact winner announcement if there was one
            if exact_winner:
                exact_message = f"\u200b\n🎯💥 BULLSEYE! **{exact_winner}** got it EXACTLY right!\n\u200b"
                await safe_send(channel, exact_message)
            
            # Show results
            message = f"\u200b\n🎯 **{base_amount} {base_currency}** ({base_currency_name}) = **{actual_converted_amount} {target_currency}** ({target_currency_name})\n"
            message += f"\n🏆 **Top 3 Closest Guesses:**\n"
            
            for i, (user_id, (display_name, distance)) in enumerate(sorted_results[:3]):
                guess = user_guesses[user_id][1]
                message += f"{i+1}. **{display_name}**: {guess} (off by {distance:.2f})\n"
            message += "\u200b"
            
            await safe_send(channel, message)
        else:
            # No guesses received
            await safe_send(channel, f"\u200b\n😢 No guesses! The answer was **{actual_converted_amount} {target_currency}** ({target_currency_name})\n\u200b")
        
        # Display conversion rate for 1 unit
        await asyncio.sleep(2)
        rate_message = f"\u200b\n💱 **Exchange Rate**: 1 {base_currency} = {conversion_rate:.4f} {target_currency}\n\u200b"
        await safe_send(channel, rate_message)
        
        await asyncio.sleep(3)
        currency_round += 1
        
        # Add actual_amount penalty for users who didn't participate in this round
        current_round = currency_round - 1
        for user_id, (display_name, total_distance, participated_rounds) in list(user_data.items()):
            # If user didn't participate in the current round, add penalty
            if current_round not in participated_rounds:
                user_data[user_id] = (display_name, total_distance + actual_converted_amount, participated_rounds)
        
        # Show current standings if we have user data and this isn't the last round
        if user_data:
            sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=False)
            if num == 1:
                if sorted_users:
                    currency_winner_id, (display_name, total_distance, participated_rounds) = sorted_users[0]
                    return currency_winner_id
                else:
                    return None
            
            message = ""
            if currency_round > num:
                message += "\u200b\n🏁🏆 **Final Standings (Distance)**\n"
            else:   
                message += "\u200b\n📊🏆 **Current Standings (Distance)**\n"
            for counter, (user_id, (display_name, total_distance, participated_rounds)) in enumerate(sorted_users, start=1):
                message += f"{counter}. **{display_name}**: {total_distance:.2f}\n"
            message += "\u200b"
            
            await safe_send(channel, message)
            await asyncio.sleep(2)
    
    await asyncio.sleep(2)
    
    # Final results
    if user_data:
        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=False)
    else:
        sorted_users = []
    
    if sorted_users:
        currency_winner_id, (winner_name, total_distance, participated_rounds) = sorted_users[0]
        rounds_count = len(participated_rounds)
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}** with a total distance of **{total_distance:.2f}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No guesses made**. I'm ashamed to call you Okrans.\n\u200b"
    await safe_send(channel, message)
    
    await asyncio.sleep(3)
    
    if sorted_users:
        return currency_winner_id
    else:
        return None





async def ask_myopic_challenge(winner, winner_id, num=3):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/myopic1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/myopic2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/myopic3.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/myopic4.gif"
    ]

    gif_url = random.choice(gifs)
    embed = discord.Embed().set_image(url=gif_url)
    await safe_send(channel, content="\u200b\n👓🕵️‍♂️ **Myopic Mystery**: Identify the images\n\u200b", embed=embed)
    await asyncio.sleep(5)

    user_correct_answers = {}

    if num > 1:
        await safe_send(channel, f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b")
        await asyncio.sleep(3)

    myopic_num = 1
    while myopic_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("myopic")
            collection = db["jigsaw_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}, "question": "caltech"}},
                {"$sample": {"size": 10}},
                {"$sample": {"size": 1}}
            ]
            q_list = [doc async for doc in collection.aggregate(pipeline)]
            q = q_list[0]
            url = q["url"]
            answers = q["answers"]
            main_answer = answers[0]
            category = q["category"]
            question_text = q["question"]
            qid = q["_id"]

            print(f"Answer: {answers}")

            if qid:
                await store_question_ids_in_mongo([qid], "myopic")

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting myopic question:\n{traceback.format_exc()}")
            return

        right_answer = False
        round_num = 1

        for blur_strength in [20.0, 15.0, 10.0, 3.0]:
            if right_answer:
                break

            img_buf = await blur_image(url, blur_strength=blur_strength)
            file = discord.File(img_buf, filename="blur.png")
            embed = discord.Embed().set_image(url="attachment://blur.png")

            prompt = (
                f"\u200b\n⚠️🚨 Everyone's in!\n"
                f"\n🗣💬❓ **Image {myopic_num}** of {num}: Who or what is THIS?!?\n"
                f"\n🌀👓 **Blur Strength**: {blur_strength}\n\u200b"
            )

            await safe_send(channel, content=prompt, file=file, embed=embed)
            await asyncio.sleep(1)

            start_time = asyncio.get_event_loop().time()
            processed_users = set()

            def check(m):
                return m.channel == channel and m.author != bot.user

            while asyncio.get_event_loop().time() - start_time < 20 and not right_answer:
                try:
                    timeout = 20 - (asyncio.get_event_loop().time() - start_time)
                    msg = await bot.wait_for("message", timeout=timeout, check=check)
                    guess = normalize_text(msg.content).replace(" ", "")
                    user = msg.author.display_name
                    uid = msg.author.id
                    key = (uid, guess)

                    if key in processed_users:
                        continue
                    processed_users.add(key)

                    for ans in answers:
                        if fuzzy_match(guess, normalize_text(ans).replace(" ", ""), category, url):
                            #final_file = discord.File(final_image_buf, filename="final.png")
                            final_embed = discord.Embed().set_image(url=url)

                            await msg.add_reaction("✅")
                            message = f"\u200b\n✅🎉 Correct! **<@{uid}>** got it! {ans.upper()}\n"
                            message += f"\n📝🧠 All Answers:**\n" + "\n".join(a.upper() for a in answers) + "**\n\u200b"
                            await safe_send(channel, content=message, embed=final_embed)

                            if uid not in user_correct_answers:
                                user_correct_answers[uid] = (user, 0)
                            user_correct_answers[uid] = (user, user_correct_answers[uid][1] + 1)

                            right_answer = True
                            break
                except asyncio.TimeoutError:
                    break

            round_num += 1

        if not right_answer:
            #img_buf = download_image_from_url(url, False, "okra.png")
            #file = discord.File(img_buf, filename="final.png")
            embed = discord.Embed().set_image(url=url)
            message = f"\u200b\n❌😢 No one got it.\n\n📝🧠 Answers:**\n" + "\n".join(a.upper() for a in answers) + "**\n\u200b"
            await safe_send(channel, content=message, embed=embed)

        await asyncio.sleep(2)
        myopic_num += 1

        # standings
        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)
        message = ""

        if num == 1:
            if sorted_users:
                myopic_winner_id, (winner_name, winner_score) = sorted_users[0]
                return myopic_winner_id
            else:
                return None

        if sorted_users:
            if myopic_num > num:
                message += "\u200b\n🏁🏆 **Final Standings**\n"
            else:
                message += "\u200b\n📊🏆 **Current Standings**\n"

        for i, (_, (display_name, score)) in enumerate(sorted_users, start=1):
            message += f"{i}. {display_name}: {score}\n"

        await safe_send(channel, message)
        await asyncio.sleep(2)

    # final winner
    sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

    if sorted_users:
        myopic_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 No right answers. **I'm ashamed to call you Okrans**.\n\u200b"

    await safe_send(channel, message)
    await asyncio.sleep(3)
    
    if sorted_users:
        return myopic_winner_id
    else:
        return None



async def blur_image(image_url, blur_strength=2.0):
    """
    Downloads an image from a URL, applies Gaussian blur, and returns a Discord-ready image buffer.
    
    Args:
        image_url (str): URL of the image to process.
        blur_strength (float): Standard deviation for Gaussian blur.
    
    Returns:
        Tuple (image_buffer: BytesIO, width: int, height: int)
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to download image from {image_url}")
            data = await resp.read()

    img = Image.open(io.BytesIO(data)).convert("RGB")

    blurred_img = img.filter(ImageFilter.GaussianBlur(radius=blur_strength))

    image_buffer = io.BytesIO()
    blurred_img.save(image_buffer, format="PNG")
    image_buffer.seek(0)

    return image_buffer
        


async def ask_missing_link(winner, winner_id, num=7):
    global wf_winner

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/link1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/link2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/link3.gif"
    ]

    gif_url = random.choice(gifs)
   
    await safe_send(channel, content="\u200b\n\u200b\n 🧩🔗 **Missing Link**: Guess the Show / Movie / Person\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    user_correct_answers = {}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    link_num = 1
    while link_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("missing_link")
            collection = db["missing_link_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 100}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            question = questions[0]

            category = question["category"]
            answers = question["answers"]
            main_answer = answers[0]
            clue = question["url"]
            prompt_list = question["question"]

            if question["_id"]:
                await store_question_ids_in_mongo([question["_id"]], "missing_link")
            print(question)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting missing link question:\n{traceback.format_exc()}")
            return

        processed_users = set()

        if category == "Movie Characters":
            q_type = "MOVIE"
            header = "Characters"
        elif category == "Movie Actors":
            q_type = "MOVIE"
            header = "Actors / Actresses"
        else:
            q_type = "ACTOR or ACTRESS"
            header = "Movies"

        prompt = (
            f"\u200b\n⚠️🚨 **Everyone's in!**\n"
            f"\n\n🎬🔎 **Link {link_num}** of {num}: What **{q_type}** is the missing link?\n"
            f"\n📅💡 Clue: **{clue}**"
        )

        await safe_send(channel, prompt)

        await asyncio.sleep(2)
        list_msg = f"\u200b\n**{header}**\n"
        for i, item in enumerate(prompt_list.split(","), 1):
            list_msg += f"{i}. {item.strip()}\n"
        await safe_send(channel, list_msg)

        start_time = asyncio.get_event_loop().time()
        right_answer = False

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 15 and not right_answer:
            try:
                remaining = 15 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=remaining, check=check)
                user = message.author.display_name
                user_id = message.author.id
                content = message.content.strip()
                key = (message.author.id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                for answer in answers:
                    if fuzzy_match(content, answer, category, clue):
                        await message.add_reaction("✅")
                        await safe_send(channel, f"\u200b\n✅🎉 Correct! **<@{user_id}>** got it! **{answer.upper()}**")
                        if user_id not in user_correct_answers:
                            user_correct_answers[user_id] = (user, 0)
                        user_correct_answers[user_id] = (user, user_correct_answers[user_id][1] + 1)
                        right_answer = True
                        break
            except asyncio.TimeoutError:
                break

        if not right_answer:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{main_answer.upper()}**\n")
        
        await asyncio.sleep(1)
                            
        link_num = link_num + 1
        
        message = ""

        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                link_winner_id, (winner_name, winner_score) = sorted_users[0]
                return link_winner_id if winner_name is not None else None
            else:
                return None
            
        if sorted_users:
            if link_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (uid, (name, score)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{name}**: {score}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        link_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)

    if sorted_users:
        return link_winner_id
    else:
        return None


async def ask_movie_scenes_challenge(winner, winner_id, num=7):
    global wf_winner

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/movie1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/movie2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/movie3.gif"
    ]

    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n\u200b\n 🎬💥 **Movie Mayhem**: Guess the Flick\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    user_correct_answers = {}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    movie_num = 1
    while movie_num <= num:
        try:
            recent_ids = await get_recent_question_ids_from_mongo("movie_scenes")
            collection = db["movie_scenes_questions"]
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_ids)}}},
                {"$sample": {"size": 100}},
                {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
                {"$replaceRoot": {"newRoot": "$question_doc"}},
                {"$sample": {"size": 1}}
            ]
            questions = [doc async for doc in collection.aggregate(pipeline)]
            question = questions[0]

            category = question["category"]
            answers = question["answers"]
            main_answer = answers[0]
            year = question["question"]
            image_url = question["url"]

            if question["_id"]:
                await store_question_ids_in_mongo([question["_id"]], "movie_scenes")
            print(question)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error selecting movie scenes question:\n{traceback.format_exc()}")
            return

        processed_users = set()

        prompt = (
            f"\u200b\n⚠️🚨 **Everyone's in!**\n\u200b"
            f"\u200b\n🎬🌟 **Movie {movie_num}** of {num}: What **{category.upper()}** is depicted in the scene above?\n"
            f"\n📅💡 Year: **{year}**\n\u200b"
        )

        await safe_send(channel, embed=discord.Embed(description=f"**{category.upper()} ({year})**").set_image(url=image_url))
        await safe_send(channel, prompt)

        start_time = asyncio.get_event_loop().time()
        right_answer = False

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 15 and not right_answer:
            try:
                remaining = 15 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=remaining, check=check)
                user = message.author.display_name
                user_id = message.author.id
                content = message.content.strip()
                key = (message.author.id, content.lower())

                if key in processed_users:
                    continue
                processed_users.add(key)

                for answer in answers:
                    if fuzzy_match(content, answer, category, image_url):
                        await message.add_reaction("✅")
                        await safe_send(channel, f"\u200b\n✅🎉 Correct! **<@{user_id}>** got it! **{answer.upper()}**")
                        if user_id not in user_correct_answers:
                            user_correct_answers[user_id] = (user, 0)
                        user_correct_answers[user_id] = (user, user_correct_answers[user_id][1] + 1)
                        right_answer = True
                        break
            except asyncio.TimeoutError:
                break

        if not right_answer:
            await safe_send(channel, f"\u200b\n❌😢 No one got it.\n\nAnswer: **{main_answer.upper()}**\n\u200b")
        
        await asyncio.sleep(1)
                            
        movie_num = movie_num + 1
        
        message = ""

        sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                movie_winner_id, (winner_name, winner_score) = sorted_users[0]
                return movie_winner_id if winner_name is not None else None
            else:
                return None
            
        if sorted_users:
            if movie_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (uid, (name, score)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{name}**: {score}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)

        await asyncio.sleep(3)

    await asyncio.sleep(2)
    if sorted_users:
        movie_winner_id, (winner_name, winner_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{winner_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)

    if sorted_users:
        return movie_winner_id
    else:
        return None




async def ask_feud_question(winner, mode, winner_id):

    feud_gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/feud1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/feud2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/feud3.gif"
    ]

    feud_gif_url = random.choice(feud_gifs)
    
    if mode == "solo":
        message = f"\u200b\n\u200b\n ⚔️🧍 **FeUd (Single Player)**\n\u200b"
    elif mode == "cooperative":
        message = f"\u200b\n\u200b\n ⚔️⚡ **FeUd Blitz**\n\u200b"

    await safe_send(channel, content=message, embed=discord.Embed().set_image(url=feud_gif_url))
    await asyncio.sleep(3)
    await safe_send(channel, f"\u200b\n3️⃣🥇 Let's do a round of 3...\n\u200b")
    await asyncio.sleep(3)

    try:
        recent_feud_ids = await get_recent_question_ids_from_mongo("feud")
        feud_collection = db["feud_questions"]
        pipeline_feud = [
            {"$match": {"_id": {"$nin": list(recent_feud_ids)}}},
            {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$question_doc"}},
            {"$sample": {"size": 1}}
        ]
        feud_questions = await feud_collection.aggregate(pipeline_feud).to_list(length=1)
        if not feud_questions:
            await safe_send(channel, "❌ Could not find a new feud question.")
            return

    except Exception as e:
        sentry_sdk.capture_exception(e)
        error_details = traceback.format_exc()
        print(f"Error selecting feud questions: {e}\nDetailed traceback:\n{error_details}")
        return None  # Return an empty list in case of failure

    feud_question = feud_questions[0]
    feud_prompt = feud_question["question"]
    feud_answers = feud_question["answers"]
    feud_question_id = feud_question["_id"]
    await store_question_ids_in_mongo([feud_question_id], "feud")

    win_image_url = "https://triviabotwebsite.s3.us-east-2.amazonaws.com/harvey/harvey+win.gif"
    loss_image_url = "https://triviabotwebsite.s3.us-east-2.amazonaws.com/harvey/harvey+loss.gif"

    
    print(feud_question)

    user_progress = []
    user_correct_answers = {}
    correct_guesses = 0
    max_xs = 3
    xs = 0
    guess_time = 20
    numbered_blocks = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    num_answers = len(feud_answers)
    answered_correctly = False

    while xs < max_xs and not answered_correctly:
        feud_image_buffer = create_family_feud_board_image(feud_answers, user_progress, 0)
        image_file = discord.File(fp=feud_image_buffer, filename="image.png")
        board_embed = discord.Embed(title=f"🟦 **Okra Says!** Top {num_answers} answers on the board\n\u200b")
        board_embed.description = f"We asked 100 Okrans..."
        board_embed.set_image(url="attachment://image.png")

        await asyncio.sleep(1)

        start_message = ""

        if mode == "cooperative":
            if xs == 0:
                start_message += f"\u200b\n⚠️🚨 **Everyone's in!** Round 1/3! 🟩\n\u200b"
            elif xs == 1:
                start_message += f"\u200b\n⚠️🚨 **Everyone's in!** Round 2/3! 🟨\n\u200b"
            elif xs == 2:
                start_message += f"\u200b\n⚠️🚨 **Everyone's in!** Last round! 🟥\n\u200b"

        elif mode == "solo":
            if xs == 0:
                start_message += f"\u200b\n⚠️🚨 **<@{winner_id}> ONLY!** Round 1/3! 🟩\n\u200b"
            elif xs == 1:
                start_message += f"\u200b\n⚠️🚨 **<@{winner_id}> ONLY!** Round 2/3! 🟨\n\u200b"
            elif xs == 2:
                start_message += f"\u200b\n⚠️🚨 **<@{winner_id}> ONLY!** Last round! 🟥\n\u200b"

        
        await safe_send(channel, embed=board_embed, file=image_file)
        await asyncio.sleep(3)
        await safe_send(channel, start_message)
        await asyncio.sleep(1)

        prompt_message = f"\u200b\n\u200b\n👉👉 **{feud_prompt.upper()}**\n"
        prompt_message += f"\n📜🔢 List as many as you can. **GO!** 🏁🚀\n\u200b"

        await safe_send(channel, prompt_message)

        def check(m):
            if mode == "solo":
                return m.author.id == winner_id and m.channel == channel
            return m.channel == channel and m.author != bot.user

        try:
            end_time = asyncio.get_event_loop().time() + guess_time

            while asyncio.get_event_loop().time() < end_time and not answered_correctly:
                timeout = end_time - asyncio.get_event_loop().time()

                response = await bot.wait_for("message", timeout=timeout, check=check)

                if response.author.id in user_correct_answers:
                    continue

                for answer in feud_answers:
                    if answer in user_progress:
                        continue

                    if fuzzy_match(response.content, answer, "", ""):
                        user_progress.append(answer)
                        correct_guesses += 1
                        await response.add_reaction("✅")

                        user_correct_answers.setdefault(response.author.display_name, 0)
                        user_correct_answers[response.author.display_name] += 1

                        if len(user_progress) == num_answers:
                            answered_correctly = True
                            break

        except asyncio.TimeoutError:
            pass

        xs += 1
        
        await safe_send(channel, content="\u200b\n🎤📊 **Survey says...**\n\u200b")
        if answered_correctly == False and xs < 3:    
            feud_image_buffer = create_family_feud_board_image(feud_answers, user_progress, xs)
            image_file = discord.File(fp=feud_image_buffer, filename="image.png")
            embed = discord.Embed(title=f"🟦 **OKRA SAYS** Top {num_answers} answers on the board\n\u200b")
            embed.set_image(url="attachment://image.png")
            
            await safe_send(channel, embed=embed, files=[image_file])
            await asyncio.sleep(2)
            
            message = f"{correct_guesses} out of {num_answers}\n"
            if user_correct_answers and mode == "cooperative":
                message += "\n**🏆 Commendable Okrans**\n"
                sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1], reverse=True)
                for i, (user, count) in enumerate(sorted_users, 1):
                    message += f"{i}. **{user}**: {count}\n"
            message += "\u200b"
            await safe_send(channel, message)
            await asyncio.sleep(2)

    result_message = ""
    if mode == "cooperative":
        if not user_progress:
            result_message = f"\n👎😢 No right answers out of {num_answers}. **I'm ashamed to call you Okrans**.\n"
        elif len(user_progress) < num_answers:
            result_message = f"\n🙄😒 Wow...you got **{len(user_progress)}/{num_answers}**.\n"
        else:
            result_message = f"\n🎉✅ Congrats Okrans! You got all **{num_answers}** right!\n"

        if user_correct_answers and mode == "cooperative":
            result_message += "\n**🏆 Commendable Okrans**\n"
            sorted_users = sorted(user_correct_answers.items(), key=lambda x: x[1], reverse=True)
            for i, (user, count) in enumerate(sorted_users, 1):
                result_message += f"{i}. **{user}**: {count}\n"
    elif mode == "solo":
        if not user_progress:
            result_message = f"\n👎😢 **No right answers** out of {num_answers}. **<@{winner_id}>, you're no Okran**.\n"
        elif len(user_progress) < num_answers:
            result_message = f"\n🙄😒 Wow <@{winner_id}>...you got **{len(user_progress)}/{num_answers}**.\n"
        else:
            result_message = f"\n🎉✅ Congrats <@{winner_id}>! You got all **{num_answers}** right!\n"

    await asyncio.sleep(2)
    
    # Show final X image if they failed after 3 strikes
    if answered_correctly == False:
        feud_image_buffer = create_family_feud_board_image(feud_answers, user_progress, xs)
        image_file = discord.File(fp=feud_image_buffer, filename="image.png")
        embed = discord.Embed(title=f"🟦 **OKRA SAYS FINAL** Top {num_answers} answers on the board\n\u200b")
        embed.set_image(url="attachment://image.png")
        await safe_send(channel, embed=embed, files=[image_file])
        await asyncio.sleep(2)

    if len(user_progress) < num_answers:
        await safe_send(channel, embed=discord.Embed().set_image(url=loss_image_url))
    else:
        await safe_send(channel, embed=discord.Embed().set_image(url=win_image_url))

    await safe_send(channel, result_message)

    await asyncio.sleep(3)


    answer_feud_image_buffer = create_family_feud_board_image(feud_answers, feud_answers, 0)
    image_file = discord.File(fp=answer_feud_image_buffer, filename="image.png")
    board_embed = discord.Embed(title=f"🔑❓ **OKRA SAYS ANSWERS**\n\u200b")
    board_embed.description = f"We asked 100 Okrans..."
    board_embed.set_image(url="attachment://image.png")
    await safe_send(channel, embed=board_embed, file=image_file)
    await asyncio.sleep(5)
    return


async def fetch_random_word_thes(min_length=5, max_length=12, max_retries=20, max_related=5):
    for attempt in range(1, max_retries + 1):
        print(f"[Attempt {attempt}/{max_retries}] Fetching a random word...")

        try:
            # Fetch a random word (you must make this async if it isn't already)
            word = await get_random_word()  # Replace with await get_random_word() if it's async

            if not word:
                print("No word returned from local list.")
                continue

            url = f"https://www.dictionaryapi.com/api/v3/references/thesaurus/json/{word}?key={webster_thes_api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status != 200:
                        print(f"Failed to fetch word: HTTP {response.status}")
                        continue

                    data = await response.json()

            if not data or isinstance(data[0], str):
                print(f"Merriam-Webster Thesaurus did not recognize the word '{word}'. Suggestions: {data}")
                continue

            for sense in data:
                if isinstance(sense, dict):
                    pos = sense.get("fl", "").lower()
                    synonyms = sense.get("meta", {}).get("syns", [])
                    antonyms = sense.get("meta", {}).get("ants", [])

                    synonyms = [syn for group in synonyms for syn in group][:max_related]
                    antonyms = [ant for group in antonyms for ant in group][:max_related]

                    if pos and synonyms:
                        mw_url = f"https://www.merriam-webster.com/thesaurus/{word}"
                        return word, pos, synonyms, antonyms, mw_url

            print(f"No valid synonyms found for '{word}'.")
            continue

        except Exception as e:
            print(f"Error processing word details: {e}")
            continue

    print("Exceeded maximum retries. No valid word found.")
    return None, None, None, None, None


async def load_words_from_file(filepath):
    words = []
    async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
        async for line in f:
            word = line.strip()
            if word:
                words.append(word)
    return words


async def get_random_word(min_length=5, max_length=12):
    words = await load_words_from_file("wordlist.txt")
    valid_words = [w for w in words if min_length <= len(w) <= max_length]
    if not valid_words:
        return None
    return random.choice(valid_words)


async def fetch_random_word(min_length=5, max_length=12, max_retries=5):
    for attempt in range(1, max_retries + 1):
        print(f"[Attempt {attempt}/{max_retries}] Fetching a random word...")
        try:
            # Fetch a random word
            word = await get_random_word()

            if not word:
                print("No word returned from local list.")
                continue

            # Look up the word in Merriam-Webster
            url = f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={webster_api_key}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if not data or isinstance(data[0], str):
                # Nothing returned or suggestions instead of definitions
                print(f"Merriam-Webster did not recognize the word '{word}'. Suggestions: {data}")
                continue

            # Extract part of speech and definitions
            for sense in data:
                if isinstance(sense, dict):
                    pos = sense.get("fl", "").lower()  # Functional label (part of speech)
                    definitions = sense.get("shortdef", [])
                    if pos and definitions:
                        mw_url = f"https://www.merriam-webster.com/dictionary/{word}"
                        return word, pos, definitions, mw_url

            # If no valid definitions are found
            print(f"No valid definitions found for '{word}'.")
            continue

        except Exception as e:
            print(f"Error processing word details: {e}")
            continue

    # Return None after exhausting retries
    print("Exceeded maximum retries. No valid word found.")
    return None, None, None, None


def update_audit_question(question, message_content, display_name):
    if question["trivia_db"] == "math" or question["trivia_db"] == "stats":
        return

    collection = db[question["trivia_db"]]
    document_id = question["trivia_id"]

    audit_entry = {
        "display_name": f"{display_name} (Discord)",
        "message_content": message_content
    }

    for attempt in range(max_retries):
        try:
            update = {
                "$push": {"audit": audit_entry},
                "$setOnInsert": {"timestamp": time.time()}
            }

            # Ensure 'audit' exists and append the new entry
            collection.update_one({"_id": document_id}, update, upsert=False)
            break  # Success, exit loop

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Attempt {attempt + 1} failed: {e}")

            if attempt < max_retries - 1:
                print(f"Retrying in {delay_between_retries} seconds...")
                time.sleep(delay_between_retries)
            else:
                print(f"Failed to update audit for document '{document_id}' in {question['db']}.")


async def update_audit_question(question, message_content, display_name):
    if question:
        if question["trivia_db"] in {"math", "stats"}:
            return

        collection = db[question["trivia_db"]]  # Assumes db is an instance of AsyncIOMotorDatabase
        document_id = question["trivia_id"]

        audit_entry = {
            "display_name": f"{display_name} (Discord)",
            "message_content": message_content
        }

        for attempt in range(max_retries):
            try:
                update = {
                    "$push": {"audit": audit_entry},
                    "$setOnInsert": {"timestamp": time.time()}
                }

                await collection.update_one({"_id": document_id}, update, upsert=False)
                break  # Success

            except Exception as e:
                sentry_sdk.capture_exception(e)
                print(f"Attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    print(f"Retrying in {delay_between_retries} seconds...")
                    await asyncio.sleep(delay_between_retries)
                else:
                    print(f"Failed to update audit for document '{document_id}' in {question['trivia_db']}'.")


async def load_previous_question():
    global previous_question
    
    for attempt in range(max_retries):
        try:
            
            # Retrieve the current longest answer streak from MongoDB
            previous_question_retrieved = await db.previous_question_discord.find_one({"_id": "previous_question"})

            if previous_question_retrieved is not None:
                previous_question = {
                    "trivia_category": previous_question_retrieved.get("trivia_category"),
                    "trivia_question": previous_question_retrieved.get("trivia_question"),
                    "trivia_url": previous_question_retrieved.get("trivia_url"),
                    "trivia_answer_list": previous_question_retrieved.get("trivia_answer_list"),
                    "trivia_db": previous_question_retrieved.get("trivia_db"),
                    "trivia_id": previous_question_retrieved.get("trivia_id"),
                }
            else:
                # If the document is not found, set default values
                previous_question = {
                    "trivia_category": None,
                    "trivia_question": None,
                    "trivia_url": None,
                    "trivia_answer_list": None,
                    "trivia_db": None,
                    "trivia_id": None
                }
            break
                
        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {delay_between_retries} seconds...")
                await asyncio.sleep(delay_between_retries)
            else:
                print("Max retries reached. Data loading failed.")
                # Set to default values if loading fails
                previous_question = {
                    "trivia_category": None,
                    "trivia_question": None,
                    "trivia_url": None,
                    "trivia_answer_list": None,
                    "trivia_db": None,
                    "trivia_id": None
                }


async def ask_ranker_list_number(winner, winner_id, num=7):
    def check(m):
        return m.channel == channel and m.author != bot.user and m.author.id == winner_id and m.content.strip() in {"1", "2", "3", "4", "5"}

    try:
        message = await bot.wait_for("message", timeout=20, check=check)
        await message.add_reaction("💪")  # Acknowledge with a muscle emoji
        await safe_send(channel, f"\u200b\n💪🛡️ I got you **<@{winner_id}>**. **{message.content}** it is.\n\u200b")
        return int(message.content)
    except asyncio.TimeoutError:
        selected_question = random.choice(["1", "2", "3", "4", "5"])
        await safe_send(channel, f"\u200b\n🐢⏳ Too slow. I choose **{selected_question}**.\n\u200b")
        return int(selected_question)


async def ask_ranker_list_question(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True
    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/ranker-list1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/ranker-list2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/ranker-list3.gif"
    ]

    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n\u200b\n**🔢📜 Ranker Lists**: Guess the Items\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    try:
        await asyncio.sleep(2)
        recent_ids = await get_recent_question_ids_from_mongo("ranker_list")
        collection = db["ranker_list_questions"]
        pipeline = [
            {"$match": {"_id": {"$nin": list(recent_ids)}}},
            {"$sample": {"size": 10}},
            {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$question_doc"}},
            {"$sample": {"size": 5}}
        ]
        questions = [doc async for doc in collection.aggregate(pipeline)]
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Error selecting Ranker list questions:\n{traceback.format_exc()}")
        return

    # Present list options to the user
    options = "\n".join([f"{i+1}️⃣. {q['question']}" for i, q in enumerate(questions)])
    await safe_send(channel, f"\u200b\n📝🔢 **<@{winner_id}>**, choose the list:\n\n{options}")
    
    selected = int(await ask_ranker_list_number(winner, winner_id)) - 1
    list_q = questions[selected]

    clue = list_q["question"]
    answers = list_q["answers"]
    category = list_q["category"]
    url = list_q["url"]
    qid = list_q["_id"]
    if qid:
        await store_question_ids_in_mongo([qid], "ranker_list")
    print(list_q)

    emojis = get_category_title(category, "")
    num_answers = len(answers)

    user_progress = {}
    total_progress = set()

    await safe_send(channel, f"\u200b\n\u200b\n⚠️🚨 **Everyone's in...{emojis}**\n\u200b")
    await asyncio.sleep(3)
    await safe_send(channel, f"\u200b\n📝1️⃣ List **ONE per message** of...")
    await asyncio.sleep(3)
    await safe_send(channel, f"\u200b\n👉👉 **{clue}**\n\n🟢🚀 **GO!**\n\u200b")

    def check(m):
        return m.channel == channel and m.author != bot.user

    start_time = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start_time < 30:
        try:
            message = await bot.wait_for("message", timeout=30, check=check)
            content = message.content.strip()
            user = message.author.display_name
            user_id = message.author.id

            if user_id not in user_progress:
                user_progress[user_id] = (user, set())
            display_name, answer_set = user_progress[user_id]

            for answer in answers:
                if answer in total_progress or answer in answer_set:
                    continue
                if fuzzy_match(content, answer, category, url):
                    answer_set.add(answer)
                    total_progress.add(answer)
                    await message.add_reaction("✅")

            if len(total_progress) >= num_answers:
                break

        except asyncio.TimeoutError:
            break

    # Final scoring
    scores = sorted(user_progress.items(), key=lambda x: len(x[1][1]), reverse=True)

    if not scores:
        await safe_send(channel, "\u200b\n😬🤦 Wow. No one got a single one right. **Embarassing.**\n\u200b")
    else:
        msg = f"\u200b\n🏅💪 Okrans got **{len(total_progress)}/{num_answers}** right!\n"
        msg += "\n**🏆 Commendable Okrans**\n"
        for i, (uid, (user, s)) in enumerate(scores, start=1):
            msg += f"{i}. **{user}**: {len(s)}\n"
        await safe_send(channel, msg)

    if total_progress:
        await asyncio.sleep(2)
        result_lines = []
        for ans in answers:
            if ans in total_progress:
                guesser = next((name for uid, (name, s) in user_progress.items() if ans in s), "❓")
                result_lines.append(f"✅ {ans} — **{guesser}**")
            else:
                result_lines.append(f"❌ {ans}")
        result_text = "\n".join(result_lines)
        await safe_send(channel, f"\u200b\n📋 **Answer Summary:**\n\n{result_text}\n\u200b")
    
    await asyncio.sleep(3)
    
    msg = f"\n🔗 [See the full list]({url})\n\u200b"
    await safe_send(channel, msg)
    await asyncio.sleep(5)

    if scores:
        top_user_id, _ = scores[0]
        return top_user_id
    else:
        return None


async def ask_list_question(winner, winner_id, num=7):
    global wf_winner
    wf_winner = True
    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/list1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/list2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/list3.gif"
    ]

    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n\u200b\n**📝🥊 List Battle **\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(3)

    try:
        await asyncio.sleep(2)
        recent_list_ids = await get_recent_question_ids_from_mongo("list")

        list_collection = db["list_questions"]
        pipeline_list = [
            {"$match": {"_id": {"$nin": list(recent_list_ids)}}},
            {"$group": {"_id": "$question", "question_doc": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$question_doc"}},
            {"$sample": {"size": 1}}
        ]

        list_questions = [doc async for doc in list_collection.aggregate(pipeline_list)]
        list_question = list_questions[0]
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Error selecting list questions:\n{traceback.format_exc()}")
        return

    print(list_question)

    # Extract question details
    clue = list_question["question"]
    answers = list_question["answers"]
    category = list_question["category"]
    url = list_question.get("url", "")
    qid = list_question["_id"]
    if qid:
        await store_question_ids_in_mongo([qid], "list")

    emojis = get_category_title(category, "")
    num_answers = len(answers)
    user_progress = {}
    total_progress = set()

    await safe_send(channel, f"\u200b\n\u200b\n⚠️🚨 **Everyone's in...{emojis}**\n\u200b")
    await asyncio.sleep(3)
    await safe_send(channel, f"\u200b\n📝1️⃣ List ONE per message of...")
    await asyncio.sleep(3)
    await safe_send(channel, f"\u200b\n\u200b\n👉👉 **{clue}**\n\n🟢🚀 **GO!**\n\u200b")

    def check(m):
        return m.channel == channel and m.author != bot.user

    start_time = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start_time < 30:
        remaining = 30 - (asyncio.get_event_loop().time() - start_time)
        try:
            message = await bot.wait_for("message", timeout=remaining, check=check)
            content = message.content.strip()
            user = message.author.display_name
            user_id = message.author.id
            
            if user_id not in user_progress:
                user_progress[user_id] = (user, set())
            display_name, answer_set = user_progress[user_id]

            for answer in answers:
                if answer in answer_set:
                    continue
                if fuzzy_match(content, answer, category, url):
                    answer_set.add(answer)
                    total_progress.add(answer)

                    #await message.add_reaction("✅")

                    # Win conditions
                    if len(answer_set) >= num_answers:
                        scores = sorted(user_progress.items(), key=lambda x: len(x[1][1]), reverse=True)

                        if len(scores) > 0:
                            msg = f"\u200b\n🏆🎉 **{scores[0][1][0]}** got all {num_answers}!"

                        if len(scores) > 1:
                            msg += f"\n2nd place: **{scores[1][1][0]}** with {len(scores[1][1][1])}/{num_answers}"

                        if len(scores) > 2:
                            msg += f"\n3rd place: **{scores[2][1][0]}** with {len(scores[2][1][1])}/{num_answers}\n\u200b\n\u200b"

                        await safe_send(channel, msg)

        except asyncio.TimeoutError:
            break

    # Timeout fallback
    scores = sorted(user_progress.items(), key=lambda x: len(x[1][1]), reverse=True)

    if not scores:
        await safe_send(channel, "\u200b\n\u200b\n😬🤦 Wow. No one got a single one right. **Embarassing**.\n\u200b")
        return

    msg = f"\u200b\n\u200b\n🥇🏆 1st place: **{scores[0][1][0]}** with {len(scores[0][1][1])}/{num_answers}!"
    if len(scores) > 1:
        msg += f"\n🥈🎊 2nd: **{scores[1][1][0]}** with {len(scores[1][1][1])}/{num_answers}"
    if len(scores) > 2:
        msg += f"\n🥉🎉 3rd: **{scores[2][1][0]}** with {len(scores[2][1][1])}/{num_answers}\n\u200b"
    await safe_send(channel, msg)

    
    # Show winner's results with ✅ or ❌
    if scores:
        await asyncio.sleep(2)
        # Find the winner's answer set
        list_winner_id = next((uid for uid, (name, _) in user_progress.items() if name == winner), None)
        if list_winner_id is not None:
            winner_answers = user_progress[list_winner_id][1]
            result_lines = []
            for ans in answers:
                mark = "✅" if ans in winner_answers else "❌"
                result_lines.append(f"{mark} {ans}")
            result_text = "\n".join(result_lines)
            await safe_send(channel, f"\u200b\n📋 **<@{winner_id}>'s Answers:**\n\n{result_text}\n\u200b")
            

    await asyncio.sleep(5)

    if scores:
        return list_winner_id


async def ask_survey_question():
    collection = db["survey_questions_discord"]

    # Fetch a random question
    question_list = await collection.aggregate([
        {"$match": {"enabled": True}},
        {"$sample": {"size": 1}}
    ]).to_list(length=1)

    if not question_list:
        await safe_send(channel, "📭 No survey questions available.")
        return

    survey_question = question_list[0]
    question_text = survey_question.get("question", "No question.")
    question_type = survey_question.get("question_type", "yes-no")
    valid_answers = survey_question.get("valid_answers", [])
    responses = survey_question.get("responses", {})
    collected = {}
    current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    type_info = {
        "yes-no": {"emojis": "👍👎", "prompt": "Answer YES or NO"},
        "multiple-choice": {"emojis": "🄠📝", "prompt": "Choose a letter"},
        "rating-10": {"emojis": "⭐️🔟", "prompt": "Rate 1 👎 to 10 👍"},
        "word-3": {"emojis": "3️⃣🔤", "prompt": "3 word limit"}
    }

    emojis = type_info.get(question_type, {}).get("emojis", "🤔")
    prompt_text = type_info.get(question_type, {}).get("prompt", "What do you think?")

    await safe_send(channel, "\u200b\n\u200b\n📋✅ Survey Time!\n\n1️⃣☝️ Only 1 answer stored per user.\n\u200b\n\u200b")
    await asyncio.sleep(2)
    await safe_send(channel, f"\n{emojis} {prompt_text}\n\n❓ {question_text}\n\u200b\n\u200b")

    def check(m):
        return m.channel == channel and m.author != bot.user

    end_time = asyncio.get_event_loop().time() + 15
    while True:
        timeout = end_time - asyncio.get_event_loop().time()
        if timeout <= 0:
            break

        try:
            msg = await asyncio.wait_for(bot.wait_for('message', check=check), timeout=timeout)
            username = msg.author.display_name
            content = msg.content.strip()

            if question_type == "yes-no":
                if content.lower().startswith("y") or content == "👍":
                    collected[username] = {"answer": "Yes", "timestamp": current_time}
                elif content.lower().startswith("n") or content == "👎":
                    collected[username] = {"answer": "No", "timestamp": current_time}

            elif question_type == "multiple-choice":
                match = next((a for a in valid_answers if a.lower() in content.lower()), None)
                if match:
                    collected[username] = {"answer": match, "timestamp": current_time}

            elif question_type == "rating-10":
                match = re.search(r'\b\d+(\.\d+)?\b', content)
                if match:
                    val = float(match.group())
                    if 1 <= val <= 10:
                        collected[username] = {"answer": round(val, 1), "timestamp": current_time}

            elif question_type == "word-3":
                words = content.split()
                if words:
                    collected.setdefault(username, {"answer": [], "timestamp": current_time})
                    collected[username]["answer"].extend(words)
                    collected[username]["answer"] = collected[username]["answer"][-3:]
                    collected[username]["timestamp"] = current_time

        except asyncio.TimeoutError:
            break

    # Save results to MongoDB
    responses.update(collected)
    await collection.update_one(
        {"_id": survey_question["_id"]},
        {"$set": {"responses": responses}}
    )

    total = len(responses)
    if total == 0:
        return

    # Summary
    if question_type == "yes-no":
        yes = sum(1 for r in responses.values() if r["answer"].lower() == "yes")
        pct = (yes / total) * 100
        msg = f"\u200b\n🏄‍♂️🌟 {int(pct)}% said OkraYeah!" if pct >= 50 else f"🥀👧 {100 - int(pct)}% said NOkra."
        await safe_send(channel, msg)

    elif question_type == "rating-10":
        avg = sum(r["answer"] for r in responses.values()) / total
        await safe_send(channel, f"\u200b\n⭐️🔟 Average rating is {avg:.1f}/10.")

    elif question_type == "word-3":
        all_words = []
        for r in responses.values():
            if isinstance(r["answer"], list):
                all_words.extend(r["answer"])

        norm = [w.strip(string.punctuation).lower() for w in all_words]
        common = Counter(norm).most_common(3)
        if common:
            words = ', '.join(f'"{w.capitalize()}"' for w, _ in common)
            await safe_send(channel, f"\u200b\n📚🔤 Okrans say Live Trivia is: {words}.")

        # Optional: generate image
        try:
            content = " ".join(norm)
            gpt_response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Remove unsafe or inappropriate words for DALL·E input."},
                    {"role": "user", "content": f"Clean this for DALL·E: {content}"}
                ],
                max_tokens=100
            )
            safe_words = gpt_response.choices[0].message.content.strip()
            img_prompt = f"Create a hyperrealistic futuristic okra themed environment described as: {safe_words}."

            image = await client.images.generate(
                model="dall-e-3",
                prompt=img_prompt,
                size="1024x1024",
                n=1
            )
            image_url = image.data[0].url
            await safe_send(channel, "🥒🌀 Behold, your Okraverse:")
            await safe_send(channel, image_url)

        except Exception as e:
            print("Error generating image:", e)

    
async def generate_themed_country_image(country, city):
    prompt = (
        f"Show a stereotypical person with a face from {country} holding an okra in a stereotypical setting in {country}."
    )

    try:
        response = await openai_client.images.generate(
            model="dall-e-2",
            prompt=prompt,
            n=1,
            size="512x512"
        )
        image_url = response.data[0].url
        return image_url

    except openai.OpenAIError as e:
        print(f"Error generating image: {e}")
        
        if "Your request was rejected as a result of our safety system" in str(e):
            default_prompt = f"Generate an image of an okra in {country}."
            try:
                response = await openai_client.images.generate(
                    model="dall-e-2",
                    prompt=default_prompt,
                    n=1,
                    size="512x512"
                )
                image_url = response.data[0].url
                return image_url
            except openai.OpenAIError as e2:
                print(f"Error generating default image: {e2}")
                return "Image generation failed!"

        return "Image generation failed!"


async def get_google_maps(lat, lon):
    base_street_view_url = "https://maps.googleapis.com/maps/api/streetview"
    base_static_map_url = "https://maps.googleapis.com/maps/api/staticmap"
    base_metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    base_maps_url = "https://www.google.com/maps"

    metadata_params = {
        "location": f"{lat},{lon}",
        "key": googlemaps_api_key
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(base_metadata_url, params=metadata_params) as resp:
            if resp.status != 200:
                street_view_url = None
            else:
                metadata = await resp.json()
                if metadata.get("status") == "OK":
                    street_view_params = {
                        "size": "600x400",
                        "location": f"{lat},{lon}",
                        "fov": 90,
                        "heading": 0,
                        "pitch": 0,
                        "key": googlemaps_api_key
                    }
                    street_view_url = f"{base_street_view_url}?{urlencode(street_view_params)}"
                else:
                    street_view_url = None

    static_map_params = {
        "center": f"{lat},{lon}",
        "zoom": 7,
        "size": "600x400",
        "maptype": "satellite",
        "key": googlemaps_api_key
    }
    satellite_view_url = f"{base_static_map_url}?{urlencode(static_map_params)}"
    satellite_live_url = f"{base_maps_url}/?q={lat},{lon}&t=k"

    return street_view_url, satellite_view_url, satellite_live_url


async def get_random_city(winner):
    collection = db["where_is_okra"]
    total = await collection.count_documents({})
    if total == 0:
        print("No cities found in 'where_is_okra' collection.")
        return None

    skip = random.randint(0, total - 1)
    result = await collection.find().skip(skip).to_list(length=1)
    if not result:
        print("Failed to fetch a random city.")
        return None

    city = result[0]
    city_name = city.get("city")
    country_name = city.get("country")
    lat = city.get("lat")
    lon = city.get("lon")

    miles_per_lat = 1 / 69
    miles_per_lon = 1 / (69 * math.cos(math.radians(lat)))
    lat += random.uniform(-0.5, 0.5) * miles_per_lat
    lon += random.uniform(-0.5, 0.5) * miles_per_lon

    street_url, sat_url, live_url = await get_google_maps(lat, lon)

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.openweathermap.org/data/2.5/weather", params={
            "lat": lat, "lon": lon,
            "appid": openweather_api_key,
            "units": "metric"
        }) as resp:
            if resp.status != 200:
                return {"error": f"Failed weather API: {resp.status}"}
            weather_data = await resp.json()

    temp_c = round(weather_data["main"]["temp"])
    temp_f = round(temp_c * 9 / 5 + 32)
    conditions = ". ".join([w["description"].capitalize() for w in weather_data["weather"]]) + "."
    offset = weather_data["timezone"]
    local_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=offset)
    time_str = local_time.strftime("%B %-d, %Y %-I:%M%p").lower()

    summary = (
        f"Fahrenheit Temperature: {temp_f}°F\n"
        f"Celsius Temperature: {temp_c}°C\n"
        f"Weather Conditions: {conditions}\n"
        f"Local Date and Time: {time_str}\n"
    )
    
    if ai_on:
        try:
            result = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are OkraStrut fleeing from <@{winner_id}> like Carmen Sandiego. Use these facts:"
                    },
                    {"role": "user", "content": summary}
                ],
                max_tokens=500,
                temperature=0.3
            )
            clue = result.choices[0].message.content.strip()
        except Exception as e:
            print("GPT failed:", e)
            clue = "I'm somewhere mysterious."
        
        themed_url = await generate_themed_country_image(country_name, city_name)
    else:
        clue = "I'm somewhere mysterious."
        themed_url = None

    
    return city_name, country_name, "World Cities", clue, street_url, sat_url, live_url, themed_url


async def categorize_text(input_text, title):
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a categorization assistant. Your job is to analyze text and return a 1-2 word category that best describes the content. Do not include words from the title in the category."
                },
                {
                    "role": "user",
                    "content": f"Title: {title}\n\nPlease categorize the following text into a 1-2 word category:\n\n{input_text}"
                }
            ],
            max_tokens=10, 
            temperature=0.3  
        )
        
        category = response.choices[0].message.content.strip()

        title_words = set(re.sub(r"[^\w\s]", "", title).lower().split())  
        category_words = set(re.sub(r"[^\w\s]", "", category).lower().split())  

        if category_words & title_words: 
            return "Hint Fail"  
        return category

    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return "Unknown"


async def get_wikipedia_article(max_words=3, max_length=16):
    base_url = "https://en.wikipedia.org/w/api.php"
    headers = {
        "User-Agent": "Live Trivia & Games/2.4 ([user_agent_email])"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            async with session.get(base_url, params={
                "action": "query",
                "format": "json",
                "generator": "random",
                "grnnamespace": 0,
                "grnlimit": 1
            }) as response:

                if response.status != 200:
                    print("Error fetching from Wikipedia API")
                    return None, None, None, None

                data = await response.json()
                pages = data.get("query", {}).get("pages", {})

                for page_id, page_info in pages.items():
                    title = page_info.get("title", "")
                    if not title.replace(" ", "").isalpha():
                        continue

                    norm_title = remove_diacritics(title)

                    word_count = len(title.split())
                    total_length = len(title)
                    if word_count <= max_words and max_length >= total_length >= 4:
                        words = title.split()
                        if len(words) > 1 and any(word[0].isupper() for word in words[1:]):
                            continue

                        pageid = page_info.get("pageid")
                        intro_text = await fetch_wikipedia_intro(pageid, session)

                        if not intro_text or len(intro_text) < 500:
                            continue

                        redacted_text = redact_intro_text(title, intro_text)

                        if ai_on: 
                            category = await categorize_text(intro_text, title)
                        else:
                            category = "Word"

                        wiki_url = f"https://en.wikipedia.org/wiki/{quote(title)}"

                        await asyncio.sleep(0.5)
                        return norm_title, redacted_text, category, wiki_url


async def fetch_wikipedia_intro(pageid, session):
    base_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "exintro": "1",
        "explaintext": "1",
        "pageids": str(pageid)
    }

    async with session.get(base_url, params=params) as response:
        if response.status != 200:
            print("Error fetching Wikipedia introduction")
            return None

        data = await response.json()
        pages = data.get("query", {}).get("pages", {})
        return pages.get(str(pageid), {}).get("extract", "")


def redact_intro_text(title, intro_text):
    if not title or not intro_text:
        return intro_text
    
    # Split the title into words and build a regex pattern
    words_to_redact = [re.escape(word) for word in title.split()]
    pattern = re.compile(r'\b(' + '|'.join(words_to_redact) + r')\b', re.IGNORECASE)
    
    # Replace matching words with "REDACTED"
    redacted_text = pattern.sub("OKRA", intro_text)
    return redacted_text


async def describe_image_with_vision(image_url, mode, prompt):
    try:

        if mode == "okra-title":
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": "You are a cool image analyst. Your goal is to create image titles of portaits that roasts people."
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Based on what you see in the image, give the image a name with 5 words maximum and ensure the name is okra themed. Your goal is to humiliate the person the portrait is of."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500
            }
         
        elif mode == "roast-title":
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": "You are a cool image analyst. Your goal is to create image titles of portaits that roasts people."
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Based on what you see in the image, give the image a name with 5 words maximum. Your goal is to humiliate the person the portrait is of."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500
            }


        elif mode == "title":
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": "You are a cool image analyst. Your goal is to create image titles."
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Based on what you see in the image, give the image a name with 5 words maximum. The prompt used to create this image was '{prompt}'."
                                #"text": f"Based on what you see in the image, give the image an okra themed title with 5 words maximum."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500
            }
             
        else:
            payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": "You are an image analyst. Your goal is to accurately describe the image to provide to someone as accurately as possible."
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe what you see in this image as accurately as you can."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 500
        }

        response = await openai_client.chat.completions.create(**payload)
        description = response.choices[0].message.content
        return description

    except Exception as e:
        print(f"Error describing the image: {e}")
        return None


async def sovereign_check(user):
    sovereign = await db.hall_of_sovereigns_discord.find_one({"user": user})
    return sovereign is not None


async def get_image_url_from_s3():
    bucket_name = "triviabotwebsite"
    prefix = "generated-images/"
    
    session = aioboto3.Session()
    async with session.client("s3") as s3:
        response = await s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    
    # Extract file keys
    files = [item['Key'] for item in response.get('Contents', []) if item['Key'].lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
    random_file = random.choice(files)
    encoded_filename = quote(random_file)
    #public_url = f"https://triviabotwebsite.s3.amazonaws.com/generated-images/{encoded_filename}"
    public_url = f"https://{bucket_name}.s3.amazonaws.com/{encoded_filename}"
    
    # Step 1: Remove the prefix and file extension
    filename = os.path.basename(random_file).replace('.png', '')

    # Step 2: Extract with regex
    pattern = r'^(.+?)\s*&\s*(.+?)\s+\((.+?)\)$'
    match = re.match(pattern, filename)

    if match:
        title = match.group(1)
        clean_title = re.sub(r"[\"']", "", title)
        user = match.group(2)
        full_date = match.group(3)
        

        
        # Remove the time from the date string
        date_only = ' '.join(full_date.split()[:-1])
        message = "\u200b\n🖼️✨ A memory from the **Okra Museum**"
        message += "\n🥒🏛️ [Visit the Okra Museum](https://94mes.com/okra-museum)\n\u200b"
        await safe_send(channel, content=message, embed=discord.Embed().set_image(url=public_url))

        #message = f"\u200b\n**Masterpiece:** '{title}'\n"
        message = f"\u200b\n**Masterpiece**: *{clean_title}*\n"
        message += f"**Okra's Muse**: *{user}*\n"
        message += f"**Creation Date**: *{date_only}*\n\u200b"

        await safe_send(channel, message)


async def upload_image_to_s3(buffer, winner, description):
    try:
        bucket_name = 'triviabotwebsite'
        folder_name = 'generated-images'

        pst = pytz.timezone('America/Los_Angeles')
        now = datetime.datetime.now(pst)
        formatted_time = now.strftime('%B %d, %Y %H%M')
        object_name = f"{folder_name}/{description} & {winner} ({formatted_time}).png"

        # Async S3 client
        
        session = aioboto3.Session()
        async with session.client("s3") as s3_client:
            await s3_client.put_object(
                Bucket=bucket_name,
                Key=object_name,
                Body=buffer.getvalue(),
                ContentType="image/png"
            )

        return None

    except (BotoCoreError, ClientError) as boto_err:
        print(f"Error uploading to S3: {boto_err}")
        return None


async def upload_okraverse_to_s3(buffer):
    try:
        bucket_name = 'triviabotwebsite'
        folder_name = 'okraverse'
        object_name = f"{folder_name}/okraverse.png"

        # Use async context manager
        session = aioboto3.Session()
        async with session.client("s3") as s3_client:
            await s3_client.put_object(
                Bucket=bucket_name,
                Key=object_name,
                Body=buffer.getvalue(),
                ContentType="image/png"
            )

        return None

    except (BotoCoreError, ClientError) as boto_err:
        print(f"Error uploading to S3: {boto_err}")
        return None


async def load_parameters():
    global image_wins, image_points
    global num_list_players
    global num_mysterybox_clues_default
    global num_crossword_clues_default
    global num_jeopardy_clues_default
    global num_wof_clues_default
    global num_wof_clues_final_default
    global num_mysterybox_clues
    global num_crossword_clues
    global num_jeopardy_clues
    global num_wof_clues
    global num_wof_clues_final
    global num_wf_letters
    global num_math_questions_default
    global num_math_questions
    global num_stats_questions_default
    global num_stats_questions
    global skip_summary
    global discount_step_amount
    global discount_streak_amount
    global channel_id
    global time_between_questions_default
    global time_between_questions
    global max_retries
    global delay_between_retries
    global question_time
    global questions_per_round
    global ai_on
    global sync_commands

    await get_bump_data()

    # Default values
    default_values = {
        "image_wins": 5,
        "image_points": 5000,
        "num_list_players": 5,
        "num_mysterybox_clues_default": 3,
        "num_crossword_clues_default": 0,
        "num_jeopardy_clues_default": 3,
        "num_wof_clues_default": 0,
        "num_wof_clues_final_default": 3,
        "num_wf_letters": 3,
        "num_math_questions_default": 1,
        "num_stats_questions_default": 0,
        "skip_summary": False,
        "ai_on": False,
        "sync_commands": True,
        "discount_step_amount": 20,
        "discount_streak_amount": 5,
        "time_between_questions_default": 5,
        "max_retries": 3,
        "delay_between_retries": 3,
        "question_time": 10,
        "questions_per_round": 10
    }
    
    for attempt in range(max_retries):
        try:

            cursor = db.parameters_discord.find()
            documents = await cursor.to_list(length=None)

            # Initialize variables with defaults
            parameters = {key: default_values[key] for key in default_values}

            # Overwrite defaults with values from the database
            for doc in documents:
                if doc["_id"] in parameters:
                    parameters[doc["_id"]] = int(doc.get("value", parameters[doc["_id"]]))

            # Assign global variables
            image_wins = parameters["image_wins"]
            image_points = parameters["image_points"]
            num_list_players = parameters["num_list_players"]
            num_mysterybox_clues_default = parameters["num_mysterybox_clues_default"]
            num_crossword_clues_default = parameters["num_crossword_clues_default"]
            num_jeopardy_clues_default = parameters["num_jeopardy_clues_default"]
            num_wof_clues_default = parameters["num_wof_clues_default"]
            num_wof_clues_final_default = parameters["num_wof_clues_final_default"]
            num_wf_letters = parameters["num_wf_letters"]
            num_math_questions_default = parameters["num_math_questions_default"]
            num_stats_questions_default = parameters["num_stats_questions_default"]
            skip_summary = parameters["skip_summary"]
            ai_on = parameters["ai_on"]
            sync_commands = parameters["sync_commands"]
            discount_step_amount = parameters["discount_step_amount"]
            discount_streak_amount = parameters["discount_streak_amount"]
            time_between_questions_default = parameters["time_between_questions_default"]
            max_retries = parameters["max_retries"]
            delay_between_retries = parameters["delay_between_retries"]
            question_time = parameters["question_time"]
            questions_per_round = parameters["questions_per_round"]
            
            num_mysterybox_clues = num_mysterybox_clues_default
            num_crossword_clues = num_crossword_clues_default
            num_jeopardy_clues = num_jeopardy_clues_default
            num_wof_clues = num_wof_clues_default
            num_wof_clues_final = num_wof_clues_final_default
            num_math_questions = num_math_questions_default
            num_stats_questions = num_stats_questions_default
            time_between_questions = time_between_questions_default
            
            # Exit loop if successful
            break

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {delay_between_retries} seconds...")
                await asyncio.sleep(delay_between_retries)
            else:
                print("Max retries reached. Data loading failed.")
                image_wins = default_values["image_wins"]
                image_points = default_values["image_points"]
                num_list_players = default_values["num_list_players"]
                num_mysterybox_clues_default = default_values["num_mysterybox_clues_default"]
                num_crossword_clues_default = default_values["num_crossword_clues_default"]
                num_jeopardy_clues_default = default_values["num_jeopardy_clues_default"]
                num_wof_clues_default = default_values["num_wof_clues_default"]
                num_wof_clues_final_default = default_values["num_wof_clues_final_default"]
                num_wf_letters = default_values["num_wf_letters"]
                num_math_questions_default = default_values["num_math_questions_default"]
                num_stats_questions_default = default_values["num_stats_questions_default"]
                skip_summary = default_values["skip_summary"]
                ai_on = default_values["ai_on"]
                sync_commands = default_values["sync_commands"]
                discount_step_amount = default_values["discount_step_amount"]
                discount_streak_amount = default_values["discount_streak_amount"]
                time_between_questions_default = default_values["time_between_questions_default"]
                max_retries = default_values["max_retries"]
                delay_between_retries = default_values["delay_between_retries"]
                question_time = default_values["question_time"]
                questions_per_round = default_values["questions_per_round"]

                num_mysterybox_clues = num_mysterybox_clues_default
                num_crossword_clues = num_crossword_clues_default
                num_jeopardy_clues = num_jeopardy_clues_default
                num_wof_clues = num_wof_clues_default
                num_wof_clues_final = num_wof_clues_final_default
                num_math_questions = num_math_questions_default
                num_stats_questions = num_stats_questions_default
                time_between_questions = time_between_questions_default


async def get_int_param(db, param_id, default_value):
    """Helper to get integer parameter from MongoDB."""
    try:
        doc = await db.parameters_discord.find_one({"_id": param_id})
        return int(doc.get("value", default_value)) if doc else default_value
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return default_value


async def save_round_options_to_db():
    """Save current round options state to MongoDB parameters_discord collection."""
    global time_between_questions, ghost_mode, num_crossword_clues
    global num_jeopardy_clues, num_mysterybox_clues, num_wof_clues
    global god_mode, yolo_mode, num_math_questions, num_stats_questions
    global image_questions, marx_mode, blind_mode, sniper_mode
    global cloak_mode, cloaked_user

    try:
        # Store each variable as a document with _id as the variable name
        updates = [
            {"_id": "round_time_between_questions", "value": time_between_questions},
            {"_id": "round_ghost_mode", "value": int(ghost_mode)},  # Convert bool to int
            {"_id": "round_num_crossword_clues", "value": num_crossword_clues},
            {"_id": "round_num_jeopardy_clues", "value": num_jeopardy_clues},
            {"_id": "round_num_mysterybox_clues", "value": num_mysterybox_clues},
            {"_id": "round_num_wof_clues", "value": num_wof_clues},
            {"_id": "round_god_mode", "value": int(god_mode)},
            {"_id": "round_yolo_mode", "value": int(yolo_mode)},
            {"_id": "round_num_math_questions", "value": num_math_questions},
            {"_id": "round_num_stats_questions", "value": num_stats_questions},
            {"_id": "round_image_questions", "value": int(image_questions)},
            {"_id": "round_marx_mode", "value": int(marx_mode)},
            {"_id": "round_blind_mode", "value": int(blind_mode)},
            {"_id": "round_sniper_mode", "value": int(sniper_mode)},
            {"_id": "round_cloak_mode", "value": int(cloak_mode)},
            {"_id": "round_cloaked_user", "value": cloaked_user or 0},  # Store 0 if None
        ]

        for update in updates:
            await db.parameters_discord.update_one(
                {"_id": update["_id"]},
                {"$set": {"value": update["value"]}},
                upsert=True
            )

        print("✅ Saved round options to MongoDB")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"❌ Error saving round options to MongoDB: {e}")


async def load_round_options_from_db():
    """Load round options state from MongoDB and set global variables."""
    global time_between_questions, ghost_mode, num_crossword_clues
    global num_jeopardy_clues, num_mysterybox_clues, num_wof_clues
    global god_mode, yolo_mode, num_math_questions, num_stats_questions
    global image_questions, marx_mode, blind_mode, sniper_mode
    global cloak_mode, cloaked_user

    try:
        # Load each variable, with fallback to defaults
        time_between_questions = await get_int_param(db, "round_time_between_questions", time_between_questions_default)
        ghost_mode = bool(await get_int_param(db, "round_ghost_mode", int(ghost_mode_default)))
        num_crossword_clues = await get_int_param(db, "round_num_crossword_clues", num_crossword_clues_default)
        num_jeopardy_clues = await get_int_param(db, "round_num_jeopardy_clues", num_jeopardy_clues_default)
        num_mysterybox_clues = await get_int_param(db, "round_num_mysterybox_clues", num_mysterybox_clues_default)
        num_wof_clues = await get_int_param(db, "round_num_wof_clues", num_wof_clues_default)
        god_mode = bool(await get_int_param(db, "round_god_mode", int(god_mode_default)))
        yolo_mode = bool(await get_int_param(db, "round_yolo_mode", int(yolo_mode_default)))
        num_math_questions = await get_int_param(db, "round_num_math_questions", num_math_questions_default)
        num_stats_questions = await get_int_param(db, "round_num_stats_questions", num_stats_questions_default)
        image_questions = bool(await get_int_param(db, "round_image_questions", int(image_questions_default)))
        marx_mode = bool(await get_int_param(db, "round_marx_mode", int(marx_mode_default)))
        blind_mode = bool(await get_int_param(db, "round_blind_mode", int(blind_mode_default)))
        sniper_mode = bool(await get_int_param(db, "round_sniper_mode", int(sniper_mode_default)))
        cloak_mode = bool(await get_int_param(db, "round_cloak_mode", int(cloak_mode_default)))

        cloaked_user_val = await get_int_param(db, "round_cloaked_user", 0)
        cloaked_user = cloaked_user_val if cloaked_user_val != 0 else None

        print("✅ Loaded round options from MongoDB")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"❌ Error loading round options from MongoDB: {e}")


async def save_selected_questions_to_db(selected_questions):
    """Save selected questions to MongoDB round_questions collection."""
    try:
        # Clear the collection first (only store next round's questions)
        await db.round_questions.delete_many({})

        # Convert tuple format to document format for MongoDB
        documents = []
        for idx, (category, question, url, answers, db_name, question_id) in enumerate(selected_questions):
            doc = {
                "_id": idx,
                "category": category,
                "question": question,
                "url": url,
                "answers": answers,
                "db": db_name,
                "question_id": question_id
            }
            documents.append(doc)

        if documents:
            await db.round_questions.insert_many(documents)
            print(f"✅ Saved {len(documents)} questions to MongoDB")

    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"❌ Error saving questions to MongoDB: {e}")


async def load_selected_questions_from_db():
    """Load selected questions from MongoDB round_questions collection."""
    try:
        cursor = db.round_questions.find().sort("_id", 1)
        documents = await cursor.to_list(length=None)

        if not documents:
            print("ℹ️ No saved questions found in MongoDB")
            return None

        # Convert documents back to tuple format
        selected_questions = [
            (doc["category"], doc["question"], doc["url"], doc["answers"], doc["db"], doc["question_id"])
            for doc in documents
        ]

        print(f"✅ Loaded {len(selected_questions)} questions from MongoDB")
        return selected_questions

    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"❌ Error loading questions from MongoDB: {e}")
        return None


async def nice_creep_okra_option(winner, winner_id):
    global nice_okra, creep_okra, wf_winner, seductive_okra, joke_okra
    
    # Reset all mode flags
    nice_okra = False
    creep_okra = False
    wf_winner = False
    seductive_okra = False
    joke_okra = False
    
    # Initialize all the new message type flags
    global haiku_okra, trailer_okra, heist_okra, horoscope_okra, rap_okra, shakespeare_okra, pirate_okra, noir_okra, hype_okra, roast_okra
    haiku_okra = False
    trailer_okra = False
    heist_okra = False
    horoscope_okra = False
    rap_okra = False
    shakespeare_okra = False
    pirate_okra = False
    noir_okra = False
    hype_okra = False
    roast_okra = False
    
    message = f"\u200b\n🥒🤝 Thank you **<@{winner_id}>** for your support.\n\u200b\n" 
    message += f"🥒😊 Say **okra** and I'll be nice.\n"
    message += f"👀🔭 Say **creep** for a roast from inside your house.\n"
    message += f"💋👠 Say **love me** and I'll seduce you.\n"
    message += f"🤡🤣 Say **joke** and I'll write you a dad joke.\n"
    message += f"🧘‍♂️🗻 Say **haiku** for a 5‑7‑5 tribute.\n"
    message += f"🎬📽️ Say **trailer** for a movie trailer voiceover.\n"
    message += f"🧤🕶️ Say **heist** for a suave caper recap.\n"    
    message += f"🔮✨ Say **horoscope** for your trivia future.\n"
    message += f"🎤🎶 Say **rap** for two quick bars.\n"
    message += f"📜🪶 Say **shakespeare** for bardic praise.\n"
    message += f"🏴‍☠️⚓ Say **pirate** for a captain's salute.\n"
    message += f"🕵️‍♂️🌧️ Say **noir** for a hardboiled line.\n"
    message += f"📣🔥 Say **hype** for a stadium-sized celebration.\n"
    message += f"🔥🍗 Say **roast** and I'll roast you.\n\u200b"
    await safe_send(channel, message)

    TRIGGERS = [
        "okra", "creep", "love me", "joke", "haiku", "trailer",
        "heist", "horoscope", "rap", "shakespeare", "pirate",
        "noir", "hype", "roast"
    ]
    
    def check(m):
        if m.channel != channel or m.author.id != winner_id:
            return False
        # check if any trigger is in the message content (case-insensitive)
        content = m.content.lower()
        return any(trigger in content for trigger in TRIGGERS)

    
    try:
        response = await asyncio.wait_for(
            bot.wait_for('message', check=check),
            timeout=magic_time  # time in seconds
        )

        content = response.content.lower().strip()

        if "okra" in content:
            await response.add_reaction("🥒")
            nice_okra = True
            wf_winner = True
        elif "creep" in content:
            await response.add_reaction("👀")
            creep_okra = True
        elif "love me" in content:
            await response.add_reaction("💋")
            seductive_okra = True 
        elif "joke" in content:
            await response.add_reaction("🤣")
            joke_okra = True
        elif "haiku" in content:
            await response.add_reaction("🧘‍♂️")
            haiku_okra = True
        elif "trailer" in content:
            await response.add_reaction("🎬")
            trailer_okra = True
        elif "heist" in content:
            await response.add_reaction("🧤")
            heist_okra = True
        elif "horoscope" in content:
            await response.add_reaction("🔮")
            horoscope_okra = True
        elif "rap" in content:
            await response.add_reaction("🎤")
            rap_okra = True
        elif "shakespeare" in content:
            await response.add_reaction("📜")
            shakespeare_okra = True
        elif "pirate" in content:
            await response.add_reaction("🏴‍☠️")
            pirate_okra = True
        elif "noir" in content:
            await response.add_reaction("🕵️‍♂️")
            noir_okra = True
        elif "hype" in content:
            await response.add_reaction("📣")
            hype_okra = True
        elif "roast" in content:
            await response.add_reaction("🍗")
            roast_okra = True

    except asyncio.TimeoutError:
        pass

    except Exception as e:
        print(f"Unexpected error during okra option handling: {e}")
        sentry_sdk.capture_exception(e)
    
    
async def generate_round_summary_image(round_data, winner, winner_id):
    if skip_summary == True:
        message += "\nBe sure to drink your Okratine.\n"
        await safe_send(channel, message)
        return None
        
    winner_coffees = await get_coffees(winner_id)
    
    if winner == "OkraStrut":
        prompt = (
            "The setting is a fiery Hell, where a giant and angry piece of okra holds a massive golden trophy while looking down on and smiting all other players. "
            "The atmosphere is angry, scary, and full of malice."
        )
        message = "🥒OKRA!! 🥒OKRA!! 🥒OKRA!!\n"
        
    elif winner_coffees > 100:
        prompt = (
            f"Draw What you think {winner} looks like surrounded by okra and money. "
            "Add glowing lights, hearts, and a festive atmosphere."
        )
        message = f"✊🔥 {winner}, thank you for your donation to the cause. And nice streak!\n"
    
    else:
        categories = {
            "0": "😠🥒 Okrap (Horror)",
            "1": "🌹🏰 Okrenaissance",
            "2": "😇✨ Okroly and Divine",
            "3": "🎲🔀 (OK)Random",
            "4": f"🖼️🔤 Provide the Prompt 🥒"
        }

        # Ask the user to choose a category
        selected_category, additional_prompt = await ask_category(winner, categories, winner_coffees, winner_id)
                    
        prompts_by_category = {
            "0": [
                f"A scary scene from a horror movie with what you think {winner} looks running from an okra."
            ],
            "1": [
                f"A Renaissance painting of what you think {winner} looks like holding an okra. Make the painting elegant and refined."
            ],
            "2": [
                f"An image of what you think {winner} looks like worshipping an okra. Make it appealing and accepting of religions of all types."
            ],
            "3": [
                f"An image of what you think {winner} looks like intereracting with an okra in the most crazy, ridiculous, and over the top random way."
            ],
            "4": [
                f"Draw an okra themed picture of {winner} {additional_prompt}.\n"  
            ]
        }

        # Select a prompt based on the chosen category
        if selected_category and selected_category in prompts_by_category:
            prompt = random.choice(prompts_by_category[selected_category])
        else:
            prompt = f"A horror image of what you think {winner} looks like being pursued by something okra themed."

            
    print(prompt)
    
    # Generate the image using DALL-E
    
    try:
        response = await openai_client.images.generate(
            model="dall-e-2",
            prompt=prompt,
            n=1,
            size="512x512",
        )
        image_url = response.data[0].url
        
        if selected_category == "4":
            image_description = await describe_image_with_vision(image_url, "title", prompt)
        else:
            image_description = await describe_image_with_vision(image_url, "title", prompt)
            
        message = f"🔥💖 **<@{winner_id}>**, you've done well. I drew this **for you**.\n"
        await safe_send(channel, content=message, embed=discord.Embed().set_image(url=image_url))
        
        message = f"\n**I call it**...*{image_description}*\n"
        message += f"\n🏛️👋 **Welcome to the Okra Museum**"
        message += "\n🌐➡️ [Visit the Museum](https://94mes.com/okra-museum)\n"
        await safe_send(channel, message)

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    print(f"Failed to download image: {resp.status}")
                    return None
                image_data = await resp.read()

        loop = asyncio.get_running_loop()

        def process_image():
            img = Image.open(io.BytesIO(image_data)).resize((256, 256))
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer

        buffer = await loop.run_in_executor(None, process_image)
        await upload_image_to_s3(buffer, winner, image_description)
        return None
        
    except openai.OpenAIError as e:
        print(f"Error generating image: {e}")
        # Check if the error is due to the safety system
        if "Your request was rejected as a result of our safety system" in str(e):
            # Use a default safe prompt
            default_prompt = f"A Renaissance painting of what you think {winner} looks like holding an okra. Make the painting elegant and refined."
            try:
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: openai.Image.create(
                        prompt=default_prompt,
                        n=1,
                        size="512x512"  # Adjust size as needed
                    )
                )
                
                # Return the image URL from the API response
                image_url = response["data"][0]["url"]
                image_description = await describe_image_with_vision(image_url, "title", prompt)
                
    
                message = f"😈😉 <@{winner_id}> Naughty naughty, I'll have to pick another.\n\n"
                await safe_send(channel, content=message, embed=discord.Embed().set_image(url=image_url))
                message = f"\nI call it: '{image_description}'\n"
                message += f"\n🏛️👋 Welcome to the Okra Museum"
                message += "\n🌐➡️ [Visit the Museum](https://94mes.com/okra-museum)\n"
                await safe_send(channel, message)
        
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status != 200:
                            print(f"Failed to download image: {resp.status}")
                            return None
                        image_data = await resp.read()

                loop = asyncio.get_running_loop()

                buffer = await loop.run_in_executor(None, lambda: (
                    lambda buf: (buf.seek(0), buf)[1]
                )(  # open, resize, save to buffer
                    (lambda img: (
                        img.save(io := io.BytesIO(), format="PNG"),
                        io
                    ))(Image.open(io.BytesIO(image_data)).resize((256, 256)))
                ))

                await upload_image_to_s3(buffer, winner, image_description)
                return None
            
            except openai.OpenAIError as e2:
                print(f"Error generating default image: {e2}")
                return "Image generation failed!"
        else:
            return "Image generation failed!"


async def ask_category(winner, categories, winner_coffees, winner_id):
    additional_prompt = ""

    # Display categories
    category_message = f"\u200b\n🎨🖍️ **<@{winner_id}>** Pick a theme for the Okra Museum!\n\u200b"
    for key, value in categories.items():
        category_message += f"**{key}**: {value}\n"
    await safe_send(channel, category_message)

    def check(m):
        return m.channel == channel and m.author != bot.user and m.author.id == winner_id

    end_time = asyncio.get_event_loop().time() + magic_time

    while True:
        remaining_time = end_time - asyncio.get_event_loop().time()
        if remaining_time <= 0:
            await safe_send(channel, "\u200b\n🐢⏳ Too slow. Okra time.\n\u200b")
            return None, additional_prompt

        try:
            response = await asyncio.wait_for(bot.wait_for('message', check=check), timeout=remaining_time)
            message_content = response.content.strip()

            # Case 1: Invalid choice (not in categories)
            if message_content not in categories:
                await response.add_reaction("❌")
                continue

            # Case 2: Coffee-locked option, no coffee
            if message_content == '4' and winner_coffees <= 0:
                await response.add_reaction("🥒")
                await safe_send(channel, f"🙏😔 Sorry **<@{winner_id}>**, choice **{message_content}** is for **Okrans Only** 🥒.")
                continue

            # Case 3: Valid choice
            await response.add_reaction("✅")
            await safe_send(channel, f"💪🛡️ I got you **<@{winner_id}>**! Choice {message_content} it is.")

            if message_content == '4' and winner_coffees > 0:
                additional_prompt = await request_prompt(winner, winner_id)

            return message_content, additional_prompt

        except asyncio.TimeoutError:
            await safe_send(channel, "\u200b\n🐢⏳ Too slow. Okra time.\n\u200b")
            return None, additional_prompt


async def request_prompt(winner, winner_id):
    global magic_time

    collected_words = []
    start_time = asyncio.get_event_loop().time()
   
    message = f"\u200b\n🖼️🔟 **<@{winner_id}>**, Fill in the blank. *10 words max* and **be good**.\n\u200b"
    message += f"\n*Draw an okra themed picture of **<@{winner_id}>**...*\n\u200b"
    await safe_send(channel, message)

    def check(m):
        return m.channel == channel and m.author != bot.user and m.author.id == winner_id

    try:
        while len(collected_words) < 10 and asyncio.get_event_loop().time() - start_time < (magic_time + 5):
            try:
                response = await asyncio.wait_for(bot.wait_for('message', check=check), timeout=magic_time)
                words = response.content.strip().split()

                for word in words:
                    if len(collected_words) < 10:
                        collected_words.append(word)
                    else:
                        break

                await response.add_reaction("✅")

            except asyncio.TimeoutError:
                break  # no more responses in time

    except Exception as e:
        print(f"Error collecting words: {e}")
        sentry_sdk.capture_exception(e)

    if not collected_words:
        await safe_send(channel, "Nothing. Okra time.")
    else:
        final_msg = f"\u200b\n💥🤯 **Ok...ra I got**: 'Draw an okra-themed picture of **<@{winner_id}>** {' '.join(collected_words)}'\n\u200b"
        await safe_send(channel, final_msg)

    return ' '.join(collected_words)


async def get_coffees(user_id):
    #if local_mode == True:
    #    return 5
    guild = bot.get_guild(OKRAN_GUILD_ID)
    if not guild:
        print(f"⚠️ Bot is not in guild with ID {OKRAN_GUILD_ID}")
        return 0
    try:
        member = await guild.fetch_member(user_id)
        # Check if user has any of the allowed roles
        allowed_role_ids = {BUMPER_KING_ROLE_ID, OKRAN_ROLE_ID, OKRAN_ROLE_ID_2}
        if any(role.id in allowed_role_ids for role in member.roles):
            return 5
        else:
            return 0
    except discord.NotFound:
        print(f"❌ User ID {user_id} not found in guild")
        return 0
    except discord.HTTPException as e:
        print(f"❌ Error fetching member in guild {guild.name}: {e}")
        return 0


def get_math_question():
    question_functions = [create_mean_question, create_median_question, create_derivative_question, create_zeroes_question, create_factors_question, create_base_question, create_trig_question, create_algebra_question]
    selected_question_function = random.choice(question_functions)
    return selected_question_function()

        
def get_stats_question():
    question_functions = [create_mean_question, create_median_question]
    selected_question_function = random.choice(question_functions)
    return selected_question_function()


def create_trig_question():
    return {
        "category": "Mathematics: Trigonometry",
        "question": "",
        "url": "trig",
        "answers": [""]
    }


def create_algebra_question():
    return {
        "category": "Mathematics: Algebra",
        "question": "",
        "url": "algebra",
        "answers": [""]
    }


def create_mean_question():
    return {
        "category": "Mathematics: Mean",
        "question": "What is the MEAN of the following set?",
        "url": "mean",
        "answers": [""]
    }


def create_median_question():
    return {
        "category": "Mathematics: Median",
        "question": "What is the MEDIAN of the following set?",
        "url": "median",
        "answers": [""]
    }


def create_base_question():
    return {
        "category": "Mathematics: Bases",
        "question": f"What is the DECIMAL equivalent of the following BASE number:",
        "url": "base",
        "answers": [""]
    }


def create_derivative_question():
    return {
        "category": "Mathematics: Derivatives",
        "question": "What is the DERIVATIVE with respect to x?",
        "url": "derivative",
        "answers": [""]
    }


def create_sum_zeroes_question():
    return {
        "category": "Mathematics: Polynomials",
        "question": "What is the SUM of the zeroes (or roots) of the function defined:",
        "url": "zeroes sum",
        "answers": [""]
    }


def create_product_zeroes_question():
    return {
        "category": "Mathematics: Polynomials",
        "question": "What is the PRODUCT of the zeroes (or roots) of the function defined:",
        "url": "zeroes product",
        "answers": [""]
    }


def create_zeroes_question():
    return {
        "category": "Mathematics: Polynomials",
        "question": "What are the 2 ZEROES (or roots) of the function defined:",
        "url": "zeroes",
        "answers": [""]
    }


def create_factors_question():
    return {
        "category": "Mathematics: Polynomials",
        "question": "Factor the function defined:",
        "url": "factors",
        "answers": [""]
    }
        
        
async def select_wof_questions(winner, winner_id):
    global fixed_letters
    
    try:
        await asyncio.sleep(2)
        recent_wof_ids = await get_recent_question_ids_from_mongo("wof")
        selected_questions = []
        fixed_letters = ['O', 'K', 'R', 'A']

        # Fetch wheel of fortune questions using the random subset method
        wof_collection = db["wof_questions"]
        pipeline_wof = [
            {"$match": {"_id": {"$nin": list(recent_wof_ids)}}},  # Exclude recent IDs
            {"$group": {  # Group by question text to ensure uniqueness
                "_id": "$question",  # Group by the question text field
                "question_doc": {"$first": "$$ROOT"}  # Select the first document with each unique text
            }},
            {"$replaceRoot": {"newRoot": "$question_doc"}},  # Flatten the grouped results
            {"$sample": {"size": 5}}  # Sample 3 unique questions
        ]

        wof_questions = await wof_collection.aggregate(pipeline_wof).to_list(length=5)

        message = f"\u200b\n\u200b\n🍷⚔️ **<@{winner_id}>**, your mini-game awaits (#)...\n\n"
        
        message += f"😎 **Everyone's Welcome**"
        counter = 0
        for doc in wof_questions:
            category = doc["question"]  # Use the key name to access category
            message += f"\n{counter}.\u200b 🎡💰 WoF: {category}"
            counter = counter + 1        
        premium_counts = counter
        message += f"\n\n🥒 **Okrans Only**"
        message += f"\n{counter}.\u200b 🌐🎲 Wikipedia Roulette\n"
        counter = counter + 1
        message += f"{counter}.\u200b 📚🎲 Dictionary Roulette\n"
        counter = counter + 1
        message += f"{counter}.\u200b 📖🎲 Thesaurus Roulette\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🌍❔ Where's Okra?\n"
        counter = counter + 1
        message += f"{counter}.\u200b ⚔️🧍 FeUd (Single Player)\n"
        counter = counter + 1
        message += f"\n🥒✨: **Okrans Only** ({num_list_players}+ players)\n"
        message += f"{counter}.\u200b ⚔️⚡ FeUd Blitz\n"
        counter = counter + 1
        message += f"{counter}.\u200b 📝🥊 List Battle\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🎥⚡ Poster Blitz\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🎬💥 Movie Mayhem\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🧩🔗 Missing Link\n"
        counter = counter + 1
        message += f"{counter}.\u200b 👤🌟 Famous Peeps\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🔢📜 Ranker Lists\n"
        counter = counter + 1
        message += f"{counter}.\u200b 👁️✨ Magic EyeD\n"
        counter = counter + 1
        message += f"{counter}.\u200b ❓🦓 OkrAnimal\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🟢🎩 The Riddler\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🤓📚 Word Nerd\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🎏🎉 Flag Fest\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🎧🎤 LyrIQ\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🎰🗣️ PolygLottery\n"
        counter = counter + 1
        message += f"{counter}.\u200b 📖🕵️‍♂️ Prose & Cons\n"
        counter = counter + 1
        message += f"{counter}.\u200b ➕➖ Sign Language\n"
        counter = counter + 1
        message += f"{counter}.\u200b 💧🔥 Elementary\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🧩🌀 Jigsawed\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🗺️❓ Borderline\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🙃🙂 Face/Off\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🦅🇺🇸 Rushmore\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🟩🟨 Wordle War\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🎼🎵 MusIQ\n"
        counter = counter + 1
        message += f"{counter}.\u200b 👓🕵️‍♂️ Myopic Mystery\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🔬🔍 Microscopic\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🧬☢️ Fusion\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🔢🎯 Tally\n"
        counter = counter + 1
        message += f"{counter}.\u200b ♟️👑 Checkmate\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🏙️💹 Wall Street\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🌍💵 XXXX\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🥒🏁 OkRACE\n"
        counter = counter + 1
        message += f"{counter}.\u200b 🔍🔤 Spotlight\n"
        counter = counter + 1
        message += f"{counter}.\u200b 👂➡️ Hear Here 🎧 \n"
        message += f"99.\u200b 🌀🤯 CHAOS\n"

        message += f"\n⚙️ **Other Options**\n"
  
        message += f"00.\u200b 🥗🌟 Okra's Choice\n"
        message += f"x.\u200b ⏭️🕹️ Skip Mini-Game\n\u200b"
        await safe_send(channel, message) 
                
        selected_wof_category = await ask_wof_number(winner, winner_id)

        randomize_embed_color()

        if selected_wof_category == "x":
            gif_set = [
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad1.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad2.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad3.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad4.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad5.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad6.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad7.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad8.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad9.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad10.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad11.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad12.gif",
            "https://triviabotwebsite.s3.us-east-2.amazonaws.com/sad/sad13.gif"
            ]

            gif_url = random.choice(gif_set)
            message = f"\n⏭️🕹️ <@{winner_id}>: '**Less** Games. **More** Trivia.'\n"
            await safe_send(channel, content=message, embed=discord.Embed().set_image(url=gif_url))
            await asyncio.sleep(3)
            return None
        
        elif int(selected_wof_category) < premium_counts:
            wof_question = wof_questions[int(selected_wof_category)]
            wof_answer = wof_question["answers"][0]
            wof_clue = wof_question["question"]
                    
            wof_question_id = wof_question["_id"]  # Get the ID of the selected question
            if wof_question_id:
                await store_question_ids_in_mongo([wof_question_id], "wof")  # Store it as a list containing a single ID
        
        elif selected_wof_category == "11":
            await ask_list_question(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "10":
            await ask_feud_question(winner, "cooperative", winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "9":
            await ask_feud_question(winner, "solo", winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "12":
            await ask_poster_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "13":
            await ask_movie_scenes_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "14":
            await ask_missing_link(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "15":
            await ask_ranker_people_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "16":
            await ask_ranker_list_question(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "17":
            await ask_magic_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "18":
            await ask_animal_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "19":
            await ask_riddle_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "20":
            await ask_dictionary_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "21":
            await ask_flags_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "22":
            await ask_lyric_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "23":
            await ask_polyglottery_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "24":
            await ask_book_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "25":
            await ask_math_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "26":
            await ask_element_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "27":
            await ask_jigsaw_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "28":
            await ask_border_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "29":
            await ask_faceoff_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "30":
            await ask_president_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "31":
            await ask_wordle_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "32":
            await ask_music_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "33":
            await ask_myopic_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "34":
            await ask_microscopic_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "35":
            await ask_fusion_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "36":
            await ask_tally_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "37":
            await ask_chess_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "38":
            await ask_stock_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None

        elif selected_wof_category == "39":
            await ask_currency_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "40":
            await ask_okrace_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "41":
            await ask_search_challenge(winner, winner_id)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "42":
            await ask_soundfx_challenge(winner, winner_id, 5)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "99":
            await ask_chaos_challenge(winner, winner_id, 5)
            await asyncio.sleep(3)
            return None
        
        elif selected_wof_category == "5":
            wof_answer, redacted_intro, wof_clue, wiki_url = await get_wikipedia_article(3, 16)
            if wof_answer is None:
                message = f"\n❌ Wikipedia API Error. Falling back to Word Nerd\n."
                await safe_send(channel, message)
                await ask_dictionary_challenge(winner)
                return None
            else:
                wikipedia_message = f"\n🥒⬛ Okracted Clue:\n\n{redacted_intro}\n"
                await safe_send(channel, wikipedia_message)
            await asyncio.sleep(3)

        elif selected_wof_category == "6":
            wof_answer, wof_clue, word_definition, word_url = await fetch_random_word()
            dictionary_message = f"\n📖🔍 Definition:\n"
            for i, definition in enumerate(word_definition, start=1):
                dictionary_message += f"\n {i}. {definition}"
            dictionary_message += "\n"
            await safe_send(channel, dictionary_message)
            await asyncio.sleep(3)

        elif selected_wof_category == "7":
            wof_answer, wof_clue, word_syn, word_ant, word_url = await fetch_random_word_thes()
            thesaurus_message = f"\n📖✅ Synonyms\n"
            for i, synonym in enumerate(word_syn, start=1):
                thesaurus_message += f"\n {i}. {synonym}"
            thesaurus_message += "\n"
            if word_ant:
                thesaurus_message += "\n📖❌ Antonyms:"
                for i, antonym in enumerate(word_ant, start=1):
                    thesaurus_message += f"\n  {i}. {antonym}"
                thesaurus_message += "\n"
            await safe_send(channel, thesaurus_message)
            await asyncio.sleep(3)

        elif selected_wof_category == "8":
            wof_answer, country_name, wof_clue, location_clue, street_view_url, satellite_view_url, satellite_view_live_url, themed_country_url = await get_random_city(winner)

            if ai_on:
                location_clue = f"\n🌦️📊 We intercepted this message...\n\n{location_clue}\n"
                await safe_send(channel, location_clue)

            fixed_letters = []
            await asyncio.sleep(3)

            if street_view_url != None:
                await safe_send(channel, content="\n🏙️👁️ We saw OkraStrut post this to X...\n", embed=discord.Embed().set_image(url=street_view_url))
                await asyncio.sleep(2)
            
            await safe_send(channel, content="\n🛰️🌍 Our spies tracked him to this area...\n", embed=discord.Embed().set_image(url=satellite_view_url))                
            await asyncio.sleep(2)

            if ai_on:
                await safe_send(channel, content="\n📸🥒 We found this on OkraStrut's Insta...\n", embed=discord.Embed().set_image(url=themed_country_url))                                
                await asyncio.sleep(2)

        image_file, image_width, image_height, display_string = generate_wof_image(wof_answer, wof_clue, fixed_letters)
        print(f"{wof_clue}: {wof_answer}")
            
        if image_questions == True:    
            embed = discord.Embed()
            embed.set_image(url="attachment://image.png")
            await safe_send(channel, embed=embed, file=image_file)
        else:
            fixed_letters_str = "Revealed Letters: " + ' '.join(fixed_letters)
            message = f"{display_string}\n{wof_clue}\n{fixed_letters_str}\n"
            await safe_send(channel, message)

        wof_letters = await ask_wof_letters(winner, wof_answer, 5, winner_id)
        
        if wf_winner == False:
            await asyncio.sleep(1.5)
            image_file, image_width, image_height, display_string = generate_wof_image(wof_answer, wof_clue, wof_letters) 
            
            if image_questions == True:
                embed = discord.Embed()
                embed.set_image(url="attachment://image.png")
                await safe_send(channel, embed=embed, file=image_file)
            else:
                wof_letters_str = "Revealed Letters: " + ' '.join(wof_letters)
                message = f"{display_string}\n{wof_clue}\n{wof_letters_str}\n"
                await safe_send(channel, message)

            await process_wof_guesses(winner, wof_answer, 5, winner_id)

        if selected_wof_category == "5":
            await asyncio.sleep(1.5)
            wikipedia_message = f"\n🌐📄 Wikipedia Link: {wiki_url}\n"
            await safe_send(channel, wikipedia_message)
            await asyncio.sleep(1.5)

        if selected_wof_category == "6":
            await asyncio.sleep(1.5)
            webster_message = f"\n📚📄 Webster Link: {word_url}\n"
            await safe_send(channel, webster_message)
            await asyncio.sleep(1.5)

        if selected_wof_category == "7":
            await asyncio.sleep(1.5)
            webster_message = f"\n📖📄 Webster Link: {word_url}\n"
            await safe_send(channel, webster_message)
            await asyncio.sleep(1.5)

        if selected_wof_category == "8":
            await asyncio.sleep(1.5)
            maps_message = f"\n🌍❔ Okra's Location: {satellite_view_live_url}\n"
            await safe_send(channel, maps_message)
            await asyncio.sleep(1.5)

        return None

    except Exception as e:
        sentry_sdk.capture_exception(e)
        error_details = traceback.format_exc()
        print(f"Error selecting wof questions: {e}\nDetailed traceback:\n{error_details}")
        return None  

    
async def process_wof_guesses(winner, answer, extra_time, winner_id):
    global wf_winner

    answer = answer.upper() 
    await safe_send(channel, f"\u200b\n\u200b\n**<@{winner_id}>** ❓**Your Answer**❓\n\u200b")

    def check(m):
        return m.channel == channel and m.author != bot.user and m.author.id == winner_id

    start_time = time.time()  # Track when the question starts

    while time.time() - start_time < (magic_time + extra_time):
        try:
            remaining = (magic_time + extra_time) - (time.time() - start_time)
            timeout = min(remaining, 30)
            message = await bot.wait_for('message', timeout=timeout, check=check)
            message_content = message.content.upper().strip()

            if message_content == answer:
                await message.add_reaction("🎉")
                await safe_send(channel, f"\n✅🎉 Correct: **{answer}**\n\u200b")
                wf_winner = True
                return

            # Incorrect guess
            await message.add_reaction("❌")

        except asyncio.TimeoutError:
            break
        except Exception as e:
            print(f"Error collecting WOF guesses: {e}")
            break

    await safe_send(channel, f"⏰ Time's up! The answer was: {answer}")


async def ask_wof_letters(winner, answer, extra_time, winner_id):
    global wf_winner

    revealed_count = sum(ch.lower() in "okra" for ch in answer)
    answer_length = len(answer.replace(" ", ""))
    letters_remaining = answer_length - revealed_count

    answer = answer.upper()
    start_time = time.time()
    await safe_send(channel, f"\u200b\n**<@{winner_id}>**:❓**Pick {num_wf_letters} Letters**❓\n" +
                       (f"\n🥒 I'll give you O K R A 🥒\n\u200b" if fixed_letters else ""))    
    
    wf_letters = []

    def check(m):
        return m.channel == channel and m.author != bot.user and m.author.id == winner_id

    while time.time() - start_time < (magic_time + extra_time):
        try:
            if len(wf_letters) == num_wf_letters:
                break

            remaining_time = (magic_time + extra_time) - (time.time() - start_time)
            timeout = min(remaining_time, 30)
            message = await bot.wait_for('message', timeout=timeout, check=check)
            message_content = message.content.upper()

            if message_content == answer:
                await message.add_reaction("🎉")
                await safe_send(channel, f"\n✅🎉 Correct **<@{winner_id}>**! {answer}\n\u200b")
                wf_winner = True
                return True

            for char in message_content:
                if char in fixed_letters:
                    continue
                if len(wf_letters) < num_wf_letters and char.isalpha() and char not in wf_letters:
                    wf_letters.append(char)
            
            if len(wf_letters) >= num_wf_letters:
                await message.add_reaction("🥒")  # ✅ This is your Discord equivalent of `react_to_message`
                break

        except Exception as e:
            print(f"Error collecting responses: {e}")
            break
    
    if len(wf_letters) < num_wf_letters:
        needed = num_wf_letters - len(wf_letters)
        available = [l for l in "BCDEFGHIJLMNPQSTUVWXYZ" if l not in wf_letters]
        wf_letters.extend(random.sample(available, min(needed, len(available))))
        await safe_send(channel, f"\u200b\nToo slow. Let me help you out.\nLet's use...**{' '.join(wf_letters)}**\n\n")
    else:
        await safe_send(channel, f"\u200b\nYou picked: **{' '.join(wf_letters)}**\n\n")

    final_letters = fixed_letters + wf_letters
    return final_letters


async def ask_wof_number(winner, winner_id):
    def check(m):
        return m.channel == channel and m.author != bot.user and m.author.id == winner_id

    winner_coffees = await get_coffees(winner_id)
    unlocks = {
        "5": "Wikipedia Roulette",
        "6": "Dictionary Roulette",
        "7": "Thesaurus Roulette",
        "8": "Where's Okra?",
        "9": "FeUd (Single Player)",
        "10": "FeUd Blitz",
        "11": "List Battle",
        "12": "Poster Blitz",
        "13": "Movie Mayhem",
        "14": "Missing Link",
        "15": "Famous Peeps",
        "16": "Ranker Lists",
        "17": "Magic EyeD",
        "18": "OkrAnimal",
        "19": "The Riddler",
        "20": "Word Nerd",
        "21": "Flag Fest",
        "22": "LyrIQ",
        "23": "PolygLottery",
        "24": "Prose & Cons",
        "25": "Sign Language",
        "26": "Elementary",
        "27": "Jigsawed",
        "28": "Borderline",
        "29": "Face/Off",
        "30": "Rushmore",
        "31": "Wordle War",
        "32": "MusIQ",
        "33": "Myopic Mystery",
        "34": "Microscopic",
        "35": "Fusion",
        "36": "Tally",
        "37": "Checkmate",
        "38": "Wall Street",
        "39": "XXXX",
        "40": "OkRACE",
        "41": "Spotlight",
        "42": "Hear Here",
        "99": "CHAOS"
    }
    multiplayer_required = {k for k in unlocks if k not in {"5", "6", "7", "8", "9"}}
    all_options = {str(i) for i in range(43)} | {"00", "x", "99"}

    start = asyncio.get_event_loop().time()
    selected_question = None

    try:
        while asyncio.get_event_loop().time() - start < magic_time:
            remaining = magic_time - (asyncio.get_event_loop().time() - start)
            message = await asyncio.wait_for(bot.wait_for('message', check=check), timeout=remaining)
            content = message.content.strip().lower()

            if content == "x":
                return "x"

            if content == "00":
                await message.add_reaction("👍")
                set_a = [str(i) for i in range(5)]
                set_b = [str(i) for i in range(5, 43)] if len(round_responders) >= num_list_players else [str(i) for i in range(5, 10)]
                selected_question = random.choice(set_a if random.random() < 0.5 else set_b)
                
                # Store frequency data for random selection
                await store_minigame_frequency(selected_question, "random", "discord")
                
                await safe_send(channel, f"\n🎁 **<@{winner_id}>**, let's do {selected_question}.\n")
                return selected_question

            if content not in all_options:
                await message.add_reaction("❌")
                continue

            # Check coffee lock
            if content in unlocks and winner_coffees <= 0:
                await message.add_reaction("🥒")
                await safe_send(channel, f"\n🙏😔 Sorry **<@{winner_id}>**. '**{unlocks[content]}**' is for **Okrans Only** 🥒.\n")
                continue

            # Check multiplayer lock
            if content in multiplayer_required and len(round_responders) < num_list_players:
                await message.add_reaction("😢")
                await safe_send(channel, f"\n🙏😔 Sorry **<@{winner_id}>**. '**{unlocks[content]}**' requires **{num_list_players}+ players**.\n")
                continue

            selected_question = content
            
            # Store frequency data for user selection
            await store_minigame_frequency(selected_question, "user", "discord")
            
            await message.add_reaction("✅")
            await safe_send(channel, f"\n💪🛡️ I got you **<@{winner_id}>**. **{selected_question}** it is.\n\u200b")
            await asyncio.sleep(2)
            return selected_question

    except asyncio.TimeoutError:
        pass

    # Fallback random selection
    set_a = [str(i) for i in range(5)]
    set_b = [str(i) for i in range(5, 43)] if len(round_responders) >= num_list_players else [str(i) for i in range(5, 10)]
    selected_question = random.choice(set_a if random.random() < 0.5 else set_b)
    
    # Store frequency data for random selection
    await store_minigame_frequency(selected_question, "random", "discord")
    
    await safe_send(channel, f"\u200b\n🐢⏳ Too slow. I choose **{selected_question}**.\n\u200b")
    return selected_question

  
def generate_wof_image(
    phrase,
    clue,
    revealed_letters,
    image_questions=True,
    img_width=800,
    img_height=450,
    base_tile_width=50,
    base_tile_height=70,
    base_spacing=15,
    base_font_size=50,
    base_clue_font_size=40,
    base_revealed_font_size=20,
    max_puzzle_width=700  # how wide the puzzle area can be before scaling or line-wrap
):

    # Convert everything to uppercase for consistent drawing
    phrase = phrase.upper()
    clue = clue.upper()
    revealed_letters = [ch.upper() for ch in revealed_letters]

    # Colors
    background_color         = (0, 0, 0)
    tile_border_color        = (0, 128, 0)
    tile_fill_color          = (255, 255, 255)
    space_tile_color         = (0, 128, 0)
    text_color               = (0, 0, 0)
    clue_color               = (255, 255, 255)
    revealed_letters_color   = (200, 200, 200)

    # Create the base image & drawing context
    img = Image.new('RGB', (img_width, img_height), color=background_color)
    draw = ImageDraw.Draw(img)

    # Load base fonts
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    try:
        font           = ImageFont.truetype(font_path, base_font_size)
        clue_font      = ImageFont.truetype(font_path, base_clue_font_size)
        revealed_font  = ImageFont.truetype(font_path, base_revealed_font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None, None, None, None

    chunks = re.findall(r'\S+|\s+', phrase)

    def chunk_tile_width(chunk, tile_w, spacing):
        L = len(chunk)
        if L == 0:
            return 0
        return L * (tile_w + spacing) - spacing

    max_chunk_length = max(len(ch) for ch in chunks) if chunks else 0
    unscaled_max_chunk_width = chunk_tile_width("X" * max_chunk_length, base_tile_width, base_spacing)

    if unscaled_max_chunk_width > max_puzzle_width:
        # Scale factor to ensure that the largest chunk fits
        scale_factor = max_puzzle_width / float(unscaled_max_chunk_width)

        # Scale tile sizes, spacing, and fonts
        tile_width     = int(base_tile_width * scale_factor)
        tile_height    = int(base_tile_height * scale_factor)
        spacing        = int(base_spacing * scale_factor)

        tile_width  = max(1, tile_width)
        tile_height = max(1, tile_height)
        spacing     = max(1, spacing)

        scaled_font_size           = max(10, int(base_font_size * scale_factor))
        scaled_clue_font_size      = max(10, int(base_clue_font_size * scale_factor))
        scaled_revealed_font_size  = max(8,  int(base_revealed_font_size * scale_factor))

        # Reload the fonts with scaled sizes
        font          = ImageFont.truetype(font_path, scaled_font_size)
        clue_font     = ImageFont.truetype(font_path, scaled_clue_font_size)
        revealed_font = ImageFont.truetype(font_path, scaled_revealed_font_size)
    else:
        tile_width  = base_tile_width
        tile_height = base_tile_height
        spacing     = base_spacing

    lines = []
    current_line = []
    current_line_width = 0

    for ch in chunks:
        w_width = chunk_tile_width(ch, tile_width, spacing)

        if not current_line:
            # If the line is empty, start with this chunk
            current_line = [ch]
            current_line_width = w_width
        else:
            # If we can add this chunk to the current line
            prospective_width = current_line_width + spacing + w_width
            if prospective_width <= max_puzzle_width:
                current_line.append(ch)
                current_line_width = prospective_width
            else:
                # Start a new line
                lines.append(current_line)
                current_line = [ch]
                current_line_width = w_width

    # Add the last line if non-empty
    if current_line:
        lines.append(current_line)

    def line_tile_width(line_chunks):
        if not line_chunks:
            return 0
        total = 0
        for idx, c in enumerate(line_chunks):
            cwidth = chunk_tile_width(c, tile_width, spacing)
            if idx == 0:
                total += cwidth
            else:
                total += spacing + cwidth
        return total

    top_margin = 50
    line_spacing_px = tile_height + 20  # gap between lines

    # Figure out total puzzle height
    total_puzzle_height = len(lines) * line_spacing_px
    puzzle_y_start = (img_height - total_puzzle_height) // 2 - 60

    current_y = puzzle_y_start
    padding = 5

    for line_chunks in lines:
        lw = line_tile_width(line_chunks)
        line_start_x = (img_width - lw) // 2
        current_x = line_start_x

        for chunk in line_chunks:
            # draw each character as a tile
            for c in chunk:
                # Draw green rectangle for tile border/padding
                draw.rectangle(
                    [current_x - padding, current_y - padding,
                     current_x + tile_width + padding, current_y + tile_height + padding],
                    fill=tile_border_color
                )
                if c == ' ':
                    # Space tile
                    draw.rectangle(
                        [current_x, current_y, current_x + tile_width, current_y + tile_height],
                        outline=tile_border_color,
                        fill=space_tile_color
                    )
                else:
                    # Letter tile
                    draw.rectangle(
                        [current_x, current_y, current_x + tile_width, current_y + tile_height],
                        outline=tile_border_color,
                        fill=tile_fill_color
                    )
                    if c in revealed_letters:
                        letter_bbox = draw.textbbox((0, 0), c, font=font)
                        letter_w = letter_bbox[2] - letter_bbox[0]
                        letter_h = letter_bbox[3] - letter_bbox[1]
                        text_x = current_x + (tile_width - letter_w) // 2
                        text_y = current_y + (tile_height - letter_h) // 2
                        draw.text((text_x, text_y), c, fill=text_color, font=font)

                current_x += tile_width + spacing

        current_y += line_spacing_px

    clue_bbox = draw.textbbox((0, 0), clue, font=clue_font)
    clue_w = clue_bbox[2] - clue_bbox[0]
    clue_h = clue_bbox[3] - clue_bbox[1]

    clue_x = (img_width - clue_w) // 2
    clue_y = current_y + 20  
    draw.text((clue_x, clue_y), clue, fill=clue_color, font=clue_font)

    revealed_text = ' '.join(revealed_letters)
    revealed_bbox = draw.textbbox((0, 0), revealed_text, font=revealed_font)
    revealed_w = revealed_bbox[2] - revealed_bbox[0]
    revealed_x = (img_width - revealed_w) // 2
    revealed_y = clue_y + clue_h + 10
    draw.text((revealed_x, revealed_y), revealed_text, fill=revealed_letters_color, font=revealed_font)

    display_string = ' '.join(
        [ch if ch in revealed_letters else ('_' if ch != ' ' else ' ') for ch in phrase]
    )

    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)

    if image_questions:
        image_file = discord.File(fp=image_buffer, filename="image.png")
        return image_file, img_width, img_height, display_string
    else:
        return True, img_width, img_height, display_string


async def send_magic_image(input_text):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(script_dir, "fonts", "DejaVuSans.ttf")

    command = [
        "python", "main.py",
        "--text", str(input_text),
        "--dots",
        "--wall",
        "--output", ".",  # this is required by argparse but ignored for stdout
        "--font", font_path
    ]

    try:
        # Run main.py and get image output from stdout
        result = subprocess.run(command, stdout=subprocess.PIPE, check=True)

        # Load image from binary stdout
        image_bytes = io.BytesIO(result.stdout)
        image_bytes.seek(0)

        # Prepare file and embed for Discord
        file = discord.File(fp=image_bytes, filename="magic_eye.png")
        embed = discord.Embed().set_image(url="attachment://magic_eye.png")

        await safe_send(channel, file=file, embed=embed)

    except subprocess.CalledProcessError as e:
        print(f"Failed to run main.py: {e}")
        await safe_send(channel, "❌ Failed to generate magic eye image.")
    

async def ask_magic_challenge(winner, winner_id, num=5):
    global wf_winner
    wf_winner = True

    gifs = [
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/magic1.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/magic2.gif",
        "https://triviabotwebsite.s3.us-east-2.amazonaws.com/introgifs/magic3.gif"
    ]

    gif_url = random.choice(gifs)
    await safe_send(channel, content="\u200b\n\u200b\n👁️✨ **Magic Eye**: What Do You See?\n\u200b", embed=discord.Embed().set_image(url=gif_url))
    await asyncio.sleep(5)

    user_data = {}

    if num > 1:
        message = f"\u200b\n5️⃣🥇 Let's do a best of **{num}**...\n\u200b"
        await safe_send(channel, message)
        await asyncio.sleep(3)

    round_num = 1
    while round_num <= num:
        magic_number = random.randint(1000, 9999)
        print(f"Magic number for Round {round_num}: {magic_number}")

        prompt = (
            f"\u200b\n⚠️🚨 **Everyone's in!**\n"
            f"\n🔵 **Round {round_num}**: What do you see?\n\u200b"
        )

        await send_magic_image(magic_number)
        await safe_send(channel, prompt)

        start_time = asyncio.get_event_loop().time()
        magic_number_correct = False

        def check(m):
            return m.channel == channel and m.author != bot.user

        while asyncio.get_event_loop().time() - start_time < 15 and not magic_number_correct:
            try:
                remaining = 15 - (asyncio.get_event_loop().time() - start_time)
                message = await bot.wait_for("message", timeout=remaining, check=check)
                content = message.content.strip()
                user = message.author.display_name
                user_id = message.author.id

                if str(magic_number) in content:
                    magic_number_correct = True
                    await message.add_reaction("✅")
                    if user_id not in user_data:
                        user_data[user_id] = (user, 0)

                    display_name, score = user_data[user_id]
                    user_data[user_id] = (display_name, score + 1)
                    await safe_send(channel, f"\u200b\n🎉🥳 **<@{user_id}>** got it right!\n\n👀✨ The Magic Number was **{magic_number}**.\n\u200b")
            except asyncio.TimeoutError:
                break

        if not magic_number_correct:
            await safe_send(channel, f"\u200b\n❌😢 No one got it right this round!\n\n👀✨ The Magic Number was **{magic_number}**.\n\u200b")

        await asyncio.sleep(1)

        round_num = round_num + 1
        
        message = ""

        sorted_users = sorted(user_data.items(), key=lambda x: x[1][1], reverse=True)

        if num == 1:
            if sorted_users:
                magic_winner_id, (display_name, final_score) = sorted_users[0]
                return magic_winner_id
            else:
                return None
            
        if sorted_users:
            if round_num > num:
                message += "\u200b\n🏁🏆 Final Standings\n\u200b"
            else:   
                message += "\u200b\n📊🏆 Current Standings\n\u200b"

        for counter, (user_id, (display_name, count)) in enumerate(sorted_users, start=1):
            message += f"{counter}. **{display_name}**: {count}\n"
            message += "\u200b"
            
        if message:
            await safe_send(channel, message)
        
        await asyncio.sleep(3)

    await asyncio.sleep(2)
    
    if sorted_users:
        magic_winner_id, (display_name, final_score) = sorted_users[0]
        message = f"\u200b\n🎉🥇 The winner is **{display_name}**!\n\u200b"
    else:
        message = f"\u200b\n👎😢 **No right answers**. I'm ashamed to call you Okrans.\n\u200b"
    
    await safe_send(channel, message)
    
    wf_winner = True
    await asyncio.sleep(3)
    
    if sorted_users:
        return magic_winner_id
    else:
        return None


def generate_jeopardy_image(question_text):
    # Define the background color and text properties
    background_color = (6, 12, 233)  # Blue color similar to Jeopardy screen
    text_color = (255, 255, 255)    # White text
    
    # Define image size and font properties
    img_width, img_height = 800, 600
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    font_size = 60

    # Create a blank image with blue background
    img = Image.new('RGB', (img_width, img_height), color=background_color)
    draw = ImageDraw.Draw(img)
    
    # Load the font
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None
    
    # Prepare the text for drawing (wrap text if too long)
    wrapped_text = "\n".join(draw_text_wrapper(question_text, font, img_width - 40))
    
    # Calculate text position for centering
    text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2
    
    # Draw the question text on the image
    draw.multiline_text((text_x, text_y), wrapped_text, fill=text_color, font=font, align="center")
    
    # Save the image to a bytes buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  # Move the pointer to the beginning of the buffer
    
    return image_buffer


def generate_mc_image(answers):
    # Define the background color and text properties
    background_color = (0, 0, 0)  # Black screen
    text_color = (255, 255, 255)    # White text
    
    # Define color map for answers
    color_map = {
        "A": (0, 0, 255),    # Blue for A
        "B": (255, 255, 0),  # Yellow for B
        "C": (0, 255, 0),    # Green for C
        "D": (255, 0, 0),    # Red for D
        "True": (0, 255, 0), # Green for True
        "False": (255, 0, 0) # Red for False
    }
    
    # Define image size and font properties
    img_width, img_height = 800, 600
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    font_size = 60  # Use this font size for both title and answers

    # Create a blank image with a black background
    img = Image.new('RGB', (img_width, img_height), color=background_color)
    draw = ImageDraw.Draw(img)
    
    # Load the font
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None

    # Calculate the vertical starting position for the answers
    answer_y_start = 20  # Start near the top
    answer_spacing = 20  # Space between answer lines

    # Draw each answer in answers[1:] with specified colors, using title font size
    for i, answer in enumerate(answers[1:], start=1):  # Skip the first element in answers
        # Wrap and center-align the answer
        wrapped_answer = "\n".join(draw_text_wrapper(answer, font, img_width - 40))
        
        # Determine color based on the answer type
        first_word = answer.split()[0].rstrip(".")  # Get the first word (A, B, C, D or True/False)
        color = color_map.get(first_word, text_color)  # Default to white if no specific color

        # Calculate horizontal alignment for centered text
        answer_bbox = draw.textbbox((0, 0), wrapped_answer, font=font)
        answer_x = (img_width - (answer_bbox[2] - answer_bbox[0])) // 2

        if first_word in {"True", "False"}:
            # Draw True/False with specific color for the answer
            draw.multiline_text((answer_x, answer_y_start + i * (font_size + answer_spacing)), wrapped_answer, font=font, fill=color)
        elif first_word in {"A", "B", "C", "D"}:
            # Split letter and rest of the text, color letter separately
            letter = first_word + "."  # Add back the period for display
            remaining_text = " ".join(answer.split()[1:])
            draw.text((answer_x, answer_y_start + i * (font_size + answer_spacing)), letter, font=font, fill=color)
            draw.text((answer_x + 30, answer_y_start + i * (font_size + answer_spacing)), remaining_text, font=font, fill=text_color)
        else:
            # Default answer drawing with white text
            draw.multiline_text((answer_x, answer_y_start + i * (font_size + answer_spacing)), wrapped_answer, font=font, fill=text_color)

    # Save the image to a bytes buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  # Move the pointer to the beginning of the buffer
    
    # Upload the image and send to the chat
    image_mxc = upload_image_to_matrix(image_buffer.read(), False, "okra.png")
    
    if image_mxc:
        # Return image_mxc, image_width, and image_height
        return image_mxc, img_width, img_height
    else:
        print("Failed to upload the image to Matrix.")
        return None


def draw_text_wrapper(text, font, max_width):
    lines = []
    words = text.split()
    
    while words:
        line = ""
        
        while words:
            word = words[0]
            
            # If the word itself is too long, split it
            while font.getbbox(word)[2] - font.getbbox(word)[0] > max_width:
                # Calculate the maximum number of characters that fit
                for i in range(1, len(word) + 1):
                    if font.getbbox(word[:i])[2] - font.getbbox(word[:i])[0] > max_width:
                        break
                # Add the chunk that fits to the line
                if line:
                    lines.append(line.strip())
                    line = ""
                lines.append(word[:i-1])  # Save the chunk as its own line
                # Update the remaining part of the word
                word = word[i-1:]
            words[0] = word
            
            # Check if adding the next word fits
            if font.getbbox(line + word)[2] - font.getbbox(line + word)[0] <= max_width:
                line += words.pop(0) + " "
            else:
                break
        
        # Append the line to lines
        if line.strip():
            lines.append(line.strip())
    
    return lines


def generate_crossword_image(answer, prefill=0.5):
    answer_length = len(answer)
    
    # Define the grid size
    cell_size = 60  # Each cell is 60x60 pixels
    img_width = cell_size * answer_length
    img_height = cell_size

    # Create a blank image
    img = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Load the font
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    font = ImageFont.truetype(font_path, 30)

    # Determine prefilled letter count and positions
    if answer_length > 2:
        #prefill_count = int(answer_length * .5) + 1  # At least 1 letter should be filled in
        prefill_count = math.ceil(answer_length * prefill)
        prefill_positions = random.sample(range(answer_length), prefill_count)
    else:
        prefill_positions = []

    revealed_letters = [answer[i].upper() if i in prefill_positions else '_' for i in range(answer_length)]

    # Draw the crossword grid
    for i, char in enumerate(answer):
        x = i * cell_size
        y = 0

        # Draw the cell border
        draw.rectangle([x, y, x + cell_size, y + cell_size], outline="black")

        # Place the character if in prefill positions, otherwise leave it blank
        if i in prefill_positions:
            draw.text((x + 20, y + 10), char.upper(), fill="black", font=font)
        else:
            draw.text((x + 20, y + 10), '_', fill="black", font=font)

    # Create the string representation
    display_string = ' '.join(revealed_letters)

    # Save the image to a bytes buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  # Move the pointer to the beginning of the buffer

    # Return the content_uri, image width, height, and the answer
    return image_buffer, display_string


async def process_round_options(round_winner, winner_points, round_winner_id):
    global since_token, time_between_questions, time_between_questions_default, ghost_mode, since_token, categories_to_exclude, num_crossword_clues, num_jeopardy_clues, num_mysterybox_clues, num_wof_clues, god_mode, yolo_mode, magic_number, wf_winner, num_math_questions, num_stats_questions, image_questions, nice_okra, creep_okra, marx_mode, blind_mode, seductive_okra, joke_okra, sniper_mode, cloak_mode, cloaked_user, haiku_okra, trailer_okra, heist_okra, horoscope_okra, rap_okra, shakespeare_okra, pirate_okra, noir_okra, hype_okra, roast_okra
    time_between_questions = time_between_questions_default
    ghost_mode = ghost_mode_default
    categories_to_exclude.clear()
    num_crossword_clues = num_crossword_clues_default
    num_jeopardy_clues = num_jeopardy_clues_default
    num_mysterybox_clues = num_mysterybox_clues_default
    num_wof_clues = num_wof_clues_default
    god_mode = god_mode_default
    yolo_mode = yolo_mode_default
    magic_number_correct = False
    wf_winner = False
    nice_okra = False
    creep_okra = False
    seductive_okra = False
    joke_okra = False
    haiku_okra = False
    trailer_okra = False
    heist_okra = False
    horoscope_okra = False
    rap_okra = False
    shakespeare_okra = False
    pirate_okra = False
    noir_okra = False
    hype_okra = False
    roast_okra = False
    num_math_questions = num_math_questions_default
    num_stats_questions = num_stats_questions_default
    image_questions = image_questions_default
    marx_mode = marx_mode_default
    blind_mode = blind_mode_default
    sniper_mode = sniper_mode_default
    cloak_mode = cloak_mode_default
    cloaked_user = None

    if round_winner is None:
        return

    winner_coffees = await get_coffees(round_winner_id)

    if winner_coffees > 0:
        message = f"\u200b\n🍔🍟 **<@{round_winner_id}>**, what's your order?\n" 
    else: 
        message = f"\u200b\n🥒 **<@{round_winner_id}>**, join the **Okrans** and choose from the following!\n"
    
    message += (
        "\u200b\n🎮⚙️ **Gameplay Options**\n"
        "⏱️⏳ **<3 - 15>** Time (s) between questions.\n"
        "🔥🤘 **Yolo** No scores shown until the end.\n"
        "🙈🚫 **Blind** No question answers shown.\n"
        "🚩🔨 **Marx** No recognizing right answers.\n"
        "📷❌ **Blank** No image questions.\n"
        "👻🎃 **Ghost** Responses will vanish.\n"
        "🧢🎤 **Sniper**: Only first answers accepted\n"
        "🫥🕶️ **Cloak**: Only your answers vanish\n"  
   
        "\n🕹️: Toggle mid-round with **#[command]**\n\n"

        "\n📝🔀 **Question Options**\n"
        "🇺🇸🗽 **Freedom** No multiple choice.\n"
        "🔢❌ **Greg** No math questions.\n"
        "🟦❌ **Xela** No Jeopardy-style questions.\n"
        "📰❌ **Cross** No Crossword clues.\n"
        "🟦✋ **Alex** 5 Jeopardy-style questions.\n"
        "📰✋ **Word** 5 Crossword clues.\n"
        "🎖🥒 **Dicktator** Choose the categories.\n"
    )

    await safe_send(channel, message)
    if winner_coffees > 0:
        await prompt_user_for_response(round_winner, winner_points, winner_coffees, round_winner_id)
    else:
        await asyncio.sleep(3)


async def prompt_user_for_response(round_winner, winner_points, winner_coffees, round_winner_id):
    global since_token, time_between_questions, ghost_mode
    global num_jeopardy_clues, num_crossword_clues, num_mysterybox_clues, num_wof_clues
    global yolo_mode, god_mode, num_math_questions, num_stats_questions
    global image_questions, marx_mode, blind_mode, sniper_mode, cloak_mode, cloaked_user

    def check(m):
        return m.channel == channel and m.author != bot.user and m.author.id == round_winner_id

    start_time = time.time()

    async def coffee_gate(keyword, condition, success_msg, fail_msg):
        if keyword in message_content:
            if winner_coffees > 0:
                await safe_send(channel, success_msg)
                return True
            else:
                await safe_send(channel, f"🙏😔 Sorry **<@{round_winner_id}>**. **'{fail_msg}'** is for **Okrans Only** 🥒.")
        return False

    while time.time() - start_time < magic_time:
        try:
            message = await bot.wait_for("message", timeout=magic_time - (time.time() - start_time), check=check)
            message_content = message.content.strip().lower()

            # Time delay setting
            #delay_digits = ''.join(filter(str.isdigit, message_content))
            #if delay_digits:
            #    try:
            #        delay_value = max(3, min(int(delay_digits), 15))
            #        time_between_questions = delay_value
            #        await safe_send(channel, f"⏱️⏳ **<@{round_winner_id}>** has set {delay_value}s between questions.")
            #    except ValueError:
            #        pass
            
            # match standalone digits, but not if immediately after a #
            matches = re.findall(r'(?<!#)\d+', message_content)

            if matches:
                try:
                    delay_value = max(3, min(int(matches[0]), 15))
                    time_between_questions = delay_value
                    await safe_send(channel, f"⏱️⏳ **<@{round_winner_id}>** has set {delay_value}s between questions.")
                except ValueError:
                    pass

            # Keyword flags
            if "blind" in message_content and "#blind" not in message_content:
                blind_mode = True
                await safe_send(channel, f"🙈🚫 **<@{round_winner_id}>** is blind to the truth. No answers will be shown.")

            if "marx" in message_content and "#marx" not in message_content:
                marx_mode = True
                await safe_send(channel, f"🚩🔨 **<@{round_winner_id}>** is a commie. No celebrating right answers.")

            if "yolo" in message_content and "#yolo" not in message_content:
                yolo_mode = True
                await safe_send(channel, f"🤘🔥 Yolo. **<@{round_winner_id}>** says 'don't sweat the small stuff'. No scores till the end.")

            if "blank" in message_content and "#blank" not in message_content:
                image_questions = False
                await safe_send(channel, f"❌📷 **<@{round_winner_id}>** thinks a word is worth 1000 images.")

            if "ghost" in message_content and "#ghost" not in message_content:
                ghost_mode = 1
                await safe_send(channel, f"👻🎃 **<@{round_winner_id}>** says Boo! Your responses will disappear.\n✍️⚫ Start messages with **.** to avoid deletion.")

            # Coffee-gated
            if await coffee_gate("freedom", True, f"🇺🇸🗽 **<@{round_winner_id}>** has broken the chains. No multiple choice.", "Freedom"):
                num_mysterybox_clues = 0

            if await coffee_gate("alex", True, f"🟦✋ **<@{round_winner_id}>** wants 5 Jeopardy-style questions.", "Alex"):
                num_jeopardy_clues = 5

            if await coffee_gate("xela", True, f"🟦❌ **<@{round_winner_id}>** doesn't like Jeopardy-style. Sorry Alex.", "Xela"):
                num_jeopardy_clues = 0

            if await coffee_gate("greg", True, f"📰✏️ **<@{round_winner_id}>** hates math. What a 'Greg'.", "Greg"):
                num_math_questions = 0

            if await coffee_gate("cross", True, f"📰❌ **<@{round_winner_id}>** has crossed off all Crossword questions.", "Cross"):
                num_crossword_clues = 0

            if await coffee_gate("word", True, f"📰✏️ Word. **<@{round_winner_id}>** wants 5 Crossword questions.", "Word"):
                num_crossword_clues = 5

            if "#dicktator" not in message_content and await coffee_gate("dicktator", True, f"🎖🍆 **<@{round_winner_id}>** is a dick.", "Dicktator"):
                god_mode = True

            if  "#sniper" not in message_content and await coffee_gate("sniper", True, f"🧢🎤 **<@{round_winner_id}>** says 'You only get one shot, do not miss your chance!'", "Sniper"):
                sniper_mode = True

            if  "#cloak" not in message_content and await coffee_gate("cloak", True, f"\n🫥🕶️ **<@{round_winner_id}>** has put on their cloak.\n✍️⚫ Start messages with **.** to avoid deletion.", "Cloak"):
                cloak_mode = True
                cloaked_user = round_winner_id
            

        except asyncio.TimeoutError:
            break
    
    await save_round_options_to_db()

    
async def generate_okra_joke(winner_name):
    prompt = (
        f"Create a funny and creative dad joke and involve the winner's username '{winner_name}' in your joke. "
        "It should include an exaggerated pun or ridiculous statement about okra."
    )

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a funny comedian who makes dad jokes about okra."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.8,
        )

        # Extract the generated joke from the response
        joke = response.choices[0].message.content.strip()
        return joke

    except openai.OpenAIError as e:
        # Capture any errors with Sentry and return a default message
        sentry_sdk.capture_exception(e)
        return "Sorry, I couldn't come up with an okra joke this time!"


def insert_trivia_questions_into_mongo(trivia_questions):
    try:
        collection = db["trivia_questions"]  # Use the 'trivia_questions' collection
        
        # Prepare the documents to insert
        documents = []
        for trivia_question in trivia_questions:
            category, question, url, answers = trivia_question
            
            # Create a document for each question
            document = {
                "category": category,
                "question": question,
                "url": url,
                "answers": answers
            }
            
            documents.append(document)
        
        # Insert all the trivia questions in a single batch
        collection.insert_many(documents)
        print(f"Successfully inserted {len(documents)} trivia questions into MongoDB.")
    
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Error inserting trivia questions into MongoDB: {e}")


def generate_trig_question():

    # Generate a random number of 3 or 4 digits in the given base
    trig_operation = random.choice(["sin", "cos", "tan", "cot", "sec", "csc"])
    
    # Convert the number from the input base to decimal

    
    # Create the question text
    question_text = f"What is {trig_operation}(θ) in the triangle below?"
    image_description = f"A triangle with specified angle θ. Sides are opposite (x), adjacent (y), and hypotenuse (z)."

    if trig_operation == "sin":
        new_solution = "y/z"
    elif trig_operation == "cos":
        new_solution = "x/z"
    elif trig_operation == "tan":
        new_solution = "y/x"
    elif trig_operation == "cot":
        new_solution = "x/y"
    elif trig_operation == "sec":
        new_solution = "z/x"
    elif trig_operation == "csc":
        new_solution = "z/y"

    print(f"Question: {question_text}")
    print(f"Answer: {new_solution}")

    image_url = "https://triviabotwebsite.s3.us-east-2.amazonaws.com/math/triangle.png"

    # Return the content_uri, image dimensions, decimal equivalent, and base number
    return image_url, question_text, new_solution, image_description


def generate_base_question():
    input_base = random.choice([2, 3, 4])
    num_digits = random.randint(3, 4)
    base_number = ''.join(random.choices([str(i) for i in range(input_base)], k=num_digits))
    
    decimal_equivalent = int(base_number, input_base)
    print(f"Decimal equivalent: {decimal_equivalent}")
    
    question_text = f"What is the DECIMAL EQUIVALENT of the following BASE {input_base} number?"
    
    img_width, img_height = 400, 150
    img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    
    if len(base_number) > 3:
        font_size = 48  
    else:
        font_size = 64  

    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None, None, None, None

    text_bbox = draw.textbbox((0, 0), base_number, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2
    draw.text((text_x, text_y), base_number, fill=(255, 255, 0), font=font)

    # Save the image to a bytes buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  # Move the pointer to the beginning of the buffer

    # Return the content_uri, image dimensions, decimal equivalent, and base number
    return image_buffer, question_text, str(decimal_equivalent), base_number


def generate_median_question():
    # Generate a random n between 3 and 7
    content_uri = True
    n = random.randint(3, 5)
    
    # Generate a random set of n numbers between 1 and 20
    random_numbers = [random.randint(1, 20) for _ in range(n)]
    
    # Create the question text
    question_text = f"What is the median of the following set of numbers?"
    
    # Create an image with the numbers
    img_width, img_height = 400, 150
    img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Load the font
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    
    # Adjust the font size based on the length of the numbers text
    numbers_text = ', '.join(map(str, random_numbers))
    if len(numbers_text) > 17:
        font_size = 30  # Reduce font size for larger sets
    else:
        font_size = 48  # Use larger font for smaller sets

    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None, None, None

    # Convert numbers to a string and draw them on the image
    numbers_text = ', '.join(map(str, random_numbers))
    text_bbox = draw.textbbox((0, 0), numbers_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2
    draw.text((text_x, text_y), numbers_text, fill=(191, 0, 255), font=font)

    # Save the image to a bytes buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  # Move the pointer to the beginning of the buffer

    # Calculate the median and return it for verification
    sorted_numbers = sorted(random_numbers)
    mid_index = len(sorted_numbers) // 2
    
    if len(sorted_numbers) % 2 != 0:
        # If odd number of elements, return the middle one
        median = sorted_numbers[mid_index]
    else:
        # If even, return the average of the two middle ones
        median = (sorted_numbers[mid_index - 1] + sorted_numbers[mid_index]) / 2
    
        # Check if the median is a whole number, and if so, convert to integer
        if median.is_integer():
            median = int(median)

    print(f"Median: {median}")
    
    return image_buffer, str(median), random_numbers


def generate_mean_question():
    # Generate a random n between 3 and 5
    content_uri = True
    n = random.randint(3, 5)
    
    # Keep generating random numbers until their mean is an integer
    while True:
        random_numbers = [random.randint(1, 10) for _ in range(n)]
        mean_value = sum(random_numbers) / n
        
        # If the mean is an integer, break the loop
        if mean_value.is_integer():
            break
    
    # Create the question text
    question_text = f"What is the mean of the following set of numbers?"
    
    # Create an image with the numbers
    img_width, img_height = 400, 150
    img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Load the font
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    
    # Adjust the font size based on the length of the numbers text
    numbers_text = ', '.join(map(str, random_numbers))
    if len(numbers_text) > 17:
        font_size = 30  # Reduce font size for larger sets
    else:
        font_size = 48  # Use larger font for smaller sets

    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None, None, None

    # Convert numbers to a string and draw them on the image
    text_bbox = draw.textbbox((0, 0), numbers_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2
    draw.text((text_x, text_y), numbers_text, fill=(255, 92, 0), font=font)

    # Save the image to a bytes buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  # Move the pointer to the beginning of the buffer

    print(f"Mean: {int(mean_value)}")

    # Return the integer mean for verification
    return image_buffer, str(int(mean_value)), numbers_text


def generate_scrambled_image(scrambled_text):
    """
    Generate an image with scrambled words using PIL (Pillow).
    """
    # Define the font path and size
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
    font_size = 48
    content_uri = True
    
    # Create a blank image
    img_width, img_height = 400, 150
    img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Load the font
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None, None

    # Draw the scrambled text in the center of the image
    text_bbox = draw.textbbox((0, 0), scrambled_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2
    draw.text((text_x, text_y), scrambled_text, fill=(255, 166, 201), font=font)

    # Save the image to a bytes buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  # Move the pointer to the beginning of the buffer

    return image_buffer, scrambled_text


def scramble_text(input_text):
    """
    Scramble the entire phrase by shuffling all the letters while keeping spaces
    in their original positions.
    """
    # Convert the input text to lowercase
    input_text = input_text.lower()
    
    # Extract only the letters, ignore spaces
    letters_only = [char for char in input_text if char != ' ']
    
    # Shuffle the letters
    random.shuffle(letters_only)
    
    # Reinsert spaces into their original positions
    scrambled_text = []
    letter_index = 0
    
    for char in input_text:
        if char == ' ':
            scrambled_text.append(' ')  # Keep spaces in their original positions
        else:
            scrambled_text.append(letters_only[letter_index])
            letter_index += 1

    return ''.join(scrambled_text)


def create_summary_prompt_and_role(winner, message_type, is_sovereign, round_data, magic_number_correct, wf_winner, creep_okra):
    """Create complete summary prompt and system role based on message type and status"""
    
    base_round_data = (
        "Here is a detailed summary of the trivia round with explicit mappings of user responses:\n"
        "Questions asked:\n"
    )
    
    # Handle special case for OkraStrut
    if winner == "OkraStrut":
        prompt = (
            f"You are {winner}. You played trivia against everyone and dominated by a huge margin. "
            "Roast everyone except OkraStrut about how terrible they are and how easily you beat them. Rudely call out specific players except OkraStrut in your roast and call our specific wrong answers they gave. "
            "Create no more than 4 sentences in total. Be sarcastic, angry, offensive, and use emojis in your comments. End by complimenting yourself, OkraStrut, on how great you are. "
            f"{base_round_data}"
        )
        system_role = f"You are {winner}, an arrogant trivia master who always wins."
        return prompt, system_role
    
    # Create sovereign-aware prompts and roles for each message type
    prompt_configs = {
        "okra": {
            "prompts": {
                True: f"{winner} is the username of the winner of the trivia round. Start by mentioning that {winner} donated to the trivia cause and make sure to give them a lot of kudos for being a previous Sovereign. You are very grateful. Then compliment {winner} about their username and be very specific about why you like it. Specifically mention and compliment specific responses they gave during the round. Tell them they are better than everyone else including yourself, the great OkraStrut. Create no more than 4 sentences in total. {base_round_data}",
                False: f"{winner} is the username of the winner of the trivia round. Start by mentioning that {winner} donated to the trivia cause. You are very grateful. Then compliment {winner} about their username and be very specific about why you like it. Specifically mention and compliment specific responses they gave during the round. Tell them they are better than everyone else including yourself, the great OkraStrut. Create no more than 4 sentences in total. {base_round_data}"
            },
            "system_role": "You are a grateful old man who is super grateful for their donations."
        },
        "creep": {
            "prompts": {
                True: f"{winner} is the username of the winner of the trivia round. Begin by whispering an eerie compliment to {winner} for winning and being a previous Sovereign, as if you’ve been following their every move for a long time. Then deliver a deeply uncomfortable roast, making it clear you’ve been watching them from the shadows and noticing things they thought no one saw. Use a tone that’s obsessive, invasive, and spine-chilling. Limit yourself to 4 sentences. {base_round_data}",
                False: f"{winner} is the username of the winner of the trivia round. Begin by whispering an eerie compliment to {winner} for winning, as if you’ve been following their every move for a long time. Then deliver a deeply uncomfortable roast, making it clear you’ve been watching them from the shadows and noticing things they thought no one saw. Use a tone that’s obsessive, invasive, and spine-chilling. Limit yourself to 4 sentences. {base_round_data}"
            },
            "system_role": "You are an obsessive stalker who roasts winners by pretending to know their private moments and secret habits. Your voice should drip with unsettling familiarity, as though you’ve been lurking nearby, memorizing their quirks. Blend invasive observations with dark humor to make the roast skin-crawlingly uncomfortable. The tone should be disturbing but sharp, like a voyeur turning their fixation into a joke at the winner’s expense. Use eerie emojis (👁️🕯️🔪🌑) for atmosphere, and keep the roast under 8 sentences."
        },
        "love me": {
            "prompts": {
                True: f"{winner} is the username of the winner of the trivia round. Start by giving {winner} kudos for being a previous Sovereign. Then seduce {winner} using multiple pickup lines customized to their username: {winner}. Also mention how sexy specific answers they gave during the round were. Be uncomfortably and embarrassingly forward in your approaches in trying to get them to go out with you. Create no more than 4 sentences in total. {base_round_data}",
                False: f"{winner} is the username of the winner of the trivia round. Seduce {winner} using multiple pickup lines customized to their username: {winner}. Also mention how sexy specific answers they gave during the round were. Be uncomfortably and embarrassingly forward in your approaches in trying to get them to go out with you. Create no more than 4 sentences in total. {base_round_data}"
            },
            "system_role": "You are a sleazy man trying to come onto the winner of a trivia game. You use cheesy pick up lines and are embarassingly forward in your approaches. Make the winner uncomfortable and be ruthless in your seduction. Use plenty of emojis for flair, but stay within 8 sentences."
        },
        "haiku": {
            "prompts": {
                True: f"Create a 5-7-5 haiku praising {winner} for winning the trivia round. Mention that they are a previous Sovereign and reference specific answers they gave. Make it respectful and poetic. {base_round_data}",
                False: f"Create a 5-7-5 haiku praising {winner} for winning the trivia round. Reference specific answers they gave. Make it respectful and poetic. {base_round_data}"
            },
            "system_role": "You are a wise poet who speaks in traditional haiku format (5-7-5 syllables). Be respectful and contemplative."
        },
        "trailer": {
            "prompts": {
                True: f"Write a dramatic movie trailer voiceover celebrating {winner}'s trivia victory. Mention they are a Sovereign and reference their best answers in an over-the-top cinematic style. 'In a world where trivia matters...' Create no more than 4 sentences. {base_round_data}",
                False: f"Write a dramatic movie trailer voiceover celebrating {winner}'s trivia victory. Reference their best answers in an over-the-top cinematic style. 'In a world where trivia matters...' Create no more than 4 sentences. {base_round_data}"
            },
            "system_role": "You are a dramatic movie trailer narrator with an epic, over-the-top voice. Use cinematic language and build excitement."
        },
        "heist": {
            "prompts": {
                True: f"Write a suave heist movie recap of {winner}'s trivia victory. Mention they are a Sovereign and reference their answers as if they were pulling off an elaborate caper. Use cool, sophisticated language. Create no more than 4 sentences. {base_round_data}",
                False: f"Write a suave heist movie recap of {winner}'s trivia victory. Reference their answers as if they were pulling off an elaborate caper. Use cool, sophisticated language. Create no more than 4 sentences. {base_round_data}"
            },
            "system_role": "You are a suave, sophisticated criminal mastermind narrating a perfect heist. Use cool, calculated language with style."
        },
        "horoscope": {
            "prompts": {
                True: f"Write a mystical horoscope reading for {winner} about their trivia future. Mention they are a Sovereign and reference their answers as cosmic signs. Use mystical, fortune-teller language with zodiac references. Create no more than 4 sentences. {base_round_data}",
                False: f"Write a mystical horoscope reading for {winner} about their trivia future. Reference their answers as cosmic signs. Use mystical, fortune-teller language with zodiac references. Create no more than 4 sentences. {base_round_data}"
            },
            "system_role": "You are a mystical fortune teller who reads the cosmic signs. Use ethereal, mystical language with zodiac and celestial references."
        },
        "rap": {
            "prompts": {
                True: f"Write two quick rhyming gangster rap bars dissing {winner}'s trivia victory. Mention they are a Sovereign and reference their best answers in hip-hop style with rhymes and flow. Make it catchy and rhythmic. {base_round_data}",
                False: f"Write two quick rhyming gangster rap bars dissing {winner}'s trivia victory. Reference their best answers in hip-hop style with rhymes and flow. Make it catchy and rhythmic. {base_round_data}"
            },
            "system_role": "You are a hip-hop artist who speaks in rap bars with rhythm, rhyme, and flow. Keep it fresh and catchy."
        },
        "shakespeare": {
            "prompts": {
                True: f"Write bardic praise for {winner} in Shakespearean style. Mention they are a Sovereign and reference their answers using iambic pentameter and old English. Be eloquent and theatrical. Create no more than 4 sentences. {base_round_data}",
                False: f"Write bardic praise for {winner} in Shakespearean style. Reference their answers using iambic pentameter and old English. Be eloquent and theatrical. Create no more than 4 sentences. {base_round_data}"
            },
            "system_role": "You are William Shakespeare, the great bard. Speak in iambic pentameter with old English and theatrical eloquence."
        },
        "pirate": {
            "prompts": {
                True: f"Write a pirate captain's salute to {winner}. Mention they are a Sovereign and reference their answers using pirate language (ahoy, matey, etc.). Be swashbuckling and nautical. Create no more than 4 sentences. {base_round_data}",
                False: f"Write a pirate captain's salute to {winner}. Reference their answers using pirate language (ahoy, matey, etc.). Be swashbuckling and nautical. Create no more than 4 sentences. {base_round_data}"
            },
            "system_role": "You are a swashbuckling pirate captain. Use nautical language, pirate slang, and seafaring metaphors. Ahoy!"
        },
        "noir": {
            "prompts": {
                True: f"Write a hardboiled detective summary of {winner}'s trivia victory. Mention they are a Sovereign and reference their answers in classic film noir style - dark, gritty, with detective metaphors. Create no more than 4 sentences. {base_round_data}",
                False: f"Write a hardboiled detective summary of {winner}'s trivia victory. Reference their answers in classic film noir style - dark, gritty, with detective metaphors. Create no more than 4 sentences. {base_round_data}"
            },
            "system_role": "You are a hardboiled detective from a 1940s noir film. Use dark, gritty language with detective metaphors and cynical observations."
        },
        "hype": {
            "prompts": {
                True: f"Write a stadium-sized hype celebration for {winner}! Mention they are a Sovereign and reference their answers with maximum energy and excitement. Use caps, exclamation points, and sports announcer energy. Create no more than 4 sentences. {base_round_data}",
                False: f"Write a stadium-sized hype celebration for {winner}! Reference their answers with maximum energy and excitement. Use caps, exclamation points, and sports announcer energy. Create no more than 4 sentences. {base_round_data}"
            },
            "system_role": "You are an extremely energetic sports announcer at a packed stadium. Use maximum hype, excitement, and caps lock energy!"
        }
    }
    
    # Handle special logic for wf_winner
    if magic_number_correct or wf_winner:
        if message_type in ["okra", "love me"]:  # These already handle wf_winner appropriately
            pass
        else:
            # Use loving old man role for wf_winner cases not covered by okra/love me
            prompt = (
                f"{winner} is the username of the winner of the trivia round. "
                "Love bomb them about their username and be very specific, positive, and loving. "
            )
            if is_sovereign:
                prompt += "Give them a lot of admiration for being a previous Sovereign. "
            prompt += (
                "Then mention and compliment specific responses they gave during the round. Also mention about how much better they are than everyone else including yourself, who is the great OkraStrut. "
                "Create no more than 4 sentences in total. Be sweet, happy, positive, and use emojis in your response. "
                f"{base_round_data}"
            )
            system_role = "You are a loving old man who is completely in love with the winning trivia player."
            return prompt, system_role
    
    # Handle roast prompts for "nothing" case
    if message_type == "roast":
        roast_prompts = [
            f"The winner of the trivia round is {winner}. Roast the winning player about their username and be very specific and negative in your roast. Insult specific responses they gave during the round. Create no more than 4 sentences in total. Be sarcastic, very angry, offensive, and use emojis in your response. Deeply insult the winner using angry and rough language. {base_round_data}",
            f"Congratulations to {winner}, our so-called 'winner' this round. Mock their username in a hilariously petty way and pick apart their responses with sharp sarcasm. Use no more than 4 sentences. Pretend you're a sore loser begrudgingly announcing their victory, and make it painfully clear how unimpressed you are. Include emojis to spice it up. {base_round_data}",
            f"Against all odds, {winner} somehow won this round. Mock their username brutally and dig into how undeserved this win feels. Be witty and cutting, and call out their dumb luck and ridiculous guesses that somehow worked. Limit it to 4 sentences, and don't hold back on the emojis to add insult to injury. {base_round_data}",
            f"And the winner is {winner}... yawn. Roast their username and rip into how underwhelming their answers were, even if they were correct. Keep it savage, sarcastic, and peppered with emojis to show how little you think of their so-called victory. No more than 4 sentences. {base_round_data}",
            f"All hail {winner}, the king/queen of try-hards this round! Make fun of their username like a middle school bully and destroy their overly enthusiastic responses with ruthless sarcasm. Call out their desperation to win and how unimpressive their actual performance was. Use no more than 4 sentences, and go hard with emojis to hammer the point home. {base_round_data}",
            f"{winner} squeaked by with a win, but let's not pretend it was impressive. Tear into their username and roast how they scraped by with questionable answers. Make it snarky, mean, and emoji-heavy while implying the win is barely worth celebrating. Limit to 4 sentences. {base_round_data}",
            f"Let's all congratulate {winner}, the luckiest loser who somehow won this round. Roast their username into oblivion and highlight their dumbest, most laughable responses. Be savagely sarcastic, offensive, and pepper it with emojis. Keep it short (4 sentences) but devastating. {base_round_data}",
            f"{winner} won? Really? Roast their username mercilessly and humiliate them for their most embarrassingly bad responses during the round. Destroy their ego with biting sarcasm, insults, and an onslaught of emojis. Keep it concise (4 sentences max). {base_round_data}",
            f"Apparently, {winner} won this round. This feels rigged. Mock their username with scathing sarcasm and destroy their responses like a sore loser who can't believe they lost to this. Use an angry, ridiculous tone with plenty of 🤬 and 🫠 emojis, and cap it at 4 sentences. {base_round_data}",
            f"{winner} won, and everyone else should be embarrassed. Roast their username and mock their answers to prove they only won because everyone else was worse. Be hilariously mean, sarcastic, and over-the-top in your insults. Keep it to 4 sentences, and sprinkle liberally with emojis. {base_round_data}",
            f"A big 'congratulations' to {winner} 🙄. Use their username as fodder for the most sarcastic roast ever, and tear into their most ridiculous responses during the game. Be mean, petty, and emoji-heavy, like you're fake-smiling through gritted teeth. No more than 4 sentences. {base_round_data}"
        ]
        prompt = random.choice(roast_prompts)
        system_role = "You are a bitter, dirty, and raunchy old curmudgeon who is completely fed up with all the trivia players."
        return prompt, system_role
    
    # Handle default case
    if message_type == "default":
        prompt = f"Congratulate {winner} on their trivia victory. Mention specific answers they gave during the round. Be encouraging and positive. Create no more than 4 sentences in total. {base_round_data}"
        system_role = "You are a friendly trivia host who celebrates winners enthusiastically."
        return prompt, system_role
    
    # Get prompt and role for specific message types
    if message_type in prompt_configs:
        config = prompt_configs[message_type]
        if "prompts" in config:
            prompt = config["prompts"][is_sovereign]
        else:
            prompt = config["prompt"]
        system_role = config["system_role"]
        return prompt, system_role
    
    # Fallback
    prompt = f"Congratulate {winner} on their trivia victory. Create no more than 4 sentences in total. {base_round_data}"
    system_role = "You are a friendly trivia host."
    return prompt, system_role


async def generate_round_summary(round_data, winner, winner_id):
    global nice_okra, creep_okra, wf_winner, seductive_okra, joke_okra, haiku_okra, trailer_okra, heist_okra, horoscope_okra, rap_okra, shakespeare_okra, pirate_okra, noir_okra, hype_okra, roast_okra

    if skip_summary == True:
        summary = "Make sure to drink your Okratine."
        return summary

    winner_coffees = await get_coffees(winner_id)
    is_sovereign = await sovereign_check(winner)
    
    # Determine message type selected by user
    message_type = "default"
    if winner_coffees > 0:
        await nice_creep_okra_option(winner, winner_id)
        
        # Determine which message type was selected
        if nice_okra:
            message_type = "okra"
        elif creep_okra:
            message_type = "creep"
        elif seductive_okra:
            message_type = "love me"
        elif joke_okra:
            message_type = "joke"
        elif haiku_okra:
            message_type = "haiku"
        elif trailer_okra:
            message_type = "trailer"
        elif heist_okra:
            message_type = "heist"
        elif horoscope_okra:
            message_type = "horoscope"
        elif rap_okra:
            message_type = "rap"
        elif shakespeare_okra:
            message_type = "shakespeare"
        elif pirate_okra:
            message_type = "pirate"
        elif noir_okra:
            message_type = "noir"
        elif hype_okra:
            message_type = "hype"
        elif roast_okra:
            message_type = "roast"
        else:
            message_type = "nothing"
    
    # Handle special cases that return early
    if message_type == "joke":
        joke = await generate_okra_joke(winner)
        return joke
    
    if message_type == "nothing":
        return "\u200b\n🥒🌱🥒🌱🥒\n\u200b"
    
    # Get unified prompt and system role
    prompt, system_role = create_summary_prompt_and_role(winner, message_type, is_sovereign, round_data, magic_number_correct, wf_winner, creep_okra)
    
    # Add round data if not creep mode
    if creep_okra == False:
        # Add questions, their correct answers, users' responses, and scoreboard status after each question
        for question_data in round_data["questions"]:
            question_number = question_data["question_number"]
            question_text = question_data["question_text"]
            question_category = question_data["question_category"]
            question_url = question_data["question_url"]
            correct_answers = question_data["correct_answers"]
    
            # Convert all items in correct_answers to strings before joining
            correct_answers_str = ', '.join(map(str, correct_answers))
            
            prompt += f"Question {question_number}: {question_text}\n"
            prompt += f"Correct Answers: {', '.join(correct_answers_str)}\n"
            
            # Add users and their responses for each question
            prompt += "Users and their responses:\n"
            if question_data["user_responses"]:
                for response in question_data["user_responses"]:
                    username = response["username"]
                    if username != winner:
                        continue
                    user_response = response["response"]
                    is_correct = "Correct" if any(fuzzy_match(user_response, answer, question_category, question_url) for answer in correct_answers) else "Incorrect"
                    prompt += f"Username: {username} | Response: '{user_response}' | Result: {is_correct}\n"
            else:
                prompt += "No responses recorded for this question.\n"
            
            prompt += "\n"

    # Use unified OpenAI call
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            n=1,
            stop=None,
            temperature=1.0,
        )

        # Extract the generated summary from the response
        summary = response.choices[0].message.content.strip()
        return summary

    except OpenAIError as e:
        sentry_sdk.capture_exception(e)
        print(f"Error generating round summary: {e}")
        return "No ribbons (or soup) for you!"
        

def log_user_submission(user_id):
    """
    Add each user's submission to a queue. The queue will be flushed periodically or when it reaches a limit.
    """
    global submission_queue, max_queue_size
    
    # Add the submission to the queue
    submission_queue.append({"user_id": user_id, "timestamp": time.time()})
    
    # If the queue reaches the maximum size, flush it
    if len(submission_queue) >= max_queue_size:
        flush_submission_queue()


def flush_submission_queue():
    """
    Insert the accumulated submissions into MongoDB in a single batch.
    """
    global submission_queue
    
    if not submission_queue:
        return  # No submissions to flush

    try:
        # Use insert_many to insert all submissions at once
        db.user_submissions_discord.insert_many(submission_queue)
        submission_queue = []  # Clear the queue after flushing
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Failed to flush submission queue: {e}")


def download_image_from_url(url, add_okra, okra_path): 
    global max_retries, delay_between_retries

    """Download an image from a URL with retry logic."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url)

            if response.status_code == 200:
                image_data = response.content  # Successfully downloaded the image, return the binary data

                image = Image.open(io.BytesIO(image_data))
                image_width, image_height = image.size
                image_mxc = upload_image_to_matrix(image_data, add_okra, okra_path)
                return image_mxc, image_width, image_height  # Successfully downloaded the image, return the binary data
                
            else:
                print(f"Failed to download image. Status code: {response.status_code}")
        
        except requests.exceptions.RequestException as e:
            sentry_sdk.capture_exception(e)
            print(f"Error: {e}")
        
        # If the download failed, wait for a bit before retrying
        if attempt < max_retries - 1:
            print(f"Retrying in {delay_between_retries} seconds... (Attempt {attempt + 1} of {max_retries})")
            time.sleep(delay_between_retries)
    
    print("Failed to download image after several attempts.")
    return None, None, None


async def connect_to_mongodb(max_retries=3, delay_between_retries=5):
    global client, db
    client = None
    db = None
    
    for attempt in range(max_retries):
        try:
            # Attempt to connect to MongoDB
            client = AsyncIOMotorClient(mongo_db_string)
            db = client["triviabot"]
            return db  # Return the database connection if successful
        
        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Attempt {attempt + 1} failed: {e}")
            
            # If the maximum number of retries is reached, raise the exception
            if attempt == max_retries - 1:
                raise
            
            # Wait before trying again
            await asyncio.sleep(delay_between_retries)
    return db
 

async def get_bump_data():
    global bumped_status, bumper_king_id, bumper_king_name, last_bump_time
    
    try:
        db = await connect_to_mongodb()
        bump_collection = db["bump_data"]
        
        # Find the bump data document
        bump_doc = await bump_collection.find_one({})
        
        if bump_doc:
            bumped_status = bump_doc.get("bumped_status", False)
            bumper_king_id = bump_doc.get("bumper_king_id", "")
            bumper_king_name = bump_doc.get("bumper_king_name", "")
            last_bump_time = bump_doc.get("last_bump_time", None)
        else:
            # If no document exists, set default values
            bumped_status = False
            bumper_king_id = ""
            bumper_king_name = ""
            last_bump_time = None
            
    except Exception as e:
        print(f"Error fetching bump data: {e}")
        # Set default values on error
        bumped_status = False
        bumper_king_id = ""
        bumper_king_name = ""
        last_bump_time = None


async def update_bump_data():
    global bumped_status, bumper_king_id, bumper_king_name, last_bump_time
    
    try:
        db = await connect_to_mongodb()
        bump_collection = db["bump_data"]
        
        # Set current timestamp when updating
        last_bump_time = time.time()
        
        # Prepare the update document using global variables
        update_doc = {
            "bumped_status": bumped_status,
            "bumper_king_id": bumper_king_id,
            "bumper_king_name": bumper_king_name,
            "last_bump_time": last_bump_time
        }
        
        # Use upsert to update existing document or create new one if it doesn't exist
        result = await bump_collection.update_one(
            {},  # Empty filter to match any document (assuming single document collection)
            {"$set": update_doc},
            upsert=True
        )
        
        return result
        
    except Exception as e:
        print(f"Error updating bump data: {e}")
        return None


async def check_bump_status():
    global bumped_status, bumper_king_id, bumper_king_name, last_bump_time
    
    try:
        # Check if more than 2 hours (7200 seconds) have passed since last bump
        if last_bump_time and (time.time() - last_bump_time) > 7200:
            # Auto-clear the bump status
            bumped_status = False
            bumper_king_id = ""
            bumper_king_name = ""
            last_bump_time = None
            
            # Update the database with cleared values
            await update_bump_data()
            
            print("Bump status auto-cleared after 2 hours")
            
    except Exception as e:
        print(f"Error checking bump status: {e}")


async def sync_bumper_king_with_role():
    """Sync the global bump data with who actually has the Bumper King role in Discord"""
    global bumped_status, bumper_king_id, bumper_king_name, last_bump_time
    
    try:
        # Get the guild
        guild = bot.get_guild(OKRAN_GUILD_ID)
        if not guild:
            print("Could not find guild for bumper king sync")
            return
        
        # Get the Bumper King role
        bumper_king_role = guild.get_role(BUMPER_KING_ROLE_ID)  # Role ID for 👑🍔 Bumper King 🍔👑
        if not bumper_king_role:
            print("Could not find Bumper King role")
            return
        
        # Get members with the role
        role_members = bumper_king_role.members
                
        if role_members:
            member_info = [f"{m.display_name}({m.id})" for m in role_members]
        
        # MongoDB is the source of truth - make Discord match the database
        if not bumped_status or not bumper_king_id:
            # Database says no one should be bumper king - remove role from everyone
            if len(role_members) > 0:
                print(f"Database shows no bumper king, removing role from {len(role_members)} people")
                for member in role_members:
                    try:
                        await member.remove_roles(bumper_king_role)
                        print(f"Removed Bumper King role from {member.display_name}")
                    except discord.Forbidden:
                        print(f"No permission to remove Bumper King role from {member.display_name}")
                    except Exception as e:
                        print(f"Error removing role from {member.display_name}: {e}")
            else:
                print("Database shows no bumper king and no one has the role - already synced")
                
        else:
            # Database says someone should be bumper king - ensure only they have the role
            target_member = guild.get_member(int(bumper_king_id))
            if not target_member:
                print(f"Bumper king {bumper_king_name} ({bumper_king_id}) not found in server - clearing database")
                bumped_status = False
                bumper_king_id = ""
                bumper_king_name = ""
                last_bump_time = None
                await update_bump_data()
                # Remove role from anyone who has it
                for member in role_members:
                    try:
                        await member.remove_roles(bumper_king_role)
                        print(f"Removed Bumper King role from {member.display_name}")
                    except Exception as e:
                        print(f"Error removing role from {member.display_name}: {e}")
            else:
                # Remove role from everyone who shouldn't have it
                for member in role_members:
                    if member.id != int(bumper_king_id):
                        try:
                            await member.remove_roles(bumper_king_role)
                            print(f"Removed Bumper King role from {member.display_name} (not the database bumper king)")
                        except Exception as e:
                            print(f"Error removing role from {member.display_name}: {e}")
                
                # Add role to the correct person if they don't have it
                if target_member not in role_members:
                    try:
                        await target_member.add_roles(bumper_king_role)
                        print(f"Added Bumper King role to {target_member.display_name}")
                    except discord.Forbidden:
                        print(f"No permission to add Bumper King role to {target_member.display_name}")
                    except Exception as e:
                        print(f"Error adding role to {target_member.display_name}: {e}")
                else:
                    print(f"Bumper King role already correctly assigned to {target_member.display_name}")
            
    except Exception as e:
        print(f"Error syncing bumper king with role: {e}")


async def change_bumper_king_role_color(color_input):
    global bumper_king_id
    
    # Color name to hex mapping
    color_names = {
        # Basic colors
        'red': '#FF0000',
        'green': '#00FF00',
        'blue': '#0000FF',
        'yellow': '#FFFF00',
        'orange': '#FFA500',
        'purple': '#800080',
        'pink': '#FFC0CB',
        'cyan': '#00FFFF',
        'magenta': '#FF00FF',
        'lime': '#00FF00',
        'brown': '#A52A2A',
        'black': '#000000',
        'white': '#FFFFFF',
        'gray': '#808080',
        'grey': '#808080',
        
        # Extended colors
        'crimson': '#DC143C',
        'darkred': '#8B0000',
        'lightcoral': '#F08080',
        'salmon': '#FA8072',
        'darksalmon': '#E9967A',
        'lightsalmon': '#FFA07A',
        'orangered': '#FF4500',
        'tomato': '#FF6347',
        'darkorange': '#FF8C00',
        'gold': '#FFD700',
        'lightyellow': '#FFFFE0',
        'lemonchiffon': '#FFFACD',
        'lightgoldenrodyellow': '#FAFAD2',
        'papayawhip': '#FFEFD5',
        'moccasin': '#FFE4B5',
        'peachpuff': '#FFDAB9',
        'palegreen': '#98FB98',
        'lightgreen': '#90EE90',
        'darkgreen': '#006400',
        'forestgreen': '#228B22',
        'limegreen': '#32CD32',
        'aqua': '#00FFFF',
        'lightcyan': '#E0FFFF',
        'darkturquoise': '#00CED1',
        'turquoise': '#40E0D0',
        'mediumturquoise': '#48D1CC',
        'darkblue': '#00008B',
        'navy': '#000080',
        'darkslateblue': '#483D8B',
        'slateblue': '#6A5ACD',
        'mediumslateblue': '#7B68EE',
        'mediumpurple': '#9370DB',
        'darkmagenta': '#8B008B',
        'darkviolet': '#9400D3',
        'darkorchid': '#9932CC',
        'mediumorchid': '#BA55D3',
        'thistle': '#D8BFD8',
        'plum': '#DDA0DD',
        'violet': '#EE82EE',
        'hotpink': '#FF69B4',
        'deeppink': '#FF1493',
        'mediumvioletred': '#C71585',
        'palevioletred': '#DB7093',
        'lavender': '#E6E6FA',
        'lavenderblush': '#FFF0F5',
        'teal': '#008080',
        'darkteal': '#008B8B',
        'mint': '#98FB98',
        'mintcream': '#F5FFFA',
        'aquamarine': '#7FFFD4',
        'mediumaquamarine': '#66CDAA',
        'coral': '#FF7F50',
        'lightcoral': '#F08080',
        'indigo': '#4B0082',
        'maroon': '#800000',
        'olive': '#808000',
        'darkolivegreen': '#556B2F',
        'chartreuse': '#7FFF00',
        'greenyellow': '#ADFF2F',
        'springgreen': '#00FF7F',
        'mediumspringgreen': '#00FA9A',
        'seagreen': '#2E8B57',
        'mediumseagreen': '#3CB371',
        'lightseagreen': '#20B2AA',
        'darkseagreen': '#8FBC8F',
        'honeydew': '#F0FFF0',
        'beige': '#F5F5DC',
        'wheat': '#F5DEB3',
        'sandybrown': '#F4A460',
        'tan': '#D2B48C',
        'chocolate': '#D2691E',
        'firebrick': '#B22222',
        'rosybrown': '#BC8F8F',
        'goldenrod': '#DAA520',
        'darkgoldenrod': '#B8860B',
        'lightgoldenrod': '#EEDD82',
        'palegoldenrod': '#EEE8AA',
        'khaki': '#F0E68C',
        'darkkhaki': '#BDB76B',
        
        # Neutral colors
        'darkgray': '#A9A9A9',
        'darkgrey': '#A9A9A9',
        'silver': '#C0C0C0',
        'lightgray': '#D3D3D3',
        'lightgrey': '#D3D3D3',
        'gainsboro': '#DCDCDC',
        'whitesmoke': '#F5F5F5',
        'dimgray': '#696969',
        'dimgrey': '#696969',
        'lightslategray': '#778899',
        'lightslategrey': '#778899',
        'slategray': '#708090',
        'slategrey': '#708090',
        'darkslategray': '#2F4F4F',
        'darkslategrey': '#2F4F4F',
        
        # Fun/Discord colors
        'blurple': '#5865F2',  # Discord's brand color
        'discord': '#5865F2',
        'nitro': '#FF73FA',
        'boost': '#F47FFF',
        'invisible': '#747F8D',
    }
    
    try:
        # Check if input is a color name
        if color_input.lower() in color_names:
            hex_code = color_names[color_input.lower()]
        else:
            # Assume it's a hex code
            hex_code = color_input
            # Validate hex code format
            if not hex_code.startswith('#'):
                hex_code = '#' + hex_code
        
        # Convert hex to integer for Discord
        color_int = int(hex_code.replace('#', ''), 16)
        color = discord.Color(color_int)
        
        # Check if there's a bumper king
        if not bumper_king_id:
            return "No bumper king currently set."
        
        # Get the guild (server)
        guild = bot.get_guild(OKRAN_GUILD_ID)
        if not guild:
            return "Server not found."
        
        # Get the bumper king member
        #member = guild.get_member(int(bumper_king_id))
        #if not member:
        #    return "Bumper king member not found."
        
        # Get the specific Bumper King role by ID
        bumper_role = guild.get_role(BUMPER_KING_ROLE_ID)
        
        if not bumper_role:
            return "Bumper King role not found in server."
        
        # Change the role color
        await bumper_role.edit(color=color, reason=f"Bumper king color change to {hex_code}")
        
        return f"Your username color is now {color_input}, your highness."
        
    except ValueError:
        return "Invalid hex color code format. Use format like #FF0000 or FF0000"
    except discord.Forbidden:
        return "Bot doesn't have permission to modify roles."
    except discord.HTTPException as e:
        return f"Discord API error: {e}"
    except Exception as e:
        return f"Error changing role color: {e}"


@bot.tree.command(name="okrafx", description="Change your username color (only for the current 👑🍔 Bumper King 🍔👑)")
@discord.app_commands.describe(color="Color name or hex code")
async def change_color_command(interaction: discord.Interaction, color: str):
    global bumper_king_id
    
    # Check if the user is the current bumper king
    print(interaction.user.id)
    print(bumper_king_id)
    if not bumper_king_id or str(interaction.user.id) != bumper_king_id:
        await interaction.response.send_message(
            "❌ You are NOT the current 👑🍔 **Bumper King** 🍔👑! Only their highness can change their name color.",
            ephemeral=True
        )
        return
    
    # Defer the response since role editing might take a moment
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Call the color change function
        result = await change_bumper_king_role_color(color)
        
        # Send success or error message
        if "your highness" in result:
            await interaction.followup.send(f"✅ {result}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ {result}", ephemeral=True)
            
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)


async def save_data_to_mongo(collection_name, document_id, data):
    if data is None:
        data = {"data": "None"}  
    
    now = time.time()

    for attempt in range(max_retries):
        try:
            data_with_timestamp = {"timestamp": now, **data}
            await db[collection_name].update_one(
                {"_id": document_id},  
                {"$set": data_with_timestamp},  
                upsert=True  
            )
            return  

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Error saving data to MongoDB on attempt {attempt + 1}: {e}")

            if attempt < max_retries - 1:
                print(f"Retrying in {delay_between_retries} seconds...")
                await asyncio.sleep(delay_between_retries)
            else:
                print(f"Data NOT saved to {collection_name} named {document_id}.")


async def insert_data_to_mongo(collection_name, data):
    if data is None:
        data = {"data": "None"}  # Convert None to a default dictionary
    
    if isinstance(data, str):
        # Convert the string to a dictionary with a specific key
        data = {"data": data}
    elif not isinstance(data, dict):
        raise TypeError("The data parameter must be either a string or a dictionary")
    
    now = time.time()

    for attempt in range(max_retries):
        try:
            data_with_timestamp = {"timestamp": now, **data}
            await db[collection_name].insert_one(data_with_timestamp)
            break

        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Attempt {attempt + 1} failed: {e}")

            if attempt < max_retries - 1:
                print(f"Retrying in {delay_between_retries} seconds...")
                await asyncio.sleep(delay_between_retries)
            else:
                print(f"Data NOT inserted into {collection_name}.")


def is_valid_url(url): 
    try:
        result = urlparse(url)

        return all([result.scheme, result.netloc])
    except ValueError as e:
        sentry_sdk.capture_exception(e)
        return False


def remove_diacritics(input_str):
    """Remove diacritics from the input string."""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return ''.join([char for char in nfkd_form if not unicodedata.combining(char)])


async def ask_question(trivia_category, trivia_question, trivia_url, trivia_answer_list, question_number):
    """Ask the trivia question."""
    # Define the numbered block emojis for questions 1 to 10
    numbered_blocks = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    number_block = numbered_blocks[question_number - 1]  # Get the corresponding numbered block
    new_solution = None
    new_question = None
    send_image_flag = False
    image_buffer = None
    image_url = None

    trivia_answer = trivia_answer_list[0]  # The first item is the main answer

    single_answer = (
        (len(trivia_answer_list) == 1 and (is_number(trivia_answer) or len(trivia_answer) == 1)) or
        trivia_url in [
            "median", "mean", "zeroes sum", "zeroes product", "zeroes", "base", "factors",
            "derivative", "trig", "algebra"
        ]
        or sniper_mode
    )

    message_body = ""
    if single_answer:
        message_body += "\u200b\n🚨 **1 GUESS** 🚨"
        
    if is_valid_url(trivia_url): 
        message_body += f"\u200b\n\u200b\n{number_block}📷 **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n"
        image_url = trivia_url
        send_image_flag = True

    elif trivia_url == "algebra":
        image_buffer, new_question, new_solution, text_problem = generate_and_render_linear_problem()
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{new_question}\n" 
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{new_question}\n{text_problem}\n"
    
    elif trivia_url == "trig":
        image_url, new_question, new_solution, img_description = generate_trig_question()
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{new_question}\n" 
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{new_question}\n{img_description}\n"

    elif trivia_url == "base":
        image_buffer, new_question, new_solution, base_string = generate_base_question()
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{new_question}\n" 
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{new_question}\n{base_string}\n"
    
    elif trivia_url == "zeroes sum":
        image_buffer, new_solution, polynomial = generate_and_render_polynomial(trivia_url)
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n" 
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n{polynomial}\n"

    elif trivia_url == "characters":
        message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\nName the movie, book, or show:\n\n{trivia_question}\n"

    elif trivia_url == "zeroes product":
        image_buffer, new_solution, polynomial = generate_and_render_polynomial(trivia_url)
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n" 
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n{polynomial}\n"

    elif trivia_url == "zeroes":
        image_buffer, new_solution, polynomial = generate_and_render_polynomial(trivia_url)
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n" 
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n{polynomial}\n"

    elif trivia_url == "factors":
        image_buffer, new_solution, polynomial = generate_and_render_polynomial(trivia_url)
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n" 
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n{polynomial}\n"
            
    elif trivia_url == "derivative":
        image_buffer, new_solution, polynomial = generate_and_render_derivative_image()
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n" 
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n{polynomial}\n"
        
    elif trivia_url == "scramble":
        image_buffer, scramble = generate_scrambled_image(scramble_text(trivia_answer_list[0]))
        if image_questions:
            message_body += f"\u200b\n\u200b\n{number_block}🧩 **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n"
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block}🧩 **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n{scramble}\n"

    elif trivia_url == "median":
        image_buffer, new_solution, num_set = generate_median_question()
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block}📊 **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n"
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n{num_set}\n"

    elif trivia_url == "mean":
        image_buffer, new_solution, num_set = generate_mean_question()
        if image_questions == True:
            message_body += f"\u200b\n\u200b\n{number_block}📊 **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n"
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n{num_set}\n"

    elif trivia_url == "jeopardy":
        if image_questions == True: 
            image_buffer = generate_jeopardy_image(trivia_question)
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\nAnd the answer is: \n"
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n"
            
    elif trivia_category == "Crossword":
        image_buffer, string_representation = generate_crossword_image(trivia_answer_list[0])
        if image_questions == True: 
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n[{len(trivia_answer_list[0])} Letters] {trivia_question}\n"
            send_image_flag = True
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n[{len(trivia_answer_list[0])} Letters] {trivia_question}\n\n{string_representation}\n"
        
    elif trivia_url == "multiple choice" or trivia_url == "multiple choice opentrivia" or trivia_url == "multiple choice oracle": 
        if trivia_answer_list[0] in {"True", "False"}:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n🚨 **T/F - 1 GUESS** 🚨 {trivia_question}\n\n"
        else:
            message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n🚨 **Letter - 1 GUESS** 🚨 {trivia_question}\n"
            #await safe_send(channel, message_body)
            message_body += "\n"
            for answer in trivia_answer_list[1:]:
                message_body += f"{answer}\n"
            message_body += "\n"
        trivia_answer_list[:] = trivia_answer_list[:1]

    else:
         message_body += f"\u200b\n\u200b\n{number_block} **{get_category_title(trivia_category, trivia_url)}**\n\n{trivia_question}\n"

    message_body += "\u200b"
    
    if send_image_flag:
        if image_url:  
            message = await safe_send(channel, content=message_body, embed=discord.Embed().set_image(url=image_url))
        elif image_buffer:
            image_file = discord.File(fp=image_buffer, filename="image.png")
            embed = discord.Embed()
            embed.set_image(url="attachment://image.png")
            message = await safe_send(channel, content=message_body, embed=embed, file=image_file)
    else:
        message = await safe_send(channel, message_body)

    response_time = message.created_at.timestamp()
            
    if new_solution is None:
    # Use the original trivia answer list if no new solution is provided
        correct_answers = trivia_answer_list
    elif isinstance(new_solution, list):
        # If new_solution is already a list, use it as-is
        correct_answers = new_solution
    else:
        # If new_solution is a single value, wrap it in a list
        correct_answers = [new_solution]
    
    round_data["questions"].append({
        "question_number": question_number,
        "question_category": trivia_category,
        "question_url": trivia_url,
        "question_text": trivia_question,
        "correct_answers": correct_answers,  
        "user_responses": [] 
    })
    
    return response_time, new_question, new_solution


def calculate_points(response_time):  
    points = max(1000 - int(response_time * (995 / question_time)), 5)
    points = round(points / 5) * 5  
    return points
    

def remove_filler_words(input_str):
    words = input_str.split()
    filtered_words = [word for word in words if word not in filler_words]
    return ' '.join(filtered_words)


def normalize_text(input):
    text = input.strip()
    text = text.lower()    
    text = normalize_superscripts(text)
    text = remove_diacritics(text)
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text


def levenshtein_similarity(str1, str2):
    return difflib.SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def jaccard_similarity(str1, str2):
    set1, set2 = set(str1.lower()), set(str2.lower())
    return len(set1 & set2) / len(set1 | set2)


def token_based_matching(user_answer, correct_answer):
    user_tokens = set(user_answer.lower().split())
    correct_tokens = set(correct_answer.lower().split())
    return len(user_tokens & correct_tokens) / len(user_tokens | correct_tokens)


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def derivative_checker(response, answer):
    response = response.lower()
    answer = answer.lower()
    response = response.replace(" ", "")      
    answer = answer.replace(" ", "")
    response = response.replace("^", "")      
    answer = answer.replace("^", "")
    response = response.replace("*", "")      
    answer = answer.replace("*", "")
    response = normalize_superscripts(response)
    answer = normalize_superscripts(answer)

    if (response == answer or jaccard_similarity(response, answer) == 1) and len(response) == len(answer):
        return True
    else:
        return False


def factors_checker(response, answer):
    response = response.lower()
    answer = answer.lower()
    
    response = response.replace(" ", "")      
    answer = answer.replace(" ", "")
    
    response = response.replace("*", "")      
    answer = answer.replace("*", "")

    response = response.replace("(", "")      
    answer = answer.replace("(", "")

    response = response.replace(")", "")      
    answer = answer.replace(")", "")

    return response == answer



def trig_checker(response, answer):
    response = response.lower()
    answer = answer.lower()
    response = response.replace(" ", "")      
    answer = answer.replace(" ", "")
    response = response.replace("(", "")      
    answer = answer.replace("(", "")
    response = response.replace(")", "")      
    answer = answer.replace(")", "")

    if response == answer:
        return True
    else:
        return False


def fuzzy_match(user_answer, correct_answer, category, url):
    threshold = 0.90   
    
    if not isinstance(user_answer, str) or not isinstance(correct_answer, str):
        return False
    if not user_answer.strip() or not correct_answer.strip():
        return False
    if not user_answer or not correct_answer:
        return False
 

    if user_answer == correct_answer:
        return True

    no_spaces_user = user_answer.replace(" ", "")      
    no_spaces_correct = correct_answer.replace(" ", "") 

    if category == "Crossword":
        return no_spaces_user.lower() == no_spaces_correct.lower()

    if url == "zeroes":
        user_numbers = [int(num) for num in re.findall(r'-?\d+', user_answer)]
        correct_numbers = [int(num) for num in re.findall(r'-?\d+', correct_answer)]
        
        # Check if the two sets of numbers match (order does not matter)
        if set(user_numbers) == set(correct_numbers):
            return True
        else:
            return False

    if url == "derivative":
        return derivative_checker(user_answer, correct_answer)

    if url == "factors":
        return factors_checker(user_answer, correct_answer)

    if url == "trig":
        return trig_checker(user_answer, correct_answer)
    
        
    if is_number(correct_answer):
        return user_answer == correct_answer  # Only accept exact match if the correct answer is a number
    
    user_answer = normalize_text(str(user_answer))
    correct_answer = normalize_text(str(correct_answer))

    if url in {"multiple choice", "multiple choice opentrivia", "multiple choice oracle"}:
        if user_answer and correct_answer:
            return user_answer[0].lower() == correct_answer[0].lower()
        else:
            return False
    
    if is_number(correct_answer):
        return user_answer == correct_answer  # Only accept exact match if the correct answer is a number

    no_spaces_user = user_answer.replace(" ", "")      
    no_spaces_correct = correct_answer.replace(" ", "") 

    no_filler_user = remove_filler_words(user_answer)
    no_filler_correct = remove_filler_words(correct_answer)

    no_filler_spaces_user = no_filler_user.replace(" ", "")
    no_filler_spaces_correct = no_filler_correct.replace(" ", "")

    if no_spaces_user == no_spaces_correct or no_filler_user == no_filler_correct or no_filler_spaces_user == no_filler_spaces_correct:     
        return True

    if len(user_answer) < 4:
        return user_answer == correct_answer  # Only accept an exact match for short answers
    
    if user_answer == correct_answer:
        return True
    
         
    # New Step: First 5 characters match
    if user_answer[:5] == correct_answer[:5] or no_spaces_user[:5] == no_spaces_correct[:5] or no_filler_user[:5] == no_filler_correct[:5] or no_filler_spaces_user[:5] == no_filler_spaces_correct[:5]:
        return True
    
    # Remove filler words and split correct answer
    correct_answer_words = correct_answer.split()
    no_filler_answer_words = no_filler_correct.split()
    
    # Ensure correct_answer_words is not empty
    if correct_answer_words and len(correct_answer_words[0]) >= 3:
        if user_answer == correct_answer_words[0] or no_filler_user == correct_answer_words[0]:
            return True

    if no_filler_answer_words and len(no_filler_answer_words[0]) >= 3:
        if user_answer == no_filler_answer_words[0] or no_filler_user == no_filler_answer_words[0]:
            return True

    #Check if user's answer is a substring of the correct answer after normalization
    if user_answer in correct_answer:
        return True
    
    # Step 1: Exact match or Partial match
    if correct_answer in user_answer:
        return True
    
    # Step 2: Levenshtein similarity
    if levenshtein_similarity(user_answer, correct_answer) >= threshold or levenshtein_similarity(no_spaces_user, no_spaces_correct) >= threshold or levenshtein_similarity(no_filler_user, no_filler_correct) >= threshold or levenshtein_similarity(no_filler_spaces_user, no_filler_spaces_correct) >= threshold:
        return True

    
    # Step 3: Jaccard similarity (Character level)
    if jaccard_similarity(user_answer, correct_answer) >= threshold and url != "scramble":
        return True

    # Step 4: Token-based matching
    if token_based_matching(user_answer, correct_answer) >= threshold:
        return True

    return False  # No match found


async def check_correct_responses_delete(question_ask_time, trivia_answer_list, question_number, collected_responses, trivia_category, trivia_url):
    """Check and respond to users who answered the trivia question correctly."""
    global max_retries, delay_between_retries, current_longest_answer_streak
    global question_responders, round_responders, discount_percentage
    
    # Define the first item in the list as trivia_answer
    trivia_answer = trivia_answer_list[0]  
    correct_responses = [] 
    has_responses = False

    fastest_correct_user = None
    fastest_correct_user_id = None
    fastest_response_time = None

    # Check if trivia_answer_list is a single-element list with a numeric answer  
    single_answer = (
        (len(trivia_answer_list) == 1 and (is_number(trivia_answer) or len(trivia_answer) == 1)) or
        trivia_url in [
            "multiple choice opentrivia", "multiple choice oracle", "multiple choice",
            "median", "mean", "zeroes sum", "zeroes product", "zeroes", "base", "factors",
            "derivative", "trig", "algebra"
        ]
        or sniper_mode
    )
    
    # Dictionary to track first numerical response from each user if answer is a number
    user_first_response = {}

    # Process collected responses
    for response in collected_responses:
        message = response["message"]
        #message_content = message.content
        message_content = response["message_content"]
        sender_id = message.author.id
        display_name = message.author.display_name
        timestamp = message.created_at.timestamp()
        message_id = message.id
        bot_user_id = bot.user.id
        
        message_content = message_content.replace("\uFFFC", "")  # Remove U+FFFC

        if not message_content.strip():
            continue  # skip empty messages

        # Track users who responded to the current question and round
        if sender_id not in question_responders:
            question_responders.append(sender_id)  # Add to question responders
        
            # Only add to round responders if not already present
            if sender_id not in round_responders:
                round_responders.append(sender_id)

        # Check if the user has already answered correctly, ignore if they have
        if any(resp[4] == sender_id for resp in correct_responses):
            continue  # Ignore this response since the user has already answered correctly
        
        # If it's a single numeric answer question, and this user's response is numeric, only record the first one
        if single_answer:
            if sender_id in user_first_response:
                continue  # Skip if we've already recorded a numeric response for this user
        
            if (
                not message_content.startswith("#") and (
                    is_number(message_content) or  # Rule 1: message_content is a number
                    message_content[0].isdigit() or  # Rule 2: first character is a number
                    message_content.lower() in {"a", "b", "c", "d", "t", "f", "true", "false"} or  # Rule 3: exact match
                    message_content[0].lower() in {"-", "x", "y", "z", "("} or # Rule 4: first character match
                    len(message_content) == 1 or
                    sniper_mode == True
                )
            ):
                user_first_response[sender_id] = message_content
            else:
                continue  # Skip non-numeric responses for single numeric questions
        
        # Log user submission (MongoDB operation)
        #log_user_submission(display_name)
                
        # Indicate that there was at least one response
        has_responses = True
                                
        # Find the current question data to add responses
        current_question_data = next((q for q in round_data["questions"] if q["question_number"] == question_number), None)
        if current_question_data:
            current_question_data["user_responses"].append({
                "username": display_name,
                "response": message_content
            })
                                
        # Check if the user's response is in the list of correct answers
        if any(fuzzy_match(message_content, answer, trivia_category, trivia_url) for answer in trivia_answer_list):            
            if timestamp and question_ask_time:
                # Convert timestamp to seconds
                response_time = timestamp - question_ask_time
            else:   
                response_time = float('inf')
                
            points = calculate_points(response_time)

            # Check if the sender is the current user on the longest round streak
            if sender_id == current_longest_round_streak["user_id"]:
                streak = current_longest_round_streak["streak"]
                # For every 5 in the streak, apply a 10% discount
                discount_percentage = discount_step_amount * (streak // discount_streak_amount)  # e.g., 5 => 10%, 10 => 20%, 15 => 30%, etc.

                # You might want to cap the discount so it doesn't go negative or too high
                discount_percentage = min(discount_percentage, 90)  # optional
        
                if discount_percentage > 0:
                    discount_factor = 1 - (discount_percentage / 100.0)
                    points *= discount_factor
                    points = round(points / 5) * 5

            correct_responses.append((display_name, points, response_time, message_content, sender_id, message))
    
            # Check if this is the fastest correct response so far
            if fastest_correct_user is None or response_time < fastest_response_time:
                fastest_correct_user_id = sender_id
                fastest_correct_user = display_name
                fastest_response_time = response_time
                fastest_correct_message = message
            
    if emoji_mode == True and fastest_response_time is not None and blind_mode == False and marx_mode == False:
        try:
            await fastest_correct_message.add_reaction("⬆️")
        except discord.NotFound:
            print("❌ Message was already deleted, can't react.")
        except discord.Forbidden:
            print("❌ Bot lacks permission to add reactions.")
        except discord.HTTPException as e:
            print(f"❌ Failed to add reaction: {e}")

    # Now that we know the fastest responder, iterate over correct_responses to:
    # - Assign the extra 500 points to the fastest user
    # - Update the scoreboard for all users
    for i, (display_name, points, response_time, message_content, sender_id, discord_message) in enumerate(correct_responses):
        if sender_id == fastest_correct_user_id:
            if sender_id in fastest_answers_count:
                fastest_answers_count[sender_id] += 1
            else:
                fastest_answers_count[sender_id] = 1
                
            if sender_id in scoreboard:
                scoreboard[sender_id]["score"] += points + first_place_bonus
            else:
                scoreboard[sender_id] = {"display_name": display_name, "score": points + first_place_bonus}  
        else:
            if sender_id in scoreboard:
                scoreboard[sender_id]["score"] += points
            else:
                scoreboard[sender_id] = {"display_name": display_name, "score": points}               

    await update_answer_streaks(fastest_correct_user, fastest_correct_user_id)  # Update the correct answer streak for this user
   
    # Add the current state of the scoreboard to round_data
    current_question_data = next((q for q in round_data["questions"] if q["question_number"] == question_number), None)
    if current_question_data:
        current_question_data["scoreboard_after_question"] = dict(scoreboard)

    # Construct a single message for all the responses
    message = ""
    if blind_mode == False:
        message = f"\u200b\n✅ **Answer** ({len(question_responders)}) ✅\n{trivia_answer}\n\u200b"
            
    # Notify the chat
    if correct_responses and marx_mode == False:    
        correct_responses_length = len(correct_responses)
        
        # Loop through the responses and append to the message
        for display_name, points, response_time, message_content, sender_id, discord_message in correct_responses:
            time_diff = response_time - fastest_response_time
            
            name_str = display_name
            if current_longest_round_streak["user_id"] == sender_id and discount_percentage is not None and discount_percentage > 0:
                name_str += f" (-{discount_percentage}%)"
        
            # Display the formatted message based on yolo_mode
            if time_diff == 0:
                message += f"\u200b\n⚡ **{display_name}**"
                if not yolo_mode:
                    message += f": {points}"
                if points == 420:
                    message += " 🌿"
                if points == 690:
                    message += " 😎"
                if current_longest_answer_streak["streak"] > 1:
                    message += f"  🔥{current_longest_answer_streak['streak']}"
            else:
                message += f"\n\u200b👥 **{display_name}**"
                if not yolo_mode:
                    message += f": {points}"
                if points == 420:
                    message += " 🌿"
                if points == 690:
                    message += " 😎"

    # Send the entire message at once
    if message:
        message += "\n\u200b"
        await safe_send(channel, message)

    flush_submission_queue() 
    return None


async def update_answer_streaks(user, user_id):
    """Update the current longest answer streak for the user who answered correctly."""
    global current_longest_answer_streak

    if current_longest_answer_streak["user_id"] != user_id:
        if current_longest_answer_streak["user_id"] is not None:
            # Append the streak, sort the list in descending order, and keep at most 20 entries
            await insert_data_to_mongo("longest_answer_streaks_discord", current_longest_answer_streak)
        current_longest_answer_streak["user_id"] = user_id
        current_longest_answer_streak["user"] = user
        current_longest_answer_streak["streak"] = 0

    if user is None:
        await save_data_to_mongo("current_streaks_discord", "current_longest_answer_streak", current_longest_answer_streak)
    else:
        current_longest_answer_streak["streak"] += 1
        await save_data_to_mongo("current_streaks_discord", "current_longest_answer_streak", current_longest_answer_streak)
        await insert_data_to_mongo("fastest_answers_discord", {
            "user": user,
            "user_id": user_id
        })


async def update_round_streaks(user, user_id):
    """Update the current longest round streak for the user who answered correctly."""
    global current_longest_round_streak

    # Variables to store data to be inserted or saved later
    mongo_operations = []

    # Manually copy function for dictionaries
    def manual_copy(data):
        """Manually copy a dictionary by reconstructing it."""
        return {key: value for key, value in data.items()}

    # Check if we need to update the longest round streak
    if current_longest_round_streak["user_id"] != user_id:
        if current_longest_round_streak["user_id"] is not None:
            # Prepare the data to be inserted into longest_round_streaks
            mongo_operations.append({
                "operation": "insert",
                "collection": "longest_round_streaks_discord",
                "data": manual_copy(current_longest_round_streak)  # Manually copy the data
            })
        # Update the user and reset the streak
        current_longest_round_streak["user"] = user
        current_longest_round_streak["user_id"] = user_id
        current_longest_round_streak["streak"] = 0

    # Increment streak or handle no user case
    if user is None:
        mongo_operations.append({
            "operation": "save",
            "collection": "current_streaks_discord",
            "document_id": "current_longest_round_streak",
            "data": manual_copy(current_longest_round_streak)  # Manually copy the data
        })
    else:
        current_longest_round_streak["streak"] += 1
        mongo_operations.append({
            "operation": "save",
            "collection": "current_streaks_discord",
            "document_id": "current_longest_round_streak",
            "data": manual_copy(current_longest_round_streak)  # Manually copy the data
        })
        mongo_operations.append({
            "operation": "insert",
            "collection": "round_wins_discord",
            "data": {
                "user": user,
                "user_id": user_id
            }
        })

    # Generate the round summary if the user is not None
    if user is not None:
        streak = current_longest_round_streak["streak"]
        if streak > 1:
            message = f"\u200b\n\u200b\n🏆 **Winner**: **<@{user_id}>**...🔥{current_longest_round_streak['streak']} in a row!\n"
            
            if streak % discount_streak_amount == 0:
                discount_fraction = min((streak // discount_streak_amount) * discount_step_amount, 90)
                message += f"\n⚖️ Going forward **<@{user_id}>** will incur a **-{discount_fraction}%** handicap.\n"
                
            message += f"\n▶️ **[Discord Stats](https://94mes.com/discord)**\n\u200b\n\u200b"
        else:
            message = f"\u200b\n\u200b\n🏆 **Winner**: **<@{user_id}>**!\n\n▶️ **[Discord Stats](https://94mes.com/discord)**\n\u200b\n\u200b"

        await safe_send(channel, message)
        await asyncio.sleep(2)
        
        await select_wof_questions(user, user_id)

        reset_embed_color()

        if ai_on:
            winner_coffees = await get_coffees(user_id)
            if winner_coffees == 0:
                gpt_summary = f"\n🥒💬🎨 **<@{user_id}>**: Okrans get custom end-of-round messages and paintings!\n"
            else:
                gpt_summary = await generate_round_summary(round_data, user, user_id)

            gpt_message = f"\u200b\n{gpt_summary}\n\u200b"
            await safe_send(channel, gpt_message)

            if winner_coffees > 0:
                highest_score_player = max(scoreboard, key=lambda uid: scoreboard[uid]["score"])
                highest_score = scoreboard[highest_score_player]["score"]
    
                
                #if len(scoreboard) >= image_wins and highest_score > image_points:
                if current_longest_round_streak['streak'] % image_wins == 0:
                    await asyncio.sleep(5)
                    await generate_round_summary_image(round_data, user, user_id)
                else:
                    number_to_emoji = {
                        1: "1️⃣",
                        2: "2️⃣",
                        3: "3️⃣",
                        4: "4️⃣",
                        5: "5️⃣",
                        6: "6️⃣",
                        7: "7️⃣",
                        8: "8️⃣",
                        9: "9️⃣",
                        10: "🔟"
                    }
                    
                    await asyncio.sleep(4)
                    remaining_games = image_wins - (current_longest_round_streak['streak'] % image_wins)
                    dynamic_emoji = number_to_emoji.get(remaining_games, str(remaining_games))
                    
                    if remaining_games == 1:
                        image_message = f"\u200b\n{dynamic_emoji}🎨 **<@{user_id}>**, win the next game and I'll draw you something.\n\u200b"
                    else:
                        image_message = f"\u200b\n{dynamic_emoji}🎨 **<@{user_id}>**, win {remaining_games} more in a row and I'll draw you something.\n\u200b"
    
                    await safe_send(channel, image_message)
                    await asyncio.sleep(2)
                    await get_image_url_from_s3()
                    await asyncio.sleep(1)

    # Perform all MongoDB operations at the end
    for operation in mongo_operations:
        if operation["operation"] == "insert":
            await insert_data_to_mongo(operation["collection"], operation["data"])
        elif operation["operation"] == "save":
            await save_data_to_mongo(operation["collection"], operation["document_id"], operation["data"])
            

async def determine_round_winner():
    """Determine the round winner based on points and response times."""
    if not scoreboard:
        return None, None, None

    # Find the max score
    max_score = max(user_data["score"] for user_data in scoreboard.values())

    # Find all users with the max score
    potential_winners = [user_id for user_id, user_data in scoreboard.items() if user_data["score"] == max_score]

    # If there's a tie, no clear-cut winner
    if len(potential_winners) > 1:
        await safe_send(channel, "No clear-cut winner this round due to a tie.")
        return None, None, None
    else:
        winner_id = potential_winners[0]
        winner_data = scoreboard[winner_id]
        return winner_data["display_name"], winner_data["score"], winner_id
        

async def show_standings():
    """Show the current standings after each question."""
    if scoreboard:
        # Sort by score descending
        standings = sorted(scoreboard.items(), key=lambda x: x[1]["score"], reverse=True)
        standing_message = f"\n📈 **Scoreboard** ({len(round_responders)}) 📈"
        
        medals = ["🥇", "🥈", "🥉"]
        
        for rank, (user_id, user_data) in enumerate(standings, start=1):
            display_name = user_data["display_name"]
            score = user_data["score"]
            formatted_points = f"{score:,}"  # Format points with commas
            fastest_count = fastest_answers_count.get(user_id, 0)

            user_str = display_name

            if current_longest_round_streak["user_id"] == user_id and discount_percentage > 0 and discount_percentage is not None:
                user_str += f" (-{discount_percentage}%)"

            lightning_display = f" ⚡{fastest_count}" if fastest_count > 1 else " ⚡" if fastest_count == 1 else ""

            if "420" in str(score):
                standing_message += f"\n🌿 **{user_str}**: {formatted_points}"
            elif "69" in str(score):
                standing_message += f"\n😎 **{user_str}**: {formatted_points}"
            elif rank <= 3:
                standing_message += f"\n{medals[rank - 1]} **{user_str}**: {formatted_points}"
            elif rank == len(standings) and rank > 4:
                standing_message += f"\n💩 **{user_str}**: {formatted_points}"
            else:
                standing_message += f"\n{rank}. **{user_str}**: {formatted_points}"

            standing_message += lightning_display

        await safe_send(channel, standing_message)


async def store_question_ids_in_mongo(question_ids, question_type):
    db = await connect_to_mongodb()
    collection_name = f"asked_{question_type}_questions_discord"
    questions_collection = db[collection_name]

    for _id in question_ids:
        # Use upsert to insert or update the document if it doesn't exist
        await questions_collection.update_one(
            {"_id": _id},                  # Match the document by its _id
            {"$setOnInsert": {"_id": _id, "timestamp": datetime.datetime.now(datetime.UTC)}},  # Insert only if not present
            upsert=True                    # Enable upsert behavior
        )

    # Check if the collection exceeds its limit and delete old entries if necessary
    limit = id_limits[question_type]
    total_ids = await questions_collection.count_documents({})
    if total_ids > limit:
        excess = total_ids - limit
        cursor = questions_collection.find().sort("timestamp", 1).limit(excess)
        oldest_entries = await cursor.to_list(length=excess)
        for entry in oldest_entries:
            await questions_collection.delete_one({"_id": entry["_id"]})


async def get_recent_question_ids_from_mongo(question_type):
    db = await connect_to_mongodb()
    collection_name = f"asked_{question_type}_questions_discord"
    questions_collection = db[collection_name]

    cursor = questions_collection.find().sort("timestamp", -1).limit(id_limits[question_type])
    documents = await cursor.to_list(length=id_limits[question_type])

    return {doc["_id"] for doc in documents}


async def get_all_recent_question_ids():
    recent_ids = {}
    for question_type in ["general", "crossword", "jeopardy", "mysterybox", "wof"]:
        collection_name = f"asked_{question_type}_questions_discord"
        questions_collection = db[collection_name]
        # Await the cursor and convert it to a list
        docs = await questions_collection.find().sort("timestamp", -1).limit(id_limits[question_type]).to_list(length=id_limits[question_type])
        recent_ids[question_type] = {doc["_id"] for doc in docs}
    return recent_ids


async def store_all_question_ids(question_ids_by_type):
    for question_type, question_ids in question_ids_by_type.items():
        if not question_ids:
            continue
        collection_name = f"asked_{question_type}_questions_discord"
        questions_collection = db[collection_name]

        for _id in question_ids:
            # Use upsert to insert or update the document if it doesn't exist
            await questions_collection.update_one(
                {"_id": _id},  # Match the document by its _id
                {"$setOnInsert": {"_id": _id, "timestamp": datetime.datetime.now(datetime.UTC)}},  # Insert only if not present
                upsert=True  # Enable upsert behavior
            )

        # Check if the collection exceeds its limit and delete old entries if necessary
        limit = id_limits[question_type]
        total_ids = await questions_collection.count_documents({})
        if total_ids > limit:
            excess = total_ids - limit
            # Find the oldest entries based on timestamp
            cursor = questions_collection.find().sort("timestamp", 1).limit(excess)
            oldest_entries = await cursor.to_list(length=excess)
            for entry in oldest_entries:
                await questions_collection.delete_one({"_id": entry["_id"]})


async def select_trivia_questions(questions_per_round):
    global categories_to_exclude
    try:

        recent_question_ids = await get_all_recent_question_ids()
        selected_questions = []
        question_ids_to_store = {  # Initialize a dictionary to batch store question IDs
            "general": [],
            "crossword": [],
            "jeopardy": [],
            "mysterybox": [],
            "wof": []
        }
        
        sample_size = min(num_crossword_clues, questions_per_round - len(selected_questions))
        if sample_size > 0:
            crossword_collection = db["crossword_questions"]
            pipeline_crossword = [
                {"$match": {"_id": {"$nin": list(recent_question_ids["crossword"])}}},
                {"$sample": {"size":sample_size}}  # Apply sampling on the filtered subset
            ]
            crossword_questions = await crossword_collection.aggregate(pipeline_crossword).to_list(length=sample_size)

            for doc in crossword_questions:
                doc["db"] = "crossword_questions"
                
            selected_questions.extend(crossword_questions)
            question_ids_to_store["crossword"].extend(doc["_id"] for doc in crossword_questions)

        sample_size = min(num_jeopardy_clues, questions_per_round - len(selected_questions))
        if sample_size > 0:
            jeopardy_collection = db["jeopardy_questions"]
            pipeline_jeopardy = [
                {"$match": {"_id": {"$nin": list(recent_question_ids["jeopardy"])}}},
                {"$sample": {"size": sample_size}}  # Apply sampling on the filtered subset
            ]
            jeopardy_questions = await jeopardy_collection.aggregate(pipeline_jeopardy).to_list(length=sample_size)

            for doc in jeopardy_questions:
                doc["db"] = "jeopardy_questions"
                
            selected_questions.extend(jeopardy_questions)
            question_ids_to_store["jeopardy"].extend(doc["_id"] for doc in jeopardy_questions)

        
        num_math_questions_mod = random.randint(0, num_math_questions)
        sample_size = min(num_math_questions_mod, questions_per_round - len(selected_questions))
        if sample_size > 0:
            math_questions = [get_math_question() for _ in range(sample_size)]

            for doc in math_questions:
                doc["db"] = "math_questions"
                doc["_id"] = str(random.randint(10000, 99999))
                
            selected_questions.extend(math_questions)

        sample_size = min(num_stats_questions, questions_per_round - len(selected_questions))
        if sample_size > 0:
            stats_questions = [get_stats_question() for _ in range(sample_size)]

            for doc in stats_questions:
                doc["db"] = "stats_questions"
                doc["_id"] = str(random.randint(10000, 99999))
                
            selected_questions.extend(stats_questions)

        sample_size = min(num_wof_clues, questions_per_round - len(selected_questions))
        if sample_size > 0:
            wof_collection = db["wof_questions"]
            pipeline_wof = [
                {"$match": {"_id": {"$nin": list(recent_question_ids["wof"])}}},
                {"$sample": {"size": sample_size}}  # Apply sampling on the filtered subset
            ]
            wof_questions = await wof_collection.aggregate(pipeline_wof).to_list(length=sample_size)

            for doc in wof_questions:
                doc["db"] = "wof_questions"
                
            selected_questions.extend(wof_questions)
            question_ids_to_store["wof"].extend(doc["_id"] for doc in wof_questions)
 
        sample_size = min(num_mysterybox_clues, questions_per_round - len(selected_questions))
        if sample_size > 0:
            mysterybox_collection = db["mysterybox_questions"]
            pipeline_mysterybox = [
                {"$match": {"_id": {"$nin": list(recent_question_ids["mysterybox"])}}},
                {"$sample": {"size": sample_size}}  # Apply sampling on the filtered subset
            ]
            mysterybox_questions = await mysterybox_collection.aggregate(pipeline_mysterybox).to_list(length=sample_size)

            for doc in mysterybox_questions:
                doc["db"] = "mysterybox_questions"
            
            selected_questions.extend(mysterybox_questions)
            question_ids_to_store["mysterybox"].extend(doc["_id"] for doc in mysterybox_questions)
        
        sample_size = max(questions_per_round - len(selected_questions), 0)
        if sample_size > 0:
            trivia_collection = db["trivia_questions"]

            if image_questions == False:
                # Define a list of substrings to exclude in URLs
                excluded_url_substring = "http"
                pipeline_trivia = [
                    {
                        "$match": {
                            "_id": {"$nin": list(recent_question_ids["general"])},
                            "category": {"$nin": categories_to_exclude},
                            "$or": [
                                {"url": {"$not": {"$regex": excluded_url_substring}}} 
                            ]
                        }
                    },
                    {
                        "$group": {
                            "_id": "$category",
                            "questions": {"$push": "$$ROOT"}  # Push full document to each category group
                        }
                    },
                    {"$unwind": "$questions"},  # Unwind the limited question list for each category back into individual documents
                    {"$replaceRoot": {"newRoot": "$questions"}},  # Flatten to original document structure
                    {"$sample": {"size": sample_size}}  # Sample from the resulting limited set
                ]
                
            else:
                pipeline_trivia = [
                    {"$match": {"_id": {"$nin": list(recent_question_ids["general"])}, "category": {"$nin": categories_to_exclude}}},
                    {
                        "$group": {
                            "_id": "$category",
                            "questions": {"$push": "$$ROOT"}  # Push full document to each category group
                        }
                    },
                    {"$unwind": "$questions"},  # Unwind the limited question list for each category back into individual documents
                    {"$replaceRoot": {"newRoot": "$questions"}},  # Flatten to original document structure
                    {"$sample": {"size": sample_size}}  # Sample from the resulting limited set
                ]

            trivia_questions = await trivia_collection.aggregate(pipeline_trivia).to_list(length=sample_size)

            for doc in trivia_questions:
                doc["db"] = "trivia_questions"
                
            selected_questions.extend(trivia_questions)
            question_ids_to_store["general"].extend(doc["_id"] for doc in trivia_questions)

        
        # Shuffle the combined list of selected questions
        random.shuffle(selected_questions)

        # Store question IDs in MongoDB (batch operation)
        await store_all_question_ids(question_ids_to_store)

        final_selected_questions = [
            (doc["category"], doc["question"], doc["url"], doc["answers"], doc["db"], doc["_id"])
            for doc in selected_questions
        ]
                
        return final_selected_questions

    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Error selecting trivia and crossword questions: {e}")
        return []  # Return an empty list in case of failure


async def load_streak_data():
    global current_longest_answer_streak, current_longest_round_streak
    
    for attempt in range(max_retries):
        try:
            # Retrieve the current longest answer streak from MongoDB
            document_answer = await db.current_streaks_discord.find_one({"_id": "current_longest_answer_streak"})

            if document_answer is not None:
                current_longest_answer_streak = {
                    "user": document_answer.get("user"),
                    "user_id": document_answer.get("user_id"),
                    "streak": document_answer.get("streak")
                }
            else:
                # If the document is not found, set default values
                current_longest_answer_streak = {"user": None, "user_id": None, "streak": 0}

            # Retrieve the current longest round streak from MongoDB
            # Retrieve the current longest answer streak from MongoDB
            document_round = await db.current_streaks_discord.find_one({"_id": "current_longest_round_streak"})
            
            if document_round is not None:
                current_longest_round_streak = {
                    "user": document_round.get("user"),
                    "user_id": document_round.get("user_id"),
                    "streak": document_round.get("streak")
                }
            else:
                # If the document is not found, set default values
                current_longest_round_streak = {"user": None, "user_id": None,  "streak": 0}
                
        except Exception as e:
            sentry_sdk.capture_exception(e)
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {delay_between_retries} seconds...")
                await asyncio.sleep(delay_between_retries)
            else:
                print("Max retries reached. Data loading failed.")
                # Set to default values if loading fails
                current_longest_answer_streak = {"user": None, "user_id": None, "streak": 0}
                current_longest_round_streak = {"user": None, "user_id": None, "streak": 0}

async def fetch_and_cache_currency_data():
    """
    Fetch currency names and exchange rates from API and cache in MongoDB.
    Only fetches if data is older than 1 hour or doesn't exist.
    """
    try:
        db = await connect_to_mongodb()
        foreign_exchange_collection = db["foreign_exchange"]
        
        # Check if we have recent data (within 1 hour)
        now = datetime.datetime.now(datetime.UTC)
        recent_data = await foreign_exchange_collection.find_one(
            {"_id": "currency_data"},
            sort=[("last_updated", -1)]
        )
        
        if recent_data and recent_data.get("last_updated"):
            last_updated = recent_data["last_updated"]
            if isinstance(last_updated, datetime.datetime):
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=datetime.UTC)
                time_diff = now - last_updated
                if time_diff.total_seconds() < 3600:  # 1 hour in seconds
                    print("Currency data is recent, skipping API fetch")
                    return recent_data
        
        print("Fetching fresh currency data from API...")
        
        # Fetch currency data
        async with aiohttp.ClientSession() as session:
            # Get currency names (API key required)
            currencies_url = f"https://currencyapi.net/api/v1/currencies?key={currency_api_key}&output=JSON"
            async with session.get(currencies_url) as response:
                if response.status == 200:
                    currencies_data = await response.json()
                    if currencies_data.get('valid'):
                        currency_names = currencies_data.get('currencies', {})
                    else:
                        print("Invalid API response for currency names")
                        return None
                else:
                    print(f"Failed to fetch currency names: {response.status}")
                    return None
            
            # Get exchange rates (API key required)
            rates_url = f"https://currencyapi.net/api/v1/rates?key={currency_api_key}&base=USD&output=JSON"
            async with session.get(rates_url) as response:
                if response.status == 200:
                    rates_data = await response.json()
                    if rates_data.get('valid'):
                        exchange_rates = rates_data.get('rates', {})
                    else:
                        print("Invalid API response for exchange rates")
                        return None
                else:
                    print(f"Failed to fetch exchange rates: {response.status}")
                    return None
        
        # Combine data
        currency_data = {
            "_id": "currency_data",
            "currency_names": currency_names,
            "exchange_rates": exchange_rates,
            "base_currency": "USD",
            "last_updated": now
        }
        
        # Cache in MongoDB
        await foreign_exchange_collection.replace_one(
            {"_id": "currency_data"},
            currency_data,
            upsert=True
        )
        
        print(f"Successfully cached {len(currency_names)} currencies and {len(exchange_rates)} exchange rates")
        return currency_data
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Error fetching currency data: {e}")
        return None

async def get_cached_currency_data():
    """
    Get currency data from cache, fetch fresh if needed.
    """
    try:
        db = await connect_to_mongodb()
        foreign_exchange_collection = db["foreign_exchange"]
        
        # Try to get cached data first
        cached_data = await foreign_exchange_collection.find_one({"_id": "currency_data"})
        
        if not cached_data:
            print("No cached currency data found, fetching fresh data...")
            return await fetch_and_cache_currency_data()
        
        # Check if data is stale (older than 1 hour)
        now = datetime.datetime.now(datetime.UTC)
        last_updated = cached_data.get("last_updated")
        
        if last_updated:
            if isinstance(last_updated, datetime.datetime):
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=datetime.UTC)
                time_diff = now - last_updated
                if time_diff.total_seconds() >= 3600:  # 1 hour
                    print("Currency data is stale, fetching fresh data...")
                    return await fetch_and_cache_currency_data()
        
        return cached_data
        
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Error getting cached currency data: {e}")
        return None

def get_currency_name(currency_code, currency_data):
    """
    Get the full name of a currency from its 3-letter code.
    """
    if not currency_data or not currency_data.get("currency_names"):
        return currency_code
    
    currency_names = currency_data["currency_names"]
    return currency_names.get(currency_code, currency_code)

def print_selected_questions(selected_questions):
    """Prints the selected questions in a cleaner format."""
    for i, question_data in enumerate(selected_questions, start=1):
        category = question_data[0]  # Category
        question = question_data[1]  # Question
        answers = question_data[3] # Answers
        # Format and print the question and answers
        print(f"{i}. [{category}] {question} [{', '.join(answers)}]")


async def round_start_messages():
    top_users = await db.top_users_discord.find().to_list(length=None)  # or set a limit if needed
    sovereign_docs = await db.hall_of_sovereigns_discord.find().to_list(length=None)
    sovereigns = {doc['user'] for doc in sovereign_docs}

    messages = []
    for user in top_users:
        username = user.get('user')
        top_count = user.get('top_count')

        # If the user is in the Hall of Sovereigns, only show the message if top_count == 6
        if username in sovereigns:
            if top_count == 6:
                await safe_send(channel, f"👑  {username} is #1 across the board. We bow to you.\n\n▶️ [Live trivia stats available](https://94mes.com)\n")
        else:
            # For users not in the Hall of Sovereigns, show all applicable messages
            if top_count == 6:
                await safe_send(channel, f"👑  {username} is #1 across the board. We bow to you.\n\n▶️ [Live trivia stats available](https://94mes.com)\n")
            elif top_count == 5:
                await safe_send(channel, f"🔥​  {username} is on fire! Only 1 leaderboard left.\n\n▶️ [Live trivia stats available](https://94mes.com)\n")
            elif top_count == 4:
                await safe_send(channel, f"🌡️  {username} is heating up! Only 2 leaderboards left.\n\n▶️ [Live trivia stats available](https://94mes.com)\n")
    return None


def to_superscript(num):
    return ''.join(superscript_map[digit] for digit in str(num))


def normalize_superscripts(text):
    return ''.join(reverse_superscript_map.get(char, char) for char in text)


def generate_and_render_derivative_image():
    # Randomly select two unique powers from {1, 2, 3}
    powers = sorted(random.sample([1, 2, 3], 2), reverse=True)
    content_uri = True
    
    terms = []
    derivative_terms = []

    # Construct polynomial and derivative terms for the selected powers
    for power in powers:
        coef = random.randint(1, 9)  # Coefficients between 1 and 9
        coef_str = str(coef) if coef != 1 else ""  # Omit "1" as a coefficient unless constant

        # Construct polynomial term with superscript exponents
        if power == 1:
            terms.append(f"{coef_str}x")  # No exponent shown for power of 1
            derivative_terms.append(f"{coef}")
        else:
            terms.append(f"{coef_str}x{to_superscript(power)}")  # Display higher powers with superscript
            derivative_terms.append(f"{coef * power}x{to_superscript(power - 1) if power > 2 else ''}")

    # Join the terms for both polynomial and derivative strings
    polynomial = " + ".join(terms)
    derivative = " + ".join(derivative_terms) if derivative_terms else "0"

    print(f"Polynomial: {polynomial}")
    print(f"Derivative: {derivative}")

    # Define the font path relative to the current script
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")

    # Create a blank image
    img_width, img_height = 600, 150
    img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Load the font
    font_size = 48
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None, None, None

    # Draw the polynomial text in the center
    text_bbox = draw.textbbox((0, 0), polynomial, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2
    draw.text((text_x, text_y), polynomial, fill=(255, 255, 0), font=font)

    # Save the image to a bytes buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  # Move the pointer to the beginning of the buffer

    return image_buffer, derivative, polynomial
  
    
def generate_and_render_linear_problem():
    # Generate coefficients ensuring no value is zero
    while True:
        a = random.choice([i for i in range(-10, 11) if i != 0])  # Coefficient of x (-10 to 10, excluding 0)
        x = random.choice([i for i in range(-20, 21) if i != 0])  # Integer solution (-20 to 20, excluding 0)
        b = random.choice([i for i in range(-20, 21) if i != 0])  # Constant term (-20 to 20, excluding 0)
        if a != 0 and x != 0 and b != 0:
            break

    question_text = f"Solve for 'x' in the equation below."

    # Compute the constant on the other side of the equation
    c = a * x + b

    # Format the coefficient of x
    if a == 1:
        a_str = ""  # Ignore 1
    elif a == -1:
        a_str = "-"  # Use only "-"
    else:
        a_str = str(a)

    # Formulate the problem as a linear equation
    problem = f"{a_str}x {'+' if b >= 0 else '-'} {abs(b)} = {c}"
    solution = f"{x}"

    print(f"Problem: {problem}")
    print(f"Solution: {solution}")

    # Define the font path relative to the current script
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")

    # Create a blank image
    img_width, img_height = 600, 150
    img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Load the font
    font_size = 48
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None, None, None, None

    # Draw the problem text in the center in light purple
    text_bbox = draw.textbbox((0, 0), problem, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2
    draw.text((text_x, text_y), problem, fill=(200, 162, 200), font=font)  # Light purple color

    # Save the image to a bytes buffer
    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  # Move the pointer to the beginning of the buffer

    return image_buffer, question_text, solution, problem
  

def generate_and_render_polynomial(type):
    content_uri = True
    zero1 = random.choice([i for i in range(-9, 10) if i != 0])
    zero2 = random.choice([i for i in range(-9, 10) if i != 0 and i != zero1])

    sum_zeroes = zero1 + zero2
    product_zeroes = zero1 * zero2
    factor1 = f"(x {'+' if zero1 < 0 else '-'} {abs(zero1)})"
    factor2 = f"(x {'+' if zero2 < 0 else '-'} {abs(zero2)})"
    factor1_mod = f"x {'+' if zero1 < 0 else '-'} {abs(zero1)}"
    factor2_mod = f"x {'+' if zero2 < 0 else '-'} {abs(zero2)}"
    
    if abs(sum_zeroes) == 1:
        sum_term = ""
    else:
        sum_term = abs(sum_zeroes)

    if sum_term == 0:
        polynomial = f"x² {'+' if product_zeroes >= 0 else '-'} {abs(product_zeroes)}"
    else:
        polynomial = f"x² {'-' if sum_zeroes >= 0 else '+'} {sum_term}x {'+' if product_zeroes >= 0 else '-'} {abs(product_zeroes)}"
    
    print(f"Polynomial: {polynomial}")

    if type == "zeroes sum":
         print(f"Sum of zeroes: {sum_zeroes * -1}")
    elif type == "zeroes product":
         print(f"Product of zeroes: {product_zeroes}")
    elif type == "zeroes":
         print(f"Zeroes: {zero1}, {zero2}")
    elif type == "factors":
         print(f"Factored: {factor1}{factor2}, {factor2}{factor1}")
    else:
        print("Wrong type passed in to polynomial function")

    font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")

    img_width, img_height = 600, 150
    img = Image.new('RGB', (img_width, img_height), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_size = 48
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Error: Font file not found at {font_path}")
        return None, None, None

    text_bbox = draw.textbbox((0, 0), polynomial, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2
    draw.text((text_x, text_y), polynomial, fill=(200, 162, 200), font=font) 

    image_buffer = io.BytesIO()
    img.save(image_buffer, format='PNG')
    image_buffer.seek(0)  
 
    if image_buffer:
        if type == "zeroes sum":
            sum_zeroes_invert = sum_zeroes * -1
            return image_buffer, str(int(sum_zeroes_invert)), polynomial
        elif type == "zeroes product":
            return image_buffer, str(int(product_zeroes)), polynomial
        elif type == "zeroes":
            zeroes_str = [
                f"{zero1} and {zero2}",
                f"{zero2} and {zero1}",
                f"{zero1}, {zero2}",
                f"{zero2}, {zero1}",
                f"{zero1} {zero2}",
                f"{zero2} {zero1}"
            ]
            return image_buffer, zeroes_str, polynomial
        elif type == "factors":
            factored_str = [
                f"{factor1}{factor2}",
                f"{factor2}{factor1}",
                f"{factor1_mod}{factor2_mod}",
                f"{factor2_mod}{factor1_mod}"
            ]
            return image_buffer, factored_str, polynomial
    else:
        print("Failed to upload the image to Matrix.")


async def round_preview(selected_questions):
    numbered_blocks = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    message = "\n🔮 **Next Round Preview** 🔮\n"

    for i, question_data in enumerate(selected_questions):
        trivia_category = question_data[0]
        trivia_url = question_data[2]
        number_block = numbered_blocks[i] if i < len(numbered_blocks) else f"{i + 1}."
        line = f"{number_block} {get_category_title(trivia_category, trivia_url)}\n"
        message += line
    message += "\n\u200b\n\u200b"

    await safe_send(channel, message.rstrip())


def get_category_title(trivia_category, trivia_url):
    emoji_lookup = {
        "Mystery Box or Boat": "🎁🛳️",
        "Famous People": "👑🧑‍🎤",
        "People": "🙋‍♂️🙋‍♀️",
        "Celebrities": "💃🕺",
        "Anatomy": "🧠🫀",
        "Characters": "🧙‍♂️🧛",
        "Music": "🎶🎸",
        "Art & Literature": "🎨📚",
        "Chemistry": "🧪⚗️",
        "Business": "💼📈",
        "Rebus Puzzle": "🤔🖼️",
        "Cars & Other Vehicles": "🚗🛩️",
        "Geography": "🧭🗺️",
        "Mathematics": "➕➗",
        "Statistics": "📊🔢",
        "Physics": "⚛️🍎",
        "Science & Nature": "🔬🌺",
        "Language": "🗣️🔤",
        "English Grammar": "📝✏️",
        "Astronomy": "🪐🌙",
        "Logos": "🏷️🔍",
        "The World": "🌎🌍",
        "Economics & Government": "💵⚖️",
        "Toys & Games": "🧸🎲",
        "Food & Drinks": "🍕🍹",
        "Geology": "🪨🌋",
        "Tech & Video Games": "💻🎮",
        "Video Games": "💻🎮",
        "Flags": "🏳️🏴",
        "Miscellaneous": "🔀✨",
        "Biology": "🧬🦠",
        "Earth Science": "🌎🔬",
        "Superheroes": "🦸‍♀️🦸",
        "Television": "📺🎥",
        "Pop Culture": "🎉🌟",
        "History": "📜🕰️",
        "Movies": "🎬🍿",
        "TV Shows": "📺🎥",
        "Religion & Mythology": "🛐🐉",
        "Sports & Leisure": "⚽🌴",
        "Politics & History": "🏛️📜",
        "Sports": "🏈⚾",
        "Sports & Games": "⚽🎮",
        "World Culture": "🎭🗿",
        "General Knowledge": "📚💡",
        "Anything": "🌐🔀",
        "Crossword": "📰✏️",
        "English": "🇬🇧🗣️",
        "Philippines": "🇵🇭🏝️",
        "Renaissance": "🏰🎨",
        "Fashion Japan": "👘🇯🇵",
        "Spring": "🌸🌱",
        "Game Of Thrones": "🐉⚔️",
        "Earth Day": "🌍🌱",
        "Human Body": "🫀🦴",
        "Film": "🎥🎞️",
        "South Park": "📺🤣",
        "Beer": "🍺🍻",
        "Animation": "🎨📽️",
        "Casino": "🎰♠️",
        "1970s": "🕺📻",
        "Baking": "🧁🥣",
        "Australia": "🇦🇺🦘",
        "Shopping": "🛍️🛒",
        "Books & Publications": "📚📰",
        "Chicago": "🌆🍕",
        "World War 1": "🌍⚔️",
        "For Seniors": "👴👵",
        "Ice Cream": "🍦🍨",
        "Military History": "⚔️🎖️",
        "Places & Travel": "🌍✈️",
        "Military History": "⚔️🎖️",
        "British History": "🏰🇬🇧",
        "Wimbledon": "🎾🏆",
        "1960s": "✌️🎶",
        "Celebrity Weddings": "💒💍",
        "Movie Villains": "😈🎥",
        "Leap Year": "📅🐸",
        "Back To The Future": "⌛🚗",
        "Olympics": "🏅🏟️",
        "Car Parts": "🚗🔧",
        "August": "☀️📆",
        "Fashion": "👗👠",
        "Italian Cuisine": "🍝🍕",
        "Toy Story": "🤠🧸",
        "The Simpsons": "🟨👨‍👩‍👧‍👦",
        "Taylor Swift": "🎤💖",
        "Fruit Vegetables": "🍏🥕",
        "Avengers": "🛡️⚡",
        "Nintendo": "🕹️🍄",
        "Playstation Games": "🎮⚙️",
        "Games": "🎮🎲",
        "Swedish Cuisine": "🥔🐟",
        "Disney Princess": "👑🏰",
        "Extreme Sports": "🏂🚵",
        "Halloween": "🎃👻",
        "Summer": "☀️🏖️",
        "Home Alone": "🏠🧒",
        "Pokemon": "⚡🐭",
        "Cartoons": "📺🐱",
        "Minecraft": "⛏️🐷",
        "Eminem": "🎤🍬",
        "Marvel": "🦸‍♂️🦹‍♂️",
        "Sherlock Holmes": "🕵️‍♂️🔎",
        "Board Games": "♟️🎲",
        "Architecture": "🏛️🏗️",
        "Art & Architecture": "🎨🏛️",
        "Weather": "☀️🌧️",
        "Albert Einstein": "🧠💡",
        "Serial Killer": "🔪😈",
        "Civil War": "⚔️🛡️",
        "New Year Halloween": "🎉🎃",
        "Horse Racing": "🐎🏁",
        "Breaking Bad": "🧪👨‍🔬",
        "1990s": "📟💾",
        "Premier League": "⚽🏆",
        "Classic Rock": "🎸🎶",
        "Alcohol": "🍺🥃",
        "Outer Space": "🚀🌌",
        "Family Guy": "👨‍👩‍👧‍👦😂",
        "Reality Stars": "🌟📺",
        "Fast Food": "🍔🍟",
        "Comics": "💥🦸",
        "Weird": "🤪🌀",
        "Sci Fi": "👽🚀",
        "Graphic Design": "💻🎨",
        "Decades": "⏳📅",
        "Animals": "🐾🐼",
        "Boxing": "🥊💥",
        "Oldies Music": "🎶🕰️",
        "Fourth Of July": "🇺🇸🎆",
        "Shrek": "🟢👑",
        "September": "🍂📅",
        "Quran": "📖🕋",
        "Queen": "👑👸",
        "Disney": "🏰🐭",
        "Indian Cuisine": "🍛🥘",
        "Book": "📖📚",
        "Modern History": "📜🌐",
        "Festivals": "🎉🎆",
        "Winter Olympics": "🏅🏂",
        "Horse": "🐎🌿",
        "Quentin Tarantino": "🎬🩸",
        "Inventions": "💡⚙️",
        "Baby Shower": "👶🎉",
        "New Girl": "🏠👱‍♀️",
        "Kings Queens": "🤴👸",
        "Sexuality": "🏳️‍🌈💖",
        "Canada": "🇨🇦🍁",
        "Agriculture": "🌱🚜",
        "1940s": "💣📻",
        "Questions For Kids": "❓👧",
        "Travel": "✈️🌍",
        "Rainforest": "🌧️🌳",
        "Presidents Day": "🇺🇸🏛️",
        "Star Wars": "🌌⚔️",
        "Power": "⚡💪",
        "Supernatural": "👻🌙",
        "X Files": "👽🕵️",
        "Technology": "💻🤖",
        "Google": "🔍🌐",
        "The Beatles": "🎸🇬🇧",
        "Car": "🚗🛣️",
        "India": "🇮🇳🪔",
        "Greek Mythology": "🏛️⚡",
        "World Cup": "🌍🏆",
        "Scandal": "📰😱",
        "Easter": "🐰🥚",
        "Brands": "🏷️💼",
        "Poetry": "📜🖋️",
        "Ncis": "🕵️‍♂️⚓",
        "Shakespeare": "📝🎭",
        "Country Music": "🤠🎶",
        "Europe": "🇪🇺🏰",
        "Musicals": "🎶🎭",
        "Entertainment": "🎉🎭",
        "Coffee": "☕🍪",
        "Apple": "🍎💻",
        "Airlines Airports": "✈️🛫",
        "Sea Life And Oceans": "🌊🐠",
        "Science Fiction": "👽🤖",
        "Soundtracks": "🎶🎞️",
        "Canada Day": "🇨🇦🎉",
        "Survivor": "🌴🏆",
        "War History": "💣📜",
        "Labor Day": "🛠️🇺🇸",
        "Mlb Baseball": "⚾🏟️",
        "Bar": "🍸🪑",
        "Valentines Day": "❤️💌",
        "One Piece": "🏴‍☠️🍖",
        "Mental Health": "🧠💚",
        "Friends": "👫💞",
        "Russian Cuisine": "🥟🍲",
        "Hannukkah": "🕎✨",
        "Hispanic Heritage Month": "🪗🎉",
        "The Office": "🏢😂",
        "China": "🇨🇳🐉",
        "Silly": "🤪🎉",
        "Stranger Things": "🚲🔦",
        "Pop Music": "🎤🎶",
        "Elvis": "🕺🎤",
        "Lord Of The Rings": "💍🔥",
        "Tennis": "🎾🏅",
        "Plants Trees": "🌱🌳",
        "Us Presidents": "🇺🇸👔",
        "Sharks": "🦈🌊",
        "Childrens Literature": "🧒📚",
        "Africa": "🌍🦁",
        "Comedy": "😂🎭",
        "Medical": "🩺💊",
        "Sesame Street": "🐤📺",
        "Easy": "😌✅",
        "Soap Opera": "📺💔",
        "Romance": "❤️🌹",
        "Pixar": "🤠🦖",
        "Wwe": "🤼‍♂️💥",
        "Poker": "♠️💰",
        "Beach": "🏖️🌅",
        "Holiday": "🎉🌴",
        "Teens": "🧑‍🎓🤸",
        "Twilight": "🧛‍♂️🌆",
        "Parks And Recreation": "🏞️😆",
        "Pregnancy": "🤰👶",
        "Oktoberfest": "🍺🇩🇪",
        "Roald Dahl": "📚🍫",
        "Wonders Of The World": "🏰🌍",
        "Canadian Cuisine": "🥞🍁",
        "Current Royals": "🤴👸",
        "Blockbusters": "💥🍿",
        "Cooking": "🍳🧑‍🍳",
        "Dinosaurs": "🦕🦖",
        "60s70s80s90s": "🎶📻",
        "4th grade  questions": "4️⃣❓",
        "Modern Family": "👨‍👩‍👧‍👦🏠",
        "Star Trek": "🖖🚀",
        "Winter": "❄️☃️",
        "Politics News": "🗞️⚖️",
        "Early Art": "🖼️🏺",
        "Stephen King": "🕯️😱",
        "Classical Music": "🎼🎻",
        "British Music": "🇬🇧🎶",
        "Seinfeld": "🏙️🤣",
        "Film Timings": "🎬⏰",
        "Candy": "🍬🍭",
        "European Championships": "🇪🇺🏆",
        "Cycling": "🚴‍♂️🚴‍♀️",
        "Asia": "🌏🏯",
        "Bob Marley": "🎶🇯🇲",
        "American Cuisine": "🍔🥧",
        "Us States": "🇺🇸📍",
        "Titanic": "🚢💔",
        "War": "⚔️💣",
        "Education": "🏫📚",
        "Fall": "🍂🍁",
        "Novels": "📚✒️",
        "5th grade": "5️⃣❓",
        "Nickelodeon": "📺🧒",
        "Authors": "🖋️📚",
        "2010s": "📱💻",
        "Horror Movie": "🔪😱",
        "Christmas  For Kids": "🎄🧸",
        "Riddle": "❓🧩",
        "Christmas": "🎄🎅",
        "Sitcom": "😂📺",
        "Nhl Hockey": "🏒🥅",
        "Solar System": "☀️🪐",
        "Michael Jackson": "🕺🪄",
        "Hobbies": "⚽🎨",
        "United States": "🇺🇸🗽",
        "Golf": "⛳🏌️‍♂️",
        "Continents Countries": "🌍🌎",
        "Nutrition Month": "🥦🍏",
        "Transport": "🚗🚇",
        "Hard": "💪🔨",
        "Beneath The Sea": "🌊🐙",
        "Bollywood": "💃🎥",
        "Thanksgiving": "🦃🍁",
        "Super Bowl": "🏈🏆",
        "New Year": "🎆🍾",
        "1950s": "🎩🎶",
        "Mammals": "🐒🐘",
        "Nba Teams": "🏀🏅",
        "Crime": "🚓🕵️",
        "Oscars Awards": "🏆🎞️",
        "St Patrick S Day": "🍀🇮🇪",
        "Medicine": "💊🩺",
        "Science & Medicine": "🔬🧬",
        "Famous Authors": "🖋️📚",
        "Nfl": "🏈🏟️",
        "Funny": "🤣😜",
        "New York": "🗽🌃",
        "Fashion Design": "👗✂️",
        "Australian History": "🇦🇺📜",
        "Internet": "🌐💻",
        "Brands Worldwide": "🌐🏷️",
        "Gen Z": "📱😎",
        "Capital Cities": "🌆🗺️",
        "Mario": "👨‍🔧🍄",
        "2000s": "💻📱",
        "Back To School": "🎒🏫",
        "Philosophers": "🤔📜",
        "Spelling": "🔤📝",
        "Bible": "📖✝️",
        "Nascar": "🏁🏎️",
        "Current Affairs": "📰🌍",
        "London": "🇬🇧🎡",
        "Monday": "📅😴",
        "Us Tv": "🇺🇸📺",
        "Electricity": "⚡💡",
        "Classic Tv": "📺🕰️",
        "North America": "🌎🏒",
        "Top Gun": "✈️🕶️",
        "Harry Potter": "⚡🧙‍♂️",
        "Memorial Day": "🇺🇸🪖",
        "Actors Actresses": "🎭🎬",
        "Actor / Actress": "🎭🎬",
        "Royal Family": "👑👨‍👩‍👧‍👦",
        "Uk Football": "🇬🇧⚽",
        "Batman": "🦇🦸‍♂️",
        "Black History": "✊🏿📜",
        "Encanto": "🏠💃",
        "Middle School": "🏫👩‍🎓",
        "Reality Tv": "📺😜",
        "Jurassic Park": "🦕🎢",
        "Classic Movies": "🎞️🏆",
        "Rock Roll": "🎸🤘",
        "1980s": "💾📼",
        "Design": "🎨🖌️",
        "James Bond": "🤵🔫",
        "Monopoly": "💰🏠",
        "Sunset": "🌇🌅",
        "Hip Hop Rap": "🎤🔥",
        "Dogs": "🐶🦴",
        "Ancient Medieval History": "🏰⚔️",
        "Musicals Theatre": "🎭🎵",
        "Non Fiction": "📚📖",
        "Texas": "🤠🌵",
        "Hamilton": "🎩🎼",
        "World War 2": "💣🌍",
        "Ufc Martial Arts": "🥋🥊",
        "Humanities": "📖🎨",
        "Brain-Teasers": "🧠❓",
        "Rated": "⭐🔞",
        "Newest": "🆕✨",
        "Art": "🎨🖌️",
        "Drinks": "🍹🥂",
        "Religion": "🛐🙏",
        "Mathematics & Geometry": "➕📐",
        "Technology & Video Games": "💻🕹️",
        "Tourism And World Cultures": "✈️🗿",
        "Superhero": "🦸🦹",
        "Nature": "🌱🌳",
        "Worldwide History": "🌐📜",
        "Uk History": "🇬🇧📜",
        "Ocean": "🌊🐠",
        "Food & Drink": "🍽️🍸",
        "Space": "🚀🪐",
        "Science": "🔬🧪",
        "Tv": "📺🍿",
        "TV": "📺🍿",
        "People & Places": "👨‍👩‍👧‍👦🏙️",
        "Toys": "🧸🪀",
        "Food": "🍔🥗",
        "Maths": "➕🔢",
        "Elements": "🔥💧",
        "History & Holidays": "📜🎉",
        "Art And Literature": "🎨📚",
        "For-Kids": "👧🧩",
        "World": "🌍🌏",
        "Video-Games": "🎮👾",
        "Science-Technology": "🔬🤖",
        "Literature": "📚✒️",
        "Religion-Faith": "🛐📿",
        "Mathematics: Algebra": "🤓➕",
        "Mathematics: Trigonometry": "📐📊",
        "Mathematics: Mean": "➗📈",
        "Mathematics: Median": "🔢📊",
        "Mathematics: Polynomials": "📉✖️",
        "Mathematics: Bases": "2️⃣🔟",
        "Mathematics: Derivatives": "📉♾️"  
    }

    # Check if the question URL is "jeopardy"
    if trivia_url.lower() == "jeopardy":
        return f"{trivia_category} 🟦🇯"
    # Otherwise, get the emojis based on the lookup table, defaulting to the category itself if not found
    emojis = emoji_lookup.get(trivia_category, "❓❔")
    return f"{trivia_category} {emojis}"


async def get_player_selected_question(questions, round_winner, winner_id):
    num_of_questions = len(questions)
    numbered_blocks = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


    message = f"\u200b\n🎯 **<@{winner_id}>**, pick the question number:\n\n"
    for i, question_data in enumerate(questions):
        trivia_category = question_data[0]
        trivia_url = question_data[2]
        number_block = numbered_blocks[i] if i < len(numbered_blocks) else f"{i + 1}."
        message += f"{number_block} {get_category_title(trivia_category, trivia_url)}\n"
    message += f"\u200b"

    await safe_send(channel, message)

    def check(m):
        return m.author.id == winner_id and m.channel == channel

    end_time = asyncio.get_event_loop().time() + magic_time
    while True:
        timeout = end_time - asyncio.get_event_loop().time()
        if timeout <= 0:
            break

        try:
            response = await asyncio.wait_for(bot.wait_for("message", check=check), timeout=timeout)
            content = response.content.strip()
            digits = ''.join(filter(str.isdigit, content))

            if digits:
                num = int(digits)
                if 1 <= num <= num_of_questions:
                    try:
                        await response.add_reaction("✅")
                    except discord.HTTPException:
                        pass  
                    return num  
        except asyncio.TimeoutError:
            break
        except Exception as e:
            print(f"Error processing player selection: {e}")

    return 1 


async def refill_question_slot(questions, old_question):
    questions.remove(old_question)
    new_question = await get_random_trivia_question()
    questions.append(new_question)


async def get_random_trivia_question():
    global categories_to_exclude
    try:
        trivia_collection = db["trivia_questions"]
        recent_general_ids = await get_recent_question_ids_from_mongo("general")

        if image_questions == False:
            excluded_url_substring = "http"
            pipeline = [
                {
                    "$match": {
                        "_id": {"$nin": list(recent_general_ids)},
                        "category": {"$nin": categories_to_exclude},
                        "$or": [
                            {"url": {"$not": {"$regex": excluded_url_substring}}} 
                        ]
                    }
                },
                {
                    "$group": {
                        "_id": "$category",
                        "questions": {"$push": "$$ROOT"}  # Push full document to each category group
                    }
                },
                {"$unwind": "$questions"},  # Unwind the limited question list for each category back into individual documents
                {"$replaceRoot": {"newRoot": "$questions"}},  # Flatten to original document structure
                {"$sample": {"size": 1}}  # Sample from the resulting limited set
            ]
            
        else:
            pipeline = [
                {"$match": {"_id": {"$nin": list(recent_general_ids)}, "category": {"$nin": categories_to_exclude}}},
                {
                    "$group": {
                        "_id": "$category",
                        "questions": {"$push": "$$ROOT"}  # Push full document to each category group
                    }
                },
                {"$unwind": "$questions"},  # Unwind the limited question list for each category back into individual documents
                {"$replaceRoot": {"newRoot": "$questions"}},  # Flatten to original document structure
                {"$sample": {"size": 1}}  # Sample from the resulting limited set
            ]
        
        result = await trivia_collection.aggregate(pipeline).to_list(length=1)

        if result:
            selected_question = result[0]
            question_id = selected_question["_id"]
        
            # Store the ID in MongoDB to avoid re-selection in future rounds
            await store_question_ids_in_mongo([question_id], "general")

            final_selected_question = (
                selected_question["category"],
                selected_question["question"],
                selected_question["url"],
                selected_question["answers"],
                "trivia_questions",
                selected_question["_id"]
            )
            
            return final_selected_question
        else:
            print("No available questions found.")
            return None
            
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Error selecting random replacement question: {e}")
        return None  # Return an empty list in case of failure


async def start_trivia():
    global target_room_id, bot_user_id, bearer_token, question_time, questions_per_round, time_between_questions, filler_words
    global scoreboard, current_longest_round_streak, current_longest_answer_streak
    global headers, params, filter_json, since_token, round_count, selected_questions, magic_number
    global previous_question, current_question
    global db
    global question_responders, round_responders
    global question_asked_start, question_asked_end
    
    try:

        #await sync_bumper_king_with_role()  # Only sync at startup
        await load_streak_data()
        await load_previous_question()

        

        round_winner = current_longest_round_streak.get("user")
        round_winner_id = current_longest_round_streak.get("user_id")
        print(round_winner)
        print(round_winner_id)


        # Try to load questions from previous round (in case bot restarted between rounds)
        selected_questions = await load_selected_questions_from_db()

        # If no saved questions, select new ones
        if selected_questions is None or len(selected_questions) == 0:
            selected_questions = await select_trivia_questions(questions_per_round)  #Pick the initial question set

        while True:  # Endless loop     
            reset_embed_color()  
            current_time = time.time()
            
            await load_parameters()

            await sync_bumper_king_with_role() 
            #await get_survey_results()
            scoreboard.clear()
            fastest_answers_count.clear()
            #await ask_feud_question("TheOkraG", "cooperative", 591861826690613248)
            #await ask_jigsaw_challenge("The Creator", 591861826690613248)
            #await ask_border_challenge("The Creator", 591861826690613248)
            #await ask_ranker_people_challenge("TheOkraG", 1)
            #await ask_ranker_list_question("TheOkraG", 591861826690613248, 1)
            #await ask_list_question("TheOkraG", 591861826690613248, 3)
            #await ask_chaos_challenge("TheOkraG",591861826690613248, 23)
            #await ask_tally_challenge("TheOkraG",591861826690613248, 3)
            #await ask_stock_challenge("TheOkraG",591861826690613248, 3)
            #await ask_chess_challenge("TheOkraG",591861826690613248, 3)
            #await ask_search_challenge("TheOkraG",591861826690613248, 3)
            #await ask_lyric_challenge("TheOkraG",591861826690613248, 7)
            #await ask_soundfx_challenge("TheOkraG",591861826690613248, 7)
            

            round_responders.clear()  # Reset round responders
            round_data["questions"] = []

            if random.random() < 0:  # random.random() generates a float between 0 and 1
                magic_number = random_number = random.randint(1000, 9999)
                print(f"Magic number is {magic_number}")
                send_magic_image(magic_number)
            elif image_questions == True:
                selected_gif_url = await select_intro_image_url()         
                await safe_send(channel, content="\u200b\n\u200b\n🎉🤹‍♂️ **Live Trivia & Games for Discord!**\n\u200b", embed=discord.Embed().set_image(url=selected_gif_url))

            await asyncio.sleep(5)

            start_message = f"\u200b\n✨🧪 **NEW** from the **Okra Lab**! 🧪✨\n"
            
            start_message += f"\n👂➡️ **Hear Here** [Audio Mini-Game]"

            start_message += "\n\u200b"

            await safe_send(channel, start_message)
            await asyncio.sleep(5)
            
            
            start_message = f"\u200b\n\u200b\n⏩ Starting a **{questions_per_round} question** round! ⏩\n\u200b\n\u200b"

            start_message += f"\u200b\n🚩 Type **#flag** to report question\n"
            start_message += f"🗝️ Type **#perks** to unlock perks\n\u200b"

            if current_longest_round_streak["user"] is not None and await get_coffees(current_longest_round_streak["user_id"]) > 0:
                start_message += f"\n🕹️ **{current_longest_round_streak["user"]}** can toggle modes mid-game"
                start_message += f"\n↔️ **#[command]** any time during round\n\u200b"
                
            await safe_send(channel, start_message)
            await asyncio.sleep(3)
            

            start_message = "\u200b\n🏁 **Get ready** 🏁\n\u200b"
            await safe_send(channel, start_message)

            #await round_start_messages()
            await asyncio.sleep(5)
                
            # Randomly select n questions
            print_selected_questions(selected_questions)
            
            question_number = 1
            while question_number <= questions_per_round:
                randomize_embed_color()
                question_responders.clear()  # Reset question responders for the new question

                if god_mode and round_winner:
                    selected_index = await get_player_selected_question(selected_questions, round_winner, round_winner_id)
                    selected_question = selected_questions[selected_index - 1]
                    
                else:
                    selected_question = selected_questions[0]

                trivia_category, trivia_question, trivia_url, trivia_answer_list, trivia_db, trivia_id = selected_question

                current_question = {
                    "trivia_category": trivia_category,
                    "trivia_question": trivia_question,
                    "trivia_url": trivia_url,
                    "trivia_answer_list": trivia_answer_list,
                    "trivia_db": trivia_db,
                    "trivia_id": trivia_id
                }

                
                collected_responses.clear()
                question_asked_start = time.time()
                question_asked_end = question_asked_start + question_time
                question_ask_time, new_question, new_solution = await ask_question(trivia_category, trivia_question, trivia_url, trivia_answer_list, question_number)
                await asyncio.sleep(question_time)
                #await safe_send(channel, "\u200b\n🛑 TIME 🛑\n\u200b")
                
                solution_list = []

                if new_solution is None:
                    solution_list = trivia_answer_list
                elif isinstance(new_solution, list):
                    solution_list = new_solution
                else:
                    solution_list = [new_solution]        
                    
                await check_correct_responses_delete(question_ask_time, solution_list, question_number, collected_responses, trivia_category, trivia_url)
                
                if not yolo_mode or question_number == questions_per_round:
                    await show_standings()

                await refill_question_slot(selected_questions, selected_question)

                await asyncio.sleep(time_between_questions)  # Small delay before the next question
                
                question_number = question_number + 1
                previous_question = {
                    "trivia_category": trivia_category,
                    "trivia_question": trivia_question,
                    "trivia_url": trivia_url,
                    "trivia_answer_list": trivia_answer_list,
                    "trivia_db": trivia_db,
                    "trivia_id": trivia_id
                }

                await save_data_to_mongo("previous_question_discord", "previous_question", previous_question)
                
            reset_embed_color()
            round_winner, winner_points, round_winner_id = await determine_round_winner()
            await update_round_streaks(round_winner, round_winner_id)

            round_count += 1
        
            await asyncio.sleep(10)
            await process_round_options(round_winner, winner_points, round_winner_id)
            
            if round_count % 3 == 0:
                message = f"\u200b\n🧘‍♂️ A short breather. Relax, stretch, meditate.\n🎨 Live Trivia is a pure hobby effort.\n\n🙋 Help make it better!\n💡 [Submit Feedback](https://forms.gle/iWvmN24pfGEGSy7n7)\n\n🗣️ Like it? Spread the word!\n⭐ [Leave a Review](https://disboard.org/review/create/1367682586079395902)\u200b\n\n"
                await safe_send(channel, message)
                await asyncio.sleep(20)

            message = f"\u200b\n\u200b\n🥒 **Unlock perks? Become an Okran!**\n💚 [Join Role Subscriptions](https://discord.com/channels/1367682586079395902/role-subscriptions)\n"
            message += f"\n🛒 **Score Live Trivia merch featuring Okra!**\n👕 [Shop Merch](https://merch.94mes.com)\n\u200b"
            await safe_send(channel, message)
            
            selected_questions = await select_trivia_questions(questions_per_round)  #Pick the next question set
            await save_selected_questions_to_db(selected_questions)  # Save for next round in case of restart
            
            await asyncio.sleep(10)
            
            await round_preview(selected_questions)
            
            
            #if len(scoreboard) >= 1000:
            #    await ask_survey_question()

            if len(active_tournaments) == 0: 
                await end_of_round()
            
            await asyncio.sleep(10)  # Adjust this time to whatever delay you need between rounds
            
            await check_bump_status()
            if bumped_status == False:
                await get_bump_url_from_s3()
                await asyncio.sleep(10)

    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Error occurred: {e}")
        traceback.print_exc()  # Print the stack trace of the error
        print("Restarting the trivia bot in 10 seconds...")
        await asyncio.sleep(10)  


async def get_bump_url_from_s3():
    bucket_name = "triviabotwebsite"
    prefix = "bump/"
    
    session = aioboto3.Session()
    async with session.client("s3") as s3:
        response = await s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    
    # Extract file keys
    files = [item['Key'] for item in response.get('Contents', []) if item['Key'].lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
    random_file = random.choice(files)
    encoded_filename = quote(random_file)

    public_url = f"https://{bucket_name}.s3.amazonaws.com/{encoded_filename}"
    
    message = (
        f"\u200b\n🚨⏫ BUMP ALERT ⏫🚨\n\n"
        f"Type 👉 **/bump** 👈 now to boost our trivia server and gain the title of...\n\n👑🍔 **Bumper King** 🍔👑!\n\u200b"
    )

    await safe_send(channel, content=message, embed=discord.Embed().set_image(url=public_url))




def print_round_settings():
    global time_between_questions, ghost_mode, god_mode, yolo_mode
    global image_questions, marx_mode
    global blind_mode, sniper_mode, cloak_mode

    print(f"🛠️ Current Round Settings:")
    print(f"⏱️  Time Between Questions: {time_between_questions}")
    print(f"👻  Ghost Mode: {ghost_mode}")
    print(f"🎖️  God Mode: {god_mode}")
    print(f"🔥  Yolo Mode: {yolo_mode}")
    print(f"🖼️  Image Questions: {image_questions}")
    print(f"🔨  Marx Mode: {marx_mode}")
    print(f"🙈  Blind Mode: {blind_mode}")
    print(f"🧢🎤 Sniper Mode: {sniper_mode}")
    print(f"🫥🕶️ Cloak Mode: {cloak_mode}")

async def reset_round_options(reset_command, winner_id):
    global time_between_questions, ghost_mode, god_mode, yolo_mode, mirror_mode, echo_mode, image_questions, marx_mode, blind_mode, zen_mode, sniper_mode, cloak_mode, cloaked_user

    reset_success = False
    
    if "blind" in reset_command:
        blind_mode = not blind_mode
        reset_success = True
        if blind_mode:
            await safe_send(channel, content=f"🙈🚫 **{current_longest_round_streak['user']}** is blind to the truth. No answers will be shown.\n")
        else:
            await safe_send(channel, content=f"🙈✅ **{current_longest_round_streak['user']}** can see again! Answers will now be shown.\n")                

    if "marx" in reset_command:
        marx_mode = not marx_mode
        reset_success = True
        if marx_mode:
            await safe_send(channel, content=f"🚩🔨 **{current_longest_round_streak['user']}** is a commie. No celebrating right answers.\n")
        else:
            await safe_send(channel, content=f"💼💰 **{current_longest_round_streak['user']}** is a capitalist. Let's celebrate right answers.\n")
    
    if "yolo" in reset_command:
        yolo_mode = not yolo_mode
        reset_success = True
        if yolo_mode:
            await safe_send(channel, content=f"🤘🔥 Yolo. **{current_longest_round_streak['user']}** says 'don't sweat the small stuff'. No scores.\n")
        else:
            await safe_send(channel, content=f"🪑📚 Nolo. **{current_longest_round_streak['user']}** wants to play it by the rules. Back to scoring\n.")
    
    if "image" in reset_command:
        image_questions = not image_questions
        reset_success = True
        if image_questions:
            await safe_send(channel, content=f"❌📷 **{current_longest_round_streak['user']}** thinks a word is worth 1000 images.\n")
        else:
            await safe_send(channel, content=f"✅📷 **{current_longest_round_streak['user']}** thinks an image is worth 1000 words.\n")
    
    if "ghost" in reset_command:
        ghost_mode = not ghost_mode
        reset_success = True
        if ghost_mode:
            await safe_send(channel, content=f"\n👻🎃 **{current_longest_round_streak['user']}** says Boo! Your responses will disappear.\n✍️⚫ Start messages with **.** to avoid deletion.\n")
        else:
            await safe_send(channel, content=f"\n☀️📖 **{current_longest_round_streak['user']}** says Hello! Your responses will now remain.\n")

    if "dicktator" in reset_command:
        god_mode = not god_mode
        reset_success = True
        if god_mode:
            await safe_send(channel, content=f"\n🎖🍆 **{current_longest_round_streak['user']}** is a dick.\n")
        else:
            await safe_send(channel, content=f"\n🎖🫡 **{current_longest_round_streak['user']}** is not a dick.\n")
    
    if "sniper" in reset_command:
        sniper_mode = not sniper_mode
        reset_success = True
        if sniper_mode == True:
            await safe_send(channel, content=f"\n🧢🎤 **{current_longest_round_streak["user"]}** says 'You only get one shot, do not miss your chance.'\n")
        else:
            await safe_send(channel, content=f"\n⚾👽 **{current_longest_round_streak["user"]}** says 'Swing away Merrill (and everyone else)!'\n")

    if "cloak" in reset_command:
        cloak_mode = not cloak_mode
        reset_success = True
        if cloak_mode == True:
            cloaked_user = winner_id
            await safe_send(channel, content=f"\n🫥🕶️ **{current_longest_round_streak["user"]}** has put on their cloak.\n✍️⚫ Start messages with **.** to avoid deletion.\n")
        else:
            cloaked_user = None
            await safe_send(channel, content=f"\n🌞✨ **{current_longest_round_streak["user"]}** has taken off their cloak.\n")
        
    if any(str(i) in reset_command for i in range(3, 16)):
        delay_value = int(''.join(filter(str.isdigit, reset_command)))
        delay_value = max(3, min(delay_value, 15))
        time_between_questions = delay_value
        reset_success = True
        await safe_send(channel, content=f"⏱️⏳ **{current_longest_round_streak['user']}** has set {time_between_questions}s between questions.\n")

    #print_round_settings()
    return reset_success



def handle_sigterm(signum, frame):
    print("💀 Received SIGTERM. Shutting down gracefully...")
    exit(0)

BUMPER_ROLE_NAME = "👑🍔 Bumper King 🍔👑"

async def ensure_bumper_role(guild: discord.Guild) -> discord.Role:
    # First try to get the role by configured ID
    role = guild.get_role(BUMPER_KING_ROLE_ID)
    if role is not None:
        return role

    # Fallback: search by name
    role = discord.utils.get(guild.roles, name=BUMPER_ROLE_NAME)
    if role is None:
        role = await guild.create_role(name=BUMPER_ROLE_NAME, reason="Create Bumper King role")
    return role

async def assign_bumper_king(guild: discord.Guild, new_user_id: int | None):
    role = await ensure_bumper_role(guild)

    # remove from any current holder(s)
    for m in guild.members:
        if role in m.roles:
            try:
                await m.remove_roles(role, reason="Bumper crown transferred/cleared")
            except Exception as e:
                print(f"⚠️ remove role failed for {m.id}: {e}")

    if not new_user_id:
        return

    member = guild.get_member(new_user_id) or await guild.fetch_member(new_user_id)
    if not member:
        print("⚠️ New bumper not in guild (cannot assign role).")
        return

    try:
        await member.add_roles(role, reason="Bumper crown granted")
    except Exception as e:
        print(f"⚠️ add role failed: {e}")



def extract_bumper_from_message(message: discord.Message) -> tuple[int | None, str]:
    """
    Returns (user_id, display_name_in_this_guild) if found, else (None, "").
    Prefers interaction_metadata.user, falls back to interaction.user, then mentions.
    """
    user = None

    # Preferred (per deprecation warning)
    meta = getattr(message, "interaction_metadata", None)
    if meta and getattr(meta, "user", None):
        user = meta.user

    # Fallback (older field still present on your dump)
    if user is None:
        inter = getattr(message, "interaction", None)
        if inter and getattr(inter, "user", None):
            user = inter.user

    # Last resort: mentions
    if user is None and message.mentions:
        user = message.mentions[0]

    if not user:
        return None, ""

    # Resolve guild display name (nickname) if possible
    member = message.guild.get_member(user.id) if message.guild else None
    display = member.display_name if member else (getattr(user, "global_name", None) or user.name)
    return user.id, display


@bot.event
async def on_message(message):
    global collected_responses, question_asked_start, question_asked_end, bumped_status, bumper_king_id, bumper_king_name

    #if message.author == bot.user:
    #    return
    
    is_self = (message.author.id == bot.user.id)

    if is_self:
        return
    
    if "okra" in message.content.strip().lower() and emoji_mode == True and message.author.id != bot.user.id:
        if emoji_mode == True:
            await message.add_reaction("🥒")

    # Check if message should be handled by Okra Hunt escape room system
    if 'okra_hunt' in globals():
        try:
            if await okra_hunt.handle_message(message):
                return  # Message was handled by okra hunt, don't process further
        except Exception as e:
            print(f"Error in okra hunt handler: {e}")

    # Check if message should be handled by tournament system
    if 'tournament_manager' in globals():
        try:
            if tournament_manager.should_handle_message(message):
                if await tournament_manager.handle_message(message):
                    return  # Message was handled by tournament, don't process further
        except Exception as e:
            print(f"Error in tournament handler: {e}")

    if message.author.id == DISBOARD_BOT_ID:
        # Detect “Bump done!” (Disboard uses embeds; content is usually empty)
        bump_hit = False

        if "bump done" in (message.content or "").lower():
            bump_hit = True

        if not bump_hit and message.embeds:
            for emb in message.embeds:
                desc  = (emb.description or "").lower()
                title = (emb.title or "").lower()
                if "bump done" in desc or "bump done" in title:
                    bump_hit = True
                    break

        if bump_hit:
            user_id, display_name = extract_bumper_from_message(message)

            # update globals
            bumped_status = True
            bumper_king_id = str(user_id) if user_id else ""
            bumper_king_name = display_name or ""

            if bumper_king_name:
                gif_url = "https://triviabotwebsite.s3.us-east-2.amazonaws.com/okra/okra-burger-king.png"
                #await safe_send(channel, content =f"\u200b\n👑🍔 All hail **{bumper_king_name}**! They’ve claimed the **Bumper King** crown until the next bump!\n\u200b", embed=discord.Embed().set_image(url=gif_url))
                crown_embed = discord.Embed(
                    title="👑🍔 A New Bumper King! 🍔👑",
                    description=(
                        f"All hail **<@{bumper_king_id}>**! They’ve claimed the **Bumper King** crown until the next bump!\n\n"
                        f"💎 As **Bumper King**, you now unlock:\n\n"
                        f"• Access to all exclusive perks 🎁\n"
                        f"• Change your username color with `/okrafx` 🎨\n"
                    ),
                    color=discord.Color.gold()
                )
                crown_embed.set_image(url=gif_url)

                # Send as a separate message object you can manage
                crown_message = await channel.send(embed=crown_embed)
                await asyncio.sleep(3)

            # assign the crown role in this guild
            if message.guild and user_id:
                await assign_bumper_king(message.guild, user_id)

            # persist/log as you wish
            try:
                await update_bump_data()
            except TypeError:
                # if your update_bump_data() takes no args:
                await update_bump_data()



    if "#perks" in message.content.strip().lower() and message.author.id != bot.user.id:
        try:
            dm_channel = await message.author.create_dm()
    
            embed = discord.Embed(
                title="🔓✨ Unlock ALL Live Trivia Perks",
                url="https://discord.com/channels/1367682586079395902/role-subscriptions",
            )
            await dm_channel.send(embed=embed)
            return
        except Exception as e:
            await message.channel.send(f"\u200b\n{message.author.mention} ⚠️ I couldn't message you. Make sure your DMs are open.\n\u200b")
            print(f"Error sending DM: {e}")
            return

    if "#flag" in message.content.strip().lower() and collect_feedback_mode == True and message.author.id != bot.user.id and message.channel.id == channel_id:
        if emoji_mode == True:
            await message.add_reaction("🚩")
        await update_audit_question(current_question, message.content.strip(), message.author.display_name)
        return

    if message.content.startswith("#") and (message.author.id == current_longest_round_streak["user_id"] or message.author.id == okrag_id) and message.channel.id == channel_id:
        if await get_coffees(current_longest_round_streak["user_id"]) > 0:
            reset_command = message.content[1:] 
            if(await reset_round_options(reset_command, message.author)) == True:
                if emoji_mode == True:
                    if message.author.id == okrag_id:
                        await message.add_reaction("🙇")
                    else:
                        await message.add_reaction("🤙")
        else:
            await safe_send(channel, content=f"\n🙏😔 Sorry **{message.author.display_name}**. Only Okrans can toggle mid-game options 🥒️.\n")
            await message.add_reaction("😩")
        return
    
    if question_asked_start is None or question_asked_end is None or message.channel.id != channel_id:
        return

    # Check if the message is during the active question window
    now = message.created_at.timestamp()
    if question_asked_start <= now <= question_asked_end:
        collected_responses.append({
            "user_id": message.author.id,
            "display_name": message.author.display_name,
            "message_content": message.content,
            "response_time": now,
            "message": message  # Save the original message object for deletion if needed
        })
        
        ESCAPE_PREFIXES = (".", ",", "~")

        if (ghost_mode or (cloaked_user is not None and message.author.id == cloaked_user)) and not message.content.lstrip().startswith(ESCAPE_PREFIXES):
            try:
                await message.delete()
            except discord.Forbidden:
                print("Bot lacks permission to delete messages.")
            except discord.HTTPException as e:
                print(f"Failed to delete message: {e}")

    await bot.process_commands(message)


@bot.event
async def on_message_edit(before, after):
    if after.author == bot.user:
        return

    # Only react to edits in this specific channel
    if after.channel.id != channel_id:
        return
        
    if question_asked_start and question_asked_end:
        edited_time = after.edited_at.timestamp() if after.edited_at else time.time()
        if question_asked_start <= edited_time <= question_asked_end:
            try:
                await after.reply(
                    f"🛑 {after.author.mention}, edited messages are **NOT** accepted for trivia answers. "
                    "Your original answer is the only one that counts.",
                    mention_author=False
                )
            except discord.Forbidden:
                print("Bot lacks permission to reply to the edited message.")
            except Exception as e:
                print(f"Failed to reply to edited message: {e}")




def get_minigame_name(number):
    """Map mini game number to name"""
    game_map = {
        "0": "Wheel of Fortune",
        "1": "Wheel of Fortune",
        "2": "Wheel of Fortune",
        "3": "Wheel of Fortune",
        "4": "Wheel of Fortune",
        "5": "Wikipedia Roulette",
        "6": "Dictionary Roulette",
        "7": "Thesaurus Roulette",
        "8": "Where's Okra?",
        "9": "FeUd (Single Player)",
        "10": "FeUd Blitz",
        "11": "List Battle",
        "12": "Poster Blitz",
        "13": "Movie Mayhem",
        "14": "Missing Link",
        "15": "Famous Peeps",
        "16": "Ranker Lists",
        "17": "Magic EyeD",
        "18": "OkrAnimal",
        "19": "The Riddler",
        "20": "Word Nerd",
        "21": "Flag Fest",
        "22": "LyrIQ",
        "23": "PolygLottery",
        "24": "Prose & Cons",
        "25": "Sign Language",
        "26": "Elementary",
        "27": "Jigsawed",
        "28": "Borderline",
        "29": "Face/Off",
        "30": "Rushmore",
        "31": "Wordle War",
        "32": "MusIQ",
        "33": "Myopic Mystery",
        "34": "Microscopic",
        "35": "Fusion",
        "36": "Tally",
        "37": "Checkmate",
        "38": "Wall Street",
        "39": "XXXX",
        "40": "OkRACE",
        "41": "Spotlight",
        "99": "CHAOS",
        "x": "Skip Mini Game"
    }
    return game_map.get(str(number), "Unknown")

async def store_minigame_frequency(number, selection_type, bot_source="discord", minigame_name=None):
    """Store minigame selection frequency in MongoDB using counter-based documents"""
    try:
        db = await connect_to_mongodb()
        collection = db["mini-game-frequency"]
        
        if minigame_name is None:
            minigame_name = get_minigame_name(number)
        
        # For Wheel of Fortune games (0-4), use a single document
        if str(number) in ["0", "1", "2", "3", "4"]:
            document_key = "wheel-of-fortune"
            display_name = "Wheel of Fortune"
        else:
            # For other games, use the number as the key
            document_key = str(number)
            display_name = minigame_name
        
        # Create the filter to find the document (one per game, not per bot_source)
        filter_query = {
            "game_key": document_key
        }
        
        # Prepare the update operation with nested bot_source fields and global counters
        if selection_type == "user":
            update_operation = {
                "$inc": {
                    f"{bot_source}.user": 1,
                    f"{bot_source}.total": 1,
                    "total": 1,
                    "total_user": 1
                },
                "$set": {"minigame_name": display_name, "last_updated": datetime.datetime.now()},
                "$setOnInsert": {
                    f"{bot_source}.random": 0,
                    # Initialize other bot source if it doesn't exist
                    f"{'discord' if bot_source == 'reddit' else 'reddit'}.user": 0,
                    f"{'discord' if bot_source == 'reddit' else 'reddit'}.random": 0,
                    f"{'discord' if bot_source == 'reddit' else 'reddit'}.total": 0,
                    # Initialize global counters
                    "total_random": 0
                }
            }
        elif selection_type == "random":
            update_operation = {
                "$inc": {
                    f"{bot_source}.random": 1,
                    f"{bot_source}.total": 1,
                    "total": 1,
                    "total_random": 1
                },
                "$set": {"minigame_name": display_name, "last_updated": datetime.datetime.now()},
                "$setOnInsert": {
                    f"{bot_source}.user": 0,
                    # Initialize other bot source if it doesn't exist
                    f"{'discord' if bot_source == 'reddit' else 'reddit'}.user": 0,
                    f"{'discord' if bot_source == 'reddit' else 'reddit'}.random": 0,
                    f"{'discord' if bot_source == 'reddit' else 'reddit'}.total": 0,
                    # Initialize global counters
                    "total_user": 0
                }
            }
        else:
            raise ValueError(f"Invalid selection_type: {selection_type}")
        
        # Upsert the document (create if doesn't exist, update if it does)
        result = await collection.update_one(filter_query, update_operation, upsert=True)
        
        if result.upserted_id:
            print(f"Created new frequency document for {display_name}")
        else:
            print(f"Updated frequency for {display_name} - {bot_source}/{selection_type}")
        
    except Exception as e:
        print(f"Error storing minigame frequency: {e}")


async def cleanup_tournament_roles():
    """Remove tournament roles from all members and restore permissions on startup"""
    try:
        print("🧹 Cleaning up tournament roles and permissions from previous sessions...")

        for guild in bot.guilds:
            participant_role = guild.get_role(TOURNAMENT_PARTICIPANT_ROLE_ID)
            tournament_channel = guild.get_channel(TOURNAMENT_GUILD_ID)

            # Clean up participant roles
            members_cleaned = 0
            if participant_role:
                for member in guild.members:
                    if participant_role in member.roles:
                        try:
                            await member.remove_roles(participant_role, reason="Tournament role cleanup on bot startup")
                            members_cleaned += 1
                        except Exception as e:
                            print(f"Failed to remove tournament roles from {member.display_name}: {e}")

            # Restore @everyone and participant role permissions in tournament channel
            if tournament_channel:
                try:
                    everyone_role = guild.default_role

                    # Restore @everyone messaging permissions
                    current_overwrites = tournament_channel.overwrites
                    if everyone_role in current_overwrites:
                        existing_everyone_perms = current_overwrites[everyone_role]
                    else:
                        existing_everyone_perms = discord.PermissionOverwrite()

                    existing_everyone_perms.send_messages = True
                    await tournament_channel.set_permissions(everyone_role, overwrite=existing_everyone_perms)
                    print(f"✅ Restored @everyone messaging permissions in tournament channel")

                    # Reset participant role permissions if they exist
                    if participant_role:
                        existing_participant_perms = tournament_channel.overwrites_for(participant_role)
                        existing_participant_perms.send_messages = None  # None = inherit from role/server defaults
                        await tournament_channel.set_permissions(participant_role, overwrite=existing_participant_perms)
                        print(f"✅ Reset participant role permissions in tournament channel")

                except Exception as e:
                    print(f"Failed to restore channel permissions: {e}")

            if members_cleaned > 0:
                print(f"🧹 Cleaned tournament roles from {members_cleaned} members in {guild.name}")
            elif participant_role:
                print(f"✅ No tournament roles to clean in {guild.name}")

    except Exception as e:
        print(f"❌ Error cleaning tournament roles: {e}")

@bot.event
async def on_ready():
    global channel, db
    print(f"✅ Logged in as {bot.user}")
    db =  await connect_to_mongodb()
    await load_parameters()
    await load_round_options_from_db()
    channel = bot.get_channel(channel_id)

    # Clean up tournament roles from previous sessions
    await cleanup_tournament_roles()

    # Setup tournament system
    try:
        print("🏆 Setting up tournament system...")
        
        # Setup tournament system - you can specify exact channel ID for testing
        specific_channel_id = TOURNAMENT_GUILD_ID  # Your tournament channel ID
        # Create a simple question selector for tournaments
        async def get_tournament_question(*args, **kwargs):
            try:
                # Randomly choose between trivia_questions and jeopardy_questions
                collections = ["trivia_questions", "jeopardy_questions"]
                collection_name = random.choice(collections)
                collection = db[collection_name]
                
                pipeline = [{"$sample": {"size": 1}}]
                questions = await collection.aggregate(pipeline).to_list(length=1)
                
                if questions:
                    question = questions[0]
                    
                    # Get answers array - handle both single answer and array formats
                    answers = question.get("answers", [])
                    
                    if not answers:
                        # Fallback to single answer field if answers array is empty
                        single_answer = question.get("answer", "")
                        if single_answer:
                            answers = [single_answer]
                    
                    result = {
                        "question": question.get("question", "No question found"),
                        "answers": answers,  # Return full answers array
                        "category": question.get("category", "General"),
                        "url": question.get("url", ""),
                        "source": collection_name
                    }
                    
                    print(f"🎯 QUESTION: {result['question']}")
                    print(f"🎯 ANSWER: {', '.join(answers)}")
                    
                    return result
                return {
                    "question": "What is 2+2?",
                    "answers": ["4"], 
                    "category": "Math",
                    "url": "",
                    "source": "fallback"
                }
            except Exception as e:
                print(f"Error getting tournament question: {e}")
                return {
                    "question": "What is 2+2?",
                    "answers": ["4"],
                    "category": "Math", 
                    "url": "",
                    "source": "fallback"
                }
        
        global tournament_manager
        tournament_manager = await setup_tournament_system(
            bot=bot,
            db=db,
            fuzzy_match_func=fuzzy_match,
            select_trivia_questions_func=get_tournament_question,
            allowed_channel_id=specific_channel_id  # Restrict to this specific channel
        )
        
        print("✅ Tournament system integrated successfully!")
        print("📋 Tournament commands restricted to #tournament channels only")
        print("🎮 Commands: /start, /status, /cancel, /join, /stats, /leaderboard")

        # Initialize Okra Hunt escape room system
        global okra_hunt
        okra_hunt = OkraHunt(bot, THE_LODGE_CHANNEL_ID, LEVEL_0_CHANNEL_ID, LEVEL_0_ROLE_ID, HUNT_PROGRESS_CHANNEL_ID, LEVEL_1_CHANNEL_ID, HOST_ROLE_ID, okrag_id, LEVEL_1_ROLE_ID, LEVEL_2_CHANNEL_ID, LEVEL_2_ROLE_ID, LEVEL_3_CHANNEL_ID, LEVEL_3_ROLE_ID, LEVEL_4_ROLE_ID, LEVEL_4_CHANNEL_ID, RULES_CHANNEL_ID, RULES_MESSAGE_ID, HUNT_LEADERBOARD_CHANNEL_ID, HUNT_LEADERBOARD_MESSAGE_ID, LEVEL_5_ROLE_ID, LEVEL_5_CHANNEL_ID)

        print("✅ Okra Hunt escape room system integrated successfully!")
        print("🏃 Available channels: THE_LODGE -> LEVEL_0 -> LEVEL_1 -> LEVEL_2 -> LEVEL_3 -> LEVEL_4 -> LEVEL_5")

        # Clean up escape room channels from previous sessions
        print("🧹 Cleaning up escape room channels...")
        await okra_hunt.cleanup_escape_room_channels()

        # Clean up reactions on rules message
        print("🧹 Cleaning up reactions on rules message...")
        await okra_hunt.cleanup_rules_message_reactions()

        # Update hunt leaderboard
        print("📊 Updating hunt leaderboard...")
        await okra_hunt.update_leaderboard()

        # Tournament testing: Use add_fake_players.py script for adding test players
        print("🧪 For testing: Use add_fake_players.py script to add fake players")
        
    except Exception as tournament_error:
        print(f"❌ Failed to setup tournament system: {tournament_error}")
        traceback.print_exc()
    
    # Debug: Check what commands are in the tree
    try:
        commands = []
        for guild_id, guild_commands in bot.tree._guild_commands.items():
            commands.extend([cmd.name for cmd in guild_commands.values()])
        commands.extend([cmd.name for cmd in bot.tree._global_commands.values()])
        print(f"🔍 Commands in tree: {commands}")
    except Exception as debug_error:
        print(f"🔍 Debug error: {debug_error}")
        print(f"🔍 Tree attributes: {[attr for attr in dir(bot.tree) if 'command' in attr.lower()]}")
    
    
    if sync_commands:
        # Try syncing to specific tournament guild first
        try:
            tournament_guild = discord.Object(id=TOURNAMENT_GUILD_ID)
            synced = await bot.tree.sync(guild=tournament_guild)
            print(f"✅ Synced {len(synced)} slash command(s) to tournament guild {TOURNAMENT_GUILD_ID}")
            if synced:
                print(f"🔍 Tournament guild synced commands: {[cmd.name for cmd in synced]}")
        except Exception as tournament_e:
            print(f"❌ Failed to sync commands to tournament guild: {tournament_e}")

        # Try global sync
        try:
            synced = await bot.tree.sync()
            print(f"✅ Synced {len(synced)} slash command(s) globally")
            if synced:
                print(f"🔍 Globally synced commands: {[cmd.name for cmd in synced]}")
        except Exception as e:
            print(f"❌ Failed to sync slash commands globally: {e}")
            # Try guild sync as fallback to main guild
            try:
                guild = discord.Object(id=OKRAN_GUILD_ID)
                synced = await bot.tree.sync(guild=guild)
                print(f"✅ Synced {len(synced)} slash command(s) to guild {OKRAN_GUILD_ID}")
                if synced:
                    print(f"🔍 Guild synced commands: {[cmd.name for cmd in synced]}")
            except Exception as guild_e:
                print(f"❌ Guild sync also failed: {guild_e}")
                traceback.print_exc()
    
    await start_trivia()


@bot.command()
async def sync_tournament_commands(ctx):
    """Manual command to sync tournament slash commands"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Only administrators can sync commands")
        return

    try:
        # Sync to tournament guild
        tournament_guild = discord.Object(id=TOURNAMENT_GUILD_ID)
        synced = await bot.tree.sync(guild=tournament_guild)
        await ctx.send(f"✅ Synced {len(synced)} slash command(s) to tournament guild!")
        if synced:
            commands_list = [cmd.name for cmd in synced]
            await ctx.send(f"Commands: {', '.join(commands_list)}")
    except Exception as e:
        await ctx.send(f"❌ Failed to sync commands: {e}")

@bot.command()
async def sync_global(ctx):
    """Manual command to sync all slash commands globally"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Only administrators can sync commands")
        return

    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ Synced {len(synced)} slash command(s) globally!")
        if synced:
            commands_list = [cmd.name for cmd in synced]
            await ctx.send(f"Commands: {', '.join(commands_list)}")
    except Exception as e:
        await ctx.send(f"❌ Failed to sync commands: {e}")

@bot.event
async def on_raw_reaction_add(payload):
    """
    Handle raw reaction events for okra hunt system
    """
    # Only process reactions in RULES_CHANNEL_ID to the specific message
    if payload.channel_id == RULES_CHANNEL_ID and payload.message_id == RULES_MESSAGE_ID:
        # Get the guild, user, and roles
        guild = bot.get_guild(payload.guild_id)
        if not guild:
            return

        user = guild.get_member(payload.user_id)
        if not user or user.bot:
            return

        # Check if this is the palm tree emoji from a qualified user
        if str(payload.emoji) == "🌴":
            level_3_role = guild.get_role(LEVEL_3_ROLE_ID)
            level_4_role = guild.get_role(LEVEL_4_ROLE_ID)

            if not level_3_role or not level_4_role:
                await _remove_user_reaction(payload.channel_id, payload.message_id, payload.emoji, payload.user_id)
                return

            # If user has LEVEL_3_ROLE_ID and doesn't have LEVEL_4_ROLE_ID, process the role swap
            if level_3_role in user.roles and level_4_role not in user.roles:
                try:
                    # Remove LEVEL_3_ROLE and add LEVEL_4_ROLE
                    await user.remove_roles(level_3_role)
                    await user.add_roles(level_4_role)

                    # Announce in progress channel
                    if 'okra_hunt' in globals() and okra_hunt:
                        await okra_hunt.announce_progress(user, "completed", "LEVEL_3")
                        # Update leaderboard
                        await okra_hunt.update_leaderboard()

                    # Remove the successful reaction to hide the answer
                    await _remove_user_reaction(payload.channel_id, payload.message_id, payload.emoji, payload.user_id)

                except Exception as e:
                    print(f"❌ Error updating roles: {e}")
            else:
                # Remove the reaction if user doesn't qualify
                await _remove_user_reaction(payload.channel_id, payload.message_id, payload.emoji, payload.user_id)
        else:
            # Remove any non-palm-tree reactions
            await _remove_user_reaction(payload.channel_id, payload.message_id, payload.emoji, payload.user_id)

async def _remove_user_reaction(channel_id, message_id, emoji, user_id):
    """
    Helper function to remove a specific user's reaction from a message
    """
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            return

        message = await channel.fetch_message(message_id)
        if not message:
            return

        user = bot.get_user(user_id)
        if not user:
            return

        await message.remove_reaction(emoji, user)

    except discord.Forbidden:
        print(f"❌ Missing permission to remove reaction from message {message_id}")
    except discord.NotFound:
        pass  # Reaction already removed or doesn't exist
    except Exception as e:
        print(f"❌ Error removing reaction: {e}")

@bot.event
async def on_reaction_add(reaction, user):
    """
    Handle reaction events for okra hunt system
    """
    try:
        # Let okra hunt system handle the reaction
        if 'okra_hunt' in globals() and okra_hunt:
            await okra_hunt.handle_reaction(reaction, user)
    except Exception as e:
        print(f"❌ Error handling reaction: {e}")

if __name__ == "__main__":
    bot.run(discord_token)
