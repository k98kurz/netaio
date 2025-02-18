from .common import (
    Header,
    Body,
    Message,
    HeaderProtocol,
    BodyProtocol,
    MessageProtocol,
    key_extractor,
    make_error_response,
    Handler
)
from typing import Any, Callable, Coroutine, Hashable
import asyncio




class TCPServer:
    host: str
    port: int
    handlers: dict[Hashable, Handler]
    header_class: type[HeaderProtocol]
    body_class: type[BodyProtocol]
    message_class: type[MessageProtocol]
    extract_key: Callable[[MessageProtocol], Hashable]
    respond_with_error: Callable[[str], MessageProtocol]
    subscriptions: dict[Hashable, set[asyncio.StreamWriter]]
    clients: set[asyncio.StreamWriter]

    def __init__(
            self, host="127.0.0.1", port=8888,
            header_class: type[HeaderProtocol] = Header,
            body_class: type[BodyProtocol] = Body,
            message_class: type[MessageProtocol] = Message,
            key_extractor: Callable[[MessageProtocol], Hashable] = key_extractor,
            make_error_response: Callable[[str], MessageProtocol] = make_error_response
        ):
        self.host = host
        self.port = port
        self.handlers = {}
        self.subscriptions = {}
        self.clients = set()
        self.header_class = header_class
        self.body_class = body_class
        self.message_class = message_class
        self.extract_key = key_extractor
        self.respond_with_error = make_error_response

    def add_handler(
            self, key: Hashable,
            handler: Handler
        ):
        """Register a handler for a specific key. The handler must
            accept a MessageProtocol object as an argument and return a
            MessageProtocol, None, or a Coroutine that resolves to
            MessageProtocol | None.
        """
        self.handlers[key] = handler

    def on(self, key: Hashable):
        """Decorator to register a handler for a specific key. The
            handler must accept a MessageProtocol object as an argument
            and return a MessageProtocol, None, or a Coroutine that
            resolves to a MessageProtocol or None.
        """
        def decorator(func: Handler):
            self.add_handler(key, func)
            return func
        return decorator

    def subscribe(self, key: Hashable, writer: asyncio.StreamWriter):
        """Subscribe a client to a specific key. The key must be a
            Hashable object.
        """
        if key not in self.subscriptions:
            self.subscriptions[key] = set()
        self.subscriptions[key].add(writer)

    def unsubscribe(self, key: Hashable, writer: asyncio.StreamWriter):
        """Unsubscribe a client from a specific key. If no subscribers
            are left, the key will be removed from the subscriptions
            dictionary.
        """
        if key in self.subscriptions:
            self.subscriptions[key].remove(writer)
            if not self.subscriptions[key]:
                del self.subscriptions[key]

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a client connection."""
        self.clients.add(writer)

        try:
            while True:
                try:
                    header_bytes = await reader.readexactly(self.header_class.header_length())
                    header = self.header_class.decode(header_bytes)

                    body_bytes = await reader.readexactly(header.body_length)
                    body = self.body_class.decode(body_bytes)

                    message = self.message_class(
                        header=header,
                        body=body
                    )

                    key = self.extract_key(message)

                    if key in self.handlers:
                        handler = self.handlers[key]
                        response = handler(message)
                        if isinstance(response, Coroutine):
                            response = await response
                    else:
                        response = self.respond_with_error("not found")

                    if response is not None:
                        writer.write(response.encode())
                        await writer.drain()

                except asyncio.IncompleteReadError:
                    break  # Client disconnected
                except Exception as e:
                    print("Error handling client:", e)
                    break
        finally:
            self.clients.discard(writer)
            for key, subscribers in list(self.subscriptions.items()):
                if writer in subscribers:
                    subscribers.discard(writer)
                    if not subscribers:
                        del self.subscriptions[key]
            writer.close()
            await writer.wait_closed()

    async def start(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        async with server:
            print(f"Server started on {self.host}:{self.port}")
            await server.serve_forever()

    async def send(
            self, client: asyncio.StreamWriter, data: bytes,
            collection: set = None
        ):
        """Helper coroutine to send data to a client. On error, it logs
            the exception and removes the client from the given
            collection.
        """
        try:
            client.write(data)
            await client.drain()
        except Exception as e:
            print("Error sending to client:", e)
            if collection is not None:
                collection.discard(client)

    async def broadcast(self, message: MessageProtocol):
        """Send the message to all connected clients concurrently using
            asyncio.gather.
        """
        data = message.encode()
        tasks = [self.send(client, data, self.clients) for client in self.clients]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def notify(self, key: Hashable, message: MessageProtocol):
        """Send the message to all subscribed clients for the given key
            concurrently using asyncio.gather.
        """
        if key not in self.subscriptions:
            return

        subscribers = self.subscriptions.get(key, set())
        if not subscribers:
            del self.subscriptions[key]
            return

        data = message.encode()
        tasks = [self.send(client, data, subscribers) for client in subscribers]
        await asyncio.gather(*tasks, return_exceptions=True)
