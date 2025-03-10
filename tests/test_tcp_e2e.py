from context import netaio, asymmetric
from nacl.signing import SigningKey
from os import urandom
from random import randint
import asyncio
import logging
import tapescript
import unittest


class TestTCPE2E(unittest.TestCase):
    PORT = randint(10000, 65535)

    @classmethod
    def setUpClass(cls):
        netaio.default_server_logger.setLevel(logging.INFO)
        netaio.default_client_logger.setLevel(logging.INFO)

    def test_e2e(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})

            server = netaio.TCPServer(port=self.PORT, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)
            client = netaio.TCPClient(port=self.PORT, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)

            client_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
                netaio.MessageType.PUBLISH_URI
            )
            client_subscribe_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'', uri=b'subscribe/test'),
                netaio.MessageType.SUBSCRIBE_URI
            )
            client_unsubscribe_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'', uri=b'subscribe/test'),
                netaio.MessageType.UNSUBSCRIBE_URI
            )
            server_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
                netaio.MessageType.OK
            )
            server_notify_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'subscribe/test'),
                netaio.MessageType.NOTIFY_URI
            )
            expected_response = netaio.Message.prepare(
                netaio.Body.prepare(b'DO NOT SEND', uri=b'NONE'),
                netaio.MessageType.OK
            )
            expected_subscribe_response = netaio.Message.prepare(
                netaio.Body.prepare(b'', uri=b'subscribe/test'),
                netaio.MessageType.CONFIRM_SUBSCRIBE
            )
            expected_unsubscribe_response = netaio.Message.prepare(
                netaio.Body.prepare(b'', uri=b'subscribe/test'),
                netaio.MessageType.CONFIRM_UNSUBSCRIBE
            )

            @server.on((netaio.MessageType.PUBLISH_URI, b'echo'))
            def server_echo(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return server_msg

            @server.on(netaio.MessageType.SUBSCRIBE_URI)
            def server_subscribe(message: netaio.Message, writer: asyncio.StreamWriter):
                server_log.append(message)
                server.subscribe(message.body.uri, writer)
                return expected_subscribe_response

            @server.on(netaio.MessageType.UNSUBSCRIBE_URI)
            def server_unsubscribe(message: netaio.Message, writer: asyncio.StreamWriter):
                server_log.append(message)
                server.unsubscribe(message.body.uri, writer)
                return expected_unsubscribe_response

            @client.on(netaio.MessageType.OK)
            def client_echo(message: netaio.Message, writer: asyncio.StreamWriter):
                client_log.append(message)
                return expected_response

            @client.on(netaio.MessageType.NOTIFY_URI)
            def client_notify(message: netaio.Message, writer: asyncio.StreamWriter):
                client_log.append(message)
                return message

            assert len(server_log) == 0
            assert len(client_log) == 0

            # Start the server as a background task.
            server_task = asyncio.create_task(server.start())

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # connect client
            await client.connect()

            await client.send(client_msg)
            response = await client.receive_once()
            assert response.encode() == expected_response.encode(), \
                (response.encode().hex(), expected_response.encode().hex())

            await client.send(client_subscribe_msg)
            response = await client.receive_once()
            assert response.header.message_type == expected_subscribe_response.header.message_type, \
                (response.header.message_type, expected_subscribe_response.header.message_type)
            assert response.body.uri == expected_subscribe_response.body.uri, \
                (response.body.uri, expected_subscribe_response.body.uri)
            assert response.body.content == expected_subscribe_response.body.content, \
                (response.body.content, expected_subscribe_response.body.content)

            await server.notify(b'subscribe/test', server_notify_msg)
            response = await client.receive_once(use_auth=False)
            assert response.header.message_type == server_notify_msg.header.message_type, \
                (response.header.message_type, server_notify_msg.header.message_type)
            assert response.body.uri == server_notify_msg.body.uri, \
                (response.body.uri, server_notify_msg.body.uri)
            assert response.body.content == server_notify_msg.body.content, \
                (response.body.content, server_notify_msg.body.content)

            await client.send(client_unsubscribe_msg)
            response = await client.receive_once()
            assert response.header.message_type == expected_unsubscribe_response.header.message_type, \
                (response.header.message_type, expected_unsubscribe_response.header.message_type)
            assert response.body.uri == expected_unsubscribe_response.body.uri, \
                (response.body.uri, expected_unsubscribe_response.body.uri)
            assert response.body.content == expected_unsubscribe_response.body.content, \
                (response.body.content, expected_unsubscribe_response.body.content)

            assert len(server_log) == 3, len(server_log)
            assert len(client_log) == 2, len(client_log)

            # test auth failure with mismatchedauth plugin config
            client.auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test2"})
            await client.send(client_msg)
            response = await client.receive_once()
            assert response is None

            # test auth failure with no auth plugins
            client.auth_plugin = None
            await client.send(client_msg)
            response = await client.receive_once(use_auth=False, use_cipher=False)
            assert response is not None
            assert response.header.message_type == netaio.MessageType.AUTH_ERROR, response

            # set different error handler on client
            def log_auth_error(client, auth_plugin, msg):
                client_log.append(msg)
                return None
            client.handle_auth_error = log_auth_error

            # test auth failure with mismatchedauth plugin config
            client_log.clear()
            client.auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test2"})
            await client.send(client_msg)
            response = await client.receive_once()
            assert response is None, response
            assert len(client_log) == 1, len(client_log)
            response = client_log[-1]
            assert response.header.message_type == netaio.MessageType.AUTH_ERROR, response

            # test auth failure with no auth plugins
            # should pass through without calling log_auth_error
            client_log.clear()
            await client.send(client_msg)
            response = await client.receive_once(use_auth=False, use_cipher=False)
            assert response is not None
            assert response.header.message_type == netaio.MessageType.AUTH_ERROR, response
            assert len(client_log) == 0, len(client_log)

            # close client and stop server
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

        print()
        asyncio.run(run_test())

    def test_peer_management_e2e(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})

            server_peer = netaio.Peer(
                addrs={('127.0.0.1', self.PORT)}, id=b'server',
                data=netaio.DefaultPeerPlugin().encode_data({
                    "name": "server",
                })
            )
            client_peer = netaio.Peer(
                addrs={('127.0.0.1', self.PORT+1)}, id=b'client',
                data=netaio.DefaultPeerPlugin().encode_data({
                    "name": "client",
                })
            )
            server = netaio.TCPServer(
                port=self.PORT, local_peer=server_peer,
                auth_plugin=auth_plugin, cipher_plugin=cipher_plugin
            )
            client = netaio.TCPClient(
                port=self.PORT, local_peer=client_peer,
                auth_plugin=auth_plugin, cipher_plugin=cipher_plugin
            )

            @server.on(netaio.MessageType.SUBSCRIBE_URI)
            def server_subscribe(message: netaio.Message, writer: asyncio.StreamWriter):
                server_log.append(message)
                server.subscribe(message.body.uri, writer)
                return netaio.Message.prepare(
                    message.body,
                    netaio.MessageType.CONFIRM_SUBSCRIBE
                )

            @client.on(netaio.MessageType.CONFIRM_SUBSCRIBE)
            def client_confirm_subscribe(message: netaio.Message, _: asyncio.StreamWriter):
                client_log.append(message)

            # Start the server as a background task.
            server_task = asyncio.create_task(server.start())

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # enable automatic peer management of peer data
            await server.manage_peers_automatically()
            await client.manage_peers_automatically()

            # connect client
            await client.connect()

            # Start the client as a background task.
            client_task = asyncio.create_task(client.receive_loop())

            # wait for peer data to be transmitted and response received
            await asyncio.sleep(0.1)

            # server should have the client as a peer because of the ADVERTISE_PEER message
            assert len(server.peers) == 1, len(server.peers)
            assert client_peer.id in server.peers, server.peers
            assert server.peers[client_peer.id].data == client_peer.data, \
                (server.peers[client_peer.id].data, client_peer.data)
            # client should have the server as a peer because of the PEER_DISCOVERED response
            assert len(client.peers) == 1, len(client.peers)
            assert server_peer.id in client.peers, client.peers
            assert client.peers[server_peer.id].data == server_peer.data, \
                (client.peers[server_peer.id].data, server_peer.data)

            # subscribe the client to a topic URI
            client_log.clear()
            server_log.clear()
            await client.send(netaio.Message.prepare(
                netaio.Body.prepare(b'', uri=b'subscribe/test'),
                netaio.MessageType.SUBSCRIBE_URI
            ))

            # server should receive the message and respond
            await asyncio.sleep(0.1)
            assert len(server_log) == 1, len(server_log)
            assert server_log[-1].header.message_type is netaio.MessageType.SUBSCRIBE_URI, server_log[-1].header
            assert len(client_log) == 1, len(client_log)
            assert client_log[-1].header.message_type is netaio.MessageType.CONFIRM_SUBSCRIBE, client_log[-1].header

            # client should be subscribed
            assert len(server.subscriptions.get(b'subscribe/test', set())) == 1, server.subscriptions

            # stop peer management on client and wait for the DISCONNECT message to be received
            await client.stop_peer_management()
            await asyncio.sleep(0.1)
            assert len(server.peers) == 0, len(server.peers)

            # client should not be a peer anymore or subscribed to the topic
            assert client_peer.id not in server.peers, server.peers
            subs = server.subscriptions.get(b'subscribe/test', set())
            assert len(subs) == 0, (list(subs), len(subs))

            # begin automatic peer management and let server respond
            await client.manage_peers_automatically()
            await asyncio.sleep(0.1)

            # server should have the client as a peer because of the ADVERTISE_PEER messages
            assert len(server.peers) == 1, len(server.peers)
            assert client_peer.id in server.peers, server.peers
            # client should have the server as a peer because of the PEER_DISCOVERED responses
            assert len(client.peers) == 1, len(client.peers)
            assert server_peer.id in client.peers, client.peers

            # close client and stop server
            client_task.cancel()
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

            try:
                await client_task
            except asyncio.CancelledError:
                pass

        print()
        asyncio.run(run_test())

    def test_peer_management_with_asymmetric_plugins(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            server_seed = urandom(32)
            server_pubkey = SigningKey(server_seed).verify_key
            client_seed = urandom(32)
            client_pubkey = SigningKey(client_seed).verify_key
            lock = tapescript.make_multisig_lock([server_pubkey, client_pubkey], 1)
            server_auth_plugin = asymmetric.TapescriptAuthPlugin({
                "lock": lock,
                "seed": server_seed,
            })
            client_auth_plugin = asymmetric.TapescriptAuthPlugin({
                "lock": lock,
                "seed": client_seed,
            })
            server_cipher_plugin = asymmetric.X25519CipherPlugin({"seed": server_seed})
            client_cipher_plugin = asymmetric.X25519CipherPlugin({"seed": client_seed})
            server_peer = netaio.Peer(
                addrs=set(), id=b'server',
                data=netaio.DefaultPeerPlugin().encode_data({
                    "pubkey": bytes(server_pubkey),
                })
            )
            client_peer = netaio.Peer(
                addrs=set(), id=b'client',
                data=netaio.DefaultPeerPlugin().encode_data({
                    "pubkey": bytes(client_pubkey),
                })
            )

            server = netaio.TCPServer(port=self.PORT, local_peer=server_peer)
            client = netaio.TCPClient(port=self.PORT, local_peer=client_peer)

            @server.on(netaio.MessageType.REQUEST_URI, server_auth_plugin, server_cipher_plugin)
            def server_handle_request_uri(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return netaio.Message.prepare(
                    netaio.Body.prepare(b'some content for u', uri=message.body.uri),
                    netaio.MessageType.RESPOND_URI
                )

            @client.on(netaio.MessageType.RESPOND_URI, client_auth_plugin, client_cipher_plugin)
            def client_handle_respond_uri(message: netaio.Message, _: asyncio.StreamWriter):
                client_log.append(message)

            # Start the server as a background task.
            server_task = asyncio.create_task(server.start())

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # enable automatic peer management of peer data
            await server.manage_peers_automatically()
            await client.manage_peers_automatically()

            # connect client
            await client.connect()

            # Start the client as a background task.
            client_task = asyncio.create_task(client.receive_loop())

            # wait for peer data to be transmitted and response received
            await asyncio.sleep(0.1)

            # server should have the client as a peer because of the ADVERTISE_PEER message
            assert len(server.peers) == 1, len(server.peers)
            assert client_peer.id in server.peers, server.peers
            assert server.peers[client_peer.id].data == client_peer.data, \
                (server.peers[client_peer.id].data, client_peer.data)
            # client should have the server as a peer because of the PEER_DISCOVERED response
            assert len(client.peers) == 1, len(client.peers)
            assert server_peer.id in client.peers, client.peers
            assert client.peers[server_peer.id].data == server_peer.data, \
                (client.peers[server_peer.id].data, server_peer.data)

            # send request to publish from client to server
            await client.send(netaio.Message.prepare(
                netaio.Body.prepare(b'pls gibs me dat', uri=b'something'),
                netaio.MessageType.REQUEST_URI
            ), auth_plugin=client_auth_plugin, cipher_plugin=client_cipher_plugin)
            await asyncio.sleep(0.1)

            # server should have received the message and responded
            assert len(server_log) == 1, len(server_log)
            assert server_log[-1].header.message_type is netaio.MessageType.REQUEST_URI, server_log[-1].header
            assert server_log[-1].body.uri == b'something', server_log[-1].body.uri
            assert server_log[-1].body.content == b'pls gibs me dat', server_log[-1].body.content

            # client should have received the response from the server
            assert len(client_log) == 1, len(client_log)
            assert client_log[-1].header.message_type is netaio.MessageType.RESPOND_URI, client_log[-1].header
            assert client_log[-1].body.uri == b'something', client_log[-1].body.uri
            assert client_log[-1].body.content == b'some content for u', client_log[-1].body.content

            # close client and stop server
            client_task.cancel()
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

            try:
                await client_task
            except asyncio.CancelledError:
                pass

        print()
        asyncio.run(run_test())


class TestTCPE2EWithoutDefaultPlugins(unittest.TestCase):
    PORT = randint(10000, 65535)

    @classmethod
    def setUpClass(cls):
        netaio.default_server_logger.setLevel(logging.INFO)
        netaio.default_client_logger.setLevel(logging.INFO)

    def test_e2e_without_default_plugins(self):
        async def run_test():
            server_log = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})

            server = netaio.TCPServer(port=self.PORT)
            client = netaio.TCPClient(port=self.PORT, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_request(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return message

            @server.on(netaio.MessageType.PUBLISH_URI, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)
            def server_publish(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return message

            echo_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
                netaio.MessageType.REQUEST_URI
            )
            publish_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'publish'),
                netaio.MessageType.PUBLISH_URI
            )

            assert len(server_log) == 0

            # Start the server as a background task.
            server_task = asyncio.create_task(server.start())

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # connect client
            await client.connect()

            # send to unprotected route
            await client.send(echo_msg, use_auth=False, use_cipher=False)
            response = await client.receive_once(use_auth=False, use_cipher=False)
            assert response is not None
            assert response.encode() == echo_msg.encode(), \
                (response.encode().hex(), echo_msg.encode().hex())

            # send to protected route
            await client.send(publish_msg)
            response = await client.receive_once()
            assert response is not None
            assert response.body.content == publish_msg.body.content, \
                (response.body.content, publish_msg.body.content)
            assert response.body.uri == publish_msg.body.uri, \
                (response.body.uri, publish_msg.body.uri)
            assert response.header.message_type == publish_msg.header.message_type, \
                (response.header.message_type, publish_msg.header.message_type)

            # close client and stop server
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

        print()
        asyncio.run(run_test())

    def test_e2e_without_default_plugins_method_2(self):
        async def run_test():
            server_log = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})

            server = netaio.TCPServer(port=self.PORT)
            client = netaio.TCPClient(port=self.PORT)

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_request(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return message

            @server.on(netaio.MessageType.PUBLISH_URI, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)
            def server_publish(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return message

            echo_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
                netaio.MessageType.REQUEST_URI
            )
            publish_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'publish'),
                netaio.MessageType.PUBLISH_URI
            )

            assert len(server_log) == 0

            # Start the server as a background task.
            server_task = asyncio.create_task(server.start())

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # connect client
            await client.connect()

            # send to unprotected route
            await client.send(echo_msg)
            response = await client.receive_once()
            assert response is not None
            assert response.encode() == echo_msg.encode(), \
                (response.encode().hex(), echo_msg.encode().hex())

            # send to protected route
            await client.send(publish_msg, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)
            response = await client.receive_once(auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)
            assert response is not None
            assert response.body.content == publish_msg.body.content, \
                (response.body.content, publish_msg.body.content)
            assert response.body.uri == publish_msg.body.uri, \
                (response.body.uri, publish_msg.body.uri)
            assert response.header.message_type == publish_msg.header.message_type, \
                (response.header.message_type, publish_msg.header.message_type)

            # close client and stop server
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

        print()
        asyncio.run(run_test())


class TestTCPE2ETwoLayersOfPlugins(unittest.TestCase):
    PORT = randint(10000, 65535)

    @classmethod
    def setUpClass(cls):
        netaio.default_server_logger.setLevel(logging.INFO)
        netaio.default_client_logger.setLevel(logging.INFO)

    def test_e2e_two_layers_of_plugins(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})
            auth_plugin2 = netaio.HMACAuthPlugin(config={
                "secret": "test2",
                "hmac_field": "hmac2",
            })
            cipher_plugin2 = netaio.Sha256StreamCipherPlugin(config={
                "key": "test2",
                "iv_field": "iv2",
                "encrypt_uri": False
            })

            server = netaio.TCPServer(port=self.PORT, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)
            client = netaio.TCPClient(port=self.PORT, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_request(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return message

            @server.on(netaio.MessageType.PUBLISH_URI, auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2)
            def server_publish(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return message

            echo_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
                netaio.MessageType.REQUEST_URI
            )
            publish_msg = lambda: netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'publish'),
                netaio.MessageType.PUBLISH_URI
            )

            assert len(server_log) == 0

            # Start the server as a background task.
            server_task = asyncio.create_task(server.start())

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # connect client
            await client.connect()

            # send to once-protected route
            await client.send(echo_msg)
            response = await client.receive_once()
            assert response is not None
            assert response.body.content == echo_msg.body.content, \
                (response.body.content, echo_msg.body.content)
            assert response.body.uri == echo_msg.body.uri, \
                (response.body.uri, echo_msg.body.uri)
            assert response.header.message_type == echo_msg.header.message_type, \
                (response.header.message_type, echo_msg.header.message_type)

            # send to twice-protected route
            await client.send(publish_msg(), auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2)
            response = await client.receive_once(auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2)
            assert response is not None
            assert response.body.content == publish_msg().body.content, \
                (response.body.content, publish_msg().body.content)
            assert response.body.uri == publish_msg().body.uri, \
                (response.body.uri, publish_msg().body.uri)
            assert response.header.message_type == publish_msg().header.message_type, \
                (response.header.message_type, publish_msg().header.message_type)

            assert len(server_log) == 2, len(server_log)

            # send to twice-protected route without the inner auth plugin
            await client.send(publish_msg())
            response = await client.receive_once()
            assert response is None, response

            # set different error handler on client
            def log_auth_error(client, auth_plugin, msg):
                client.logger.debug("log_auth_error called")
                client_log.append(msg)
                return None
            client.handle_auth_error = log_auth_error

            # send to twice-protected route without the inner auth plugin
            await client.send(publish_msg())
            response = await client.receive_once()
            assert response is None, response
            assert len(client_log) == 1, len(client_log)
            response = client_log[-1]
            assert response.header.message_type == netaio.MessageType.AUTH_ERROR, response

            # close client and stop server
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

        print()
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
