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
            second_client_log: list[netaio.Message] = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})

            server = netaio.TCPServer(
                port=self.PORT, auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin
            )
            client = netaio.TCPClient(
                port=self.PORT, auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin
            )
            second_client = netaio.TCPClient(
                port=self.PORT, auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin
            )

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
            def server_subscribe(
                    message: netaio.Message, writer: asyncio.StreamWriter
                ):
                server_log.append(message)
                server.subscribe(message.body.uri, writer)
                return expected_subscribe_response

            @server.on(netaio.MessageType.UNSUBSCRIBE_URI)
            def server_unsubscribe(
                    message: netaio.Message, writer: asyncio.StreamWriter
                ):
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

            @second_client.on(netaio.MessageType.NOTIFY_URI)
            def second_client_notify(
                    message: netaio.Message, writer: asyncio.StreamWriter
                ):
                second_client_log.append(message)
                return message

            assert len(server_log) == 0
            assert len(client_log) == 0
            assert len(second_client_log) == 0

            # Start the server as a background task.
            server_task = asyncio.create_task(server.start())

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # connect clients
            await client.connect()
            await second_client.connect()

            await client.send(client_msg)
            response = await client.receive_once()
            assert response.encode() == expected_response.encode(), \
                (response.encode().hex(), expected_response.encode().hex())

            # subscribe first client
            await client.send(client_subscribe_msg)
            response = await client.receive_once()
            assert response.header.message_type == \
                expected_subscribe_response.header.message_type, \
                (
                    response.header.message_type,
                    expected_subscribe_response.header.message_type
                )
            assert response.body.uri == expected_subscribe_response.body.uri, \
                (response.body.uri, expected_subscribe_response.body.uri)
            assert response.body.content == expected_subscribe_response.body.content, \
                (response.body.content, expected_subscribe_response.body.content)

            # subscribe second client
            await second_client.send(client_subscribe_msg)
            response = await second_client.receive_once()
            assert response.header.message_type == \
                expected_subscribe_response.header.message_type, \
                (
                    response.header.message_type,
                    expected_subscribe_response.header.message_type
                )
            assert response.body.uri == expected_subscribe_response.body.uri, \
                (response.body.uri, expected_subscribe_response.body.uri)
            assert response.body.content == expected_subscribe_response.body.content, \
                (response.body.content, expected_subscribe_response.body.content)

            # notify both clients
            await server.notify(b'subscribe/test', server_notify_msg)

            # get notification from first client
            response = await client.receive_once(use_auth=False)
            assert response.header.message_type == \
                server_notify_msg.header.message_type, \
                (response.header.message_type, server_notify_msg.header.message_type)
            assert response.body.uri == server_notify_msg.body.uri, \
                (response.body.uri, server_notify_msg.body.uri)
            assert response.body.content == server_notify_msg.body.content, \
                (response.body.content, server_notify_msg.body.content)

            # get notification from second client
            response = await second_client.receive_once(use_auth=False)
            assert response.header.message_type == \
                server_notify_msg.header.message_type, \
                (response.header.message_type, server_notify_msg.header.message_type)
            assert response.body.uri == server_notify_msg.body.uri, \
                (response.body.uri, server_notify_msg.body.uri)
            assert response.body.content == server_notify_msg.body.content, \
                (response.body.content, server_notify_msg.body.content)

            await client.send(client_unsubscribe_msg)
            response = await client.receive_once()
            assert response.header.message_type == \
                expected_unsubscribe_response.header.message_type, \
                (
                    response.header.message_type,
                    expected_unsubscribe_response.header.message_type
                )
            assert response.body.uri == expected_unsubscribe_response.body.uri, \
                (response.body.uri, expected_unsubscribe_response.body.uri)
            assert response.body.content == \
                expected_unsubscribe_response.body.content, \
                (response.body.content, expected_unsubscribe_response.body.content)

            assert len(server_log) == 4, len(server_log)
            assert len(client_log) == 2, len(client_log)
            assert len(second_client_log) == 1, len(second_client_log)

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
            assert response.header.message_type == \
                netaio.MessageType.AUTH_ERROR, response

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
            assert response.header.message_type == \
                netaio.MessageType.AUTH_ERROR, response

            # test auth failure with no auth plugins
            # should pass through without calling log_auth_error
            client_log.clear()
            await client.send(client_msg)
            response = await client.receive_once(use_auth=False, use_cipher=False)
            assert response is not None
            assert response.header.message_type == \
                netaio.MessageType.AUTH_ERROR, response
            assert len(client_log) == 0, len(client_log)

            # Cancel server task and close client - proper shutdown pattern
            await client.close()
            await second_client.close()
            server_task.cancel()
            try:
                print('DEBUG 1')
                await server_task
                print('DEBUG 2')
            except asyncio.CancelledError:
                print('DEBUG 3')
                pass

        print()
        print(f'{self.__class__.__name__}.test_e2e')
        asyncio.run(run_test())

    def test_ephemeral_handler_request_response_pattern(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})

            server = netaio.TCPServer(
                port=self.PORT,
                auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin
            )
            client = netaio.TCPClient(
                port=self.PORT,
                auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin
            )

            resources = {b'/resource1': b'content1', b'/resource2': b'content2'}

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_handle_request(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                server_log.append(message)
                uri = message.body.uri
                if uri in resources:
                    return netaio.Message.prepare(
                        netaio.Body.prepare(resources[uri], uri=uri),
                        netaio.MessageType.RESPOND_URI
                    )
                return None

            server_task = asyncio.create_task(server.start())
            await asyncio.sleep(0.1)

            await client.connect()

            @client.once((netaio.MessageType.RESPOND_URI, b'/resource1'))
            def client_handle_response1(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                client_log.append(('resource1', message))

            await client.send(netaio.Message.prepare(
                netaio.Body.prepare(b'', uri=b'/resource1'),
                netaio.MessageType.REQUEST_URI
            ))
            response = await client.receive_once()
            assert response is not None
            assert response.body.content == b'content1'
            assert (netaio.MessageType.RESPOND_URI, b'/resource1') not in \
                client.ephemeral_handlers

            @client.once((netaio.MessageType.RESPOND_URI, b'/resource2'))
            def client_handle_response2(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                client_log.append(('resource2', message))

            await client.send(netaio.Message.prepare(
                netaio.Body.prepare(b'', uri=b'/resource2'),
                netaio.MessageType.REQUEST_URI
            ))
            response = await client.receive_once()
            assert response is not None
            assert response.body.content == b'content2'

            assert len([log for log in client_log if log[0] == 'resource1']) == 1
            assert len([log for log in client_log if log[0] == 'resource2']) == 1

            # test client.request: positive case
            response = await client.request(b'/resource1')
            assert response is not None
            assert response.body.content == b'content1'

            # test client.request: timeout case
            with self.assertRaises(TimeoutError) as e:
                response = await client.request(b'/notgooduri', timeout=1.0)

            # change server handler to respond with NOT_FOUND
            server.remove_handler(netaio.MessageType.REQUEST_URI)

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_handle_request(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                server_log.append(message)
                uri = message.body.uri
                if uri in resources:
                    return netaio.Message.prepare(
                        netaio.Body.prepare(resources[uri], uri=uri),
                        netaio.MessageType.RESPOND_URI
                    )
                return netaio.Message.prepare(
                    netaio.Body.prepare(b'', uri=uri),
                    netaio.MessageType.NOT_FOUND
                )

            # now request the bad uri
            response = await client.request(b'/notgooduri')
            assert response is not None
            assert response.header.message_type is \
                netaio.MessageType.NOT_FOUND, response

            # now test create happy path and error case
            @server.on(netaio.MessageType.CREATE_URI)
            def server_handle_create(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                uri = message.body.uri
                if uri == b'/yep':
                    return netaio.Message.prepare(
                        netaio.Body.prepare(message.body.content, uri=uri),
                        netaio.MessageType.OK
                    )
                return netaio.Message.prepare(
                    netaio.Body.prepare(b'invalid', uri=uri),
                    netaio.MessageType.ERROR
                )
            # create happy path
            response = await client.create(b'/yep', b'something')
            assert response is not None
            assert response.header.message_type is netaio.MessageType.OK, response
            # create error case
            response = await client.create(b'/nope', b'nothing')
            assert response is not None
            assert response.header.message_type is netaio.MessageType.ERROR, response

            # now test update happy path and error case
            @server.on(netaio.MessageType.UPDATE_URI)
            def server_handle_update(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                uri = message.body.uri
                if uri == b'/yep':
                    return netaio.Message.prepare(
                        netaio.Body.prepare(message.body.content, uri=uri),
                        netaio.MessageType.OK
                    )
                return netaio.Message.prepare(
                    netaio.Body.prepare(b'invalid', uri=uri),
                    netaio.MessageType.ERROR
                )
            # update happy path
            response = await client.update(b'/yep', b'something')
            assert response is not None
            assert response.header.message_type is netaio.MessageType.OK, response
            # update error case
            response = await client.update(b'/nope', b'nothing')
            assert response is not None
            assert response.header.message_type is netaio.MessageType.ERROR, response

            # now test delete happy path and error case
            @server.on(netaio.MessageType.DELETE_URI)
            def server_handle_delete(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                uri = message.body.uri
                if uri == b'/yep':
                    return netaio.Message.prepare(
                        netaio.Body.prepare(message.body.content, uri=uri),
                        netaio.MessageType.OK
                    )
                return netaio.Message.prepare(
                    netaio.Body.prepare(b'invalid', uri=uri),
                    netaio.MessageType.ERROR
                )
            # delete happy path
            response = await client.delete(b'/yep')
            assert response is not None
            assert response.header.message_type is netaio.MessageType.OK, response
            # delete error case
            response = await client.delete(b'/nope')
            assert response is not None
            assert response.header.message_type is netaio.MessageType.ERROR, response


            # close client and cancel server
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

        print()
        print(
            f'{self.__class__.__name__}.'
            'test_ephemeral_handler_request_response_pattern'
        )
        asyncio.run(run_test())

    def test_ephemeral_handler_server_side(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})

            server = netaio.TCPServer(
                port=self.PORT,
                auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin
            )
            client = netaio.TCPClient(
                port=self.PORT,
                auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin
            )

            call_count = {'value': 0}
            call_count2 = {'value': 0}

            @server.once((netaio.MessageType.PUBLISH_URI, b'ephemeral_test'))
            def server_ephemeral_handler(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                call_count['value'] += 1
                server_log.append(message)
                return netaio.Message.prepare(
                    netaio.Body.prepare(b'once_response', uri=message.body.uri),
                    netaio.MessageType.OK
                )

            @server.on((netaio.MessageType.PUBLISH_URI, b'ephemeral_test'))
            def server_regular_handler(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                server_log.append(message)
                return netaio.Message.prepare(
                    netaio.Body.prepare(b'regular_response', uri=message.body.uri),
                    netaio.MessageType.OK
                )

            @client.on(netaio.MessageType.OK)
            def client_ok_handler(message: netaio.Message, _: asyncio.StreamWriter):
                client_log.append(message)

            server_task = asyncio.create_task(server.start())
            await asyncio.sleep(0.1)

            await client.connect()

            msg = netaio.Message.prepare(
                netaio.Body.prepare(b'test', uri=b'ephemeral_test'),
                netaio.MessageType.PUBLISH_URI
            )
            await client.send(msg)
            response = await client.receive_once()
            assert response.body.content == b'once_response'
            assert call_count['value'] == 1
            assert (netaio.MessageType.PUBLISH_URI, b'ephemeral_test') not in \
                server.ephemeral_handlers

            await client.send(msg)
            response = await client.receive_once()
            assert response.body.content == b'regular_response'
            assert call_count['value'] == 1

            auth_plugin2 = netaio.HMACAuthPlugin(
                config={"secret": "test2", "hmac_field": "hmac2"}
            )
            cipher_plugin2 = netaio.Sha256StreamCipherPlugin(
                config={"key": "test2", "iv_field": "iv2", "encrypt_uri": False}
            )

            @server.once(
                (netaio.MessageType.PUBLISH_URI, b'ephemeral_test2'),
                auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2
            )
            def server_ephemeral_handler_layer2(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                call_count2['value'] += 1
                return netaio.Message.prepare(
                    netaio.Body.prepare(b'layer2_response', uri=message.body.uri),
                    netaio.MessageType.OK
                )

            msg2 = netaio.Message.prepare(
                netaio.Body.prepare(b'test2', uri=b'ephemeral_test2'),
                netaio.MessageType.PUBLISH_URI
            )
            await client.send(
                msg2, auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2
            )
            response = await client.receive_once(
                auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2
            )
            assert response.body.content == b'layer2_response'
            assert call_count2['value'] == 1

            # test remove ephemeral handler
            assert netaio.MessageType.OK not in client.ephemeral_handlers
            @client.once(netaio.MessageType.OK)
            def client_ephemeral_handler(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                call_count['value'] += 1
                client_log.append(message)
                return None
            assert netaio.MessageType.OK in client.ephemeral_handlers
            client.remove_ephemeral_handler(netaio.MessageType.OK)
            assert netaio.MessageType.OK not in client.ephemeral_handlers


            # close client and cancel server
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

        print()
        print(f'{self.__class__.__name__}.test_ephemeral_handler_server_side')
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
            def server_subscribe(
                    message: netaio.Message, writer: asyncio.StreamWriter
                ):
                server_log.append(message)
                server.subscribe(message.body.uri, writer)
                return netaio.Message.prepare(
                    message.body,
                    netaio.MessageType.CONFIRM_SUBSCRIBE
                )

            @client.on(netaio.MessageType.CONFIRM_SUBSCRIBE)
            def client_confirm_subscribe(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
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

            # server should have the client as a peer because of the
            # ADVERTISE_PEER message
            assert len(server.peers) == 1, len(server.peers)
            assert client_peer.id in server.peers, server.peers
            assert server.peers[client_peer.id].data == client_peer.data, \
                (server.peers[client_peer.id].data, client_peer.data)
            # client should have the server as a peer because of the
            # PEER_DISCOVERED response
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
            assert server_log[-1].header.message_type is \
                netaio.MessageType.SUBSCRIBE_URI, server_log[-1].header
            assert len(client_log) == 1, len(client_log)
            assert client_log[-1].header.message_type is \
                netaio.MessageType.CONFIRM_SUBSCRIBE, client_log[-1].header

            # client should be subscribed
            assert len(server.subscriptions.get(b'subscribe/test', set())) == 1, \
                server.subscriptions

            # stop peer management on client and wait for the DISCONNECT message
            # to be received
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

            # server should have the client as a peer because of the
            # ADVERTISE_PEER messages
            assert len(server.peers) == 1, len(server.peers)
            assert client_peer.id in server.peers, server.peers
            # client should have the server as a peer because of the
            # PEER_DISCOVERED responses
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
        print(f'{self.__class__.__name__}.test_peer_management_e2e')
        asyncio.run(run_test())

    def test_peer_management_with_asymmetric_plugins(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            server_seed = urandom(32)
            server_vkey = SigningKey(server_seed).verify_key
            client_seed = urandom(32)
            client_vkey = SigningKey(client_seed).verify_key
            lock = tapescript.make_multisig_lock([server_vkey, client_vkey], 1)
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
                    "pubkey": bytes(server_cipher_plugin.pubk),
                })
            )
            client_peer = netaio.Peer(
                addrs=set(), id=b'client',
                data=netaio.DefaultPeerPlugin().encode_data({
                    "pubkey": bytes(client_cipher_plugin.pubk),
                })
            )

            server = netaio.TCPServer(port=self.PORT, local_peer=server_peer)
            client = netaio.TCPClient(port=self.PORT, local_peer=client_peer)

            @server.on(
                netaio.MessageType.REQUEST_URI,
                auth_plugin=server_auth_plugin, cipher_plugin=server_cipher_plugin
            )
            def server_handle_request_uri(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
                server_log.append(message)
                return netaio.Message.prepare(
                    netaio.Body.prepare(b'some content for u', uri=message.body.uri),
                    netaio.MessageType.RESPOND_URI
                )

            @client.on(
                netaio.MessageType.RESPOND_URI,
                auth_plugin=client_auth_plugin, cipher_plugin=client_cipher_plugin
            )
            def client_handle_respond_uri(
                    message: netaio.Message, _: asyncio.StreamWriter
                ):
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

            # server should have the client as a peer because of the
            # ADVERTISE_PEER message
            assert len(server.peers) == 1, len(server.peers)
            assert client_peer.id in server.peers, server.peers
            assert server.peers[client_peer.id].data == client_peer.data, \
                (server.peers[client_peer.id].data, client_peer.data)
            # client should have the server as a peer because of the
            # PEER_DISCOVERED response
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
            assert server_log[-1].header.message_type is \
                netaio.MessageType.REQUEST_URI, server_log[-1].header
            assert server_log[-1].body.uri == b'something', server_log[-1].body.uri
            assert server_log[-1].body.content == b'pls gibs me dat', \
                server_log[-1].body.content

            # client should have received the response from the server
            assert len(client_log) == 1, len(client_log)
            assert client_log[-1].header.message_type is \
                netaio.MessageType.RESPOND_URI, client_log[-1].header
            assert client_log[-1].body.uri == b'something', client_log[-1].body.uri
            assert client_log[-1].body.content == b'some content for u', \
                client_log[-1].body.content

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
        print(
            f'{self.__class__.__name__}.test_peer_management_with_asymmetric_plugins'
        )
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
            client = netaio.TCPClient(
                port=self.PORT, auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin
            )

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_request(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return message

            @server.on(
                netaio.MessageType.PUBLISH_URI,
                auth_plugin=auth_plugin, cipher_plugin=cipher_plugin
            )
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
        print(f'{self.__class__.__name__}.test_e2e_without_default_plugins')
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

            @server.on(
                netaio.MessageType.PUBLISH_URI,
                auth_plugin=auth_plugin, cipher_plugin=cipher_plugin
            )
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
            await client.send(
                publish_msg, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin
            )
            response = await client.receive_once(
                auth_plugin=auth_plugin, cipher_plugin=cipher_plugin
            )
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
        print(f'{self.__class__.__name__}.test_e2e_without_default_plugins_method_2')
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

            server = netaio.TCPServer(
                port=self.PORT, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin
            )
            client = netaio.TCPClient(
                port=self.PORT, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin
            )

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_request(message: netaio.Message, _: asyncio.StreamWriter):
                server_log.append(message)
                return message

            @server.on(
                netaio.MessageType.PUBLISH_URI,
                auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2
            )
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
            await client.send(
                publish_msg(), auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2
            )
            response = await client.receive_once(
                auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2
            )
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
            assert response.header.message_type == netaio.MessageType.AUTH_ERROR, \
                response

            # close client and stop server
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

        print()
        print(f'{self.__class__.__name__}.test_e2e_two_layers_of_plugins')
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
