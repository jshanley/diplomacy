# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

_Nothing yet._

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
