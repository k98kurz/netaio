from .auth import AuthPluginProtocol
from .common import (
    Header,
    AuthFields,
    Body,
    Message,
    HeaderProtocol,
    BodyProtocol,
    MessageProtocol,
    keys_extractor,
    make_error_response,
    Handler,
    default_server_logger
)
from typing import Callable, Coroutine, Hashable
import asyncio
import logging


def not_found_handler(_: MessageProtocol) -> MessageProtocol | None:
    return make_error_response("not found")


class TCPServer:
    host: str
    port: int
    handlers: dict[Hashable, tuple[Handler, AuthPluginProtocol|None]]
    default_handler: Handler
    header_class: type[HeaderProtocol]
    body_class: type[BodyProtocol]
    message_class: type[MessageProtocol]
    extract_keys: Callable[[MessageProtocol], list[Hashable]]
    make_error: Callable[[str], MessageProtocol]
    subscriptions: dict[Hashable, set[asyncio.StreamWriter]]
    clients: set[asyncio.StreamWriter]
    logger: logging.Logger
    auth_plugin: AuthPluginProtocol

    def __init__(
            self, host: str = "127.0.0.1", port: int = 8888,
            header_class: type[HeaderProtocol] = Header,
            body_class: type[BodyProtocol] = Body,
            message_class: type[MessageProtocol] = Message,
            keys_extractor: Callable[[MessageProtocol], list[Hashable]] = keys_extractor,
            make_error_response: Callable[[str], MessageProtocol] = make_error_response,
            default_handler: Handler = not_found_handler,
            logger: logging.Logger = default_server_logger,
            auth_plugin: AuthPluginProtocol = None
        ):
        self.host = host
        self.port = port
        self.handlers = {}
        self.subscriptions = {}
        self.clients = set()
        self.header_class = header_class
        self.body_class = body_class
        self.message_class = message_class
        self.extract_keys = keys_extractor
        self.make_error = make_error_response
        self.default_handler = default_handler
        self.logger = logger
        self.auth_plugin = auth_plugin

    def add_handler(
            self, key: Hashable,
            handler: Handler,
            auth_plugin: AuthPluginProtocol = None
        ):
        """Register a handler for a specific key. The handler must
            accept a MessageProtocol object as an argument and return a
            MessageProtocol, None, or a Coroutine that resolves to
            MessageProtocol | None.
        """
        self.logger.debug("Adding handler for key=%s", key)
        self.handlers[key] = (handler, auth_plugin)

    def on(self, key: Hashable, auth_plugin: AuthPluginProtocol = None):
        """Decorator to register a handler for a specific key. The
            handler must accept a MessageProtocol object as an argument
            and return a MessageProtocol, None, or a Coroutine that
            resolves to a MessageProtocol or None.
        """
        def decorator(func: Handler):
            self.add_handler(key, func, auth_plugin)
            return func
        return decorator

    def subscribe(self, key: Hashable, writer: asyncio.StreamWriter):
        """Subscribe a client to a specific key. The key must be a
            Hashable object.
        """
        self.logger.info("Subscribing client to key=%s", key)
        if key not in self.subscriptions:
            self.subscriptions[key] = set()
        self.subscriptions[key].add(writer)

    def unsubscribe(self, key: Hashable, writer: asyncio.StreamWriter):
        """Unsubscribe a client from a specific key. If no subscribers
            are left, the key will be removed from the subscriptions
            dictionary.
        """
        self.logger.info("Unsubscribing client from key=%s", key)
        if key in self.subscriptions:
            self.subscriptions[key].remove(writer)
            if not self.subscriptions[key]:
                del self.subscriptions[key]

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a client connection. When a client connects, it is
            added to the clients set. The client is then read from until
            the connection is lost, and the proper handlers are called
            if they are defined and the message is valid.
        """
        self.logger.info("Client connected from %s", writer.get_extra_info("peername"))
        self.clients.add(writer)
        header_length = self.header_class.header_length()

        try:
            while True:
                auth_plugin = None
                header_bytes = await reader.readexactly(header_length)
                header = self.header_class.decode(header_bytes)

                auth_bytes = await reader.readexactly(header.auth_length)
                auth = AuthFields.decode(auth_bytes)

                body_bytes = await reader.readexactly(header.body_length)
                body = self.body_class.decode(body_bytes)

                message = self.message_class(
                    header=header,
                    auth_data=auth,
                    body=body
                )

                if not message.check():
                    self.logger.info("Invalid message received from %s", writer.get_extra_info("peername"))
                    response = self.make_error("invalid message")
                else:
                    if self.auth_plugin is not None:
                        if not self.auth_plugin.check(auth, body):
                            self.logger.info("Invalid auth fields received from %s", writer.get_extra_info("peername"))
                            response = self.auth_plugin.error()
                            await self.send(writer, response.encode())
                            continue
                        else:
                            self.logger.debug("Valid auth fields received from %s", writer.get_extra_info("peername"))

                    keys = self.extract_keys(message)
                    self.logger.info("Message received from %s with keys=%s", writer.get_extra_info("peername"), keys)

                    for key in keys:
                        if key in self.handlers:
                            self.logger.info("Calling handler for key=%s", key)
                            handler, auth_plugin = self.handlers[key]

                            if auth_plugin is not None:
                                if not auth_plugin.check(auth, body):
                                    self.logger.info("Invalid auth fields received from %s", writer.get_extra_info("peername"))
                                    response = auth_plugin.error()
                                    await self.send(writer, response.encode())
                                    continue

                            response = handler(message)
                            if isinstance(response, Coroutine):
                                response = await response
                            break
                    else:
                        self.logger.debug("No handler found for keys=%s, calling default handler", keys)
                        response = self.default_handler(message)

                if response is not None:
                    set_auth_fields = False
                    if self.auth_plugin is not None:
                        self.auth_plugin.make(response.auth_data, response.body)
                        set_auth_fields = True
                    if auth_plugin is not None:
                        auth_plugin.make(response.auth_data, response.body)
                        set_auth_fields = True
                    if set_auth_fields:
                        self.logger.debug("Set auth_fields for response")
                    await self.send(writer, response.encode())
        except asyncio.IncompleteReadError:
            self.logger.info("Client disconnected from %s", writer.get_extra_info("peername"))
            pass  # Client disconnected
        except ConnectionResetError:
            self.logger.info("Client disconnected from %s", writer.get_extra_info("peername"))
            pass  # Client disconnected
        except Exception as e:
            self.logger.error("Error handling client:", exc_info=True)
        finally:
            self.logger.info("Removing closed client %s", writer.get_extra_info("peername"))
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
            self.logger.info(f"Server started on {self.host}:{self.port}")
            await server.serve_forever()

    async def send(
            self, client: asyncio.StreamWriter, data: bytes,
            collection: set = None
        ):
        """Helper coroutine to send data to a client. On error, it logs
            the exception and removes the client from the given
            collection.
        """
        self.logger.debug("Sending data to %s", client.get_extra_info("peername"))
        try:
            client.write(data)
            await client.drain()
        except Exception as e:
            self.logger.error("Error sending to client:", exc_info=True)
            if collection is not None:
                self.logger.info("Removing client %s from collection", client.get_extra_info("peername"))
                collection.discard(client)

    async def broadcast(self, message: MessageProtocol, use_auth: bool = True):
        """Send the message to all connected clients concurrently using
            asyncio.gather.
        """
        self.logger.debug("Broadcasting message to all clients")
        if use_auth and self.auth_plugin is not None:
            self.logger.debug("Setting auth fields for broadcast message")
            self.auth_plugin.make(message.auth_data, message.body)
        data = message.encode()
        tasks = [self.send(client, data, self.clients) for client in self.clients]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def notify(self, key: Hashable, message: MessageProtocol, use_auth: bool = True):
        """Send the message to all subscribed clients for the given key
            concurrently using asyncio.gather.
        """
        if key not in self.subscriptions:
            self.logger.debug("No subscribers found for key=%s, skipping notification", key)
            return

        self.logger.debug("Notifying %d clients for key=%s", len(self.subscriptions[key]), key)

        if use_auth and self.auth_plugin is not None:
            self.logger.debug("Setting auth fields for notify message")
            self.auth_plugin.make(message.auth_data, message.body)

        subscribers = self.subscriptions.get(key, set())
        if not subscribers:
            self.logger.debug("No subscribers found for key=%s, removing from subscriptions", key)
            del self.subscriptions[key]
            return

        data = message.encode()
        tasks = [self.send(client, data, subscribers) for client in subscribers]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.logger.debug("Notified %d clients for key=%s", len(subscribers), key)

    def set_logger(self, logger: logging.Logger):
        """Replace the current logger."""
        self.logger = logger
