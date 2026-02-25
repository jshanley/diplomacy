# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENTS                                 │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Web UI   │  │ Admin UI │  │ AI Agent │  │ AI Agent   │  │
│  │ (Human)  │  │ (Setup)  │  │ (Python) │  │ (Python)   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
│       │              │             │               │         │
└───────┼──────────────┼─────────────┼───────────────┼─────────┘
        │              │             │               │
        │   WebSocket / REST API     │               │
        │              │             │               │
┌───────┼──────────────┼─────────────┼───────────────┼─────────┐
│       ▼              ▼             ▼               ▼         │
│  ┌──────────────────────────────────────────────────────┐    │
│  │                    SERVER                             │    │
│  │                                                       │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │    │
│  │  │ Connection  │  │   Request    │  │  Notifier  │  │    │
│  │  │  Handler    │──│  Managers    │──│ (broadcast)│  │    │
│  │  └─────────────┘  └──────┬───────┘  └────────────┘  │    │
│  │                          │                            │    │
│  │  ┌─────────────┐  ┌─────▼────────┐  ┌────────────┐  │    │
│  │  │   Lobby     │  │ Server Game  │  │ Scheduler  │  │    │
│  │  │  Manager    │  │  (per game)  │  │ (deadlines)│  │    │
│  │  └─────────────┘  └──────┬───────┘  └────────────┘  │    │
│  │                          │                            │    │
│  │  ┌─────────────┐  ┌─────▼────────┐  ┌────────────┐  │    │
│  │  │  HTTP API   │  │  Player Log  │  │   Users    │  │    │
│  │  │  (REST)     │  │   (JSONL)    │  │  (JWT)     │  │    │
│  │  └─────────────┘  └──────────────┘  └────────────┘  │    │
│  └──────────────────────────────────────────────────────┘    │
│                          │                                    │
│  ┌───────────────────────▼──────────────────────────────┐    │
│  │                    ENGINE                              │    │
│  │                                                       │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │    │
│  │  │   Game   │  │   Map    │  │     Power        │   │    │
│  │  │ (4500 L) │  │ (1450 L) │  │   (per player)   │   │    │
│  │  └──────────┘  └──────────┘  └──────────────────┘   │    │
│  │                                                       │    │
│  │  Order resolution, DATC compliance, phase management  │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Layer Breakdown

### Engine (`diplomacy/engine/`)

Pure game logic. No networking, no UI. Can be used standalone.

| File | Lines | Purpose |
|------|-------|---------|
| `game.py` | 4,518 | Game state machine. Order validation, combat resolution, phase advancement. |
| `map.py` | 1,453 | Board topology. Adjacency lists, coasts, supply centers, convoy paths. |
| `power.py` | 407 | Player state. Units, centers, orders, influence, civil disorder. |
| `message.py` | 122 | In-game message objects. |
| `renderer.py` | — | SVG/PNG map rendering. |

**Key API:**
```python
game = Game(map_name='standard')
game.get_all_possible_orders()        # Dict[location, Set[order_strings]]
game.set_orders('FRANCE', ['A PAR - MAR'])
game.process()                         # Resolve phase, advance
game.get_units('FRANCE')              # ['A MAR']
game.get_centers('FRANCE')            # ['PAR', 'MAR', 'BRE']
```

**Phase cycle:** `SPRING M → SPRING R → FALL M → FALL R → WINTER A → repeat`

### Server (`diplomacy/server/`)

Tornado-based async server. Handles connections, auth, game lifecycle, notifications.

| File | Lines | Purpose |
|------|-------|---------|
| `server.py` | 1,005 | Main server. Startup, game management, backup. |
| `server_game.py` | 726 | Game wrapper with role-based filtering and server hooks. |
| `connection_handler.py` | 136 | WebSocket handler. JSON in, JSON out. |
| `request_managers.py` | 1,268 | Routes requests to handlers. All game actions go through here. |
| `notifier.py` | 760 | Broadcasts state changes to connected clients. |
| `scheduler.py` | 412 | Phase deadline management. |
| `http_api.py` | 650+ | REST API for stateless access. |
| `lobby.py` | 319 | Lobby management (John's addition). |
| `player_log.py` | 82 | Per-player JSONL logging (John's addition). |
| `users.py` | ~180 | User management with JWT auth (John's rewrite). |

### Client (`diplomacy/client/`)

Python client library. Connects to the server over WebSocket. This is how AI agents will play.

| File | Lines | Purpose |
|------|-------|---------|
| `connection.py` | 635 | WebSocket connection management. |
| `channel.py` | 185 | Authenticated session. Create/join/leave games. |
| `network_game.py` | 462 | Client-side game. Submit orders, send messages, receive notifications. |

**Agent connection flow:**
```python
from diplomacy.client.connection import connect

connection = await connect('localhost', 8888)
channel = await connection.authenticate('bot_name', 'password')
game = await channel.join_game(game_id='abc', power_name='FRANCE')

possible = await game.get_all_possible_orders()
await game.set_orders(['A PAR - MAR'])
await game.send_game_message('Support me in MAR?', 'ENGLAND')
```

### Communication (`diplomacy/communication/`)

Protocol definitions. Request/response/notification classes shared by client and server.

- **Requests:** `SignIn`, `CreateGame`, `JoinGame`, `SetOrders`, `SendGameMessage`, etc.
- **Responses:** `Ok`, `Error`, `DataGame`, `DataToken`, etc.
- **Notifications:** `GamePhaseUpdate`, `GameProcessed`, `GameMessageReceived`, etc.

### Web (`diplomacy/web/`)

React 18 frontend, built with Vite, styled with Bootstrap 5.

- Interactive SVG map with click-to-order
- Dark-themed lobby (dashboard, landing, lobby views)
- Hash-based routing
- Communicates with server via same WebSocket protocol as Python client

### DAIDE (`diplomacy/daide/`)

DAIDE (Diplomacy AI Development Environment) protocol adapter. TCP server for connecting legacy AI bots. Binary protocol, separate from the WebSocket API. Available but not critical for our use case — we'll use the Python client instead.

## Data Flow

### Order Submission
```
Player/Agent submits orders
  → Client sends SetOrders request (WebSocket JSON)
    → ConnectionHandler.on_message()
      → request_managers.handle_request()
        → game.set_orders(power, orders)
        → Notifier broadcasts OrdersUpdated to interested clients
      → Response sent back to client
```

### Phase Processing
```
All players ready (or deadline expires)
  → Scheduler triggers processing
    → server_game.process()
      → engine validates orders
      → engine resolves combat (supports, convoys, bounces, dislodgments)
      → engine updates units and centers
      → engine advances phase
    → Notifier broadcasts GameProcessed to all clients
    → Player logs written (JSONL)
    → Scheduler sets next deadline
```

### Message Relay
```
Player sends message
  → Client sends SendGameMessage request
    → server validates (sender controls power, game is active)
    → message stored in game state
    → Notifier sends GameMessageReceived to recipient(s)
  → Press log metadata recorded
```

## What Exists vs. What We Need to Build

### Exists (from upstream + John's fork)
- Complete DATC-compliant game engine
- WebSocket server with game lifecycle management
- Python client for programmatic play (agent foundation)
- JWT authentication
- REST API
- Lobby system (backend + frontend)
- Docker deployment
- Per-player game logging
- React web UI with interactive map

### Needs to Be Built
- **Agent runner** — Takes agent definition + API key, connects to server, feeds game state to LLM, submits orders and messages
- **Press engine** — Batch delivery (Round A/B), message limits, character counting, public communiques, press logs
- **Game mode configuration** — Three modes with smart defaults, admin setup flow
- **Admin portal** — Game creation wizard with full specification options
- **Player portal** — In-game UI for humans (order submission, negotiation, map view)
- **Post-game analysis** — Message logs, alliance mapping, trustworthiness scoring
- **Presentation layer** — Dramatic intros, recaps, animations (stretch)

## Key Technical Decisions (Inherited)

- **Python 3 + Tornado** — Async but single-threaded. Fine for game workloads.
- **WebSocket** — Persistent connections, real-time notifications. Both web UI and Python client use the same protocol.
- **AGPL-3.0** — Any modifications must be shared if distributed. We're building on top, so our additions inherit this license.
- **Backstabbr-compatible notation** — Orders use full province names, explicit coasts.
