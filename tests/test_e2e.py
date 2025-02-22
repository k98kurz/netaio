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
            server_msg = netaio.Message.prepare(
                netaio.Body.prepare(b'hello', uri=b'echo'),
                netaio.MessageType.OK
            )
            expected_response = netaio.Message.prepare(
                netaio.Body.prepare(b'DO NOT SEND', uri=b'NONE'),
                netaio.MessageType.OK
            )

            @server.on((netaio.MessageType.PUBLISH_URI, b'echo'))
            def server_echo(message: netaio.Message):
                server_log.append(message)
                return server_msg

            @client.on(netaio.MessageType.OK)
            def client_echo(message: netaio.Message):
                client_log.append(message)
                return expected_response

            self.assertEqual(len(server_log), 0)
            self.assertEqual(len(client_log), 0)

            # Start the server as a background task.
            server_task = asyncio.create_task(server.start())

            # Wait briefly to allow the server time to bind and listen.
            await asyncio.sleep(0.1)

            await client.connect()
            await client.send(client_msg)
            response = await client.receive_once()
            self.assertEqual(response, expected_response)
            await client.close()

            self.assertEqual(len(server_log), 1)
            self.assertEqual(len(client_log), 1)

            server_task.cancel()

            try:
                await server_task
            except asyncio.CancelledError:
                pass

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
