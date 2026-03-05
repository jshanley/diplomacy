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
- All tests pass (300+ total: engine, DATC compliance, JWT, player logs, Talk phase)
- Server runs on `localhost:8432`, web UI at `/app`
- Python client connects, authenticates, creates games, submits orders
- Existing web UI has a known crash bug (documented in `known-bugs.md`) — we're building our own UI later
- **Track A (Negotiation Engine) is complete** — all 8 steps done on `feature/talk-phase-engine`

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

**Step 3 — Batch message collection** ✅ DONE
- Reuses `send_game_message` — intercepted in `request_managers.py` during Talk rounds
- Messages submitted during `round_open` are held in `talk_held_messages`, not delivered
- Message validation: per-round count limits, character limits
- Void messages (validation failures) still count against sender's quota
- Config: `talk_max_messages_per_round` (default 5), `talk_max_chars_per_message` (default 500)
- 13 unit tests

**Step 4 — Batch delivery** ✅ DONE
- `_close_talk_round()` delivers all valid held messages simultaneously with server timestamps
- Void messages discarded (not delivered, not kept in held list)
- Transient `_last_delivered_messages` used for notification dispatch in `_process_game`
- 8 unit tests

**Step 5 — Client notifications for round changes** ✅ DONE
- `TalkRoundUpdate` notification broadcasts talk_round, talk_round_state, talk_num_rounds
- Python client: handler in `notification_managers.py`, callback setters on `NetworkGame`
- JS client: handler in `notification_managers.js`, level in `notifications.js`
- 3 unit tests

**Step 6 — Timer/deadline integration** ✅ DONE
- `talk_round_deadline` and `talk_orders_deadline` config fields (default 0 = no auto-advance)
- `_process_game` reschedules with talk-specific deadline via `schedule_game_with_deadline()`
- Deadline=0 means wait for all-ready signal only
- 4 unit tests

**Step 7 — Public communique support** ✅ DONE
- Per-year communique quota (`talk_max_communiques_per_year`, default 1) separate from private limits
- Character limit: `talk_max_communique_chars` (default 500)
- Delivered as `GLOBAL` recipient messages on round close
- Counts reset at Spring Talk round 1 of each year
- 8 unit tests

**Step 8 — Press log** ✅ DONE
- `TalkPressLog` notification with entries: sender, recipient, char_count, status, type
- `_generate_press_log()` builds metadata before messages are cleared
- Broadcast to all game tokens after round close, before round update notification
- No message body revealed — metadata only
- Python + JS client handlers added
- 8 unit tests

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
Track A (negotiation):  Step 1 ✅ -> Step 2 ✅ -> Step 3 ✅ -> Step 4 ✅ -> Step 5 ✅ -> Step 6 ✅ -> Step 7 ✅ -> Step 8 ✅  COMPLETE
Track B (agents):       2.1 -> 2.2 -> 2.4
                                    ↘ merge ↙
                              2.3 -> 2.5
                                    ↓
                         3.1 -> 3.2 -> 4.1 -> 4.2
                                    ↓
                           5.x (parallel)  6.x (after core is solid)
```

Track A is complete. Next priority is Track B (agent framework).

**Fastest demo (Mode 3, no talking):** 2.1 → 2.4 — can start now.

**Full Mode 3 (with negotiation):** Track B → 2.3 → 2.5 (Track A already done)

**Full Mode 2 (humans + agents):** Above + 3.1 → 4.1 → 4.2

**Full Mode 1 (humans only):** 3.1 → 3.2 → 4.1 → 4.2 (Track A already done)

## Key Files

- `game-rules-v1.md` — Full configurable ruleset with design rationale
- `known-bugs.md` — Documented issues from playtesting
- `docs/ARCHITECTURE.md` — System diagram, layers, data flow (in repo)
- `diplomacy/engine/game.py` — Core engine (~4,500 lines)
- `diplomacy/engine/map.py` — Board topology, adjacency, phase sequences
- `diplomacy/client/` — Python client (how agents connect)
- `diplomacy/server/` — WebSocket server, request managers, scheduler
- `diplomacy/server/server_game.py` — Talk round state machine, batch delivery, press log generation
- `diplomacy/server/request_managers.py` — Talk message interception (batch collection, communique handling)
- `diplomacy/server/notifier.py` — TalkRoundUpdate and TalkPressLog notification dispatch
- `diplomacy/communication/notifications.py` — TalkRoundUpdate and TalkPressLog notification classes
- `diplomacy/tests/test_talk_phase.py` — 150 Talk phase tests (Steps 1-8)
