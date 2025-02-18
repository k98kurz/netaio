from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Hashable, Protocol, runtime_checkable, Callable, Coroutine, Any
from zlib import crc32
import struct
import logging


@runtime_checkable
class HeaderProtocol(Protocol):
    @property
    def body_length(self) -> int:
        """At a minimum, a Header must have body_length and message_type
            properties.
        """
        ...

    @property
    def message_type(self) -> MessageType:
        """At a minimum, a Header must have body_length and message_type
            properties.
        """
        ...

    @staticmethod
    def header_length() -> int:
        """Return the byte length of the header."""
        ...

    @staticmethod
    def struct_fstring() -> str:
        """Return the struct format string for decoding the header."""
        ...

    @classmethod
    def decode(cls, data: bytes) -> HeaderProtocol:
        """Decode the header from the data."""
        ...

    def encode(self) -> bytes:
        """Encode the header into a bytes object."""
        ...


@runtime_checkable
class BodyProtocol(Protocol):
    @property
    def content(self) -> bytes:
        """At a minimum, a Body must have content and uri properties."""
        ...

    @property
    def uri(self) -> bytes:
        """At a minimum, a Body must have content and uri properties."""
        ...

    @classmethod
    def decode(cls, data: bytes) -> BodyProtocol:
        """Decode the body from the data."""
        ...

    def encode(self) -> bytes:
        """Encode the body into a bytes object."""
        ...

    @classmethod
    def prepare(cls, content: bytes, *args, **kwargs) -> BodyProtocol:
        """Prepare a body from content and optional arguments."""
        ...


@runtime_checkable
class MessageProtocol(Protocol):
    @property
    def header(self) -> HeaderProtocol:
        """A Message must have header and body properties."""
        ...

    @property
    def body(self) -> BodyProtocol:
        """A Message must have header and body properties."""
        ...

    def check(self) -> bool:
        """Check if the message is valid."""
        ...

    def encode(self) -> bytes:
        """Encode the message into a bytes object."""
        ...

    @classmethod
    def prepare(cls, body: BodyProtocol) -> MessageProtocol:
        """Prepare a message from a body."""
        ...


class MessageType(Enum):
    REQUEST_URI = 0
    RESPOND_URI = 1
    CREATE_URI = 2
    UPDATE_URI = 3
    DELETE_URI = 4
    SUBSCRIBE_URI = 5
    UNSUBSCRIBE_URI = 6
    PUBLISH_URI = 7
    NOTIFY_URI = 8
    OK = 10
    ERROR = 20
    AUTH_ERROR = 23
    NOT_FOUND = 24
    DISCONNECT = 30


@dataclass
class Header:
    message_type: MessageType
    body_length: int
    checksum: int

    @staticmethod
    def header_length() -> int:
        return 9

    @staticmethod
    def struct_fstring() -> str:
        return '!BII'

    @classmethod
    def decode(cls, data: bytes) -> Header:
        """Decode the header from the data."""
        excess = False
        fstr = cls.struct_fstring()
        if len(data) > cls.header_length():
            fstr += f'{len(data)-cls.header_length()}s'
            excess = True

        if excess:
            message_type, body_length, checksum, _ = struct.unpack(
                fstr,
                data
            )
        else:
            message_type, body_length, checksum = struct.unpack(
                fstr,
                data
            )

        return cls(
            message_type=MessageType(message_type),
            body_length=body_length,
            checksum=checksum
        )

    def encode(self) -> bytes:
        return struct.pack(
            self.struct_fstring(),
            self.message_type.value,
            self.body_length,
            self.checksum
        )


@dataclass
class Body:
    uri_length: int
    uri: bytes
    content: bytes

    @classmethod
    def decode(cls, data: bytes) -> Body:
        uri_length, data = struct.unpack(
            f'!I{len(data)-4}s',
            data
        )
        uri, content = struct.unpack(
            f'!{uri_length}s{len(data)-uri_length}s',
            data
        )
        return cls(
            uri_length=uri_length,
            uri=uri,
            content=content
        )

    def encode(self) -> bytes:
        return struct.pack(
            f'!I{len(self.uri)}s{len(self.content)}s',
            self.uri_length,
            self.uri,
            self.content,
        )

    @classmethod
    def prepare(cls, content: bytes, uri: bytes = b'1', *args, **kwargs) -> Body:
        return cls(
            uri_length=len(uri),
            uri=uri,
            content=content
        )


@dataclass
class Message:
    header: Header
    body: Body

    def check(self) -> bool:
        """Check if the message is valid."""
        return self.header.checksum == crc32(self.body.encode())

    @classmethod
    def decode(cls, data: bytes) -> Message:
        """Decode the message from the data. Raises ValueError if the
            checksum does not match.
        """
        header = Header.decode(data[:Header.header_length()])
        body = Body.decode(data[Header.header_length():])

        if header.checksum != crc32(body.encode()):
            raise ValueError("Checksum mismatch")

        return cls(
            header=header,
            body=body
        )

    def encode(self) -> bytes:
        return self.header.encode() + self.body.encode()

    @classmethod
    def prepare(
            cls, body: BodyProtocol,
            message_type: MessageType = MessageType.REQUEST_URI
        ) -> Message:
        return cls(
            header=Header(
                message_type=message_type,
                body_length=body.encode().__len__(),
                checksum=crc32(body.encode())
            ),
            body=body
        )


Handler = Callable[[MessageProtocol], MessageProtocol | None | Coroutine[Any, Any, MessageProtocol | None]]


def keys_extractor(message: MessageProtocol) -> list[Hashable]:
    """Extract handler keys for a given message. Custom implementations
        should return at least one key, and the more specific keys
        should be listed first. This is used to determine which handler
        to call for a given message, and it returns two keys: one that
        includes both the message type and the body uri, and one that is
        just the message type.
    """
    return [(message.header.message_type, message.body.uri), message.header.message_type]

def make_error_response(msg: str) -> Message:
    """Make an error response message."""
    if "not found" in msg:
        message_type = MessageType.NOT_FOUND
    elif "auth" in msg:
        message_type = MessageType.AUTH_ERROR
    else:
        message_type = MessageType.ERROR

    body = Body(
        uri_length=5,
        uri=b'ERROR',
        content=msg.encode()
    )

    header=Header(
        message_type=message_type,
        body_length=len(body.encode()),
        checksum=crc32(body.encode())
    )

    return Message(header, body)

# Setup default loggers for netaio
default_server_logger = logging.getLogger("netaio.server")
default_server_logger.setLevel(logging.INFO)
if not default_server_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    default_server_logger.addHandler(handler)
    del handler

default_client_logger = logging.getLogger("netaio.client")
default_client_logger.setLevel(logging.INFO)
if not default_client_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    default_client_logger.addHandler(handler)
    del handler
