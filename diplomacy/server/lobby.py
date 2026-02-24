"""Lobby system for Jackbox-style game joining.

Players join games by entering a short code and a display name.
Identity is stable — a JWT tied to a persistent username stored client-side.
The same identity works across multiple games.

The host creates a game, gets a code to share, and starts it when ready.
Game creation is separate from joining as a power.
"""
import logging
import random
import time

from diplomacy.communication import requests as req_mod
from diplomacy.server import request_managers
from diplomacy.server.server_game import ServerGame
from diplomacy.utils import strings

LOGGER = logging.getLogger(__name__)

# Unambiguous characters (no 0/O, 1/I/L)
CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
CODE_LENGTH = 4

ASSIGNMENT_RANDOM = 'random'

LOBBY_STATUS_WAITING = 'waiting'
LOBBY_STATUS_STARTED = 'started'


class Player:
    """A player in a lobby, backed by a stable user identity."""

    def __init__(self, username, display_name, token, is_host=False):
        self.username = username      # stable identity (JWT sub)
        self.display_name = display_name
        self.token = token            # current JWT (may be refreshed)
        self.is_host = is_host
        self.power = None             # assigned when game starts
        self.joined_at = time.time()

    def to_dict(self):
        return {
            'username': self.username,
            'display_name': self.display_name,
            'is_host': self.is_host,
            'power': self.power,
        }


class GameLobby:
    """A lobby for a single game, identified by a short code."""

    def __init__(self, code, host_player, map_name='standard',
                 assignment=ASSIGNMENT_RANDOM, n_powers=7):
        self.code = code
        self.map_name = map_name
        self.assignment = assignment
        self.n_powers = n_powers
        self.status = LOBBY_STATUS_WAITING
        self.players = {}   # username -> Player
        self.host_username = host_player.username
        self.game_id = None  # set when engine game is created
        self.created_at = time.time()

        self.add_player(host_player)

    def add_player(self, player):
        self.players[player.username] = player

    def remove_player(self, username):
        self.players.pop(username, None)

    def get_player_by_username(self, username):
        return self.players.get(username)

    def get_player_by_token(self, token):
        """Look up player by token. Also handles token refresh."""
        for p in self.players.values():
            if p.token == token:
                return p
        return None

    def player_count(self):
        return len(self.players)

    def is_full(self):
        return self.player_count() >= self.n_powers

    def to_dict(self):
        return {
            'code': self.code,
            'map_name': self.map_name,
            'assignment': self.assignment,
            'n_powers': self.n_powers,
            'status': self.status,
            'players': [p.to_dict() for p in self.players.values()],
            'player_count': self.player_count(),
            'host_username': self.host_username,
            'game_id': self.game_id,
        }


class LobbyManager:
    """Manages all active game lobbies."""

    def __init__(self, server):
        self.server = server
        self.lobbies = {}           # code -> GameLobby
        self._system_token = None   # admin token for creating engine games

    def _generate_code(self):
        """Generate a unique 4-char game code."""
        for _ in range(100):
            code = ''.join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))
            if code not in self.lobbies:
                return code
        raise RuntimeError('Could not generate unique code after 100 attempts')

    def _get_system_token(self):
        """Get (or create) an admin token for engine game creation."""
        if self._system_token and self.server.users.has_token(self._system_token):
            return self._system_token

        from diplomacy.utils.token import create_token
        from diplomacy.server.http_api import _EphemeralConnection

        token = create_token(self.server.secret_key, 'admin')
        conn = _EphemeralConnection()
        self.server.users.connect_user('admin', conn, token)
        self._system_token = token
        return token

    def _ensure_user_registered(self, username, token):
        """Make sure the user + token are registered with the server's user system."""
        from diplomacy.utils.common import hash_password
        from diplomacy.server.http_api import _EphemeralConnection

        if not self.server.users.has_username(username):
            self.server.users.add_user(username, hash_password(username))

        if not self.server.users.has_token(token):
            conn = _EphemeralConnection()
            self.server.users.connect_user(username, conn, token)

    def _attach_token(self, token):
        """Attach a token to a fresh ephemeral connection for a request."""
        from diplomacy.server.http_api import _EphemeralConnection

        conn = _EphemeralConnection()
        existing = self.server.users.get_connection_handler(token)
        if existing is not None and existing is not conn:
            self.server.users.token_to_connection_handler.pop(token, None)
            if existing in self.server.users.connection_handler_to_tokens:
                self.server.users.connection_handler_to_tokens[existing].discard(token)
                if not self.server.users.connection_handler_to_tokens[existing]:
                    self.server.users.connection_handler_to_tokens.pop(existing, None)
        self.server.users.attach_connection_handler(token, conn)
        return conn

    def create_game(self, username, display_name, token,
                    map_name='standard', assignment=ASSIGNMENT_RANDOM):
        """Create a new game lobby. The caller provides their stable identity.

        Returns (lobby, player).
        """
        code = self._generate_code()
        self._ensure_user_registered(username, token)

        host = Player(username, display_name, token, is_host=True)

        # Determine number of powers from map
        map_info = self.server.get_map(map_name)
        n_powers = len(map_info['powers']) if map_info else 7

        lobby = GameLobby(code, host, map_name=map_name,
                          assignment=assignment, n_powers=n_powers)
        self.lobbies[code] = lobby

        LOGGER.info('Game created: code=%s host=%s map=%s', code, display_name, map_name)
        return lobby, host

    def join_game(self, code, username, display_name, token):
        """Join an existing game lobby with a stable identity.

        Returns (lobby, player).
        """
        code = code.upper().strip()
        lobby = self.lobbies.get(code)
        if not lobby:
            return None, None

        if lobby.status != LOBBY_STATUS_WAITING:
            raise ValueError('Game has already started')
        if lobby.is_full():
            raise ValueError(f'Game is full ({lobby.n_powers} players)')

        # Check if this user is already in the lobby
        existing = lobby.get_player_by_username(username)
        if existing:
            # Update their token (reconnection) and return
            existing.token = token
            return lobby, existing

        # Check for duplicate display name
        for p in lobby.players.values():
            if p.display_name.lower() == display_name.lower():
                raise ValueError(f'Name "{display_name}" is already taken')

        self._ensure_user_registered(username, token)

        player = Player(username, display_name, token)
        lobby.add_player(player)

        LOGGER.info('Player joined: code=%s name=%s (%d/%d)',
                     code, display_name, lobby.player_count(), lobby.n_powers)
        return lobby, player

    def get_lobby(self, code):
        return self.lobbies.get(code.upper().strip())

    def get_lobby_for_token(self, token):
        """Find the lobby a token belongs to."""
        for lobby in self.lobbies.values():
            if lobby.get_player_by_token(token):
                return lobby
        return None

    def start_game(self, code, username):
        """Host starts the game.

        1. Creates the engine game using the system admin account (no player role)
        2. Assigns powers to players
        3. Each player joins the engine game via standard JoinGame

        Returns the lobby with updated state.
        """
        code = code.upper().strip()
        lobby = self.lobbies.get(code)
        if not lobby:
            raise ValueError('Game not found')

        # Verify the caller is the host
        if username != lobby.host_username:
            raise ValueError('Only the host can start the game')

        if lobby.status != LOBBY_STATUS_WAITING:
            raise ValueError('Game has already started')

        # Get available powers from the map
        map_info = self.server.get_map(lobby.map_name)
        if not map_info:
            raise ValueError(f'Unknown map: {lobby.map_name}')
        power_names = sorted(map_info['powers'])

        # Assign powers
        players = list(lobby.players.values())
        if lobby.assignment == ASSIGNMENT_RANDOM:
            assigned_powers = random.sample(power_names, len(players))
            for player, power in zip(players, assigned_powers):
                player.power = power

        # Step 1: Create the engine game using the system admin account
        game_id = f'game_{code}'
        n_controls = len(players)
        system_token = self._get_system_token()
        system_conn = self._attach_token(system_token)

        try:
            create_req = req_mod.CreateGame.from_dict({
                'name': 'create_game',
                'request_id': 'lobby_create',
                'token': system_token,
                'game_id': game_id,
                'n_controls': n_controls,
                'deadline': 0,
                'map_name': lobby.map_name,
                'rules': ['POWER_CHOICE'],
            })
            result = request_managers.handle_request(
                self.server, create_req, system_conn)
            from tornado.concurrent import Future
            if isinstance(result, Future):
                result = result.result()
        except Exception as e:
            raise ValueError(f'Failed to create engine game: {e}')

        # Step 2: Each player joins the engine game as their assigned power
        for player in players:
            self._ensure_user_registered(player.username, player.token)
            p_conn = self._attach_token(player.token)

            try:
                join_req = req_mod.JoinGame.from_dict({
                    'name': 'join_game',
                    'request_id': 'lobby_join',
                    'token': player.token,
                    'game_id': game_id,
                    'power_name': player.power,
                })
                result = request_managers.handle_request(
                    self.server, join_req, p_conn)
                from tornado.concurrent import Future
                if isinstance(result, Future):
                    result = result.result()
                LOGGER.info('Player %s joined as %s',
                            player.display_name, player.power)
            except Exception as e:
                LOGGER.error('Failed to join player %s as %s: %s',
                             player.display_name, player.power, e)
                raise ValueError(
                    f'Failed to join {player.display_name} as {player.power}: {e}')

        lobby.status = LOBBY_STATUS_STARTED
        lobby.game_id = game_id

        LOGGER.info('Game started: code=%s game_id=%s players=%d',
                     code, game_id, len(players))
        return lobby
