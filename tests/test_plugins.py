from context import netaio, asymmetric
from nacl.signing import SigningKey
from os import urandom
from time import time
import tapescript
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

    def test_hmac_auth_plugin_with_stream_cipher(self):
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

    def test_default_peer_plugin(self):
        peer_plugin = netaio.DefaultPeerPlugin()
        peer_data = {'foo': 'bar'}
        peer_data = peer_plugin.encode_data(peer_data)
        peer = netaio.Peer(addrs=set(), id=b'test', data=peer_data)
        packed = peer_plugin.pack(peer)
        unpacked = peer_plugin.unpack(packed)
        assert unpacked == peer
        assert unpacked.data == peer_data
        assert type(peer_plugin.parse_data(peer)) == dict
        assert 'foo' in peer_plugin.parse_data(peer)
        assert peer_plugin.parse_data(peer)['foo'] == 'bar'

    def test_tapescript_auth_plugin(self):
        seed = urandom(32)
        auth_plugin = asymmetric.TapescriptAuthPlugin({
            "lock": tapescript.make_single_sig_lock(SigningKey(seed).verify_key),
            "seed": seed,
        })
        message = netaio.Message.prepare(
            netaio.Body.prepare(b'hello world', b'123'),
            netaio.MessageType.PUBLISH_URI,
        )
        msg = message.copy()
        auth_plugin.make(msg.auth_data, msg.body)
        assert msg.auth_data.fields['witness'] is not None
        assert msg.auth_data.fields['ts'] is not None
        assert auth_plugin.check(msg.auth_data, msg.body)

        seed2 = urandom(32)
        peer_plugin = netaio.DefaultPeerPlugin()
        peer_data = {
            'lock': tapescript.make_single_sig_lock(SigningKey(seed2).verify_key).bytes,
        }
        peer = netaio.Peer(
            addrs=set(), id=b'test', data=peer_plugin.encode_data(peer_data)
        )
        msg = message.copy()
        auth_plugin.seed = seed2
        auth_plugin.make(
            msg.auth_data, msg.body, peer=peer,
            peer_plugin=peer_plugin
        )
        assert msg.auth_data.fields['witness'] is not None
        assert msg.auth_data.fields['ts'] is not None

        # prove it doesn't work without using the peer lock
        auth_plugin.use_peer_lock = False
        assert not auth_plugin.check(
            msg.auth_data, msg.body, peer=peer,
            peer_plugin=peer_plugin
        )

        # prove it works with the peer lock
        auth_plugin.use_peer_lock = True
        assert auth_plugin.check(
            msg.auth_data, msg.body, peer=peer,
            peer_plugin=peer_plugin
        )

        # tamper with the message
        msg.body.content = b'hello world, caesar is alive'
        assert not auth_plugin.check(
            msg.auth_data, msg.body, peer=peer,
            peer_plugin=peer_plugin
        )

    def test_tapescript_auth_plugin_with_custom_witness_func(self):
        root_seed = urandom(32)
        seed1 = urandom(32)
        seed2 = urandom(32)
        begin_ts = int(time()) - 120 # NB: must use int that encodes to 32 bits
        end_ts = int(time()) + 120
        certs = [
            tapescript.make_delegate_key_cert(
                seed1, SigningKey(seed2).verify_key, begin_ts, end_ts
            ),
            tapescript.make_delegate_key_cert(
                root_seed, SigningKey(seed1).verify_key, begin_ts, end_ts
            ),
        ]

        def witness_func(
                seed: bytes, sigfields: dict[str, bytes]
            ) -> tapescript.Script:
            return tapescript.make_delegate_key_chain_witness(
                seed, certs, sigfields
            )

        auth_plugin = asymmetric.TapescriptAuthPlugin({
            "lock": tapescript.make_delegate_key_chain_lock(
                SigningKey(root_seed).verify_key
            ),
            "seed": seed2,
            "witness_func": witness_func,
        })
        message = netaio.Message.prepare(
            netaio.Body.prepare(b'hello world', b'123'),
            netaio.MessageType.PUBLISH_URI,
        )
        msg = message.copy()
        auth_plugin.make(msg.auth_data, msg.body)
        assert msg.auth_data.fields['witness'] is not None
        assert auth_plugin.check(msg.auth_data, msg.body)

    def test_x25519_cipher_plugin(self):
        seed1 = urandom(32)
        seed2 = urandom(32)
        pubkey1 = SigningKey(seed1).verify_key
        pubkey2 = SigningKey(seed2).verify_key
        local_cipher_plugin = asymmetric.X25519CipherPlugin({
            "seed": seed1,
        })
        remote_cipher_plugin = asymmetric.X25519CipherPlugin({
            "seed": seed2,
        })
        peer_plugin = netaio.DefaultPeerPlugin()
        local_peer = netaio.Peer(
            addrs=set(), id=b'local', data=peer_plugin.encode_data({
                'pubkey': bytes(pubkey1),
            })
        )
        remote_peer = netaio.Peer(
            addrs=set(), id=b'remote', data=peer_plugin.encode_data({
                'pubkey': bytes(pubkey2),
            })
        )
        message = netaio.Message.prepare(
            netaio.Body.prepare(b'hello world', b'123'),
            netaio.MessageType.PUBLISH_URI,
        )
        msg = message.copy()

        with self.assertRaises(ValueError) as e:
            local_cipher_plugin.encrypt(msg)
        assert 'peer' in str(e.exception)
        assert 'peer_plugin' in str(e.exception)

        msg = local_cipher_plugin.encrypt(msg, peer=remote_peer, peer_plugin=peer_plugin)
        assert msg.body.encode() != message.body.encode()
        assert len(msg.body.encode()) == len(message.body.encode()) + 40, \
            len(msg.body.encode()) - len(message.body.encode())

        with self.assertRaises(ValueError) as e:
            remote_cipher_plugin.decrypt(msg)
        assert 'peer' in str(e.exception)
        assert 'peer_plugin' in str(e.exception)

        msg = remote_cipher_plugin.decrypt(msg, peer=local_peer, peer_plugin=peer_plugin)
        assert msg is not None
        assert msg.body.encode() == message.body.encode()

    def test_tapescript_auth_with_x25519_cipher(self):
        seed1 = urandom(32)
        seed2 = urandom(32)
        pubkey1 = SigningKey(seed1).verify_key
        pubkey2 = SigningKey(seed2).verify_key
        lock = tapescript.make_multisig_lock([pubkey1, pubkey2], 1)
        local_cipher_plugin = asymmetric.X25519CipherPlugin({"seed": seed1})
        remote_cipher_plugin = asymmetric.X25519CipherPlugin({"seed": seed2})
        local_auth_plugin = asymmetric.TapescriptAuthPlugin({
            "lock": lock,
            "seed": seed1,
        })
        remote_auth_plugin = asymmetric.TapescriptAuthPlugin({
            "lock": lock,
            "seed": seed2,
        })
        peer_plugin = netaio.DefaultPeerPlugin()
        local_peer = netaio.Peer(
            addrs=set(), id=b'local', data=peer_plugin.encode_data({
                'pubkey': bytes(pubkey1),
            })
        )
        remote_peer = netaio.Peer(
            addrs=set(), id=b'remote', data=peer_plugin.encode_data({
                'pubkey': bytes(pubkey2),
            })
        )
        message = netaio.Message.prepare(
            netaio.Body.prepare(b'hello world', b'123'),
            netaio.MessageType.PUBLISH_URI,
        )
        msg = message.copy()
        msg = local_cipher_plugin.encrypt(
            msg, peer=remote_peer, peer_plugin=peer_plugin
        )
        local_auth_plugin.make(msg.auth_data, msg.body)
        assert remote_auth_plugin.check(msg.auth_data, msg.body)
        msg = remote_cipher_plugin.decrypt(
            msg, peer=local_peer, peer_plugin=peer_plugin
        )
        assert msg is not None
        assert msg.body.encode() == message.body.encode()


if __name__ == "__main__":
    unittest.main()
