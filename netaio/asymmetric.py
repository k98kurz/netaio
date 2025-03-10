from .common import (
    HeaderProtocol,
    AuthFieldsProtocol,
    BodyProtocol,
    MessageProtocol,
    NetworkNodeProtocol,
    CipherPluginProtocol,
    PeerPluginProtocol,
    make_error_response,
    Message,
    MessageType,
    Header,
    AuthFields,
    Body,
    Peer,
)
from enum import IntEnum
from nacl.public import PrivateKey, Box
from nacl.signing import SigningKey, VerifyKey
from os import urandom
from time import time
from typing import Callable
import tapescript


class TapescriptAuthPlugin:
    """Tapescript auth plugin."""
    lock: tapescript.Script
    seed: bytes
    nonce_field: str
    ts_field: str
    use_peer_lock: bool
    witness_field: str
    witness_func: Callable[[bytes, dict[str, bytes]], tapescript.Script|bytes]
    contracts: dict
    plugins: dict

    def __init__(self, config: dict):
        """Initialize the auth plugin with a config. The config should
            contain {"lock": <tapescript.Script>, "seed": <bytes>}.
            It can contain {"nonce_field": <str>} to specify the auth
            field name for the nonce; default is "nonce".
            It can contain {"witness_field": <str>} to specify the auth
            field name for the witness script; default is "witness".
            It can contain {"ts_field": <str>} to specify the auth field
            name for the Unix epoch timestamp; the default is "ts".
            It can contain {"use_peer_lock": <bool>} to specify whether
            to use the peer's locking script instead of the plugin's;
            the default is False.
            It can contain {"witness_func": <Callable>} to specify a
            Callable for making witness scripts, which must accept the
            seed and a sigfields dict with the encoded message body as
            sigfield1, the nonce as sigfield2, and the timestamp as
            sigfield3, and it must return a tapescript.Script or bytes.
            It can contain {"contracts": <dict>} and/or
            {"plugins": <dict>} to pass to the tapescript runtime.
            By default, this will assume a single-signature scheme and
            use the tapescript.make_single_sig_witness tool to create
            witnesses.
        """
        if 'seed' not in config:
            raise ValueError("'seed' must be provided in the config")
        if 'lock' not in config:
            raise ValueError("'lock' must be provided in the config")
        self.lock = config['lock']
        self.seed = config['seed']
        self.nonce_field = config.get('nonce_field', 'nonce')
        self.ts_field = config.get('ts_field', 'ts')
        self.witness_field = config.get('witness_field', 'witness')
        self.use_peer_lock = config.get('use_peer_lock', False)
        self.witness_func = config.get('make', tapescript.make_single_sig_witness)
        self.contracts = config.get('contracts', {})
        self.plugins = config.get('plugins', {})

    def make(
            self, auth_fields: AuthFieldsProtocol, body: BodyProtocol,
            node: NetworkNodeProtocol|None = None, peer: Peer|None = None,
            peer_plugin: PeerPluginProtocol|None = None,
        ) -> None:
        """If the nonce and ts fields are not set, generate them. Then,
            call the witness function with the seed and the sigfields
            dict to produce a witness.
        """
        nonce = auth_fields.fields.get(self.nonce_field, urandom(16))
        ts = auth_fields.fields.get(self.ts_field, int(time()))
        witness = self.witness_func(
            self.seed,
            {
                'sigfield1': body.encode(),
                'sigfield2': nonce,
                'sigfield3': ts.to_bytes(4, 'big'),
            },
        )
        auth_fields.fields.update({
            self.nonce_field: nonce,
            self.ts_field: ts,
            self.witness_field: bytes(witness),
        })

    def check(
            self, auth_fields: AuthFieldsProtocol, body: BodyProtocol,
            node: NetworkNodeProtocol|None = None, peer: Peer|None = None,
            peer_plugin: PeerPluginProtocol|None = None,
        ) -> bool:
        """Check the witness script. If the peer is set, and the
            peer_plugin parses peer.data to a dict containing a "lock",
            and self.use_peer_lock is True, that locking script will be
            used instead of the plugin's locking script.
        """
        ts = auth_fields.fields.get(self.ts_field, 0)
        nonce = auth_fields.fields.get(self.nonce_field, None)
        witness = auth_fields.fields.get(self.witness_field, None)
        if ts == 0 or nonce is None or witness is None:
            return False

        lock = self.lock
        if peer is not None and self.use_peer_lock:
            peer_data = peer_plugin.parse_data(peer)
            if 'lock' in peer_data:
                lock = peer_data['lock']

        return tapescript.run_auth_script(
            bytes(witness) + bytes(lock),
            {
                'sigfield1': body.encode(),
                'sigfield2': nonce,
                'sigfield3': ts.to_bytes(4, 'big'),
            },
            self.contracts,
            self.plugins,
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
            "tapescript auth failed",
            message_class=message_class,
            message_type_class=message_type_class,
            body_class=body_class
        )
