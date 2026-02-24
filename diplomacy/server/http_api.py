"""REST HTTP API for Diplomacy.

Provides a stateless HTTP interface to the game server, running alongside
the existing WebSocket interface. Both share the same server, same auth,
same game state.

Routes:
    POST   /api/auth/login              Sign in (create account if needed), get JWT
    GET    /api/games                    List games
    POST   /api/games                    Create a new game
    GET    /api/games/{id}               Game state overview
    POST   /api/games/{id}/join          Join a game as a power or observer
    POST   /api/games/{id}/leave         Leave a game
    DELETE /api/games/{id}               Delete a game (admin/master)
    GET    /api/games/{id}/orders        Possible orders for your power
    POST   /api/games/{id}/orders        Submit orders
    POST   /api/games/{id}/process       Force-process current phase (admin)
"""
import logging
import traceback

import ujson as json
import tornado.web

from diplomacy.communication import requests, responses
from diplomacy.server import request_managers
from diplomacy.utils import exceptions, strings
from diplomacy.utils.token import create_token, decode_token

LOGGER = logging.getLogger(__name__)


class _EphemeralConnection:
    """Minimal stand-in for a WebSocket ConnectionHandler.

    The request_managers handlers receive a connection_handler argument
    that they only use for token-to-connection mapping (for push notifications).
    For HTTP, we use this lightweight object — notifications sent to it are
    silently dropped since the HTTP response has already been sent.
    """

    def write_message(self, message, binary=False):
        pass

    @staticmethod
    def translate_notification(notification):
        return [notification]


class _BaseApiHandler(tornado.web.RequestHandler):
    """Base class for API endpoints."""

    def initialize(self, server):
        self.server = server

    def prepare(self):
        # Disable XSRF for API routes (use JWT auth instead)
        pass

    def check_xsrf_cookie(self):
        pass

    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')
        # CORS — allow any origin for LAN party ergonomics
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Access-Control-Allow-Headers',
                        'Content-Type, Authorization')
        self.set_header('Access-Control-Allow-Methods',
                        'GET, POST, DELETE, OPTIONS')

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def _get_token(self):
        """Extract JWT from Authorization: Bearer header."""
        auth = self.request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            return auth[7:]
        return None

    def _get_username(self, token):
        """Decode username from a valid JWT."""
        try:
            payload = decode_token(self.server.secret_key, token)
            return payload['sub']
        except Exception:
            return None

    def _require_token(self):
        """Validate JWT and return (token, username). Raises 401 on failure."""
        token = self._get_token()
        if not token:
            self._error(401, 'Missing Authorization: Bearer <token> header')
            return None, None
        if not self.server.users.has_token(token):
            self._error(401, 'Invalid or expired token. Sign in again via POST /api/auth/login')
            return None, None
        username = self._get_username(token)
        return token, username

    def _json_body(self):
        """Parse JSON request body. Returns dict or None on error."""
        try:
            return json.loads(self.request.body)
        except (ValueError, TypeError):
            self._error(400, 'Request body must be valid JSON')
            return None

    def _ok(self, data=None, status=200):
        """Send a success response."""
        self.set_status(status)
        body = {'ok': True}
        if data is not None:
            body.update(data)
        self.write(json.dumps(body))

    def _error(self, status, message, details=None):
        """Send an error response with a helpful message."""
        self.set_status(status)
        body = {'ok': False, 'error': message}
        if details is not None:
            body['details'] = details
        self.write(json.dumps(body))

    def _attach_token(self, token, conn):
        """Attach a token to an ephemeral connection handler, handling reassignment."""
        existing = self.server.users.get_connection_handler(token)
        if existing is not None and existing is not conn:
            # Detach from previous ephemeral handler (other HTTP request finished)
            self.server.users.token_to_connection_handler.pop(token, None)
            if existing in self.server.users.connection_handler_to_tokens:
                self.server.users.connection_handler_to_tokens[existing].discard(token)
                if not self.server.users.connection_handler_to_tokens[existing]:
                    self.server.users.connection_handler_to_tokens.pop(existing, None)
        self.server.users.attach_connection_handler(token, conn)

    def write_error(self, status_code, **kwargs):
        """Override Tornado's default HTML error page with JSON."""
        message = 'Internal server error'
        if 'exc_info' in kwargs:
            exc = kwargs['exc_info'][1]
            if isinstance(exc, tornado.web.HTTPError):
                message = exc.log_message or str(exc)
            elif isinstance(exc, Exception):
                message = str(exc)
        self.set_header('Content-Type', 'application/json')
        self.write(json.dumps({'ok': False, 'error': message}))


class LoginHandler(_BaseApiHandler):
    """POST /api/auth/login — authenticate and get a JWT."""

    def post(self):
        body = self._json_body()
        if body is None:
            return
        username = body.get('username')
        password = body.get('password')
        if not username or not password:
            return self._error(400, 'Provide "username" and "password" in JSON body')

        # Create account if it doesn't exist (matching WebSocket behavior)
        if not self.server.users.has_username(username):
            from diplomacy.utils.common import hash_password
            self.server.users.add_user(username, hash_password(password))
            LOGGER.info('Created account: %s', username)
        elif not self.server.users.has_user(username, password):
            return self._error(401, 'Wrong password')

        token = create_token(self.server.secret_key, username)

        # Register token with an ephemeral connection
        conn = _EphemeralConnection()
        self.server.users.connect_user(username, conn, token)

        self._ok({
            'token': token,
            'username': username,
        })


class GamesListHandler(_BaseApiHandler):
    """GET /api/games — list games. POST /api/games — create a game."""

    def get(self):
        token, username = self._require_token()
        if not token:
            return
        games = []
        for game_id in self.server.get_game_indices():
            game = self.server.load_game(game_id)
            if game:
                games.append({
                    'game_id': game.game_id,
                    'phase': game.get_current_phase(),
                    'status': game.status,
                    'map_name': game.map_name,
                    'n_players': game.count_controlled_powers(),
                    'n_controls': game.get_expected_controls_count(),
                    'deadline': game.deadline,
                    'rules': list(game.rules),
                })
        self._ok({'games': games})

    def post(self):
        token, username = self._require_token()
        if not token:
            return
        body = self._json_body()
        if body is None:
            return

        game_id = body.get('game_id')
        if not game_id:
            return self._error(400, 'Provide "game_id"')

        # Check if game already exists
        if self.server.has_game_id(game_id):
            return self._error(409, f'Game "{game_id}" already exists',
                               details='Delete it first or choose a different ID')

        conn = _EphemeralConnection()
        self._attach_token(token, conn)

        try:
            req = requests.CreateGame.from_dict({
                'name': 'create_game',
                'request_id': 'http',
                'token': token,
                'game_id': game_id,
                'n_controls': body.get('n_controls', 7),
                'deadline': body.get('deadline', 0),
                'map_name': body.get('map_name', 'standard'),
                'rules': body.get('rules', ['POWER_CHOICE', 'NO_PRESS']),
            })
            response = request_managers.handle_request(self.server, req, conn)
            # handle_request returns a Future for sync handlers
            from tornado.concurrent import Future
            if isinstance(response, Future):
                # Sync handler — result is already set
                response = response.result()
        except exceptions.DiplomacyException as e:
            return self._error(400, str(e))

        self._ok({
            'game_id': game_id,
            'message': f'Game "{game_id}" created',
        }, status=201)


class GameHandler(_BaseApiHandler):
    """
    GET    /api/games/{id}  — game state overview
    DELETE /api/games/{id}  — delete game
    """

    def get(self, game_id):
        token, username = self._require_token()
        if not token:
            return
        if not self.server.has_game_id(game_id):
            return self._error(404, f'Game "{game_id}" not found')
        game = self.server.get_game(game_id)

        units = game.get_units()
        centers = game.get_centers()

        powers = {}
        for pwr_name, power in game.powers.items():
            controller = power.controller.last_value() if power.controller else None
            powers[pwr_name] = {
                'units': units.get(pwr_name, []),
                'centers': centers.get(pwr_name, []),
                'controller': controller if controller != strings.DUMMY else None,
                'is_controlled': power.is_controlled(),
                'order_is_set': power.order_is_set,
                'wait': power.wait,
            }

        self._ok({
            'game_id': game_id,
            'phase': game.get_current_phase(),
            'status': game.status,
            'map_name': game.map_name,
            'is_done': game.is_game_done,
            'rules': list(game.rules),
            'powers': powers,
        })

    def delete(self, game_id):
        token, username = self._require_token()
        if not token:
            return
        if not self.server.has_game_id(game_id):
            return self._error(404, f'Game "{game_id}" not found')
        game = self.server.get_game(game_id)

        # Only admin or game master can delete
        if not self.server.users.has_admin(username):
            return self._error(403, 'Only administrators can delete games')

        conn = _EphemeralConnection()
        self._attach_token(token, conn)

        try:
            # Register as omniscient to get delete permission
            game.add_omniscient_token(token)
            req = requests.DeleteGame.from_dict({
                'name': 'delete_game',
                'request_id': 'http',
                'token': token,
                'game_id': game_id,
                'game_role': strings.OMNISCIENT_TYPE,
                'phase': game.get_current_phase(),
            })
            result = request_managers.handle_request(self.server, req, conn)
            from tornado.concurrent import Future
            if isinstance(result, Future):
                result.result()
        except exceptions.DiplomacyException as e:
            return self._error(400, str(e))

        self._ok({'message': f'Game "{game_id}" deleted'})


class JoinHandler(_BaseApiHandler):
    """POST /api/games/{id}/join — join a game."""

    def post(self, game_id):
        token, username = self._require_token()
        if not token:
            return
        if not self.server.has_game_id(game_id):
            return self._error(404, f'Game "{game_id}" not found')
        game = self.server.get_game(game_id)

        body = self._json_body()
        if body is None:
            return

        power_name = body.get('power')
        if power_name and power_name not in game.powers:
            available = [p.name for p in game.powers.values() if not p.is_controlled()]
            return self._error(400,
                               f'"{power_name}" is not a valid power',
                               details={'available_powers': available})

        conn = _EphemeralConnection()
        self._attach_token(token, conn)

        try:
            req_dict = {
                'name': 'join_game',
                'request_id': 'http',
                'token': token,
                'game_id': game_id,
                'power_name': power_name,
            }
            if body.get('registration_password'):
                req_dict['registration_password'] = body['registration_password']
            req = requests.JoinGame.from_dict(req_dict)
            result = request_managers.handle_request(self.server, req, conn)
            from tornado.concurrent import Future
            if isinstance(result, Future):
                result = result.result()
        except exceptions.DiplomacyException as e:
            return self._error(400, str(e))

        role = power_name or 'observer'
        self._ok({
            'game_id': game_id,
            'role': role,
            'message': f'Joined game as {role}',
        })


class LeaveHandler(_BaseApiHandler):
    """POST /api/games/{id}/leave — leave a game."""

    def post(self, game_id):
        token, username = self._require_token()
        if not token:
            return
        if not self.server.has_game_id(game_id):
            return self._error(404, f'Game "{game_id}" not found')
        game = self.server.get_game(game_id)

        conn = _EphemeralConnection()
        self._attach_token(token, conn)

        # Determine role
        role = None
        for pwr_name, power in game.powers.items():
            if power.is_controlled() and game.is_controlled_by(pwr_name, username):
                role = pwr_name
                break
        if role is None:
            if game.has_observer_token(token):
                role = strings.OBSERVER_TYPE
            elif game.has_omniscient_token(token):
                role = strings.OMNISCIENT_TYPE

        if role is None:
            return self._error(400, 'You are not in this game')

        try:
            req = requests.LeaveGame.from_dict({
                'name': 'leave_game',
                'request_id': 'http',
                'token': token,
                'game_id': game_id,
                'game_role': role,
                'phase': game.get_current_phase(),
            })
            result = request_managers.handle_request(self.server, req, conn)
            from tornado.concurrent import Future
            if isinstance(result, Future):
                result.result()
        except exceptions.DiplomacyException as e:
            return self._error(400, str(e))

        self._ok({'message': f'Left game "{game_id}"'})


class OrdersHandler(_BaseApiHandler):
    """
    GET  /api/games/{id}/orders  — get possible orders for a power
    POST /api/games/{id}/orders  — submit orders
    """

    def get(self, game_id):
        token, username = self._require_token()
        if not token:
            return
        if not self.server.has_game_id(game_id):
            return self._error(404, f'Game "{game_id}" not found')
        game = self.server.get_game(game_id)

        power_name = self.get_argument('power', None)
        if not power_name:
            return self._error(400, 'Provide ?power=FRANCE query parameter')

        if power_name not in game.powers:
            return self._error(400, f'"{power_name}" is not a valid power',
                               details={'valid_powers': list(game.powers.keys())})

        possible = game.get_all_possible_orders()
        orderable = game.get_orderable_locations()
        my_locs = orderable.get(power_name, [])

        orders_by_loc = {}
        for loc in my_locs:
            loc_orders = possible.get(loc, [])
            if loc_orders:
                orders_by_loc[loc] = loc_orders

        self._ok({
            'game_id': game_id,
            'phase': game.get_current_phase(),
            'power': power_name,
            'units': game.get_units().get(power_name, []),
            'centers': game.get_centers().get(power_name, []),
            'orderable_locations': my_locs,
            'possible_orders': orders_by_loc,
            'n_orders_needed': len(orders_by_loc),
        })

    def post(self, game_id):
        token, username = self._require_token()
        if not token:
            return
        if not self.server.has_game_id(game_id):
            return self._error(404, f'Game "{game_id}" not found')
        game = self.server.get_game(game_id)

        body = self._json_body()
        if body is None:
            return

        power_name = body.get('power')
        orders = body.get('orders', [])
        wait = body.get('wait', False)

        if not power_name:
            return self._error(400, 'Provide "power" in JSON body')
        if not isinstance(orders, list):
            return self._error(400, '"orders" must be a JSON array of strings')

        if power_name not in game.powers:
            return self._error(400, f'"{power_name}" is not a valid power')

        # Check the user controls this power
        if not game.is_controlled_by(power_name, username):
            # Check if admin
            if not self.server.users.has_admin(username):
                controller = game.powers[power_name].controller.last_value()
                return self._error(403,
                                   f'You do not control {power_name}',
                                   details=f'Controlled by: {controller}')

        # Validate orders against possible orders and give useful feedback
        possible = game.get_all_possible_orders()
        orderable = game.get_orderable_locations()
        my_locs = orderable.get(power_name, [])

        orders_by_loc = {}
        for loc in my_locs:
            loc_orders = possible.get(loc, [])
            if loc_orders:
                orders_by_loc[loc] = loc_orders

        all_possible = set()
        for loc_orders in orders_by_loc.values():
            all_possible.update(loc_orders)

        valid_orders = []
        invalid_orders = []
        for order in orders:
            if order in all_possible:
                valid_orders.append(order)
            else:
                # Try to identify the location to suggest alternatives
                parts = order.split()
                loc = parts[1] if len(parts) >= 2 else None
                suggestion = None
                if loc and loc in orders_by_loc:
                    suggestion = orders_by_loc[loc][:5]
                invalid_orders.append({
                    'order': order,
                    'reason': 'Not in the set of possible orders',
                    'suggestions': suggestion,
                })

        if invalid_orders:
            return self._error(400, f'{len(invalid_orders)} invalid order(s)',
                               details={
                                   'invalid_orders': invalid_orders,
                                   'valid_orders_accepted': valid_orders,
                                   'hint': 'Use GET /api/games/{id}/orders?power=X to see all possible orders',
                               })

        # Submit via the internal handler
        conn = _EphemeralConnection()
        self._attach_token(token, conn)

        try:
            req = requests.SetOrders.from_dict({
                'name': 'set_orders',
                'request_id': 'http',
                'token': token,
                'game_id': game_id,
                'game_role': power_name,
                'phase': game.get_current_phase(),
                'orders': valid_orders,
                'wait': wait,
            })
            result = request_managers.handle_request(self.server, req, conn)
            from tornado.concurrent import Future
            if isinstance(result, Future):
                result.result()
        except exceptions.DiplomacyException as e:
            return self._error(400, str(e))

        self._ok({
            'game_id': game_id,
            'phase': game.get_current_phase(),
            'power': power_name,
            'orders_submitted': valid_orders,
            'n_orders': len(valid_orders),
            'wait': wait,
        })


class ProcessHandler(_BaseApiHandler):
    """POST /api/games/{id}/process — force-process current phase."""

    async def post(self, game_id):
        token, username = self._require_token()
        if not token:
            return
        if not self.server.has_game_id(game_id):
            return self._error(404, f'Game "{game_id}" not found')
        game = self.server.get_game(game_id)

        if not self.server.users.has_admin(username):
            return self._error(403, 'Only administrators can force-process')

        conn = _EphemeralConnection()
        self._attach_token(token, conn)

        old_phase = game.get_current_phase()

        try:
            # Register as omniscient for process permission
            game.add_omniscient_token(token)
            req = requests.ProcessGame.from_dict({
                'name': 'process_game',
                'request_id': 'http',
                'token': token,
                'game_id': game_id,
                'game_role': strings.OMNISCIENT_TYPE,
                'phase': game.get_current_phase(),
            })
            result = request_managers.handle_request(self.server, req, conn)
            from tornado.concurrent import Future
            if isinstance(result, Future):
                result.result()
        except exceptions.DiplomacyException as e:
            return self._error(400, str(e))

        # The scheduler processes async — yield to let it run
        from tornado import gen
        await gen.sleep(0.5)

        # Reload game to get new state
        game = self.server.get_game(game_id)
        new_phase = game.get_current_phase()

        units = game.get_units()
        centers = game.get_centers()
        standings = {}
        for pwr in sorted(units.keys()):
            standings[pwr] = {
                'units': len(units.get(pwr, [])),
                'centers': len(centers.get(pwr, [])),
            }

        self._ok({
            'game_id': game_id,
            'previous_phase': old_phase,
            'new_phase': new_phase,
            'is_done': game.is_game_done,
            'standings': standings,
        })


def get_api_routes(server):
    """Return list of Tornado route tuples for the HTTP API."""
    kwargs = {'server': server}
    return [
        tornado.web.url(r'/api/auth/login', LoginHandler, kwargs),
        tornado.web.url(r'/api/games', GamesListHandler, kwargs),
        tornado.web.url(r'/api/games/([^/]+)', GameHandler, kwargs),
        tornado.web.url(r'/api/games/([^/]+)/join', JoinHandler, kwargs),
        tornado.web.url(r'/api/games/([^/]+)/leave', LeaveHandler, kwargs),
        tornado.web.url(r'/api/games/([^/]+)/orders', OrdersHandler, kwargs),
        tornado.web.url(r'/api/games/([^/]+)/process', ProcessHandler, kwargs),
    ]
