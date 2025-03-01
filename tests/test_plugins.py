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
        # default
        body = netaio.Body.prepare(b'brutus is plotting something sus', b'123')
        message = netaio.Message.prepare(body, netaio.MessageType.PUBLISH_URI)
        cipher_plugin = netaio.Sha256StreamEncryptionPlugin({"key": "test"})
        before = message.body.encode()
        assert 'iv' not in message.auth_data.fields
        message = cipher_plugin.encrypt(message)
        assert 'iv' in message.auth_data.fields
        after = message.body.encode()
        assert before != after
        msg_or_err = cipher_plugin.decrypt(message)
        assert msg_or_err is not None
        assert not isinstance(msg_or_err, BaseException), msg_or_err
        assert msg_or_err.body.encode() == before

        # without uri encryption
        cipher_plugin = netaio.Sha256StreamEncryptionPlugin({
            "key": "test",
            "encrypt_uri": False
        })
        before = message.body.encode()
        before_uri = message.body.uri
        message = cipher_plugin.encrypt(message)
        assert 'iv' in message.auth_data.fields
        after = message.body.encode()
        assert before != after
        assert message.body.uri == before_uri
        msg_or_err = cipher_plugin.decrypt(message)
        assert msg_or_err is not None
        assert not isinstance(msg_or_err, BaseException), msg_or_err
        assert msg_or_err.body.encode() == before

    def test_hmac_auth_plugin_with_encryption(self):
        # setup
        body = netaio.Body.prepare(b'brutus attacks, pls send backup', b'123')
        message = netaio.Message.prepare(body, netaio.MessageType.PUBLISH_URI)
        before = message.body.encode()
        auth_plugin = netaio.HMACAuthPlugin({"secret": "test"})
        cipher_plugin = netaio.Sha256StreamEncryptionPlugin({"key": "test"})

        # encrypt and authenticate
        msg = cipher_plugin.encrypt(message)
        auth_plugin.make(msg.auth_data, msg.body)
        after = msg.body.encode()
        assert before != after
        assert msg.auth_data.fields['hmac'] is not None
        assert msg.auth_data.fields['iv'] is not None
        # authenticate and decrypt
        auth_plugin.check(msg.auth_data, msg.body)
        msg_or_err = cipher_plugin.decrypt(msg)
        assert msg_or_err is not None
        assert not isinstance(msg_or_err, BaseException), msg_or_err
        assert msg_or_err.body.encode() == before

        # tamper with the message, then re-encrypt but don't re-authenticate
        msg_or_err.body.content = b'everything is fine'
        before = msg_or_err.body.encode()
        msg_or_err = cipher_plugin.encrypt(msg_or_err)
        assert msg_or_err.auth_data.fields['hmac'] is not None
        assert msg_or_err.body.encode() != before
        # auth plugin catches the tampering
        assert not auth_plugin.check(msg_or_err.auth_data, msg_or_err.body)


if __name__ == "__main__":
    unittest.main()
