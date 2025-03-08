from .common import (
    HeaderProtocol,
    AuthFieldsProtocol,
    BodyProtocol,
    MessageProtocol,
    make_error_response,
    Message,
    MessageType,
    Header,
    AuthFields,
    Body
)
from .crypto import sha256, hmac, check_hmac, IV_SIZE
from enum import IntEnum
from os import urandom
from time import time


class HMACAuthPlugin:
    """HMAC auth plugin."""
    secret: bytes
    nonce_field: str
    ts_field: str
    hmac_field: str

    def __init__(self, config: dict):
        """Initialize the HMAC auth plugin with a config. The config
            must contain {"secret": <str|bytes>}. It can contain
            {"hmac_field": <str>} to specify the auth field name for the
            hmac; the default is "hmac". It can contain {"nonce_field":
            <str>} to specify the auth field name for the nonce; the
            default is "nonce". It can contain {"ts_field": <str>} to
            specify the auth field name for the timestamp; the default is
            "ts".
        """
        secret = config["secret"]
        if isinstance(secret, str):
            secret = secret.encode()
        self.secret = sha256(secret).digest()
        self.hmac_field = config.get("hmac_field", "hmac")
        self.nonce_field = config.get("nonce_field", "nonce")
        self.ts_field = config.get("ts_field", "ts")

    def make(self, auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> None:
        """If the nonce and ts fields are not set, generate them. If the
            nonce is not the IV_SIZE, generate a new one. Then, create
            an hmac of the nonce, ts, and body and store it in the
            auth_data field specified by the "hmac_field" config option;
            the default is "hmac".
        """
        nonce = auth_fields.fields.get(self.nonce_field, b'')
        if len(nonce) != IV_SIZE:
            nonce = urandom(IV_SIZE)
        ts = auth_fields.fields.get(self.ts_field, int(time()))
        auth_fields.fields.update({
            self.nonce_field: nonce,
            self.ts_field: ts,
            self.hmac_field: hmac(self.secret, nonce + ts.to_bytes(4, "big") + body.encode())
        })

    def check(self, auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> bool:
        """Check if the auth fields are valid for the given body.
            Performs an hmac check on the nonce, ts, and body. Returns
            False if any of the fields are missing or if the hmac check
            fails.
        """
        ts = auth_fields.fields.get(self.ts_field, 0)
        nonce = auth_fields.fields.get(self.nonce_field, None)
        mac = auth_fields.fields.get(self.hmac_field, None)
        if ts == 0 or nonce is None or mac is None:
            return False
        return check_hmac(
            self.secret,
            nonce + ts.to_bytes(4, "big") + body.encode(),
            mac
        )

    def error(
            self,
            message_class: type[MessageProtocol] = Message,
            message_type_class: type[IntEnum] = MessageType,
            header_class: type[HeaderProtocol] = Header,
            auth_fields_class: type[AuthFieldsProtocol] = AuthFields,
            body_class: type[BodyProtocol] = Body
        ) -> MessageProtocol:
        """Make an error message that says "HMAC auth failed"."""
        return make_error_response(
            "HMAC auth failed",
            message_class=message_class,
            message_type_class=message_type_class,
            body_class=body_class
        )
