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
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Callable
from itertools import combinations
from collections import defaultdict

import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from bson import ObjectId
import pymongo

# Tournament Configuration Constants
ACTIVE_STATUSES = {"signup", "rr", "semis", "final"}

# Tournament Configuration - Easily configurable defaults
JOIN_WINDOW_SEC_DEFAULT = 30
RR_QUESTIONS_PER_MATCH_DEFAULT = 5
ANSWER_TIMEOUT_SEC_DEFAULT = 15
MIN_PLAYERS_DEFAULT = 4
MAX_PLAYERS_DEFAULT = 8
MODE_DEFAULT = "progressive"
POINTS_PER_QUESTION_DEFAULT = 10
MATCH_POINTS = {"win": 3, "tie": 1, "loss": 0}
KO_BEST_OF = 5

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

    async def ensure_indexes(self):
        """Ensure database indexes are created"""
        tournaments = self.db.tournaments
        matches = self.db.matches
        
        # Single active tournament per channel constraint
        await tournaments.create_index(
            [("channel_id", 1), ("status", 1)],
            unique=True,
            partialFilterExpression={"status": {"$in": list(ACTIVE_STATUSES)}},
            name="unique_active_tournament_per_channel"
        )
        
        # Performance indexes
        await tournaments.create_index([("created_at", -1)])
        await tournaments.create_index([("guild_id", 1)])
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
                "match_points": MATCH_POINTS.copy()
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

            # Check for existing active tournament (should be clean now)
            existing = self.load_tournament_by_channel(channel_id)
            if existing:
                raise ActiveTournamentError("A tournament is already active in this channel")

            # Create tournament
            config = {
                "join_window_sec": JOIN_WINDOW_SEC_DEFAULT,
                "rr_questions_per_match": RR_QUESTIONS_PER_MATCH_DEFAULT,
                "answer_timeout_sec": ANSWER_TIMEOUT_SEC_DEFAULT,
                "min_players": MIN_PLAYERS_DEFAULT,
                "max_players": MAX_PLAYERS_DEFAULT,
                "mode": MODE_DEFAULT
            }

            tournament_id = self.create_tournament(interaction.channel, config)
            
            # Send signup message
            embed = discord.Embed(
                title="🥒 Tournament Signup Open!",
                description=f"Type `okra` in the next **{JOIN_WINDOW_SEC_DEFAULT}** seconds to join the tournament!",
                color=discord.Color.green()
            )
            embed.add_field(name="\u200b\nSettings",
                           value=f"• Mode: {MODE_DEFAULT.title()}\n• Min Players: {MIN_PLAYERS_DEFAULT}\n• Max Players: {MAX_PLAYERS_DEFAULT}\n• Round Robin Questions: {RR_QUESTIONS_PER_MATCH_DEFAULT}\n• Answer Timeout: {ANSWER_TIMEOUT_SEC_DEFAULT}s")
            
            await interaction.response.send_message(embed=embed)
            
            # Start signup phase in background (don't await)
            task = asyncio.create_task(
                self.run_signup_phase(channel_id, JOIN_WINDOW_SEC_DEFAULT, MIN_PLAYERS_DEFAULT)
            )
            self.running_tasks[channel_id] = task

    async def run_signup_phase(self, channel_id: int, join_window_sec: int, min_players: int) -> None:
        """Handle the signup phase"""
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
        
        signup_end_time = asyncio.get_event_loop().time() + join_window_sec
        
        def check_signup(message):
            return (message.channel.id == channel.id and
                   not message.author.bot and
                   message.content.lower().strip() == "okra")

        try:
            while asyncio.get_event_loop().time() < signup_end_time:
                timeout = max(0.1, signup_end_time - asyncio.get_event_loop().time())
                try:
                    message = await self.bot.wait_for('message', timeout=timeout, check=check_signup)

                    # Check if user has OKRAN_ROLE_ID or BUMPER_KING_ROLE_ID
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

                    if not has_tournament_role:
                        # User doesn't have tournament role
                        await message.reply("Tournaments are for Okrans and Bumper Kings only")
                        await message.add_reaction("😔")
                        continue

                    # Add player if not already signed up
                    if not any(p["user_id"] == str(message.author.id) for p in players):
                        # Check if tournament is at capacity
                        if len(tournament["players"]) >= MAX_PLAYERS_DEFAULT:
                            await message.add_reaction("🙏")
                            await message.reply(f"Sorry, the tournament has reached its maximum capacity of {MAX_PLAYERS_DEFAULT} players.")
                            continue

                        player = {
                            "user_id": str(message.author.id),
                            "display_name": message.author.display_name,
                            "joined_at": datetime.now(timezone.utc),
                            "active": True,
                            "afk_strikes": 0
                        }
                        players.append(player)
                        # Also add to tournament memory immediately
                        tournament["players"].append(player)

                        # React to confirm signup with golden trophy
                        await message.add_reaction("🏆")
                        
                except asyncio.TimeoutError:
                    break
        
        except Exception as e:
            logger.error(f"Error in signup phase: {e}")
            return
        
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

        # Update tournament in memory and start round-robin
        tournament["players"] = all_players
        tournament["status"] = "rr"
        tournament["started_at"] = datetime.now(timezone.utc)
        
        embed = discord.Embed(
            title="🏆 Tournament Starting!",
            description=f"**{len(all_players)} players** signed up. Beginning round-robin phase...",
            color=discord.Color.blue()
        )
        player_list = "\n".join([f"• {p['display_name']}" for p in all_players])
        embed.add_field(name="\u200b\nPlayers", value=player_list)
        embed.add_field(name="", value="\u200b\n🚨 **ONE answer per question. Be careful!**", inline=False)
        await channel.send(embed=embed)

        # 5 second delay before starting matches
        await asyncio.sleep(5)

        await self.build_rr_schedule_and_start(channel_id, all_players)

    async def build_rr_schedule_and_start(self, channel_id: int, players: List[Dict]) -> None:
        """Build round-robin schedule and start matches"""
        # Get tournament from memory
        tournament = active_tournaments.get(channel_id)
        if not tournament:
            return

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
        print(f"DEBUG: Round-robin completed, moving to knockout phase for channel {channel_id}")
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
        print(f"DEBUG: Starting knockout phase with {len(standings)} players")
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
                value=f"First to {KO_BEST_OF} wins!",
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
            "semi", KO_BEST_OF, KO_BEST_OF
        )

        s2_match = self.create_match(
            tournament["id"], players_by_seed[2], players_by_seed[3],
            "semi", KO_BEST_OF, KO_BEST_OF
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
            tournament["id"], s1_winner, s2_winner, "final", KO_BEST_OF, KO_BEST_OF
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
            value=f"First to {KO_BEST_OF} wins!",
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

        # Calculate final standings
        rr_standings = self.compute_rr_standings(tournament)
        tournament["standings"] = rr_standings
        
        # Determine champion and runner-up
        champion = None
        runner_up = None
        
        # Look for final match in tournament matches
        final_matches = [m for m in tournament["matches"] if m["phase"] == "final"]
        if final_matches:
            final_match = final_matches[0]
            if final_match.get("winner_user_id"):
                # Find champion and runner-up from final
                for player in tournament["players"]:
                    if player["user_id"] == final_match["winner_user_id"]:
                        champion = player
                    elif player["user_id"] in [final_match["player_a"]["user_id"], final_match["player_b"]["user_id"]]:
                        if player["user_id"] != final_match["winner_user_id"]:
                            runner_up = player
        
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
        
        # Add RR standings
        if rr_standings:
            standings_text = ""
            for i, player in enumerate(rr_standings[:5], 1):
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
            okran_role_id = getattr(discordbot, 'OKRAN_ROLE_ID', None)
            bumper_king_role_id = getattr(discordbot, 'BUMPER_KING_ROLE_ID', None)

            if not participant_role_id:
                logger.error("Tournament Participant role ID not found in discordbot.py")
                return

            # Get the roles
            participant_role = channel.guild.get_role(participant_role_id)
            okran_role = channel.guild.get_role(okran_role_id) if okran_role_id else None
            bumper_king_role = channel.guild.get_role(bumper_king_role_id) if bumper_king_role_id else None

            if not participant_role:
                logger.error("Tournament Participant role not found in guild")
                return

            # Set channel permissions: only participants can send messages (preserve other permissions)
            existing_participant_perms = channel.overwrites_for(participant_role)
            existing_participant_perms.send_messages = True
            await channel.set_permissions(participant_role, overwrite=existing_participant_perms)

            # Disable Okran role messaging during questions (preserve other permissions)
            if okran_role:
                # Get existing permissions for this role
                existing_perms = channel.overwrites_for(okran_role)
                # Only modify send_messages, keep everything else
                existing_perms.send_messages = False
                await channel.set_permissions(okran_role, overwrite=existing_perms)

            # Disable Bumper King role messaging during questions (preserve other permissions)
            if bumper_king_role:
                # Get existing permissions for this role
                existing_perms = channel.overwrites_for(bumper_king_role)
                # Only modify send_messages, keep everything else
                existing_perms.send_messages = False
                await channel.set_permissions(bumper_king_role, overwrite=existing_perms)

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
            okran_role_id = getattr(discordbot, 'OKRAN_ROLE_ID', None)
            bumper_king_role_id = getattr(discordbot, 'BUMPER_KING_ROLE_ID', None)

            if participant_role_id:
                participant_role = channel.guild.get_role(participant_role_id)
                okran_role = channel.guild.get_role(okran_role_id) if okran_role_id else None
                bumper_king_role = channel.guild.get_role(bumper_king_role_id) if bumper_king_role_id else None

                if participant_role:
                    # Remove channel permission overrides for tournament participant role (preserve other permissions)
                    existing_participant_perms = channel.overwrites_for(participant_role)
                    existing_participant_perms.send_messages = None  # None = inherit from role/server defaults
                    await channel.set_permissions(participant_role, overwrite=existing_participant_perms)

                    # Re-enable Okran role messaging after questions (preserve other permissions)
                    if okran_role:
                        # Get existing permissions for this role
                        existing_perms = channel.overwrites_for(okran_role)
                        # Explicitly allow send_messages for Okran role, keep everything else
                        existing_perms.send_messages = True  # Explicitly allow messaging
                        await channel.set_permissions(okran_role, overwrite=existing_perms)

                    # Re-enable Bumper King role messaging after questions (preserve other permissions)
                    if bumper_king_role:
                        # Get existing permissions for this role
                        existing_perms = channel.overwrites_for(bumper_king_role)
                        # Explicitly allow send_messages for Bumper King role, keep everything else
                        existing_perms.send_messages = True  # Explicitly allow messaging
                        await channel.set_permissions(bumper_king_role, overwrite=existing_perms)

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
        
        is_ko = match["phase"] in ["semi", "final"]
        target_questions = match["questions_target"]
        
        while True:
            # Check if match should end
            if is_ko:
                # KO: first to KO_BEST_OF wins
                if score_a >= KO_BEST_OF or score_b >= KO_BEST_OF:
                    break
                # Continue if neither reached KO_BEST_OF after target questions
                if questions_asked >= target_questions and score_a < KO_BEST_OF and score_b < KO_BEST_OF:
                    # Sudden death - continue until someone wins a question
                    pass
            else:
                # RR: fixed number of questions
                if questions_asked >= target_questions:
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
            question_title = f"**Question {questions_asked}**: {category_text}"

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
                    # Fixed reveal duration of 5 seconds with 1 update per second
                    reveal_time = 5.0
                    update_interval = 1.0  # Update every 1 second
                    total_updates = 5  # Exactly 5 updates over 5 seconds
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

                    # Start answer monitoring immediately but with extended timeout
                    answer_task = asyncio.create_task(self.wait_for_answer(
                        channel, [player_a_id, player_b_id],
                        question, reveal_time + config["answer_timeout_sec"]
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
                        # Reveal completed, now wait for answer with 5 seconds
                        answer_task.cancel()
                        answer_result = await self.wait_for_answer(
                            channel, [player_a_id, player_b_id],
                            question, 5
                        )

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
            
            if answer_result:
                answered_by = answer_result["user_id"]
                correct = True
                awarded_points = config["points_per_question"]
                
                if answered_by == player_a_id:
                    score_a += 1 if is_ko else awarded_points
                else:
                    score_b += 1 if is_ko else awarded_points
                
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
            else:

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
        
        if is_ko:
            if score_a > score_b:
                winner_user_id = player_a_id
            else:
                winner_user_id = player_b_id
        else:
            # RR scoring with match points
            if score_a > score_b:
                winner_user_id = player_a_id
            elif score_b > score_a:
                winner_user_id = player_b_id
            else:
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
        """Wait for a correct answer from participants (supports simple fake player format)"""
        fake_players = ["alpha", "beta", "gamma", "delta"]
        
        def check_answer(message):
            # Check for simple fake player format: "alpha paris" or "beta london"
            words = message.content.strip().split()
            if (len(words) >= 2 and 
                words[0].lower() in fake_players):
                
                player_name = words[0].lower()
                # Check if this fake player is a participant
                for participant_id in participants:
                    if (participant_id.startswith('fake_') and 
                        player_name in participant_id.lower()):
                        return True
                return False
            
            # Regular player answer
            return (message.channel.id == channel.id and
                   str(message.author.id) in participants and
                   not message.author.bot)
        
        try:
            while True:
                message = await self.bot.wait_for('message', timeout=timeout_sec, check=check_answer)
                
                words = message.content.strip().split()
                
                # Handle fake player answer: "alpha answer" or "beta multiple word answer"
                # Only allow fake player answers when local_mode is enabled
                import discordbot
                if (len(words) >= 2 and words[0].lower() in fake_players and
                    getattr(discordbot, 'local_mode', False)):
                    try:
                        player_name = words[0].lower()
                        answer = ' '.join(words[1:])  # Everything after the player name
                        
                        # Find matching fake player ID
                        fake_user_id = None
                        for participant_id in participants:
                            if (participant_id.startswith('fake_') and 
                                player_name in participant_id.lower()):
                                fake_user_id = participant_id
                                break
                        
                        if fake_user_id:
                            evaluation_result = self.evaluate_answer(answer, question_data)

                            # Remove participant role after submitting answer
                            await self.remove_participant_role_after_answer(channel, fake_user_id)

                            # React to fake player answer (for testing purposes)
                            try:
                                if evaluation_result:
                                    await message.add_reaction("✅")
                                else:
                                    await message.add_reaction("❌")
                            except discord.HTTPException:
                                pass  # Ignore reaction failures

                            if evaluation_result:
                                # Show first correct answer instead of user's answer
                                correct_answer = question_data.get("answers", [""])[0]
                                #await channel.send(f"✅ {player_name.capitalize()} answered correctly: {correct_answer}")
                                return {
                                    "user_id": fake_user_id,
                                    "answer": answer
                                }
                    except Exception as e:
                        logger.error(f"Error processing fake player answer: {e}")
                        continue
                
                # Handle regular player answer (your own answer)
                else:
                    evaluation_result = self.evaluate_answer(message.content, question_data)

                    # Remove participant role after submitting answer
                    await self.remove_participant_role_after_answer(channel, str(message.author.id))

                    # React to player answer
                    try:
                        if evaluation_result:
                            await message.add_reaction("✅")
                        else:
                            await message.add_reaction("❌")
                    except discord.HTTPException:
                        pass  # Ignore reaction failures

                    if evaluation_result:
                        # Show first correct answer instead of user's answer
                        correct_answer = question_data.get("answers", [""])[0]
                        #await channel.send(f"✅ {message.author.display_name} answered correctly: {correct_answer}")
                        return {
                            "user_id": str(message.author.id),
                            "answer": message.content
                        }
        except asyncio.TimeoutError:
            return None
    
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
                "Tournaments are for Okrans and Bumper Kings only",
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
                "❌ A tournament is already active in this channel",
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
        logger.info("  • /cancel - Cancel active tournament (admin only)")
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
