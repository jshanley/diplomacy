""" JWT token utilities for server authentication.

    Tokens are JWTs signed with HMAC-SHA256 carrying:
    - sub: username
    - iat: issued-at timestamp
    - exp: expiry timestamp
    - jti: unique token ID (for connection handler mapping)
"""
import os
import time
import uuid

import jwt

# Default token lifetime: 24 hours
TOKEN_LIFETIME_SECONDS = 24 * 60 * 60

# Algorithm for signing
_ALGORITHM = 'HS256'


def generate_secret_key():
    """ Generate a random 256-bit secret key for JWT signing. """
    return os.urandom(32)


def create_token(secret_key, username, lifetime_seconds=TOKEN_LIFETIME_SECONDS):
    """ Create a signed JWT for the given username.

        :param secret_key: bytes used as HMAC signing key
        :param username: the username to embed in the token
        :param lifetime_seconds: token validity duration in seconds
        :return: encoded JWT string
        :rtype: str
    """
    now = time.time()
    payload = {
        'sub': username,
        'iat': now,
        'exp': now + lifetime_seconds,
        'jti': str(uuid.uuid4()),
    }
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def decode_token(secret_key, token):
    """ Decode and verify a JWT, returning its claims.

        :param secret_key: bytes used as HMAC signing key
        :param token: encoded JWT string
        :return: decoded payload dict with keys: sub, iat, exp, jti
        :raises jwt.ExpiredSignatureError: if token has expired
        :raises jwt.InvalidTokenError: if token is malformed or signature is invalid
    """
    return jwt.decode(token, secret_key, algorithms=[_ALGORITHM])


def get_username(secret_key, token):
    """ Extract the username from a JWT without full validation.
        Uses decode with verification to ensure the token is valid.

        :param secret_key: bytes used as HMAC signing key
        :param token: encoded JWT string
        :return: username
        :rtype: str
    """
    payload = decode_token(secret_key, token)
    return payload['sub']


def get_token_id(token):
    """ Extract the jti (unique token ID) from a JWT without verification.
        Used for connection handler mapping where we need a stable key.

        :param token: encoded JWT string
        :return: jti claim value
        :rtype: str
    """
    payload = jwt.decode(token, options={'verify_signature': False})
    return payload['jti']
