from .common import MessageProtocol
from .crypto import encrypt, decrypt
from hashlib import sha256
from typing import Protocol, runtime_checkable


@runtime_checkable
class EncryptionPluginProtocol(Protocol):
    """Shows what an encryption plugin should do."""
    def __init__(self, config: dict):
        """Initialize the encryption plugin with a config."""
        ...

    def encrypt(self, message: MessageProtocol) -> MessageProtocol:
        """Encrypt the message body, setting values in the header or
            auth_data as necessary. Returns a new message with the
            encrypted body and updated auth_data.
        """
        ...

    def decrypt(self, message: MessageProtocol) -> MessageProtocol:
        """Decrypt the message body, reading values from the auth_data
            as necessary. Returns a new message with the decrypted body.
            May raise an exception if the decryption fails.
        """
        ...


class Sha256StreamEncryptionPlugin:
    """SHA-256 stream encryption plugin."""
    key: bytes

    def __init__(self, config: dict):
        """Initialize the encryption plugin with a config."""
        key = config['key']
        key = sha256(key.encode() if isinstance(key, str) else key).digest()
        self.key = key

    def encrypt(self, message: MessageProtocol) -> MessageProtocol:
        """Encrypt the message body, setting the iv in the auth_data if
            it is not already set.
        """
        iv = None
        if message.auth_data.fields.get('iv'):
            iv = message.auth_data.fields['iv']
        plaintext = message.body.uri + message.body.content
        iv, ciphertext = encrypt(self.key, plaintext, iv)
        uri = ciphertext[:len(message.body.uri)]
        message_type = message.header.message_type
        content = ciphertext[len(message.body.uri):]
        auth_data = message.auth_data.fields.copy()
        auth_data['iv'] = iv
        auth_data = message.auth_data.__class__(auth_data)
        body = message.body.prepare(content, uri)
        return message.prepare(body, message_type, auth_data)

    def decrypt(self, message: MessageProtocol) -> MessageProtocol:
        """Decrypt the message body, reading values from the header or
            auth_data as necessary. Returns a new message with the
            decrypted body.
        """
        iv = None
        if message.auth_data.fields.get('iv'):
            iv = message.auth_data.fields['iv']
        ciphertext = message.body.uri + message.body.content
        content = decrypt(self.key, iv, ciphertext)
        uri = content[:len(message.body.uri)]
        content = content[len(message.body.uri):]
        message_type = message.header.message_type
        auth_data = message.auth_data.fields.copy()
        auth_data = message.auth_data.__class__(auth_data)
        body = message.body.prepare(content, uri)
        return message.prepare(body, message_type, auth_data)
