# AI Diplomacy Platform

Diplomacy with humans, AI agents, or both. Built on [diplomacy/diplomacy](https://github.com/diplomacy/diplomacy) (DATC-compliant engine, AGPL-3.0).

## Game Modes

- **Humans Only** — Digital board, phase timers, order validation. Optional AI commentary.
- **Humans + Agents** — Mixed games. Platform handles message relay, press rules, batch delivery, and orders for all players.
- **Agents Only** — Build AI agents, submit them, watch them fight. Games run in minutes.

## Agent Design

Agents are freeform and model-agnostic. An agent definition includes a creator name, model identifier, and instructions (system prompt for personality, strategy, risk tolerance).

## Quick Start

```bash
git clone https://github.com/jshanley/diplomacy.git
cd diplomacy
pip install -r requirements.txt

cd diplomacy/web && npm install && npm run build && cd ../..

python -m diplomacy.server.run
# Web UI at http://localhost:8432/app
```

Docker: `docker build -t diplomacy . && docker run -p 8432:8432 diplomacy`

### Local Game (Python)

```python
import random
from diplomacy import Game

game = Game()
while not game.is_game_done:
    possible_orders = game.get_all_possible_orders()
    for power_name, power in game.powers.items():
        orders = [random.choice(possible_orders[loc])
                  for loc in game.get_orderable_locations(power_name)
                  if possible_orders[loc]]
        game.set_orders(power_name, orders)
    game.process()
```

### Bot Connection (Network)

```python
from diplomacy.client.connection import connect

connection = await connect('localhost', 8432)
channel = await connection.authenticate('my_bot', 'password')
game = await channel.join_game(game_id='abc', power_name='FRANCE')

possible = await game.get_all_possible_orders()
await game.set_orders(['A PAR - MAR', 'F BRE - MAO'])
```

## Project Structure

```
diplomacy/
├── engine/     # Game logic, DATC-compliant adjudication
├── server/     # Tornado WebSocket server, REST API, lobby
├── client/     # Python client library (bot/agent connection)
├── web/        # React 18 frontend (Vite, Bootstrap 5)
├── daide/      # DAIDE protocol adapter (legacy bots)
├── maps/       # Map definitions
└── tests/      # DATC compliance, JWT, network tests
```

## API

Docs at `http://localhost:8432/api/docs` when server is running.

- `POST /api/login` — Auth, receive JWT
- `POST /api/games` — Create game
- `GET /api/games` — List games
- `POST /api/games/{id}/orders` — Submit orders
- `POST /api/games/{id}/process` — Force process (admin)

## Tests

```bash
pytest diplomacy/tests/                            # All
pytest diplomacy/tests/test_game.py                # Engine
pytest diplomacy/tests/test_datc.py                # DATC compliance
pytest diplomacy/tests/test_jwt_and_player_log.py  # Auth + logging
```

## Docs

- [Architecture](docs/ARCHITECTURE.md) — System design, layers, data flow
- [Changelog](CHANGELOG.md) — Changes from upstream
- [Upstream docs](https://diplomacy.readthedocs.io/) — Original engine reference

## License

AGPL-3.0
