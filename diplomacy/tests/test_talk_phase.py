# ==============================================================================
# Tests for the Talk phase engine integration.
# Validates that Talk phases appear in the sequence, are skipped when NO_TALK
# is set, and process correctly when enabled.
# ==============================================================================
from copy import deepcopy
from diplomacy.engine.game import Game
from diplomacy.engine.map import Map
from diplomacy.engine.message import Message
from diplomacy.server.server_game import ServerGame
from diplomacy.utils import strings
from diplomacy.utils.order_results import BOUNCE


def _game_with_talk(**kwargs):
    """ Helper: create a game with Talk phases enabled """
    rules = kwargs.pop('rules', ['SOLITAIRE', 'NO_PRESS', 'IGNORE_ERRORS', 'POWER_CHOICE'])
    return Game(rules=rules, **kwargs)


def _game_default(**kwargs):
    """ Helper: create a default game (NO_TALK active) """
    return Game(**kwargs)


# ===========================================================================
# MAP-LEVEL TESTS
# ===========================================================================

def test_talk_in_phase_sequence():
    """ Talk phases appear in the map sequence """
    this_map = deepcopy(Map())
    assert 'SPRING TALK' in this_map.seq
    assert 'FALL TALK' in this_map.seq

def test_talk_not_in_winter():
    """ No Talk phase before Winter Adjustments """
    this_map = deepcopy(Map())
    assert 'WINTER TALK' not in this_map.seq

def test_talk_phase_abbrev():
    """ T maps to TALK in phase_abbrev """
    this_map = deepcopy(Map())
    assert this_map.phase_abbrev['T'] == 'TALK'

def test_talk_phase_abbreviation():
    """ SPRING 1901 TALK abbreviates to S1901T """
    this_map = deepcopy(Map())
    assert this_map.phase_abbr('SPRING 1901 TALK') == 'S1901T'
    assert this_map.phase_abbr('FALL 1901 TALK') == 'F1901T'
    assert this_map.phase_abbr('SPRING 1905 TALK') == 'S1905T'
    assert this_map.phase_abbr('FALL 2000 TALK') == 'F2000T'

def test_talk_phase_long():
    """ S1901T expands to SPRING 1901 TALK """
    this_map = deepcopy(Map())
    assert this_map.phase_long('S1901T') == 'SPRING 1901 TALK'
    assert this_map.phase_long('F1901T') == 'FALL 1901 TALK'
    assert this_map.phase_long('S1950T') == 'SPRING 1950 TALK'

def test_talk_phase_abbreviation_case_insensitive():
    """ Phase abbreviation is case insensitive """
    this_map = deepcopy(Map())
    assert this_map.phase_abbr('spring 1901 talk') == 'S1901T'
    assert this_map.phase_long('s1901t') == 'SPRING 1901 TALK'

def test_talk_phase_ordering_in_seq():
    """ Talk phases come before their Movement phases in sequence """
    this_map = deepcopy(Map())
    seq = this_map.seq
    spring_talk_ix = seq.index('SPRING TALK')
    spring_move_ix = seq.index('SPRING MOVEMENT')
    fall_talk_ix = seq.index('FALL TALK')
    fall_move_ix = seq.index('FALL MOVEMENT')
    assert spring_talk_ix < spring_move_ix
    assert fall_talk_ix < fall_move_ix
    # Talk comes right before Movement (adjacent)
    assert spring_move_ix - spring_talk_ix == 1
    assert fall_move_ix - fall_talk_ix == 1

def test_talk_phase_comparison_same_season():
    """ Talk < Movement < Retreats within the same season """
    this_map = deepcopy(Map())
    assert this_map.compare_phases('S1901T', 'S1901M') == -1
    assert this_map.compare_phases('S1901M', 'S1901T') == 1
    assert this_map.compare_phases('S1901T', 'S1901R') == -1
    assert this_map.compare_phases('F1901T', 'F1901M') == -1
    assert this_map.compare_phases('F1901T', 'F1901R') == -1

def test_talk_phase_comparison_cross_season():
    """ Talk respects cross-season ordering """
    this_map = deepcopy(Map())
    # Fall Talk comes after Spring Retreats
    assert this_map.compare_phases('F1901T', 'S1901R') == 1
    # Spring Talk comes after previous Winter
    assert this_map.compare_phases('S1902T', 'W1901A') == 1
    # Fall Talk comes before Winter of same year
    assert this_map.compare_phases('F1901T', 'W1901A') == -1

def test_talk_phase_comparison_cross_year():
    """ Talk phases compare correctly across years """
    this_map = deepcopy(Map())
    assert this_map.compare_phases('S1902T', 'F1901T') == 1
    assert this_map.compare_phases('S1901T', 'S1902T') == -1
    assert this_map.compare_phases('F1901T', 'S1902T') == -1

def test_talk_phase_comparison_same():
    """ Same Talk phase compares equal """
    this_map = deepcopy(Map())
    assert this_map.compare_phases('S1901T', 'S1901T') == 0
    assert this_map.compare_phases('F1901T', 'F1901T') == 0

def test_find_next_phase_from_talk():
    """ Next phase after Talk is Movement """
    this_map = deepcopy(Map())
    assert this_map.find_next_phase('SPRING 1901 TALK') == 'SPRING 1901 MOVEMENT'
    assert this_map.find_next_phase('FALL 1901 TALK') == 'FALL 1901 MOVEMENT'

def test_find_next_phase_to_talk():
    """ Talk is reachable as next phase from prior phases """
    this_map = deepcopy(Map())
    # After Winter Adjustments, next is Spring Talk
    assert this_map.find_next_phase('WINTER 1901 ADJUSTMENTS') == 'SPRING 1902 TALK'
    # After Spring Retreats, next is Fall Talk
    assert this_map.find_next_phase('SPRING 1901 RETREATS') == 'FALL 1901 TALK'

def test_find_next_phase_with_type_filter():
    """ Phase type filter works with Talk """
    this_map = deepcopy(Map())
    # From Fall Retreats, next Talk is Spring
    assert this_map.find_next_phase('FALL 1901 RETREATS', phase_type='T') == 'SPRING 1902 TALK'
    # From Spring Talk, next Talk is Fall
    assert this_map.find_next_phase('SPRING 1901 TALK', phase_type='T') == 'FALL 1901 TALK'
    # Skipping Talk: next Movement from Winter
    assert this_map.find_next_phase('WINTER 1901 ADJUSTMENTS', phase_type='M') == 'SPRING 1902 MOVEMENT'

def test_find_previous_phase_from_movement():
    """ Previous phase before Movement is Talk """
    this_map = deepcopy(Map())
    assert this_map.find_previous_phase('SPRING 1901 MOVEMENT') == 'SPRING 1901 TALK'
    assert this_map.find_previous_phase('FALL 1901 MOVEMENT') == 'FALL 1901 TALK'

def test_find_previous_phase_from_talk():
    """ Previous phase before Talk is the prior season's last phase """
    this_map = deepcopy(Map())
    # Before Spring Talk is NEWYEAR (wraps to Winter Adjustments)
    assert this_map.find_previous_phase('SPRING 1902 TALK') == 'WINTER 1901 ADJUSTMENTS'
    # Before Fall Talk is Spring Retreats
    assert this_map.find_previous_phase('FALL 1901 TALK') == 'SPRING 1901 RETREATS'

def test_find_previous_phase_with_type_filter():
    """ Phase type filter works for previous Talk """
    this_map = deepcopy(Map())
    assert this_map.find_previous_phase('SPRING 1902 MOVEMENT', phase_type='T') == 'SPRING 1902 TALK'
    assert this_map.find_previous_phase('FALL 1901 MOVEMENT', phase_type='T') == 'FALL 1901 TALK'

def test_full_sequence_order():
    """ Complete phase sequence for one year """
    this_map = deepcopy(Map())
    expected = [
        'SPRING 1901 TALK',
        'SPRING 1901 MOVEMENT',
        'SPRING 1901 RETREATS',
        'FALL 1901 TALK',
        'FALL 1901 MOVEMENT',
        'FALL 1901 RETREATS',
        'WINTER 1901 ADJUSTMENTS',
        'SPRING 1902 TALK',
    ]
    phase = 'SPRING 1901 TALK'
    for expected_phase in expected[1:]:
        phase = this_map.find_next_phase(phase)
        assert phase == expected_phase, f'Expected {expected_phase}, got {phase}'


# ===========================================================================
# GAME-LEVEL TESTS: NO_TALK (DEFAULT BEHAVIOR)
# ===========================================================================

def test_default_game_skips_talk():
    """ Default game (NO_TALK) starts at S1901M, not S1901T """
    game = _game_default()
    assert game.get_current_phase() == 'S1901M'
    assert game.phase_type == 'M'

def test_no_talk_in_default_rules():
    """ NO_TALK is in the rules for a default game """
    game = _game_default()
    assert 'NO_TALK' in game.rules

def test_default_game_advances_past_talk():
    """ Default game advances S1901M -> F1901M (Talk and Retreats skipped) """
    game = _game_default()
    game.process()
    assert game.get_current_phase() == 'F1901M'

def test_default_game_full_year():
    """ Default game plays a full year without seeing Talk """
    game = _game_default()
    game.process()  # S1901M -> F1901M
    assert game.get_current_phase() == 'F1901M'
    game.process()  # F1901M -> S1902M
    assert game.get_current_phase() == 'S1902M'

def test_default_game_no_talk_in_history():
    """ Default game history never contains Talk phases """
    game = _game_default()
    for _ in range(6):  # play 3 years
        game.process()
    for key in game.state_history.keys():
        assert str(key)[-1] != 'T', f'Talk phase {key} found in history with NO_TALK'

def test_default_game_multi_year():
    """ Default game advances correctly over multiple years """
    game = _game_default()
    for year in range(1, 5):
        game.process()  # Spring -> Fall
        game.process()  # Fall -> next Spring
        expected_year = game.map.first_year + year
        assert int(game.get_current_phase()[1:5]) == expected_year


# ===========================================================================
# GAME-LEVEL TESTS: TALK ENABLED
# ===========================================================================

def test_talk_enabled_starts_at_talk():
    """ Game without NO_TALK starts at S1901T """
    game = _game_with_talk()
    assert game.get_current_phase() == 'S1901T'
    assert game.phase_type == 'T'

def test_talk_enabled_no_notalk_in_rules():
    """ Talk-enabled game does not have NO_TALK in rules """
    game = _game_with_talk()
    assert 'NO_TALK' not in game.rules

def test_talk_process_advances_to_movement():
    """ Processing a Talk phase advances to Movement """
    game = _game_with_talk()
    game.process()
    assert game.get_current_phase() == 'S1901M'
    assert game.phase_type == 'M'

def test_talk_full_sequence_one_year():
    """ Full year with Talk: T -> M -> T -> M -> T (next year) """
    game = _game_with_talk()
    expected = ['S1901T', 'S1901M', 'F1901T', 'F1901M', 'S1902T']
    phases = [game.get_current_phase()]
    for _ in range(4):
        game.process()
        phases.append(game.get_current_phase())
    assert phases == expected

def test_talk_full_sequence_with_retreats():
    """ When retreats exist, sequence is T -> M -> R -> T """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M

    # Set up a situation that creates a retreat
    game.clear_units()
    game.set_units('FRANCE', ['A BUR'])
    game.set_units('GERMANY', ['A MUN', 'A RUH'])
    game.set_orders('FRANCE', ['A BUR H'])
    game.set_orders('GERMANY', ['A MUN - BUR', 'A RUH S A MUN - BUR'])
    game.process()  # S1901M -> S1901R (France dislodged from BUR)
    assert game.get_current_phase() == 'S1901R'
    assert game.phase_type == 'R'

    # Process retreats
    france = game.get_power('FRANCE')
    assert len(france.retreats) > 0
    game.set_orders('FRANCE', ['A BUR - PAR'])
    game.process()  # S1901R -> F1901T
    assert game.get_current_phase() == 'F1901T'

def test_talk_full_sequence_with_adjustments():
    """ When adjustments exist, sequence includes Winter """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M

    # France takes Spain
    game.clear_units()
    game.set_units('FRANCE', ['A MAR'])
    game.set_orders('FRANCE', ['A MAR - SPA'])
    game.process()  # S1901M -> F1901T
    game.process()  # F1901T -> F1901M

    game.set_orders('FRANCE', ['A SPA H'])
    game.process()  # F1901M -> W1901A (France has 4 centers, 1 unit -> needs builds)
    assert game.get_current_phase() == 'W1901A'

    # Build
    game.set_orders('FRANCE', ['A PAR B'])
    game.process()  # W1901A -> S1902T
    assert game.get_current_phase() == 'S1902T'

def test_talk_multi_year():
    """ Talk-enabled game advances correctly over multiple years """
    game = _game_with_talk()
    # Each year: T, M, T, M = 4 phases (skipping R and A when nothing to do)
    for year in range(1, 4):
        game.process()  # Spring T -> Spring M
        game.process()  # Spring M -> Fall T
        game.process()  # Fall T -> Fall M
        game.process()  # Fall M -> next Spring T
        expected_year = game.map.first_year + year
        phase = game.get_current_phase()
        assert phase == f'S{expected_year}T', f'Expected S{expected_year}T, got {phase}'


# ===========================================================================
# HISTORY TESTS
# ===========================================================================

def test_talk_phase_in_state_history():
    """ Talk phase appears in state_history after processing """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M
    assert len(game.state_history) == 1
    assert 'S1901T' in [str(k) for k in game.state_history.keys()]

def test_talk_phase_in_order_history():
    """ Talk phase appears in order_history (empty orders) """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M
    assert len(game.order_history) == 1
    phase_key = str(game.order_history.first_key())
    assert phase_key == 'S1901T'

def test_talk_phase_in_message_history():
    """ Messages sent during Talk appear in message_history """
    game = _game_with_talk()
    msg = Message(sender='FRANCE', recipient='ENGLAND', phase=game.current_short_phase,
                  message='Alliance proposal')
    game.add_message(msg)
    game.process()  # S1901T -> S1901M
    assert len(game.message_history) == 1
    talk_messages = list(game.message_history.first_value().values())
    assert len(talk_messages) == 1
    assert talk_messages[0].message == 'Alliance proposal'

def test_talk_and_movement_both_in_history():
    """ Both Talk and Movement phases appear in history """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M
    game.set_orders('FRANCE', ['A PAR - BUR'])
    game.process()  # S1901M -> F1901T
    assert len(game.state_history) == 2
    keys = [str(k) for k in game.state_history.keys()]
    assert keys == ['S1901T', 'S1901M']

def test_history_ordering_with_talk():
    """ History keys are in chronological order including Talk """
    game = _game_with_talk()
    for _ in range(4):
        game.process()
    # Should have 4 history entries: S1901T, S1901M, F1901T, F1901M
    keys = [str(k) for k in game.state_history.keys()]
    assert keys == ['S1901T', 'S1901M', 'F1901T', 'F1901M']

def test_talk_messages_not_carried_to_movement():
    """ Messages from Talk phase don't appear in Movement phase's current messages """
    game = _game_with_talk()
    msg = Message(sender='FRANCE', recipient='ENGLAND', phase=game.current_short_phase,
                  message='Secret deal')
    game.add_message(msg)
    assert len(game.messages) == 1
    game.process()  # S1901T -> S1901M
    assert len(game.messages) == 0

def test_result_history_with_talk():
    """ Talk phase has empty results in result_history """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M
    talk_key = game.result_history.first_key()
    assert str(talk_key) == 'S1901T'
    assert game.result_history[talk_key] == {}


# ===========================================================================
# SERIALIZATION TESTS
# ===========================================================================

def test_talk_game_to_dict_and_back():
    """ Talk-enabled game survives serialization round-trip """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M
    game_dict = game.to_dict()
    game_copy = Game.from_dict(game_dict)
    assert game_copy.get_current_phase() == 'S1901M'
    assert 'NO_TALK' not in game_copy.rules

def test_talk_game_server_game_round_trip():
    """ Talk-enabled ServerGame survives serialization """
    game = _game_with_talk()
    msg = Message(sender='FRANCE', recipient='ENGLAND', phase=game.current_short_phase,
                  message='Test message')
    game.add_message(msg)
    game.process()  # S1901T -> S1901M
    game_dict = game.to_dict()
    game_copy = ServerGame.from_dict(game_dict)
    assert game_copy.get_current_phase() == 'S1901M'
    assert len(game_copy.message_history) == 1
    keys = [str(k) for k in game_copy.state_history.keys()]
    assert 'S1901T' in keys

def test_talk_game_deepcopy():
    """ Talk-enabled game can be deep copied """
    game = _game_with_talk()
    game_copy = deepcopy(game)
    assert game_copy.get_current_phase() == 'S1901T'
    assert game_copy.phase_type == 'T'
    # Advance copy, original stays
    game_copy.process()
    assert game_copy.get_current_phase() == 'S1901M'
    assert game.get_current_phase() == 'S1901T'


# ===========================================================================
# ORDER RESOLUTION THROUGH TALK PHASES
# ===========================================================================

def test_orders_resolve_after_talk():
    """ Orders resolve correctly in Movement phase after Talk """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M
    game.set_orders('FRANCE', ['A PAR - BUR', 'A MAR - BUR'])
    game.process()  # S1901M -> F1901T
    phase_data = game.get_phase_from_history('S1901M')
    assert BOUNCE in phase_data.results['A PAR']
    assert BOUNCE in phase_data.results['A MAR']

def test_combat_resolution_after_talk():
    """ Multi-power combat resolves correctly after Talk """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M
    game.set_orders('FRANCE', ['A MAR - BUR'])
    game.set_orders('GERMANY', ['A MUN - BUR'])
    game.process()  # S1901M -> F1901T
    phase_data = game.get_phase_from_history('S1901M')
    assert BOUNCE in phase_data.results['A MAR']
    assert BOUNCE in phase_data.results['A MUN']

def test_successful_move_after_talk():
    """ Successful moves work after Talk phase """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M
    game.set_orders('FRANCE', ['A PAR - BUR'])
    game.process()  # S1901M -> F1901T
    assert 'A BUR' in game.get_units('FRANCE')


# ===========================================================================
# EDGE CASES
# ===========================================================================

def test_talk_phase_with_dont_skip_phases():
    """ DONT_SKIP_PHASES + Talk enabled: Retreats and Adjustments still appear """
    rules = ['SOLITAIRE', 'NO_PRESS', 'IGNORE_ERRORS', 'POWER_CHOICE', 'DONT_SKIP_PHASES']
    game = Game(rules=rules)
    assert game.get_current_phase() == 'S1901T'
    game.process()  # S1901T -> S1901M
    assert game.get_current_phase() == 'S1901M'
    game.process()  # S1901M -> S1901R (not skipped)
    assert game.get_current_phase() == 'S1901R'
    game.process()  # S1901R -> F1901T
    assert game.get_current_phase() == 'F1901T'

def test_set_current_phase_to_talk():
    """ set_current_phase works with Talk phases """
    game = _game_with_talk()
    game.set_current_phase('F1901T')
    assert game.get_current_phase() == 'F1901T'
    assert game.phase_type == 'T'

def test_talk_phase_get_phase_from_history():
    """ get_phase_from_history works for Talk phases """
    game = _game_with_talk()
    msg = Message(sender='FRANCE', recipient='ENGLAND', phase='S1901T',
                  message='Hello')
    game.add_message(msg)
    game.process()  # S1901T -> S1901M
    phase_data = game.get_phase_from_history('S1901T')
    assert phase_data is not None
    assert phase_data.name == 'S1901T'
    messages = list(phase_data.messages.values())
    assert len(messages) == 1
    assert messages[0].message == 'Hello'

def test_game_not_done_after_talk():
    """ Game is not done after processing a Talk phase """
    game = _game_with_talk()
    game.process()  # S1901T -> S1901M
    assert game.is_game_done is False
    assert game.phase != 'COMPLETED'


# ===========================================================================
# SERVER-LEVEL ROUND STATE TESTS
# ===========================================================================

def _server_game_with_talk(**kwargs):
    """Helper: create a ServerGame with Talk phases enabled and status=active."""
    rules = kwargs.pop('rules', ['SOLITAIRE', 'NO_PRESS', 'IGNORE_ERRORS', 'POWER_CHOICE'])
    return ServerGame(status=strings.ACTIVE, rules=rules, **kwargs)


def _server_game_with_controlled_powers(**kwargs):
    """Helper: create a ServerGame with Talk enabled and two controlled powers."""
    rules = kwargs.pop('rules', ['NO_PRESS', 'IGNORE_ERRORS', 'POWER_CHOICE'])
    game = ServerGame(status=strings.ACTIVE, rules=rules, **kwargs)
    # Control two powers
    game.get_power('FRANCE').set_controlled('user_france')
    game.get_power('ENGLAND').set_controlled('user_england')
    return game


def test_talk_round_initial_state():
    """New ServerGame starts with talk_round=0."""
    game = _server_game_with_talk()
    assert game.talk_round == 0
    assert game.talk_round_state == ''
    assert game.talk_ready == set()
    assert game.talk_held_messages == []


def test_talk_round_opens_on_process():
    """First process() of Talk phase opens round 1."""
    game = _server_game_with_talk()
    assert game.phase_type == 'T'
    prev, curr, kicked = game.process()
    assert prev is None and curr is None and kicked is None
    assert game.talk_round == 1
    assert game.talk_round_state == 'round_open'
    assert game.talk_ready == set()


def test_talk_round_advances():
    """Signaling ready advances through rounds (default 2 rounds)."""
    game = _server_game_with_talk()
    assert game.talk_num_rounds == 2

    # Open round 1
    game.process()
    assert game.talk_round == 1
    assert game.talk_round_state == 'round_open'

    # Process again -> should advance to round 2
    game.process()
    assert game.talk_round == 2
    assert game.talk_round_state == 'round_open'


def test_talk_round_to_orders_open():
    """After final round, transitions to orders_open."""
    game = _server_game_with_talk()

    # Open round 1
    game.process()
    # Advance to round 2
    game.process()
    assert game.talk_round == 2
    # Process final round -> orders_open
    game.process()
    assert game.talk_round_state == 'orders_open'
    assert game.talk_ready == set()


def test_talk_round_to_movement():
    """After orders_open ready, advances to Movement."""
    game = _server_game_with_talk()

    # Round 1
    game.process()
    # Round 2
    game.process()
    # orders_open
    game.process()
    assert game.talk_round_state == 'orders_open'

    # Final process -> should advance past Talk to Movement
    game.process()
    assert game.phase_type == 'M'
    assert game.get_current_phase() == 'S1901M'
    # Talk state should be reset
    assert game.talk_round == 0
    assert game.talk_round_state == ''


def test_talk_round_state_serialization():
    """to_dict/from_dict preserves round state."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    game.process()  # advance to round 2

    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)
    assert restored.talk_round == 2
    assert restored.talk_round_state == 'round_open'
    assert restored.talk_ready == set()


def test_talk_round_complete_skips_eliminated():
    """Eliminated powers don't block talk_round_complete()."""
    game = _server_game_with_controlled_powers()
    game.process()  # open round 1

    # Eliminate FRANCE by removing all units and centers
    france = game.get_power('FRANCE')
    france.units = []
    france.centers = []
    france.retreats = {}

    # Only ENGLAND needs to be ready
    game.talk_ready.add('ENGLAND')
    assert game.talk_round_complete()


def test_talk_round_complete_skips_dummy():
    """Uncontrolled (dummy) powers don't block talk_round_complete()."""
    game = _server_game_with_controlled_powers()
    game.process()  # open round 1

    # Only FRANCE and ENGLAND are controlled; others are dummy
    game.talk_ready.add('FRANCE')
    game.talk_ready.add('ENGLAND')
    assert game.talk_round_complete()


def test_talk_round_resets_on_new_phase():
    """New Talk phase starts at round 0 after full cycle."""
    game = _server_game_with_talk()

    # Go through full Talk cycle: round 1, round 2, orders_open, then advance
    game.process()  # round 1
    game.process()  # round 2
    game.process()  # orders_open
    game.process()  # advance to Movement

    assert game.phase_type == 'M'
    assert game.talk_round == 0
    assert game.talk_round_state == ''

    # Process Movement to get to Fall Talk
    game.process()  # S1901M -> F1901T
    assert game.phase_type == 'T'
    assert game.talk_round == 0

    # First process of new Talk phase opens round 1
    game.process()
    assert game.talk_round == 1
    assert game.talk_round_state == 'round_open'


def test_talk_num_rounds_config():
    """talk_num_rounds=3 gives 3 rounds."""
    game = _server_game_with_talk(talk_num_rounds=3)
    assert game.talk_num_rounds == 3

    game.process()  # round 1
    assert game.talk_round == 1
    game.process()  # round 2
    assert game.talk_round == 2
    game.process()  # round 3
    assert game.talk_round == 3
    assert game.talk_round_state == 'round_open'

    # Now should go to orders_open
    game.process()
    assert game.talk_round_state == 'orders_open'

    # Then advance to Movement
    game.process()
    assert game.phase_type == 'M'


def test_talk_round_complete_false_not_talk_phase():
    """talk_round_complete() returns False when not in a Talk phase."""
    game = _server_game_with_talk()
    # Advance through full Talk cycle to reach Movement
    game.process()  # round 1
    game.process()  # round 2
    game.process()  # orders_open
    game.process()  # -> Movement
    assert game.phase_type == 'M'
    assert game.talk_round_complete() is False


def test_talk_round_complete_false_wrong_state():
    """talk_round_complete() returns False when round_state is not round_open or orders_open."""
    game = _server_game_with_talk()
    # round_state is '' before any process()
    assert game.talk_round_complete() is False

    game.process()  # round 1, state='round_open'
    # Manually set to round_closed
    game.talk_round_state = 'round_closed'
    assert game.talk_round_complete() is False


def test_talk_round_complete_false_missing_power():
    """talk_round_complete() returns False when a controlled power hasn't signaled ready."""
    game = _server_game_with_controlled_powers()
    game.process()  # open round 1

    # Only FRANCE is ready, ENGLAND is not
    game.talk_ready.add('FRANCE')
    assert game.talk_round_complete() is False

    # Now ENGLAND too
    game.talk_ready.add('ENGLAND')
    assert game.talk_round_complete() is True


def test_talk_round_complete_true_orders_open():
    """talk_round_complete() returns True during orders_open when all controlled powers are ready."""
    game = _server_game_with_controlled_powers()
    game.process()  # round 1
    game.process()  # round 2
    game.process()  # orders_open
    assert game.talk_round_state == 'orders_open'
    assert game.talk_ready == set()

    game.talk_ready.add('FRANCE')
    game.talk_ready.add('ENGLAND')
    assert game.talk_round_complete() is True


def test_talk_round_complete_solitaire_all_dummy():
    """talk_round_complete() returns True in solitaire (all powers are dummy)."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    # Solitaire: no controlled powers -> no one to wait for
    assert game.talk_round_complete() is True


def test_process_inactive_game_returns_none():
    """process() returns (None, None, None) for inactive game."""
    from diplomacy.utils import strings
    game = ServerGame(status=strings.FORMING,
                      rules=['SOLITAIRE', 'NO_PRESS', 'IGNORE_ERRORS', 'POWER_CHOICE'])
    assert not game.is_game_active
    prev, curr, kicked = game.process()
    assert prev is None and curr is None and kicked is None


def test_process_no_talk_rule_skips_round_handling():
    """process() with NO_TALK in rules skips talk round handling entirely."""
    from diplomacy.utils import strings
    game = ServerGame(status=strings.ACTIVE)
    # Default rules include NO_TALK, game starts at Movement
    assert 'NO_TALK' in game.rules
    assert game.phase_type == 'M'
    # process() should work normally (no talk round interference)
    prev, curr, kicked = game.process()
    # Should advance normally past Movement
    assert game.talk_round == 0
    assert game.talk_round_state == ''


def test_talk_ready_cleared_between_rounds():
    """talk_ready set is cleared when advancing from one round to the next."""
    game = _server_game_with_talk()
    game.process()  # round 1
    game.talk_ready.add('FRANCE')
    game.talk_ready.add('ENGLAND')
    assert len(game.talk_ready) == 2

    game.process()  # round 2
    assert game.talk_ready == set()


def test_talk_ready_cleared_entering_orders_open():
    """talk_ready set is cleared when transitioning to orders_open."""
    game = _server_game_with_talk()
    game.process()  # round 1
    game.process()  # round 2
    game.talk_ready.add('FRANCE')

    game.process()  # orders_open
    assert game.talk_round_state == 'orders_open'
    assert game.talk_ready == set()


def test_talk_held_messages_cleared_on_reset():
    """talk_held_messages is cleared when talk state resets."""
    game = _server_game_with_talk()
    game.process()  # round 1
    game.talk_held_messages.append({'test': 'message'})

    # Complete full cycle
    game.process()  # round 2
    game.process()  # orders_open
    game.process()  # -> Movement
    assert game.talk_held_messages == []


def test_talk_round_serialization_with_ready():
    """to_dict/from_dict preserves talk_ready with values."""
    game = _server_game_with_talk()
    game.process()  # round 1
    game.talk_ready.add('FRANCE')
    game.talk_ready.add('ENGLAND')

    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)
    assert restored.talk_ready == {'FRANCE', 'ENGLAND'}
    assert restored.talk_round == 1
    assert restored.talk_round_state == 'round_open'


def test_talk_round_serialization_orders_open():
    """to_dict/from_dict preserves orders_open state."""
    game = _server_game_with_talk()
    game.process()  # round 1
    game.process()  # round 2
    game.process()  # orders_open

    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)
    assert restored.talk_round_state == 'orders_open'
    assert restored.talk_round == 2


def test_talk_num_rounds_one():
    """talk_num_rounds=1 gives exactly one talk round before orders_open."""
    game = _server_game_with_talk(talk_num_rounds=1)
    assert game.talk_num_rounds == 1

    game.process()  # round 1
    assert game.talk_round == 1
    assert game.talk_round_state == 'round_open'

    # Next process should go to orders_open (no round 2)
    game.process()
    assert game.talk_round_state == 'orders_open'

    # Then advance to Movement
    game.process()
    assert game.phase_type == 'M'


def test_talk_num_rounds_serialization():
    """talk_num_rounds survives Game serialization."""
    game = _game_with_talk(talk_num_rounds=5)
    game_dict = game.to_dict()
    restored = Game.from_dict(game_dict)
    assert restored.talk_num_rounds == 5


def test_talk_round_multi_year_server_game():
    """ServerGame Talk round state resets properly across multiple years."""
    game = _server_game_with_talk()

    for year_cycle in range(3):
        # Spring Talk
        assert game.phase_type == 'T', f'Year cycle {year_cycle}: expected Talk, got {game.phase_type}'
        assert game.talk_round == 0
        game.process()  # round 1
        game.process()  # round 2
        game.process()  # orders_open
        game.process()  # -> Movement

        assert game.phase_type == 'M'
        assert game.talk_round == 0
        game.process()  # Movement -> Fall Talk

        # Fall Talk
        assert game.phase_type == 'T'
        assert game.talk_round == 0
        game.process()  # round 1
        game.process()  # round 2
        game.process()  # orders_open
        game.process()  # -> Movement

        assert game.phase_type == 'M'
        game.process()  # Movement -> next Spring Talk


def test_process_return_values_during_talk_rounds():
    """All process() calls during talk rounds return (None, None, None)."""
    game = _server_game_with_talk()

    # Round 1 open
    result = game.process()
    assert result == (None, None, None)

    # Round 2 open
    result = game.process()
    assert result == (None, None, None)

    # Orders open
    result = game.process()
    assert result == (None, None, None)

    # Fall through to actual processing (returns phase data)
    prev, curr, kicked = game.process()
    assert prev is not None  # previous phase data
    assert curr is not None  # current phase data
    assert kicked is None


def test_talk_round_state_not_affected_by_movement_process():
    """Processing a Movement phase doesn't alter talk round state."""
    game = _server_game_with_talk()
    # Complete Talk cycle
    game.process()  # round 1
    game.process()  # round 2
    game.process()  # orders_open
    game.process()  # -> Movement

    assert game.phase_type == 'M'
    assert game.talk_round == 0
    assert game.talk_round_state == ''

    # Process Movement
    game.process()
    # Should still be clean
    assert game.talk_round == 0
    assert game.talk_round_state == ''


# ===========================================================================
# STEP 3 — BATCH MESSAGE COLLECTION TESTS
# ===========================================================================

def _simulate_send_message(game, sender, recipient, body):
    """Simulate what on_send_game_message does during a Talk round.

    Returns (held_dict, status) or raises if messages are blocked.
    """
    if (game.phase_type == 'T'
            and 'NO_TALK' not in game.rules
            and game.talk_round_state == strings.ROUND_OPEN):
        is_communique = (recipient == 'GLOBAL')

        status = 'valid'
        void_reason = ''

        if is_communique:
            comm_count = game.talk_communique_counts.get(sender, 0)
            game.talk_communique_counts[sender] = comm_count + 1
            if comm_count >= game.talk_max_communiques_per_year:
                status = 'void'
                void_reason = 'Communique limit exceeded (%d per year)' % game.talk_max_communiques_per_year
            elif len(body) > game.talk_max_communique_chars:
                status = 'void'
                void_reason = 'Communique too long (%d char limit)' % game.talk_max_communique_chars
        else:
            current_count = game.talk_message_counts.get(sender, 0)
            game.talk_message_counts[sender] = current_count + 1
            if current_count >= game.talk_max_messages_per_round:
                status = 'void'
                void_reason = 'Message limit exceeded (%d per round)' % game.talk_max_messages_per_round
            elif len(body) > game.talk_max_chars_per_message:
                status = 'void'
                void_reason = 'Message too long (%d char limit)' % game.talk_max_chars_per_message

        held = {
            'sender': sender,
            'recipient': recipient,
            'phase': game.current_short_phase,
            'message': body,
            'round': game.talk_round,
            'status': status,
            'void_reason': void_reason,
            'type': 'communique' if is_communique else 'private',
        }
        game.talk_held_messages.append(held)
        return held, status

    if (game.phase_type == 'T'
            and 'NO_TALK' not in game.rules
            and game.talk_round_state in (strings.ORDERS_OPEN, strings.ROUND_CLOSED)):
        raise RuntimeError('Messages can only be sent during talk rounds.')

    return None, None


def test_message_held_during_round_open():
    """Messages submitted during round_open go into talk_held_messages, not game.messages."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    assert game.talk_round_state == strings.ROUND_OPEN

    held, status = _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Hello England!')
    assert status == 'valid'
    assert len(game.talk_held_messages) == 1
    assert game.talk_held_messages[0]['sender'] == 'FRANCE'
    assert game.talk_held_messages[0]['recipient'] == 'ENGLAND'
    assert game.talk_held_messages[0]['message'] == 'Hello England!'
    assert game.talk_held_messages[0]['round'] == 1
    assert game.talk_held_messages[0]['status'] == 'valid'
    assert game.talk_held_messages[0]['type'] == 'private'
    # Message should NOT be in game.messages (not delivered yet)
    assert len(game.messages) == 0


def test_message_count_incremented():
    """talk_message_counts tracks per-power submission count."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'msg1')
    assert game.talk_message_counts['FRANCE'] == 1

    _simulate_send_message(game, 'FRANCE', 'GERMANY', 'msg2')
    assert game.talk_message_counts['FRANCE'] == 2

    _simulate_send_message(game, 'ENGLAND', 'FRANCE', 'msg3')
    assert game.talk_message_counts['ENGLAND'] == 1


def test_void_message_over_count_limit():
    """Message exceeding per-round count limit is stored with status='void'."""
    game = _server_game_with_talk(talk_max_messages_per_round=2)
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'msg1')
    _simulate_send_message(game, 'FRANCE', 'GERMANY', 'msg2')
    held, status = _simulate_send_message(game, 'FRANCE', 'ITALY', 'msg3')

    assert status == 'void'
    assert held['void_reason'] == 'Message limit exceeded (2 per round)'
    assert len(game.talk_held_messages) == 3
    assert game.talk_held_messages[2]['status'] == 'void'


def test_void_message_over_char_limit():
    """Message exceeding character limit is stored with status='void'."""
    game = _server_game_with_talk(talk_max_chars_per_message=10)
    game.process()  # open round 1

    held, status = _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'This is way too long')
    assert status == 'void'
    assert 'char limit' in held['void_reason']


def test_void_message_still_counts_against_quota():
    """Void messages increment the counter (prevents probing)."""
    game = _server_game_with_talk(talk_max_messages_per_round=2, talk_max_chars_per_message=5)
    game.process()  # open round 1

    # First message is too long -> void
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Way too long message')
    assert game.talk_message_counts['FRANCE'] == 1

    # Second message is valid
    _simulate_send_message(game, 'FRANCE', 'GERMANY', 'Hi')
    assert game.talk_message_counts['FRANCE'] == 2

    # Third message exceeds count limit -> void
    held, status = _simulate_send_message(game, 'FRANCE', 'ITALY', 'Hey')
    assert status == 'void'
    assert 'limit exceeded' in held['void_reason']


def test_message_counts_reset_on_new_round():
    """talk_message_counts resets when a new round opens."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'round 1 msg')
    assert game.talk_message_counts['FRANCE'] == 1

    game.process()  # close round 1, open round 2
    assert game.talk_message_counts == {}


def test_message_blocked_during_orders_open():
    """Messages cannot be sent during orders_open state."""
    game = _server_game_with_talk()
    game.process()  # round 1
    game.process()  # round 2
    game.process()  # orders_open
    assert game.talk_round_state == strings.ORDERS_OPEN

    try:
        _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Should fail')
        assert False, 'Should have raised'
    except RuntimeError as e:
        assert 'talk rounds' in str(e)


def test_config_defaults():
    """Default config values for message limits."""
    game = _server_game_with_talk()
    assert game.talk_max_messages_per_round == 5
    assert game.talk_max_chars_per_message == 500


def test_config_custom_limits():
    """Custom message limits survive creation."""
    game = _server_game_with_talk(talk_max_messages_per_round=3, talk_max_chars_per_message=200)
    assert game.talk_max_messages_per_round == 3
    assert game.talk_max_chars_per_message == 200


def test_config_serialization_round_trip():
    """Message limit config survives to_dict/from_dict."""
    game = _server_game_with_talk(talk_max_messages_per_round=3, talk_max_chars_per_message=200)
    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)
    assert restored.talk_max_messages_per_round == 3
    assert restored.talk_max_chars_per_message == 200


def test_talk_message_counts_serialization():
    """talk_message_counts survives serialization."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'test')

    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)
    assert restored.talk_message_counts == {'FRANCE': 1}


def test_held_messages_serialization():
    """talk_held_messages survives serialization with full structure."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Hello!')

    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)
    assert len(restored.talk_held_messages) == 1
    assert restored.talk_held_messages[0]['sender'] == 'FRANCE'
    assert restored.talk_held_messages[0]['status'] == 'valid'
    assert restored.talk_held_messages[0]['type'] == 'private'


def test_multiple_powers_submit_messages():
    """Multiple powers can submit messages in the same round."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'From France')
    _simulate_send_message(game, 'ENGLAND', 'FRANCE', 'From England')
    _simulate_send_message(game, 'GERMANY', 'FRANCE', 'From Germany')

    assert len(game.talk_held_messages) == 3
    assert game.talk_message_counts['FRANCE'] == 1
    assert game.talk_message_counts['ENGLAND'] == 1
    assert game.talk_message_counts['GERMANY'] == 1


# ===========================================================================
# STEP 4 — BATCH DELIVERY TESTS
# ===========================================================================

def test_valid_messages_delivered_on_round_close():
    """Valid held messages appear in game.messages after _close_talk_round."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Hello England')
    _simulate_send_message(game, 'GERMANY', 'FRANCE', 'Hello France')
    assert len(game.messages) == 0  # not yet delivered

    game.process()  # close round 1, open round 2
    # Messages should now be in game.messages
    assert len(game.messages) == 2
    senders = {msg.sender for msg in game.messages.values()}
    assert senders == {'FRANCE', 'GERMANY'}


def test_void_messages_not_delivered():
    """Void messages do not appear in game.messages after round close."""
    game = _server_game_with_talk(talk_max_messages_per_round=1)
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'First msg')
    _simulate_send_message(game, 'FRANCE', 'GERMANY', 'Over limit')  # void

    game.process()  # close round 1, open round 2
    # Only the valid message should be delivered
    assert len(game.messages) == 1
    assert list(game.messages.values())[0].message == 'First msg'


def test_delivered_messages_have_timestamps():
    """Delivered messages have server-generated timestamps."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Test')
    game.process()  # close round 1, open round 2

    for msg in game.messages.values():
        assert msg.time_sent is not None
        assert msg.time_sent > 0


def test_round1_messages_visible_when_round2_opens():
    """Messages from round 1 are in game.messages when round 2 is active."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Round 1 msg')
    game.process()  # close round 1, open round 2

    assert game.talk_round == 2
    assert game.talk_round_state == strings.ROUND_OPEN
    assert len(game.messages) == 1
    assert list(game.messages.values())[0].message == 'Round 1 msg'


def test_round2_messages_delivered_on_close():
    """Messages from round 2 are also delivered when round 2 closes."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'R1 msg')

    game.process()  # close round 1, open round 2
    _simulate_send_message(game, 'ENGLAND', 'FRANCE', 'R2 msg')

    game.process()  # close round 2 (orders_open)
    assert len(game.messages) == 2


def test_talk_messages_in_phase_history_after_advance():
    """After Talk→Movement, Talk messages are in message_history."""
    game = _server_game_with_talk()
    talk_phase = game.current_short_phase  # S1901T
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Diplomacy!')

    game.process()  # round 2
    game.process()  # orders_open
    game.process()  # -> Movement

    assert game.phase_type == 'M'
    assert talk_phase in game.message_history
    talk_msgs = game.message_history[talk_phase]
    assert len(talk_msgs) == 1


def test_last_delivered_messages_populated_on_round_close():
    """_last_delivered_messages is populated with delivered Message objects."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Test')
    _simulate_send_message(game, 'GERMANY', 'ITALY', 'Another')

    game.process()  # close round 1, open round 2
    # _last_delivered_messages holds the Message objects from the just-closed round
    # (In server flow, _process_game uses these for notifications then clears them)
    assert len(game._last_delivered_messages) == 2
    assert game._last_delivered_messages[0].sender == 'FRANCE'
    assert game._last_delivered_messages[1].sender == 'GERMANY'
    # And the messages ARE in game.messages (delivered)
    assert len(game.messages) == 2


def test_void_messages_removed_from_held_after_round_close():
    """Void messages for the closed round are removed from talk_held_messages."""
    game = _server_game_with_talk(talk_max_messages_per_round=1)
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Valid')
    _simulate_send_message(game, 'FRANCE', 'GERMANY', 'Over limit')  # void

    game.process()  # close round 1, open round 2
    # Both valid and void for round 1 should be cleared from held messages
    assert len(game.talk_held_messages) == 0


# ===========================================================================
# STEP 5 — CLIENT NOTIFICATION TESTS
# ===========================================================================

def test_talk_round_update_notification_class():
    """TalkRoundUpdate notification serializes and deserializes correctly."""
    from diplomacy.communication.notifications import TalkRoundUpdate
    notif = TalkRoundUpdate(
        token='test_token',
        game_id='test_game',
        game_role='FRANCE',
        talk_round=2,
        talk_round_state=strings.ROUND_OPEN,
        talk_num_rounds=3,
    )
    assert notif.talk_round == 2
    assert notif.talk_round_state == strings.ROUND_OPEN
    assert notif.talk_num_rounds == 3

    # Round-trip via dict
    notif_dict = notif.to_dict()
    assert notif_dict['talk_round'] == 2
    assert notif_dict['talk_round_state'] == 'round_open'
    assert notif_dict['talk_num_rounds'] == 3


def test_talk_round_update_in_notification_mapping():
    """TalkRoundUpdate is registered in the client notification MAPPING."""
    from diplomacy.client.notification_managers import MAPPING
    from diplomacy.communication.notifications import TalkRoundUpdate
    assert TalkRoundUpdate in MAPPING


def test_talk_round_update_callback_on_network_game():
    """NetworkGame has add_on_talk_round_update callback setter."""
    from diplomacy.client.network_game import NetworkGame
    assert hasattr(NetworkGame, 'add_on_talk_round_update')
    assert hasattr(NetworkGame, 'clear_on_talk_round_update')


# ===========================================================================
# STEP 6 — TIMER/DEADLINE TESTS
# ===========================================================================

def test_talk_deadline_defaults():
    """Default deadline values are 0 (no auto-advance)."""
    game = _server_game_with_talk()
    assert game.talk_round_deadline == 0
    assert game.talk_orders_deadline == 0


def test_talk_deadline_custom():
    """Custom deadline values survive creation."""
    game = _server_game_with_talk(talk_round_deadline=60, talk_orders_deadline=120)
    assert game.talk_round_deadline == 60
    assert game.talk_orders_deadline == 120


def test_talk_deadline_serialization():
    """Deadline config survives to_dict/from_dict."""
    game = _server_game_with_talk(talk_round_deadline=30, talk_orders_deadline=90)
    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)
    assert restored.talk_round_deadline == 30
    assert restored.talk_orders_deadline == 90


def test_talk_deadline_zero_means_no_auto_advance():
    """With deadline=0, round advancement only happens via ready signaling."""
    game = _server_game_with_talk(talk_round_deadline=0)
    game.process()  # open round 1
    assert game.talk_round == 1
    assert game.talk_round_state == strings.ROUND_OPEN
    # With no deadline, game waits for all powers to signal ready
    # (No auto-advance happens without server scheduler)


# ===========================================================================
# STEP 7 — PUBLIC COMMUNIQUE TESTS
# ===========================================================================

def test_communique_held_during_round():
    """Global messages are held as communiques during talk rounds."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Public announcement!')
    assert len(game.talk_held_messages) == 1
    assert game.talk_held_messages[0]['type'] == 'communique'
    assert game.talk_held_messages[0]['recipient'] == 'GLOBAL'
    assert game.talk_held_messages[0]['status'] == 'valid'


def test_communique_separate_from_private_quota():
    """Communiques don't count against per-round private message limit."""
    game = _server_game_with_talk(talk_max_messages_per_round=1)
    game.process()  # open round 1

    # Send 1 private message (hits limit)
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Private msg')
    assert game.talk_message_counts['FRANCE'] == 1

    # Communique should still be valid (separate quota)
    held, status = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Public msg')
    assert status == 'valid'
    assert held['type'] == 'communique'
    # Private count unchanged by communique
    assert game.talk_message_counts['FRANCE'] == 1


def test_communique_limit_per_year():
    """Second communique in same year is void."""
    game = _server_game_with_talk(talk_max_communiques_per_year=1)
    game.process()  # open round 1

    held1, status1 = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'First communique')
    assert status1 == 'valid'

    held2, status2 = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Second communique')
    assert status2 == 'void'
    assert 'limit exceeded' in held2['void_reason']


def test_communique_limit_resets_on_new_year():
    """Communique count resets at Spring Talk (new year)."""
    game = _server_game_with_talk(talk_max_communiques_per_year=1)

    # Spring Talk
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Spring communique')
    assert game.talk_communique_counts['FRANCE'] == 1

    # Complete spring talk and movement
    game.process()  # round 2
    game.process()  # orders_open
    game.process()  # -> Movement
    game.process()  # -> Fall Talk (or retreats)

    # Process until we hit next Spring Talk
    # Fall Talk
    if game.phase_type == 'T':
        # Fall Talk — communique count should NOT reset yet
        game.process()  # open round 1 of Fall
        assert game.talk_communique_counts.get('FRANCE', 0) == 1  # still from spring

        # Complete Fall
        game.process()  # round 2
        game.process()  # orders_open
        game.process()  # -> Fall Movement
        game.process()  # -> Winter or Spring

    # Keep advancing until Spring Talk of next year
    while game.phase_type != 'T' or not game.current_short_phase.startswith('S'):
        game.process()

    # Now at Spring Talk of new year — process to open round 1
    game.process()  # open round 1
    # Communique count should be reset
    assert game.talk_communique_counts.get('FRANCE', 0) == 0


def test_communique_char_limit():
    """Communique exceeding char limit is void."""
    game = _server_game_with_talk(talk_max_communique_chars=10)
    game.process()  # open round 1

    held, status = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'This communique is way too long')
    assert status == 'void'
    assert 'char limit' in held['void_reason']


def test_communique_delivered_on_round_close():
    """Valid communiques are delivered as GLOBAL recipient messages."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Public!')
    game.process()  # close round 1, open round 2

    # Communique should be in game.messages with GLOBAL recipient
    assert len(game.messages) == 1
    msg = list(game.messages.values())[0]
    assert msg.recipient == 'GLOBAL'
    assert msg.sender == 'FRANCE'


def test_communique_counts_serialization():
    """talk_communique_counts survives serialization."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Public!')

    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)
    assert restored.talk_communique_counts == {'FRANCE': 1}


def test_communique_config_defaults():
    """Default communique config values."""
    game = _server_game_with_talk()
    assert game.talk_max_communiques_per_year == 1
    assert game.talk_max_communique_chars == 500


# ===========================================================================
# STEP 8 — PRESS LOG TESTS
# ===========================================================================

def test_press_log_contains_metadata_only():
    """Press log entries contain sender, recipient, char_count, status, type — no message body."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Hello England!')
    game.process()  # close round 1, open round 2

    assert len(game._last_press_log) == 1
    entry = game._last_press_log[0]
    assert entry['sender'] == 'FRANCE'
    assert entry['recipient'] == 'ENGLAND'
    assert entry['char_count'] == len('Hello England!')
    assert entry['status'] == 'valid'
    assert entry['type'] == 'private'
    # No message body in press log
    assert 'message' not in entry


def test_press_log_includes_void_messages():
    """Void messages appear in the press log."""
    game = _server_game_with_talk(talk_max_messages_per_round=1)
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Valid')
    _simulate_send_message(game, 'FRANCE', 'GERMANY', 'Over limit')  # void

    game.process()  # close round 1, open round 2

    assert len(game._last_press_log) == 2
    statuses = {e['status'] for e in game._last_press_log}
    assert statuses == {'valid', 'void'}


def test_press_log_empty_round():
    """An empty round produces an empty press log."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    # No messages sent

    game.process()  # close round 1, open round 2
    assert game._last_press_log == []


def test_press_log_per_round_separation():
    """Each round's press log only contains entries from that round."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'R1')
    game.process()  # close round 1, open round 2

    r1_log = list(game._last_press_log)
    assert len(r1_log) == 1
    assert r1_log[0]['sender'] == 'FRANCE'

    _simulate_send_message(game, 'GERMANY', 'ITALY', 'R2 msg')
    _simulate_send_message(game, 'ENGLAND', 'FRANCE', 'R2 reply')
    game.process()  # close round 2, orders_open

    r2_log = game._last_press_log
    assert len(r2_log) == 2
    senders = {e['sender'] for e in r2_log}
    assert senders == {'GERMANY', 'ENGLAND'}


def test_press_log_includes_communiques():
    """Communiques appear in press log with type='communique'."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Private msg')
    _simulate_send_message(game, 'GERMANY', 'GLOBAL', 'Public announcement')

    game.process()  # close round 1, open round 2

    assert len(game._last_press_log) == 2
    types = {e['type'] for e in game._last_press_log}
    assert types == {'private', 'communique'}


def test_press_log_notification_class():
    """TalkPressLog notification serializes and deserializes correctly."""
    from diplomacy.communication.notifications import TalkPressLog
    entries = [
        {'sender': 'FRANCE', 'recipient': 'ENGLAND', 'char_count': 14, 'status': 'valid', 'type': 'private'},
        {'sender': 'GERMANY', 'recipient': 'GLOBAL', 'char_count': 20, 'status': 'valid', 'type': 'communique'},
    ]
    notif = TalkPressLog(
        token='test_token',
        game_id='test_game',
        game_role='FRANCE',
        talk_round=1,
        entries=entries,
    )
    assert notif.talk_round == 1
    assert len(notif.entries) == 2

    notif_dict = notif.to_dict()
    assert notif_dict['talk_round'] == 1
    assert len(notif_dict['entries']) == 2
    assert notif_dict['entries'][0]['sender'] == 'FRANCE'


def test_press_log_in_notification_mapping():
    """TalkPressLog is registered in the client notification MAPPING."""
    from diplomacy.client.notification_managers import MAPPING
    from diplomacy.communication.notifications import TalkPressLog
    assert TalkPressLog in MAPPING


def test_press_log_callback_on_network_game():
    """NetworkGame has add_on_talk_press_log callback setter."""
    from diplomacy.client.network_game import NetworkGame
    assert hasattr(NetworkGame, 'add_on_talk_press_log')
    assert hasattr(NetworkGame, 'clear_on_talk_press_log')


# ===========================================================================
# ADDITIONAL EDGE CASE & INTEGRATION TESTS
# ===========================================================================

# --- Boundary conditions ---

def test_message_exactly_at_char_limit():
    """A message exactly at the char limit is valid."""
    game = _server_game_with_talk(talk_max_chars_per_message=10)
    game.process()  # open round 1

    held, status = _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'A' * 10)
    assert status == 'valid'


def test_message_one_over_char_limit():
    """A message one char over the limit is void."""
    game = _server_game_with_talk(talk_max_chars_per_message=10)
    game.process()  # open round 1

    held, status = _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'A' * 11)
    assert status == 'void'


def test_last_valid_message_at_count_limit():
    """The Nth message (at limit) is valid; the N+1th is void."""
    game = _server_game_with_talk(talk_max_messages_per_round=2)
    game.process()  # open round 1

    _, s1 = _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'msg1')
    _, s2 = _simulate_send_message(game, 'FRANCE', 'GERMANY', 'msg2')
    _, s3 = _simulate_send_message(game, 'FRANCE', 'ITALY', 'msg3')

    assert s1 == 'valid'
    assert s2 == 'valid'
    assert s3 == 'void'


def test_zero_message_limit_all_void():
    """With talk_max_messages_per_round=0, every message is void."""
    game = _server_game_with_talk(talk_max_messages_per_round=0)
    game.process()  # open round 1

    _, s1 = _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Hi')
    assert s1 == 'void'
    assert game.talk_message_counts['FRANCE'] == 1


def test_zero_communique_limit_all_void():
    """With talk_max_communiques_per_year=0, every communique is void."""
    game = _server_game_with_talk(talk_max_communiques_per_year=0)
    game.process()  # open round 1

    _, status = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Announcement')
    assert status == 'void'
    assert game.talk_communique_counts['FRANCE'] == 1


def test_empty_message_body():
    """An empty string message is valid (0 chars, under any positive limit)."""
    game = _server_game_with_talk(talk_max_chars_per_message=500)
    game.process()  # open round 1

    held, status = _simulate_send_message(game, 'FRANCE', 'ENGLAND', '')
    assert status == 'valid'
    assert held['message'] == ''


def test_communique_exactly_at_char_limit():
    """A communique exactly at the char limit is valid."""
    game = _server_game_with_talk(talk_max_communique_chars=15)
    game.process()  # open round 1

    held, status = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'A' * 15)
    assert status == 'valid'


def test_communique_one_over_char_limit():
    """A communique one char over the limit is void."""
    game = _server_game_with_talk(talk_max_communique_chars=15)
    game.process()  # open round 1

    held, status = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'A' * 16)
    assert status == 'void'


# --- Independent per-power limits ---

def test_independent_power_limits():
    """Each power has its own message count limit."""
    game = _server_game_with_talk(talk_max_messages_per_round=1)
    game.process()  # open round 1

    _, s1 = _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'fr-msg')
    _, s2 = _simulate_send_message(game, 'ENGLAND', 'FRANCE', 'en-msg')
    _, s3 = _simulate_send_message(game, 'FRANCE', 'GERMANY', 'fr-over')

    assert s1 == 'valid'
    assert s2 == 'valid'
    assert s3 == 'void'


def test_independent_communique_limits():
    """Each power has its own communique count limit."""
    game = _server_game_with_talk(talk_max_communiques_per_year=1)
    game.process()  # open round 1

    _, s1 = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'fr communique')
    _, s2 = _simulate_send_message(game, 'ENGLAND', 'GLOBAL', 'en communique')
    _, s3 = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'fr second')

    assert s1 == 'valid'
    assert s2 == 'valid'
    assert s3 == 'void'


# --- Void communiques still count ---

def test_void_communique_still_counts_against_quota():
    """A void communique (char limit) still increments the counter."""
    game = _server_game_with_talk(talk_max_communiques_per_year=2, talk_max_communique_chars=5)
    game.process()  # open round 1

    # First communique: too long -> void, but counts
    _, s1 = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Way too long')
    assert s1 == 'void'
    assert game.talk_communique_counts['FRANCE'] == 1

    # Second communique: valid length
    _, s2 = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'OK')
    assert s2 == 'valid'
    assert game.talk_communique_counts['FRANCE'] == 2

    # Third: over count limit
    _, s3 = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'No')
    assert s3 == 'void'
    assert 'limit exceeded' in game.talk_held_messages[-1]['void_reason']


# --- Communique counts persist across rounds within a season ---

def test_communique_counts_persist_across_rounds():
    """Communique counts don't reset between rounds within the same Talk phase."""
    game = _server_game_with_talk(talk_max_communiques_per_year=1)
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Used my communique')
    assert game.talk_communique_counts['FRANCE'] == 1

    game.process()  # close round 1, open round 2

    # Count should persist (communique is per-year, not per-round)
    assert game.talk_communique_counts['FRANCE'] == 1
    _, s2 = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Try again')
    assert s2 == 'void'


def test_communique_counts_persist_into_fall():
    """Communique counts from Spring persist into Fall Talk."""
    game = _server_game_with_talk(talk_max_communiques_per_year=1)
    game.process()  # Spring Talk, open round 1
    _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Spring communique')

    # Complete Spring Talk + Movement
    game.process()  # round 2
    game.process()  # orders_open
    game.process()  # -> Movement
    game.process()  # -> Fall Talk

    assert game.phase_type == 'T'
    assert game.current_short_phase.startswith('F')
    game.process()  # open Fall round 1

    # France already used their communique in Spring
    _, status = _simulate_send_message(game, 'FRANCE', 'GLOBAL', 'Fall communique')
    assert status == 'void'


# --- Mixed delivery ---

def test_mixed_valid_void_across_powers_on_delivery():
    """Multiple powers with mix of valid/void — only valid delivered."""
    game = _server_game_with_talk(talk_max_messages_per_round=1)
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'fr-valid')
    _simulate_send_message(game, 'FRANCE', 'GERMANY', 'fr-void')  # void
    _simulate_send_message(game, 'ENGLAND', 'FRANCE', 'en-valid')
    _simulate_send_message(game, 'ENGLAND', 'GERMANY', 'en-void')  # void

    game.process()  # close round 1, open round 2

    assert len(game.messages) == 2
    bodies = {msg.message for msg in game.messages.values()}
    assert bodies == {'fr-valid', 'en-valid'}


def test_communique_and_private_delivered_together():
    """Both private and communique messages delivered on same round close."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Private hello')
    _simulate_send_message(game, 'GERMANY', 'GLOBAL', 'Public hello')

    game.process()  # close round 1, open round 2

    assert len(game.messages) == 2
    recipients = {msg.recipient for msg in game.messages.values()}
    assert 'ENGLAND' in recipients
    assert 'GLOBAL' in recipients


# --- Full cycle integration ---

def test_full_talk_cycle_messages_in_both_rounds():
    """Messages from both rounds are all in game.messages after orders_open."""
    game = _server_game_with_talk()

    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'R1 from France')

    game.process()  # close round 1, open round 2
    assert len(game.messages) == 1

    _simulate_send_message(game, 'ENGLAND', 'FRANCE', 'R2 from England')

    game.process()  # close round 2, orders_open
    assert len(game.messages) == 2
    senders = {msg.sender for msg in game.messages.values()}
    assert senders == {'FRANCE', 'ENGLAND'}


def test_full_cycle_messages_in_history_after_movement():
    """After Talk→Movement, all Talk messages appear in message_history."""
    game = _server_game_with_talk()
    talk_phase = game.current_short_phase

    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'R1 msg')
    game.process()  # round 2
    _simulate_send_message(game, 'GERMANY', 'ITALY', 'R2 msg')
    game.process()  # orders_open
    game.process()  # -> Movement

    assert game.phase_type == 'M'
    assert talk_phase in game.message_history
    assert len(game.message_history[talk_phase]) == 2


def test_no_messages_carried_from_talk_to_movement():
    """game.messages is empty in Movement phase (messages archived to history)."""
    game = _server_game_with_talk()

    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Hello')
    game.process()  # round 2
    game.process()  # orders_open
    game.process()  # -> Movement

    assert game.phase_type == 'M'
    assert len(game.messages) == 0


# --- Serialization mid-cycle ---

def test_full_state_serialization_mid_cycle():
    """All talk state survives serialization mid-cycle."""
    game = _server_game_with_talk(
        talk_max_messages_per_round=3,
        talk_max_chars_per_message=200,
        talk_max_communiques_per_year=2,
        talk_max_communique_chars=100,
        talk_round_deadline=30,
        talk_orders_deadline=60,
    )
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Private')
    _simulate_send_message(game, 'GERMANY', 'GLOBAL', 'Communique')

    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)

    assert restored.talk_round == 1
    assert restored.talk_round_state == strings.ROUND_OPEN
    assert restored.talk_max_messages_per_round == 3
    assert restored.talk_max_chars_per_message == 200
    assert restored.talk_max_communiques_per_year == 2
    assert restored.talk_max_communique_chars == 100
    assert restored.talk_round_deadline == 30
    assert restored.talk_orders_deadline == 60
    assert restored.talk_message_counts == {'FRANCE': 1}
    assert restored.talk_communique_counts == {'GERMANY': 1}
    assert len(restored.talk_held_messages) == 2


def test_serialization_after_round_close_with_delivered():
    """After round close, delivered messages are in game.messages and survive serialization."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Test message')

    game.process()  # close round 1, open round 2

    game_dict = game.to_dict()
    restored = ServerGame.from_dict(game_dict)

    assert len(restored.messages) == 1
    assert list(restored.messages.values())[0].message == 'Test message'
    # Held messages should be empty (round 1 cleared)
    assert len(restored.talk_held_messages) == 0


# --- talk_num_rounds=1 with messages ---

def test_single_round_messages_delivered_at_orders_open():
    """With talk_num_rounds=1, messages from round 1 delivered when transitioning to orders_open."""
    game = _server_game_with_talk(talk_num_rounds=1)
    game.process()  # open round 1
    assert game.talk_round == 1
    assert game.talk_round_state == strings.ROUND_OPEN

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Only round')

    game.process()  # -> orders_open (round 1 closes since talk_num_rounds=1)
    assert game.talk_round_state == strings.ORDERS_OPEN
    assert len(game.messages) == 1
    assert list(game.messages.values())[0].message == 'Only round'


# --- Press log char_count accuracy ---

def test_press_log_char_count_accuracy():
    """Press log char_count matches actual message length."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    messages = ['Hi', 'A' * 100, '', 'Hello World!']
    for body in messages:
        _simulate_send_message(game, 'FRANCE', 'ENGLAND', body)

    game.process()  # close round 1

    assert len(game._last_press_log) == 4
    for i, entry in enumerate(game._last_press_log):
        assert entry['char_count'] == len(messages[i])


# --- Press log void entries have correct char_count ---

def test_press_log_void_entry_has_correct_char_count():
    """Void messages in press log still record the attempted char_count."""
    game = _server_game_with_talk(talk_max_chars_per_message=5)
    game.process()  # open round 1

    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Way too long message')

    game.process()  # close round 1

    assert len(game._last_press_log) == 1
    entry = game._last_press_log[0]
    assert entry['status'] == 'void'
    assert entry['char_count'] == len('Way too long message')


# --- Multi-year state reset ---

def test_multi_year_clean_state():
    """Talk state fully resets each Talk phase across multiple years."""
    game = _server_game_with_talk()

    for _ in range(2):
        # Spring Talk
        assert game.phase_type == 'T'
        assert game.talk_round == 0
        assert game.talk_round_state == ''
        assert game.talk_held_messages == []
        assert game.talk_message_counts == {}

        game.process()  # round 1
        _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'msg')
        game.process()  # round 2
        game.process()  # orders_open
        game.process()  # -> Movement
        game.process()  # -> Fall Talk

        # Fall Talk
        assert game.phase_type == 'T'
        assert game.talk_round == 0
        assert game.talk_round_state == ''
        assert game.talk_held_messages == []
        assert game.talk_message_counts == {}

        game.process()  # round 1
        game.process()  # round 2
        game.process()  # orders_open
        game.process()  # -> Movement
        game.process()  # -> next Spring Talk


# --- _generate_press_log isolation ---

def test_generate_press_log_only_current_round():
    """_generate_press_log only includes entries for the specified round."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'R1 msg')

    # Manually add a fake held message for round 99
    game.talk_held_messages.append({
        'sender': 'GERMANY', 'recipient': 'ITALY', 'phase': 'S1901T',
        'message': 'fake', 'round': 99, 'status': 'valid',
        'void_reason': '', 'type': 'private',
    })

    log = game._generate_press_log(1)
    assert len(log) == 1
    assert log[0]['sender'] == 'FRANCE'

    log99 = game._generate_press_log(99)
    assert len(log99) == 1
    assert log99[0]['sender'] == 'GERMANY'


# --- Blocked messages in round_closed state ---

def test_message_blocked_during_round_closed():
    """Messages cannot be sent when talk_round_state is round_closed."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    # Manually set to round_closed to test blocking
    game.talk_round_state = strings.ROUND_CLOSED

    try:
        _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Should fail')
        assert False, 'Should have raised'
    except RuntimeError as e:
        assert 'talk rounds' in str(e)


# --- Transient slots not in model ---

def test_transient_slots_not_serialized():
    """_last_delivered_messages, _last_closed_round, _last_press_log are not in serialized dict."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'Test')
    game.process()  # close round 1

    game_dict = game.to_dict()
    assert '_last_delivered_messages' not in game_dict
    assert '_last_closed_round' not in game_dict
    assert '_last_press_log' not in game_dict


# --- Notification parse_dict round-trip ---

def test_talk_round_update_parse_dict():
    """TalkRoundUpdate survives full parse_dict round-trip."""
    from diplomacy.communication import notifications as notifs
    notif = notifs.TalkRoundUpdate(
        token='tok', game_id='g1', game_role='FRANCE',
        talk_round=2, talk_round_state='round_open', talk_num_rounds=3,
    )
    d = notif.to_dict()
    restored = notifs.parse_dict(d)
    assert isinstance(restored, notifs.TalkRoundUpdate)
    assert restored.talk_round == 2
    assert restored.talk_round_state == 'round_open'
    assert restored.talk_num_rounds == 3


def test_talk_press_log_parse_dict():
    """TalkPressLog survives full parse_dict round-trip."""
    from diplomacy.communication import notifications as notifs
    entries = [{'sender': 'FRANCE', 'recipient': 'ENGLAND', 'char_count': 5, 'status': 'valid', 'type': 'private'}]
    notif = notifs.TalkPressLog(
        token='tok', game_id='g1', game_role='FRANCE',
        talk_round=1, entries=entries,
    )
    d = notif.to_dict()
    restored = notifs.parse_dict(d)
    assert isinstance(restored, notifs.TalkPressLog)
    assert restored.talk_round == 1
    assert len(restored.entries) == 1
    assert restored.entries[0]['sender'] == 'FRANCE'


# --- Five powers all active in same round ---

def test_five_powers_all_send_messages():
    """Five different powers each send messages in the same round."""
    game = _server_game_with_talk()
    game.process()  # open round 1

    powers = ['FRANCE', 'ENGLAND', 'GERMANY', 'ITALY', 'RUSSIA']
    for i, power in enumerate(powers):
        target = powers[(i + 1) % len(powers)]
        _simulate_send_message(game, power, target, 'Hello from %s' % power)

    assert len(game.talk_held_messages) == 5
    for power in powers:
        assert game.talk_message_counts[power] == 1

    game.process()  # close round 1
    assert len(game.messages) == 5
    delivered_senders = {msg.sender for msg in game.messages.values()}
    assert delivered_senders == set(powers)


# --- Press log after full cycle with no held messages remaining ---

def test_press_log_and_held_messages_clean_after_full_cycle():
    """After all rounds close, no held messages remain, and press log reflects last round."""
    game = _server_game_with_talk()
    game.process()  # open round 1
    _simulate_send_message(game, 'FRANCE', 'ENGLAND', 'R1')
    game.process()  # close round 1, open round 2
    _simulate_send_message(game, 'GERMANY', 'ITALY', 'R2')
    game.process()  # close round 2, orders_open

    # Held messages cleared
    assert len(game.talk_held_messages) == 0
    # Press log from round 2
    assert len(game._last_press_log) == 1
    assert game._last_press_log[0]['sender'] == 'GERMANY'
