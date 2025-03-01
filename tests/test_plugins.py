from context import netaio
import unittest


class TestPlugins(unittest.TestCase):
    def test_hmac_auth_plugin(self):
        body = netaio.Body.prepare(b'hello world, caesar is dead', b'123')
        message = netaio.Message.prepare(body, netaio.MessageType.PUBLISH_URI)
        auth_plugin = netaio.HMACAuthPlugin({"secret": "test"})
        before = {**message.auth_data.fields}
        auth_plugin.make(message.auth_data, message.body)
        after = {**message.auth_data.fields}
        assert before != after
        assert 'hmac' not in before
        assert 'hmac' in after
        assert after['hmac'] is not None
        assert auth_plugin.check(message.auth_data, message.body)

        # tamper with the message
        message.body.content = b'hello world, caesar is alive'
        assert not auth_plugin.check(message.auth_data, message.body)

    def test_sha256_stream_encryption_plugin(self):
        body = netaio.Body.prepare(b'brutus is plotting something sus', b'123')
        message = netaio.Message.prepare(body, netaio.MessageType.PUBLISH_URI)
        cipher_plugin = netaio.Sha256StreamEncryptionPlugin({"key": "test"})
        before = message.body.encode()
        assert 'iv' not in message.auth_data.fields
        cipher_plugin.encrypt(message)
        assert 'iv' in message.auth_data.fields
        after = message.body.encode()
        assert before != after
        error = cipher_plugin.decrypt(message)
        assert error is None, error
        assert message.body.encode() == before

    def test_hmac_auth_plugin_with_encryption(self):
        # setup
        body = netaio.Body.prepare(b'brutus attacks, pls send backup', b'123')
        message = netaio.Message.prepare(body, netaio.MessageType.PUBLISH_URI)
        before = message.body.encode()
        auth_plugin = netaio.HMACAuthPlugin({"secret": "test"})
        cipher_plugin = netaio.Sha256StreamEncryptionPlugin({"key": "test"})

        # encrypt and authenticate
        cipher_plugin.encrypt(message)
        auth_plugin.make(message.auth_data, message.body)
        after = message.body.encode()
        assert before != after
        assert message.auth_data.fields['hmac'] is not None
        assert message.auth_data.fields['iv'] is not None
        # authenticate and decrypt
        auth_plugin.check(message.auth_data, message.body)
        error = cipher_plugin.decrypt(message)
        assert error is None, error
        assert message.body.encode() == before

        # tamper with the message, then re-encrypt but don't re-authenticate
        message.body.content = b'everything is fine'
        before = message.body.encode()
        cipher_plugin.encrypt(message)
        assert message.auth_data.fields['hmac'] is not None
        # auth plugin catches the tampering
        assert not auth_plugin.check(message.auth_data, message.body)


if __name__ == "__main__":
    unittest.main()
