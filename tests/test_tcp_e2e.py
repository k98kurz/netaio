from context import netaio
from random import randint
import asyncio
import unittest
import logging


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
