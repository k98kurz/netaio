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

    def test_sha256_stream_cipher_plugin(self):
        # default
        body = netaio.Body.prepare(b'brutus is plotting something sus', b'123')
        message = netaio.Message.prepare(body, netaio.MessageType.PUBLISH_URI)
        cipher_plugin = netaio.Sha256StreamCipherPlugin({"key": "test"})
        before = message.body.encode()
        assert 'iv' not in message.auth_data.fields
        message = cipher_plugin.encrypt(message)
        assert 'iv' in message.auth_data.fields
        after = message.body.encode()
        assert before != after
        msg = cipher_plugin.decrypt(message)
        assert msg is not None
        assert msg.body.encode() == before

        # without uri cipher
        cipher_plugin = netaio.Sha256StreamCipherPlugin({
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
        msg = cipher_plugin.decrypt(message)
        assert msg is not None
        assert msg.body.encode() == before

    def test_hmac_auth_plugin_with_cipher(self):
        # setup
        body = netaio.Body.prepare(b'brutus attacks, pls send backup', b'123')
        message = netaio.Message.prepare(body, netaio.MessageType.PUBLISH_URI)
        before = message.body.encode()
        auth_plugin = netaio.HMACAuthPlugin({"secret": "test"})
        cipher_plugin = netaio.Sha256StreamCipherPlugin({"key": "test"})

        # encrypt and authenticate
        msg = cipher_plugin.encrypt(message)
        auth_plugin.make(msg.auth_data, msg.body)
        after = msg.body.encode()
        assert before != after
        assert msg.auth_data.fields['hmac'] is not None
        assert msg.auth_data.fields['iv'] is not None
        # authenticate and decrypt
        auth_plugin.check(msg.auth_data, msg.body)
        msg = cipher_plugin.decrypt(msg)
        assert msg is not None
        assert msg.body.encode() == before

        # tamper with the message, then re-encrypt but don't re-authenticate
        msg.body.content = b'everything is fine'
        before = msg.body.encode()
        msg = cipher_plugin.encrypt(msg)
        assert msg.auth_data.fields['hmac'] is not None
        assert msg.body.encode() != before
        # auth plugin catches the tampering
        assert not auth_plugin.check(msg.auth_data, msg.body)

    def test_two_layers_of_plugins(self):
        # setup
        body = netaio.Body.prepare(b'eschew republic, establish empire', b'123')
        message = netaio.Message.prepare(body, netaio.MessageType.PUBLISH_URI)
        before = message.body.encode()
        auth_plugin_outer = netaio.HMACAuthPlugin({"secret": "test"})
        cipher_plugin_outer = netaio.Sha256StreamCipherPlugin({"key": "test"})
        auth_plugin_inner = netaio.HMACAuthPlugin({
            "secret": "test2",
            "hmac_field": "hmac2",
        })
        cipher_plugin_inner = netaio.Sha256StreamCipherPlugin({
            "key": "test2",
            "iv_field": "iv2",
            "encrypt_uri": False
        })

        # inner cipher
        message = cipher_plugin_inner.encrypt(message)
        # inner auth
        auth_plugin_inner.make(message.auth_data, message.body)
        # outer cipher
        message = cipher_plugin_outer.encrypt(message)
        # outer auth
        auth_plugin_outer.make(message.auth_data, message.body)
        after = message.body.encode()
        assert before != after
        assert message.auth_data.fields['hmac'] is not None
        assert message.auth_data.fields['iv'] is not None
        assert message.auth_data.fields['hmac2'] is not None
        assert message.auth_data.fields['iv2'] is not None

        # outer auth
        assert auth_plugin_outer.check(message.auth_data, message.body)
        # outer cipher
        message = cipher_plugin_outer.decrypt(message)
        assert message is not None
        # inner auth
        assert auth_plugin_inner.check(message.auth_data, message.body)
        # inner cipher
        message = cipher_plugin_inner.decrypt(message)
        assert message is not None
        assert message.body.encode() == before


if __name__ == "__main__":
    unittest.main()
