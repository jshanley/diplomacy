# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — Talk Phase Negotiation Engine (Track A)

Branch: `feature/talk-phase-engine`

### Added
- **Talk phase type** — New `'T'` (Talk) phase in `Map.seq` creating a `T-M-R-A-T` cycle. `NO_TALK` rule (default on) skips Talk phases for backward compatibility. (`8a4a058`)
- **Server round state machine** — Configurable multi-round Talk phases (`talk_num_rounds`, default 2). Round state machine: `round_open(1..N) → orders_open → phase advance`. Ready signaling via `SetWaitFlag`. (`994f8a5`)
- **Batch message collection** — Messages submitted during `round_open` are held in `talk_held_messages`, not delivered immediately. Per-round count limits (`talk_max_messages_per_round`) and character limits (`talk_max_chars_per_message`). Void messages still count against quota. (`da2f1d6`)
- **Batch delivery** — Valid held messages delivered simultaneously when a round closes via `_close_talk_round()`. Void messages discarded. Server timestamps generated at delivery time. (`da2f1d6`)
- **TalkRoundUpdate notification** — New `TalkRoundUpdate` notification class broadcasts round number, state, and total rounds to all game tokens. Python + JS client handlers added. (`da2f1d6`)
- **Timer/deadline integration** — `talk_round_deadline` and `talk_orders_deadline` config fields (default 0 = no auto-advance). Server scheduler reschedules with talk-specific deadlines when configured. (`da2f1d6`)
- **Public communique support** — Per-year communique quota (`talk_max_communiques_per_year`, default 1) separate from private message limits. Delivered as `GLOBAL` recipient messages. Counts reset at Spring Talk round 1. (`da2f1d6`)
- **Press log** — `TalkPressLog` notification broadcasts metadata (sender, recipient, char_count, status, type) after each round closes. No message body revealed. Python + JS client handlers added. (`da2f1d6`)
- **191 Talk phase tests** — Comprehensive coverage across all 8 steps: phase sequences, state machine, batch collection/delivery, notifications, timers, communiques, press log, boundary conditions, serialization, multi-year cycles.

## Fork from diplomacy/diplomacy — 2026-02-23 / 2026-02-24

Forked from [diplomacy/diplomacy](https://github.com/diplomacy/diplomacy) v1.1.2 (last upstream release: April 2020). The following changes were made by John Shanley ([@jshanley](https://github.com/jshanley)):

### Added
- **JWT authentication** — Replaced opaque server-side tokens with PyJWT-based tokens carrying username, jti, and expiry in claims. New `diplomacy/utils/token.py` module for create/decode/verify. (`7d7395d`)
- **Per-player game log system** — JSONL storage at `data/player_logs/<username>/<game_id>.jsonl` with role-filtered GamePhaseData. New `GetPlayerHistory` request/response pair and handler. (`af8d1ea`)
- **HTTP REST API** — Stateless endpoints under `/api/` for login, game CRUD, order submission with error feedback, and force-processing. CORS allows any origin for LAN use. 650+ lines in `diplomacy/server/http_api.py`. (`78280a8`)
- **Docker support** — Multi-stage Dockerfile (Node 14 builds React, Python 3.10 runs server). Static file serving for web UI at `/app`. (`78280a8`)
- **Lobby system** — Backend lobby management (`diplomacy/server/lobby.py`, 319 lines), identity auth, and API docs endpoint at `/api/docs`. (`288625f`)
- **Lobby frontend** — Dark-themed lobby UI with dashboard, landing page, lobby view, hash-based routing, and full CSS overhaul (1700+ lines). New pages: `content_dashboard.jsx`, `content_landing.jsx`, `content_lobby.jsx`. (`0942747`)
- **Tests for JWT and player logs** — 158 lines of test coverage in `test_jwt_and_player_log.py`. (`a888aa9`)

### Changed
- **Web UI migrated from Create React App to Vite 6.0 + React 18 + Bootstrap 5.3.3** — All `.js` component files renamed to `.jsx`. Package dependencies modernized. (`cd31482`)
- **Server startup** — Wires JWT key loading, player log hooks, and static file serving. (`78280a8`)

### Upstream baseline (v1.1.2)
- DATC-compliant Diplomacy game engine
- Tornado-based WebSocket client-server architecture
- Python client library for programmatic play
- DAIDE protocol adapter for bot integration
- React web interface (pre-migration: CRA, React 16)
- 122 commits, last upstream activity: April 2020
