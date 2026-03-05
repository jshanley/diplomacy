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
"""DumbBot -- an agent that picks random legal orders every turn."""
import random as _random

from diplomacy.agents.agent_def import AgentDef
from diplomacy.agents.base_agent import BaseAgent


class DumbBot(BaseAgent):
    """Agent that selects uniformly random legal orders for every orderable location.

    This is the simplest possible agent. It exists to prove the agent pipeline
    works end-to-end with both local Game and NetworkGame.
    """

    def __init__(self, seed=None):
        """Initialize DumbBot.

        :param seed: Optional RNG seed for reproducibility.
        :type seed: int or None
        """
        self._rng = _random.Random(seed)
        self._agent_def = AgentDef(
            creator='diplomacy-framework',
            model_id='random',
            description='Picks uniformly random legal orders each turn.',
        )

    @property
    def agent_def(self):
        return self._agent_def

    def generate_orders(self, game, power_name):
        """Pick one random legal order per orderable location.

        :param game: Current game state.
        :param power_name: Power to generate orders for.
        :return: List of order strings.
        """
        orderable_locs = game.get_orderable_locations(power_name)
        possible_orders = game.get_all_possible_orders()
        orders = []
        for loc in orderable_locs:
            loc_orders = possible_orders.get(loc, [])
            if loc_orders:
                orders.append(self._rng.choice(list(loc_orders)))
        return orders
