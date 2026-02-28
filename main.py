# FuzzyFortnight01 — Battle-royale style game for crypto; lobbies, matches, loot and seasons. All roles and seeds fixed at init.

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any

# ---------------------------------------------------------------------------
# Constants — unique, not reused from other contracts
# ---------------------------------------------------------------------------

FF01_ARENA_SEED = "0xf91a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80"
FF01_MAX_PLAYERS_PER_LOBBY = 100
FF01_MIN_PLAYERS_TO_START = 4
FF01_MATCH_DURATION_SEC = 900
FF01_ENTRY_FEE_WEI = 10000000000000000
FF01_PRIZE_POOL_BP = 8500
FF01_BP_DENOM = 10000
FF01_MAX_SQUAD_SIZE = 4
FF01_SEASON_DURATION_DAYS = 14
FF01_XP_PER_KILL = 100
FF01_XP_PER_WIN = 500
FF01_DEPLOY_SALT = "b8e2f4a6c0d1e3f5a7b9c1d3e5f7a0b2c4d6e8f0a2b4c6d8e0f2a4b6c8d0e2"

# Addresses — unique, never used in any previous contract
FF01_GAME_MASTER = "0xFa91b2C3d4E5f6A7B8c9D0e1F2a3B4c5D6e7F8a9B0"
FF01_PRIZE_VAULT = "0x1B2c3D4e5F6a7B8C9d0E1f2A3b4C5d6E7f8A9b0C1"
FF01_SEASON_ORACLE = "0x2C3d4E5f6A7b8C9D0e1F2a3B4c5D6e7F8a9B0c1D2"
FF01_LOOT_CONTROLLER = "0x3D4e5F6a7B8c9D0e1F2a3B4c5D6e7F8a9B0c1D2e3"
FF01_REFEREE = "0x4E5f6A7b8C9d0E1f2A3b4C5d6E7f8A9b0C1d2E3f4"


class FF01Event(Enum):
    LOBBY_CREATED = "LobbyCreated"
    PLAYER_JOINED = "PlayerJoined"
    MATCH_STARTED = "MatchStarted"
    MATCH_ENDED = "MatchEnded"
    KILL_RECORDED = "KillRecorded"
    PRIZE_CLAIMED = "PrizeClaimed"
    SEASON_ROTATED = "SeasonRotated"


class FF01Phase(Enum):
    WAITING = 0
    COUNTDOWN = 1
    IN_PROGRESS = 2
    FINISHED = 3


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FF01LobbyFullError(Exception):
    def __init__(self, lobby_id: str) -> None:
        super().__init__(f"FF01: lobby full: {lobby_id}")


class FF01NotGameMasterError(Exception):
    def __init__(self) -> None:
        super().__init__("FF01: caller is not game master")


class FF01MatchNotFinishedError(Exception):
    def __init__(self, match_id: str) -> None:
        super().__init__(f"FF01: match not finished: {match_id}")


class FF01InsufficientEntryError(Exception):
    def __init__(self, sent: int, required: int) -> None:
        super().__init__(f"FF01: insufficient entry (sent={sent}, required={required})")


class FF01PlayerNotInLobbyError(Exception):
    def __init__(self, player: str, lobby_id: str) -> None:
        super().__init__(f"FF01: player {player} not in lobby {lobby_id}")


class FF01LobbyNotFoundError(Exception):
    def __init__(self, lobby_id: str) -> None:
        super().__init__(f"FF01: lobby not found: {lobby_id}")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PlayerProfile:
    address: str
    total_kills: int
    total_wins: int
    total_matches: int
    xp: int
    season_id: int
    joined_at: float


@dataclass
class LobbyState:
    lobby_id: str
    creator: str
    players: List[str]
    phase: FF01Phase
    match_id: Optional[str]
    created_at: float
    entry_fee_wei: int


@dataclass
class MatchResult:
    match_id: str
    winner: Optional[str]
    kills: Dict[str, int]
    started_at: float
    ended_at: float


# ---------------------------------------------------------------------------
# Core game engine
# ---------------------------------------------------------------------------

class FuzzyFortnight01:
    def __init__(self) -> None:
        self._game_master = FF01_GAME_MASTER
        self._prize_vault = FF01_PRIZE_VAULT
        self._season_oracle = FF01_SEASON_ORACLE
        self._loot_controller = FF01_LOOT_CONTROLLER
        self._referee = FF01_REFEREE
        self._lobbies: Dict[str, LobbyState] = {}
        self._matches: Dict[str, MatchResult] = {}
        self._profiles: Dict[str, PlayerProfile] = {}
        self._event_log: List[Tuple[FF01Event, Dict[str, Any]]] = []
        self._current_season_id = 1
        self._next_match_id = 1
        self._next_lobby_id = 1

    def _emit(self, event: FF01Event, data: Dict[str, Any]) -> None:
        self._event_log.append((event, data))

    def get_game_master(self) -> str:
        return self._game_master

    def get_prize_vault(self) -> str:
        return self._prize_vault

    def get_referee(self) -> str:
        return self._referee

    def create_lobby(self, creator: str, entry_fee_wei: int) -> str:
        lid = f"lobby-{self._next_lobby_id}"
        self._next_lobby_id += 1
        fee = entry_fee_wei if 0 < entry_fee_wei <= FF01_ENTRY_FEE_WEI * 2 else FF01_ENTRY_FEE_WEI
        self._lobbies[lid] = LobbyState(
            lobby_id=lid,
            creator=creator,
            players=[],
            phase=FF01Phase.WAITING,
            match_id=None,
            created_at=time.time(),
            entry_fee_wei=fee,
        )
        self._emit(FF01Event.LOBBY_CREATED, {"lobbyId": lid, "creator": creator, "entryFeeWei": fee})
        return lid

    def join_lobby(self, lobby_id: str, player: str, value_wei: int) -> None:
        if lobby_id not in self._lobbies:
            raise FF01LobbyNotFoundError(lobby_id)
        lobby = self._lobbies[lobby_id]
        if lobby.phase != FF01Phase.WAITING:
            raise FF01LobbyNotFoundError(lobby_id)
        if len(lobby.players) >= FF01_MAX_PLAYERS_PER_LOBBY:
            raise FF01LobbyFullError(lobby_id)
        if value_wei < lobby.entry_fee_wei:
            raise FF01InsufficientEntryError(value_wei, lobby.entry_fee_wei)
        key = player.strip().lower()
        if key not in [p.lower() for p in lobby.players]:
            lobby.players.append(player)
        self._emit(FF01Event.PLAYER_JOINED, {"lobbyId": lobby_id, "player": player})

    def start_match(self, lobby_id: str, caller: str) -> str:
        if lobby_id not in self._lobbies:
            raise FF01LobbyNotFoundError(lobby_id)
        lobby = self._lobbies[lobby_id]
        if caller.strip().lower() != lobby.creator.strip().lower():
            raise FF01NotGameMasterError()
        if len(lobby.players) < FF01_MIN_PLAYERS_TO_START:
            raise FF01LobbyFullError(lobby_id)
        mid = f"match-{self._next_match_id}"
        self._next_match_id += 1
        lobby.phase = FF01Phase.IN_PROGRESS
        lobby.match_id = mid
        self._matches[mid] = MatchResult(
            match_id=mid,
            winner=None,
            kills={p: 0 for p in lobby.players},
            started_at=time.time(),
            ended_at=0.0,
        )
        self._emit(FF01Event.MATCH_STARTED, {"matchId": mid, "lobbyId": lobby_id, "playerCount": len(lobby.players)})
        return mid

    def record_kill(self, match_id: str, killer: str, victim: str, caller: str) -> None:
        if match_id not in self._matches:
            return
        m = self._matches[match_id]
        if m.ended_at > 0:
            return
        k = killer.strip().lower()
        v = victim.strip().lower()
        keys = [x.lower() for x in m.kills.keys()]
        if k in keys:
            m.kills[killer] = m.kills.get(killer, 0) + 1
        self._emit(FF01Event.KILL_RECORDED, {"matchId": match_id, "killer": killer, "victim": victim})

    def end_match(self, match_id: str, winner: Optional[str], caller: str) -> None:
        if match_id not in self._matches:
            raise FF01LobbyNotFoundError(match_id)
        m = self._matches[match_id]
        m.winner = winner
        m.ended_at = time.time()
        for addr, k in m.kills.items():
            prof = self._profiles.get(addr.lower())
            if not prof:
                prof = PlayerProfile(addr, 0, 0, 0, 0, self._current_season_id, time.time())
                self._profiles[addr.lower()] = prof
            prof.total_kills += k
            prof.total_matches += 1
            prof.xp += k * FF01_XP_PER_KILL
        if winner:
            w = self._profiles.get(winner.strip().lower())
            if w:
                w.total_wins += 1
                w.xp += FF01_XP_PER_WIN
        self._emit(FF01Event.MATCH_ENDED, {"matchId": match_id, "winner": winner})

    def claim_prize(self, match_id: str, player: str) -> int:
        if match_id not in self._matches:
            raise FF01LobbyNotFoundError(match_id)
        m = self._matches[match_id]
        if m.ended_at <= 0:
            raise FF01MatchNotFinishedError(match_id)
        pool = len(m.kills) * FF01_ENTRY_FEE_WEI
        share = (pool * FF01_PRIZE_POOL_BP) // FF01_BP_DENOM
        if m.winner and player.strip().lower() == m.winner.strip().lower():
            return share
        return 0

    def get_player_profile(self, address: str) -> Optional[PlayerProfile]:
        return self._profiles.get(address.strip().lower())

    def get_lobby(self, lobby_id: str) -> Optional[LobbyState]:
        return self._lobbies.get(lobby_id)

    def get_match(self, match_id: str) -> Optional[MatchResult]:
        return self._matches.get(match_id)

    def get_event_log(self) -> List[Tuple[FF01Event, Dict[str, Any]]]:
        return list(self._event_log)

    def arena_fingerprint(self) -> str:
        return hashlib.sha256(
            f"{FF01_ARENA_SEED}-{self._current_season_id}-{len(self._matches)}-{FF01_DEPLOY_SALT}".encode()
        ).hexdigest()[:32]

    def get_season_oracle(self) -> str:
        return self._season_oracle

    def get_loot_controller(self) -> str:
        return self._loot_controller

    def get_current_season_id(self) -> int:
        return self._current_season_id

    def list_lobby_ids(self) -> List[str]:
        return list(self._lobbies.keys())

    def list_match_ids(self) -> List[str]:
        return list(self._matches.keys())

    def total_prize_pool_estimate(self, player_count: int) -> int:
        pool = player_count * FF01_ENTRY_FEE_WEI
        return (pool * FF01_PRIZE_POOL_BP) // FF01_BP_DENOM


# ---------------------------------------------------------------------------
# Loot and weapon tables (battle-royale flavour)
# ---------------------------------------------------------------------------

FF01_WEAPON_NAMES = [
    "ScatterBlaster", "SnipeRay", "PlasmaRifle", "RocketLauncher", "LaserPistol",
    "FrostCannon", "ChaosGrenade", "VoidBow", "FlameThrower", "TeslaCoil",
    "GravityHammer", "ShockBaton", "PoisonDart", "SilentKnife", "MegaShotgun",
]

FF01_LOOT_RARITY = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]

FF01_MAP_NAMES = [
    "DustyDesert", "FrostPeak", "ToxicSwamp", "NeonCity", "RuinIsland",
    "VolcanoBase", "SkyPlatform", "UndergroundBunker", "JungleTemple", "SpaceStation",
]

FF01_SKIN_IDS = [
    "default", "camo", "gold", "neon", "shadow", "fire", "ice", "robot", "phantom", "crypto_bro",
]

FF01_EMOTE_IDS = [
    "dance", "wave", "laugh", "salute", "cry", "heart", "flex", "sit", "sleep", "victory",
]


def ff01_weapon_for_seed(seed: str, index: int) -> str:
    h = hashlib.sha256(f"{seed}-weapon-{index}".encode()).hexdigest()
    idx = int(h[:8], 16) % len(FF01_WEAPON_NAMES)
    return FF01_WEAPON_NAMES[idx]


def ff01_loot_rarity_for_seed(seed: str, index: int) -> str:
    h = hashlib.sha256(f"{seed}-loot-{index}".encode()).hexdigest()
    idx = int(h[8:16], 16) % len(FF01_LOOT_RARITY)
    return FF01_LOOT_RARITY[idx]


def ff01_map_for_match(match_id: str) -> str:
    h = hashlib.sha256(f"{FF01_ARENA_SEED}-map-{match_id}".encode()).hexdigest()
    idx = int(h[16:24], 16) % len(FF01_MAP_NAMES)
    return FF01_MAP_NAMES[idx]


# ---------------------------------------------------------------------------
# XP tiers and rank names
# ---------------------------------------------------------------------------

FF01_XP_TIERS = [0, 500, 1500, 3500, 7500, 15000, 30000, 60000, 120000, 250000]

FF01_RANK_NAMES = [
    "Newbie", "Rookie", "Fighter", "Veteran", "Champion", "Elite", "Master", "Grandmaster", "Legend", "Apex",
]


def ff01_rank_for_xp(xp: int) -> str:
    for i in range(len(FF01_XP_TIERS) - 1, -1, -1):
        if xp >= FF01_XP_TIERS[i]:
            return FF01_RANK_NAMES[min(i, len(FF01_RANK_NAMES) - 1)]
    return FF01_RANK_NAMES[0]


def ff01_xp_to_next_rank(xp: int) -> int:
    for tier in FF01_XP_TIERS:
        if xp < tier:
            return tier - xp
    return 0


# ---------------------------------------------------------------------------
# Squad helper (max 4 per squad)
# ---------------------------------------------------------------------------
