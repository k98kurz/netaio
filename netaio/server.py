from .auth import AuthPluginProtocol
from .cipher import CipherPluginProtocol
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


def not_found_handler(*_) -> MessageProtocol | None:
    return make_error_response("not found")


class TCPServer:
    """TCP server class."""
    host: str
    port: int
    handlers: dict[Hashable, tuple[Handler, AuthPluginProtocol|None, CipherPluginProtocol|None]]
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
    cipher_plugin: CipherPluginProtocol

    def __init__(
            self, host: str = "0.0.0.0", port: int = 8888,
            header_class: type[HeaderProtocol] = Header,
            body_class: type[BodyProtocol] = Body,
            message_class: type[MessageProtocol] = Message,
            keys_extractor: Callable[[MessageProtocol], list[Hashable]] = keys_extractor,
            make_error_response: Callable[[str], MessageProtocol] = make_error_response,
            default_handler: Handler = not_found_handler,
            logger: logging.Logger = default_server_logger,
            auth_plugin: AuthPluginProtocol = None,
            cipher_plugin: CipherPluginProtocol = None
        ):
        """Initialize the TCPServer.

        Args:
            host: The host to listen on.
            port: The port to listen on.
            header_class: The header class to use.
            body_class: The body class to use.
            message_class: The message class to use.
            keys_extractor: A function that extracts the keys from a message.
            make_error_response: A function that makes an error response.
            default_handler: The default handler to use for messages that
                do not match any registered handler keys.
            logger: The logger to use.
            auth_plugin: The auth plugin to use.
            cipher_plugin: The cipher plugin to use.
        """
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
        self.cipher_plugin = cipher_plugin

    def add_handler(
            self, key: Hashable,
            handler: Handler,
            auth_plugin: AuthPluginProtocol = None,
            cipher_plugin: CipherPluginProtocol = None
        ):
        """Register a handler for a specific key. The handler must
            accept a MessageProtocol object as an argument and return a
            MessageProtocol, None, or a Coroutine that resolves to
            MessageProtocol | None. If an auth plugin is provided, it
            will be used to check the message in addition to any auth
            plugin that is set on the server. If a cipher plugin is
            provided, it will be used to decrypt the message in addition
            to any cipher plugin that is set on the server. These
            plugins will also be used for preparing any response
            message sent by the handler.
        """
        self.logger.debug("Adding handler for key=%s", key)
        self.handlers[key] = (handler, auth_plugin, cipher_plugin)

    def on(
            self, key: Hashable,
            auth_plugin: AuthPluginProtocol = None,
            cipher_plugin: CipherPluginProtocol = None
        ):
        """Decorator to register a handler for a specific key. The
            handler must accept a MessageProtocol object as an argument
            and return a MessageProtocol, None, or a Coroutine that
            resolves to a MessageProtocol or None. If an auth plugin is
            provided, it will be used to check the message in addition
            to any auth plugin that is set on the server. If a cipher
            plugin is provided, it will be used to decrypt the message in
            addition to any cipher plugin that is set on the server.
            These plugins will also be used for preparing any response
            message sent by the handler.
        """
        def decorator(func: Handler):
            self.add_handler(key, func, auth_plugin, cipher_plugin)
            return func
        return decorator

    def subscribe(self, key: Hashable, writer: asyncio.StreamWriter):
        """Subscribe a client to a specific key. The key must be a
            Hashable object.
        """
        self.logger.debug("Subscribing client to key=%s", key)
        if key not in self.subscriptions:
            self.subscriptions[key] = set()
        self.subscriptions[key].add(writer)

    def unsubscribe(self, key: Hashable, writer: asyncio.StreamWriter):
        """Unsubscribe a client from a specific key. If no subscribers
            are left, the key will be removed from the subscriptions
            dictionary.
        """
        self.logger.debug("Unsubscribing client from key=%s", key)
        if key in self.subscriptions:
            self.subscriptions[key].remove(writer)
            if not self.subscriptions[key]:
                del self.subscriptions[key]

    async def handle_client(
            self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
            use_auth: bool = True, use_cipher: bool = True
        ):
        """Handle a client connection. When a client connects, it is
            added to the clients set. The client is then read from until
            the connection is lost, and the proper handlers are called
            if they are defined and the message is valid. If use_auth is
            False, the auth plugin set on the server will not be used.
            If use_cipher is False, the cipher plugin set on the
            server will not be used.
        """
        self.logger.info("Client connected from %s", writer.get_extra_info("peername"))
        self.clients.add(writer)
        header_length = self.header_class.header_length()

        try:
            while True:
                auth_plugin = None
                cipher_plugin = None
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
                    self.logger.debug("Invalid message received from %s", writer.get_extra_info("peername"))
                    response = self.make_error("invalid message")
                else:
                    # outer auth
                    if use_auth and self.auth_plugin is not None:
                        self.logger.debug("Calling self.auth_plugin.check on auth and body")
                        if not self.auth_plugin.check(message.auth_data, message.body):
                            self.logger.warning("Invalid auth_fields received from %s", writer.get_extra_info("peername"))
                            response = self.auth_plugin.error()
                            await self.send(writer, response, use_auth=False, use_cipher=False)
                            continue
                        else:
                            self.logger.debug("Valid auth_fields received from %s", writer.get_extra_info("peername"))

                    # outer cipher
                    if use_cipher and self.cipher_plugin is not None:
                        self.logger.debug("Calling self.cipher_plugin.decrypt on message")
                        message = self.cipher_plugin.decrypt(message)

                    keys = self.extract_keys(message)
                    self.logger.debug("Message received from %s with keys=%s", writer.get_extra_info("peername"), keys)

                    for key in keys:
                        if key in self.handlers:
                            handler, auth_plugin, cipher_plugin = self.handlers[key]

                            # inner auth
                            if auth_plugin is not None:
                                self.logger.debug("Calling auth_plugin.check on auth and body")
                                if not auth_plugin.check(message.auth_data, message.body):
                                    self.logger.warning("Invalid auth_fields received from %s", writer.get_extra_info("peername"))
                                    response = auth_plugin.error()
                                    break

                            # inner cipher
                            if cipher_plugin is not None:
                                self.logger.debug("Calling cipher_plugin.decrypt on message")
                                message = cipher_plugin.decrypt(message)

                            self.logger.debug("Calling handler for key=%s", key)
                            response = handler(message, writer)
                            if isinstance(response, Coroutine):
                                response = await response
                            break
                    else:
                        self.logger.warning("No handler found for keys=%s, calling default handler", keys)
                        response = self.default_handler(message, writer)

                if response is not None:
                    # inner cipher
                    if cipher_plugin is not None:
                        self.logger.debug("Calling cipher_plugin.encrypt on response (handler)")
                        response = cipher_plugin.encrypt(response)

                    # inner auth
                    if auth_plugin is not None:
                        self.logger.debug("Calling auth_plugin.make on response.body (handler)")
                        auth_plugin.make(response.auth_data, response.body)

                    # outer cipher
                    if use_cipher and self.cipher_plugin is not None:
                        self.logger.debug("Calling cipher_plugin.encrypt on response")
                        response = self.cipher_plugin.encrypt(response)

                    # outer auth
                    if use_auth and self.auth_plugin is not None:
                        self.logger.debug("Calling self.auth_plugin.make on response.body")
                        self.auth_plugin.make(response.auth_data, response.body)

                    await self.send(writer, response, use_auth=False, use_cipher=False)
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

    async def start(self, use_auth: bool = True, use_cipher: bool = True):
        """Start the server."""
        server = await asyncio.start_server(
            lambda r, w: self.handle_client(r, w, use_auth, use_cipher),
            self.host, self.port
        )
        async with server:
            self.logger.info(f"Server started on {self.host}:{self.port}")
            await server.serve_forever()

    async def send(
            self, client: asyncio.StreamWriter, message: MessageProtocol,
            collection: set = None, use_auth: bool = True,
            use_cipher: bool = True, auth_plugin: AuthPluginProtocol|None = None,
            cipher_plugin: CipherPluginProtocol|None = None
        ):
        """Helper coroutine to send a message to a client. On error, it
            logs the exception and removes the client from the given
            collection. If an auth plugin is provided, it will be used
            to authorize the message in addition to any auth plugin that
            is set on the server. If a cipher plugin is provided, it
            will be used to encrypt the message in addition to any
            cipher plugin that is set on the server. If use_auth is
            False, the auth plugin set on the server will not be used.
            If use_cipher is False, the cipher plugin set on the
            server will not be used.
        """
        # inner cipher
        if cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = cipher_plugin.encrypt(message)

        # inner auth
        if auth_plugin is not None:
            self.logger.debug("Calling auth_plugin.make on auth_data and body")
            auth_plugin.make(message.auth_data, message.body)

        # outer cipher
        if use_cipher and self.cipher_plugin is not None:
            self.logger.debug("Calling self.cipher_plugin.encrypt on message")
            message = self.cipher_plugin.encrypt(message)

        # outer auth
        if use_auth and self.auth_plugin is not None:
            self.logger.debug("Calling self.auth_plugin.make on auth_data and body")
            self.auth_plugin.make(message.auth_data, message.body)

        try:
            self.logger.debug("Sending message to %s", client.get_extra_info("peername"))
            client.write(message.encode())
            await client.drain()
        except Exception as e:
            self.logger.error("Error sending to client:", exc_info=True)
            if collection is not None:
                self.logger.info("Removing client %s from collection", client.get_extra_info("peername"))
                collection.discard(client)

    async def broadcast(
            self, message: MessageProtocol, use_auth: bool = True,
            use_cipher: bool = True, auth_plugin: AuthPluginProtocol|None = None,
            cipher_plugin: CipherPluginProtocol|None = None
        ):
        """Send the message to all connected clients concurrently using
            asyncio.gather. If an auth plugin is provided, it will be
            used to authorize the message in addition to any auth plugin
            that is set on the server. If a cipher plugin is provided,
            it will be used to encrypt the message in addition to any
            cipher plugin that is set on the server. If use_auth is
            False, the auth plugin set on the server will not be used. If
            use_cipher is False, the cipher plugin set on the
            server will not be used.
        """
        self.logger.debug("Broadcasting message to all clients")

        # inner cipher
        if use_cipher and cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = cipher_plugin.encrypt(message)

        # inner auth
        if use_auth and auth_plugin is not None:
            self.logger.debug("Calling auth_plugin.make on message.body (broadcast)")
            auth_plugin.make(message.auth_data, message.body)

        # outer cipher
        if use_cipher and self.cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = self.cipher_plugin.encrypt(message)

        # outer auth
        if use_auth and self.auth_plugin is not None:
            self.logger.debug("Calling self.auth_plugin.make on message.body (broadcast)")
            self.auth_plugin.make(message.auth_data, message.body)

        tasks = [self.send(client, message, self.clients, False, False) for client in self.clients]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def notify(
            self, key: Hashable, message: MessageProtocol, use_auth: bool = True,
            use_cipher: bool = True, auth_plugin: AuthPluginProtocol|None = None,
            cipher_plugin: CipherPluginProtocol|None = None
        ):
        """Send the message to all subscribed clients for the given key
            concurrently using asyncio.gather. If an auth plugin is
            provided, it will be used to authorize the message in
            addition to any auth plugin that is set on the server. If a
            cipher plugin is provided, it will be used to encrypt the
            message in addition to any cipher plugin that is set on
            the server. If use_auth is False, the auth plugin set on the
            server will not be used. If use_cipher is False, the
            cipher plugin set on the server will not be used.
        """
        if key not in self.subscriptions:
            self.logger.debug("No subscribers found for key=%s, skipping notification", key)
            return

        self.logger.debug("Notifying %d clients for key=%s", len(self.subscriptions[key]), key)

        # inner cipher
        if use_cipher and cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = cipher_plugin.encrypt(message)

        # inner auth
        if use_auth and auth_plugin is not None:
            self.logger.debug("Calling auth_plugin.make on message.body (notify)")
            auth_plugin.make(message.auth_data, message.body)

        # outer cipher
        if use_cipher and self.cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = self.cipher_plugin.encrypt(message)

        # outer auth
        if use_auth and self.auth_plugin is not None:
            self.logger.debug("Calling self.auth_plugin.make on message.body (notify)")
            self.auth_plugin.make(message.auth_data, message.body)

        subscribers = self.subscriptions.get(key, set())
        if not subscribers:
            self.logger.debug("No subscribers found for key=%s, removing from subscriptions", key)
            del self.subscriptions[key]
            return

        tasks = [self.send(client, message, subscribers, False, False) for client in subscribers]
        await asyncio.gather(*tasks, return_exceptions=True)
        self.logger.debug("Notified %d clients for key=%s", len(subscribers), key)

    def set_logger(self, logger: logging.Logger):
        """Replace the current logger."""
        self.logger = logger
