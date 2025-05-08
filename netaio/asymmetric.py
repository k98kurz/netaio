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
from random import randint
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
        self.witness_func = config.get(
            'witness_func', tapescript.make_single_sig_witness
        )
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
            self.witness_field: witness.bytes,
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

        return tapescript.run_auth_scripts(
            [bytes(witness), bytes(lock)],
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


class X25519CipherPlugin(CipherPluginProtocol):
    """X25519 cipher plugin."""
    key: PrivateKey
    encrypt_uri: bool

    def __init__(self, config: dict):
        """Initialize the cipher plugin with a config. The config
            must contain {"seed": <bytes>}.
            It can contain {"encrypt_uri": <bool>} to specify whether to
            encrypt the uri; the default is False.
        """
        seed = config['seed']
        self.key = SigningKey(seed).to_curve25519_private_key()
        self.encrypt_uri = config.get('encrypt_uri', False)

    def encrypt(
            self, message: MessageProtocol,
            node: NetworkNodeProtocol|None = None, peer: Peer|None = None,
            peer_plugin: PeerPluginProtocol|None = None
        ) -> MessageProtocol:
        """Encrypt the message body, setting the self.iv_field in the
            auth_data. This will overwrite any existing value in that
            auth_data field. If the self.encrypt_uri is True, the uri
            will be encrypted as well as the content.
        """
        if peer is None or peer_plugin is None:
            raise ValueError("peer and peer_plugin must be provided")

        plaintext = b''
        if self.encrypt_uri:
            plaintext += message.body.uri_length.to_bytes(2, 'big')
            plaintext += message.body.uri
        plaintext += message.body.content

        peer_data = peer_plugin.parse_data(peer)
        if 'pubkey' not in peer_data:
            raise ValueError("peer pubkey not found")
        pubkey = VerifyKey(peer_data['pubkey']).to_curve25519_public_key()
        ciphertext = Box(self.key, pubkey).encrypt(plaintext)

        if self.encrypt_uri:
            uri_len = randint(1, len(ciphertext)-1)
            if node is not None:
                node.logger.debug('Encrypting URI and content')
            uri = ciphertext[:uri_len]
            content = ciphertext[uri_len:]
        else:
            if node is not None:
                node.logger.debug('Encrypting content')
            uri = message.body.uri
            content = ciphertext

        message_type = message.header.message_type
        body = message.body.prepare(content, uri)
        return message.prepare(body, message_type, message.auth_data)

    def decrypt(
            self, message: MessageProtocol,
            node: NetworkNodeProtocol|None = None, peer: Peer|None = None,
            peer_plugin: PeerPluginProtocol|None = None
        ) -> MessageProtocol:
        """Decrypt the message body, reading the self.iv_field from
            the auth_data. Returns a new message with the decrypted body.
        """
        if peer is None or peer_plugin is None:
            raise ValueError("peer and peer_plugin must be provided")

        if self.encrypt_uri:
            if node is not None:
                node.logger.debug('Decrypting URI and content')
            ciphertext = message.body.uri + message.body.content
        else:
            if node is not None:
                node.logger.debug('Decrypting content')
            ciphertext = message.body.content

        peer_data = peer_plugin.parse_data(peer)
        if 'pubkey' not in peer_data:
            raise ValueError("peer pubkey not found")
        pubkey = VerifyKey(peer_data['pubkey']).to_curve25519_public_key()
        content = Box(self.key, pubkey).decrypt(ciphertext)

        if self.encrypt_uri:
            uri_len = int.from_bytes(content[:2], 'big')
            uri = content[2:uri_len+2]
            content = content[uri_len+2:]
        else:
            uri = message.body.uri

        message_type = message.header.message_type
        body = message.body.prepare(content, uri)
        return message.prepare(body, message_type, message.auth_data)
