""" Player log storage — persists per-player filtered game phase data.

    Each player's game history is stored as a JSONL file:
        data/player_logs/<username>/<game_id>.jsonl

    One JSON line per phase, containing the GamePhaseData that the player
    was allowed to see at that point in the game.
"""
import os
import logging

import ujson as json

LOGGER = logging.getLogger(__name__)


class PlayerLog:
    """ Manages per-player game log storage. """
    __slots__ = ['logs_path']

    def __init__(self, data_path):
        self.logs_path = os.path.join(data_path, 'player_logs')
        os.makedirs(self.logs_path, exist_ok=True)

    def _user_dir(self, username):
        """ Return the log directory for a given username, creating it if needed. """
        user_dir = os.path.join(self.logs_path, username)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def _game_log_path(self, username, game_id):
        """ Return the JSONL file path for a given user+game. """
        return os.path.join(self._user_dir(username), '%s.jsonl' % game_id)

    def append_phase(self, username, game_id, phase_data_dict):
        """ Append a phase data dict (already filtered for this player) to the log.

            :param username: player username
            :param game_id: game ID
            :param phase_data_dict: dict from GamePhaseData.to_dict()
        """
        log_path = self._game_log_path(username, game_id)
        with open(log_path, 'a') as log_file:
            log_file.write(json.dumps(phase_data_dict))
            log_file.write('\n')

    def get_game_log(self, username, game_id, limit=None, offset=0):
        """ Read phase data entries for a given user+game.

            :param username: player username
            :param game_id: game ID
            :param limit: max number of entries to return (None = all)
            :param offset: number of entries to skip from the start
            :return: list of phase data dicts
            :rtype: list
        """
        log_path = self._game_log_path(username, game_id)
        if not os.path.exists(log_path):
            return []
        entries = []
        with open(log_path, 'r') as log_file:
            for i, line in enumerate(log_file):
                if i < offset:
                    continue
                if limit is not None and len(entries) >= limit:
                    break
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def list_game_ids(self, username):
        """ List all game IDs that have logs for a given user.

            :param username: player username
            :return: list of game ID strings
            :rtype: list
        """
        user_dir = os.path.join(self.logs_path, username)
        if not os.path.isdir(user_dir):
            return []
        return [f[:-6] for f in os.listdir(user_dir) if f.endswith('.jsonl')]
