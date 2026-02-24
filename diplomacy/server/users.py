# ==============================================================================
# Copyright (C) 2019 - Philip Paquette, Steven Bocco
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
""" Helper class to manage user accounts and connections on server side.

    Tokens are JWTs signed by the server. The server does not store token state —
    validity is determined by signature verification and expiry claims.

    Each connected token is associated to at most 1 connection handler (in-memory only).
    A revocation set tracks explicitly invalidated tokens (e.g. logout).
"""
import logging

import jwt as pyjwt

from diplomacy.server.user import User
from diplomacy.utils import parsing, strings
from diplomacy.utils.jsonable import Jsonable
from diplomacy.utils.token import decode_token, get_username, get_token_id

LOGGER = logging.getLogger(__name__)


class Users(Jsonable):
    """ Users class.

        Properties:

        - **users**: dictionary mapping usernames to User objects.
        - **administrators**: set of administrator usernames.
        - **revoked_tokens**: set of token IDs (jti) that have been explicitly revoked.
        - **token_to_connection_handler**: (memory only) dictionary mapping each token to a connection handler
        - **connection_handler_to_tokens**: (memory only) dictionary mapping a connection handler to a set of its tokens
    """
    __slots__ = ['users', 'administrators', 'revoked_tokens',
                 'token_to_connection_handler', 'connection_handler_to_tokens',
                 '_secret_key']
    model = {
        strings.USERS: parsing.DefaultValueType(parsing.DictType(str, parsing.JsonableClassType(User)), {}),
        strings.ADMINISTRATORS: parsing.DefaultValueType(parsing.SequenceType(str, sequence_builder=set), ()),
        strings.REVOKED_TOKENS: parsing.DefaultValueType(parsing.SequenceType(str, sequence_builder=set), ()),
    }

    def __init__(self, **kwargs):
        self.users = {}
        self.administrators = set()
        self.revoked_tokens = set()
        self.token_to_connection_handler = {}
        self.connection_handler_to_tokens = {}
        self._secret_key = None
        super(Users, self).__init__(**kwargs)

    def set_secret_key(self, secret_key):
        """ Set the JWT signing key. Must be called before any token operations. """
        self._secret_key = secret_key

    def has_username(self, username):
        """ Return True if users have given username. """
        return username in self.users

    def has_user(self, username, password):
        """ Return True if users have given username with given password. """
        return username in self.users and self.users[username].is_valid_password(password)

    def has_admin(self, username):
        """ Return True if given username is an administrator. """
        return username in self.administrators

    def has_token(self, token):
        """ Return True if token is a valid, non-expired, non-revoked JWT
            for a known username.
        """
        try:
            payload = decode_token(self._secret_key, token)
            if payload['jti'] in self.revoked_tokens:
                return False
            return payload['sub'] in self.users
        except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
            return False

    def get_name(self, token):
        """ Return username from JWT claims. """
        return get_username(self._secret_key, token)

    def token_is_alive(self, token):
        """ Return True if token is valid and not expired.
            With JWTs, expiry is encoded in the token itself.
        """
        return self.has_token(token)

    def relaunch_token(self, token):
        """ No-op for JWTs. Expiry is fixed at creation time.
            To extend a session, the client should request a new token.
        """

    def token_is_admin(self, token):
        """ Return True if given token is associated to an administrator. """
        return self.has_token(token) and self.has_admin(self.get_name(token))

    def count_connections(self):
        """ Return number of registered connection handlers. """
        return len(self.connection_handler_to_tokens)

    def get_tokens(self, username):
        """ Return a set of active tokens for the given username.
            Scans connection handlers since tokens are not tracked server-side.
        """
        tokens = set()
        for token in self.token_to_connection_handler:
            try:
                if get_username(self._secret_key, token) == username:
                    tokens.add(token)
            except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
                continue
        return tokens

    def get_user(self, username):
        """ Returns user linked to username """
        return self.users.get(username, None)

    def get_connection_handler(self, token):
        """ Return connection handler associated to given token, or None if no handler currently associated. """
        return self.token_to_connection_handler.get(token, None)

    def add_admin(self, username):
        """ Set given username as administrator. Related user must exists in this Users object. """
        assert username in self.users
        self.administrators.add(username)

    def remove_admin(self, username):
        """ Remove given username from administrators. """
        if username in self.administrators:
            self.administrators.remove(username)

    def add_user(self, username, password_hash):
        """ Add a new user with given username and hashed password. """
        user = User(username=username, password_hash=password_hash)
        self.users[username] = user
        return user

    def replace_user(self, username, new_user):
        """ Replaces user object with a new user """
        self.users[username] = new_user

    def remove_user(self, username):
        """ Remove user related to given username. """
        self.users.pop(username)
        self.remove_admin(username)
        # Remove any active connections for this user
        tokens_to_remove = set()
        for token in list(self.token_to_connection_handler):
            try:
                if get_username(self._secret_key, token) == username:
                    tokens_to_remove.add(token)
            except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
                tokens_to_remove.add(token)
        for token in tokens_to_remove:
            self.disconnect_token(token)

    def remove_connection(self, connection_handler, remove_tokens=True):
        """ Remove given connection handler.
            Return tokens associated to this connection handler,
            or None if connection handler is unknown.

            :param connection_handler: connection handler to remove.
            :param remove_tokens: if True, tokens are revoked.
            :return: either None or a set of tokens.
        """
        if connection_handler in self.connection_handler_to_tokens:
            tokens = self.connection_handler_to_tokens.pop(connection_handler)
            for token in tokens:
                self.token_to_connection_handler.pop(token, None)
                if remove_tokens:
                    try:
                        jti = get_token_id(token)
                        self.revoked_tokens.add(jti)
                    except (pyjwt.InvalidTokenError, KeyError):
                        pass
            return tokens
        return None

    def connect_user(self, username, connection_handler, token):
        """ Register a token (JWT) for the given username and connection handler.

            :param username: username to connect
            :param connection_handler: connection handler to link to user
            :param token: the JWT token string
            :return: the token
        """
        if connection_handler not in self.connection_handler_to_tokens:
            self.connection_handler_to_tokens[connection_handler] = set()
        self.token_to_connection_handler[token] = connection_handler
        self.connection_handler_to_tokens[connection_handler].add(token)
        return token

    def attach_connection_handler(self, token, connection_handler):
        """ Associate given token with given connection handler.

            :param token: token (JWT string)
            :param connection_handler: connection handler
        """
        if self.has_token(token):
            previous_connection = self.get_connection_handler(token)
            if previous_connection:
                assert previous_connection == connection_handler, \
                    "A new connection handler cannot be attached to a token always connected to another handler."
            else:
                LOGGER.warning('Attaching a new connection handler to a token.')
                if connection_handler not in self.connection_handler_to_tokens:
                    self.connection_handler_to_tokens[connection_handler] = set()
                self.token_to_connection_handler[token] = connection_handler
                self.connection_handler_to_tokens[connection_handler].add(token)

    def disconnect_token(self, token):
        """ Revoke and disconnect given token. """
        try:
            jti = get_token_id(token)
            self.revoked_tokens.add(jti)
        except (pyjwt.InvalidTokenError, KeyError):
            pass
        connection_handler = self.token_to_connection_handler.pop(token, None)
        if connection_handler and connection_handler in self.connection_handler_to_tokens:
            self.connection_handler_to_tokens[connection_handler].discard(token)
            if not self.connection_handler_to_tokens[connection_handler]:
                self.connection_handler_to_tokens.pop(connection_handler)
