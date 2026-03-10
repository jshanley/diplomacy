"""Bot runner — drives AI players inside a lobby game.

Each bot runs as a Tornado coroutine that polls game state and submits
orders/messages through request_managers (same path as the HTTP API).
LLM calls are offloaded to a ThreadPoolExecutor to avoid blocking the
event loop.
"""
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

from tornado import gen
from tornado.ioloop import IOLoop

from diplomacy.communication import requests as req_mod
from diplomacy.engine.message import Message
from diplomacy.server import request_managers

LOGGER = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=7)

# Personality snippets keyed by power name
_PERSONALITIES = {
    'AUSTRIA': 'You are cautious and diplomatic. Seek alliances but watch your back.',
    'ENGLAND': 'You are an island power. Control the seas and choose continental allies carefully.',
    'FRANCE': 'You are versatile. Balance aggression with diplomacy.',
    'GERMANY': 'You are centrally located. Alliances are critical for survival.',
    'ITALY': 'You are opportunistic. Look for weak neighbors and strike decisively.',
    'RUSSIA': 'You are large but spread thin. Focus your forces and negotiate truces.',
    'TURKEY': 'You are in a corner position. Expand methodically and build strong defenses.',
}

BOT_POLL_INTERVAL = 1.5  # seconds between game state checks


def start_bots(server, lobby):
    """Spawn a bot coroutine for each AI player in the lobby."""
    for username, config in lobby.bot_configs.items():
        player = lobby.get_player_by_username(username)
        if not player:
            continue
        IOLoop.current().spawn_callback(
            _run_bot, server, lobby, player, config)
        LOGGER.info('Bot runner started: %s as %s', player.display_name, player.power)


@gen.coroutine
def _run_bot(server, lobby, player, config):
    """Main loop for a single bot player."""
    try:
        agent = _create_agent(player.power, config)
    except Exception as exc:
        LOGGER.error('Bot %s: failed to create agent: %s', player.display_name, exc)
        return

    game_id = lobby.game_id
    last_acted = None  # (phase, round_num, round_state) tuple
    LOGGER.info('Bot %s (%s): agent created, starting poll loop', player.display_name, player.power)

    while True:
        yield gen.sleep(BOT_POLL_INTERVAL)

        try:
            game = server.get_game(game_id)
        except Exception:
            LOGGER.debug('Bot %s: game not found, stopping', player.display_name)
            return

        if game.is_game_done:
            LOGGER.info('Bot %s: game finished', player.display_name)
            return

        # Stop polling if this bot's power was eliminated
        bot_power = game.get_power(player.power)
        if bot_power and bot_power.is_eliminated():
            LOGGER.info('Bot %s: power %s eliminated, stopping', player.display_name, player.power)
            return

        phase = game.get_current_phase()
        phase_type = game.phase_type
        round_num = getattr(game, 'talk_round', 0)
        round_state = getattr(game, 'talk_round_state', '')

        # Skip if we already acted this phase+round+state
        current = (phase, round_num, round_state)
        if current == last_acted:
            continue

        if phase_type == 'T' and round_state == 'round_open':
            yield _bot_talk_round(server, game, lobby, player, agent)
            last_acted = current

        elif phase_type == 'T' and round_state == 'orders_open':
            yield _bot_submit_orders(server, game, lobby, player, agent)
            last_acted = current

        elif phase_type in ('M', 'R', 'A'):
            yield _bot_submit_orders(server, game, lobby, player, agent)
            last_acted = current


def _create_agent(power_name, config):
    """Create an LLMAgent for a bot player."""
    provider_name = config.get('provider', 'anthropic')
    api_key = config['api_key']
    model = config.get('model')

    if provider_name == 'anthropic':
        from diplomacy.agents.llm_provider import AnthropicProvider
        kwargs = {'api_key': api_key}
        if model:
            kwargs['model'] = model
        provider = AnthropicProvider(**kwargs)
    elif provider_name == 'openai':
        from diplomacy.agents.llm_provider import OpenAIProvider
        kwargs = {'api_key': api_key}
        if model:
            kwargs['model'] = model
        provider = OpenAIProvider(**kwargs)
    elif provider_name == 'google':
        from diplomacy.agents.llm_provider import GoogleProvider
        kwargs = {'api_key': api_key}
        if model:
            kwargs['model'] = model
        provider = GoogleProvider(**kwargs)
    else:
        from diplomacy.agents.llm_provider import AnthropicProvider
        kwargs = {'api_key': api_key}
        if model:
            kwargs['model'] = model
        provider = AnthropicProvider(**kwargs)

    from diplomacy.agents.llm_agent import LLMAgent
    instructions = _PERSONALITIES.get(power_name, '')
    return LLMAgent(provider, instructions=instructions, creator='lobby-bot')


@gen.coroutine
def _bot_talk_round(server, game, lobby, player, agent):
    """Generate messages and signal ready for a Talk round."""
    power_name = player.power
    LOGGER.info('Bot %s (%s): generating messages for round %d',
                player.display_name, power_name, game.talk_round)

    try:
        messages = yield gen.with_timeout(
            datetime.timedelta(seconds=60),
            IOLoop.current().run_in_executor(
                _executor, agent.generate_messages, game, power_name))
    except gen.TimeoutError:
        LOGGER.warning('Bot %s: message generation timed out', player.display_name)
        messages = []
    except Exception as exc:
        LOGGER.warning('Bot %s: message generation failed: %s', player.display_name, exc)
        messages = []

    # Send each message
    for recipient, body in messages:
        try:
            _send_message(server, game, lobby, player, recipient, body)
        except Exception as exc:
            LOGGER.warning('Bot %s: failed to send message to %s: %s',
                           player.display_name, recipient, exc)

    # Signal ready
    try:
        _signal_ready(server, game, lobby, player)
    except Exception as exc:
        LOGGER.warning('Bot %s: failed to signal ready: %s', player.display_name, exc)


@gen.coroutine
def _bot_submit_orders(server, game, lobby, player, agent):
    """Generate and submit orders, then signal ready."""
    power_name = player.power
    LOGGER.info('Bot %s (%s): generating orders for %s',
                player.display_name, power_name, game.get_current_phase())

    try:
        orders = yield gen.with_timeout(
            datetime.timedelta(seconds=60),
            IOLoop.current().run_in_executor(
                _executor, agent.generate_orders, game, power_name))
    except gen.TimeoutError:
        LOGGER.warning('Bot %s: order generation timed out', player.display_name)
        orders = []
    except Exception as exc:
        LOGGER.warning('Bot %s: order generation failed: %s', player.display_name, exc)
        orders = []

    # Submit orders with wait=False (auto-ready)
    try:
        _submit_orders(server, game, lobby, player, orders)
    except Exception as exc:
        LOGGER.warning('Bot %s: failed to submit orders: %s', player.display_name, exc)

    # During Talk orders_open, force_game_processing is skipped,
    # so we must explicitly signal ready via SetWaitFlag.
    if game.phase_type == 'T':
        try:
            _signal_ready(server, game, lobby, player)
        except Exception as exc:
            LOGGER.warning('Bot %s: failed to signal ready: %s', player.display_name, exc)


def _attach_token(server, token):
    """Attach a bot token to an ephemeral connection."""
    from diplomacy.server.http_api import _EphemeralConnection

    conn = _EphemeralConnection()
    existing = server.users.get_connection_handler(token)
    if existing is not None and existing is not conn:
        server.users.token_to_connection_handler.pop(token, None)
        if existing in server.users.connection_handler_to_tokens:
            server.users.connection_handler_to_tokens[existing].discard(token)
            if not server.users.connection_handler_to_tokens[existing]:
                server.users.connection_handler_to_tokens.pop(existing, None)
    server.users.attach_connection_handler(token, conn)
    return conn


def _send_message(server, game, lobby, player, recipient, body):
    """Send a diplomatic message through request_managers."""
    msg = Message(
        sender=player.power,
        recipient=recipient,
        phase=game.get_current_phase(),
        message=body,
    )

    conn = _attach_token(server, player.token)
    req = req_mod.SendGameMessage.from_dict({
        'name': 'send_game_message',
        'request_id': 'bot_msg',
        'token': player.token,
        'game_id': lobby.game_id,
        'game_role': player.power,
        'phase': game.get_current_phase(),
        'message': msg.to_dict(),
    })
    result = request_managers.handle_request(server, req, conn)
    from tornado.concurrent import Future
    if isinstance(result, Future):
        result.result()


def _submit_orders(server, game, lobby, player, orders):
    """Submit orders through request_managers with wait=False."""
    conn = _attach_token(server, player.token)
    req = req_mod.SetOrders.from_dict({
        'name': 'set_orders',
        'request_id': 'bot_orders',
        'token': player.token,
        'game_id': lobby.game_id,
        'game_role': player.power,
        'phase': game.get_current_phase(),
        'orders': orders,
        'wait': False,
    })
    result = request_managers.handle_request(server, req, conn)
    from tornado.concurrent import Future
    if isinstance(result, Future):
        result.result()


def _signal_ready(server, game, lobby, player):
    """Signal ready (wait=False) through request_managers."""
    conn = _attach_token(server, player.token)
    req = req_mod.SetWaitFlag.from_dict({
        'name': 'set_wait_flag',
        'request_id': 'bot_ready',
        'token': player.token,
        'game_id': lobby.game_id,
        'game_role': player.power,
        'phase': game.get_current_phase(),
        'wait': False,
    })
    result = request_managers.handle_request(server, req, conn)
    from tornado.concurrent import Future
    if isinstance(result, Future):
        result.result()
