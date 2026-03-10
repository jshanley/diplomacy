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
"""Diplomacy agent framework -- bots that play the game."""
from diplomacy.agents.agent_def import AgentDef
from diplomacy.agents.base_agent import BaseAgent
from diplomacy.agents.dumb_bot import DumbBot
from diplomacy.agents.harness import run_local_game, run_network_game, GameResult
from diplomacy.agents.llm_provider import (LLMProvider, OpenAIProvider, AnthropicProvider,
                                           GoogleProvider, GrokProvider, StubProvider)
from diplomacy.agents.state_formatter import format_game_state, format_message_prompt
from diplomacy.agents.order_parser import parse_orders, parse_messages
from diplomacy.agents.llm_agent import LLMAgent
