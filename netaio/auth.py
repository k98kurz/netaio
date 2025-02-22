from .common import (
    BodyProtocol,
    AuthFieldsProtocol,
    AuthFields,
    MessageProtocol,
    make_error_response
)
from .crypto import sha256, hmac, check_hmac, IV_SIZE
from os import urandom
from time import time
from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthPluginProtocol(Protocol):
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
        secret = config["secret"]
        if isinstance(secret, str):
            secret = secret.encode()
        self.secret = sha256(secret).digest()

    def make(self, auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> None:
        nonce = auth_fields.fields.get("nonce", b'')
        if len(nonce) != IV_SIZE:
            nonce = urandom(IV_SIZE)
        ts = int(time())
        auth_fields.fields.update({
            "nonce": nonce,
            "ts": ts,
            "hmac": hmac(self.secret, nonce + ts.to_bytes(4, "big") + body.encode())
        })

    def check(self, auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> bool:
        ts = auth_fields.fields.get("ts", 0)
        if ts == 0:
            return False
        return check_hmac(
            self.secret,
            auth_fields.fields["nonce"] + ts.to_bytes(4, "big") + body.encode(),
            auth_fields.fields["hmac"]
        )

    def error(self) -> MessageProtocol:
        return make_error_response("HMAC auth failed")
