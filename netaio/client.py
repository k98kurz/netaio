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


class TCPClient:
    host: str
    port: int
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    header_class: type[HeaderProtocol]
    body_class: type[BodyProtocol]
    message_class: type[MessageProtocol]
    handlers: dict[Hashable, Handler]
    extract_key: Callable[[MessageProtocol], Hashable]
    respond_with_error: Callable[[str], MessageProtocol]

    def __init__(
            self, host="127.0.0.1", port=8888,
            header_class: type[HeaderProtocol] = Header,
            body_class: type[BodyProtocol] = Body,
            message_class: type[MessageProtocol] = Message,
            handlers: dict[Hashable, Handler] = {},
            extract_key: Callable[[MessageProtocol], Hashable] = key_extractor,
            respond_with_error: Callable[[str], MessageProtocol] = make_error_response
        ):
        self.host = host
        self.port = port
        self.header_class = header_class
        self.body_class = body_class
        self.message_class = message_class
        self.handlers = handlers
        self.extract_key = extract_key
        self.respond_with_error = respond_with_error

    def add_handler(
            self, key: Hashable,
            handler: Handler
        ):
        """Register a handler for a specific key. The handler must
            accept a MessageProtocol object as an argument and return
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

    async def connect(self):
        """Connect to the server."""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

    async def send(self, message: MessageProtocol):
        """Send a message to the server."""
        self.writer.write(message.encode())
        await self.writer.drain()

    async def receive_once(self) -> MessageProtocol:
        """Receive a message from the server. If a handler was
            registered for the message key, the handler will be called
            with the message as an argument, and the result will be
            returned if it is not None; otherwise, the received message
            will be returned.
        """
        data = await self.reader.readexactly(self.header_class.header_length())
        header = self.header_class.decode(data)
        body = await self.reader.readexactly(header.body_length)
        body = self.body_class.decode(body)
        msg = self.message_class(header=header, body=body)
        key = self.extract_key(msg)

        if key in self.handlers:
            handler = self.handlers[key]
            result = handler(msg)
            if isinstance(result, Coroutine):
                result = await result

            if result is not None:
                return result

        return msg

    async def close(self):
        """Close the connection to the server."""
        self.writer.close()
        await self.writer.wait_closed()
