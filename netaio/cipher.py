from .common import MessageProtocol
from .crypto import encrypt, decrypt
from hashlib import sha256


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

    def encrypt(self, message: MessageProtocol) -> MessageProtocol:
        """Encrypt the message body, setting the self.iv_field in the
            auth_data. This will overwrite any existing value in that
            auth_data field. If the self.encrypt_uri is True, the uri
            will be encrypted as well as the content.
        """
        plaintext = b''
        if self.encrypt_uri:
            plaintext += message.body.uri
        plaintext += message.body.content
        iv, ciphertext = encrypt(self.key, plaintext)
        if self.encrypt_uri:
            uri = ciphertext[:len(message.body.uri)]
            content = ciphertext[len(message.body.uri):]
        else:
            uri = message.body.uri
            content = ciphertext

        message_type = message.header.message_type
        auth_data = message.auth_data.fields.copy()
        auth_data[self.iv_field] = iv
        auth_data = message.auth_data.__class__(auth_data)
        body = message.body.prepare(content, uri)
        return message.prepare(body, message_type, auth_data)

    def decrypt(self, message: MessageProtocol) -> MessageProtocol:
        """Decrypt the message body, reading the self.iv_field from
            the auth_data. Returns a new message with the decrypted body.
        """
        iv = message.auth_data.fields[self.iv_field]

        if self.encrypt_uri:
            ciphertext = message.body.uri + message.body.content
        else:
            ciphertext = message.body.content
        content = decrypt(self.key, iv, ciphertext)
        if self.encrypt_uri:
            uri = content[:len(message.body.uri)]
            content = content[len(message.body.uri):]
        else:
            uri = message.body.uri

        message_type = message.header.message_type
        auth_data = message.auth_data.fields.copy()
        auth_data = message.auth_data.__class__(auth_data)
        body = message.body.prepare(content, uri)
        return message.prepare(body, message_type, auth_data)
