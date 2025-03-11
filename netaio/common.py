from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from time import time
from typing import (
    Hashable,
    Protocol,
    runtime_checkable,
    Callable,
    Coroutine,
    Any,
    NamedTuple,
)
from zlib import crc32
import asyncio
import logging
import packify
import socket
import struct


@runtime_checkable
class HeaderProtocol(Protocol):
    """Shows what a Header class should have and do."""
    @property
    def body_length(self) -> int:
        """At a minimum, a Header must have body_length, auth_length,
            message_type, and checksum properties.
        """
        ...

    @property
    def auth_length(self) -> int:
        """At a minimum, a Header must have body_length, auth_length,
            message_type, and checksum properties.
        """
        ...

    @property
    def message_type(self) -> MessageType:
        """At a minimum, a Header must have body_length, auth_length,
            message_type, and checksum properties.
        """
        ...

    @property
    def checksum(self) -> int:
        """At a minimum, a Header must have body_length, auth_length,
            message_type, and checksum properties.
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
class AuthFieldsProtocol(Protocol):
    """Shows what an AuthFields class should have and do."""
    @property
    def fields(self) -> dict[str, bytes]:
        """At a minimum, an AuthFields must have fields property."""
        ...

    @classmethod
    def decode(cls, data: bytes) -> AuthFieldsProtocol:
        """Decode the auth fields from the data."""
        ...

    def encode(self) -> bytes:
        """Encode the auth fields into a bytes object."""
        ...


@runtime_checkable
class BodyProtocol(Protocol):
    """Shows what a Body class should have and do."""
    @property
    def content(self) -> bytes:
        """At a minimum, a Body must have content, uri, and uri_length properties."""
        ...

    @property
    def uri(self) -> bytes:
        """At a minimum, a Body must have content, uri, and uri_length properties."""
        ...

    @property
    def uri_length(self) -> int:
        """At a minimum, a Body must have content, uri, and uri_length properties."""
        ...

    @classmethod
    def decode(cls, data: bytes) -> BodyProtocol:
        """Decode the body from the data."""
        ...

    def encode(self) -> bytes:
        """Encode the body into a bytes object."""
        ...

    @classmethod
    def prepare(cls, content: bytes, uri: bytes = b'', overhead: int = 0, *args, **kwargs) -> BodyProtocol:
        """Prepare a body from content and optional arguments."""
        ...


@runtime_checkable
class MessageProtocol(Protocol):
    """Shows what a Message class should have and do."""
    @property
    def header(self) -> HeaderProtocol:
        """A Message must have a header property."""
        ...

    @property
    def auth_data(self) -> AuthFieldsProtocol:
        """A Message must have an auth_data property."""
        ...

    @property
    def body(self) -> BodyProtocol:
        """A Message must have a body property."""
        ...

    def check(self) -> bool:
        """Check if the message is valid."""
        ...

    def encode(self) -> bytes:
        """Encode the message into a bytes object."""
        ...

    def copy(self) -> MessageProtocol:
        """Returns a copy of the message."""
        ...

    @classmethod
    def prepare(
            cls, body: BodyProtocol, message_type: MessageType,
            auth_data: AuthFieldsProtocol = None
        ) -> MessageProtocol:
        """Prepare a message from a body."""
        ...


@runtime_checkable
class NetworkNodeProtocol(Protocol):
    """For type-hinting objects that handle networking."""
    @property
    def port(self) -> int:
        """A class implementing this protocol must have a port property
            representing either the port to listen on or the port to
            connect to.
        """
        ...

    @property
    def local_peer(self) -> Peer|None:
        """A class implementing this protocol must have a local_peer
            property containing the local peer data.
        """
        ...

    @property
    def header_class(self) -> type[HeaderProtocol]:
        """A class implementing this protocol must have a header_class
            property referencing the header class to use for parsing
            received messages.
        """
        ...

    @property
    def message_type_class(self) -> type[MessageType]:
        """A class implementing this protocol must have a message_type_class
            property referencing the message type class to use for parsing
            received messages.
        """
        ...

    @property
    def auth_fields_class(self) -> type[AuthFieldsProtocol]:
        """A class implementing this protocol must have an auth_fields_class
            property referencing the auth fields class to use for parsing
            received messages.
        """
        ...

    @property
    def body_class(self) -> type[BodyProtocol]:
        """A class implementing this protocol must have a body_class
            property referencing the body class to use for parsing
            received messages.
        """
        ...

    @property
    def message_class(self) -> type[MessageProtocol]:
        """A class implementing this protocol must have a message_class
            property referencing the message class to use for parsing
            received messages.
        """
        ...

    @property
    def handlers(self) -> dict[Hashable, tuple[Handler|UDPHandler, AuthPluginProtocol|None, CipherPluginProtocol|None]]:
        """A class implementing this protocol must have a handlers property
            referencing a dictionary of handler functions, keyed by a hashable
            object, that will be called when a message with the corresponding
            key is received.
        """
        ...

    @property
    def default_handler(self) -> Handler|UDPHandler:
        """A class implementing this protocol must have a default_handler
            property referencing the default handler to use for messages
            that do not match any registered handler keys.
        """
        ...

    @property
    def extract_keys(self) -> Callable[[MessageProtocol], list[Hashable]]:
        """A class implementing this protocol must have an extract_keys
            property referencing a function that extracts the keys used
            for routing/choosing responses from a message.
        """
        ...

    @property
    def make_error(self) -> Callable[[str], MessageProtocol]:
        """A class implementing this protocol must have a make_error
            property referencing a function that makes error messages.
        """
        ...

    @property
    def logger(self) -> logging.Logger:
        """A class implementing this protocol must have a logger property
            referencing a logger for logging messages.
        """
        ...

    @property
    def auth_plugin(self) -> AuthPluginProtocol:
        """A class implementing this protocol must have an auth_plugin
            property referencing an auth plugin for
            authenticating/authorizing messages.
        """
        ...

    @property
    def cipher_plugin(self) -> CipherPluginProtocol:
        """A class implementing this protocol must have a cipher_plugin
            property referencing a cipher plugin for encrypting and
            decrypting messages.
        """
        ...

    @property
    def handle_auth_error(self) -> AuthErrorHandler:
        """A class implementing this protocol must have a
            handle_auth_error property referencing a function that is
            called when the auth check fails for a received message. If
            the function returns a message, that message will be sent as
            a response to the sender of the message that failed the auth
            check.
        """
        ...

    def add_handler(
            self, key: Hashable, handler: Handler|UDPHandler,
            auth_plugin: AuthPluginProtocol|None = None,
            cipher_plugin: CipherPluginProtocol|None = None
        ):
        """Register a handler for a specific key. The handler must
            accept a MessageProtocol object as an argument and return a
            MessageProtocol or None. If an auth plugin is provided, it
            will be used to check the message in addition to any auth
            plugin that is set on the node. If a cipher plugin is
            provided, it will be used to decrypt the message in addition
            to any cipher plugin that is set on the node. These
            plugins will also be used for preparing any response
            message sent by the handler.
        """
        ...

    def on(
            self,
            key: Hashable,
            auth_plugin: AuthPluginProtocol = None,
            cipher_plugin: CipherPluginProtocol = None
        ):
        """Decorator to register a handler for a specific key. The handler must
            accept a MessageProtocol object as an argument and return a
            MessageProtocol or None. If an auth plugin is provided, it
            will be used to check the message in addition to any auth
            plugin that is set on the node. If a cipher plugin is
            provided, it will be used to decrypt the message in addition
            to any cipher plugin that is set on the node. These
            plugins will also be used for preparing any response
            message sent by the handler.
        """
        ...

    def remove_handler(self, key: Hashable):
        """Remove a handler from the node."""
        ...

    def set_logger(self, logger: logging.Logger):
        """Replace the current logger."""
        ...


class MessageType(IntEnum):
    """Some default message types: REQUEST_URI, RESPOND_URI, CREATE_URI,
        UPDATE_URI, DELETE_URI, SUBSCRIBE_URI, UNSUBSCRIBE_URI,
        PUBLISH_URI, NOTIFY_URI, ADVERTISE_PEER, OK, CONFIRM_SUBSCRIBE,
        CONFIRM_UNSUBSCRIBE, PEER_DISCOVERED, ERROR, AUTH_ERROR,
        NOT_FOUND, DISCONNECT.
    """
    REQUEST_URI = 0
    RESPOND_URI = 1
    CREATE_URI = 2
    UPDATE_URI = 3
    DELETE_URI = 4
    SUBSCRIBE_URI = 5
    UNSUBSCRIBE_URI = 6
    PUBLISH_URI = 7
    NOTIFY_URI = 8
    ADVERTISE_PEER = 9
    OK = 10
    CONFIRM_SUBSCRIBE = 11
    CONFIRM_UNSUBSCRIBE = 12
    PEER_DISCOVERED = 13
    ERROR = 20
    AUTH_ERROR = 23
    NOT_FOUND = 24
    DISCONNECT = 30


@dataclass
class Header:
    """Default header class."""
    message_type: MessageType
    auth_length: int
    body_length: int
    checksum: int
    message_type_class = MessageType

    @staticmethod
    def header_length() -> int:
        """Return the byte length of the header."""
        return 9

    @staticmethod
    def struct_fstring() -> str:
        """Return the struct format string for decoding the header."""
        return '!BHHI'

    @classmethod
    def decode(
            cls, data: bytes,
            message_type_factory: Callable[[int], IntEnum]|None = None
        ) -> Header:
        """Decode the header from the data."""
        excess = False
        fstr = cls.struct_fstring()
        if len(data) > cls.header_length():
            fstr += f'{len(data)-cls.header_length()}s'
            excess = True

        if excess:
            message_type, auth_length, body_length, checksum, _ = struct.unpack(
                fstr,
                data
            )
        else:
            message_type, auth_length, body_length, checksum = struct.unpack(
                fstr,
                data
            )

        if message_type_factory is None:
            message_type_factory = cls.message_type_class

        return cls(
            message_type=message_type_factory(message_type),
            auth_length=auth_length,
            body_length=body_length,
            checksum=checksum
        )

    def encode(self) -> bytes:
        """Encode the header into bytes."""
        return struct.pack(
            self.struct_fstring(),
            self.message_type.value,
            self.auth_length,
            self.body_length,
            self.checksum
        )


@dataclass
class AuthFields:
    """Default auth fields class."""
    fields: dict[str, bytes] = field(default_factory=dict)

    @classmethod
    def decode(cls, data: bytes) -> AuthFields:
        """Decode the auth fields from bytes."""
        return cls(fields=packify.unpack(data))

    def encode(self) -> bytes:
        """Encode the auth fields into bytes."""
        return packify.pack(self.fields)


@dataclass
class Body:
    """Default body class."""
    uri_length: int
    uri: bytes
    content: bytes

    @classmethod
    def decode(cls, data: bytes) -> Body:
        """Decode the body from bytes."""
        uri_length, data = struct.unpack(
            f'!H{len(data)-2}s',
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
        """Encode the body into bytes."""
        return struct.pack(
            f'!H{len(self.uri)}s{len(self.content)}s',
            self.uri_length,
            self.uri,
            self.content,
        )

    @classmethod
    def prepare(cls, content: bytes, uri: bytes = b'', overhead: int = 0) -> Body:
        """Prepare a body from content and optional arguments. Raises
            ValueError if the content + uri is too long. (Calculated by
            subtracting the header length, overhead, and 104 from 2**16.
            The 104 value is for IP encapsulation and other known
            sources of overhead.)
        """
        if len(content) + len(uri) >= 2**16 - Header.header_length() - overhead - 104:
            raise ValueError("Content + uri is too long for encapsulation")

        return cls(
            uri_length=len(uri),
            uri=uri,
            content=content
        )


@dataclass
class Message:
    """Default message class."""
    header: Header
    auth_data: AuthFields
    body: Body

    def check(self) -> bool:
        """Check if the message is valid."""
        return self.header.checksum == crc32(self.body.encode())

    @classmethod
    def decode(
            cls, data: bytes,
            message_type_factory: Callable[[int], IntEnum]|None = None
        ) -> Message:
        """Decode the message from the data. Raises ValueError if the
            checksum does not match.
        """
        header_data = data[:Header.header_length()]
        data = data[Header.header_length():]
        header = Header.decode(header_data, message_type_factory)
        auth_data = AuthFields.decode(data[:header.auth_length])
        body = Body.decode(data[header.auth_length:])

        if header.checksum != crc32(body.encode()):
            raise ValueError("Checksum mismatch")

        return cls(
            header=header,
            auth_data=auth_data,
            body=body
        )

    def encode(self) -> bytes:
        """Encode the message into bytes."""
        auth_data = self.auth_data.encode()
        body = self.body.encode()
        self.header.auth_length = len(auth_data)
        self.header.body_length = len(body)
        self.header.checksum = crc32(body)
        return self.header.encode() + auth_data + body

    def copy(self) -> Message:
        """Returns a copy of the message."""
        return self.decode(self.encode(), self.header.message_type_class)

    @classmethod
    def prepare(
            cls, body: BodyProtocol, message_type: MessageType|IntEnum,
            auth_data: AuthFields|None = None
        ) -> Message:
        """Prepare a message from a body and optional arguments."""
        auth_data = AuthFields() if auth_data is None else auth_data
        return cls(
            header=Header(
                message_type=message_type,
                auth_length=len(auth_data.encode()),
                body_length=len(body.encode()),
                checksum=crc32(body.encode())
            ),
            auth_data=auth_data,
            body=body
        )


@dataclass
class Peer:
    """Class for storing peer information."""
    addrs: set[tuple[str, int]]
    id: bytes|None = field(default=None)
    data: bytes|None = field(default=None)
    last_rx: int = field(default_factory=lambda: int(time()))

    def __hash__(self):
        """Make the peer Hashable."""
        return hash((self.addrs, self.id, self.data))

    def update(self, data: bytes|None = None):
        """Update the peer data and last_rx time."""
        if data is not None:
            self.data = data
        self.last_rx = int(time())

    def timed_out(self, timeout: int = 60) -> bool:
        """Check if the peer has timed out."""
        return int(time()) - self.last_rx > timeout


@runtime_checkable
class AuthPluginProtocol(Protocol):
    """Shows what an auth plugin should do."""
    def __init__(self, config: dict):
        """Initialize the auth plugin with a config."""
        ...

    def make(
            self, auth_fields: AuthFieldsProtocol, body: BodyProtocol,
            node: NetworkNodeProtocol|None = None, peer: Peer|None = None,
            peer_plugin: PeerPluginProtocol|None = None,
        ) -> None:
        """Set auth_fields appropriate for a given body. Optional args
            peer and peer_plugin will be provided if they are available.
            The local peer information will be stored in node.local_peer
            if it exists. If peer, peer_plugin, or node.local_peer are
            required for functionality but are not provided/set, this
            method should fail gracefully: log an error message using
            node.logger (if provided) and return.
        """
        ...

    def check(
            self, auth_fields: AuthFieldsProtocol, body: BodyProtocol,
            node: NetworkNodeProtocol|None = None, peer: Peer|None = None,
            peer_plugin: PeerPluginProtocol|None = None,
        ) -> bool:
        """Check if the auth fields are valid for the given body.
            Optional args peer and peer_plugin will be provided if they
            are available. The local peer information will be stored in
            node.local_peer if it exists. If peer, peer_plugin, or
            node.local_peer are required for functionality but are not
            provided, this method should fail gracefully: log an error
            using node.logger (if provided) and return False.
        """
        ...

    def error(
            self,
            message_class: type[MessageProtocol] = Message,
            message_type_class: type[IntEnum] = MessageType,
            header_class: type[HeaderProtocol] = Header,
            auth_fields_class: type[AuthFieldsProtocol] = AuthFields,
            body_class: type[BodyProtocol] = Body
        ) -> MessageProtocol:
        """Make an error message."""
        ...


@runtime_checkable
class CipherPluginProtocol(Protocol):
    """Shows what a cipher plugin should do."""
    def __init__(self, config: dict):
        """Initialize the cipher plugin with a config."""
        ...

    def encrypt(
            self, message: MessageProtocol,
            node: NetworkNodeProtocol|None = None, peer: Peer|None = None,
            peer_plugin: PeerPluginProtocol|None = None,
        ) -> MessageProtocol:
        """Encrypt the message body, setting values in the header or
            auth_data as necessary. Returns a new message with the
            encrypted body and updated auth_data. Optional args peer and
            peer_plugin will be provided if they are available. The
            local peer information will be stored in node.local_peer if
            it exists. If peer, peer_plugin, or node.local_peer are
            required for functionality but are not provided, or in the
            case of an encryption failure, this method should raise an
            exception.
        """
        ...

    def decrypt(
            self, message: MessageProtocol,
            node: NetworkNodeProtocol|None = None, peer: Peer|None = None,
            peer_plugin: PeerPluginProtocol|None = None,
        ) -> MessageProtocol:
        """Decrypt the message body, reading values from the auth_data
            as necessary. Returns a new message with the decrypted body.
            May raise an exception if the decryption fails. Optional
            args peer and peer_plugin will be provided if they are
            available. The local peer information will be stored in
            node.local_peer if it exists. If peer and peer_plugin are
            required for functionality but are not provided, or in the
            case of a decryption failure, this method should raise an
            exception.
        """
        ...


@runtime_checkable
class PeerPluginProtocol(Protocol):
    """Shows what a peer plugin should do."""
    def __init__(self, config: dict = {}):
        """Initialize the peer plugin. Optionally parse a config."""
        ...

    def validate(self, peer: Peer) -> bool:
        """Validate a peer. Must return True if the peer is valid,
            False otherwise, and it must not raise an exception.
        """
        ...

    def parse_data(self, peer: Peer) -> dict[str, Any]|NamedTuple:
        """Parse a peer's data. Must return a dictionary or namedtuple."""
        ...

    def encode_data(self, peer_data: dict[str, Any]|NamedTuple, peer_id: bytes|None = None) -> bytes:
        """Encode a peer's data. Implementation may reference or include
            the peer_id, but it should gracefully handle an empty
            peer_id.
        """
        ...

    def pack(self, peer: Peer) -> bytes:
        """Pack a peer into a bytes object. Does not have to include the
            addrs.
        """
        ...

    def unpack(self, data: bytes) -> Peer:
        """Unpack a peer from a bytes object. Should set the addrs to an
            empty set if the data does not contain any addresses.
        """
        ...


Handler = Callable[[MessageProtocol, asyncio.StreamWriter], MessageProtocol | None | Coroutine[Any, Any, MessageProtocol | None]]
UDPHandler = Callable[[MessageProtocol, tuple[str, int]], MessageProtocol | None]
AuthErrorHandler = Callable[[NetworkNodeProtocol, AuthPluginProtocol, MessageProtocol|None], MessageProtocol|None]


class DefaultPeerPlugin:
    """Default peer plugin."""
    def __init__(self, config: dict = {}):
        """Initialize the peer plugin. No configuration necessary."""
        ...

    def validate(self, peer: Peer) -> bool:
        """Validate a peer. By default, accept all peers that have an id."""
        return peer.id is not None

    def parse_data(self, peer: Peer) -> dict[str, Any]|NamedTuple:
        """Parse a peer's data. Must return a dictionary or namedtuple."""
        return packify.unpack(peer.data)

    def encode_data(self, peer_data: dict[str, Any]|NamedTuple, peer_id: bytes|None = None) -> bytes:
        """Encode a peer's data. Ignores peer_id."""
        return packify.pack(peer_data)

    def pack(self, peer: Peer) -> bytes:
        """Pack a peer into a bytes object. Does not include addrs."""
        return packify.pack((peer.id, peer.data))

    def unpack(self, data: bytes) -> Peer:
        """Unpack a peer from a bytes object. Sets the addrs to an empty set."""
        peer_id, peer_data = packify.unpack(data)
        return Peer(addrs=set(), id=peer_id, data=peer_data)


def keys_extractor(message: MessageProtocol) -> list[Hashable]:
    """Extract handler keys for a given message. Custom implementations
        should return at least one key, and the more specific keys
        should be listed first. This is used to determine which handler
        to call for a given message, and it returns two keys: one that
        includes both the message type and the body uri, and one that is
        just the message type.
    """
    return [(message.header.message_type, message.body.uri), message.header.message_type]

def make_error_response(
        msg: str,
        message_class: type[MessageProtocol] = Message,
        message_type_class: type[IntEnum] = MessageType,
        body_class: type[BodyProtocol] = Body
    ) -> MessageProtocol:
    """Make an error response message."""
    if "not found" in msg:
        assert 'NOT_FOUND' in dir(message_type_class)
        message_type = message_type_class.NOT_FOUND
    elif "auth" in msg:
        assert 'AUTH_ERROR' in dir(message_type_class)
        message_type = message_type_class.AUTH_ERROR
    else:
        assert 'ERROR' in dir(message_type_class)
        message_type = message_type_class.ERROR

    body = body_class.prepare(
        content=msg.encode(),
        uri=b'ERROR',
    )

    return message_class.prepare(body, message_type)

def auth_error_handler(
        node: NetworkNodeProtocol, auth_plugin: AuthPluginProtocol,
        msg: MessageProtocol
    ) -> MessageProtocol|None:
    """Called when the auth check call fails for a message. If the
        message that failed the auth check was an error message, do
        not send a response. Otherwise, send the error message returned
        by the auth plugin.
    """
    node.logger.debug(f"Message auth failed for message with type {msg.header.message_type.name}")
    if 'ERROR' in msg.header.message_type.name.upper():
        node.logger.debug("Message is an error message, not sending a response")
        return None
    return auth_plugin.error(
        message_class=node.message_class,
        message_type_class=node.message_type_class,
        header_class=node.header_class,
        auth_fields_class=node.auth_fields_class,
        body_class=node.body_class
    )

def get_ip():
    """Get the primary local IP address of the machine.
        Credit: fatal_error CC BY-SA 4.0
        https://stackoverflow.com/a/28950776
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

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

default_node_logger = logging.getLogger("netaio.node")
default_node_logger.setLevel(logging.INFO)
if not default_node_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    default_node_logger.addHandler(handler)
    del handler
