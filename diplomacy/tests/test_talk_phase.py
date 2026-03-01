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
    from diplomacy.utils import strings
    return ServerGame(status=strings.ACTIVE, rules=rules, **kwargs)


def _server_game_with_controlled_powers(**kwargs):
    """Helper: create a ServerGame with Talk enabled and two controlled powers."""
    from diplomacy.utils import strings
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
