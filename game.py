"""
game.py — GameState engine. Pure logic, zero I/O.

Enforces information boundaries, validates moves, resolves votes,
and tracks all game state. The only place ground-truth alignment is held.
"""

import random
from typing import Dict, List, Optional, Tuple

from config import (Alignment, Phase, QUEST_CONFIG, ROLE_CONFIG,
                    ROLE_ALIGNMENT, MAX_REJECTION_STREAK, DEFAULT_AI_NAMES,
                    Personality, Role)
from player import Player, PlayerView, QuestResult, RoundRecord


class GameState:

    def __init__(self, players: List[Player], player_count: int = 5):
        assert player_count in QUEST_CONFIG, f"Unsupported player count: {player_count}"
        self.players = players
        self.player_count = player_count
        self.quest_config = QUEST_CONFIG[player_count]  # list of (size, fails_needed)

        self.quest_results: List[QuestResult] = []
        self.round_history: List[RoundRecord] = []
        self.current_leader: int = random.randrange(player_count)
        self.rejection_streak: int = 0
        self.phase: Phase = Phase.TEAM_PROPOSAL
        self.current_quest: int = 0         # 0-indexed
        self._current_round_num: int = 0    # rejection count within current quest
        self._pending_team: Optional[List[int]] = None
        self.winner: Optional[Alignment] = None

    # ── Accessors ────────────────────────────────────────────────────────────

    def get_quest_team_size(self) -> int:
        return self.quest_config[self.current_quest][0]

    def get_quest_fails_needed(self) -> int:
        return self.quest_config[self.current_quest][1]

    def get_quest_scores(self) -> Tuple[int, int]:
        good = sum(1 for r in self.quest_results if r.result == "success")
        evil = sum(1 for r in self.quest_results if r.result == "fail")
        return (good, evil)

    def get_evil_players(self) -> List[int]:
        return [p.idx for p in self.players if p.alignment == Alignment.EVIL]

    def get_merlin_idx(self) -> Optional[int]:
        for p in self.players:
            if p.role == Role.MERLIN:
                return p.idx
        return None

    def get_assassin_idx(self) -> Optional[int]:
        for p in self.players:
            if p.role == Role.ASSASSIN:
                return p.idx
        return None

    # ── PlayerView construction ───────────────────────────────────────────────

    def build_player_view(self, player_idx: int) -> PlayerView:
        """
        Construct the information view for one player.
        CRITICAL: This is the only place where information boundaries are enforced.
          - Evil players learn each other's identities
          - Merlin learns evil players' identities (one-way — evil don't know Merlin knows)
          - Loyal Servants learn nothing about alignment
        No other code path should access ground-truth alignment.
        """
        player = self.players[player_idx]
        evil_indices = frozenset(self.get_evil_players())

        if player.alignment == Alignment.EVIL or player.role == Role.MERLIN:
            known_evil = evil_indices
        else:
            known_evil = frozenset()

        good_wins, evil_wins = self.get_quest_scores()

        return PlayerView(
            player_idx=player_idx,
            own_role=player.role,
            own_alignment=player.alignment,
            known_evil=known_evil,
            quest_history=list(self.quest_results),
            round_history=list(self.round_history),
            current_leader=self.current_leader,
            rejection_streak=self.rejection_streak,
            quest_scores=(good_wins, evil_wins),
            player_names={i: p.name for i, p in enumerate(self.players)},
            player_count=self.player_count,
            current_quest=self.current_quest,
            phase=self.phase,
        )

    # ── Phase transitions ─────────────────────────────────────────────────────

    def record_team_proposal(self, team: List[int]) -> None:
        """Leader proposes a team. Validates size and uniqueness."""
        assert self.phase == Phase.TEAM_PROPOSAL, f"Wrong phase: {self.phase}"
        expected = self.get_quest_team_size()
        assert len(team) == expected, f"Team must have {expected} members, got {len(team)}"
        assert len(set(team)) == len(team), "Duplicate players in team"
        assert all(0 <= i < self.player_count for i in team), "Invalid player index"
        self._pending_team = list(team)
        self.phase = Phase.TEAM_VOTE

    def record_team_votes(self, votes: Dict[int, bool]) -> bool:
        """
        Record all team votes. Returns True if approved.
        Advances leader on rejection; resets streak on approval.
        """
        assert self.phase == Phase.TEAM_VOTE, f"Wrong phase: {self.phase}"
        assert len(votes) == self.player_count, "All players must vote"

        approve_count = sum(1 for v in votes.values() if v)
        approved = approve_count > self.player_count / 2

        record = RoundRecord(
            quest_num=self.current_quest,
            round_num=self._current_round_num,
            leader=self.current_leader,
            proposed_team=list(self._pending_team),
            votes=dict(votes),
            approved=approved,
        )
        self.round_history.append(record)

        if approved:
            self.rejection_streak = 0
            self.phase = Phase.QUEST
        else:
            self.rejection_streak += 1
            self._current_round_num += 1
            self._advance_leader()
            self.phase = Phase.TEAM_PROPOSAL
            self._pending_team = None

        return approved

    def record_quest_votes(self, votes: Dict[int, bool]) -> QuestResult:
        """
        Record quest votes from team members.
        Good players CANNOT submit Fail — enforced here.
        Returns the QuestResult.
        """
        assert self.phase == Phase.QUEST, f"Wrong phase: {self.phase}"
        assert set(votes.keys()) == set(self._pending_team), "Votes must come from team members"

        for idx, success in votes.items():
            if self.players[idx].alignment == Alignment.GOOD:
                assert success, f"Good player {self.players[idx].name} cannot submit Fail"

        fail_count = sum(1 for v in votes.values() if not v)
        result_str = "fail" if fail_count >= self.get_quest_fails_needed() else "success"

        quest_result = QuestResult(
            quest_num=self.current_quest,
            team=list(self._pending_team),
            result=result_str,
            fail_count=fail_count,
        )
        self.quest_results.append(quest_result)
        self.current_quest += 1
        self._current_round_num = 0
        self._advance_leader()
        self._pending_team = None

        good_wins, evil_wins = self.get_quest_scores()
        if evil_wins >= 3:
            self.phase = Phase.GAME_OVER
            self.winner = Alignment.EVIL
        elif good_wins >= 3:
            self.phase = Phase.ASSASSINATION  # evil gets one shot at Merlin
        else:
            self.phase = Phase.TEAM_PROPOSAL

        return quest_result

    def record_assassination(self, target_idx: int) -> bool:
        """
        Assassin names a player as Merlin.
        Returns True if Assassin was correct (evil wins).
        """
        assert self.phase == Phase.ASSASSINATION, f"Wrong phase: {self.phase}"
        merlin_idx = self.get_merlin_idx()
        correct = (target_idx == merlin_idx)
        self.winner = Alignment.EVIL if correct else Alignment.GOOD
        self.phase = Phase.GAME_OVER
        return correct

    def check_rejection_loss(self) -> bool:
        """Returns True if rejection streak has triggered an evil win."""
        if self.rejection_streak >= MAX_REJECTION_STREAK:
            self.winner = Alignment.EVIL
            self.phase = Phase.GAME_OVER
            return True
        return False

    # ── Internal ─────────────────────────────────────────────────────────────

    def _advance_leader(self) -> None:
        self.current_leader = (self.current_leader + 1) % self.player_count

    def get_pending_team(self) -> Optional[List[int]]:
        return self._pending_team


# ── Factory ───────────────────────────────────────────────────────────────────

def create_game(human_name: str, num_players: int = 5,
                human_personality: Optional[Personality] = None) -> GameState:
    """
    Create a new game with one human player and AI opponents.
    Assigns roles randomly; human is always Good.
    """
    assert num_players in ROLE_CONFIG, f"Unsupported player count: {num_players}"
    good_roles, evil_roles = ROLE_CONFIG[num_players]
    all_roles = good_roles + evil_roles

    # Human gets a random Good role
    good_roles_copy = list(good_roles)
    random.shuffle(good_roles_copy)
    human_role = good_roles_copy.pop()

    # Remaining roles for AI
    remaining_good = good_roles_copy
    remaining_evil = list(evil_roles)
    random.shuffle(remaining_evil)
    ai_roles = remaining_good + remaining_evil
    random.shuffle(ai_roles)

    ai_names = random.sample(DEFAULT_AI_NAMES, num_players - 1)
    personalities = list(Personality)

    players: List[Player] = []

    # Insert human at a random position
    human_idx = random.randrange(num_players)
    ai_cursor = 0

    for i in range(num_players):
        if i == human_idx:
            role = human_role
            p = Personality(random.choice(personalities)) if human_personality is None else human_personality
            players.append(Player(
                idx=i,
                name=human_name,
                role=role,
                alignment=ROLE_ALIGNMENT[role],
                personality=p,
                is_human=True,
            ))
        else:
            role = ai_roles[ai_cursor]
            ai_cursor += 1
            p = random.choice(personalities)
            players.append(Player(
                idx=i,
                name=ai_names[i if i < human_idx else i - 1],
                role=role,
                alignment=ROLE_ALIGNMENT[role],
                personality=p,
                is_human=False,
            ))

    return GameState(players, num_players)
