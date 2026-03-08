"""
config.py — Enums, constants, and configuration tables.
No logic here — just data.
"""

from enum import Enum
from typing import Dict, List, Tuple


class Alignment(Enum):
    GOOD = "Good"
    EVIL = "Evil"


class Role(Enum):
    MERLIN = "Merlin"
    LOYAL_SERVANT = "Loyal Servant"
    ASSASSIN = "Assassin"
    MINION_OF_MORDRED = "Minion of Mordred"


class Personality(Enum):
    HAWK = "Hawk"
    DOVE = "Dove"
    FOX = "Fox"
    BULL = "Bull"


class Phase(Enum):
    TEAM_PROPOSAL = "team_proposal"
    TEAM_VOTE = "team_vote"
    QUEST = "quest"
    ASSASSINATION = "assassination"
    GAME_OVER = "game_over"


# Alignment of each role
ROLE_ALIGNMENT: Dict[Role, Alignment] = {
    Role.MERLIN: Alignment.GOOD,
    Role.LOYAL_SERVANT: Alignment.GOOD,
    Role.ASSASSIN: Alignment.EVIL,
    Role.MINION_OF_MORDRED: Alignment.EVIL,
}

# Quest config per player count: list of (team_size, fails_needed) per quest
QUEST_CONFIG: Dict[int, List[Tuple[int, int]]] = {
    5: [(2,1), (3,1), (2,1), (3,1), (3,1)],
    6: [(2,1), (3,1), (4,1), (3,1), (4,1)],
    7: [(2,1), (3,1), (3,1), (4,2), (4,1)],
    8: [(3,1), (4,1), (4,1), (5,2), (5,1)],
    9: [(3,1), (4,1), (4,1), (5,2), (5,1)],
    10: [(3,1), (4,1), (4,1), (5,2), (5,1)],
}

# Roles assigned per player count: (good_roles, evil_roles)
ROLE_CONFIG: Dict[int, Tuple[List[Role], List[Role]]] = {
    5: ([Role.MERLIN, Role.LOYAL_SERVANT, Role.LOYAL_SERVANT],
        [Role.ASSASSIN, Role.MINION_OF_MORDRED]),
}

MAX_REJECTION_STREAK = 5

DEFAULT_AI_NAMES: List[str] = ["Aldric", "Mira", "Dorin", "Seska", "Calder",
                                 "Brennan", "Lysa", "Corvin", "Tilda", "Rhett"]

# Personality decision thresholds
# reject_threshold: suspicion level above which player is voted against
# update_rate: multiplier on suspicion delta when processing evidence
# stubbornness: resistance to updating (Bull), or openness (Fox)
PERSONALITY_CONFIG: Dict[Personality, Dict] = {
    Personality.HAWK: {"reject_threshold": 0.35, "update_rate": 1.2, "noise": 0.05},
    Personality.DOVE: {"reject_threshold": 0.65, "update_rate": 0.7, "noise": 0.08},
    Personality.FOX:  {"reject_threshold": 0.50, "update_rate": 1.5, "noise": 0.02},
    Personality.BULL: {"reject_threshold": 0.50, "update_rate": 0.4, "noise": 0.03},
}
