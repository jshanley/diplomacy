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
"""LLM-powered Diplomacy agent (smart bot)."""
import logging
import random as _random

from diplomacy.agents.agent_def import AgentDef
from diplomacy.agents.base_agent import BaseAgent
from diplomacy.agents.state_formatter import format_game_state, format_message_prompt
from diplomacy.agents.order_parser import parse_orders, parse_messages

LOGGER = logging.getLogger(__name__)


class LLMAgent(BaseAgent):
    """Agent that uses an LLM to generate orders and diplomatic messages.

    Feeds structured game state to an LLMProvider and parses the response
    into validated orders. Falls back to random legal orders if the LLM
    call fails or returns unparseable output.

    :param provider: An LLMProvider instance (OpenAI, Anthropic, etc.).
    :param instructions: Custom strategy/personality prompt prepended to system prompt.
    :param creator: Creator name for AgentDef metadata.
    :param fallback_seed: RNG seed for fallback random orders.
    :type provider: diplomacy.agents.llm_provider.LLMProvider
    :type instructions: str
    :type creator: str
    :type fallback_seed: int or None
    """

    def __init__(self, provider, instructions='', creator='user', fallback_seed=None):
        self._provider = provider
        self._fallback_rng = _random.Random(fallback_seed)
        self._agent_def = AgentDef(
            creator=creator,
            model_id=provider.model,
            instructions=instructions,
            description='LLM-powered Diplomacy agent',
        )

    @property
    def agent_def(self):
        return self._agent_def

    def generate_orders(self, game, power_name):
        """Format game state, call LLM, parse and validate orders.

        :param game: Current game state.
        :param power_name: Power to generate orders for.
        :return: List of validated order strings.
        :rtype: list[str]
        """
        state_text = format_game_state(game, power_name)
        system_prompt = self._build_order_prompt(power_name)

        try:
            response = self._provider.complete(system_prompt, state_text)
        except Exception as exc:
            LOGGER.warning('LLM call failed for %s: %s — falling back to random', power_name, exc)
            return self._fallback_orders(game, power_name)

        possible = game.get_all_possible_orders()
        orderable = game.get_orderable_locations(power_name)
        orders = parse_orders(response, possible, orderable)

        # Fill any locations the LLM missed with random valid orders
        orders = self._fill_missing(orders, possible, orderable)
        return orders

    def generate_messages(self, game, power_name):
        """Generate diplomatic messages for Talk phases.

        :param game: Current game state.
        :param power_name: Power to generate messages for.
        :return: List of (recipient, body) tuples.
        :rtype: list[tuple[str, str]]
        """
        msg_text = format_message_prompt(game, power_name)
        system_prompt = self._build_message_prompt(power_name)

        try:
            response = self._provider.complete(system_prompt, msg_text)
        except Exception as exc:
            LOGGER.warning('LLM message call failed for %s: %s', power_name, exc)
            return []

        return parse_messages(response, list(game.get_map_power_names()))

    def _build_order_prompt(self, power_name):
        """Build the system prompt for order generation."""
        base = (
            'You are playing Diplomacy as %s. '
            'Analyze the board state and choose your orders carefully.\n\n'
            'IMPORTANT: Respond with a list of orders, one per line. '
            'Each order must be copied exactly from the "Your Possible Orders" section. '
            'Do not include any other text.'
        ) % power_name
        if self._agent_def.instructions:
            return self._agent_def.instructions + '\n\n' + base
        return base

    def _build_message_prompt(self, power_name):
        """Build the system prompt for message generation."""
        base = (
            'You are playing Diplomacy as %s during a negotiation round. '
            'You may send diplomatic messages to other powers.\n\n'
            'IMPORTANT: Respond with messages in this format, one per line:\n'
            'RECIPIENT: message body\n\n'
            'Where RECIPIENT is a power name (e.g. ENGLAND, FRANCE) or GLOBAL.\n'
            'You may send zero or more messages. Only include message lines, no other text.'
        ) % power_name
        if self._agent_def.instructions:
            return self._agent_def.instructions + '\n\n' + base
        return base

    def _fallback_orders(self, game, power_name):
        """Generate random valid orders (same logic as DumbBot)."""
        orderable_locs = game.get_orderable_locations(power_name)
        possible_orders = game.get_all_possible_orders()
        orders = []
        for loc in orderable_locs:
            loc_orders = possible_orders.get(loc, [])
            if loc_orders:
                orders.append(self._fallback_rng.choice(list(loc_orders)))
        return orders

    def _fill_missing(self, orders, possible_orders, orderable_locs):
        """Fill missing locations with random valid orders."""
        # Determine which locations are already covered
        covered_locs = set()
        for order in orders:
            for loc in orderable_locs:
                if order in possible_orders.get(loc, set()):
                    covered_locs.add(loc)
                    break

        # Fill gaps
        for loc in orderable_locs:
            if loc not in covered_locs:
                loc_orders = possible_orders.get(loc, [])
                if loc_orders:
                    orders.append(self._fallback_rng.choice(list(loc_orders)))

        return orders
