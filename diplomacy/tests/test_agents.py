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
"""Tests for the agent framework (Track B: tasks 2.1, 2.2, 2.4)."""
from diplomacy.engine.game import Game
from diplomacy.agents.agent_def import AgentDef
from diplomacy.agents.base_agent import BaseAgent
from diplomacy.agents.dumb_bot import DumbBot
from diplomacy.agents.harness import run_local_game, run_network_game, GameResult


# =========================================================================
# 2.2 -- AgentDef tests
# =========================================================================

def test_agent_def_creation():
    """AgentDef can be created with required fields."""
    ad = AgentDef(creator='test', model_id='random')
    assert ad.creator == 'test'
    assert ad.model_id == 'random'
    assert ad.instructions == ''
    assert ad.metadata == {}
    assert ad.version == '0.1.0'
    assert ad.description == ''

def test_agent_def_full_creation():
    """AgentDef accepts all optional fields."""
    ad = AgentDef(creator='team-x', model_id='gpt-4',
                  instructions='You are a diplomat.',
                  description='GPT-4 agent',
                  version='1.0.0',
                  metadata={'temp': 0.7})
    assert ad.creator == 'team-x'
    assert ad.model_id == 'gpt-4'
    assert ad.instructions == 'You are a diplomat.'
    assert ad.description == 'GPT-4 agent'
    assert ad.version == '1.0.0'
    assert ad.metadata == {'temp': 0.7}

def test_agent_def_to_dict():
    """AgentDef.to_dict() produces a complete dictionary."""
    ad = AgentDef(creator='team-x', model_id='gpt-4',
                  instructions='You are a diplomat.', metadata={'temp': 0.7})
    d = ad.to_dict()
    assert d['creator'] == 'team-x'
    assert d['model_id'] == 'gpt-4'
    assert d['instructions'] == 'You are a diplomat.'
    assert d['metadata'] == {'temp': 0.7}
    assert d['version'] == '0.1.0'
    assert d['description'] == ''

def test_agent_def_repr():
    """AgentDef has a useful repr."""
    ad = AgentDef(creator='test', model_id='random')
    r = repr(ad)
    assert 'random' in r
    assert 'test' in r

def test_agent_def_metadata_isolation():
    """Two AgentDefs don't share the same metadata dict."""
    ad1 = AgentDef(creator='a', model_id='x')
    ad2 = AgentDef(creator='b', model_id='y')
    ad1.metadata['key'] = 'value'
    assert 'key' not in ad2.metadata


# =========================================================================
# 2.1 -- DumbBot tests
# =========================================================================

def test_dumb_bot_is_base_agent():
    """DumbBot is a subclass of BaseAgent."""
    bot = DumbBot()
    assert isinstance(bot, BaseAgent)

def test_dumb_bot_has_agent_def():
    """DumbBot provides a valid AgentDef."""
    bot = DumbBot()
    assert isinstance(bot.agent_def, AgentDef)
    assert bot.agent_def.model_id == 'random'
    assert bot.agent_def.creator == 'diplomacy-framework'

def test_dumb_bot_generates_valid_orders():
    """DumbBot produces orders that are legal for the given game state."""
    game = Game()
    bot = DumbBot(seed=42)
    possible = game.get_all_possible_orders()
    for power_name in game.get_map_power_names():
        orders = bot.generate_orders(game, power_name)
        for order in orders:
            found = any(order in loc_orders for loc_orders in possible.values())
            assert found, "Order %r not found in possible orders" % order

def test_dumb_bot_all_orderable_locations():
    """DumbBot generates one order per orderable location that has options."""
    game = Game()
    bot = DumbBot(seed=42)
    possible = game.get_all_possible_orders()
    for power_name in game.get_map_power_names():
        orders = bot.generate_orders(game, power_name)
        orderable_locs = game.get_orderable_locations(power_name)
        expected_count = sum(1 for loc in orderable_locs if possible.get(loc))
        assert len(orders) == expected_count

def test_dumb_bot_deterministic_with_seed():
    """Two DumbBots with the same seed produce the same orders."""
    game = Game()
    bot1 = DumbBot(seed=123)
    bot2 = DumbBot(seed=123)
    for power_name in sorted(game.get_map_power_names()):
        assert bot1.generate_orders(game, power_name) == bot2.generate_orders(game, power_name)

def test_dumb_bot_different_seeds_differ():
    """Two DumbBots with different seeds likely produce different orders."""
    game = Game()
    bot1 = DumbBot(seed=1)
    bot2 = DumbBot(seed=2)
    any_different = False
    for power_name in game.get_map_power_names():
        if bot1.generate_orders(game, power_name) != bot2.generate_orders(game, power_name):
            any_different = True
            break
    assert any_different

def test_dumb_bot_handles_eliminated_power():
    """DumbBot returns empty list for a power with no orderable locations."""
    game = Game()
    game.clear_units('AUSTRIA')
    game.clear_centers('AUSTRIA')
    bot = DumbBot(seed=42)
    orders = bot.generate_orders(game, 'AUSTRIA')
    assert orders == []

def test_dumb_bot_survives_full_phase():
    """DumbBot orders for all 7 powers can be processed without errors."""
    game = Game()
    bot = DumbBot(seed=42)
    for power_name in game.get_map_power_names():
        orders = bot.generate_orders(game, power_name)
        game.set_orders(power_name, orders)
    game.process()
    assert not game.is_game_done
    assert game.get_current_phase() != 'S1901M'


# =========================================================================
# 2.4 -- Local harness tests
# =========================================================================

def test_local_game_completes():
    """run_local_game with a single DumbBot runs to completion."""
    bot = DumbBot(seed=42)
    result = run_local_game(bot)
    assert isinstance(result, GameResult)
    assert result.is_done
    assert result.phases_played > 0
    assert len(result.phase_history) > 0

def test_local_game_seven_agents():
    """run_local_game with 7 distinct DumbBots runs to completion."""
    bots = [DumbBot(seed=i) for i in range(7)]
    result = run_local_game(bots)
    assert result.is_done
    assert result.phases_played > 0

def test_local_game_dict_agents():
    """run_local_game accepts a dict of {power_name: agent}."""
    game = Game()
    power_names = sorted(game.get_map_power_names())
    agents = {pn: DumbBot(seed=hash(pn)) for pn in power_names}
    result = run_local_game(agents)
    assert result.is_done

def test_local_game_result_has_centers():
    """GameResult contains final supply center counts."""
    bot = DumbBot(seed=42)
    result = run_local_game(bot)
    assert isinstance(result.final_centers, dict)
    assert len(result.final_centers) == 7
    total_centers = sum(len(c) for c in result.final_centers.values())
    assert total_centers > 0

def test_local_game_result_has_agent_metadata():
    """GameResult records which agent played each power."""
    bot = DumbBot(seed=42)
    result = run_local_game(bot)
    assert len(result.agents) == 7
    for power_name, agent_dict in result.agents.items():
        assert agent_dict['model_id'] == 'random'
        assert agent_dict['creator'] == 'diplomacy-framework'

def test_local_game_max_phases_limit():
    """run_local_game respects max_phases safety limit."""
    bot = DumbBot(seed=42)
    result = run_local_game(bot, max_phases=5)
    assert result.phases_played <= 5

def test_local_game_no_crashes_10_runs():
    """Run 10 local games with different seeds -- no crashes."""
    for seed in range(10):
        bot = DumbBot(seed=seed)
        result = run_local_game(bot)
        assert result.is_done
        assert result.phases_played > 0

def test_local_game_has_winner_or_draw():
    """Game result either has a winner or all powers have been processed."""
    bot = DumbBot(seed=42)
    result = run_local_game(bot)
    assert result.is_done
    # Winner can be None (draw after 100 years) or a power name.
    if result.winner:
        assert result.winner in result.final_centers


# =========================================================================
# 2.4 -- Network harness tests
# =========================================================================

def test_network_game_completes():
    """run_network_game with 7 DumbBots runs a game over the network."""
    bot = DumbBot(seed=42)
    result = run_network_game(bot)
    assert isinstance(result, GameResult)
    assert result.is_done
    assert result.phases_played > 0

def test_network_game_result_has_data():
    """Network game result has centers and agent metadata."""
    bot = DumbBot(seed=42)
    result = run_network_game(bot)
    assert len(result.final_centers) == 7
    assert len(result.agents) == 7
    total_centers = sum(len(c) for c in result.final_centers.values())
    assert total_centers > 0
