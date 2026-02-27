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

