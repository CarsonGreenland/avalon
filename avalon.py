#!/usr/bin/env python3
"""
avalon.py — Main entry point and game loop.
"""

import sys
from typing import Dict, List, Optional

from config import Alignment, Phase, Role, QUEST_CONFIG
from game import GameState, create_game
from player import Player, PlayerView, QuestResult
from ai import AIPlayer
import cli


def build_ai_players(players: List[Player]) -> Dict[int, AIPlayer]:
    """Create AIPlayer instances for all non-human players."""
    return {
        p.idx: AIPlayer(p.idx, p.personality)
        for p in players if not p.is_human
    }


def run_team_proposal(state: GameState, ai_players: Dict[int, AIPlayer],
                      human_idx: int):
    """Handle a team proposal phase."""
    leader_idx = state.current_leader
    leader = state.players[leader_idx]
    view = state.build_player_view(leader_idx)
    size = state.get_quest_team_size()

    cli.show_board(view, state.players)
    cli.clear_line()

    if leader.is_human:
        cli.header("YOUR TURN — Propose a Team")
        team = cli.prompt_team(view, state.players, size)
    else:
        ai = ai_players[leader_idx]
        team, stmt = ai.decide_team(view, size)
        team_names = [view.player_names[i] for i in team]
        cli.show_team_proposal(leader.name, team_names)
        if stmt:
            cli.ai_speaks(leader.name, stmt)
        # No press_enter — flow straight to team vote

    state.record_team_proposal(team)
    return team


def run_team_vote(state: GameState, ai_players: Dict[int, AIPlayer],
                  team: List[int], human_idx: int) -> bool:
    """Handle the team vote phase. Returns True if approved."""
    proposer_idx = state.current_leader  # still the proposer at this point

    cli.header(f"Team Vote — Quest {state.current_quest + 1}")
    team_names = [state.players[i].name for i in team]
    print(f"\n  Proposed team: {', '.join(team_names)}")

    votes: Dict[int, bool] = {}
    ai_statements = []

    for p in state.players:
        view = state.build_player_view(p.idx)
        if p.is_human:
            vote = cli.prompt_team_vote()
            votes[p.idx] = vote
        else:
            # Leader always approves their own proposal
            if p.idx == proposer_idx:
                votes[p.idx] = True
            else:
                ai = ai_players[p.idx]
                vote, stmt = ai.decide_team_vote(view, team)
                votes[p.idx] = vote
                if stmt:
                    ai_statements.append((p.name, stmt))

    # Show AI statements
    if ai_statements:
        print()
        for name, stmt in ai_statements:
            cli.ai_speaks(name, stmt)

    # Show vote results
    name_votes = {state.players[i].name: v for i, v in votes.items()}
    cli.show_votes(name_votes)
    # No press_enter — flow straight to quest or next proposal

    approved = state.record_team_votes(votes)

    if state.check_rejection_loss():
        cli.header("5 CONSECUTIVE REJECTIONS")
        print(f"\n  The kingdom falls to chaos. Evil wins by default.")
        cli.press_enter()
        return False

    return approved


def run_quest(state: GameState, ai_players: Dict[int, AIPlayer],
              team: List[int], human_idx: int) -> QuestResult:
    """Handle the quest voting phase."""
    cli.header(f"Quest {state.current_quest} in Progress")
    print(f"\n  Team: {', '.join(state.players[i].name for i in team)}")
    print(f"  {cli.DIM}Each team member secretly votes Success or Fail.{cli.RESET}")

    votes: Dict[int, bool] = {}

    for idx in team:
        p = state.players[idx]
        view = state.build_player_view(idx)
        if p.is_human:
            vote = cli.prompt_quest_vote(p.alignment == Alignment.EVIL)
        else:
            ai = ai_players[idx]
            vote = ai.decide_quest_vote(view, team)
        votes[idx] = vote

    result = state.record_quest_votes(votes)
    cli.show_quest_result(result, {p.idx: p.name for p in state.players})

    # AI reactions
    reactions = []
    for p in state.players:
        if not p.is_human:
            ai = ai_players[p.idx]
            view = state.build_player_view(p.idx)
            stmt = ai.react_to_quest(view, result)
            if stmt:
                reactions.append((p.name, stmt))

    if reactions:
        print()
        for name, stmt in reactions:
            cli.ai_speaks(name, stmt)

    # No press_enter — flow straight to next proposal
    return result


def run_assassination(state: GameState, ai_players: Dict[int, AIPlayer],
                      human_idx: int) -> bool:
    """Handle the assassination phase. Returns True if Assassin wins."""
    assassin_idx = state.get_assassin_idx()
    merlin_idx = state.get_merlin_idx()
    assassin = state.players[assassin_idx]
    merlin = state.players[merlin_idx]

    if assassin.is_human:
        cli.header("ASSASSINATION PHASE")
        view = state.build_player_view(assassin_idx)
        print(f"\n  Good has won three quests. As the Assassin, you have one chance.")
        print(f"  Name your target as Merlin.")
        target_idx = cli.prompt_assassination(view, state.players)
        stmt = f"I name {state.players[target_idx].name} as Merlin."
    else:
        ai = ai_players[assassin_idx]
        view = state.build_player_view(assassin_idx)
        target_idx, stmt = ai.decide_assassination(view)

    cli.show_assassination(assassin.name, state.players[target_idx].name, stmt)

    correct = state.record_assassination(target_idx)
    cli.show_assassination_result(correct, state.players[target_idx].name, merlin.name)
    cli.press_enter()
    return correct


def play_game():
    cli.banner()
    name = cli.get_player_name()
    cli.press_enter("Starting a new game... ")

    state = create_game(human_name=name, num_players=5)
    ai_players = build_ai_players(state.players)
    human_idx = next(p.idx for p in state.players if p.is_human)
    human = state.players[human_idx]

    # Reveal role to human
    human_view = state.build_player_view(human_idx)
    cli.show_role(human)
    known_evil_names = [state.players[i].name for i in human_view.known_evil]
    if known_evil_names:
        cli.show_evil_knowledge(human, known_evil_names)
    cli.press_enter("Memorise your role. ")

    # Main game loop
    while state.phase not in (Phase.GAME_OVER, Phase.ASSASSINATION):
        if state.phase == Phase.TEAM_PROPOSAL:
            team = run_team_proposal(state, ai_players, human_idx)

        elif state.phase == Phase.TEAM_VOTE:
            approved = run_team_vote(state, ai_players, team, human_idx)
            if state.phase == Phase.GAME_OVER:
                break

        elif state.phase == Phase.QUEST:
            run_quest(state, ai_players, team, human_idx)

        if state.phase == Phase.GAME_OVER:
            break

    # Assassination phase
    if state.phase == Phase.ASSASSINATION:
        run_assassination(state, ai_players, human_idx)

    # Game over
    cli.show_game_over(state.winner, state.players)


def main():
    try:
        while True:
            play_game()
            print("\n  Play again? [Y/N]")
            again = input("  > ").strip().lower()
            if again not in ("y", "yes"):
                print("\n  Thanks for playing.\n")
                break
    except KeyboardInterrupt:
        print("\n\n  Goodbye.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
