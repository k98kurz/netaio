# netaio

## Classes

### `TCPClient`

#### Annotations

- host: <class 'str'>
- port: <class 'int'>
- reader: <class 'asyncio.streams.StreamReader'>
- writer: <class 'asyncio.streams.StreamWriter'>
- header_class: type[netaio.common.HeaderProtocol]
- body_class: type[netaio.common.BodyProtocol]
- message_class: type[netaio.common.MessageProtocol]
- handlers: dict[typing.Hashable,
typing.Callable[[netaio.common.MessageProtocol],
typing.Union[netaio.common.MessageProtocol, NoneType,
typing.Coroutine[typing.Any, typing.Any, netaio.common.MessageProtocol |
None]]]]
- extract_keys: typing.Callable[[netaio.common.MessageProtocol],
list[typing.Hashable]]
- logger: <class 'logging.Logger'>

#### Methods

##### `__init__(host: str = '127.0.0.1', port: int = 8888, header_class: type = Header, body_class: type = Body, message_class: type = Message, handlers: dict = {}, extract_keys: Callable = <function keys_extractor at 0x74ec1e6da680>, logger: Logger = <Logger netaio.client (INFO)>):`

##### `add_handler(key: Hashable, handler: Callable):`

Register a handler for a specific key. The handler must accept a MessageProtocol
object as an argument and return MessageProtocol, None, or a Coroutine that
resolves to MessageProtocol | None.

##### `on(key: Hashable):`

Decorator to register a handler for a specific key. The handler must accept a
MessageProtocol object as an argument and return a MessageProtocol, None, or a
Coroutine that resolves to a MessageProtocol or None.

##### `async connect():`

Connect to the server.

##### `async send(message: MessageProtocol):`

Send a message to the server.

##### `async receive_once() -> MessageProtocol:`

Receive a message from the server. If a handler was registered for the message
key, the handler will be called with the message as an argument, and the result
will be returned if it is not None; otherwise, the received message will be
returned. If the message checksum fails, the message will be discarded and None
will be returned.

##### `async receive_loop():`

Receive messages from the server indefinitely. Use with asyncio.create_task() to
run concurrently, then use task.cancel() to stop.

##### `async close():`

Close the connection to the server.

##### `set_logger(logger: Logger):`

Replace the current logger.

### `TCPServer`

#### Annotations

- host: <class 'str'>
- port: <class 'int'>
- handlers: dict[typing.Hashable,
typing.Callable[[netaio.common.MessageProtocol],
typing.Union[netaio.common.MessageProtocol, NoneType,
typing.Coroutine[typing.Any, typing.Any, netaio.common.MessageProtocol |
None]]]]
- default_handler: typing.Callable[[netaio.common.MessageProtocol],
typing.Union[netaio.common.MessageProtocol, NoneType,
typing.Coroutine[typing.Any, typing.Any, netaio.common.MessageProtocol | None]]]
- header_class: type[netaio.common.HeaderProtocol]
- body_class: type[netaio.common.BodyProtocol]
- message_class: type[netaio.common.MessageProtocol]
- extract_keys: typing.Callable[[netaio.common.MessageProtocol],
list[typing.Hashable]]
- make_error: typing.Callable[[str], netaio.common.MessageProtocol]
- subscriptions: dict[typing.Hashable, set[asyncio.streams.StreamWriter]]
- clients: set[asyncio.streams.StreamWriter]
- logger: <class 'logging.Logger'>

#### Methods

##### `__init__(host: str = '127.0.0.1', port: int = 8888, header_class: type = Header, body_class: type = Body, message_class: type = Message, keys_extractor: Callable = <function keys_extractor at 0x74ec1e6da680>, make_error_response: Callable = <function make_error_response at 0x74ec1e77e0e0>, default_handler: Callable = <function not_found_handler at 0x74ec1df7f250>, logger: Logger = <Logger netaio.server (INFO)>):`

##### `add_handler(key: Hashable, handler: Callable):`

Register a handler for a specific key. The handler must accept a MessageProtocol
object as an argument and return a MessageProtocol, None, or a Coroutine that
resolves to MessageProtocol | None.

##### `on(key: Hashable):`

Decorator to register a handler for a specific key. The handler must accept a
MessageProtocol object as an argument and return a MessageProtocol, None, or a
Coroutine that resolves to a MessageProtocol or None.

##### `subscribe(key: Hashable, writer: StreamWriter):`

Subscribe a client to a specific key. The key must be a Hashable object.

##### `unsubscribe(key: Hashable, writer: StreamWriter):`

Unsubscribe a client from a specific key. If no subscribers are left, the key
will be removed from the subscriptions dictionary.

##### `async handle_client(reader: StreamReader, writer: StreamWriter):`

Handle a client connection. When a client connects, it is added to the clients
set. The client is then read from until the connection is lost, and the proper
handlers are called if they are defined and the message is valid.

##### `async start():`

##### `async send(client: StreamWriter, data: bytes, collection: set = None):`

Helper coroutine to send data to a client. On error, it logs the exception and
removes the client from the given collection.

##### `async broadcast(message: MessageProtocol):`

Send the message to all connected clients concurrently using asyncio.gather.

##### `async notify(key: Hashable, message: MessageProtocol):`

Send the message to all subscribed clients for the given key concurrently using
asyncio.gather.

##### `set_logger(logger: Logger):`

Replace the current logger.

### `Header`

Header(message_type: 'MessageType', body_length: 'int', checksum: 'int')

#### Annotations

- message_type: MessageType
- body_length: int
- checksum: int

#### Methods

##### `__init__(message_type: MessageType, body_length: int, checksum: int):`

##### `@staticmethod header_length() -> int:`

##### `@staticmethod struct_fstring() -> str:`

##### `@classmethod decode(data: bytes) -> Header:`

Decode the header from the data.

##### `encode() -> bytes:`

### `Body`

Body(uri_length: 'int', uri: 'bytes', content: 'bytes')

#### Annotations

- uri_length: int
- uri: bytes
- content: bytes

#### Methods

##### `__init__(uri_length: int, uri: bytes, content: bytes):`

##### `@classmethod decode(data: bytes) -> Body:`

##### `encode() -> bytes:`

##### `@classmethod prepare(content: bytes, uri: bytes = b'1') -> Body:`

### `Message`

Message(header: 'Header', body: 'Body')

#### Annotations

- header: Header
- body: Body

#### Methods

##### `__init__(header: Header, body: Body):`

##### `check() -> bool:`

Check if the message is valid.

##### `@classmethod decode(data: bytes) -> Message:`

Decode the message from the data. Raises ValueError if the checksum does not
match.

##### `encode() -> bytes:`

##### `@classmethod prepare(body: BodyProtocol, message_type: MessageType = MessageType.REQUEST_URI) -> Message:`

### `MessageType(Enum)`

An enumeration.

### `HeaderProtocol(Protocol)`

#### Properties

- body_length: At a minimum, a Header must have body_length and message_type
properties.
- message_type: At a minimum, a Header must have body_length and message_type
properties.

#### Methods

##### `@staticmethod header_length() -> int:`

Return the byte length of the header.

##### `@staticmethod struct_fstring() -> str:`

Return the struct format string for decoding the header.

##### `@classmethod decode(data: bytes) -> HeaderProtocol:`

Decode the header from the data.

##### `encode() -> bytes:`

Encode the header into a bytes object.

### `BodyProtocol(Protocol)`

#### Properties

- content: At a minimum, a Body must have content and uri properties.
- uri: At a minimum, a Body must have content and uri properties.

#### Methods

##### `@classmethod decode(data: bytes) -> BodyProtocol:`

Decode the body from the data.

##### `encode() -> bytes:`

Encode the body into a bytes object.

##### `@classmethod prepare(content: bytes) -> BodyProtocol:`

Prepare a body from content and optional arguments.

### `MessageProtocol(Protocol)`

#### Properties

- header: A Message must have header and body properties.
- body: A Message must have header and body properties.

#### Methods

##### `check() -> bool:`

Check if the message is valid.

##### `encode() -> bytes:`

Encode the message into a bytes object.

##### `@classmethod prepare(body: BodyProtocol) -> MessageProtocol:`

Prepare a message from a body.

## Functions

### `keys_extractor(message: MessageProtocol) -> list[Hashable]:`

Extract handler keys for a given message. Custom implementations should return
at least one key, and the more specific keys should be listed first. This is
used to determine which handler to call for a given message, and it returns two
keys: one that includes both the message type and the body uri, and one that is
just the message type.

### `make_error_response(msg: str) -> Message:`

Make an error response message.

### `version():`

Return the version of the netaio package.

## Values

- `Handler`: _CallableGenericAlias
- `default_server_logger`: Logger
- `default_client_logger`: Logger

