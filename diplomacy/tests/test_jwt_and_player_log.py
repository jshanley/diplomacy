""" Tests for JWT token authentication and player log system. """
import os
import time
import tempfile

from diplomacy.utils.token import (
    create_token, decode_token, get_username, get_token_id, generate_secret_key, TOKEN_LIFETIME_SECONDS
)
from diplomacy.server.player_log import PlayerLog

import jwt as pyjwt


# ==================
# JWT Token Tests
# ==================

def test_create_and_decode_token():
    """ A created JWT can be decoded and contains expected claims. """
    key = generate_secret_key()
    token = create_token(key, 'alice')
    payload = decode_token(key, token)
    assert payload['sub'] == 'alice'
    assert 'iat' in payload
    assert 'exp' in payload
    assert 'jti' in payload
    assert payload['exp'] - payload['iat'] == TOKEN_LIFETIME_SECONDS

def test_get_username():
    """ get_username extracts the subject from a valid JWT. """
    key = generate_secret_key()
    token = create_token(key, 'bob')
    assert get_username(key, token) == 'bob'

def test_get_token_id():
    """ get_token_id extracts the jti without verification. """
    key = generate_secret_key()
    token = create_token(key, 'carol')
    jti = get_token_id(token)
    assert isinstance(jti, str)
    assert len(jti) > 0

def test_unique_jti():
    """ Each token gets a unique jti. """
    key = generate_secret_key()
    t1 = create_token(key, 'alice')
    t2 = create_token(key, 'alice')
    assert get_token_id(t1) != get_token_id(t2)

def test_expired_token():
    """ A token created with 0 lifetime expires immediately. """
    key = generate_secret_key()
    token = create_token(key, 'dave', lifetime_seconds=0)
    time.sleep(0.1)
    try:
        decode_token(key, token)
        assert False, 'Should have raised ExpiredSignatureError'
    except pyjwt.ExpiredSignatureError:
        pass

def test_wrong_key_rejected():
    """ A token signed with one key cannot be verified with a different key. """
    key1 = generate_secret_key()
    key2 = generate_secret_key()
    token = create_token(key1, 'eve')
    try:
        decode_token(key2, token)
        assert False, 'Should have raised InvalidSignatureError'
    except pyjwt.InvalidTokenError:
        pass

def test_token_is_string():
    """ Token is a plain string suitable for use as dict key and in sets. """
    key = generate_secret_key()
    token = create_token(key, 'frank')
    assert isinstance(token, str)
    # Usable as dict key
    d = {token: 'value'}
    assert d[token] == 'value'
    # Usable in set
    s = {token}
    assert token in s


# ==================
# Player Log Tests
# ==================

def _make_phase_data(name, power_orders=None):
    """ Helper to create a minimal phase data dict. """
    return {
        'name': name,
        'state': {'name': name, 'units': {}},
        'orders': power_orders or {},
        'results': {},
        'messages': {},
    }

def test_player_log_append_and_read():
    """ Appended phase data can be read back. """
    with tempfile.TemporaryDirectory() as tmpdir:
        log = PlayerLog(tmpdir)
        phase1 = _make_phase_data('S1901M', {'FRANCE': ['A PAR - BUR']})
        phase2 = _make_phase_data('F1901M', {'FRANCE': ['A BUR - MUN']})
        log.append_phase('alice', 'game1', phase1)
        log.append_phase('alice', 'game1', phase2)
        entries = log.get_game_log('alice', 'game1')
        assert len(entries) == 2
        assert entries[0]['name'] == 'S1901M'
        assert entries[1]['name'] == 'F1901M'

def test_player_log_limit_offset():
    """ limit and offset work correctly. """
    with tempfile.TemporaryDirectory() as tmpdir:
        log = PlayerLog(tmpdir)
        for i in range(5):
            log.append_phase('bob', 'game2', _make_phase_data('phase_%d' % i))
        # limit
        entries = log.get_game_log('bob', 'game2', limit=2)
        assert len(entries) == 2
        assert entries[0]['name'] == 'phase_0'
        # offset
        entries = log.get_game_log('bob', 'game2', offset=3)
        assert len(entries) == 2
        assert entries[0]['name'] == 'phase_3'
        # limit + offset
        entries = log.get_game_log('bob', 'game2', limit=1, offset=2)
        assert len(entries) == 1
        assert entries[0]['name'] == 'phase_2'

def test_player_log_list_game_ids():
    """ list_game_ids returns all games a user has logs for. """
    with tempfile.TemporaryDirectory() as tmpdir:
        log = PlayerLog(tmpdir)
        log.append_phase('carol', 'gameA', _make_phase_data('S1901M'))
        log.append_phase('carol', 'gameB', _make_phase_data('S1901M'))
        game_ids = sorted(log.list_game_ids('carol'))
        assert game_ids == ['gameA', 'gameB']

def test_player_log_empty():
    """ Reading a non-existent log returns empty list. """
    with tempfile.TemporaryDirectory() as tmpdir:
        log = PlayerLog(tmpdir)
        assert log.get_game_log('nobody', 'noGame') == []
        assert log.list_game_ids('nobody') == []

def test_player_log_separate_users():
    """ Different users have separate logs even for the same game. """
    with tempfile.TemporaryDirectory() as tmpdir:
        log = PlayerLog(tmpdir)
        log.append_phase('alice', 'game1', _make_phase_data('S1901M', {'FRANCE': ['A PAR H']}))
        log.append_phase('bob', 'game1', _make_phase_data('S1901M', {'ENGLAND': ['F LON H']}))
        alice_log = log.get_game_log('alice', 'game1')
        bob_log = log.get_game_log('bob', 'game1')
        assert len(alice_log) == 1
        assert len(bob_log) == 1
        assert alice_log[0]['orders'] == {'FRANCE': ['A PAR H']}
        assert bob_log[0]['orders'] == {'ENGLAND': ['F LON H']}
