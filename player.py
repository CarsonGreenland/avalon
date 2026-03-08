"""
player.py — Player, PlayerView, and history data classes.

PlayerView is the ONLY information passed to AI decision-making.
Information boundaries are enforced structurally in GameState.build_player_view().
"""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from config import Alignment, Personality, Phase, Role


@dataclass
class QuestResult:
    quest_num: int          # 0-indexed
    team: List[int]         # player indices on the quest
    result: str             # "success" or "fail"
    fail_count: int         # number of fail cards submitted (not who)


@dataclass
class RoundRecord:
    quest_num: int
    round_num: int          # 0 = first attempt for this quest; increments on rejection
    leader: int             # player index of the proposing leader
    proposed_team: List[int]
    votes: Dict[int, bool]  # player_idx -> True (approve) / False (reject)
    approved: bool


@dataclass
class Player:
    idx: int
    name: str
    role: Role
    alignment: Alignment    # derived from role; stored for convenience
    personality: Personality
    is_human: bool


@dataclass
class PlayerView:
    """
    The information available to one player at any decision point.
    Constructed by GameState.build_player_view().
    Information boundaries are enforced structurally — not by convention.

    known_evil is populated for:
      - Evil players: indices of all evil players (they know each other)
      - Merlin: indices of all evil players (he sees them; one-way)
      - Loyal Servant: empty frozenset
    """
    player_idx: int
    own_role: Role
    own_alignment: Alignment
    known_evil: FrozenSet[int]      # see docstring above
    quest_history: List[QuestResult]
    round_history: List[RoundRecord]
    current_leader: int
    rejection_streak: int
    quest_scores: Tuple[int, int]   # (good_wins, evil_wins)
    player_names: Dict[int, str]    # idx -> name (public)
    player_count: int
    current_quest: int              # 0-indexed
    phase: Phase
