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
"""Tests for LLM agent framework (Track B: tasks 2.3, 2.5)."""
from diplomacy.engine.game import Game
from diplomacy.agents.agent_def import AgentDef
from diplomacy.agents.base_agent import BaseAgent
from diplomacy.agents.dumb_bot import DumbBot
from diplomacy.agents.llm_provider import (LLMProvider, OpenAIProvider, AnthropicProvider,
                                           GrokProvider, StubProvider)
from diplomacy.agents.state_formatter import format_game_state, format_message_prompt
from diplomacy.agents.order_parser import parse_orders, parse_messages
from diplomacy.agents.llm_agent import LLMAgent
from diplomacy.agents.harness import run_local_game


# =========================================================================
# Provider tests
# =========================================================================

def test_stub_provider_returns_canned_responses():
    """StubProvider returns responses in order, then empty string."""
    stub = StubProvider(['first', 'second'])
    assert stub.complete('sys', 'msg') == 'first'
    assert stub.complete('sys', 'msg') == 'second'
    assert stub.complete('sys', 'msg') == ''

def test_stub_provider_tracks_calls():
    """StubProvider tracks call count and last arguments."""
    stub = StubProvider(['ok'])
    stub.complete('my system', 'my user')
    assert stub.call_count == 1
    assert stub.last_system_prompt == 'my system'
    assert stub.last_user_message == 'my user'

def test_stub_provider_callable():
    """StubProvider accepts a callable for dynamic responses."""
    stub = StubProvider(lambda s, u: 'echo: ' + u)
    assert stub.complete('sys', 'hello') == 'echo: hello'
    assert stub.complete('sys', 'world') == 'echo: world'

def test_stub_provider_model_property():
    """StubProvider has model='stub'."""
    stub = StubProvider()
    assert stub.model == 'stub'

def test_grok_provider_is_openai_subclass():
    """GrokProvider inherits from OpenAIProvider."""
    assert issubclass(GrokProvider, OpenAIProvider)

def test_llm_provider_is_abstract():
    """LLMProvider cannot be instantiated directly."""
    try:
        LLMProvider()
        assert False, 'Should have raised TypeError'
    except TypeError:
        pass


# =========================================================================
# State formatter tests
# =========================================================================

def test_format_game_state_has_phase():
    """Formatted state includes the current phase."""
    game = Game()
    text = format_game_state(game, 'FRANCE')
    assert 'S1901M' in text

def test_format_game_state_has_power_name():
    """Formatted state identifies the agent's power."""
    game = Game()
    text = format_game_state(game, 'FRANCE')
    assert 'You are: FRANCE' in text

def test_format_game_state_has_power_units():
    """Formatted state shows units for all powers."""
    game = Game()
    text = format_game_state(game, 'FRANCE')
    assert 'A PAR' in text
    assert 'A VIE' in text  # Austria's unit

def test_format_game_state_has_possible_orders():
    """Formatted state lists possible orders for the agent's locations."""
    game = Game()
    text = format_game_state(game, 'FRANCE')
    assert 'Your Possible Orders' in text
    assert 'A PAR' in text

def test_format_game_state_marks_your_power():
    """Formatted state marks the agent's power with (YOU)."""
    game = Game()
    text = format_game_state(game, 'FRANCE')
    assert 'FRANCE (YOU)' in text
    # Other powers should NOT have (YOU)
    assert 'ENGLAND (YOU)' not in text

def test_format_game_state_all_powers_present():
    """Formatted state includes all 7 powers."""
    game = Game()
    text = format_game_state(game, 'FRANCE')
    for pn in game.get_map_power_names():
        assert pn in text

def test_format_message_prompt_has_recipients():
    """Message prompt lists other powers as potential recipients."""
    game = Game()
    text = format_message_prompt(game, 'FRANCE')
    assert 'ENGLAND' in text
    assert 'GLOBAL' in text
    assert 'Talk Phase' in text


# =========================================================================
# Order parser tests
# =========================================================================

def _get_france_orders_context():
    """Helper: return possible_orders and orderable_locs for France in S1901M."""
    game = Game()
    possible = game.get_all_possible_orders()
    orderable = game.get_orderable_locations('FRANCE')
    return possible, orderable

def test_parse_exact_orders():
    """Parser finds exact order matches."""
    possible, orderable = _get_france_orders_context()
    # Pick one valid order per location
    valid_lines = []
    for loc in orderable:
        loc_orders = possible.get(loc, [])
        if loc_orders:
            valid_lines.append(sorted(loc_orders)[0])
    response = '\n'.join(valid_lines)
    orders = parse_orders(response, possible, orderable)
    assert len(orders) == len(valid_lines)

def test_parse_orders_strips_bullets():
    """Parser strips bullet markers (-)."""
    possible, orderable = _get_france_orders_context()
    # Get a valid order for PAR
    par_order = sorted(possible.get('PAR', []))[0]
    response = '- %s' % par_order
    orders = parse_orders(response, possible, orderable)
    assert par_order in orders

def test_parse_orders_strips_numbering():
    """Parser strips numbered list prefixes."""
    possible, orderable = _get_france_orders_context()
    par_order = sorted(possible.get('PAR', []))[0]
    response = '1. %s' % par_order
    orders = parse_orders(response, possible, orderable)
    assert par_order in orders

def test_parse_orders_strips_backticks():
    """Parser strips backtick formatting."""
    possible, orderable = _get_france_orders_context()
    par_order = sorted(possible.get('PAR', []))[0]
    response = '`%s`' % par_order
    orders = parse_orders(response, possible, orderable)
    assert par_order in orders

def test_parse_orders_ignores_invalid():
    """Parser ignores lines that aren't valid orders."""
    possible, orderable = _get_france_orders_context()
    response = 'This is not an order\nNeither is this\nA PAR - MARS'
    orders = parse_orders(response, possible, orderable)
    assert len(orders) == 0

def test_parse_orders_one_per_location():
    """Parser returns at most one order per location."""
    possible, orderable = _get_france_orders_context()
    par_orders = sorted(possible.get('PAR', []))
    if len(par_orders) >= 2:
        response = '%s\n%s' % (par_orders[0], par_orders[1])
        orders = parse_orders(response, possible, orderable)
        par_count = sum(1 for o in orders if o in par_orders)
        assert par_count == 1

def test_parse_messages_basic():
    """Parser extracts RECIPIENT: body format messages."""
    power_names = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']
    response = 'ENGLAND: Let us ally against Germany.\nGLOBAL: I propose peace.'
    messages = parse_messages(response, power_names)
    assert len(messages) == 2
    assert messages[0] == ('ENGLAND', 'Let us ally against Germany.')
    assert messages[1] == ('GLOBAL', 'I propose peace.')

def test_parse_messages_ignores_invalid_recipient():
    """Parser ignores messages to non-existent powers."""
    power_names = ['AUSTRIA', 'ENGLAND', 'FRANCE']
    response = 'NARNIA: Hello there.'
    messages = parse_messages(response, power_names)
    assert len(messages) == 0

def test_parse_messages_arrow_format():
    """Parser handles arrow format (RECIPIENT -> body)."""
    power_names = ['AUSTRIA', 'ENGLAND', 'FRANCE']
    response = 'ENGLAND -> We should coordinate.'
    messages = parse_messages(response, power_names)
    assert len(messages) == 1
    assert messages[0][0] == 'ENGLAND'


# =========================================================================
# LLMAgent tests
# =========================================================================

def _make_order_stub(game, power_name):
    """Create a StubProvider that returns valid orders for a power."""
    possible = game.get_all_possible_orders()
    orderable = game.get_orderable_locations(power_name)
    valid_orders = []
    for loc in orderable:
        loc_orders = possible.get(loc, [])
        if loc_orders:
            valid_orders.append(sorted(loc_orders)[0])

    def respond(system, user):
        return '\n'.join(valid_orders)
    return StubProvider(respond)

def test_llm_agent_is_base_agent():
    """LLMAgent is a subclass of BaseAgent."""
    agent = LLMAgent(StubProvider())
    assert isinstance(agent, BaseAgent)

def test_llm_agent_has_agent_def():
    """LLMAgent provides a valid AgentDef."""
    agent = LLMAgent(StubProvider(), creator='test-team')
    assert isinstance(agent.agent_def, AgentDef)
    assert agent.agent_def.model_id == 'stub'
    assert agent.agent_def.creator == 'test-team'

def test_llm_agent_generates_valid_orders():
    """LLMAgent generates valid orders when stub returns valid order text."""
    game = Game()
    stub = _make_order_stub(game, 'FRANCE')
    agent = LLMAgent(stub, fallback_seed=42)
    possible = game.get_all_possible_orders()

    orders = agent.generate_orders(game, 'FRANCE')
    assert len(orders) > 0
    for order in orders:
        found = any(order in loc_orders for loc_orders in possible.values())
        assert found, 'Order %r not valid' % order

def test_llm_agent_fallback_on_error():
    """LLMAgent falls back to random orders when LLM raises an exception."""
    def raise_error(system, user):
        raise RuntimeError('API down')

    game = Game()
    agent = LLMAgent(StubProvider(raise_error), fallback_seed=42)
    orders = agent.generate_orders(game, 'FRANCE')

    # Should still produce valid orders via fallback
    possible = game.get_all_possible_orders()
    assert len(orders) > 0
    for order in orders:
        found = any(order in loc_orders for loc_orders in possible.values())
        assert found, 'Fallback order %r not valid' % order

def test_llm_agent_fallback_on_bad_parse():
    """LLMAgent fills with random orders when LLM returns garbage."""
    game = Game()
    stub = StubProvider(['This is total nonsense with no valid orders at all.'])
    agent = LLMAgent(stub, fallback_seed=42)
    orders = agent.generate_orders(game, 'FRANCE')

    # Should still produce valid orders (all filled by fallback)
    possible = game.get_all_possible_orders()
    orderable = game.get_orderable_locations('FRANCE')
    expected_count = sum(1 for loc in orderable if possible.get(loc))
    assert len(orders) == expected_count

def test_llm_agent_fills_missing_locations():
    """LLMAgent fills missing locations when LLM returns partial orders."""
    game = Game()
    possible = game.get_all_possible_orders()
    orderable = game.get_orderable_locations('FRANCE')

    # Return only one valid order (for PAR), leaving others empty
    par_order = sorted(possible.get('PAR', []))[0]
    stub = StubProvider([par_order])
    agent = LLMAgent(stub, fallback_seed=42)
    orders = agent.generate_orders(game, 'FRANCE')

    # All orderable locations should have orders
    expected_count = sum(1 for loc in orderable if possible.get(loc))
    assert len(orders) == expected_count
    assert par_order in orders

def test_llm_agent_custom_instructions():
    """LLMAgent passes custom instructions to the LLM."""
    stub = StubProvider([''])
    agent = LLMAgent(stub, instructions='Be aggressive and expand quickly.')
    game = Game()
    agent.generate_orders(game, 'FRANCE')
    assert 'Be aggressive' in stub.last_system_prompt

def test_llm_agent_generate_messages():
    """LLMAgent generates diplomatic messages from LLM response."""
    stub = StubProvider(['ENGLAND: Let us form an alliance.\nGLOBAL: Peace to all.'])
    agent = LLMAgent(stub)
    game = Game()
    messages = agent.generate_messages(game, 'FRANCE')
    assert len(messages) == 2
    assert messages[0] == ('ENGLAND', 'Let us form an alliance.')
    assert messages[1] == ('GLOBAL', 'Peace to all.')

def test_llm_agent_generate_messages_on_error():
    """LLMAgent returns empty messages when LLM fails."""
    def raise_error(system, user):
        raise RuntimeError('API down')
    agent = LLMAgent(StubProvider(raise_error))
    game = Game()
    messages = agent.generate_messages(game, 'FRANCE')
    assert messages == []

def test_llm_agent_survives_full_local_game():
    """LLMAgent with stub can run a full local game to completion."""
    def respond(system, user):
        # Parse possible orders from the state text and return the first one per location
        lines = user.split('\n')
        orders = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('- ') and (' H' in stripped or ' - ' in stripped or ' S ' in stripped):
                # This looks like a possible order line
                order = stripped[2:]
                orders.append(order)
        # Return first order we found (partial is fine — agent will fill the rest)
        return '\n'.join(orders[:1]) if orders else ''

    stub = StubProvider(respond)
    agent = LLMAgent(stub, fallback_seed=42)
    result = run_local_game(agent)
    assert result.is_done
    assert result.phases_played > 0

def test_llm_agent_mixed_with_dumbbot():
    """LLMAgent can play alongside DumbBots in a local game."""
    game = Game()
    power_names = sorted(game.get_map_power_names())
    agents = {}
    for i, pn in enumerate(power_names):
        if i == 0:
            stub = StubProvider(lambda s, u: '')  # Always fallback
            agents[pn] = LLMAgent(stub, fallback_seed=42)
        else:
            agents[pn] = DumbBot(seed=i)
    result = run_local_game(agents)
    assert result.is_done
    assert result.phases_played > 0
    # Verify agent metadata
    assert result.agents[power_names[0]]['model_id'] == 'stub'
    assert result.agents[power_names[1]]['model_id'] == 'random'

def test_llm_agent_local_game_10_phases():
    """LLMAgent with stub survives 10 phases (smoke test)."""
    stub = StubProvider(lambda s, u: '')  # Always fallback to random
    agent = LLMAgent(stub, fallback_seed=42)
    result = run_local_game(agent, max_phases=10)
    assert result.phases_played <= 10
    assert result.phases_played > 0
    assert len(result.final_centers) == 7

def test_base_agent_generate_messages_default():
    """BaseAgent.generate_messages returns empty list by default."""
    bot = DumbBot(seed=42)
    game = Game()
    messages = bot.generate_messages(game, 'FRANCE')
    assert messages == []
