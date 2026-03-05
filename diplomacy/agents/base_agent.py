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
"""Abstract base class for all Diplomacy agents."""
from abc import ABCMeta, abstractmethod


class BaseAgent(metaclass=ABCMeta):
    """Abstract base for agents that play Diplomacy.

    An agent receives the game state and a power name, and returns orders.
    This interface is deliberately minimal -- it works with both the local
    Game (synchronous) and NetworkGame (async) via the harness layer.

    Subclasses must implement:
        - agent_def (property returning AgentDef)
        - generate_orders(game, power_name) -> List[str]
    """

    @property
    @abstractmethod
    def agent_def(self):
        """Return the AgentDef metadata for this agent.

        :rtype: AgentDef
        """

    @abstractmethod
    def generate_orders(self, game, power_name):
        """Given the current game state, return a list of order strings.

        :param game: A diplomacy.engine.game.Game object (current state).
        :param power_name: The power this agent is playing (e.g. 'FRANCE').
        :type game: diplomacy.engine.game.Game
        :type power_name: str
        :return: A list of order strings (e.g. ['A PAR - MAR', 'F BRE - MAO']).
        :rtype: list[str]
        """

    def on_game_start(self, game, power_name):
        """Optional hook called when the game begins. Override if needed."""

    def on_phase_end(self, game, power_name):
        """Optional hook called after each phase resolves. Override if needed."""

    def generate_messages(self, game, power_name):
        """Optional: generate diplomatic messages for Talk phases.

        Override to send messages during negotiation rounds. The default
        implementation sends no messages.

        :param game: Current game state.
        :param power_name: The power this agent is playing.
        :type game: diplomacy.engine.game.Game
        :type power_name: str
        :return: A list of (recipient, body) tuples.
        :rtype: list[tuple[str, str]]
        """
        return []
