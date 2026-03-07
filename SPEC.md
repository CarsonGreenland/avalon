# Avalon — Design Spec v1.0

## Overview

CLI implementation of *The Resistance: Avalon*, core game only. 1 human vs 4 AI opponents. 5-player configuration. Written in Python 3, no external dependencies beyond standard library.

---

## Game Rules (5-Player Core)

### Setup
- 3 Good players (Loyal Servants of Arthur), 2 Evil players (Minions of Mordred)
- Evil players know each other. Good players know nothing about alignment.
- Roles are assigned randomly. Human player is always Good (consider making this a future option).
- Leader starts randomly.

### Quest Structure (5-player)

| Quest | Team Size | Fails to Fail Quest |
|-------|-----------|---------------------|
| 1     | 2         | 1                   |
| 2     | 3         | 1                   |
| 3     | 2         | 1                   |
| 4     | 3         | 1                   |
| 5     | 3         | 1                   |

### Round Flow

Each round:
1. **Leader proposes a team** of the required size
2. **Team vote** — all players simultaneously vote Approve/Reject (public)
   - Majority approves → proceed to quest
   - Majority rejects → leadership passes clockwise; repeat
   - 5 consecutive rejections → Evil wins immediately
3. **Quest** — each team member secretly submits Success or Fail
   - Good players may only submit Success
   - Evil players may submit Success or Fail (strategic choice)
   - Any Fail card → Quest fails
   - All Success → Quest succeeds
4. **Result announced** — number of Fail cards revealed (not who submitted them)
5. Leadership passes clockwise

### Victory
- **Good wins** if 3 quests succeed
- **Evil wins** if 3 quests fail, or if 5 consecutive team proposals are rejected

*Note: The Merlin assassination phase (Evil identifies and kills Merlin after Good wins 3 quests) is a special roles mechanic — not present in the core game. Add when Merlin/Assassin roles are implemented.*

---

## Information Model

Each player has a distinct **knowledge state**:

```
PlayerView:
  - own_alignment: Good | Evil
  - known_evil: set of player indices (Evil players know each other; Good know nobody)
  - quest_history: list of (team, result, fail_count) — public
  - vote_history: list of (round, player, approve/reject) — public
  - team_history: list of (round, leader, proposed_team) — public
  - current_leader: player index
  - rejection_streak: int (0–4)
  - quest_scores: (good_wins, evil_wins)
```

**Critical design principle:** The game engine holds ground truth. Each AI player is given only its own PlayerView when making decisions. No player ever receives information they shouldn't have. This must be enforced structurally, not by convention.

---

## AI Behavior

### Shared AI Framework

All AI players maintain:
- **Suspicion model** — a float per other player representing estimated probability they are evil (initialized to 0.4 for everyone, updated from evidence)
- **Trust events** — events that update suspicion: voting patterns, quest failures, team proposals

Evidence that increases suspicion:
- Proposed or approved a team that failed a quest
- Consistently rejected teams that succeeded
- Unusual voting patterns (always approves, always rejects)
- Proposed teams skewing toward the same players repeatedly

Evidence that decreases suspicion:
- Proposed a team that succeeded
- Voted against a team that later failed
- Voted for a team that later succeeded

### Decision Points

**1. Team Proposal (Leader)**
- Build a team that maximizes expected quest success
- Good: pick players with lowest suspicion scores
- Evil: pick self + one evil ally if possible, disguise by including trusted Goods; or sacrifice one evil if strategically necessary

**2. Team Vote**
- Good: approve if suspicion of all team members is below threshold; reject if any member highly suspected
- Evil: approve teams containing at least one evil player; reject otherwise (but occasionally approve bad teams to avoid being read as predictable)

**3. Quest Vote (on team)**
- Good: always Success
- Evil: strategic — Fail if it won't be obvious (e.g., team of 3 with 1 evil → 1 fail is ambiguous); consider Success if maintaining cover matters more

### Personality Types

Personality shapes **thresholds and tendencies**, not alignment. Same personality system applies to all players regardless of good/evil — it affects *how* they play their role.

**The Hawk**
- Low suspicion threshold — quick to reject teams, quick to accuse
- Aggressive team vetoes; strong opinions on who to include/exclude
- As evil: risky, may draw attention; compensates by being loudly accusatory toward Good players
- Tendency: high variance, often right but can disrupt good runs

**The Dove**
- High suspicion threshold — gives people the benefit of the doubt
- Approves most teams, avoids confrontation
- As evil: excellent cover, blends in easily, rarely suspected
- Tendency: low variance, safe but sometimes naive

**The Fox**
- Adaptive suspicion — starts neutral, updates aggressively from evidence
- Makes voting decisions based on computed patterns, not instinct
- As evil: plays the long game, maintains cover, fails quests only when strategically clear
- Tendency: most rational, hardest to read

**The Bull**
- Stubborn — once suspicion is formed, slow to update
- Commits to a read on players and sticks with it
- As evil: consistent cover story, hard to flip once trusted
- Tendency: stable but can get stuck on wrong reads

---

## Game State & Engine

```
GameState:
  players: list[Player]
  quest_results: list[QuestResult]
  round_history: list[Round]
  current_leader: int
  rejection_streak: int
  phase: Setup | TeamProposal | TeamVote | Quest | GameOver
```

```
Player:
  name: str
  alignment: Good | Evil
  personality: Hawk | Dove | Fox | Bull
  is_human: bool
  suspicion_model: dict[int, float]
```

### Engine Responsibilities
- Enforce information boundaries (PlayerView construction)
- Validate moves (e.g., Good player can't submit Fail)
- Resolve votes (majority calculation, rejection streaks)
- Announce results with appropriate information (fail count but not who)

---

## CLI Interface

### Display
- Clear board state each round: quest progress, current leader, rejection streak
- Show team vote results (who voted what — this is public)
- Show quest result (pass/fail + number of fail cards)
- Suspense: brief pause before revealing quest result

### Human Interaction
- Team proposal: choose from numbered player list
- Team vote: Approve / Reject
- Quest vote: Success only (can't fail as Good — enforce this)

### Output Style
- Similar tone to Coup — terse, atmospheric
- AI players have names; show their votes and behaviors
- After game: brief summary of who was evil, key moments

---

## Code Structure

```
avalon/
  avalon.py          # Main entry point, game loop
  game.py            # GameState, engine, rules enforcement
  player.py          # Player class, PlayerView construction
  ai.py              # AI decision-making, suspicion model, personalities
  cli.py             # All terminal I/O, display formatting
  config.py          # Constants: quest sizes, player counts, etc.
```

Modularity notes:
- `game.py` has no I/O — pure logic
- `ai.py` receives only PlayerView — never GameState directly
- Adding special roles later: extend PlayerView with role-specific knowledge fields; add role behaviors in `ai.py`
- Adding players: `config.py` holds quest size tables per player count

---

## Future Expansion Hooks

- Special roles (Merlin, Percival, Mordred, Morgana, Assassin, Oberon) — architecture supports via PlayerView extensions
- Variable player count (5–10) — config table already planned
- Multi-round match mode (like Coup)
- Personality evolution / learning across matches
- Human can play Evil

---

## AI Verbalization

AI players verbalize their reasoning at each decision point. This is core to the experience — it makes the social deduction feel alive and gives the human meaningful signals to read (and be deceived by).

### When AI speaks
- **Team proposal:** Leader explains their picks ("I'm going with Aldric and myself — I trust Aldric's voting record so far")
- **Team vote:** Each AI briefly states their position ("Rejecting — I don't like seeing Mira on this team twice in a row")
- **After quest result:** Reactions to outcome, sometimes accusatory ("One fail on a team of two. I think we know who.")

### Verbalization rules
- Statements must be **consistent with the player's knowledge state** — Good players can't reveal certainty about evil
- Evil players **lie convincingly** — their verbalizations should deflect, accuse Good players, and justify self-serving team proposals
- Personality shapes tone:
  - Hawk: blunt, accusatory ("I don't trust Mira. I haven't trusted her since round one.")
  - Dove: gentle, diplomatic ("I'd feel better with a slightly different team, but I'll support whatever we decide")
  - Fox: analytical, pattern-citing ("The voting record shows a correlation I find hard to ignore")
  - Bull: stubborn, repetitive ("I've said it before — Aldric is the problem here")
- Statements should be **short** (1–2 sentences), not monologues
- Occasional silence is fine — not every player speaks every round

### Implementation
- Each personality has a pool of statement templates per situation, filled with player names and game context
- Evil players draw from a separate pool of misdirection templates when it serves them
- Randomize enough to avoid feeling repetitive across rounds

## Resolved Design Questions

1. ✅ AI verbalizes reasoning — see section above
2. Rejection streak: display count each round; show urgent warning at 4 ("One more rejection and Evil wins automatically")
3. Human player position: random
