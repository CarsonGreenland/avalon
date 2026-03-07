"""
cli.py — All terminal I/O. No game logic here.
"""

import time
from typing import Dict, List, Optional

from config import Alignment, Phase, Role
from player import Player, PlayerView, QuestResult


GOOD_COLOR = "\033[94m"    # blue
EVIL_COLOR = "\033[91m"    # red
NEUTRAL_COLOR = "\033[93m" # yellow
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def clear_line():
    print()


def header(text: str):
    width = 60
    print(f"\n{BOLD}{'─' * width}{RESET}")
    print(f"{BOLD}  {text}{RESET}")
    print(f"{BOLD}{'─' * width}{RESET}")


def banner():
    print(f"""
{BOLD}╔══════════════════════════════════════════════╗
║          THE RESISTANCE: AVALON              ║
╚══════════════════════════════════════════════╝{RESET}
""")


def show_role(player: Player):
    """Tell the human their role at game start."""
    alignment_str = f"{GOOD_COLOR}GOOD{RESET}" if player.alignment == Alignment.GOOD else f"{EVIL_COLOR}EVIL{RESET}"
    print(f"\n{BOLD}Your role:{RESET} {BOLD}{player.role.value}{RESET} ({alignment_str})")
    if player.role == Role.MERLIN:
        print(f"  {DIM}You know who the evil players are. Guide Good without revealing yourself.{RESET}")
    elif player.role == Role.LOYAL_SERVANT:
        print(f"  {DIM}You have no special knowledge. Use your wits.{RESET}")
    elif player.role == Role.ASSASSIN:
        print(f"  {DIM}You know your evil ally. If Good wins 3 quests, you get one shot at Merlin.{RESET}")
    elif player.role == Role.MINION_OF_MORDRED:
        print(f"  {DIM}You know your evil ally. Sabotage quests and stay hidden.{RESET}")


def show_evil_knowledge(player: Player, known_evil: List[str]):
    """Tell Merlin or evil players who they know."""
    if player.role == Role.MERLIN:
        print(f"  {DIM}Evil players: {RESET}{EVIL_COLOR}{', '.join(known_evil)}{RESET}")
    elif player.alignment == Alignment.EVIL:
        allies = [n for n in known_evil if n != player.name]
        if allies:
            print(f"  {DIM}Your evil ally: {RESET}{EVIL_COLOR}{', '.join(allies)}{RESET}")


def show_board(view: PlayerView, players: List[Player]):
    """Display the current game state."""
    good_wins, evil_wins = view.quest_scores
    quest_display = []
    for i, result in enumerate(view.quest_history):
        if result.result == "success":
            quest_display.append(f"{GOOD_COLOR}✓{RESET}")
        else:
            quest_display.append(f"{EVIL_COLOR}✗{RESET}")
    pending = ["○"] * (5 - len(quest_display))
    quests = "  ".join(quest_display + pending)

    streak_warn = ""
    if view.rejection_streak >= 3:
        streak_warn = f"  {NEUTRAL_COLOR}⚠ {view.rejection_streak} rejections{RESET}"
    if view.rejection_streak >= 4:
        streak_warn = f"  {EVIL_COLOR}⚠⚠ ONE MORE REJECTION = EVIL WINS{RESET}"

    print(f"\n  Quests:  {quests}   [{GOOD_COLOR}{good_wins}{RESET} - {EVIL_COLOR}{evil_wins}{RESET}]{streak_warn}")
    print(f"  Leader:  {BOLD}{view.player_names[view.current_leader]}{RESET}")
    print(f"  Quest {view.current_quest + 1}: team of {_quest_size(view)}")


def _quest_size(view: PlayerView) -> int:
    from config import QUEST_CONFIG
    return QUEST_CONFIG[view.player_count][view.current_quest][0]


def show_players(players: List[Player], human_idx: int):
    """List all players with indices."""
    print(f"\n  {BOLD}Players:{RESET}")
    for p in players:
        marker = " (you)" if p.is_human else ""
        print(f"    {p.idx + 1}. {p.name}{DIM}{marker}{RESET}")


def ai_speaks(name: str, statement: str):
    """Print an AI player's verbalized reasoning."""
    print(f"  {DIM}{name}:{RESET} \"{statement}\"")
    time.sleep(0.3)


def show_team_proposal(leader_name: str, team_names: List[str]):
    print(f"\n  {BOLD}{leader_name}{RESET} proposes: {BOLD}{', '.join(team_names)}{RESET}")


def show_votes(votes: Dict[str, bool]):
    """Display the team vote results."""
    print(f"\n  {BOLD}Votes:{RESET}")
    approvals = [n for n, v in votes.items() if v]
    rejections = [n for n, v in votes.items() if not v]
    approve_count = len(approvals)
    reject_count = len(rejections)
    print(f"    {GOOD_COLOR}Approve ({approve_count}):{RESET} {', '.join(approvals) or '—'}")
    print(f"    {EVIL_COLOR}Reject  ({reject_count}):{RESET} {', '.join(rejections) or '—'}")
    total = approve_count + reject_count
    if approve_count > total / 2:
        print(f"  → {GOOD_COLOR}Team approved.{RESET}")
    else:
        print(f"  → {EVIL_COLOR}Team rejected.{RESET}")


def show_quest_result(result: QuestResult, player_names: Dict[int, str]):
    """Reveal quest outcome with dramatic pause."""
    print(f"\n  The team ventures forth", end="", flush=True)
    for _ in range(3):
        time.sleep(0.5)
        print(".", end="", flush=True)
    time.sleep(0.8)
    print()

    if result.result == "success":
        print(f"\n  {GOOD_COLOR}{BOLD}✓ Quest Succeeded!{RESET}")
    else:
        card_s = "card" if result.fail_count == 1 else "cards"
        print(f"\n  {EVIL_COLOR}{BOLD}✗ Quest Failed!{RESET}  ({result.fail_count} fail {card_s})")


def prompt_team(view: PlayerView, players: List[Player], size: int) -> List[int]:
    """Prompt human leader to choose a team."""
    show_players(players, view.player_idx)
    print(f"\n  Choose {size} players for the quest (enter numbers separated by spaces):")
    while True:
        try:
            raw = input("  > ").strip()
            chosen = [int(x) - 1 for x in raw.split()]
            if len(chosen) != size:
                print(f"  Need exactly {size} players.")
                continue
            if len(set(chosen)) != size:
                print("  No duplicates.")
                continue
            if not all(0 <= i < view.player_count for i in chosen):
                print(f"  Numbers must be between 1 and {view.player_count}.")
                continue
            return chosen
        except ValueError:
            print("  Enter numbers only.")


def prompt_team_vote() -> bool:
    """Prompt human for approve/reject."""
    print("\n  Your vote: [A]pprove or [R]eject?")
    while True:
        raw = input("  > ").strip().lower()
        if raw in ("a", "approve", "yes", "y"):
            return True
        if raw in ("r", "reject", "no", "n"):
            return False
        print("  Enter A or R.")


def prompt_quest_vote(is_evil: bool) -> bool:
    """Prompt human quest vote. Good players can only succeed."""
    if not is_evil:
        input("  [Quest] You submit: Success (press Enter)")
        return True
    print("\n  Your quest vote: [S]uccess or [F]ail?")
    while True:
        raw = input("  > ").strip().lower()
        if raw in ("s", "success"):
            return True
        if raw in ("f", "fail"):
            return False
        print("  Enter S or F.")


def prompt_assassination(view: PlayerView, players: List[Player]) -> int:
    """Prompt human (if Assassin) to name Merlin. Should not normally occur since Assassin is AI."""
    show_players(players, view.player_idx)
    print("\n  Name your target as Merlin (enter number):")
    while True:
        try:
            raw = int(input("  > ").strip()) - 1
            if 0 <= raw < view.player_count and raw != view.player_idx:
                return raw
            print("  Invalid choice.")
        except ValueError:
            print("  Enter a number.")


def show_assassination(assassin_name: str, target_name: str, statement: str):
    header("ASSASSINATION PHASE")
    print(f"\n  {DIM}Good has won three quests. But the game is not over.{RESET}")
    print(f"\n  {BOLD}{assassin_name}{RESET} rises.")
    time.sleep(1.0)
    print(f"\n  {assassin_name}: \"{statement}\"")
    time.sleep(1.5)


def show_assassination_result(correct: bool, target_name: str, merlin_name: str):
    if correct:
        print(f"\n  {EVIL_COLOR}{BOLD}The blade finds its mark.{RESET}")
        print(f"  {target_name} was indeed {BOLD}Merlin{RESET}.")
        print(f"\n  {EVIL_COLOR}{BOLD}EVIL WINS.{RESET}")
    else:
        print(f"\n  {GOOD_COLOR}The Assassin hesitates... and misses.{RESET}")
        print(f"  {target_name} was not Merlin. {DIM}({merlin_name} was Merlin.){RESET}")
        print(f"\n  {GOOD_COLOR}{BOLD}GOOD WINS.{RESET}")


def show_game_over(winner: Alignment, players: List[Player], merlin_name: Optional[str] = None):
    header("GAME OVER")
    if winner == Alignment.GOOD:
        print(f"\n  {GOOD_COLOR}{BOLD}The forces of Good have prevailed!{RESET}")
    else:
        print(f"\n  {EVIL_COLOR}{BOLD}Evil corrupts the realm.{RESET}")
    print(f"\n  {BOLD}Roles revealed:{RESET}")
    for p in players:
        color = GOOD_COLOR if p.alignment == Alignment.GOOD else EVIL_COLOR
        print(f"    {color}{p.name:<12}{RESET}  {p.role.value}")
    print()


def get_player_name() -> str:
    print("\n  Enter your name:")
    name = input("  > ").strip()
    return name or "You"


def press_enter(msg: str = ""):
    input(f"\n  {msg}[Press Enter to continue]")
