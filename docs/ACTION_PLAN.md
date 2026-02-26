# Action Plan — AI Diplomacy Platform

## What This Is

A platform for playing Diplomacy where humans and AI agents compete in the same game anonymously. The core mechanic is structured negotiation rounds with batch message delivery — everyone writes blind, messages deliver simultaneously, no one can tell who's human and who's a model.

## Three Game Modes

Everything serves these three modes:

- **Mode 1: Humans Only** — Live play, no agents. Digital table for board game night.
- **Mode 2: Humans + Agents** — Mixed play, anonymous. The flagship experience.
- **Mode 3: Agents Only** — No humans in the game. Agents negotiate and fight at machine speed. Full game in minutes.

## Current State

The base engine is working:
- DATC-compliant game engine (Python, Tornado async, WebSocket)
- All tests pass (270+ total: engine, DATC compliance, JWT, player logs, Talk phase)
- Server runs on `localhost:8432`, web UI at `/app`
- Python client connects, authenticates, creates games, submits orders
- Existing web UI has a known crash bug (documented in `known-bugs.md`) — we're building our own UI later
- **Talk phase engine layer is in place** (Steps 1-2 complete on `feature/talk-phase-engine`)

To verify locally:
```bash
cd diplomacy
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest diplomacy/tests/
python -m diplomacy.server.run
```

## What Needs To Be Built

Two tracks can run in parallel. Track B does not depend on Track A.

---

### Track A: Negotiation Engine

Structured Talk phases with batch message delivery. Steps 1-2 are complete.

**Step 1 — Talk phase type in engine** ✅ DONE
- Added `'T'` (Talk) as a phase type in `Map.seq` (T-M-R-A-T cycle)
- `NO_TALK` rule skips Talk phases (default on for backward compat)
- Engine processes Talk → Movement transition
- 48 unit tests covering map sequences, phase transitions, serialization
- Branch: `feature/talk-phase-engine`

**Step 2 — Server round state machine** ✅ DONE
- Configurable multi-round Talk phases (`talk_num_rounds`, default 2)
- Round state machine: `round_open(1..N) → orders_open → phase advance`
- Ready signaling via existing `SetWaitFlag(wait=False)` — no new request types
- `talk_round_complete()` checks non-eliminated, controlled powers
- `ServerGame.process()` intercepts Talk phases, manages round advancement
- `_process_game` in server.py keeps game scheduled during Talk rounds
- Serialization round-trips for all talk state fields
- 27 additional unit tests (75 total Talk tests)
- Branch: `feature/talk-phase-engine`

**Step 3 — Batch message collection** ← NEXT
- New request type or reuse `send_game_message` during Talk rounds
- Messages submitted during `round_open` are held in `talk_held_messages`, not delivered
- Message validation: count limits per round, character limits, language rules
- Void messages (validation failures) still count against sender's quota
- Config fields: `talk_max_messages_per_round`, `talk_max_chars_per_message`

**Step 4 — Batch delivery**
- When a round closes (`_close_talk_round`), deliver all held messages simultaneously
- Use existing notification system to push to recipients
- Clear `talk_held_messages` after delivery
- Messages delivered between rounds, before next round opens

**Step 5 — Client notifications for round changes**
- Notify clients when round opens/closes/advances
- Send round number, state, and time remaining
- Clients need to know when they can send messages vs. when to submit orders

**Step 6 — Timer/deadline integration**
- Round-specific deadlines (separate from phase deadline)
- Config: `talk_round_deadline` (seconds per round), `talk_orders_deadline`
- Auto-advance round when deadline expires (even if not all powers ready)
- Wire into server scheduler (`_process_game` reschedule with round deadline)

**Step 7 — Public communique support**
- 1 per game-year per player, separate from private message limits
- Delivered to ALL players (not just recipients)
- Configurable: max chars, language, frequency
- Separate from private message quota

**Step 8 — Press log**
- After each round closes: sender, recipient(s), char count, status (DELIVERED/VOID), type (PRIVATE/PUBLIC)
- Broadcast press log to all players for information symmetry
- Metadata only — no message content revealed

---

### Track B: Agent Framework (no negotiation dependency)

These tasks use the existing engine as-is. Bots submit orders — no talking required.

**2.1 — Minimal "dumb bot" agent**
- Connects to server via Python client
- Picks random legal orders each turn
- Proves the agent pipeline works end-to-end
- Test: bot connects, submits valid orders, game advances

**2.2 — Agent standard data structure**
- Creator name (associated with the player)
- Model identifier (which AI model)
- Agent instructions (freeform strategy/personality prompt)
- Constraints: agent can only touch game state, nothing else
- Metadata for post-game analysis

**2.4 — Agent-vs-agent test harness**
- Spin up a game with 7 dumb bots
- Run the full game to completion
- Verify: all phases resolve, no crashes, game ends properly
- This is Mode 3 in its most primitive form

---

### After Tracks Merge

These need both the negotiation engine and the agent framework.

**2.3 — Agent runner**
- Takes an agent definition + API key
- Spins up a session that connects to the game server
- Feeds game state to the LLM, gets orders back
- Handles the negotiation/press phase (sends/receives messages)
- Model-agnostic: works with OpenAI, Anthropic, Google, etc.

**2.5 — "Smart bot" with LLM integration**
- Connect a real LLM as an agent
- Feed it: board state, possible orders, press messages
- Get back: orders + diplomatic messages
- Test: LLM agent plays a full game without errors

---

### Phase 3: Admin Portal

**3.1 — Game setup API**
- `POST /game/create` with all specifications
- Game mode selection, map selection, all press/communication settings
- Returns game ID + connection info

**3.2 — Admin frontend**
- Game mode → map → specifications (with smart defaults per mode) → connection → start
- Defaults vary by mode (see `game-rules-v1.md` for the full ruleset)

**3.3 — Specification defaults by mode**
- Mode 1: Anonymity off, no press channels, no AI features
- Mode 2: Anonymity on, restricted press, 2 rounds x 10 min, message limits, public communiques
- Mode 3: Anonymity off, restricted press, 2 rounds (seconds not minutes), message limits, public communiques

---

### Phase 4: Player Portal

**4.1 — Player connection flow**
- Human: join via link/code, enter name, waiting screen
- Agent: connect via API
- Show ready status for each seat

**4.2 — In-game player screen**
- Map view, powers panel, countdown timer
- Order submission, negotiation/press interface, build/disband interface

**4.3 — Spectator/display view**
- Read-only map for admin/audience
- Could be projected on a screen

---

### Phase 5: Polish (parallel, as time allows)

- 5.1 — Dramatic introductions (auto-generated intro cards, hype text)
- 5.2 — Post-turn recaps (AI-generated summaries, alliance visualization)
- 5.3 — Agent personas library (pre-built personalities, difficulty/suspicion/aggression sliders)
- 5.4 — Post-game analysis (message log, alliance timeline, trustworthiness scoring, ELO)
- 5.5 — Animations and presentation (map animations, radio room aesthetic, news ticker)

---

### Phase 6: Deployment

- 6.1 — Local network play
- 6.2 — Online hosting (stretch)
- 6.3 — Board game con demo (~6 months out, need stable Mode 1 + Mode 3 minimum)

## Task Order

```
Track A (negotiation):  Step 1 ✅ -> Step 2 ✅ -> Step 3 -> Step 4 -> Step 5 -> Step 6 -> Step 7 -> Step 8
Track B (agents):       2.1 -> 2.2 -> 2.4
                                    ↘ merge ↙
                              2.3 -> 2.5
                                    ↓
                         3.1 -> 3.2 -> 4.1 -> 4.2
                                    ↓
                           5.x (parallel)  6.x (after core is solid)
```

Track A implementation order rationale:
- Steps 3+4 (message collection + delivery) are the core negotiation mechanic — do these next
- Step 5 (client notifications) makes round changes visible — needed before timers make sense
- Step 6 (timers) adds auto-advance — needed for real gameplay but not for testing
- Steps 7+8 (communiques + press log) are additive features, can be done last

**Fastest demo (Mode 3, no talking):** 2.1 → 2.4 — can start now.

**Full Mode 3 (with negotiation):** Track A (Steps 3-6 minimum) + Track B → 2.3 → 2.5

**Full Mode 2 (humans + agents):** Above + 3.1 → 4.1 → 4.2

**Full Mode 1 (humans only):** Track A (Steps 3-6) → 3.1 → 3.2 → 4.1 → 4.2

## Key Files

- `game-rules-v1.md` — Full configurable ruleset with design rationale
- `known-bugs.md` — Documented issues from playtesting
- `docs/ARCHITECTURE.md` — System diagram, layers, data flow (in repo)
- `diplomacy/engine/game.py` — Core engine (~4,500 lines)
- `diplomacy/engine/map.py` — Board topology, adjacency, phase sequences
- `diplomacy/client/` — Python client (how agents connect)
- `diplomacy/server/` — WebSocket server, request managers, scheduler
- `diplomacy/server/server_game.py` — Talk round state machine (Steps 1-2)
- `diplomacy/tests/test_talk_phase.py` — 75 Talk phase tests
