# ==============================================================================
# Copyright (C) 2019 - Philip Paquette
#
#  This program is free software: you can redistribute it and/or modify it under
#  the terms of the GNU Affero General Public License as published by the Free
#  Software Foundation, either version 3 of the License, or (at your option) any
#  later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
#  FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
#  details.
#
#  You should have received a copy of the GNU Affero General Public License along
#  with this program.  If not, see <https://www.gnu.org/licenses/>.
# ==============================================================================
"""Harness for running agent-vs-agent Diplomacy games."""
import logging
import random as _random

from tornado import gen
from tornado.concurrent import Future
from tornado.ioloop import IOLoop

from diplomacy.engine.game import Game
from diplomacy.client.connection import connect
from diplomacy.server.server import Server
from diplomacy.utils import common

from diplomacy.agents.base_agent import BaseAgent

LOGGER = logging.getLogger(__name__)


class GameResult:
    """Container for the outcome of a completed game.

    Attributes:
        phases_played:  Number of phases that were processed.
        phase_history:  List of phase short-names in order.
        final_centers:  Dict mapping power_name -> list of supply centers at game end.
        winner:         Power name that achieved victory, or None if draw/no winner.
        is_done:        Whether the game reached COMPLETED status.
        agents:         Dict mapping power_name -> AgentDef dict.
    """
    __slots__ = ['phases_played', 'phase_history', 'final_centers', 'winner',
                 'is_done', 'agents']

    def __init__(self):
        self.phases_played = 0
        self.phase_history = []
        self.final_centers = {}
        self.winner = None
        self.is_done = False
        self.agents = {}


def _extract_result(game, agent_map):
    """Build a GameResult from a completed Game object."""
    result = GameResult()
    result.phases_played = len(game.state_history)
    result.phase_history = list(game.state_history.keys())
    result.final_centers = game.get_centers()
    result.is_done = game.is_game_done
    result.agents = {pn: agent.agent_def.to_dict() for pn, agent in agent_map.items()}

    # Determine winner: first power with >= win supply centers.
    if game.win:
        for power_name, centers in result.final_centers.items():
            if len(centers) >= game.win:
                result.winner = power_name
                break

    return result


def _normalize_agents(agents, power_names):
    """Convert agents argument into a dict mapping power_name -> BaseAgent.

    Accepts:
        - A single BaseAgent (used for all powers)
        - A list of BaseAgents (one per power, assigned alphabetically)
        - A dict {power_name: BaseAgent}
    """
    if isinstance(agents, BaseAgent):
        return {pn: agents for pn in power_names}
    elif isinstance(agents, list):
        if len(agents) != len(power_names):
            raise ValueError(
                'Expected %d agents, got %d' % (len(power_names), len(agents)))
        return dict(zip(power_names, agents))
    elif isinstance(agents, dict):
        missing = set(power_names) - set(agents.keys())
        if missing:
            raise ValueError('Missing agents for powers: %s' % missing)
        return agents
    else:
        raise TypeError('agents must be BaseAgent, list, or dict, got %s' % type(agents))


# ---------------------------------------------------------------------------
# Local game harness (fast, no server)
# ---------------------------------------------------------------------------

def run_local_game(agents, max_phases=1000, map_name='standard'):
    """Run a full game locally (no server) with the given agents.

    :param agents: A single BaseAgent (all 7 powers), list of 7, or dict {power: agent}.
    :param max_phases: Safety limit on number of phases.
    :param map_name: Name of the map to use.
    :return: A GameResult with the outcome.
    :rtype: GameResult
    """
    game = Game(map_name=map_name)
    power_names = sorted(game.get_map_power_names())
    agent_map = _normalize_agents(agents, power_names)

    for power_name, agent in agent_map.items():
        agent.on_game_start(game, power_name)

    phases = 0
    while not game.is_game_done and phases < max_phases:
        for power_name in power_names:
            if game.get_power(power_name).is_eliminated():
                continue
            orders = agent_map[power_name].generate_orders(game, power_name)
            game.set_orders(power_name, orders)
        game.process()
        phases += 1

        for power_name, agent in agent_map.items():
            if not game.get_power(power_name).is_eliminated():
                agent.on_phase_end(game, power_name)

    return _extract_result(game, agent_map)


# ---------------------------------------------------------------------------
# Network game harness (proves pipeline with server)
# ---------------------------------------------------------------------------

def run_network_game(agents, port=None, max_phases=1000, map_name='standard',
                     enable_talk=False, talk_num_rounds=2):
    """Run a full game over the network with server in the same process.

    Spins up a Server, creates a game, connects 7 bot clients, and runs
    to completion. Follows the pattern in diplomacy/tests/network/test_real_game.py.

    :param agents: Same format as run_local_game.
    :param port: Port for the server (random if None).
    :param max_phases: Safety limit.
    :param map_name: Map name.
    :param enable_talk: If True, enable Talk phases for negotiation.
    :param talk_num_rounds: Number of talk rounds per Talk phase (when enabled).
    :return: A GameResult.
    :rtype: GameResult
    """
    if port is None:
        port = _random.randint(9000, 9999)

    game_template = Game(map_name=map_name)
    power_names = sorted(game_template.get_map_power_names())
    agent_map = _normalize_agents(agents, power_names)

    io_loop = IOLoop()
    io_loop.make_current()
    common.Tornado.stop_loop_on_callback_error(io_loop)

    server = Server()
    result_holder = [None]

    @gen.coroutine
    def _run():
        """Main coroutine: create game, connect bots, play to completion."""
        # Connect as admin, create game.
        connection = yield connect('localhost', port)
        admin_channel = yield connection.authenticate('admin', 'password')
        rules = ['IGNORE_ERRORS', 'POWER_CHOICE', 'REAL_TIME']
        if not enable_talk:
            rules.extend(['NO_PRESS', 'NO_TALK'])
        create_kwargs = dict(map_name=map_name, rules=rules, deadline=0)
        if enable_talk:
            create_kwargs['n_controls'] = len(power_names)
            create_kwargs['talk_num_rounds'] = talk_num_rounds
        admin_game = yield admin_channel.create_game(**create_kwargs)
        game_id = admin_game.game_id

        all_done = Future()
        bot_games = {}

        # Each bot connects as a separate user and joins the game.
        for power_name in power_names:
            username = 'bot_%s' % power_name
            password = 'password_%s' % power_name
            user_channel = yield connection.authenticate(username, password)
            user_game = yield user_channel.join_game(
                game_id=game_id, power_name=power_name)
            bot_games[power_name] = user_game

            # Register callback: when phase processes, submit next orders.
            def _make_callback(pn, agent):
                @gen.coroutine
                def _on_game_processed(network_game, notification=None):
                    if network_game.is_game_done:
                        if not all_done.done():
                            all_done.set_result(None)
                        return
                    agent.on_phase_end(network_game, pn)
                    # If the new phase is a Talk phase, the talk_round_update
                    # callback handles messaging; we still submit orders for
                    # non-Talk phases.
                    phase = network_game.get_current_phase()
                    if not phase or phase == 'COMPLETED':
                        return
                    phase_type = phase[-1] if len(phase) > 1 else ''
                    if phase_type != 'T':
                        orders = agent.generate_orders(network_game, pn)
                        yield network_game.set_orders(orders=orders)
                return _on_game_processed

            user_game.add_on_game_processed(
                _make_callback(power_name, agent_map[power_name]))

            # Register Talk round callback if talk is enabled.
            if enable_talk:
                def _make_talk_callback(pn, agent):
                    @gen.coroutine
                    def _on_talk_round_update(network_game, notification=None):
                        if not notification:
                            return
                        if notification.talk_round_state != 'ROUND_OPEN':
                            return
                        messages = agent.generate_messages(network_game, pn)
                        for recipient, body in messages:
                            msg = network_game.new_power_message(recipient, body)
                            yield network_game.send_game_message(message=msg)
                        # Signal ready for this round.
                        yield network_game.no_wait()
                    return _on_talk_round_update

                user_game.add_on_talk_round_update(
                    _make_talk_callback(power_name, agent_map[power_name]))

        # Notify agents and submit initial orders.
        for power_name in power_names:
            agent = agent_map[power_name]
            agent.on_game_start(bot_games[power_name], power_name)
            orders = agent.generate_orders(bot_games[power_name], power_name)
            yield bot_games[power_name].set_orders(orders=orders)

        # Wait for game to complete.
        yield all_done

        result_holder[0] = _extract_result(admin_game, agent_map)
        io_loop.stop()

    io_loop.add_callback(_run)
    server.start(port, io_loop)
    io_loop.clear_current()
    io_loop.close()
    server.backend.http_server.stop()
    Server.__cache__.clear()

    return result_holder[0]
