from context import netaio
from random import randint
import asyncio
import unittest
import logging


class TestUDPE2E(unittest.TestCase):
    PORT = randint(10000, 65535)

    @classmethod
    def setUpClass(cls):
        netaio.default_client_logger.setLevel(logging.INFO)
        netaio.default_server_logger.setLevel(logging.INFO)

    def test_e2e(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})
            default_server_handler = lambda msg, addr: server_log.append(msg)
            default_client_handler = lambda msg, addr: client_log.append(msg)

            server = netaio.UDPNode(
                port=self.PORT, auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin, logger=netaio.default_server_logger,
                default_handler=default_server_handler, ignore_own_ip=False
            )
            client = netaio.UDPNode(
                port=self.PORT+1, auth_plugin=auth_plugin,
                cipher_plugin=cipher_plugin, logger=netaio.default_client_logger,
                default_handler=default_client_handler, ignore_own_ip=False
            )
            server_addr = ('0.0.0.0', self.PORT)

            client_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
                netaio.MessageType.PUBLISH_URI
            )
            client_multicast_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'multicast'),
                netaio.MessageType.ADVERTISE_PEER
            )
            client_subscribe_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'', uri=b'subscribe/test'),
                netaio.MessageType.SUBSCRIBE_URI
            )
            client_unsubscribe_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'', uri=b'subscribe/test'),
                netaio.MessageType.UNSUBSCRIBE_URI
            )
            server_echo_msg = lambda msg: netaio.Message.prepare(
                netaio.Body.prepare(msg.body.content, uri=msg.body.uri),
                netaio.MessageType.OK
            )
            server_notify_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'subscribe/test'),
                netaio.MessageType.NOTIFY_URI
            )
            expected_response = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
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

            @server.on(netaio.MessageType.PUBLISH_URI)
            def server_echo(message: netaio.Message, _: tuple[str, int]):
                server_log.append(message)
                return server_echo_msg(message)

            @client.on(netaio.MessageType.OK)
            def client_echo(message: netaio.Message, addr: tuple[str, int]):
                client_log.append(message)

            @server.on(netaio.MessageType.ADVERTISE_PEER)
            def server_advertise_echo(message: netaio.Message, _: tuple[str, int]):
                print("server received ADVERTISE_PEER")
                server_log.append(message)
                return message

            @client.on(netaio.MessageType.ADVERTISE_PEER)
            def client_advertise(message: netaio.Message, _: tuple[str, int]):
                print("client received ADVERTISE_PEER")
                client_log.append(message)

            @server.on(netaio.MessageType.SUBSCRIBE_URI)
            def server_subscribe(message: netaio.Message, addr: tuple[str, int]):
                server_log.append(message)
                server.subscribe(message.body.uri, addr)
                return expected_subscribe_response

            @server.on(netaio.MessageType.UNSUBSCRIBE_URI)
            def server_unsubscribe(message: netaio.Message, addr: tuple[str, int]):
                server_log.append(message)
                server.unsubscribe(message.body.uri, addr)
                return expected_unsubscribe_response

            @client.on(netaio.MessageType.NOTIFY_URI)
            def client_notify(message: netaio.Message, addr: tuple[str, int]):
                client_log.append(message)

            assert len(server_log) == 0
            assert len(client_log) == 0

            await server.start()
            await client.start()

            # Wait briefly to allow the nodes time to bind and begin listening.
            await asyncio.sleep(0.01)

            client.send(client_msg, addr=server_addr)
            await asyncio.sleep(0.1)
            assert len(server_log) == 1, len(server_log)
            assert len(client_log) == 1, len(client_log)
            response = client_log[-1]
            assert response.header.message_type == expected_response.header.message_type, \
                (response.header.message_type, expected_response.header.message_type)
            assert response.body.uri == expected_response.body.uri, \
                (response.body.uri, expected_response.body.uri)
            assert response.body.content == expected_response.body.content, \
                (response.body.content, expected_response.body.content)

            client_log.clear()
            server_log.clear()
            client.multicast(client_multicast_msg, port=server.port)
            await asyncio.sleep(0.1)
            # assert len(server_log) == 1, len(server_log)
            assert len(client_log) == 1, len(client_log)
            response = client_log[-1]
            expected_response = client_multicast_msg
            assert response.header.message_type == expected_response.header.message_type, \
                (response.header.message_type, expected_response.header.message_type)
            assert response.body.uri == expected_response.body.uri, \
                (response.body.uri, expected_response.body.uri)

            server_log.clear()
            client.send(client_subscribe_msg, addr=server_addr)
            await asyncio.sleep(0.1)
            assert len(server_log) == 1, len(server_log)
            assert len(client_log) == 2, len(client_log)
            response = client_log[-1]
            assert response.header.message_type == expected_subscribe_response.header.message_type, \
                (response.header.message_type, expected_subscribe_response.header.message_type)
            assert response.body.uri == expected_subscribe_response.body.uri, \
                (response.body.uri, expected_subscribe_response.body.uri)
            assert response.body.content == expected_subscribe_response.body.content, \
                (response.body.content, expected_subscribe_response.body.content)

            client_log.clear()
            server_log.clear()
            server.notify(b'subscribe/test', server_notify_msg)
            await asyncio.sleep(0.1)
            assert len(server_log) == 0, len(server_log)
            assert len(client_log) == 1, len(client_log)
            response = client_log[-1]
            assert response.header.message_type == server_notify_msg.header.message_type, \
                (response.header.message_type, server_notify_msg.header.message_type)
            assert response.body.uri == server_notify_msg.body.uri, \
                (response.body.uri, server_notify_msg.body.uri)
            assert response.body.content == server_notify_msg.body.content, \
                (response.body.content, server_notify_msg.body.content)

            client_log.clear()
            server_log.clear()
            client.send(client_unsubscribe_msg, addr=server_addr)
            await asyncio.sleep(0.1)
            assert len(server_log) == 1, len(server_log)
            assert len(client_log) == 1, len(client_log)
            response = client_log[-1]
            assert response.header.message_type == expected_unsubscribe_response.header.message_type, \
                (response.header.message_type, expected_unsubscribe_response.header.message_type)
            assert response.body.uri == expected_unsubscribe_response.body.uri, \
                (response.body.uri, expected_unsubscribe_response.body.uri)
            assert response.body.content == expected_unsubscribe_response.body.content, \
                (response.body.content, expected_unsubscribe_response.body.content)

            # test auth failure
            client.auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test2"})
            client_log.clear()
            client.send(client_msg, server_addr)
            await asyncio.sleep(0.1)
            assert len(client_log) == 0, len(client_log) # response error message should be dropped

            # set different error handler on client
            def log_auth_error(client, auth_plugin, msg):
                client.logger.debug("log_auth_error called")
                client_log.append(msg)
                return None
            client.handle_auth_error = log_auth_error

            # test auth failure again
            client.auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test2"})
            client_log.clear()
            client.send(client_msg, server_addr)
            await asyncio.sleep(0.1)
            assert len(client_log) == 1, len(client_log)
            response = client_log[-1]
            assert response.header.message_type == netaio.MessageType.AUTH_ERROR, response

            # stop nodes
            await server.stop()
            await client.stop()
            await asyncio.sleep(0.1)

        print()
        asyncio.run(run_test())

    def test_peer_management_e2e(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            default_server_handler = lambda msg, addr: server_log.append(msg)
            default_client_handler = lambda msg, addr: client_log.append(msg)

            server = netaio.UDPNode(
                port=self.PORT, default_handler=default_server_handler,
                logger=netaio.default_server_logger,
                local_peer=netaio.Peer(addrs={('127.0.0.1', self.PORT)}, peer_id=b'server', peer_data=b'abc'),
                ignore_own_ip=False
            )
            client = netaio.UDPNode(
                port=self.PORT+1, default_handler=default_client_handler,
                logger=netaio.default_client_logger,
                local_peer=netaio.Peer(addrs={('127.0.0.1', self.PORT+1)}, peer_id=b'client', peer_data=b'def'),
                ignore_own_ip=False
            )

            @server.on(netaio.MessageType.ADVERTISE_PEER)
            def server_advertise(message: netaio.Message, _: tuple[str, int]):
                server_log.append(message)

            @client.on(netaio.MessageType.ADVERTISE_PEER)
            def client_advertise(message: netaio.Message, _: tuple[str, int]):
                client_log.append(message)

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_request(message: netaio.Message, _: tuple[str, int]):
                server_log.append(message)
                return netaio.Message.prepare(
                    message.body,
                    netaio.MessageType.RESPOND_URI
                )

            @client.on(netaio.MessageType.RESPOND_URI)
            def client_request(message: netaio.Message, _: tuple[str, int]):
                client_log.append(message)

            await server.start()
            await client.start()

            # Wait briefly to allow the nodes time to bind and begin listening.
            await asyncio.sleep(0.01)

            # monkey-patch the client port to make local multicast work
            client.port = self.PORT

            # begin automatic peer advertisement
            await server.begin_peer_advertisement(every=0.1)
            await client.begin_peer_advertisement(every=0.1)

            # wait for peers to be advertised
            await asyncio.sleep(0.2)

            # stop peer advertisement
            await server.stop_peer_advertisement()
            await client.stop_peer_advertisement()

            assert len(server_log) > 0, len(server_log)
            for msg in server_log:
                assert msg.header.message_type is netaio.MessageType.ADVERTISE_PEER, msg.header
            # drain DISCONNECT messages
            await asyncio.sleep(0.1)
            assert server_log[-1].header.message_type is netaio.MessageType.DISCONNECT, server_log[-1].header
            server_log.clear()
            # it is a known issue that the client will not receive the ADVERTISE_PEER message

            # begin automatic peer management of server
            await server.manage_peers_automatically(advertise_every=0.1, peer_timeout=0.3)

            # wait some time to prove the server does not add itself as a peer
            await asyncio.sleep(0.2)
            assert len(server.peers) == 0, len(server.peers)

            # begin automatic peer management of client
            await client.manage_peers_automatically(advertise_every=0.1, peer_timeout=0.3)

            # wait for peers to be discovered
            await asyncio.sleep(0.2)

            # server should have the client as a peer because of the ADVERTISE_PEER messages
            assert len(server.peers) == 1, len(server.peers)
            assert b'client' in server.peers, server.peers
            # client should have the server as a peer because of the PEER_DISCOVERED responses
            assert len(client.peers) == 1, len(client.peers)
            assert b'server' in client.peers, client.peers

            # client broadcasts a message to all peers
            client_log.clear()
            server_log.clear()
            client.broadcast(netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'broadcast'),
                netaio.MessageType.REQUEST_URI
            ))

            # server should receive the message and respond
            await asyncio.sleep(0.1)
            assert len(server_log) == 1, len(server_log)
            assert server_log[-1].header.message_type is netaio.MessageType.REQUEST_URI, server_log[-1].header
            assert len(client_log) == 1, len(client_log)
            assert client_log[-1].header.message_type is netaio.MessageType.RESPOND_URI, client_log[-1].header

            # stop peer management on client and wait for the DISCONNECT message to be received
            await client.stop_peer_management()
            await asyncio.sleep(0.1)
            assert len(server.peers) == 0, len(server.peers)

            # begin automatic peer management
            await client.manage_peers_automatically(advertise_every=0.1, peer_timeout=0.3)

            # wait for peers to be discovered
            await asyncio.sleep(0.2)

            # server should have the client as a peer because of the ADVERTISE_PEER messages
            assert len(server.peers) == 1, len(server.peers)
            assert b'client' in server.peers, server.peers
            # client should have the server as a peer because of the PEER_DISCOVERED responses
            assert len(client.peers) == 1, len(client.peers)
            assert b'server' in client.peers, client.peers

            # stop peer management on server but ignore the DISCONNECT message
            client.remove_handler((netaio.MessageType.DISCONNECT, b'netaio'))
            await server.stop_peer_management()

            # wait for server to time out
            await asyncio.sleep(1)
            assert len(client.peers) == 0

            # stop nodes
            await server.stop()
            await client.stop() # peer management will be stopped automatically
            await asyncio.sleep(0.1)

        print()
        asyncio.run(run_test())

    def test_peer_management_with_plugins_e2e(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            default_server_handler = lambda msg, addr: server_log.append(msg)
            default_client_handler = lambda msg, addr: client_log.append(msg)
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            auth_plugin2 = netaio.HMACAuthPlugin(config={"secret": "test2", "hmac_field": "hmac2"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})
            cipher_plugin2 = netaio.Sha256StreamCipherPlugin(config={
                "key": "test2",
                "iv_field": "iv2",
                "encrypt_uri": False
            })

            server = netaio.UDPNode(
                port=self.PORT, default_handler=default_server_handler,
                logger=netaio.default_server_logger,
                local_peer=netaio.Peer(addrs={('127.0.0.1', self.PORT)}, peer_id=b'server', peer_data=b'abc'),
                auth_plugin=auth_plugin, cipher_plugin=cipher_plugin,
                ignore_own_ip=False
            )
            client = netaio.UDPNode(
                port=self.PORT+1, default_handler=default_client_handler,
                logger=netaio.default_client_logger,
                local_peer=netaio.Peer(addrs={('127.0.0.1', self.PORT+1)}, peer_id=b'client', peer_data=b'def'),
                auth_plugin=auth_plugin, cipher_plugin=cipher_plugin,
                ignore_own_ip=False
            )

            await server.start()
            await client.start()

            # Wait briefly to allow the nodes time to bind and begin listening.
            await asyncio.sleep(0.01)

            # monkey-patch the client port to make local multicast work
            client.port = self.PORT

            # begin automatic peer advertisement
            await server.begin_peer_advertisement(every=0.1)
            await client.begin_peer_advertisement(every=0.1)

            # wait for peers to be advertised
            await asyncio.sleep(0.3)

            # stop peer advertisement
            await server.stop_peer_advertisement()
            await client.stop_peer_advertisement()

            assert len(server_log) > 0, len(server_log)
            for msg in server_log:
                assert msg.header.message_type is netaio.MessageType.ADVERTISE_PEER, msg.header
            server_log.clear()
            # it is a known issue that the client will not receive the ADVERTISE_PEER message

            # begin automatic peer management
            await server.manage_peers_automatically(advertise_every=0.1, peer_timeout=0.3)
            await client.manage_peers_automatically(advertise_every=0.1, peer_timeout=0.3)

            # wait for peers to be discovered
            await asyncio.sleep(0.2)

            # stop peer management on client
            await client.stop_peer_management()

            # server should have the client as a peer because of the ADVERTISE_PEER messages
            assert len(server.peers) == 1, len(server.peers)
            assert b'client' in server.peers, server.peers
            # client should have the server as a peer because of the PEER_DISCOVERED responses
            assert len(client.peers) == 1, len(client.peers)
            assert b'server' in client.peers, client.peers

            # wait for client to time out
            await asyncio.sleep(0.4)
            await server.stop_peer_management()

            assert len(server.peers) == 0, len(server.peers)

            # test with an additional layer of plugins
            await server.manage_peers_automatically(
                advertise_every=0.1, peer_timeout=0.3, auth_plugin=auth_plugin2,
                cipher_plugin=cipher_plugin2
            )
            await client.manage_peers_automatically(
                advertise_every=0.1, peer_timeout=0.3, auth_plugin=auth_plugin2,
                cipher_plugin=cipher_plugin2
            )

            # wait for peers to be discovered
            await asyncio.sleep(0.2)

            # stop peer management on client
            await client.stop_peer_management()

            # server should have the client as a peer because of the ADVERTISE_PEER messages
            assert len(server.peers) == 1, len(server.peers)
            assert b'client' in server.peers, server.peers
            # client should have the server as a peer because of the PEER_DISCOVERED responses
            assert len(client.peers) == 1, len(client.peers)
            assert b'server' in client.peers, client.peers

            # stop nodes
            await server.stop() # peer management will be stopped automatically
            await client.stop()
            await asyncio.sleep(0.1)

        print()
        asyncio.run(run_test())


class TestUDPE2EWithoutDefaultPlugins(unittest.TestCase):
    PORT = randint(10000, 65535)

    @classmethod
    def setUpClass(cls):
        netaio.default_server_logger.setLevel(logging.INFO)
        netaio.default_client_logger.setLevel(logging.INFO)

    def test_e2e_without_default_plugins(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})
            cipher_plugin = netaio.Sha256StreamCipherPlugin(config={"key": "test"})
            default_server_handler = lambda msg, addr: server_log.append(msg)
            default_client_handler = lambda msg, addr: client_log.append(msg)

            server = netaio.UDPNode(
                port=self.PORT, default_handler=default_server_handler,
                logger=netaio.default_server_logger,
                ignore_own_ip=False
            )
            client = netaio.UDPNode(
                port=self.PORT+1, default_handler=default_client_handler,
                logger=netaio.default_client_logger,
                ignore_own_ip=False
            )
            server_addr = ('0.0.0.0', self.PORT)

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_request(message: netaio.Message, _: tuple[str, int]):
                server_log.append(message)
                return message

            @server.on(netaio.MessageType.PUBLISH_URI, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)
            def server_publish(message: netaio.Message, _: tuple[str, int]):
                server_log.append(message)
                return message

            @client.on(netaio.MessageType.PUBLISH_URI, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)
            def client_publish(message: netaio.Message, _: tuple[str, int]):
                client_log.append(message)

            echo_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
                netaio.MessageType.REQUEST_URI
            )
            publish_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'publish'),
                netaio.MessageType.PUBLISH_URI
            )

            assert len(server_log) == 0
            assert len(client_log) == 0

            await server.start()
            await client.start()

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # send to unprotected route
            client.send(echo_msg, server_addr)
            await asyncio.sleep(0.1)
            assert len(client_log) == 1, len(client_log)
            response = client_log[-1]
            assert response is not None
            assert response.encode() == echo_msg.encode(), \
                (response.encode().hex(), echo_msg.encode().hex())

            # send to protected route
            client.send(publish_msg, server_addr, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin)
            await asyncio.sleep(0.1)
            assert len(client_log) == 2, len(client_log)
            response = client_log[-1]
            assert response is not None
            assert response.body.content == publish_msg.body.content, \
                (response.body.content, publish_msg.body.content)
            assert response.body.uri == publish_msg.body.uri, \
                (response.body.uri, publish_msg.body.uri)
            assert response.header.message_type == publish_msg.header.message_type, \
                (response.header.message_type, publish_msg.header.message_type)

            # stop nodes
            await server.stop()
            await client.stop()
            await asyncio.sleep(0.1)

        print()
        asyncio.run(run_test())


class TestUDPE2ETwoLayersOfPlugins(unittest.TestCase):
    PORT = randint(10000, 65535)

    @classmethod
    def setUpClass(cls):
        netaio.default_server_logger.setLevel(logging.INFO)
        netaio.default_client_logger.setLevel(logging.INFO)

    def test_e2e_two_layers_of_plugins(self):
        async def run_test():
            server_log: list[netaio.Message] = []
            client_log: list[netaio.Message] = []
            default_server_handler = lambda msg, addr: server_log.append(msg)
            default_client_handler = lambda msg, addr: client_log.append(msg)
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

            server = netaio.UDPNode(
                port=self.PORT, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin,
                default_handler=default_server_handler, logger=netaio.default_server_logger,
                ignore_own_ip=False
            )
            client = netaio.UDPNode(
                port=self.PORT+1, auth_plugin=auth_plugin, cipher_plugin=cipher_plugin,
                default_handler=default_client_handler, logger=netaio.default_client_logger,
                ignore_own_ip=False
            )
            server_addr = ('0.0.0.0', self.PORT)

            @server.on(netaio.MessageType.REQUEST_URI)
            def server_request(message: netaio.Message, _: tuple[str, int]):
                server_log.append(message)
                return message

            @server.on(netaio.MessageType.PUBLISH_URI, auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2)
            def server_publish(message: netaio.Message, _: tuple[str, int]):
                server_log.append(message)
                return message

            @client.on(netaio.MessageType.PUBLISH_URI, auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2)
            def client_publish(message: netaio.Message, _: tuple[str, int]):
                client_log.append(message)

            echo_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
                netaio.MessageType.REQUEST_URI
            )
            publish_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'publish'),
                netaio.MessageType.PUBLISH_URI
            )

            assert len(server_log) == 0
            assert len(client_log) == 0

            await server.start()
            await client.start()

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # send to once-protected route
            client.send(echo_msg, server_addr)
            await asyncio.sleep(0.1)
            assert len(client_log) == 1, len(client_log)
            response = client_log[-1]
            assert response is not None
            assert response.body.content == echo_msg.body.content, \
                (response.body.content, echo_msg.body.content)
            assert response.body.uri == echo_msg.body.uri, \
                (response.body.uri, echo_msg.body.uri)
            assert response.header.message_type == echo_msg.header.message_type, \
                (response.header.message_type, echo_msg.header.message_type)

            # send to twice-protected route
            client.send(publish_msg, server_addr, auth_plugin=auth_plugin2, cipher_plugin=cipher_plugin2)
            await asyncio.sleep(0.1)
            assert len(client_log) == 2, len(client_log)
            response = client_log[-1]
            assert response is not None
            assert response.body.content == publish_msg.body.content, \
                (response.body.content, publish_msg.body.content)
            assert response.body.uri == publish_msg.body.uri, \
                (response.body.uri, publish_msg.body.uri)
            assert response.header.message_type == publish_msg.header.message_type, \
                (response.header.message_type, publish_msg.header.message_type)

            assert len(server_log) == 2, len(server_log)

            # close client and stop server
            await client.stop()
            await server.stop()
            await asyncio.sleep(0.1)

        print()
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
