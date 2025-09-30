"""
Discord Round-Robin Tournament System
=====================================

A comprehensive tournament system supporting:
- Round-robin phase with head-to-head matches
- Knockout semifinals and finals
- Question selection from trivia, jeopardy, and crossword collections
- Tournament persistence and recovery
- Concurrency controls and channel restrictions

Requirements:
- Only works in designated tournament channel
- Single active tournament per channel
- Tournament phases: signup -> rr -> semis -> final -> completed
- Question timeout, AFK tracking, forfeit system
"""

import asyncio
import random
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
from itertools import combinations
from collections import defaultdict

import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId
import pymongo

# Tournament Configuration Constants
ACTIVE_STATUSES = {"signup", "rr", "points_race", "semis", "final"}

# Tournament Configuration - Easily configurable defaults
JOIN_WINDOW_SEC_DEFAULT = 60
VOTE_WINDOW_SEC_DEFAULT = 30
RR_QUESTIONS_PER_MATCH_DEFAULT = 3
ANSWER_TIMEOUT_SEC_DEFAULT = 15
RR_REVEAL_TIME = 5  # Round robin question reveal time
MIN_PLAYERS_DEFAULT = 4
MAX_PLAYERS_DEFAULT = 12
MODE_DEFAULT = "progressive"
POINTS_PER_QUESTION_DEFAULT = 10
MATCH_POINTS = {"win": 3, "tie": 1, "loss": 0}
KO_MAX_QUESTIONS = 7  # Knockout phases: max 7 questions (up to 7 questions, early end if decided)

# Seeding Mode Configuration
SEEDING_MODE_DEFAULT = "points_race" # or "round_robin"

POINTS_RACE_QUESTIONS = 10
POINTS_RACE_REVEAL_TIME = 5  # Question reveals over 5 seconds
POINTS_RACE_ANSWER_TIME = 15  # Answer window after full reveal
POINTS_RACE_QUESTION_DELAY = 15  # Delay between questions
POINTS_RACE_MAX_POINTS = 100

# Global tournament locks per channel
tournament_locks: Dict[int, asyncio.Lock] = {}

# Tournament question tracking - limits for recent questions to exclude
TOURNAMENT_QUESTION_LIMITS = {
    "trivia": 2000,
    "jeopardy": 2000
}

# Tournament question selection percentages (easily configurable)
JEOPARDY_PERCENTAGE = 50  # 70% jeopardy questions
TRIVIA_PERCENTAGE = 50   # 30% trivia questions

# In-memory tournament storage
active_tournaments: Dict[int, Dict] = {}  # channel_id -> tournament_data


logger = logging.getLogger(__name__)

class TournamentError(Exception):
    """Base exception for tournament-related errors"""
    pass

class ChannelError(TournamentError):
    """Raised when tournament operations are attempted outside designated tournament channel"""
    pass

class ActiveTournamentError(TournamentError):
    """Raised when trying to start a tournament while one is already active"""
    pass

def get_tournament_lock(channel_id: int) -> asyncio.Lock:
    """Get or create a lock for the given channel"""
    if channel_id not in tournament_locks:
        tournament_locks[channel_id] = asyncio.Lock()
    return tournament_locks[channel_id]

def validate_tournament_channel(channel: discord.TextChannel) -> bool:
    """Validate that the channel ID matches TOURNAMENT_GUILD_ID"""
    import discordbot
    tournament_guild_id = getattr(discordbot, 'TOURNAMENT_GUILD_ID', None)
    return tournament_guild_id is not None and channel.id == tournament_guild_id

class TournamentManager:
    """Main tournament management class"""

    def __init__(self, db: AsyncIOMotorDatabase, bot: commands.Bot, question_func=None, fuzzy_match_func=None):
        self.db = db  # Only used for final results storage
        self.bot = bot
        self.active_questions: Dict[int, Dict] = {}  # channel_id -> question_data
        self.question_func = question_func  # Function to get questions
        self.fuzzy_match_func = fuzzy_match_func  # Function to check answers
        self.running_tasks: Dict[int, asyncio.Task] = {}  # channel_id -> tournament task

        # Tournament state management for event-driven message handling
        self.tournament_contexts: Dict[int, Dict] = {}  # channel_id -> tournament context
        self.signup_contexts: Dict[int, Dict] = {}  # channel_id -> signup context
        self.question_contexts: Dict[int, Dict] = {}  # channel_id -> question context
        self.active_tournament_channels: Set[int] = set()  # channels with active tournaments

    async def ensure_indexes(self):
        """Ensure database indexes are created for completed tournament storage"""
        tournaments = self.db.tournaments
        matches = self.db.matches

        # Performance indexes for completed tournament data
        await tournaments.create_index([("created_at", -1)])
        await tournaments.create_index([("guild_id", 1)])
        await tournaments.create_index([("status", 1)])  # For querying completed tournaments
        await matches.create_index([("tournament_id", 1)])
        await matches.create_index([("phase", 1)])
        await matches.create_index([("completed_at", 1)])
        
        logger.info("Tournament database indexes created")

    async def get_recent_tournament_question_ids(self):
        """Get recently used tournament question IDs to exclude from selection"""
        recent_ids = {}
        for question_type in ["trivia", "jeopardy"]:
            collection_name = f"asked_tourney_{question_type}_questions"
            questions_collection = self.db[collection_name]
            limit = TOURNAMENT_QUESTION_LIMITS[question_type]

            # Get recent question IDs sorted by timestamp (newest first)
            docs = await questions_collection.find().sort("timestamp", -1).limit(limit).to_list(length=limit)
            recent_ids[question_type] = {doc["_id"] for doc in docs}

        return recent_ids

    async def store_tournament_question_ids(self, question_ids_by_type):
        """Store used tournament question IDs and clean up old entries"""
        for question_type, question_ids in question_ids_by_type.items():
            if not question_ids:
                continue

            collection_name = f"asked_tourney_{question_type}_questions"
            questions_collection = self.db[collection_name]

            # Store question IDs with timestamps
            for _id in question_ids:
                await questions_collection.update_one(
                    {"_id": _id},
                    {"$setOnInsert": {"_id": _id, "timestamp": datetime.now(timezone.utc)}},
                    upsert=True
                )

            # Clean up old entries if collection exceeds limit
            limit = TOURNAMENT_QUESTION_LIMITS[question_type]
            total_ids = await questions_collection.count_documents({})
            if total_ids > limit:
                excess = total_ids - limit
                # Find oldest entries and delete them
                cursor = questions_collection.find().sort("timestamp", 1).limit(excess)
                oldest_entries = await cursor.to_list(length=excess)
                for entry in oldest_entries:
                    await questions_collection.delete_one({"_id": entry["_id"]})



    def create_tournament(self, channel: discord.TextChannel, config: Dict[str, Any]) -> str:
        """Create a new in-memory tournament"""
        tournament_id = f"tournament_{channel.id}_{int(datetime.now().timestamp())}"

        tournament_data = {
            "id": tournament_id,
            "guild_id": str(channel.guild.id),
            "channel_id": str(channel.id),
            "channel_name": channel.name,
            "status": "signup",
            "config": {
                "join_window_sec": config.get("join_window_sec", JOIN_WINDOW_SEC_DEFAULT),
                "rr_questions_per_match": config.get("rr_questions_per_match", RR_QUESTIONS_PER_MATCH_DEFAULT),
                "answer_timeout_sec": config.get("answer_timeout_sec", ANSWER_TIMEOUT_SEC_DEFAULT),
                "min_players": config.get("min_players", MIN_PLAYERS_DEFAULT),
                "mode": config.get("mode", "standard"),
                "points_per_question": config.get("points_per_question", POINTS_PER_QUESTION_DEFAULT),
                "match_points": MATCH_POINTS.copy(),
                "seeding_mode": config.get("seeding_mode", SEEDING_MODE_DEFAULT)
            },
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "players": [],
            "matches": [],  # In-memory match storage
            "current_match_index": 0,
            "standings": [],
            "winner": None,
            "runner_up": None
        }

        active_tournaments[channel.id] = tournament_data
        logger.info(f"Created in-memory tournament {tournament_id} in channel {channel.name}")
        return tournament_id

    def load_tournament_by_channel(self, channel_id: int) -> Optional[Dict]:
        """Load the active tournament for a channel from memory"""
        return active_tournaments.get(channel_id)

    def update_tournament(self, channel_id: int, updates: Dict):
        """Update tournament in memory"""
        if channel_id in active_tournaments:
            tournament = active_tournaments[channel_id]
            tournament.update(updates)

    def create_match(self, tournament_id: str, player_a: Dict,
                    player_b: Dict, phase: str, questions_target: int,
                    best_of: Optional[int] = None) -> str:
        """Create an in-memory match"""
        import uuid
        match_id = str(uuid.uuid4())

        match_data = {
            "id": match_id,
            "tournament_id": tournament_id,
            "phase": phase,
            "player_a": {
                "user_id": player_a["user_id"],
                "display_name": player_a["display_name"]
            },
            "player_b": {
                "user_id": player_b["user_id"],
                "display_name": player_b["display_name"]
            },
            "best_of": best_of,
            "questions_target": questions_target,
            "score": {"a": 0, "b": 0},
            "winner_user_id": None,
            "draw": False,
            "started_at": None,
            "completed_at": None
        }

        return match_data

    async def start_tournament(self, interaction: discord.Interaction) -> None:
        """Start a new tournament"""
        if not validate_tournament_channel(interaction.channel):
            raise ChannelError("Tournaments can only be started in designated tournament channel")

        channel_id = interaction.channel.id
        async with get_tournament_lock(channel_id):
            # Check for existing active tournament FIRST (before any cleanup)
            existing = self.load_tournament_by_channel(channel_id)
            if existing and existing["status"] in ACTIVE_STATUSES:
                raise ActiveTournamentError("A tournament is already active in this channel. Please wait for it to finish before starting a new one.")

            # Only clean up if no active tournament exists or tournament is completed
            # Cancel any existing tournament task
            if channel_id in self.running_tasks:
                self.running_tasks[channel_id].cancel()
                del self.running_tasks[channel_id]

            # Remove any existing tournament from memory
            if channel_id in active_tournaments:
                del active_tournaments[channel_id]

            # Clear active question state
            if channel_id in self.active_questions:
                del self.active_questions[channel_id]

            # Create tournament
            config = {
                "join_window_sec": JOIN_WINDOW_SEC_DEFAULT,
                "rr_questions_per_match": RR_QUESTIONS_PER_MATCH_DEFAULT,
                "answer_timeout_sec": ANSWER_TIMEOUT_SEC_DEFAULT,
                "min_players": MIN_PLAYERS_DEFAULT,
                "max_players": MAX_PLAYERS_DEFAULT,
                "mode": MODE_DEFAULT,
                "seeding_mode": SEEDING_MODE_DEFAULT
            }

            tournament_id = self.create_tournament(interaction.channel, config)
            
            # Send signup message
            embed = discord.Embed(
                title="🥒 Tournament Signup Open!",
                description=f"Type `okra` in the next **{JOIN_WINDOW_SEC_DEFAULT}** seconds to join the tournament!\n\n**Okrans** and **The Bumper King** get preference!",
                color=discord.Color.green()
            )
            seeding_display = "Round Robin" if SEEDING_MODE_DEFAULT == "round_robin" else "Points Race"
            embed.add_field(name="\u200b\nSettings",
                           value=f"• Min Players: {MIN_PLAYERS_DEFAULT}\n• Max Players: {MAX_PLAYERS_DEFAULT}\n• Seeding: Points Race or Round Robin (Vote)\n• Knockout Rounds: Best of 7\n• Reveal Time: 5s\n• Question Time: 10s")

            # Add joined players section
            embed.add_field(name="Joined Players (0)", value="*Waiting for players...*", inline=False)

            await interaction.response.send_message(embed=embed)

            # Get the message for editing later
            signup_message = await interaction.original_response()

            # Store signup message reference for dynamic updates
            tournament_data = active_tournaments.get(channel_id)
            if tournament_data:
                tournament_data["signup_embed"] = embed
                tournament_data["signup_message"] = signup_message
            
            # Start signup phase in background (don't await)
            task = asyncio.create_task(
                self.run_signup_phase(channel_id, JOIN_WINDOW_SEC_DEFAULT, MIN_PLAYERS_DEFAULT)
            )
            self.running_tasks[channel_id] = task

    async def run_signup_phase(self, channel_id: int, join_window_sec: int, min_players: int) -> None:
        """Handle the signup phase using event-driven approach"""
        # Get tournament from memory
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        players = tournament["players"].copy()

        # AUTO-ADD FAKE PLAYERS FOR TESTING (only in local mode)
        import discordbot
        if discordbot.local_mode:
            fake_players = [
                {
                    "user_id": "fake_alpha",
                    "display_name": "Alpha",
                    "joined_at": datetime.now(timezone.utc),
                    "active": True,
                    "afk_strikes": 0
                },
                {
                    "user_id": "fake_beta",
                    "display_name": "Beta",
                    "joined_at": datetime.now(timezone.utc),
                    "active": True,
                    "afk_strikes": 0
                },
                {
                    "user_id": "fake_gamma",
                    "display_name": "Gamma",
                    "joined_at": datetime.now(timezone.utc),
                    "active": True,
                    "afk_strikes": 0
                },
                {
                    "user_id": "fake_delta",
                    "display_name": "Delta",
                    "joined_at": datetime.now(timezone.utc),
                    "active": True,
                    "afk_strikes": 0
                }
            ]

            # Add fake players to tournament in memory
            tournament["players"].extend(fake_players)

            print(f"🤖 Auto-added {len(fake_players)} fake players for testing")
            await channel.send(f"🤖 Added {len(fake_players)} fake players for testing!")

        # Set up signup context for event-driven message handling
        self.set_signup_context(channel_id, tournament)

        signup_end_time = asyncio.get_event_loop().time() + join_window_sec

        # Initialize waitlist in tournament
        if "waitlist" not in tournament:
            tournament["waitlist"] = []

        try:
            # Event-driven signup processing loop
            while asyncio.get_event_loop().time() < signup_end_time:
                signup_context = self.signup_contexts.get(channel_id)

                # Process privileged signup queue (first come first serve up to max)
                if signup_context and 'signup_queue' in signup_context:
                    while signup_context['signup_queue']:
                        signup_data = signup_context['signup_queue'].pop(0)

                        user_id = str(signup_data['user_id'])
                        display_name = signup_data['display_name']
                        message = signup_data['message']

                        # Add player if not already signed up (check tournament memory directly)
                        if not any(p["user_id"] == user_id for p in tournament["players"]):
                            # Check if tournament is at capacity
                            if len(tournament["players"]) >= MAX_PLAYERS_DEFAULT:
                                await message.add_reaction("🙏")
                                await message.reply(f"Sorry, the tournament has reached its maximum capacity of {MAX_PLAYERS_DEFAULT} players.")
                                continue

                            player = {
                                "user_id": user_id,
                                "display_name": display_name,
                                "joined_at": datetime.now(timezone.utc),
                                "active": True,
                                "afk_strikes": 0
                            }
                            # Add to tournament memory
                            tournament["players"].append(player)

                            # React to confirm signup with golden trophy
                            await message.add_reaction("🏆")

                            # Update signup embed with new player
                            await self.update_signup_embed(channel_id)

                # Process waitlist queue
                if signup_context and 'waitlist_queue' in signup_context:
                    while signup_context['waitlist_queue']:
                        signup_data = signup_context['waitlist_queue'].pop(0)

                        user_id = str(signup_data['user_id'])
                        display_name = signup_data['display_name']
                        message = signup_data['message']

                        # Add to waitlist if not already in waitlist or participants
                        if not any(p["user_id"] == user_id for p in tournament["players"]) and \
                           not any(w["user_id"] == user_id for w in tournament["waitlist"]):
                            waitlist_entry = {
                                "user_id": user_id,
                                "display_name": display_name,
                                "message": message,
                                "joined_at": datetime.now(timezone.utc)
                            }
                            tournament["waitlist"].append(waitlist_entry)

                            # React to confirm waitlist with hourglass
                            await message.add_reaction("⏳")

                            # Update signup embed with new waitlist user
                            await self.update_signup_embed(channel_id)

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in signup phase: {e}")
            return
        finally:
            # Clear signup context
            self.clear_signup_context(channel_id)

        # Process waitlist - randomly select users to fill remaining spots
        import random
        waitlist = tournament.get("waitlist", [])
        selected_from_waitlist = []

        if waitlist:
            remaining_spots = MAX_PLAYERS_DEFAULT - len(tournament["players"])
            if remaining_spots > 0:
                # Randomly select from waitlist to fill remaining spots
                num_to_select = min(remaining_spots, len(waitlist))
                selected_entries = random.sample(waitlist, num_to_select)
                selected_user_ids = {entry["user_id"] for entry in selected_entries}

                # Update reactions for all waitlist users
                for entry in waitlist:
                    if entry["user_id"] in selected_user_ids:
                        # Selected: add to participants and change reaction to trophy
                        player = {
                            "user_id": entry["user_id"],
                            "display_name": entry["display_name"],
                            "joined_at": datetime.now(timezone.utc),
                            "active": True,
                            "afk_strikes": 0
                        }
                        tournament["players"].append(player)
                        selected_from_waitlist.append(entry)

                        # Update reaction from hourglass to trophy
                        try:
                            await entry["message"].remove_reaction("⏳", channel.guild.me)
                            await entry["message"].add_reaction("🏆")
                        except Exception as e:
                            logger.error(f"Error updating reaction for selected waitlist user: {e}")
                    else:
                        # Not selected: change reaction to red X
                        try:
                            await entry["message"].remove_reaction("⏳", channel.guild.me)
                            await entry["message"].add_reaction("❌")
                        except Exception as e:
                            logger.error(f"Error updating reaction for unselected waitlist user: {e}")
            else:
                # No spots available - mark all waitlist users with red X
                for entry in waitlist:
                    try:
                        await entry["message"].remove_reaction("⏳", channel.guild.me)
                        await entry["message"].add_reaction("❌")
                    except Exception as e:
                        logger.error(f"Error updating reaction for unselected waitlist user: {e}")

        # Store selected waitlist users for later announcement
        tournament["selected_from_waitlist"] = selected_from_waitlist

        # Get final player count from memory
        final_player_count = len(tournament["players"])

        # Check minimum players
        if final_player_count < min_players:
            embed = discord.Embed(
                title="❌ Tournament Cancelled", 
                description=f"Only {final_player_count} players signed up. Minimum required: {min_players}",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)

            # Remove tournament from memory
            if channel_id in active_tournaments:
                del active_tournaments[channel_id]
            return
        
        # Merge new players with existing ones (avoid duplicates by user_id)
        existing_user_ids = {p["user_id"] for p in tournament["players"]}
        new_players_to_add = [p for p in players if p["user_id"] not in existing_user_ids]
        all_players = tournament["players"] + new_players_to_add

        # Update tournament in memory
        tournament["players"] = all_players
        tournament["status"] = "rr"  # This will be updated in build_rr_schedule_and_start if needed
        tournament["started_at"] = datetime.now(timezone.utc)

        # Announce final participants with waitlist information
        selected_from_waitlist = tournament.get("selected_from_waitlist", [])

        participants_embed = discord.Embed(
            title="📋 Final Tournament Participants",
            description=f"**{len(all_players)} players** will compete in the tournament!",
            color=discord.Color.green()
        )

        # List all participants
        players_list = "\n".join([f"🏆 {p['display_name']}" for p in all_players])
        participants_embed.add_field(name="Participants", value=players_list, inline=False)

        # Add waitlist selection info if applicable
        if selected_from_waitlist:
            waitlist_selected = "\n".join([f"✨ {entry['display_name']}" for entry in selected_from_waitlist])
            participants_embed.add_field(
                name=f"🎲 Randomly Selected from Waitlist ({len(selected_from_waitlist)})",
                value=waitlist_selected,
                inline=False
            )

        await channel.send(embed=participants_embed)

        # 5 second delay before voting
        await asyncio.sleep(5)

        # Conduct seeding mode vote
        seeding_mode = await self.conduct_seeding_vote(channel, tournament)

        # Store the voting result in tournament config
        tournament["config"]["seeding_mode"] = seeding_mode

        if seeding_mode == "points_race":
            embed = discord.Embed(
                title="🏆 Tournament Starting!",
                description=f"**{len(all_players)} players** signed up. Beginning Points Race phase...",
                color=discord.Color.blue()
            )
            player_list = "\n".join([f"• {p['display_name']}" for p in all_players])
            embed.add_field(name="\u200b\n👥 Players", value=player_list, inline=False)
            embed.add_field(
                name="\u200b\n📋 Format",
                value=f"Points Race: {POINTS_RACE_QUESTIONS} questions, time-based scoring (100→0 pts)",
                inline=False
            )
            embed.add_field(
                name="\u200b\n🎯 Advancement",
                value="Top 4 players advance to knockout semifinals!",
                inline=False
            )
            embed.add_field(
                name="\u200b\n⏱️ Starting Soon",
                value="Points Race will begin in 15 seconds!",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="🏆 Tournament Starting!",
                description=f"**{len(all_players)} players** signed up. Beginning round-robin phase...",
                color=discord.Color.blue()
            )
            player_list = "\n".join([f"• {p['display_name']}" for p in all_players])
            embed.add_field(name="\u200b\n👥 Players", value=player_list, inline=False)
            embed.add_field(
                name="\u200b\n📋 Format",
                value="Best of 3 questions per match!",
                inline=False
            )
            embed.add_field(
                name="\u200b\n🎯 Advancement",
                value="Top 4 players advance to knockout semifinals!",
                inline=False
            )
            embed.add_field(
                name="\u200b\n⏱️ Starting Soon",
                value="Round-robin will begin in 15 seconds!\n\n🚨 **ONE answer per question. Be careful!**",
                inline=False
            )
        await channel.send(embed=embed)

        # 15 second delay before starting matches
        await asyncio.sleep(15)

        await self.build_rr_schedule_and_start(channel_id, all_players)

    async def conduct_seeding_vote(self, channel: discord.TextChannel, tournament: Dict) -> str:
        """Conduct a vote to determine seeding mode between Round Robin and Points Race"""
        # Create voting embed
        embed = discord.Embed(
            title="🗳️ Choose Seeding Format",
            description="Tournament participants, vote for your preferred seeding format!\n\n**Round Robin:** Head-to-head matches determine rankings\n**Points Race:** 10 rapid-fire questions with time-based scoring",
            color=discord.Color.gold()
        )

        # Add fields for vote counts (will be updated)
        embed.add_field(name="🥊 Round Robin", value="*No votes yet*", inline=True)
        embed.add_field(name="🏃 Points Race", value="*No votes yet*", inline=True)

        # Create voting view
        view = SeedingVoteView(tournament, embed)
        message = await channel.send(embed=embed, view=view)
        view.message = message

        # Wait for voting to complete (30 seconds)
        await asyncio.sleep(VOTE_WINDOW_SEC_DEFAULT)

        # Disable buttons and announce result
        view.disable_all_buttons()

        # Determine result
        rr_votes = len(view.round_robin_votes)
        pr_votes = len(view.points_race_votes)
        total_participants = len(tournament["players"])

        # Round Robin wins only if it has majority of votes cast, ties default to Points Race
        total_votes = rr_votes + pr_votes
        if rr_votes > pr_votes:
            result = "round_robin"
            result_text = f"🥊 **Round Robin** wins! ({rr_votes}-{pr_votes} vote margin)"
        else:
            result = "points_race"
            if rr_votes == pr_votes:
                result_text = f"🏃 **Points Race** wins! (Tie {rr_votes}-{pr_votes}, default to Points Race)"
            else:
                result_text = f"🏃 **Points Race** wins! ({pr_votes}-{rr_votes} vote margin)"

        # Update embed with final results (keep voter names visible)
        embed.title = "🗳️ Voting Complete!"
        embed.color = discord.Color.green()
        # Don't change the fields - they already show voter names from update_embed_votes()
        embed.add_field(name="🏆 Result", value=result_text, inline=False)

        await message.edit(embed=embed, view=view)

        return result

    async def build_rr_schedule_and_start(self, channel_id: int, players: List[Dict]) -> None:
        """Build schedule and start seeding phase (either round-robin or points race)"""
        # Get tournament from memory
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        seeding_mode = tournament["config"].get("seeding_mode", SEEDING_MODE_DEFAULT)

        if seeding_mode == "points_race":
            # Start Points Race
            tournament["status"] = "points_race"
            await self.run_points_race(channel_id)
        else:
            # Default to Round Robin
            questions_per_match = tournament["config"]["rr_questions_per_match"]

            # Generate all player pairs
            all_pairs = list(combinations(players, 2))

            # Create rounds of matches, each round has different pairs
            scheduled_matches = []

            for round_num in range(1):  # 1 round per pair (change to range(2), range(3), etc. for more rounds)
                # Shuffle pairs for this round to mix up the order
                round_pairs = all_pairs.copy()
                random.shuffle(round_pairs)

                round_matches = []
                for player_a, player_b in round_pairs:
                    match_data = self.create_match(
                        tournament["id"], player_a, player_b, "rr", questions_per_match
                    )
                    round_matches.append(match_data)

                scheduled_matches.extend(round_matches)

            # Store matches in tournament
            tournament["matches"] = scheduled_matches

            # Start round-robin matches
            await self.run_round_robin(channel_id)

    async def run_round_robin(self, channel_id: int) -> None:
        """Execute all round-robin matches"""
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        total_matches = len(tournament["matches"])
        
        previous_pair = None
        
        for i, match in enumerate(tournament["matches"], 1):
            if match.get("completed_at"):
                continue
            
            # Create current pair identifier for comparison (sorted to handle order)
            current_pair = tuple(sorted([match['player_a']['user_id'], match['player_b']['user_id']]))
            
            # Check if this is a new player pairing
            if previous_pair != current_pair:
                # Merged matchup announcement
                merged_embed = discord.Embed(
                    title=f"🔔 Round Robin Match {i} of {total_matches}",
                    description=f"\n**{match['player_a']['display_name']}** vs **{match['player_b']['display_name']}**\n\nMatch will begin in 15 seconds!",
                    color=discord.Color.gold()
                )
                await channel.send(embed=merged_embed)

                # 15-second pause for new matchups
                await asyncio.sleep(15)
                previous_pair = current_pair
            else:
                # Same pairing, just show match start without announcement
                match_embed = discord.Embed(
                    title=f"🥊 Round Robin Match {i}/{total_matches}",
                    description=f"{match['player_a']['display_name']} vs {match['player_b']['display_name']}",
                    color=discord.Color.orange()
                )
                match_embed.add_field(name="Format", value=f"{match['questions_target']} questions")
                await channel.send(embed=match_embed)
            
            await self.run_match(match, channel)
        
        # Round-robin complete, move to knockout phase
        await self.start_knockout_phase(channel_id)

    async def start_knockout_phase(self, channel_id: int) -> None:
        """Start the knockout phase after round-robin"""
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)
        
        # Calculate final standings
        standings = self.compute_rr_standings(tournament)
        
        # Determine knockout format based on player count
        if len(standings) >= 4:
            # Top 4 to semifinals
            seedings = [
                {"user_id": standings[i]["user_id"], "seed": i + 1}
                for i in range(4)
            ]
            
            # Update tournament in memory
            tournament["status"] = "semis"
            tournament["seedings"] = seedings

            # Announce round-robin standings and semifinal bracket
            standings_text = "\n".join([
                f"{i+1}. {player['display_name']} ({player['mw']}-{player['md']}-{player['ml']}) - {player['mp']} MP"
                for i, player in enumerate(standings[:4])
            ])

            bracket_embed = discord.Embed(
                title="🏆 ROUND-ROBIN COMPLETE!",
                description="Here are the final standings and semifinal bracket:",
                color=discord.Color.gold()
            )
            bracket_embed.add_field(
                name="\u200b\n📊 Final Standings",
                value=standings_text,
                inline=False
            )
            bracket_embed.add_field(
                name="\u200b\n⚔️ Semifinal Bracket",
                value=f"**Match 1:** {standings[0]['display_name']} (#1) vs {standings[3]['display_name']} (#4)\n**Match 2:** {standings[1]['display_name']} (#2) vs {standings[2]['display_name']} (#3)",
                inline=False
            )
            bracket_embed.add_field(
                name="\u200b\n📋 Format",
                value=f"Best of {KO_MAX_QUESTIONS} wins!",
                inline=False
            )
            bracket_embed.add_field(
                name="\u200b\n⏱️ Starting Soon",
                value="Semifinals will begin in 30 seconds!",
                inline=False
            )
            await channel.send(embed=bracket_embed)

            # 15 second break before first semifinal
            await asyncio.sleep(15)
            await self.run_semifinals(channel_id)
            
        elif len(standings) == 3:
            # Top 2 to final
            seedings = [
                {"user_id": standings[i]["user_id"], "seed": i + 1}
                for i in range(2)
            ]
            
            # Update tournament in memory
            tournament["status"] = "final"
            tournament["seedings"] = seedings

            await self.run_final(channel_id)
            
        else:
            # 2 or fewer players - declare winner from RR standings
            await self.complete_tournament(channel_id)

    async def run_points_race(self, channel_id: int) -> None:
        """Execute Points Race seeding phase - all players compete on 10 questions simultaneously"""
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        players = tournament["players"]
        if len(players) < 4:
            await channel.send("❌ Need at least 4 players for Points Race")
            return

        # Initialize Points Race data structure
        tournament["points_race_scores"] = {}
        tournament["points_race_questions"] = []

        for player in players:
            tournament["points_race_scores"][player["user_id"]] = {
                "total_points": 0,
                "questions_correct": 0,
                "questions_answered": 0,
                "answer_times": []
            }

        # Update tournament status
        tournament["status"] = "points_race"

        # Wait 15 seconds before starting
        await asyncio.sleep(15)

        # Run 10 questions
        for question_num in range(1, POINTS_RACE_QUESTIONS + 1):
            await self.run_points_race_question(channel_id, question_num)

            # Delay between questions (except after the last one)
            if question_num < POINTS_RACE_QUESTIONS:
                await asyncio.sleep(POINTS_RACE_QUESTION_DELAY)

        # Show final standings and determine top 4
        try:
            await asyncio.sleep(5)
            await self.complete_points_race(channel_id)
        except Exception as e:
            import traceback
            traceback.print_exc()

    async def run_points_race_question(self, channel_id: int, question_num: int) -> None:
        """Run a single Points Race question with progressive reveal and time-based scoring"""
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        # Get all players for this question
        player_ids = [p["user_id"] for p in tournament["players"]]

        # Assign Tournament Participant role to all players
        await self.assign_points_race_participant_roles(channel, player_ids)

        # Restrict channel permissions before question
        await self.restrict_channel_permissions(channel, [str(pid) for pid in player_ids])

        # Get question
        question = await self.select_head_to_head_question()
        if not question:
            await channel.send("❌ Could not fetch question")
            return

        # Store question data
        question_data = {
            "number": question_num,
            "question": question,
            "answers": {},
            "reveal_start_time": None,
            "reveal_complete_time": None
        }
        tournament["points_race_questions"].append(question_data)

        # Progressive reveal setup
        full_prompt = question["prompt"]
        answers = question.get("answers", [])
        if not answers:
            answers = [question.get("answer", "No answer available")]

        # Display first answer or all answers if multiple, in all caps
        if len(answers) == 1:
            answer_text = answers[0].upper()
        else:
            answer_text = " / ".join([ans.upper() for ans in answers])

        # Create initial question embed with category
        category_text = question.get("category", "General")
        question_embed = discord.Embed(
            title=f"⚡ Question {question_num}/{POINTS_RACE_QUESTIONS}: {category_text}",
            description="",  # Will be filled during reveal
            color=discord.Color.blue()
        )

        # Add image if available
        question_url = question.get("url", "")
        if question_url and question_url.startswith("http"):
            question_embed.set_image(url=question_url)

        # Send initial embed
        message = await channel.send(embed=question_embed)

        # Progressive reveal
        reveal_time = POINTS_RACE_REVEAL_TIME
        update_interval = 1.0
        total_updates = int(reveal_time)

        question_data["reveal_start_time"] = time.time()

        async def progressive_reveal(msg):
            for i in range(total_updates):
                if i == 0:
                    await asyncio.sleep(update_interval)
                    continue

                # Calculate how much of the prompt to reveal
                chars_to_reveal = int((i / total_updates) * len(full_prompt))
                partial_prompt = full_prompt[:chars_to_reveal]

                # Update embed
                question_embed.description = partial_prompt
                try:
                    await msg.edit(embed=question_embed)
                except (discord.NotFound, discord.HTTPException):
                    pass  # Ignore if message can't be edited

                await asyncio.sleep(update_interval)

            # Final reveal - show complete question
            question_embed.description = full_prompt
            try:
                await msg.edit(embed=question_embed)
                question_data["reveal_complete_time"] = time.time()
            except (discord.NotFound, discord.HTTPException):
                pass

        # Start progressive reveal and answer monitoring
        reveal_task = asyncio.create_task(progressive_reveal(message))
        answer_task = asyncio.create_task(self.wait_for_points_race_answers(
            channel, player_ids, question, question_data, reveal_time + POINTS_RACE_ANSWER_TIME
        ))

        # Wait for both to complete
        await asyncio.gather(reveal_task, answer_task)

        # Show correct answer with question results
        embed = discord.Embed(
            title=f"✅ Question {question_num}/{POINTS_RACE_QUESTIONS}: {category_text} Complete",
            description=f"**Correct Answer:** {answer_text}",
            color=discord.Color.green()
        )

        # Add question results showing who got it right and their points
        tournament = active_tournaments.get(channel_id)
        if tournament:
            question_results = []
            for player in tournament["players"]:
                if "points_race_scores" in player and len(player["points_race_scores"]) >= question_num:
                    score_data = player["points_race_scores"][question_num - 1]  # question_num is 1-indexed
                    if score_data["correct"]:
                        username = player.get("username") or player.get("display_name") or f"Player {player['user_id']}"
                        question_results.append({
                            "username": username,
                            "points": score_data["points"],
                            "time": score_data["answer_time"]
                        })

            # Sort by points (highest first)
            question_results.sort(key=lambda x: x["points"], reverse=True)

            if question_results:
                results_text = ""
                for result in question_results:
                    results_text += f"**{result['username']}** - {result['points']} pts ({result['time']:.1f}s)\n"
                embed.add_field(
                    name="",
                    value=results_text,
                    inline=False
                )
            else:
                embed.add_field(
                    name="",
                    value="No one got this question right",
                    inline=False
                )

        await channel.send(embed=embed)

        # Show current standings after this question
        try:
            await asyncio.sleep(3)
            await self.show_points_race_standings(channel_id, question_num)
        except Exception as e:
            import traceback
            traceback.print_exc()

        # Restore channel permissions
        await self.restore_channel_permissions(channel)

    async def wait_for_points_race_answers(self, channel: discord.TextChannel, player_ids: List[int],
                                         question: Dict[str, Any], question_data: Dict[str, Any],
                                         timeout: float) -> None:
        """Wait for answers from all Points Race participants and handle scoring using event-driven approach"""
        tournament = active_tournaments.get(channel.id)
        if not tournament:
            return

        # Convert all player IDs to strings for consistent comparison (like round robin)
        participants = [str(pid) for pid in player_ids]

        answered_players = set()
        answer_messages = []  # Store messages for reactions later

        # Set up question context for event-driven message handling
        self.set_question_context(channel.id, participants, question_data)

        start_time = time.time()
        reveal_complete_time = question_data.get("reveal_complete_time", start_time)
        total_players = len(participants)

        try:
            # Event-driven answer processing loop
            while time.time() - start_time < timeout and len(answered_players) < total_players:
                # Process answer queue
                question_context = self.question_contexts.get(channel.id)
                if question_context and 'answer_queue' in question_context:
                    while question_context['answer_queue']:
                        answer_data = question_context['answer_queue'].pop(0)

                        if answer_data['type'] == 'fake_player':
                            # Process fake player answer
                            player_name = answer_data['player_name']
                            answer_text = answer_data['answer']
                            message = answer_data['message']

                            # Find matching fake player ID
                            answering_player_id = None
                            for participant_id in participants:
                                if (participant_id.startswith('fake_') and
                                    player_name in participant_id.lower()):
                                    answering_player_id = participant_id
                                    break

                            if not answering_player_id or answering_player_id in answered_players:
                                continue

                        elif answer_data['type'] == 'regular_player':
                            # Process real player answer
                            answering_player_id = answer_data['user_id']
                            answer_text = answer_data['answer']
                            message = answer_data['message']

                            if answering_player_id in answered_players:
                                continue

                        else:
                            continue

                        # Mark player as answered
                        answered_players.add(answering_player_id)
                        question_context['answered_participants'].add(answering_player_id)

                        try:
                            # Calculate answer time relative to when reveal completed
                            if reveal_complete_time is None:
                                reveal_complete_time = start_time
                            answer_time = time.time() - reveal_complete_time

                            # Calculate points based on time (1000 → 0 over full 20-second window)
                            total_window = POINTS_RACE_REVEAL_TIME + POINTS_RACE_ANSWER_TIME  # 5 + 15 = 20 seconds

                            if answer_time < 0:
                                # Answered before question started (shouldn't happen)
                                points_earned = POINTS_RACE_MAX_POINTS
                            elif answer_time >= total_window:
                                # Answered at/after full timeout
                                points_earned = 0
                            else:
                                # Linear decrease from 1000 points at 0s to 0 points at 20s
                                points_earned = int(POINTS_RACE_MAX_POINTS * (1 - (answer_time / total_window)))

                            # Check if answer is correct
                            is_correct = self.evaluate_answer(answer_text, question)

                            if not is_correct:
                                points_earned = 0

                            # Update player's Points Race score (handle both string and int IDs)
                            for player in tournament["players"]:
                                if str(player["user_id"]) == str(answering_player_id):
                                    if "points_race_scores" not in player:
                                        player["points_race_scores"] = []
                                    player["points_race_scores"].append({
                                        "question_num": len(player["points_race_scores"]) + 1,
                                        "points": points_earned,
                                        "answer_time": answer_time,
                                        "correct": is_correct
                                    })
                                    break

                            # Store message data for later reaction processing (reactions only)
                            answer_messages.append({
                                'message': message,
                                'is_correct': is_correct,
                                'player_id': answering_player_id
                            })

                            # Remove player from Tournament Participant role immediately (but delay reactions)
                            if not str(answering_player_id).startswith('fake_'):
                                try:
                                    # Ensure answering_player_id is an integer for get_member()
                                    player_id_int = int(answering_player_id) if isinstance(answering_player_id, str) else answering_player_id
                                    member = channel.guild.get_member(player_id_int)
                                    if member:
                                        tournament_participant_role = discord.utils.get(channel.guild.roles, name="Tournament Participant")
                                        okran_role = discord.utils.get(channel.guild.roles, name="Okran")

                                        if tournament_participant_role and tournament_participant_role in member.roles:
                                            await member.remove_roles(tournament_participant_role)
                                        if okran_role:
                                            await member.add_roles(okran_role)
                                except (discord.HTTPException, ValueError):
                                    pass

                        except Exception:
                            continue

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)

        finally:
            # Clear question context
            self.clear_question_context(channel.id)


        # Handle players who didn't answer - assign 0 points
        for player in tournament["players"]:
            if str(player["user_id"]) not in answered_players:
                if "points_race_scores" not in player:
                    player["points_race_scores"] = []
                player["points_race_scores"].append({
                    "question_num": len(player["points_race_scores"]) + 1,
                    "points": 0,
                    "answer_time": POINTS_RACE_ANSWER_TIME,
                    "correct": False
                })

                # Remove from Tournament Participant role and add to Okran role (only for real users)
                if not str(player["user_id"]).startswith('fake_'):
                    try:
                        # Ensure user_id is an integer for get_member()
                        player_id_int = int(player["user_id"]) if isinstance(player["user_id"], str) else player["user_id"]
                        member = channel.guild.get_member(player_id_int)
                        if member:
                            tournament_participant_role = discord.utils.get(channel.guild.roles, name="Tournament Participant")
                            okran_role = discord.utils.get(channel.guild.roles, name="Okran")

                            if tournament_participant_role and tournament_participant_role in member.roles:
                                await member.remove_roles(tournament_participant_role)
                            if okran_role:
                                await member.add_roles(okran_role)
                    except (discord.HTTPException, ValueError):
                        pass

        # Process delayed reactions for all answers
        for answer_data in answer_messages:
            message = answer_data['message']
            is_correct = answer_data['is_correct']
            player_id = answer_data['player_id']

            # Add reaction to indicate correct/incorrect
            try:
                if is_correct:
                    await message.add_reaction("✅")
                else:
                    await message.add_reaction("❌")
            except discord.HTTPException:
                pass


    async def show_points_race_standings(self, channel_id: int, question_num: int) -> None:
        """Display current Points Race standings"""

        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return


        # Calculate total points for each player
        player_standings = []

        for i, player in enumerate(tournament["players"]):
            total_points = 0
            questions_answered = 0

            if "points_race_scores" in player:
                for score in player["points_race_scores"]:
                    total_points += score["points"]
                    questions_answered += 1
            else:
                pass

            # Use display_name if username doesn't exist
            username = player.get("username") or player.get("display_name") or f"Player {player['user_id']}"

            player_standings.append({
                "user_id": player["user_id"],
                "username": username,
                "total_points": total_points,
                "questions_answered": questions_answered
            })


        # Sort by total points (descending)
        player_standings.sort(key=lambda x: x["total_points"], reverse=True)

        # Create standings embed
        embed = discord.Embed(
            title=f"🏁 Points Race Standings - After Question {question_num}/{POINTS_RACE_QUESTIONS}",
            color=discord.Color.blue()
        )

        standings_text = ""
        for i, standing in enumerate(player_standings, 1):
            place_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅" if i == 4 else "📍"
            standings_text += f"{place_emoji} **{i}.** {standing['username']} - **{standing['total_points']}** pts\n"


        embed.add_field(
            name="",
            value=standings_text if standings_text else "No standings yet",
            inline=False
        )

        # Add qualification status
        if len(player_standings) >= 4:
            embed.add_field(
                name="",
                value="Top 4 Advance to Semifinals",
                inline=False
            )

        embed.set_footer(text=f"{POINTS_RACE_QUESTIONS - question_num} questions remaining")

        await channel.send(embed=embed)

    async def complete_points_race(self, channel_id: int) -> None:
        """Complete Points Race and advance top 4 to semifinals"""

        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return


        # Calculate final standings
        player_standings = []
        for player in tournament["players"]:
            total_points = 0
            if "points_race_scores" in player:
                for score in player["points_race_scores"]:
                    total_points += score["points"]

            # Use display_name if username doesn't exist
            username = player.get("username") or player.get("display_name") or f"Player {player['user_id']}"

            player_standings.append({
                "user_id": player["user_id"],
                "username": username,
                "total_points": total_points
            })

        # Sort by total points (descending)
        player_standings.sort(key=lambda x: x["total_points"], reverse=True)

        # Create final standings embed
        embed = discord.Embed(
            title="🏆 Points Race Final Results",
            color=discord.Color.gold()
        )

        final_standings_text = ""
        for i, standing in enumerate(player_standings, 1):
            place_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅" if i == 4 else "📍"
            status = " ✅ **Qualified**" if i <= 4 else " ❌ Eliminated"
            final_standings_text += f"{place_emoji} **{i}.** {standing['username']} - **{standing['total_points']}** pts{status}\n"

        embed.add_field(
            name=f"",
            value=final_standings_text,
            inline=False
        )

        await channel.send(embed=embed)
        await asyncio.sleep(5)

        # Update tournament data with seedings for semifinals
        if len(player_standings) >= 4:
            seedings = []
            for i in range(4):
                seedings.append({
                    "user_id": player_standings[i]["user_id"],
                    "seed": i + 1,
                    "total_points": player_standings[i]["total_points"]
                })

            tournament["seedings"] = seedings
            # Store complete Points Race standings for final standings calculation
            tournament["points_race_standings"] = player_standings
            tournament["status"] = "semis"

            # Announce semifinals setup
            semis_embed = discord.Embed(
                title="🏟️ Semifinals Setup",
                description="The top 4 players will now compete in knockout semifinals!",
                color=discord.Color.purple()
            )

            semis_embed.add_field(
                name="",
                value=f"**Match 1:** #{seedings[0]['seed']} {player_standings[0]['username']} vs #{seedings[3]['seed']} {player_standings[3]['username']}\n"
                      f"**Match 2:** #{seedings[1]['seed']} {player_standings[1]['username']} vs #{seedings[2]['seed']} {player_standings[2]['username']}",
                inline=False
            )

            await channel.send(embed=semis_embed)
            await asyncio.sleep(5)

            # Wait a moment before starting semifinals
            await asyncio.sleep(3)
            await self.run_semifinals(channel_id)
        else:
            # Not enough players for semifinals
            embed = discord.Embed(
                title="❌ Tournament Incomplete",
                description="Not enough players qualified for semifinals. Tournament ended.",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)
            tournament["status"] = "completed"

    async def run_semifinals(self, channel_id: int) -> None:
        """Run semifinal matches"""
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)
        seedings = tournament["seedings"]
        
        # Get players by seeding
        players_by_seed = {}
        for player in tournament["players"]:
            for seed_info in seedings:
                if seed_info["user_id"] == player["user_id"]:
                    players_by_seed[seed_info["seed"]] = player
                    break
        
        # Create semifinal matches: #1 vs #4, #2 vs #3
        s1_match = self.create_match(
            tournament["id"], players_by_seed[1], players_by_seed[4],
            "semi", KO_MAX_QUESTIONS, KO_MAX_QUESTIONS
        )

        s2_match = self.create_match(
            tournament["id"], players_by_seed[2], players_by_seed[3],
            "semi", KO_MAX_QUESTIONS, KO_MAX_QUESTIONS
        )

        # Store semifinal matches in tournament
        if "semi_matches" not in tournament:
            tournament["semi_matches"] = []
        tournament["semi_matches"].extend([s1_match, s2_match])

        # Announce and run first semifinal
        match1_embed = discord.Embed(
            title="🔔 Semifinal Match 1",
            description=f"\n**{s1_match['player_a']['display_name']}** vs **{s1_match['player_b']['display_name']}**\n\nMatch will begin in 15 seconds!",
            color=discord.Color.gold()
        )
        await channel.send(embed=match1_embed)
        await asyncio.sleep(15)

        await self.run_match(s1_match, channel)

        # 5 second break after first semifinal results
        await asyncio.sleep(5)

        # Announce and run second semifinal
        match2_embed = discord.Embed(
            title="🔔 Semifinal Match 2",
            description=f"\n**{s2_match['player_a']['display_name']}** vs **{s2_match['player_b']['display_name']}**\n\nMatch will begin in 15 seconds!",
            color=discord.Color.gold()
        )
        await channel.send(embed=match2_embed)
        await asyncio.sleep(15)

        await self.run_match(s2_match, channel)

        await self.setup_final(channel_id)

    async def setup_final(self, channel_id: int) -> None:
        """Setup the final match"""
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        # Get semifinal winners from memory
        semi_matches = tournament.get("semi_matches", [])
        if len(semi_matches) < 2:
            return

        s1_match, s2_match = semi_matches[0], semi_matches[1]

        if not s1_match.get("winner_user_id") or not s2_match.get("winner_user_id"):
            return
        
        # Get winner player objects
        s1_winner = None
        s2_winner = None
        
        for player in tournament["players"]:
            if player["user_id"] == s1_match["winner_user_id"]:
                s1_winner = player
            elif player["user_id"] == s2_match["winner_user_id"]:
                s2_winner = player
        
        if not s1_winner or not s2_winner:
            return
        
        # Create final match
        final_match = self.create_match(
            tournament["id"], s1_winner, s2_winner, "final", KO_MAX_QUESTIONS, KO_MAX_QUESTIONS
        )

        # Store final match in tournament
        tournament["final_match"] = final_match
        tournament["status"] = "final"

        await self.run_final(channel_id)

    async def run_final(self, channel_id: int) -> None:
        """Run the final match"""
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)

        final_match = tournament.get("final_match")
        if not final_match:
            return
        
        # Announce finals bracket
        embed = discord.Embed(
            title="🏆 SEMIFINALS COMPLETE!",
            description="The final matchup has been determined:",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="\u200b\n🥇 Championship Match",
            value=f"**{final_match['player_a']['display_name']}** vs **{final_match['player_b']['display_name']}**",
            inline=False
        )
        embed.add_field(
            name="\u200b\n📋 Format",
            value=f"Best of {KO_MAX_QUESTIONS} wins!",
            inline=False
        )
        embed.add_field(
            name="\u200b\n⏱️ Starting Soon",
            value="Finals will begin in 30 seconds!",
            inline=False
        )
        await channel.send(embed=embed)

        # 15 second break before final announcement
        await asyncio.sleep(15)

        # Announce final match
        final_embed = discord.Embed(
            title="🔔 Final",
            description=f"\n**{final_match['player_a']['display_name']}** vs **{final_match['player_b']['display_name']}**\n\nMatch will begin in 15 seconds!",
            color=discord.Color.gold()
        )
        await channel.send(embed=final_embed)
        await asyncio.sleep(15)

        await self.run_match(final_match, channel)

        await self.complete_tournament(channel_id)

    async def store_tournament_results(self, tournament: Dict) -> None:
        """Store final tournament results for stats/leaderboard"""
        try:
            results_doc = {
                "guild_id": tournament["guild_id"],
                "channel_id": tournament["channel_id"],
                "winner_user_id": tournament.get("winner"),
                "runner_up_user_id": tournament.get("runner_up"),
                "players": [
                    {
                        "user_id": p["user_id"],
                        "display_name": p["display_name"],
                        "final_rank": i + 1
                    }
                    for i, p in enumerate(tournament.get("standings", []))
                ],
                "completed_at": datetime.now(timezone.utc),
                "tournament_format": "round_robin_knockout"
            }

            await self.db.tournament_results.insert_one(results_doc)
            logger.info(f"Stored tournament results for channel {tournament['channel_id']}")
        except Exception as e:
            logger.error(f"Failed to store tournament results: {e}")

    async def complete_tournament(self, channel_id: int) -> None:
        """Complete the tournament and announce results"""
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        # Calculate final standings based on tournament type
        seeding_mode = tournament["config"].get("seeding_mode", "round_robin")
        if seeding_mode == "points_race" and "points_race_standings" in tournament:
            # Use Points Race standings for seeding and tie-breaking
            base_standings = tournament["points_race_standings"]
            tournament["standings"] = base_standings
        else:
            # Use Round Robin standings
            rr_standings = self.compute_rr_standings(tournament)
            tournament["standings"] = rr_standings
            base_standings = rr_standings
        
        # Determine champion and runner-up
        champion = None
        runner_up = None
        
        # Look for final match - check tournament["final_match"] directly
        final_match = tournament.get("final_match")
        if final_match and final_match.get("winner_user_id"):
            # Find champion and runner-up from final
            for player in tournament["players"]:
                if player["user_id"] == final_match["winner_user_id"]:
                    champion = player
                elif player["user_id"] in [final_match["player_a"]["user_id"], final_match["player_b"]["user_id"]]:
                    if player["user_id"] != final_match["winner_user_id"]:
                        runner_up = player
        else:
            # Debug logging for final match issues
            if final_match:
                logger.warning(f"Final match found but no winner_user_id: {final_match.get('winner_user_id')}")
            else:
                logger.warning("No final match found in tournament data")
        
        if not champion and rr_standings:
            # Use RR standings if no knockout
            champion = rr_standings[0]
            if len(rr_standings) > 1:
                runner_up = rr_standings[1]
        
        # Create results embed
        embed = discord.Embed(
            title="🎉 TOURNAMENT COMPLETE! 🎉",
            color=discord.Color.gold()
        )
        
        if champion:
            embed.add_field(
                name="🥇 Champion",
                value=f"**{champion.get('display_name', 'Unknown')}**",
                inline=True
            )
        
        if runner_up:
            embed.add_field(
                name="🥈 Runner-up", 
                value=f"**{runner_up.get('display_name', 'Unknown')}**",
                inline=True
            )
        
        # Add actual tournament standings (not just RR standings)
        if champion or runner_up:
            # Tournament with knockout phases completed
            standings_text = ""
            placement = 1

            # 1st place: Champion
            if champion:
                standings_text += f"{placement}. {champion['display_name']} (Champion)\n"
                placement += 1

            # 2nd place: Runner-up (finalist who lost)
            if runner_up:
                standings_text += f"{placement}. {runner_up['display_name']} (Runner-up)\n"
                placement += 1

            # 3rd & 4th place: Semifinal losers, then all others in base standings order
            remaining_players = []
            if base_standings:
                for player in base_standings:
                    # Skip champion and runner-up, they're already placed
                    if (champion and player["user_id"] == champion["user_id"]) or \
                       (runner_up and player["user_id"] == runner_up["user_id"]):
                        continue
                    remaining_players.append(player)

                # Add remaining players in original standings order (Points Race or RR)
                for player in remaining_players:
                    if seeding_mode == "points_race":
                        # Show Points Race total points
                        points_text = f"{player.get('total_points', 0)} pts"
                        standings_text += f"{placement}. {player.get('username', player.get('display_name', 'Unknown'))} ({points_text})\n"
                    else:
                        # Show Round Robin stats
                        standings_text += f"{placement}. {player['display_name']} ({player['mp']} MP, {player['qp_diff']:+d} QPD)\n"
                    placement += 1

            embed.add_field(name="\u200b\nFinal Standings", value=standings_text, inline=False)
        elif base_standings:
            # Tournament ended early, show base standings
            standings_text = ""
            for i, player in enumerate(base_standings[:5], 1):
                if seeding_mode == "points_race":
                    # Show Points Race total points
                    points_text = f"{player.get('total_points', 0)} pts"
                    standings_text += f"{i}. {player.get('username', player.get('display_name', 'Unknown'))} ({points_text})\n"
                else:
                    # Show Round Robin stats
                    standings_text += f"{i}. {player['display_name']} ({player['mp']} MP, {player['qp_diff']:+d} QPD)\n"
            embed.add_field(name="\u200b\nFinal Standings", value=standings_text, inline=False)
        
        await channel.send(embed=embed)

        # Store winner/runner-up in tournament for results storage
        if champion:
            tournament["winner"] = champion["user_id"]
        if runner_up:
            tournament["runner_up"] = runner_up["user_id"]

        # Store final results in database for stats
        await self.store_tournament_results(tournament)

        # Clear tournament from memory and active questions
        if channel.id in self.active_questions:
            del self.active_questions[channel.id]
        if channel.id in active_tournaments:
            del active_tournaments[channel.id]

        # Clean up the running task (tournament naturally completed)
        if channel.id in self.running_tasks:
            del self.running_tasks[channel.id]

        logger.info(f"Tournament completed in channel {channel.id}")

    async def restrict_channel_permissions(self, channel: discord.TextChannel, allowed_user_ids: List[str]):
        """Restrict channel so only competing players can send messages using roles"""
        try:
            # Import the role IDs from discordbot.py
            import discordbot
            participant_role_id = getattr(discordbot, 'TOURNAMENT_PARTICIPANT_ROLE_ID', None)

            if not participant_role_id:
                logger.error("Tournament Participant role ID not found in discordbot.py")
                return

            # Get the roles
            participant_role = channel.guild.get_role(participant_role_id)
            everyone_role = channel.guild.default_role  # @everyone role

            if not participant_role:
                logger.error("Tournament Participant role not found in guild")
                return

            # Disable @everyone from sending messages (preserve all other permissions)
            # Get current overwrite if it exists, preserving all settings
            current_overwrites = channel.overwrites
            if everyone_role in current_overwrites:
                existing_everyone_perms = current_overwrites[everyone_role]
            else:
                existing_everyone_perms = discord.PermissionOverwrite()

            existing_everyone_perms.send_messages = False
            await channel.set_permissions(everyone_role, overwrite=existing_everyone_perms)

            # Set channel permissions: only participants can send messages (preserve other permissions)
            existing_participant_perms = channel.overwrites_for(participant_role)
            existing_participant_perms.send_messages = True
            await channel.set_permissions(participant_role, overwrite=existing_participant_perms)

            # Assign participant role to the two current participants
            await self.assign_tournament_roles(channel, allowed_user_ids, participant_role)

            logger.debug(f"Restricted permissions in {channel.name} to participants: {allowed_user_ids}")
        except Exception as e:
            logger.error(f"Failed to restrict channel permissions: {e}")

    async def restore_channel_permissions(self, channel: discord.TextChannel):
        """Restore normal channel permissions and remove tournament roles"""
        try:
            # Import the role IDs from discordbot.py
            import discordbot
            participant_role_id = getattr(discordbot, 'TOURNAMENT_PARTICIPANT_ROLE_ID', None)

            everyone_role = channel.guild.default_role  # @everyone role

            # Explicitly enable @everyone messaging (preserve all other permissions)
            # Get current overwrite if it exists, preserving all settings
            current_overwrites = channel.overwrites
            if everyone_role in current_overwrites:
                existing_everyone_perms = current_overwrites[everyone_role]
            else:
                existing_everyone_perms = discord.PermissionOverwrite()

            existing_everyone_perms.send_messages = True  # Explicitly enable with green checkmark
            await channel.set_permissions(everyone_role, overwrite=existing_everyone_perms)

            if participant_role_id:
                participant_role = channel.guild.get_role(participant_role_id)

                if participant_role:
                    # Remove channel permission overrides for tournament participant role (preserve other permissions)
                    existing_participant_perms = channel.overwrites_for(participant_role)
                    existing_participant_perms.send_messages = None  # None = inherit from role/server defaults
                    await channel.set_permissions(participant_role, overwrite=existing_participant_perms)

                    # Remove tournament participant role from all members
                    await self.remove_tournament_roles(channel, participant_role)

            logger.debug(f"Restored permissions in {channel.name}")
        except Exception as e:
            logger.error(f"Failed to restore channel permissions: {e}")

    async def assign_tournament_roles(self, channel: discord.TextChannel, participant_user_ids: List[str],
                                    participant_role: discord.Role):
        """Assign tournament participant role to the current participants"""
        try:
            # Only assign participant role to the two current participants
            for member in channel.guild.members:
                if channel.permissions_for(member).view_channel and not member.bot:
                    if str(member.id) in participant_user_ids:
                        # Add participant role if not already present
                        if participant_role not in member.roles:
                            await member.add_roles(participant_role, reason="Tournament participant")

        except Exception as e:
            logger.error(f"Failed to assign tournament roles: {e}")
            import traceback
            traceback.print_exc()

    async def remove_tournament_roles(self, channel: discord.TextChannel,
                                    participant_role: discord.Role):
        """Remove tournament participant role from all members"""
        try:
            for member in channel.guild.members:
                if participant_role in member.roles:
                    await member.remove_roles(participant_role, reason="Tournament question answered")

        except Exception as e:
            logger.error(f"Failed to remove tournament roles: {e}")

    async def remove_participant_role_after_answer(self, channel: discord.TextChannel, user_id: str):
        """Remove tournament participant role after they submit an answer"""
        try:
            # Skip fake players
            if user_id.startswith('fake_'):
                return

            # Import the role IDs from discordbot.py
            import discordbot
            participant_role_id = getattr(discordbot, 'TOURNAMENT_PARTICIPANT_ROLE_ID', None)

            if not participant_role_id:
                return

            # Get the role
            participant_role = channel.guild.get_role(participant_role_id)

            if not participant_role:
                return

            # Get the member
            member = channel.guild.get_member(int(user_id))
            if not member:
                return

            # Remove participant role after submitting answer
            if participant_role in member.roles:
                await member.remove_roles(participant_role, reason="Submitted answer")

        except Exception as e:
            logger.error(f"Failed to remove participant role after answer: {e}")

    async def assign_points_race_participant_roles(self, channel: discord.TextChannel, player_ids: List[int]) -> None:
        """Assign Tournament Participant role to all Points Race players"""
        try:
            import discordbot
            participant_role_id = getattr(discordbot, 'TOURNAMENT_PARTICIPANT_ROLE_ID', None)

            if not participant_role_id:
                logger.error("Tournament Participant role ID not found in discordbot.py")
                return

            participant_role = channel.guild.get_role(participant_role_id)

            if not participant_role:
                logger.error("Tournament Participant role not found in guild")
                return

            # Assign participant role to all Points Race players
            for player_id in player_ids:
                member = channel.guild.get_member(player_id)
                if member and participant_role not in member.roles:
                    await member.add_roles(participant_role, reason="Points Race participant")

        except Exception as e:
            logger.error(f"Failed to assign Points Race participant roles: {e}")

    async def run_match(self, match: Dict, channel: discord.TextChannel) -> None:
        """Run a single match (RR or KO)"""
        if match.get("completed_at"):
            return

        # Mark match as started in memory
        match["started_at"] = datetime.now(timezone.utc)

        # Get tournament from memory
        tournament = active_tournaments.get(channel.id)
        if not tournament:
            logger.error(f"No tournament found in memory for channel {channel.id}")
            logger.error(f"Active tournaments: {list(active_tournaments.keys())}")
            return

        config = tournament["config"]
        
        player_a_id = match["player_a"]["user_id"]
        player_b_id = match["player_b"]["user_id"]
        
        score_a = 0
        score_b = 0
        questions_asked = 0
        questions_correct_a = 0  # Count of questions answered correctly by player A
        questions_correct_b = 0  # Count of questions answered correctly by player B
        
        is_ko = match["phase"] in ["semi", "final"]
        target_questions = match["questions_target"]
        
        while True:
            # Check if match should end
            if is_ko:
                # KO phases: continue until someone has more points (no draws allowed)
                # Hard cap at 10 questions to prevent indefinite matches
                if questions_asked >= 10 and questions_correct_a == questions_correct_b:
                    # Force random winner selection after 10 questions
                    import random
                    random_winner = random.choice([player_a_id, player_b_id])

                    # Award points to random winner to break tie
                    if random_winner == player_a_id:
                        questions_correct_a += 1
                        score_a += 10  # Always use 10 points
                    else:
                        questions_correct_b += 1
                        score_b += 10

                    # Announce random winner selection
                    random_embed = discord.Embed(
                        title="🎲 Random Winner Selected!",
                        description="It's clear neither player has any idea what's going on.\n\nRandomly selecting a winner to move forward.",
                        color=discord.Color.purple()
                    )
                    await channel.send(embed=random_embed)
                    break

                # After target_questions, announce sudden death if tied
                elif questions_asked >= target_questions and questions_correct_a == questions_correct_b:
                    if questions_asked == target_questions:  # First time hitting limit
                        sudden_death_embed = discord.Embed(
                            title="🔥 TIE! SUDDEN DEATH! 🔥",
                            description="Continuing until we have a winner...",
                            color=discord.Color.orange()
                        )
                        await channel.send(embed=sudden_death_embed)
                        # 15 second delay before first sudden death question
                        await asyncio.sleep(15)
                    # Continue asking questions
                elif questions_asked >= target_questions and questions_correct_a != questions_correct_b:
                    # Someone is ahead after target questions, end match
                    break
                # Check for mathematical impossibility based on question counts
                remaining_questions = target_questions - questions_asked
                if questions_asked < target_questions:
                    if questions_correct_a > questions_correct_b + remaining_questions:
                        # Player A has already won (B can't catch up)
                        break
                    elif questions_correct_b > questions_correct_a + remaining_questions:
                        # Player B has already won (A can't catch up)
                        break
            else:
                # RR phases: max questions format with early termination
                if questions_asked >= target_questions:
                    break

                # Check if match is mathematically decided based on question counts
                remaining_questions = target_questions - questions_asked
                if questions_correct_a > questions_correct_b + remaining_questions:
                    # Player A has already won (B can't catch up)
                    break
                elif questions_correct_b > questions_correct_a + remaining_questions:
                    # Player B has already won (A can't catch up)
                    break
            
            questions_asked += 1
            
            # Select and ask question
            question = await self.select_head_to_head_question()
            
            answers = question.get("answers", [])
            if not answers:
                answers = [question.get("answer", "No answer available")]

            # Display first answer or all answers if multiple, in all caps
            if len(answers) == 1:
                answer_text = answers[0].upper()
            else:
                answer_text = " / ".join([ans.upper() for ans in answers])

            if not question:
                continue
            
            # First embed - Score info
            score_embed = discord.Embed(
                title="**Score**",
                color=discord.Color.blue()
            )

            # Add individual player scores
            score_text = f"{match['player_a']['display_name']}: {score_a}\n{match['player_b']['display_name']}: {score_b}"
            score_embed.description = score_text

            # Send first embed
            await channel.send(embed=score_embed)

            # Wait 3 seconds
            await asyncio.sleep(3)

            # Second embed - Question text and image
            category_text = question.get("category", "General")
            question_title = f"⚡ Question {questions_asked}/{target_questions}: {category_text}"

            # Store active question
            self.active_questions[channel.id] = {
                "match": match,
                "question": question,
                "participants": [player_a_id, player_b_id],
                "start_time": asyncio.get_event_loop().time()
            }

            # Check if progressive mode
            current_mode = config.get("mode", "standard")
            if current_mode == "progressive":
                # Progressive mode: reveal question character by character
                full_prompt = question["prompt"]
                answer_timeout = config["answer_timeout_sec"]
                reveal_duration = answer_timeout - 3  # Reveal for all but last 3 seconds

                if reveal_duration > 0:
                    # Fixed reveal duration with 1 update per second
                    reveal_time = RR_REVEAL_TIME
                    update_interval = 1.0  # Update every 1 second
                    total_updates = int(RR_REVEAL_TIME)  # Updates based on reveal time
                    chars_per_update = len(full_prompt) / total_updates if total_updates > 0 else len(full_prompt)

                    # Restrict channel permissions BEFORE sending embed
                    await self.restrict_channel_permissions(channel, [player_a_id, player_b_id])

                    # Initial embed with just title - NO question text
                    question_embed = discord.Embed(
                        title=question_title,
                        description="",  # Start with empty description
                        color=discord.Color.blue()
                    )

                    # Add image if URL starts with http
                    question_url = question.get("url", "")
                    if question_url and question_url.startswith("http"):
                        question_embed.set_image(url=question_url)

                    message = await channel.send(embed=question_embed)

                    # Start answer monitoring in background while revealing question
                    async def progressive_reveal(msg):
                        current_message = msg
                        for update_num in range(1, total_updates + 1):
                            # Sleep first, then update
                            await asyncio.sleep(update_interval)

                            # Calculate how many characters to show
                            chars_to_show = int(chars_per_update * update_num)
                            chars_to_show = min(chars_to_show, len(full_prompt))  # Don't exceed prompt length

                            # Update embed with partial prompt
                            partial_text = full_prompt[:chars_to_show]
                            question_embed.description = partial_text

                            try:
                                await current_message.edit(embed=question_embed)
                            except discord.NotFound:
                                # Message was deleted, send new one
                                current_message = await channel.send(embed=question_embed)
                            except discord.HTTPException as e:
                                if e.status == 429:  # Rate limited
                                    retry_after = e.response.headers.get('retry-after', 1)
                                    await asyncio.sleep(float(retry_after))
                                    # Try editing again after rate limit
                                    try:
                                        await current_message.edit(embed=question_embed)
                                    except:
                                        pass
                                pass

                        # Ensure the full question is shown at the end
                        if question_embed.description != full_prompt:
                            question_embed.description = full_prompt
                            try:
                                await current_message.edit(embed=question_embed)
                            except (discord.NotFound, discord.HTTPException):
                                pass

                    # Start progressive reveal in background
                    reveal_task = asyncio.create_task(progressive_reveal(message))

                    # Start answer monitoring immediately for the entire question duration
                    answer_task = asyncio.create_task(self.wait_for_answer(
                        channel, [player_a_id, player_b_id],
                        question, reveal_time + 10  # 5s reveal + 10s answer = 15s total
                    ))

                    # Wait for either reveal completion or early answer
                    done, pending = await asyncio.wait(
                        [reveal_task, answer_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # If someone answered early, cancel reveal and return result
                    if answer_task in done:
                        if not reveal_task.done():
                            reveal_task.cancel()

                            # Update embed with full question since someone answered
                            question_embed.description = full_prompt
                            try:
                                await message.edit(embed=question_embed)
                            except (discord.NotFound, discord.HTTPException):
                                pass  # Ignore if message can't be edited

                        answer_result = await answer_task
                    else:
                        # Reveal completed, continue waiting for the existing answer_task
                        answer_result = await answer_task

                else:
                    # If reveal duration is 0 or negative, show full question immediately
                    # Restrict channel permissions BEFORE sending embed
                    await self.restrict_channel_permissions(channel, [player_a_id, player_b_id])

                    question_embed = discord.Embed(
                        title=question_title,
                        description=question["prompt"],
                        color=discord.Color.blue()
                    )

                    question_url = question.get("url", "")
                    if question_url and question_url.startswith("http"):
                        question_embed.set_image(url=question_url)

                    await channel.send(embed=question_embed)
                    answer_result = await self.wait_for_answer(
                        channel, [player_a_id, player_b_id],
                        question, config["answer_timeout_sec"]
                    )
            else:
                # Standard mode: show full question immediately
                # Restrict channel permissions BEFORE sending embed
                await self.restrict_channel_permissions(channel, [player_a_id, player_b_id])

                question_embed = discord.Embed(
                    title=question_title,
                    description=question["prompt"],
                    color=discord.Color.blue()
                )

                # Add image if URL starts with http
                question_url = question.get("url", "")
                if question_url and question_url.startswith("http"):
                    question_embed.set_image(url=question_url)

                await channel.send(embed=question_embed)

                # Wait for answer or timeout
                answer_result = await self.wait_for_answer(
                    channel, [player_a_id, player_b_id],
                    question, config["answer_timeout_sec"]
                )
            
            # Process answer result
            awarded_points = 0
            answered_by = None
            correct = False
            
            if answer_result and "user_id" in answer_result:
                # Someone answered correctly
                answered_by = answer_result["user_id"]
                correct = True
                awarded_points = config["points_per_question"]

                if answered_by == player_a_id:
                    score_a += awarded_points  # Always use 10 points per question for all rounds
                    questions_correct_a += 1
                else:
                    score_b += awarded_points  # Always use 10 points per question for all rounds
                    questions_correct_b += 1

                # Announce correct answer
                # Handle fake players vs real users
                if answered_by.startswith('fake_'):
                    # For fake players, use the display name from memory
                    player_name = "Unknown"
                    for player in tournament["players"]:
                        if player["user_id"] == answered_by:
                            player_name = player["display_name"]
                            break

                    embed = discord.Embed(
                        title=f"✅ {player_name}",
                        description=f"Answer: **{answer_text}**",
                        color=discord.Color.green()
                    )
                else:
                    # For real users
                    user = self.bot.get_user(int(answered_by))
                    embed = discord.Embed(
                        title=f"✅ {user.display_name}",
                        description=f"Answer: **{answer_text}**",
                        color=discord.Color.green()
                    )
                #embed.add_field(name="Answer", value=question["answer"].upper())
                if is_ko:
                    embed.add_field(name="Score", value=f"{score_a} - {score_b}")
                await channel.send(embed=embed)
            elif answer_result and answer_result.get("both_wrong"):
                # Both contestants answered incorrectly
                embed = discord.Embed(
                    title="❌ Both contestants answered incorrectly!",
                    description=f"Answer: **{answer_text}**",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed)
            else:
                # Actual timeout - no one answered
                embed = discord.Embed(
                    title="⏰ Time's up!",
                    description=f"Answer: **{answer_text}**",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed)
            
            # Update match score in memory (no detailed logging needed)
            match["score"]["a"] = score_a
            match["score"]["b"] = score_b
            
            # Clear active question
            if channel.id in self.active_questions:
                del self.active_questions[channel.id]

            # Restore channel permissions for everyone
            await self.restore_channel_permissions(channel)

            # Small delay between questions
            await asyncio.sleep(5)
        
        # Determine match result
        winner_user_id = None
        is_draw = False
        
        # Determine match result
        if score_a > score_b:
            winner_user_id = player_a_id
        elif score_b > score_a:
            winner_user_id = player_b_id
        else:
            # Only RR phases can end in draws (KO phases use sudden death)
            is_draw = True
        
        # Complete match in memory
        match["winner_user_id"] = winner_user_id
        match["draw"] = is_draw
        match["completed_at"] = datetime.now(timezone.utc)
        
        # Announce match result with current standings
        tournament = active_tournaments.get(channel.id)
        if is_draw:
            result_embed = discord.Embed(
                title="🤝 Match Result: Draw",
                description=f"Final Score: {score_a} - {score_b}",
                color=discord.Color.yellow()
            )
        else:
            winner_name = (match["player_a"]["display_name"] if winner_user_id == player_a_id
                          else match["player_b"]["display_name"])
            result_embed = discord.Embed(
                title=f"🏆 {winner_name} wins!",
                description=f"Final Score: {score_a} - {score_b}",
                color=discord.Color.green()
            )

        # Add current standings if tournament is found
        if tournament and tournament["status"] == "rr":
            standings = self.compute_rr_standings(tournament)
            if standings:
                standings_text = "\n".join([
                    f"`{i+1}.` **{player['display_name']}** `({player.get('mw', 0)}-{player.get('md', 0)}-{player.get('ml', 0)})` **{player.get('mp', 0)} MP**"
                    for i, player in enumerate(standings)
                ])
                result_embed.add_field(
                    name="\u200b\n📊 Current Standings",
                    value=standings_text,
                    inline=False
                )

        await channel.send(embed=result_embed)

        # Just wait 5 seconds between matches (next matchup is announced in match flow)
        if tournament and tournament["status"] == "rr":
            await asyncio.sleep(5)

    async def wait_for_answer(self, channel: discord.TextChannel,
                            participants: List[str], question_data: Dict,
                            timeout_sec: int) -> Optional[Dict]:
        """Wait for a correct answer from participants using event-driven approach"""
        answered_participants = set()  # Track which participants have answered

        # Set up question context for event-driven message handling
        self.set_question_context(channel.id, participants, question_data)

        start_time = time.time()

        try:
            # Event-driven answer processing loop
            while time.time() - start_time < timeout_sec:
                # Process answer queue
                question_context = self.question_contexts.get(channel.id)
                if question_context and 'answer_queue' in question_context:
                    while question_context['answer_queue']:
                        answer_data = question_context['answer_queue'].pop(0)

                        if answer_data['type'] == 'fake_player':
                            # Process fake player answer
                            player_name = answer_data['player_name']
                            answer = answer_data['answer']
                            message = answer_data['message']

                            # Find matching fake player ID
                            fake_user_id = None
                            for participant_id in participants:
                                if (participant_id.startswith('fake_') and
                                    player_name in participant_id.lower()):
                                    fake_user_id = participant_id
                                    break

                            if not fake_user_id or fake_user_id in answered_participants:
                                continue

                            evaluation_result = self.evaluate_answer(answer, question_data)

                            if evaluation_result:
                                # FIRST correct answer wins - immediately return
                                await self.remove_participant_role_after_answer(channel, fake_user_id)

                                try:
                                    await message.add_reaction("✅")
                                except discord.HTTPException:
                                    pass

                                return {
                                    "user_id": fake_user_id,
                                    "answer": answer
                                }
                            else:
                                # Wrong answer - add X reaction and track participant
                                try:
                                    await message.add_reaction("❌")
                                except discord.HTTPException:
                                    pass

                                await self.remove_participant_role_after_answer(channel, fake_user_id)
                                answered_participants.add(fake_user_id)
                                question_context['answered_participants'].add(fake_user_id)

                                # Check if all participants have now answered incorrectly
                                if len(answered_participants) >= len(participants):
                                    return {"both_wrong": True}

                        elif answer_data['type'] == 'regular_player':
                            # Process real player answer
                            user_id = answer_data['user_id']
                            answer = answer_data['answer']
                            message = answer_data['message']

                            if user_id in answered_participants:
                                continue

                            evaluation_result = self.evaluate_answer(answer, question_data)

                            if evaluation_result:
                                # FIRST correct answer wins - immediately return
                                await self.remove_participant_role_after_answer(channel, user_id)

                                try:
                                    await message.add_reaction("✅")
                                except discord.HTTPException:
                                    pass

                                return {
                                    "user_id": user_id,
                                    "answer": answer
                                }
                            else:
                                # Wrong answer - add X reaction and track participant
                                try:
                                    await message.add_reaction("❌")
                                except discord.HTTPException:
                                    pass

                                await self.remove_participant_role_after_answer(channel, user_id)
                                answered_participants.add(user_id)
                                question_context['answered_participants'].add(user_id)

                                # Check if all participants have now answered incorrectly
                                if len(answered_participants) >= len(participants):
                                    return {"both_wrong": True}

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)

            # Timeout reached
            return None

        finally:
            # Clear question context
            self.clear_question_context(channel.id)
    
    def evaluate_answer(self, user_answer: str, question_data: Dict) -> bool:
        """Check if user answer matches any of the correct answers"""
        if not user_answer:
            return False
        
        # Get all possible answers
        answers = question_data.get("answers", [])
        if not answers:
            # Fallback to single answer field
            single_answer = question_data.get("answer", "")
            if single_answer:
                answers = [single_answer]
        
        if not answers:
            return False
        
        # Use fuzzy match function if available
        if self.fuzzy_match_func:
            try:
                category = question_data.get("category", "")
                url = question_data.get("url", "")
                
                # Check against all possible answers
                for correct_answer in answers:
                    result = self.fuzzy_match_func(user_answer, correct_answer, category, url)
                    if result:
                        return True
                return False
            except Exception as e:
                logger.error(f"Error using fuzzy match function: {e}")
                # Fall back to simple matching
        
        # Simple fallback matching
        user_answer = user_answer.strip().lower()
        for correct_answer in answers:
            if user_answer == correct_answer.strip().lower():
                return True
        return False

    async def select_head_to_head_question(self) -> Optional[Dict]:
        """Select a random question from jeopardy_questions or trivia_questions with configurable percentages"""
        try:
            # Get recent tournament question IDs to exclude
            recent_ids = await self.get_recent_tournament_question_ids()

            # Randomly choose collection based on configured percentages
            rand_num = random.randint(1, 100)
            if rand_num <= JEOPARDY_PERCENTAGE:
                collection_name = "jeopardy_questions"
                question_type = "jeopardy"
            else:
                collection_name = "trivia_questions"
                question_type = "trivia"

            # Query the selected collection
            collection = self.db[collection_name]
            exclude_ids = list(recent_ids.get(question_type, set()))
            pipeline = [
                {"$match": {"_id": {"$nin": exclude_ids}}},
                {"$sample": {"size": 1}}
            ]

            cursor = collection.aggregate(pipeline)
            docs = await cursor.to_list(length=1)

            if docs:
                doc = docs[0]

                # Handle answers array
                answers = doc.get("answers", [])
                if not answers:
                    single_answer = doc.get("answer", "")
                    if single_answer:
                        answers = [single_answer]

                first_answer = answers[0] if answers else ""

                # Store the selected question ID in tournament tracking
                question_ids_to_store = {question_type: [doc["_id"]]}
                await self.store_tournament_question_ids(question_ids_to_store)

                # Debug logging for question audit
                print(f"Question: {doc.get('question', doc.get('clue', 'N/A'))}")
                print(f"Answer: {first_answer}")

                return {
                    "q_id": str(doc["_id"]),
                    "source": question_type,
                    "prompt": doc.get("question", doc.get("clue", "")),
                    "answer": first_answer,
                    "answers": answers,
                    "category": doc.get("category", ""),
                    "url": doc.get("url", "")
                }

        except Exception as e:
            logger.error(f"Error selecting tournament question: {e}")

        return None

    def compute_rr_standings(self, tournament: Dict) -> List[Dict]:
        """Compute round-robin standings from memory"""
        # Get all completed RR matches
        rr_matches = [
            match for match in tournament["matches"]
            if match["phase"] == "rr" and match.get("completed_at")
        ]
        
        # Initialize player stats
        player_stats = {}
        for player in tournament["players"]:
            player_stats[player["user_id"]] = {
                "user_id": player["user_id"],
                "display_name": player["display_name"],
                "mp": 0,  # match points
                "mw": 0, "md": 0, "ml": 0,  # match wins/draws/losses
                "qp_for": 0, "qp_against": 0, "qp_diff": 0,  # question points
                "joined_at": player["joined_at"]
            }
        
        # Process matches
        match_points = tournament["config"]["match_points"]
        
        for match in rr_matches:
            a_id = match["player_a"]["user_id"]
            b_id = match["player_b"]["user_id"]
            
            a_score = match["score"]["a"]
            b_score = match["score"]["b"]
            
            # Update question points
            player_stats[a_id]["qp_for"] += a_score
            player_stats[a_id]["qp_against"] += b_score
            player_stats[b_id]["qp_for"] += b_score
            player_stats[b_id]["qp_against"] += a_score
            
            # Update match points
            if match.get("draw"):
                player_stats[a_id]["mp"] += match_points["tie"]
                player_stats[b_id]["mp"] += match_points["tie"]
                player_stats[a_id]["md"] += 1
                player_stats[b_id]["md"] += 1
            elif match.get("winner_user_id") == a_id:
                player_stats[a_id]["mp"] += match_points["win"]
                player_stats[b_id]["mp"] += match_points["loss"]
                player_stats[a_id]["mw"] += 1
                player_stats[b_id]["ml"] += 1
            elif match.get("winner_user_id") == b_id:
                player_stats[b_id]["mp"] += match_points["win"]
                player_stats[a_id]["mp"] += match_points["loss"]
                player_stats[b_id]["mw"] += 1
                player_stats[a_id]["ml"] += 1
        
        # Calculate point differentials
        for stats in player_stats.values():
            stats["qp_diff"] = stats["qp_for"] - stats["qp_against"]
        
        # Sort by: 1) Match Points, 2) Question Point Diff, 3) Join time
        standings = sorted(
            player_stats.values(),
            key=lambda x: (-x["mp"], -x["qp_diff"], x["joined_at"])
        )
        
        return standings

    async def get_tournament_status(self, channel: discord.TextChannel) -> Optional[discord.Embed]:
        """Get tournament status embed"""
        tournament = self.load_tournament_by_channel(channel.id)
        if not tournament:
            return discord.Embed(
                title="No Active Tournament",
                description="No tournament is currently running in this channel.",
                color=discord.Color.gray()
            )
        
        embed = discord.Embed(
            title=f"Tournament Status - {tournament['status'].upper()}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Players",
            value=f"{len(tournament['players'])} joined",
            inline=True
        )
        
        if tournament["status"] == "signup":
            embed.add_field(
                name="Phase",
                value="Signup in progress",
                inline=True
            )
        elif tournament["status"] == "rr":
            embed.add_field(
                name="Phase", 
                value="Round Robin",
                inline=True
            )
            
            # Show current standings
            standings = self.compute_rr_standings(tournament)
            if standings:
                standings_text = ""
                for i, player in enumerate(standings[:5], 1):
                    standings_text += f"{i}. {player['display_name']} ({player['mw']}-{player['md']}-{player['ml']}) - {player['mp']} MP\n"
                embed.add_field(name="\u200b\nCurrent Standings", value=standings_text, inline=False)
                
        elif tournament["status"] in ["semis", "final"]:
            embed.add_field(
                name="Phase",
                value="Knockout Stage",
                inline=True
            )
        
        return embed

    async def cancel_tournament(self, channel: discord.TextChannel, user: discord.Member) -> bool:
        """Cancel the active tournament (admin only)"""
        if not user.guild_permissions.manage_channels:
            return False

        tournament = self.load_tournament_by_channel(channel.id)
        if not tournament:
            return False

        # Cancel running tournament task
        if channel.id in self.running_tasks:
            self.running_tasks[channel.id].cancel()
            del self.running_tasks[channel.id]

        # Clean up roles and restore permissions
        await self.restore_channel_permissions(channel)

        # Remove tournament from memory
        if channel.id in active_tournaments:
            del active_tournaments[channel.id]

        # Clear active question state
        if channel.id in self.active_questions:
            del self.active_questions[channel.id]

        return True

    async def add_fake_players_to_tournament(self, channel: discord.TextChannel) -> bool:
        """Add fake players to active tournament for testing purposes"""
        tournament = self.load_tournament_by_channel(channel.id)
        if not tournament:
            return False

        if tournament["status"] != "signup":
            return False

        # Check if fake players are already added
        existing_fake_players = [p for p in tournament["players"] if p["user_id"].startswith("fake_")]
        if existing_fake_players:
            return False  # Already have fake players

        # Create fake players (same structure as in local_mode)
        fake_players = [
            {
                "user_id": "fake_alpha",
                "display_name": "Alpha",
                "joined_at": datetime.now(timezone.utc),
                "active": True,
                "afk_strikes": 0
            },
            {
                "user_id": "fake_beta",
                "display_name": "Beta",
                "joined_at": datetime.now(timezone.utc),
                "active": True,
                "afk_strikes": 0
            },
            {
                "user_id": "fake_gamma",
                "display_name": "Gamma",
                "joined_at": datetime.now(timezone.utc),
                "active": True,
                "afk_strikes": 0
            },
            {
                "user_id": "fake_delta",
                "display_name": "Delta",
                "joined_at": datetime.now(timezone.utc),
                "active": True,
                "afk_strikes": 0
            }
        ]

        # Add fake players to tournament in memory
        tournament["players"].extend(fake_players)

        print(f"🤖 Added {len(fake_players)} fake players for testing via /test command")
        await channel.send(f"🤖 Added {len(fake_players)} fake players for testing!")

        return True

    # Event-driven message handling methods

    def should_handle_message(self, message: discord.Message) -> bool:
        """Determine if a message should be handled by the tournament system"""
        if message.author.bot:
            return False

        channel_id = message.channel.id

        # Check if this channel has any active tournament contexts
        if (channel_id in self.signup_contexts or
            channel_id in self.question_contexts or
            channel_id in self.active_tournament_channels):
            return True

        return False

    async def handle_message(self, message: discord.Message) -> bool:
        """Handle tournament-related messages. Returns True if message was handled."""
        channel_id = message.channel.id

        try:
            # Handle signup messages
            if channel_id in self.signup_contexts:
                return await self._handle_signup_message(message)

            # Handle question answer messages
            if channel_id in self.question_contexts:
                return await self._handle_question_message(message)

            return False

        except Exception as e:
            logger.error(f"Error handling tournament message: {e}")
            return False

    async def _handle_signup_message(self, message: discord.Message) -> bool:
        """Handle messages during tournament signup phase"""
        channel_id = message.channel.id
        signup_context = self.signup_contexts.get(channel_id)

        if not signup_context:
            return False

        # Check if message is "okra" signup
        if message.content.lower().strip() != "okra":
            return False

        # Check if user has privileged tournament role
        import discordbot
        okran_role_id = getattr(discordbot, 'OKRAN_ROLE_ID', None)
        okran_role_id_2 = getattr(discordbot, 'OKRAN_ROLE_ID_2', None)
        bumper_king_role_id = getattr(discordbot, 'BUMPER_KING_ROLE_ID', None)

        has_tournament_role = False
        if okran_role_id and any(role.id == okran_role_id for role in message.author.roles):
            has_tournament_role = True
        elif okran_role_id_2 and any(role.id == okran_role_id_2 for role in message.author.roles):
            has_tournament_role = True
        elif bumper_king_role_id and any(role.id == bumper_king_role_id for role in message.author.roles):
            has_tournament_role = True

        # Add to appropriate queue for processing
        if has_tournament_role:
            if 'signup_queue' not in signup_context:
                signup_context['signup_queue'] = []
            signup_context['signup_queue'].append({
                'user_id': message.author.id,
                'display_name': message.author.display_name,
                'message': message,
                'privileged': True
            })
        else:
            if 'waitlist_queue' not in signup_context:
                signup_context['waitlist_queue'] = []
            signup_context['waitlist_queue'].append({
                'user_id': message.author.id,
                'display_name': message.author.display_name,
                'message': message,
                'privileged': False
            })

        return True

    async def _handle_question_message(self, message: discord.Message) -> bool:
        """Handle messages during tournament question phase"""
        channel_id = message.channel.id
        question_context = self.question_contexts.get(channel_id)

        if not question_context:
            return False

        participants = question_context.get('participants', [])
        fake_players = ["alpha", "beta", "gamma", "delta"]

        words = message.content.strip().split()

        # Handle fake player commands
        if (len(words) >= 2 and words[0].lower() in fake_players):
            import discordbot
            host_role_id = getattr(discordbot, 'HOST_ROLE_ID', None)
            has_host_role = host_role_id and any(role.id == host_role_id for role in message.author.roles)

            if has_host_role:
                # Add to answer queue for processing
                if 'answer_queue' not in question_context:
                    question_context['answer_queue'] = []

                question_context['answer_queue'].append({
                    'type': 'fake_player',
                    'player_name': words[0].lower(),
                    'answer': ' '.join(words[1:]),
                    'message': message
                })
                return True

        # Handle regular player answers
        user_id = str(message.author.id)
        if user_id in participants:
            answered_participants = question_context.get('answered_participants', set())

            if user_id not in answered_participants:
                # Add to answer queue for processing
                if 'answer_queue' not in question_context:
                    question_context['answer_queue'] = []

                question_context['answer_queue'].append({
                    'type': 'regular_player',
                    'user_id': user_id,
                    'answer': message.content,
                    'message': message
                })
                return True

        return False

    def set_signup_context(self, channel_id: int, tournament_data: Dict):
        """Set up signup context for a tournament"""
        self.signup_contexts[channel_id] = {
            'tournament': tournament_data,
            'signup_queue': []
        }
        self.active_tournament_channels.add(channel_id)

    def clear_signup_context(self, channel_id: int):
        """Clear signup context when signup phase ends"""
        if channel_id in self.signup_contexts:
            del self.signup_contexts[channel_id]

    def set_question_context(self, channel_id: int, participants: List[str], question_data: Dict):
        """Set up question context for answer collection"""
        self.question_contexts[channel_id] = {
            'participants': participants,
            'question_data': question_data,
            'answer_queue': [],
            'answered_participants': set()
        }
        self.active_tournament_channels.add(channel_id)

    def clear_question_context(self, channel_id: int):
        """Clear question context when question phase ends"""
        if channel_id in self.question_contexts:
            del self.question_contexts[channel_id]

    def clear_tournament_context(self, channel_id: int):
        """Clear all tournament contexts for a channel"""
        self.clear_signup_context(channel_id)
        self.clear_question_context(channel_id)
        if channel_id in self.active_tournament_channels:
            self.active_tournament_channels.remove(channel_id)

    async def update_signup_embed(self, channel_id: int):
        """Update the signup embed with current joined players and waitlist"""
        tournament = active_tournaments.get(channel_id)
        if not tournament or "signup_embed" not in tournament or "signup_message" not in tournament:
            return

        # Get current players
        players = tournament.get("players", [])
        player_count = len(players)

        # Get waitlist
        waitlist = tournament.get("waitlist", [])
        waitlist_count = len(waitlist)

        # Create participants text
        if player_count == 0:
            participants_text = "*Waiting for players...*"
        else:
            participants_list = []
            for player in players:
                display_name = player.get("display_name", f"Player {player['user_id']}")
                participants_list.append(f"🏆 {display_name}")
            participants_text = "\n".join(participants_list)

        # Create waitlist text
        if waitlist_count == 0:
            waitlist_text = "*No one waiting*"
        else:
            waitlist_list = []
            for entry in waitlist:
                display_name = entry.get("display_name", f"Player {entry['user_id']}")
                waitlist_list.append(f"⏳ {display_name}")
            waitlist_text = "\n".join(waitlist_list)

        # Update the embed
        embed = tournament["signup_embed"]
        # Find and update the joined players field (it should be the last field)
        if embed.fields:
            # Remove the last field (old joined players field)
            embed.remove_field(len(embed.fields) - 1)

            # Add two new fields: Participants and Waitlist
            embed.add_field(
                name=f"✅ Participants ({player_count}/{MAX_PLAYERS_DEFAULT})",
                value=participants_text,
                inline=False
            )
            embed.add_field(
                name=f"📋 Waitlist ({waitlist_count})",
                value=waitlist_text,
                inline=False
            )

            # Try to edit the message
            try:
                signup_message = tournament["signup_message"]
                await signup_message.edit(embed=embed)
            except (discord.NotFound, discord.HTTPException):
                # Message might have been deleted or we can't edit it
                pass


class TournamentCog(commands.Cog):
    """Discord cog for tournament slash commands"""
    
    def __init__(self, bot: commands.Bot, tournament_manager: TournamentManager, allowed_channel_id: int = None):
        self.bot = bot
        self.tournament_manager = tournament_manager
        self.allowed_channel_id = allowed_channel_id
    
    def _is_channel_allowed(self, interaction: discord.Interaction) -> bool:
        """Check if command is being used in allowed channel"""
        if self.allowed_channel_id is None:
            # If no specific channel set, allow only in designated tournament channel
            return validate_tournament_channel(interaction.channel)
        return interaction.channel.id == self.allowed_channel_id

    @discord.app_commands.command(name="start", description="Start a new tournament")
    async def start(self, interaction: discord.Interaction):
        if not self._is_channel_allowed(interaction):
            await interaction.response.send_message(
                "❌ Tournament commands can only be used in the designated tournament channel",
                ephemeral=True
            )
            return

        # Check if user has OKRAN_ROLE_ID or BUMPER_KING_ROLE_ID
        import discordbot
        okran_role_id = getattr(discordbot, 'OKRAN_ROLE_ID', None)
        okran_role_id_2 = getattr(discordbot, 'OKRAN_ROLE_ID_2', None)
        bumper_king_role_id = getattr(discordbot, 'BUMPER_KING_ROLE_ID', None)

        has_tournament_role = False
        if okran_role_id and any(role.id == okran_role_id for role in interaction.user.roles):
            has_tournament_role = True
        elif okran_role_id_2 and any(role.id == okran_role_id_2 for role in interaction.user.roles):
            has_tournament_role = True
        elif bumper_king_role_id and any(role.id == bumper_king_role_id for role in interaction.user.roles):
            has_tournament_role = True

        if not has_tournament_role:
            await interaction.response.send_message(
                "Tournaments can only be started by Okrans and The Bumper King.",
                ephemeral=True
            )
            return

        try:
            print(f"🏆 Starting tournament with default settings")
            await self.tournament_manager.start_tournament(interaction)
            print("✅ Tournament started successfully")
        except ChannelError as e:
            print(f"❌ ChannelError: {e}")
            await interaction.response.send_message(
                "❌ Tournaments can only be started in the designated tournament channel",
                ephemeral=True
            )
        except ActiveTournamentError as e:
            print(f"❌ ActiveTournamentError: {e}")
            await interaction.response.send_message(
                f"❌ {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            print(f"❌ Unexpected error starting tournament: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            try:
                await interaction.response.send_message(
                    f"❌ Error starting tournament: {e}",
                    ephemeral=True
                )
            except:
                print("❌ Could not send error response to Discord")

    @discord.app_commands.command(name="status", description="Show tournament status")
    async def status(self, interaction: discord.Interaction):
        if not self._is_channel_allowed(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the designated tournament channel",
                ephemeral=True
            )
            return
        
        embed = await self.tournament_manager.get_tournament_status(interaction.channel)
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="cancel", description="Cancel the active tournament")
    async def cancel(self, interaction: discord.Interaction):
        if not self._is_channel_allowed(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the designated tournament channel",
                ephemeral=True
            )
            return

        # Check if user has HOST_ROLE_ID to cancel tournaments
        import discordbot
        host_role_id = getattr(discordbot, 'HOST_ROLE_ID', None)

        has_host_role = False
        if host_role_id and any(role.id == host_role_id for role in interaction.user.roles):
            has_host_role = True

        if not has_host_role:
            await interaction.response.send_message(
                "❌ Only hosts can cancel tournaments.",
                ephemeral=True
            )
            return

        success = await self.tournament_manager.cancel_tournament(interaction.channel, interaction.user)
        if success:
            embed = discord.Embed(
                title="❌ Tournament Cancelled",
                description="The active tournament has been cancelled by an administrator.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "❌ No active tournament to cancel or insufficient permissions",
                ephemeral=True
            )

    @discord.app_commands.command(name="test", description="Add fake players for testing")
    async def test(self, interaction: discord.Interaction):
        if not self._is_channel_allowed(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the designated tournament channel",
                ephemeral=True
            )
            return

        # Check if user has HOST_ROLE_ID to add test players
        import discordbot
        host_role_id = getattr(discordbot, 'HOST_ROLE_ID', None)

        has_host_role = False
        if host_role_id and any(role.id == host_role_id for role in interaction.user.roles):
            has_host_role = True

        if not has_host_role:
            await interaction.response.send_message(
                "❌ Only hosts can add test players.",
                ephemeral=True
            )
            return

        success = await self.tournament_manager.add_fake_players_to_tournament(interaction.channel)
        if success:
            await interaction.response.send_message("✅ Added 4 fake players (Alpha, Beta, Gamma, Delta) for testing!", ephemeral=True)
        else:
            # Check specific reasons for failure
            tournament = self.tournament_manager.load_tournament_by_channel(interaction.channel.id)
            if not tournament:
                await interaction.response.send_message(
                    "❌ No active tournament found",
                    ephemeral=True
                )
            elif tournament["status"] != "signup":
                await interaction.response.send_message(
                    "❌ Can only add test players during signup phase",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Fake players already added or tournament at capacity",
                    ephemeral=True
                )


class TournamentStatsManager:
    """Manages tournament statistics and historical data"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_player_stats(self, user_id: str, guild_id: str) -> Dict:
        """Get historical stats for a player using simplified tournament results"""
        try:
            # Query the simplified tournament_results collection
            tournaments = await self.db.tournament_results.find({
                "guild_id": guild_id,
                "players.user_id": user_id
            }).to_list(length=None)

            stats = {
                "tournaments_played": len(tournaments),
                "wins": 0,
                "finals_reached": 0,
                "semifinals_reached": 0
            }

            for tournament in tournaments:
                # Check if player won
                if tournament.get("winner_user_id") == user_id:
                    stats["wins"] += 1

                # Check if player reached finals (winner or runner-up)
                if user_id in [tournament.get("winner_user_id"), tournament.get("runner_up_user_id")]:
                    stats["finals_reached"] += 1

            return stats
        except Exception as e:
            logger.error(f"Error getting player stats: {e}")
            return {"tournaments_played": 0, "wins": 0, "finals_reached": 0, "semifinals_reached": 0}
    
    async def get_leaderboard(self, guild_id: str, limit: int = 10) -> List[Dict]:
        """Get tournament leaderboard for a guild using simplified results"""
        try:
            pipeline = [
                {
                    "$match": {
                        "guild_id": guild_id
                    }
                },
                {
                    "$unwind": "$players"
                },
                {
                    "$group": {
                        "_id": "$players.user_id",
                        "display_name": {"$last": "$players.display_name"},
                        "tournaments": {"$sum": 1},
                        "wins": {
                            "$sum": {
                                "$cond": [{"$eq": ["$winner_user_id", "$players.user_id"]}, 1, 0]
                            }
                        }
                    }
                },
                {
                    "$sort": {"wins": -1, "tournaments": -1}
                },
                {
                    "$limit": limit
                }
            ]

            results = await self.db.tournament_results.aggregate(pipeline).to_list(length=limit)
            return results
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []

class TournamentStatsCommands(commands.Cog):
    """Tournament statistics and management commands"""
    
    def __init__(self, bot: commands.Bot, stats_manager: TournamentStatsManager, allowed_channel_id: int = None):
        self.bot = bot
        self.stats_manager = stats_manager
        self.allowed_channel_id = allowed_channel_id
    
    def _is_channel_allowed(self, interaction: discord.Interaction) -> bool:
        """Check if command is being used in allowed channel"""
        if self.allowed_channel_id is None:
            # If no specific channel set, allow only in designated tournament channel
            return validate_tournament_channel(interaction.channel)
        return interaction.channel.id == self.allowed_channel_id
    
    @discord.app_commands.command(name="stats", description="Show your tournament statistics")
    async def stats(self, interaction: discord.Interaction):
        if not self._is_channel_allowed(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the designated tournament channel",
                ephemeral=True
            )
            return
            
        stats = await self.stats_manager.get_player_stats(
            str(interaction.user.id), str(interaction.guild.id)
        )
        
        embed = discord.Embed(
            title=f"🏆 Tournament Stats - {interaction.user.display_name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Tournaments Played", value=stats["tournaments_played"], inline=True)
        embed.add_field(name="Championships", value=stats["wins"], inline=True)
        embed.add_field(name="Finals Reached", value=stats["finals_reached"], inline=True)
        
        if stats["tournaments_played"] > 0:
            win_rate = (stats["wins"] / stats["tournaments_played"]) * 100
            embed.add_field(name="Win Rate", value=f"{win_rate:.1f}%", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @discord.app_commands.command(name="leaderboard", description="Show tournament leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        if not self._is_channel_allowed(interaction):
            await interaction.response.send_message(
                "❌ This command can only be used in the designated tournament channel",
                ephemeral=True
            )
            return
            
        leaderboard = await self.stats_manager.get_leaderboard(str(interaction.guild.id))
        
        if not leaderboard:
            await interaction.response.send_message("No completed tournaments found for this server.")
            return
        
        embed = discord.Embed(
            title="🏆 Tournament Leaderboard",
            color=discord.Color.gold()
        )
        
        description = ""
        medals = ["🥇", "🥈", "🥉"]
        
        for i, player in enumerate(leaderboard, 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            description += f"{medal} **{player['display_name']}** - {player['wins']} wins ({player['tournaments']} tournaments)\n"
        
        embed.description = description
        await interaction.response.send_message(embed=embed)


class SeedingVoteView(discord.ui.View):
    """View for seeding mode voting with buttons"""

    def __init__(self, tournament: Dict, embed: discord.Embed):
        super().__init__(timeout=30)
        self.tournament = tournament
        self.embed = embed
        self.message = None
        self.round_robin_votes = set()  # Set of user IDs who voted for Round Robin
        self.points_race_votes = set()  # Set of user IDs who voted for Points Race

        # Get tournament participant IDs for validation
        self.participant_ids = {player["user_id"] for player in tournament["players"]}

    def is_participant(self, user_id: str) -> bool:
        """Check if user is a tournament participant"""
        return user_id in self.participant_ids

    def update_embed_votes(self):
        """Update the embed with current vote counts and voter names"""
        # Round Robin voters
        rr_names = []
        for user_id in self.round_robin_votes:
            for player in self.tournament["players"]:
                if player["user_id"] == user_id:
                    name = player.get("display_name", f"Player {user_id}")
                    rr_names.append(name)
                    break

        # Points Race voters
        pr_names = []
        for user_id in self.points_race_votes:
            for player in self.tournament["players"]:
                if player["user_id"] == user_id:
                    name = player.get("display_name", f"Player {user_id}")
                    pr_names.append(name)
                    break

        # Update embed fields
        rr_value = "\n".join([f"• {name}" for name in rr_names]) if rr_names else "*No votes yet*"
        pr_value = "\n".join([f"• {name}" for name in pr_names]) if pr_names else "*No votes yet*"

        self.embed.set_field_at(0, name="🥊 Round Robin", value=rr_value, inline=True)
        self.embed.set_field_at(1, name="🏃 Points Race", value=pr_value, inline=True)

    @discord.ui.button(label="Round Robin", style=discord.ButtonStyle.success, emoji="🥊")
    async def round_robin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        # Check if user is a tournament participant
        if not self.is_participant(user_id):
            await interaction.response.send_message("❌ Only tournament participants can vote!", ephemeral=True)
            return

        # Remove from other vote if present, add to this vote
        self.points_race_votes.discard(user_id)
        self.round_robin_votes.add(user_id)

        # Update embed and respond
        self.update_embed_votes()
        await interaction.response.edit_message(embed=self.embed, view=self)

    @discord.ui.button(label="Points Race", style=discord.ButtonStyle.primary, emoji="🏃")
    async def points_race_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        # Check if user is a tournament participant
        if not self.is_participant(user_id):
            await interaction.response.send_message("❌ Only tournament participants can vote!", ephemeral=True)
            return

        # Remove from other vote if present, add to this vote
        self.round_robin_votes.discard(user_id)
        self.points_race_votes.add(user_id)

        # Update embed and respond
        self.update_embed_votes()
        await interaction.response.edit_message(embed=self.embed, view=self)

    def disable_all_buttons(self):
        """Disable all buttons after voting ends"""
        for item in self.children:
            item.disabled = True


async def setup_tournament_system(bot: commands.Bot, 
                                db: AsyncIOMotorDatabase,
                                fuzzy_match_func: Callable[[str, str, str, str], bool],
                                select_trivia_questions_func: Callable = None,
                                allowed_channel_id: int = None) -> TournamentManager:
    """
    Complete tournament system setup for the Discord bot.
    
    Args:
        bot: Discord bot instance
        db: MongoDB database instance  
        fuzzy_match_func: Existing fuzzy_match function from discordbot.py
        select_trivia_questions_func: Optional existing question selection function
        allowed_channel_id: Optional specific channel ID to restrict commands to
    
    Returns:
        TournamentManager instance for additional customization if needed
    """
    
    logger.info("Setting up tournament system...")
    
    try:
        # 1. Create and setup tournament manager with custom functions
        tournament_manager = TournamentManager(db, bot, select_trivia_questions_func, fuzzy_match_func)
        await tournament_manager.ensure_indexes()
        
        # 2. Add tournament slash commands cog
        tournament_cog = TournamentCog(bot, tournament_manager, allowed_channel_id)
        await bot.add_cog(tournament_cog)
        
        # 3. Setup statistics system
        stats_manager = TournamentStatsManager(db)
        stats_cog = TournamentStatsCommands(bot, stats_manager, allowed_channel_id)
        await bot.add_cog(stats_cog)
        
        # 4. Store references for later access
        bot._tournament_manager = tournament_manager
        bot._tournament_stats = stats_manager
        
        logger.info("Tournament system setup complete!")
        logger.info("Available commands:")
        logger.info("  • /start - Start a new tournament")
        logger.info("  • /status - Show current tournament status")
        logger.info("  • /cancel - Cancel active tournament (host only)")
        logger.info("  • /test - Add fake players for testing (host only)")
        logger.info("  • /stats - Show your tournament statistics")
        logger.info("  • /leaderboard - Show server leaderboard")
        logger.info("  • Type 'okra' during signup to join tournaments")
        
        if allowed_channel_id:
            logger.info(f"Tournament commands restricted to channel ID: {allowed_channel_id}")
        else:
            logger.info("Tournament commands restricted to designated tournament channel")
        
        return tournament_manager
        
    except Exception as e:
        logger.error(f"Failed to setup tournament system: {e}")
        raise

# Legacy function for backwards compatibility
async def setup_tournament(bot: commands.Bot, db: AsyncIOMotorDatabase):
    """Legacy setup function - use setup_tournament_system instead"""
    return await setup_tournament_system(bot, db, None, None)
