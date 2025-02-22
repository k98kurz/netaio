from context import netaio
from random import randint
import asyncio
import unittest
import logging


class TestE2E(unittest.TestCase):
    PORT = randint(10000, 65535)

    @classmethod
    def setUpClass(cls):
        netaio.default_server_logger.setLevel(logging.DEBUG)
        netaio.default_client_logger.setLevel(logging.DEBUG)

    def test_e2e(self):
        async def run_test():
            server_log = []
            client_log = []
            auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test"})

            server = netaio.TCPServer(port=self.PORT, auth_plugin=auth_plugin)
            client = netaio.TCPClient(port=self.PORT, auth_plugin=auth_plugin)

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

            self.assertEqual(len(server_log), 0)
            self.assertEqual(len(client_log), 0)

            # Start the server as a background task.
            server_task = asyncio.create_task(server.start())

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            # connect client
            await client.connect()

            await client.send(client_msg)
            response = await client.receive_once()
            self.assertEqual(response, expected_response)

            await client.send(client_subscribe_msg)
            response = await client.receive_once()
            self.assertEqual(response, expected_subscribe_response)

            await server.notify(b'subscribe/test', server_notify_msg)
            response = await client.receive_once()
            self.assertEqual(response, server_notify_msg)

            await client.send(client_unsubscribe_msg)
            response = await client.receive_once()
            self.assertEqual(response, expected_unsubscribe_response)

            self.assertEqual(len(server_log), 3)
            self.assertEqual(len(client_log), 2)

            # test auth failure
            client.auth_plugin = netaio.HMACAuthPlugin(config={"secret": "test2"})
            await client.send(client_msg)
            response = await client.receive_once()
            self.assertIsNone(response)

            # close client and stop server
            await client.close()
            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
