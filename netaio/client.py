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
    Handler,
    default_client_logger
)
from typing import Callable, Coroutine, Hashable
import asyncio
import logging


class TCPClient:
    hosts: dict[tuple[str, int], tuple[asyncio.StreamReader, asyncio.StreamWriter]]
    port: int
    header_class: type[HeaderProtocol]
    body_class: type[BodyProtocol]
    message_class: type[MessageProtocol]
    handlers: dict[Hashable, tuple[Handler, AuthPluginProtocol|None]]
    extract_keys: Callable[[MessageProtocol], list[Hashable]]
    logger: logging.Logger
    auth_plugin: AuthPluginProtocol

    def __init__(
            self, port: int = 8888,
            header_class: type[HeaderProtocol] = Header,
            body_class: type[BodyProtocol] = Body,
            message_class: type[MessageProtocol] = Message,
            handlers: dict[Hashable, Handler] = {},
            extract_keys: Callable[[MessageProtocol], list[Hashable]] = keys_extractor,
            logger: logging.Logger = default_client_logger,
            auth_plugin: AuthPluginProtocol = None
        ):
        self.hosts = {}
        self.port = port
        self.header_class = header_class
        self.body_class = body_class
        self.message_class = message_class
        self.handlers = handlers
        self.extract_keys = extract_keys
        self.logger = logger
        self.auth_plugin = auth_plugin

    def add_handler(
            self, key: Hashable,
            handler: Handler,
            auth_plugin: AuthPluginProtocol = None
        ):
        """Register a handler for a specific key. The handler must
            accept a MessageProtocol object as an argument and return
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

    async def connect(self, host: str = "127.0.0.1", port: int = None):
        """Connect to a server."""
        port = port or self.port
        self.logger.info("Connecting to %s:%d", host, port)
        reader, writer = await asyncio.open_connection(host, port)
        self.hosts[(host, port)] = (reader, writer)

    async def send(self, server: tuple[str, int], message: MessageProtocol, set_auth: bool = True):
        """Send a message to the server. If set_auth is True and an auth
            plugin is set, it will be called to set the auth fields on the
            message.
        """
        if set_auth and self.auth_plugin is not None:
            self.logger.debug("Calling auth_plugin.make on message.body")
            self.auth_plugin.make(message.auth_data, message.body)
        self.logger.debug(f"Sending message of type={message.header.message_type} to server...")
        _, writer = self.hosts[server]
        writer.write(message.encode())
        await writer.drain()
        self.logger.debug("Message sent to server")

    async def receive_once(self, server: tuple[str, int]) -> MessageProtocol|None:
        """Receive a message from the server. If a handler was
            registered for the message key, the handler will be called
            with the message as an argument, and the result will be
            returned if it is not None; otherwise, the received message
            will be returned. If the message checksum fails, the message
            will be discarded and None will be returned. If an auth
            plugin is set, it will be checked before the message handler
            is called, and if the check fails, the message will be
            discarded and None will be returned.
        """
        self.logger.debug("Receiving message from server...")
        reader, writer = self.hosts[server]
        data = await reader.readexactly(self.header_class.header_length())
        header = self.header_class.decode(data)
        self.logger.debug(f"Received message of type={header.message_type} from server")

        auth_bytes = await reader.readexactly(header.auth_length)
        auth = AuthFields.decode(auth_bytes)

        body_bytes = await reader.readexactly(header.body_length)
        body = self.body_class.decode(body_bytes)

        msg = self.message_class(header=header, auth_data=auth, body=body)

        if not msg.check():
            self.logger.warning("Message checksum failed")
            return None

        if self.auth_plugin is not None:
            if not self.auth_plugin.check(auth, body):
                self.logger.warning("Message auth failed")
                return None

        keys = self.extract_keys(msg)
        result = None

        self.logger.debug("Message received from server")
        for key in keys:
            if key in self.handlers:
                handler, auth_plugin = self.handlers[key]

                if auth_plugin is not None:
                    if not auth_plugin.check(auth, body):
                        self.logger.warning("Message auth failed")
                        return None

                self.logger.debug("Calling handler for key=%s", key)
                result = handler(msg, writer)
                if isinstance(result, Coroutine):
                    result = await result
                break

        if result is not None:
            return result

        return msg

    async def receive_loop(self, server: tuple[str, int]):
        """Receive messages from the server indefinitely. Use with
            asyncio.create_task() to run concurrently, then use
            task.cancel() to stop.
        """
        while True:
            try:
                await self.receive_once(server)
            except asyncio.CancelledError:
                self.logger.info("Receive loop cancelled")
                break
            except Exception as e:
                self.logger.error("Error in receive_loop", exc_info=True)
                break

    async def close(self, server: tuple[str, int]):
        """Close the connection to the server."""
        self.logger.info("Closing connection to server...")
        _, writer = self.hosts[server]
        writer.close()
        await writer.wait_closed()
        self.logger.info("Connection to server closed")

    def set_logger(self, logger: logging.Logger):
        """Replace the current logger."""
        self.logger = logger
