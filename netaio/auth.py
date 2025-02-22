from .common import (
    BodyProtocol,
    AuthFieldsProtocol,
    MessageProtocol,
    make_error_response
)
from .crypto import sha256, hmac, check_hmac, IV_SIZE
from os import urandom
from time import time
from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthPluginProtocol(Protocol):
    """Shows what an auth plugin should do."""
    def __init__(self, config: dict):
        """Initialize the auth plugin with a config."""
        ...

    def make(self, auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> None:
        """Set auth_fields appropriate for a given body."""
        ...

    def check(self, auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> bool:
        """Check if the auth fields are valid for the given body."""
        ...

    def error(self) -> MessageProtocol:
        """Make an error message."""
        ...


class HMACAuthPlugin:
    """HMAC auth plugin."""
    secret: bytes

    def __init__(self, config: dict):
        """Initialize the HMAC auth plugin with a config. The config
            must contain {"secret": <str|bytes>}.
        """
        secret = config["secret"]
        if isinstance(secret, str):
            secret = secret.encode()
        self.secret = sha256(secret).digest()

    def make(self, auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> None:
        """If the nonce and ts fields are not present, generate them.
            Then, create an hmac of the nonce, ts, and body and store it
            in the hmac field.
        """
        nonce = auth_fields.fields.get("nonce", b'')
        if len(nonce) != IV_SIZE:
            nonce = urandom(IV_SIZE)
        ts = auth_fields.fields.get("ts", int(time()))
        auth_fields.fields.update({
            "nonce": nonce,
            "ts": ts,
            "hmac": hmac(self.secret, nonce + ts.to_bytes(4, "big") + body.encode())
        })

    def check(self, auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> bool:
        """Check if the auth fields are valid for the given body.
            Performs an hmac check on the nonce, ts, and body. Returns
            False if any of the fields are missing or if the hmac check
            fails.
        """
        ts = auth_fields.fields.get("ts", 0)
        nonce = auth_fields.fields.get("nonce", None)
        mac = auth_fields.fields.get("hmac", None)
        if ts == 0 or nonce is None or mac is None:
            return False
        return check_hmac(
            self.secret,
            nonce + ts.to_bytes(4, "big") + body.encode(),
            mac
        )

    def error(self) -> MessageProtocol:
        """Make an error message that says "HMAC auth failed"."""
        return make_error_response("HMAC auth failed")
