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

    def encrypt(self, message: MessageProtocol) -> None:
        """Encrypt the message body, setting values in the header or
            auth_data as necessary.
        """
        ...

    def decrypt(self, message: MessageProtocol) -> None|BaseException:
        """Decrypt the message body, reading values from the header or
            auth_data as necessary. Returns an exception if the
            decryption fails.
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

    def encrypt(self, message: MessageProtocol) -> None:
        """Encrypt the message body, setting values in the header or
            auth_data as necessary.
        """
        iv = None
        if message.auth_data.fields.get('iv'):
            iv = message.auth_data.fields['iv']
        plaintext = message.body.uri + message.body.content
        iv, ciphertext = encrypt(self.key, plaintext, iv)
        uri = ciphertext[:len(message.body.uri)]
        content = ciphertext[len(message.body.uri):]
        message.auth_data.fields['iv'] = iv
        message.body = message.body.prepare(content, uri)

    def decrypt(self, message: MessageProtocol) -> None|BaseException:
        """Decrypt the message body, reading values from the header or
            auth_data as necessary. Returns an exception if the
            decryption fails.
        """
        iv = None
        if message.auth_data.fields.get('iv'):
            iv = message.auth_data.fields['iv']
        try:
            ciphertext = message.body.uri + message.body.content
            content = decrypt(self.key, iv, ciphertext)
            uri = content[:len(message.body.uri)]
            content = content[len(message.body.uri):]
        except Exception as e:
            return e
        message.body = message.body.prepare(content, uri)
