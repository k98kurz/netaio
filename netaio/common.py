from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Hashable, Protocol, runtime_checkable, Callable, Coroutine, Any
from zlib import crc32
import struct


@runtime_checkable
class HeaderProtocol(Protocol):
    @property
    def body_length(self) -> int:
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
        ...

    @property
    def body(self) -> BodyProtocol:
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
    SUBSCRIBE_URI = 2
    UNSUBSCRIBE_URI = 3
    PUBLISH_URI = 4
    NOTIFY_URI = 5
    OK = 10
    ERROR = 20
    AUTH_ERROR = 23
    NOT_FOUND = 24
    DISCONNECT = 30


@dataclass
class Header:
    message_type: int
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
            message_type=message_type,
            body_length=body_length,
            checksum=checksum
        )

    def encode(self) -> bytes:
        return struct.pack(
            self.struct_fstring(),
            self.message_type,
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
                message_type=message_type.value,
                body_length=body.encode().__len__(),
                checksum=crc32(body.encode())
            ),
            body=body
        )


Handler = Callable[[MessageProtocol], MessageProtocol | None | Coroutine[Any, Any, MessageProtocol | None]]


def key_extractor(message: Message) -> Hashable:
    """Extract a handler key for a given message."""
    return (message.header.message_type, message.body.uri)

def make_error_response(msg: str) -> Message:
    """Make an error response message."""
    if "not found" in msg:
        message_type = MessageType.NOT_FOUND.value
    elif "auth" in msg:
        message_type = MessageType.AUTH_ERROR.value
    else:
        message_type = MessageType.ERROR.value

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
