# netaio

## Classes

### `AuthPluginProtocol(Protocol)`

Shows what an auth plugin should do.

#### Methods

##### `make(auth_fields: AuthFieldsProtocol, body: BodyProtocol):`

Set auth_fields appropriate for a given body.

##### `check(auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> bool:`

Check if the auth fields are valid for the given body.

##### `error() -> MessageProtocol:`

Make an error message.

### `HMACAuthPlugin`

HMAC auth plugin.

#### Annotations

- secret: <class 'bytes'>
- nonce_field: <class 'str'>
- ts_field: <class 'str'>
- hmac_field: <class 'str'>

#### Methods

##### `__init__(config: dict):`

Initialize the HMAC auth plugin with a config. The config must contain
{"secret": <str|bytes>}. It can contain {"hmac_field": <str>} to specify the
auth field name for the hmac; the default is "hmac". It can contain
{"nonce_field": <str>} to specify the auth field name for the nonce; the default
is "nonce". It can contain {"ts_field": <str>} to specify the auth field name
for the timestamp; the default is "ts".

##### `make(auth_fields: AuthFieldsProtocol, body: BodyProtocol):`

If the nonce and ts fields are not set, generate them. If the nonce is not the
IV_SIZE, generate a new one. Then, create an hmac of the nonce, ts, and body and
store it in the auth_data field specified by the "hmac_field" config option; the
default is "hmac".

##### `check(auth_fields: AuthFieldsProtocol, body: BodyProtocol) -> bool:`

Check if the auth fields are valid for the given body. Performs an hmac check on
the nonce, ts, and body. Returns False if any of the fields are missing or if
the hmac check fails.

##### `error() -> MessageProtocol:`

Make an error message that says "HMAC auth failed".

### `EncryptionPluginProtocol(Protocol)`

Shows what an encryption plugin should do.

#### Methods

##### `encrypt(message: MessageProtocol) -> MessageProtocol:`

Encrypt the message body, setting values in the header or auth_data as
necessary. Returns a new message with the encrypted body and updated auth_data.

##### `decrypt(message: MessageProtocol) -> MessageProtocol:`

Decrypt the message body, reading values from the auth_data as necessary.
Returns a new message with the decrypted body. May raise an exception if the
decryption fails.

### `Sha256StreamEncryptionPlugin`

SHA-256 stream encryption plugin.

#### Annotations

- key: <class 'bytes'>
- iv_field: <class 'str'>
- encrypt_uri: <class 'bool'>

#### Methods

##### `__init__(config: dict):`

Initialize the encryption plugin with a config. The config must contain {"key":
<str|bytes>}. It can contain {"iv_field": <str>} to specify the auth field name
for the iv; the default is "iv". It can contain {"encrypt_uri": <bool>} to
specify whether to encrypt the uri; the default is True.

##### `encrypt(message: MessageProtocol) -> MessageProtocol:`

Encrypt the message body, setting the self.iv_field in the auth_data. This will
overwrite any existing value in that auth_data field. If the self.encrypt_uri is
True, the uri will be encrypted as well as the content.

##### `decrypt(message: MessageProtocol) -> MessageProtocol:`

Decrypt the message body, reading the self.iv_field from the auth_data. Returns
a new message with the decrypted body.

### `TCPClient`

#### Annotations

- hosts: dict[tuple[str, int], tuple[asyncio.streams.StreamReader,
asyncio.streams.StreamWriter]]
- default_host: tuple[str, int]
- port: <class 'int'>
- header_class: type[netaio.common.HeaderProtocol]
- body_class: type[netaio.common.BodyProtocol]
- message_class: type[netaio.common.MessageProtocol]
- handlers: dict[typing.Hashable,
tuple[typing.Callable[[netaio.common.MessageProtocol,
asyncio.streams.StreamWriter], typing.Union[netaio.common.MessageProtocol,
NoneType, typing.Coroutine[typing.Any, typing.Any, netaio.common.MessageProtocol
| None]]], netaio.auth.AuthPluginProtocol | None,
netaio.encryption.EncryptionPluginProtocol | None]]
- extract_keys: typing.Callable[[netaio.common.MessageProtocol],
list[typing.Hashable]]
- logger: <class 'logging.Logger'>
- auth_plugin: <class 'netaio.auth.AuthPluginProtocol'>
- encrypt_plugin: <class 'netaio.encryption.EncryptionPluginProtocol'>

#### Methods

##### `__init__(host: str = '127.0.0.1', port: int = 8888, header_class: type = Header, body_class: type = Body, message_class: type = Message, handlers: dict = {}, extract_keys: Callable = <function keys_extractor at 0x7f29e26de7a0>, logger: Logger = <Logger netaio.client (INFO)>, auth_plugin: AuthPluginProtocol = None, encrypt_plugin: EncryptionPluginProtocol = None):`

Initialize the TCPClient. Args: host: The default host IPv4 address. port: The
default port to connect to. header_class: The header class to use. body_class:
The body class to use. message_class: The message class to use. handlers: A
dictionary of handlers for specific message keys. extract_keys: A function that
extracts the keys from a message. logger: The logger to use. auth_plugin: The
auth plugin to use. encrypt_plugin: The encryption plugin to use.

##### `add_handler(key: Hashable, handler: Callable, auth_plugin: AuthPluginProtocol = None, encrypt_plugin: EncryptionPluginProtocol = None):`

Register a handler for a specific key. The handler must accept a MessageProtocol
object as an argument and return MessageProtocol, None, or a Coroutine that
resolves to MessageProtocol | None. If an auth plugin is provided, it will be
used to check the message in addition to any auth plugin that is set on the
client. If an encrypt plugin is provided, it will be used to decrypt the message
in addition to any encryption plugin that is set on the client.

##### `on(key: Hashable, auth_plugin: AuthPluginProtocol = None, encrypt_plugin: EncryptionPluginProtocol = None):`

Decorator to register a handler for a specific key. The handler must accept a
MessageProtocol object as an argument and return a MessageProtocol, None, or a
Coroutine that resolves to a MessageProtocol or None. If an auth plugin is
provided, it will be used to check the message in addition to any auth plugin
that is set on the client. If an encrypt plugin is provided, it will be used to
decrypt the message in addition to any encryption plugin that is set on the
client.

##### `async connect(host: str = None, port: int = None):`

Connect to a server.

##### `async send(message: MessageProtocol, server: tuple = None, use_auth: bool = True, use_encryption: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, encrypt_plugin: netaio.encryption.EncryptionPluginProtocol | None = None):`

Send a message to the server. If use_auth is True and an auth plugin is set, it
will be called to set the auth fields on the message. If an auth plugin is
provided, it will be used to authorize the message in addition to any auth
plugin that is set on the client. If an encrypt plugin is provided, it will be
used to encrypt the message in addition to any encryption plugin that is set on
the client. If use_auth is False, the auth plugin set on the client will not be
used. If use_encryption is False, the encryption plugin set on the client will
not be used.

##### `async receive_once(server: tuple = None, use_auth: bool = True, use_encryption: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, encrypt_plugin: netaio.encryption.EncryptionPluginProtocol | None = None) -> netaio.common.MessageProtocol | None:`

Receive a message from the server. If a handler was registered for the message
key, the handler will be called with the message as an argument, and the result
will be returned if it is not None; otherwise, the received message will be
returned. If the message checksum fails, the message will be discarded and None
will be returned. If an auth plugin is set, it will be checked before the
message handler is called, and if the check fails, the message will be discarded
and None will be returned. If use_auth is False, the auth plugin set on the
client will not be used. If use_encryption is False, the encryption plugin set
on the client will not be used. If an auth plugin is provided, it will be used
to check the message in addition to any auth plugin that is set on the client.
If an encrypt plugin is provided, it will be used to decrypt the message in
addition to any encryption plugin that is set on the client.

##### `async receive_loop(server: tuple = None, use_auth: bool = True, use_encryption: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, encrypt_plugin: netaio.encryption.EncryptionPluginProtocol | None = None):`

Receive messages from the server indefinitely. Use with asyncio.create_task() to
run concurrently, then use task.cancel() to stop. If use_auth is False, the auth
plugin set on the client will not be used. If use_encryption is False, the
encryption plugin set on the client will not be used. If an auth plugin is
provided, it will be used to check the message in addition to any auth plugin
that is set on the client. If an encrypt plugin is provided, it will be used to
decrypt the message in addition to any encryption plugin that is set on the
client.

##### `async close(server: tuple = None):`

Close the connection to the server.

##### `set_logger(logger: Logger):`

Replace the current logger.

### `TCPServer`

#### Annotations

- host: <class 'str'>
- port: <class 'int'>
- handlers: dict[typing.Hashable,
tuple[typing.Callable[[netaio.common.MessageProtocol,
asyncio.streams.StreamWriter], typing.Union[netaio.common.MessageProtocol,
NoneType, typing.Coroutine[typing.Any, typing.Any, netaio.common.MessageProtocol
| None]]], netaio.auth.AuthPluginProtocol | None,
netaio.encryption.EncryptionPluginProtocol | None]]
- default_handler: typing.Callable[[netaio.common.MessageProtocol,
asyncio.streams.StreamWriter], typing.Union[netaio.common.MessageProtocol,
NoneType, typing.Coroutine[typing.Any, typing.Any, netaio.common.MessageProtocol
| None]]]
- header_class: type[netaio.common.HeaderProtocol]
- body_class: type[netaio.common.BodyProtocol]
- message_class: type[netaio.common.MessageProtocol]
- extract_keys: typing.Callable[[netaio.common.MessageProtocol],
list[typing.Hashable]]
- make_error: typing.Callable[[str], netaio.common.MessageProtocol]
- subscriptions: dict[typing.Hashable, set[asyncio.streams.StreamWriter]]
- clients: set[asyncio.streams.StreamWriter]
- logger: <class 'logging.Logger'>
- auth_plugin: <class 'netaio.auth.AuthPluginProtocol'>
- encrypt_plugin: <class 'netaio.encryption.EncryptionPluginProtocol'>

#### Methods

##### `__init__(host: str = '0.0.0.0', port: int = 8888, header_class: type = Header, body_class: type = Body, message_class: type = Message, keys_extractor: Callable = <function keys_extractor at 0x7f29e26de7a0>, make_error_response: Callable = <function make_error_response at 0x7f29e1f8e200>, default_handler: Callable = <function not_found_handler at 0x7f29e1f8f910>, logger: Logger = <Logger netaio.server (INFO)>, auth_plugin: AuthPluginProtocol = None, encrypt_plugin: EncryptionPluginProtocol = None):`

Initialize the TCPServer. Args: host: The host to listen on. port: The port to
listen on. header_class: The header class to use. body_class: The body class to
use. message_class: The message class to use. keys_extractor: A function that
extracts the keys from a message. make_error_response: A function that makes an
error response. default_handler: The default handler to use for messages that do
not match any registered handler keys. logger: The logger to use. auth_plugin:
The auth plugin to use. encrypt_plugin: The encrypt plugin to use.

##### `add_handler(key: Hashable, handler: Callable, auth_plugin: AuthPluginProtocol = None, encrypt_plugin: EncryptionPluginProtocol = None):`

Register a handler for a specific key. The handler must accept a MessageProtocol
object as an argument and return a MessageProtocol, None, or a Coroutine that
resolves to MessageProtocol | None. If an auth plugin is provided, it will be
used to check the message in addition to any auth plugin that is set on the
server. If an encrypt plugin is provided, it will be used to decrypt the message
in addition to any encryption plugin that is set on the server. These plugins
will also be used for preparing any response message sent by the handler.

##### `on(key: Hashable, auth_plugin: AuthPluginProtocol = None, encrypt_plugin: EncryptionPluginProtocol = None):`

Decorator to register a handler for a specific key. The handler must accept a
MessageProtocol object as an argument and return a MessageProtocol, None, or a
Coroutine that resolves to a MessageProtocol or None. If an auth plugin is
provided, it will be used to check the message in addition to any auth plugin
that is set on the server. If an encrypt plugin is provided, it will be used to
decrypt the message in addition to any encryption plugin that is set on the
server. These plugins will also be used for preparing any response message sent
by the handler.

##### `subscribe(key: Hashable, writer: StreamWriter):`

Subscribe a client to a specific key. The key must be a Hashable object.

##### `unsubscribe(key: Hashable, writer: StreamWriter):`

Unsubscribe a client from a specific key. If no subscribers are left, the key
will be removed from the subscriptions dictionary.

##### `async handle_client(reader: StreamReader, writer: StreamWriter, use_auth: bool = True, use_encryption: bool = True):`

Handle a client connection. When a client connects, it is added to the clients
set. The client is then read from until the connection is lost, and the proper
handlers are called if they are defined and the message is valid. If use_auth is
False, the auth plugin set on the server will not be used. If use_encryption is
False, the encryption plugin set on the server will not be used.

##### `async start(use_auth: bool = True, use_encryption: bool = True):`

Start the server.

##### `async send(client: StreamWriter, message: MessageProtocol, collection: set = None, use_auth: bool = True, use_encryption: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, encrypt_plugin: netaio.encryption.EncryptionPluginProtocol | None = None):`

Helper coroutine to send a message to a client. On error, it logs the exception
and removes the client from the given collection. If an auth plugin is provided,
it will be used to authorize the message in addition to any auth plugin that is
set on the server. If an encrypt plugin is provided, it will be used to encrypt
the message in addition to any encryption plugin that is set on the server. If
use_auth is False, the auth plugin set on the server will not be used. If
use_encryption is False, the encryption plugin set on the server will not be
used.

##### `async broadcast(message: MessageProtocol, use_auth: bool = True, use_encryption: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, encrypt_plugin: netaio.encryption.EncryptionPluginProtocol | None = None):`

Send the message to all connected clients concurrently using asyncio.gather. If
an auth plugin is provided, it will be used to authorize the message in addition
to any auth plugin that is set on the server. If an encrypt plugin is provided,
it will be used to encrypt the message in addition to any encryption plugin that
is set on the server. If use_auth is False, the auth plugin set on the server
will not be used. If use_encryption is False, the encryption plugin set on the
server will not be used.

##### `async notify(key: Hashable, message: MessageProtocol, use_auth: bool = True, use_encryption: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, encrypt_plugin: netaio.encryption.EncryptionPluginProtocol | None = None):`

Send the message to all subscribed clients for the given key concurrently using
asyncio.gather. If an auth plugin is provided, it will be used to authorize the
message in addition to any auth plugin that is set on the server. If an encrypt
plugin is provided, it will be used to encrypt the message in addition to any
encryption plugin that is set on the server. If use_auth is False, the auth
plugin set on the server will not be used. If use_encryption is False, the
encryption plugin set on the server will not be used.

##### `set_logger(logger: Logger):`

Replace the current logger.

### `Header`

Default header class.

#### Annotations

- message_type: MessageType
- auth_length: int
- body_length: int
- checksum: int

#### Methods

##### `__init__(message_type: MessageType, auth_length: int, body_length: int, checksum: int):`

##### `@staticmethod header_length() -> int:`

Return the byte length of the header.

##### `@staticmethod struct_fstring() -> str:`

Return the struct format string for decoding the header.

##### `@classmethod decode(data: bytes) -> Header:`

Decode the header from the data.

##### `encode() -> bytes:`

Encode the header into bytes.

### `AuthFields`

Default auth fields class.

#### Annotations

- fields: dict[str, bytes]

#### Methods

##### `__init__(fields: dict[str, bytes] = <factory>):`

##### `@classmethod decode(data: bytes) -> AuthFields:`

Decode the auth fields from bytes.

##### `encode() -> bytes:`

Encode the auth fields into bytes.

### `Body`

Default body class.

#### Annotations

- uri_length: int
- uri: bytes
- content: bytes

#### Methods

##### `__init__(uri_length: int, uri: bytes, content: bytes):`

##### `@classmethod decode(data: bytes) -> Body:`

Decode the body from bytes.

##### `encode() -> bytes:`

Encode the body into bytes.

##### `@classmethod prepare(content: bytes, uri: bytes = b'1') -> Body:`

Prepare a body from content and optional arguments.

### `Message`

Default message class.

#### Annotations

- header: Header
- auth_data: AuthFields
- body: Body

#### Methods

##### `__init__(header: Header, auth_data: AuthFields, body: Body):`

##### `check() -> bool:`

Check if the message is valid.

##### `@classmethod decode(data: bytes) -> Message:`

Decode the message from the data. Raises ValueError if the checksum does not
match.

##### `encode() -> bytes:`

Encode the message into bytes.

##### `@classmethod prepare(body: BodyProtocol, message_type: MessageType = MessageType.REQUEST_URI, auth_data: AuthFields = None) -> Message:`

Prepare a message from a body and optional arguments.

### `MessageType(Enum)`

Some default message types: REQUEST_URI, RESPOND_URI, CREATE_URI, UPDATE_URI,
DELETE_URI, SUBSCRIBE_URI, UNSUBSCRIBE_URI, PUBLISH_URI, NOTIFY_URI, OK,
CONFIRM_SUBSCRIBE, CONFIRM_UNSUBSCRIBE, ERROR, AUTH_ERROR, NOT_FOUND,
DISCONNECT.

### `HeaderProtocol(Protocol)`

Shows what a Header class should have and do.

#### Properties

- body_length: At a minimum, a Header must have body_length, auth_length, and
message_type properties.
- auth_length: At a minimum, a Header must have body_length, auth_length, and
message_type properties.
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

### `AuthFieldsProtocol(Protocol)`

Shows what an AuthFields class should have and do.

#### Properties

- fields: At a minimum, an AuthFields must have fields property.

#### Methods

##### `@classmethod decode(data: bytes) -> AuthFieldsProtocol:`

Decode the auth fields from the data.

##### `encode() -> bytes:`

Encode the auth fields into a bytes object.

### `BodyProtocol(Protocol)`

Shows what a Body class should have and do.

#### Properties

- content: At a minimum, a Body must have content and uri properties.
- uri: At a minimum, a Body must have content and uri properties.

#### Methods

##### `@classmethod decode(data: bytes) -> BodyProtocol:`

Decode the body from the data.

##### `encode() -> bytes:`

Encode the body into a bytes object.

##### `@classmethod prepare(content: bytes, uri: bytes = b'1') -> BodyProtocol:`

Prepare a body from content and optional arguments.

### `MessageProtocol(Protocol)`

Shows what a Message class should have and do.

#### Properties

- header: A Message must have a header property.
- auth_data: A Message must have an auth_data property.
- body: A Message must have a body property.

#### Methods

##### `check() -> bool:`

Check if the message is valid.

##### `encode() -> bytes:`

Encode the message into a bytes object.

##### `@classmethod prepare(body: BodyProtocol, message_type: MessageType, auth_data: AuthFieldsProtocol = None) -> MessageProtocol:`

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

