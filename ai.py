"""
ai.py — AI decision-making, suspicion model, verbalization, and personalities.

AI players receive ONLY a PlayerView — never GameState directly.
All decisions are made from the player's knowledge state alone.
"""

import random
from typing import Dict, List, Optional, Tuple

from config import Alignment, Personality, Role, PERSONALITY_CONFIG
from player import PlayerView, QuestResult, RoundRecord


# ── Suspicion model ───────────────────────────────────────────────────────────

def initial_suspicion(view: PlayerView) -> Dict[int, float]:
    """
    Build starting suspicion scores for all other players.
    Evil players know who is evil; Merlin knows too.
    Loyal Servants start with uniform prior.
    """
    suspicion: Dict[int, float] = {}
    for i in range(view.player_count):
        if i == view.player_idx:
            continue
        if i in view.known_evil:
            suspicion[i] = 0.0   # known innocent (from our perspective as evil/Merlin)
        else:
            suspicion[i] = 0.40  # uniform prior for unknowns
    return suspicion


def update_suspicion(suspicion: Dict[int, float], view: PlayerView,
                     personality: Personality) -> Dict[int, float]:
    """
    Update suspicion scores based on quest and voting history.
    Returns updated dict (does not mutate in place).
    """
    cfg = PERSONALITY_CONFIG[personality]
    rate = cfg["update_rate"]
    noise = cfg["noise"]
    s = dict(suspicion)

    for quest in view.quest_history:
        if quest.result == "fail":
            # Someone on this team submitted a fail
            suspects = [i for i in quest.team if i != view.player_idx]
            if suspects:
                delta = (0.15 * rate) / len(suspects)
                for i in suspects:
                    if i in s:
                        s[i] = min(1.0, s[i] + delta + random.uniform(-noise, noise))
        else:
            # Quest succeeded — team members slightly less suspect
            for i in quest.team:
                if i in s:
                    s[i] = max(0.0, s[i] - 0.05 * rate + random.uniform(-noise, noise))

    for rnd in view.round_history:
        if not rnd.approved and rnd.result if hasattr(rnd, 'result') else False:
            pass  # not applicable here

        # Players who voted to approve a team that later failed
        if rnd.approved:
            # Find if this quest failed
            matching = [q for q in view.quest_history
                        if q.quest_num == rnd.quest_num]
            if matching and matching[0].result == "fail":
                for i, voted_approve in rnd.votes.items():
                    if voted_approve and i in s:
                        s[i] = min(1.0, s[i] + 0.05 * rate)

        # Players who proposed a team that failed
        if rnd.approved:
            matching = [q for q in view.quest_history
                        if q.quest_num == rnd.quest_num]
            if matching and matching[0].result == "fail":
                if rnd.leader in s:
                    s[rnd.leader] = min(1.0, s[rnd.leader] + 0.08 * rate)

    # Bull: resist big swings — cap individual update
    if personality == Personality.BULL:
        for i in s:
            if i in suspicion:
                s[i] = suspicion[i] + max(-0.10, min(0.10, s[i] - suspicion[i]))

    return s


def assassination_guess(view: PlayerView, suspicion: Dict[int, float]) -> int:
    """
    Assassin chooses who to accuse as Merlin.
    Strategy: among known-Good players, pick the one who seemed most informed.
    Heuristics:
      - Proposed clean teams (that succeeded) frequently
      - Voted against evil-heavy teams that later failed
      - Made accurate-seeming accusations
    We use suspicion scores inverted — least suspicious Good player is most likely Merlin.
    """
    # We know who evil players are; Merlin must be among the Good
    candidates = [i for i in range(view.player_count)
                  if i != view.player_idx and i not in view.known_evil]

    if not candidates:
        return random.randrange(view.player_count)

    # Build a "merlin score" — higher = more likely to be Merlin
    merlin_score: Dict[int, float] = {i: 0.0 for i in candidates}

    for rnd in view.round_history:
        if rnd.approved:
            matching = [q for q in view.quest_history
                        if q.quest_num == rnd.quest_num]
            if matching and matching[0].result == "success":
                # Leader proposed a successful team — slightly more Merlin-like
                if rnd.leader in merlin_score:
                    merlin_score[rnd.leader] += 0.15
            if matching and matching[0].result == "fail":
                # Leader proposed a failed team — less Merlin-like
                if rnd.leader in merlin_score:
                    merlin_score[rnd.leader] -= 0.10

        # Players who voted to reject a team that later failed: informed
        if not rnd.approved:
            matching = [q for q in view.quest_history
                        if q.quest_num == rnd.quest_num]
            # (no quest result for rejected rounds — skip)

    # Add some noise to make it imperfect
    for i in merlin_score:
        merlin_score[i] += random.uniform(-0.1, 0.1)

    return max(merlin_score, key=lambda i: merlin_score[i])


# ── Team proposal ─────────────────────────────────────────────────────────────

def propose_team(view: PlayerView, suspicion: Dict[int, float], size: int) -> List[int]:
    """
    AI proposes a quest team of the given size.
    Always includes self. Fills remainder based on role strategy.
    """
    me = view.player_idx

    if view.own_alignment == Alignment.EVIL:
        # Include self + as many evil allies as possible without being obvious
        evil_allies = [i for i in view.known_evil if i != me]
        # On small teams (size 2), include one evil ally if possible
        # On larger teams, try to include self + 1 evil ally + trusted Goods
        team = [me]
        if evil_allies and len(team) < size:
            team.append(random.choice(evil_allies))
        # Fill with least-suspicious players (cover)
        others = sorted(
            [i for i in range(view.player_count) if i not in team],
            key=lambda i: suspicion.get(i, 0.5)
        )
        team += others[:size - len(team)]
        return team[:size]

    elif view.own_role == Role.MERLIN:
        # Know who's evil; avoid them, but can't be too obvious
        # Occasionally tolerate one evil player to maintain cover
        good_players = [i for i in range(view.player_count)
                        if i not in view.known_evil]
        team = [me]
        trusted = [i for i in good_players if i != me]
        random.shuffle(trusted)
        # Very rarely slip in an evil player to avoid looking all-knowing
        if random.random() < 0.05 and len(view.known_evil) > 0:
            team.append(random.choice(list(view.known_evil)))
        team += trusted[:size - len(team)]
        return team[:size]

    else:
        # Loyal Servant: pick lowest-suspicion players
        team = [me]
        others = sorted(
            [i for i in range(view.player_count) if i != me],
            key=lambda i: suspicion.get(i, 0.5)
        )
        team += others[:size - len(team)]
        return team[:size]


# ── Team vote ─────────────────────────────────────────────────────────────────

def vote_on_team(view: PlayerView, suspicion: Dict[int, float],
                 team: List[int], personality: Personality) -> bool:
    """
    Decide whether to approve or reject the proposed team.
    Returns True = Approve, False = Reject.
    """
    cfg = PERSONALITY_CONFIG[personality]
    threshold = cfg["reject_threshold"]

    if view.own_alignment == Alignment.EVIL:
        # Approve if team contains at least one evil player
        evil_on_team = any(i in view.known_evil for i in team) or view.player_idx in team
        if evil_on_team:
            # Occasionally reject even good evil teams to avoid being predictable
            return random.random() > 0.08
        else:
            # Rarely approve a clean team (to avoid obvious pattern)
            return random.random() < 0.12

    elif view.own_role == Role.MERLIN:
        # Reject if any known evil on team; occasional tolerance for cover
        evil_on_team = any(i in view.known_evil for i in team)
        if evil_on_team:
            # Reject, but not always — Merlin must seem fallible
            return random.random() < 0.08
        return True

    else:
        # Loyal Servant: reject if any team member is too suspicious
        max_suspicion = max((suspicion.get(i, 0.4) for i in team), default=0.4)
        if max_suspicion > threshold:
            return False
        # Also consider rejection streak urgency
        if view.rejection_streak >= 3:
            return True  # too risky to reject further
        return True


# ── Quest vote ────────────────────────────────────────────────────────────────

def vote_on_quest(view: PlayerView, team: List[int], personality: Personality) -> bool:
    """
    Decide Success or Fail on a quest.
    Good players always vote Success (enforced by engine too).
    Evil players decide strategically.
    Returns True = Success, False = Fail.
    """
    if view.own_alignment == Alignment.GOOD:
        return True  # Good players must succeed

    # Evil: Fail when it won't be immediately obvious who did it
    evil_on_team = sum(1 for i in team if i in view.known_evil or i == view.player_idx)
    team_size = len(team)

    if evil_on_team == 1 and team_size >= 3:
        # Single evil on a team of 3+ — fail is ambiguous
        return False
    elif evil_on_team == 1 and team_size == 2:
        # Single evil on team of 2 — fail is very suspicious
        # Fail anyway if we're behind; maintain cover if we're ahead
        good_wins, evil_wins = view.quest_scores
        if evil_wins >= 2:
            return False  # go for the win
        return random.random() < 0.35  # risky fail
    elif evil_on_team >= 2:
        # Multiple evil — one fails, one succeeds to muddy waters
        return random.random() < 0.4

    return True  # shouldn't happen


# ── Verbalization ─────────────────────────────────────────────────────────────

def verbalize_proposal(view: PlayerView, team: List[int],
                       personality: Personality) -> Optional[str]:
    """Generate a short statement about the proposed team."""
    names = view.player_names
    team_names = [names[i] for i in team if i != view.player_idx]
    me = names[view.player_idx]

    if not random.random() < 0.85:  # 15% chance of silence
        return None

    if view.own_alignment == Alignment.EVIL:
        # Evil: justify self-serving picks convincingly
        templates = [
            f"I'm going with {' and '.join(team_names)}. I trust them based on what I've seen.",
            f"Simple choice for me — {' and '.join(team_names)} have been consistent.",
            f"I'd put myself with {' and '.join(team_names)}. Solid group.",
            f"{' and '.join(team_names)} — no hesitation from me.",
        ]
    elif view.own_role == Role.MERLIN:
        # Merlin: steer carefully without revealing knowledge
        templates = [
            f"I feel good about {' and '.join(team_names)}. Gut feeling at this point.",
            f"Going with {' and '.join(team_names)} — I think that's a safe group.",
            f"I'd like to see {' and '.join(team_names)} on this one.",
            f"{' and '.join(team_names)} — I have my reasons.",
        ]
    else:
        templates = [
            f"I'm proposing {' and '.join(team_names)}. Low suspicion, clean record.",
            f"Taking {' and '.join(team_names)} — I think we can trust them.",
            f"My pick: {' and '.join(team_names)}. Let's see what happens.",
            f"Going with {' and '.join(team_names)} on this one.",
        ]

    stmt = random.choice(templates)
    return _apply_personality_tone(stmt, personality)


def verbalize_team_vote(view: PlayerView, team: List[int], approve: bool,
                        personality: Personality) -> Optional[str]:
    """Generate a short statement about a team vote."""
    names = view.player_names
    leader_name = names[view.current_leader]
    suspects = [names[i] for i in team
                if i != view.player_idx and view.own_alignment == Alignment.GOOD
                and i not in view.known_evil]

    if not random.random() < 0.80:
        return None

    if approve:
        if view.own_alignment == Alignment.EVIL and not any(
                i in view.known_evil or i == view.player_idx for i in team):
            # Evil approving a clean team — reluctant cover
            templates = [
                "Fine. I'll approve, but I'm watching.",
                "Not my ideal team, but I won't hold things up.",
                "Approve. We need to keep moving.",
            ]
        else:
            templates = [
                f"Approve. {leader_name}'s team looks reasonable to me.",
                "Approve — no serious objections.",
                "I'll go with it. Approve.",
                "Looks fine. Approve.",
            ]
    else:
        if view.own_role == Role.MERLIN and any(i in view.known_evil for i in team):
            # Merlin rejecting a team with evil — must be vague
            templates = [
                "Something doesn't sit right with me. Reject.",
                "I'd like a different team. Reject.",
                "Not comfortable with this group. Reject.",
                "My instincts say no. Reject.",
            ]
        elif view.own_alignment == Alignment.EVIL:
            # Evil rejecting a clean team — needs justification
            templates = [
                "I don't love this team. We can do better. Reject.",
                "Reject. I want to see different faces on this one.",
                "Something feels off. Reject.",
            ]
        else:
            suspect_str = f"I'm not sure about {suspects[0]}" if suspects else "Something feels off"
            templates = [
                f"{suspect_str}. Reject.",
                f"Reject — {suspect_str.lower()}.",
                "Not the team I'd choose. Reject.",
                "Reject. Let's try again.",
            ]

    stmt = random.choice(templates)
    return _apply_personality_tone(stmt, personality)


def verbalize_quest_result(view: PlayerView, result: QuestResult,
                           personality: Personality) -> Optional[str]:
    """Generate a reaction to a quest result."""
    if not random.random() < 0.75:
        return None

    fail_count = result.fail_count
    team_size = len(result.team)
    team_names = [view.player_names[i] for i in result.team]

    if result.result == "success":
        templates = [
            "Good. That's what I expected.",
            "Quest succeeded. Trust was well placed.",
            "Exactly right.",
            "Clean result. Good.",
        ]
    else:
        if view.own_alignment == Alignment.EVIL and view.player_idx in result.team:
            # Evil — they know they failed it (or an ally did), must deflect
            templates = [
                f"One fail on a team of {team_size}. Someone here isn't who they say they are.",
                f"Interesting. {fail_count} fail card{'s' if fail_count > 1 else ''}. Not from me.",
                f"I submitted Success. Someone else is lying.",
                "We have a problem. And it isn't me.",
            ]
        elif view.own_role == Role.MERLIN and any(i in view.known_evil for i in result.team):
            # Merlin knows who did it — can't say so directly
            templates = [
                "I had a feeling about this team.",
                "Not surprised, honestly.",
                f"{fail_count} fail card{'s' if fail_count > 1 else ''} — we need to look carefully at who was on that mission.",
                "We should talk about this team.",
            ]
        else:
            templates = [
                f"{fail_count} fail card{'s' if fail_count > 1 else ''} on a team of {team_size}. Someone in {', '.join(team_names)} is lying.",
                "Disappointing. One of that team betrayed us.",
                f"Failed. {fail_count} traitor{'s' if fail_count > 1 else ''} among us.",
                f"We trusted the wrong person. One of {', '.join(team_names)}.",
            ]

    stmt = random.choice(templates)
    return _apply_personality_tone(stmt, personality)


def verbalize_assassination(view: PlayerView, target_idx: int,
                             personality: Personality) -> str:
    """Assassin announces their Merlin guess."""
    target_name = view.player_names[target_idx]
    templates = [
        f"I've made my choice. {target_name} — you are Merlin.",
        f"The game is over. {target_name} is Merlin.",
        f"I've watched carefully. {target_name} knew too much. My blade falls on {target_name}.",
        f"{target_name}. That's my guess. Merlin.",
    ]
    return random.choice(templates)


def _apply_personality_tone(stmt: str, personality: Personality) -> str:
    """Adjust statement tone to fit personality. Mostly intact — personality shows in word choice."""
    if personality == Personality.HAWK:
        # Occasionally add sharpness
        if random.random() < 0.3:
            stmt = stmt.rstrip(".") + " — and I mean it."
    elif personality == Personality.DOVE:
        if random.random() < 0.3:
            stmt = stmt.rstrip(".") + ", but I respect whatever we decide."
    elif personality == Personality.FOX:
        if random.random() < 0.3:
            stmt = stmt.rstrip(".") + " — the pattern supports it."
    elif personality == Personality.BULL:
        if random.random() < 0.3:
            stmt = stmt.rstrip(".") + " — I've said it before and I'll say it again."
    return stmt


# ── AI player entry points ────────────────────────────────────────────────────

class AIPlayer:
    """
    Stateful AI player. Holds its suspicion model across rounds.
    Receives only PlayerView at each decision point.
    """

    def __init__(self, player_idx: int, personality: Personality):
        self.player_idx = player_idx
        self.personality = personality
        self._suspicion: Optional[Dict[int, float]] = None

    def _get_suspicion(self, view: PlayerView) -> Dict[int, float]:
        if self._suspicion is None:
            self._suspicion = initial_suspicion(view)
        self._suspicion = update_suspicion(self._suspicion, view, self.personality)
        return self._suspicion

    def decide_team(self, view: PlayerView, size: int) -> Tuple[List[int], Optional[str]]:
        """Returns (team, optional_statement)."""
        s = self._get_suspicion(view)
        team = propose_team(view, s, size)
        stmt = verbalize_proposal(view, team, self.personality)
        return team, stmt

    def decide_team_vote(self, view: PlayerView, team: List[int]) -> Tuple[bool, Optional[str]]:
        """Returns (approve, optional_statement)."""
        s = self._get_suspicion(view)
        approve = vote_on_team(view, s, team, self.personality)
        stmt = verbalize_team_vote(view, team, approve, self.personality)
        return approve, stmt

    def decide_quest_vote(self, view: PlayerView, team: List[int]) -> bool:
        """Returns True = Success, False = Fail."""
        return vote_on_quest(view, team, self.personality)

    def react_to_quest(self, view: PlayerView, result: QuestResult) -> Optional[str]:
        """Returns optional reaction statement."""
        return verbalize_quest_result(view, result, self.personality)

    def decide_assassination(self, view: PlayerView) -> Tuple[int, str]:
        """Returns (target_idx, statement)."""
        s = self._get_suspicion(view)
        target = assassination_guess(view, s)
        stmt = verbalize_assassination(view, target, self.personality)
        return target, stmt
