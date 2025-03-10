from .common import MessageProtocol, NetworkNodeProtocol, Peer, PeerPluginProtocol
from .crypto import encrypt, decrypt
from hashlib import sha256
from random import randint


class Sha256StreamCipherPlugin:
    """SHA-256 stream cipher plugin."""
    key: bytes
    iv_field: str
    encrypt_uri: bool

    def __init__(self, config: dict):
        """Initialize the cipher plugin with a config. The config
            must contain {"key": <str|bytes>}. It can contain {"iv_field":
            <str>} to specify the auth field name for the iv; the
            default is "iv". It can contain {"encrypt_uri": <bool>} to
            specify whether to encrypt the uri; the default is True.
        """
        key = config['key']
        self.key = sha256(key.encode() if isinstance(key, str) else key).digest()
        self.iv_field = config.get('iv_field', 'iv')
        self.encrypt_uri = config.get('encrypt_uri', True)

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
        plaintext = b''
        if self.encrypt_uri:
            plaintext += message.body.uri_length.to_bytes(2, 'big')
            plaintext += message.body.uri
        plaintext += message.body.content
        iv, ciphertext = encrypt(self.key, plaintext)
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
        auth_data = message.auth_data.fields.copy()
        auth_data[self.iv_field] = iv
        auth_data = message.auth_data.__class__(auth_data)
        body = message.body.prepare(content, uri)
        return message.prepare(body, message_type, auth_data)

    def decrypt(
            self, message: MessageProtocol,
            node: NetworkNodeProtocol|None = None, peer: Peer|None = None,
            peer_plugin: PeerPluginProtocol|None = None
        ) -> MessageProtocol:
        """Decrypt the message body, reading the self.iv_field from
            the auth_data. Returns a new message with the decrypted body.
        """
        iv = message.auth_data.fields[self.iv_field]

        if self.encrypt_uri:
            if node is not None:
                node.logger.debug('Decrypting URI and content')
            ciphertext = message.body.uri + message.body.content
        else:
            if node is not None:
                node.logger.debug('Decrypting content')
            ciphertext = message.body.content
        content = decrypt(self.key, iv, ciphertext)
        if self.encrypt_uri:
            uri_len = int.from_bytes(content[:2], 'big')
            uri = content[2:uri_len+2]
            content = content[uri_len+2:]
        else:
            uri = message.body.uri

        message_type = message.header.message_type
        auth_data = message.auth_data.fields.copy()
        auth_data = message.auth_data.__class__(auth_data)
        body = message.body.prepare(content, uri)
        return message.prepare(body, message_type, auth_data)
