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

### `CipherPluginProtocol(Protocol)`

Shows what a cipher plugin should do.

#### Methods

##### `encrypt(message: MessageProtocol) -> MessageProtocol:`

Encrypt the message body, setting values in the header or auth_data as
necessary. Returns a new message with the encrypted body and updated auth_data.

##### `decrypt(message: MessageProtocol) -> MessageProtocol:`

Decrypt the message body, reading values from the auth_data as necessary.
Returns a new message with the decrypted body. May raise an exception if the
decryption fails.

### `Sha256StreamCipherPlugin`

SHA-256 stream cipher plugin.

#### Annotations

- key: <class 'bytes'>
- iv_field: <class 'str'>
- encrypt_uri: <class 'bool'>

#### Methods

##### `__init__(config: dict):`

Initialize the cipher plugin with a config. The config must contain {"key":
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

TCP client class.

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
netaio.cipher.CipherPluginProtocol | None]]
- extract_keys: typing.Callable[[netaio.common.MessageProtocol],
list[typing.Hashable]]
- logger: <class 'logging.Logger'>
- auth_plugin: <class 'netaio.auth.AuthPluginProtocol'>
- cipher_plugin: <class 'netaio.cipher.CipherPluginProtocol'>

#### Methods

##### `__init__(host: str = '127.0.0.1', port: int = 8888, header_class: type = Header, body_class: type = Body, message_class: type = Message, extract_keys: Callable = <function keys_extractor at 0x7ec1d9222680>, logger: Logger = <Logger netaio.client (INFO)>, auth_plugin: AuthPluginProtocol = None, cipher_plugin: CipherPluginProtocol = None):`

Initialize the TCPClient. `host` is the default host IPv4 address. `port` is the
default port to connect to. `header_class`, `body_class`, and `message_class`
will be used for sending messages and parsing responses. `extract_keys` is a
function that extracts the keys from a message. If `auth_plugin` is provided, it
will be used to check the authenticity/authorization of all received messages
and set the auth_fields of every sent message. If `cipher_plugin` is provided,
it will be used to encrypt and decrypt all messages.

##### `add_handler(key: Hashable, handler: Callable, auth_plugin: AuthPluginProtocol = None, cipher_plugin: CipherPluginProtocol = None):`

Register a handler for a specific key. The handler must accept a MessageProtocol
object as an argument and return MessageProtocol, None, or a Coroutine that
resolves to MessageProtocol | None. If an auth plugin is provided, it will be
used to check the message in addition to any auth plugin that is set on the
client. If a cipher plugin is provided, it will be used to decrypt the message
in addition to any cipher plugin that is set on the client.

##### `on(key: Hashable, auth_plugin: AuthPluginProtocol = None, cipher_plugin: CipherPluginProtocol = None):`

Decorator to register a handler for a specific key. The handler must accept a
MessageProtocol object as an argument and return a MessageProtocol, None, or a
Coroutine that resolves to a MessageProtocol or None. If an auth plugin is
provided, it will be used to check the message in addition to any auth plugin
that is set on the client. If a cipher plugin is provided, it will be used to
decrypt the message in addition to any cipher plugin that is set on the client.

##### `async connect(host: str = None, port: int = None):`

Connect to a server.

##### `async send(message: MessageProtocol, server: tuple = None, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None):`

Send a message to the server. If use_auth is True and an auth plugin is set, it
will be called to set the auth fields on the message. If an auth plugin is
provided, it will be used to authorize the message in addition to any auth
plugin that is set on the client. If a cipher plugin is provided, it will be
used to encrypt the message in addition to any cipher plugin that is set on the
client. If use_auth is False, the auth plugin set on the client will not be
used. If use_cipher is False, the cipher plugin set on the client will not be
used.

##### `async receive_once(server: tuple = None, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None) -> netaio.common.MessageProtocol | None:`

Receive a message from the server. If a handler was registered for the message
key, the handler will be called with the message as an argument, and the result
will be returned if it is not None; otherwise, the received message will be
returned. If the message checksum fails, the message will be discarded and None
will be returned. If an auth plugin is set, it will be checked before the
message handler is called, and if the check fails, the message will be discarded
and None will be returned. If use_auth is False, the auth plugin set on the
client will not be used. If use_cipher is False, the cipher plugin set on the
client will not be used. If an auth plugin is provided, it will be used to check
the message in addition to any auth plugin that is set on the client. If a
cipher plugin is provided, it will be used to decrypt the message in addition to
any cipher plugin that is set on the client.

##### `async receive_loop(server: tuple = None, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None):`

Receive messages from the server indefinitely. Use with asyncio.create_task() to
run concurrently, then use task.cancel() to stop. If use_auth is False, the auth
plugin set on the client will not be used. If use_cipher is False, the cipher
plugin set on the client will not be used. If an auth plugin is provided, it
will be used to check the message in addition to any auth plugin that is set on
the client. If a cipher plugin is provided, it will be used to decrypt the
message in addition to any cipher plugin that is set on the client.

##### `async close(server: tuple = None):`

Close the connection to the server.

##### `set_logger(logger: Logger):`

Replace the current logger.

### `TCPServer`

TCP server class.

#### Annotations

- host: <class 'str'>
- port: <class 'int'>
- handlers: dict[typing.Hashable,
tuple[typing.Callable[[netaio.common.MessageProtocol,
asyncio.streams.StreamWriter], typing.Union[netaio.common.MessageProtocol,
NoneType, typing.Coroutine[typing.Any, typing.Any, netaio.common.MessageProtocol
| None]]], netaio.auth.AuthPluginProtocol | None,
netaio.cipher.CipherPluginProtocol | None]]
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
- cipher_plugin: <class 'netaio.cipher.CipherPluginProtocol'>

#### Methods

##### `__init__(host: str = '0.0.0.0', port: int = 8888, header_class: type = Header, body_class: type = Body, message_class: type = Message, keys_extractor: Callable = <function keys_extractor at 0x7ec1d9222680>, make_error_response: Callable = <function make_error_response at 0x7ec1d8b82440>, default_handler: Callable = <function not_found_handler at 0x7ec1d8b83be0>, logger: Logger = <Logger netaio.server (INFO)>, auth_plugin: AuthPluginProtocol = None, cipher_plugin: CipherPluginProtocol = None):`

Initialize the TCPServer. `host` is the host to listen on. `port` is the port to
listen on. `header_class`, `body_class`, and `message_class` will be used for
parsing received messages and sending responses. `keys_extractor` is a function
that extracts the keys from a message. `make_error_response` is a function that
makes an error response. `default_handler` is the default handler to use for
messages that do not match any registered handler keys. If `auth_plugin` is
provided, it will be used to check the authenticity/authorization of all
received messages and set the auth_fields of every sent message. If
`cipher_plugin` is provided, it will be used to encrypt and decrypt all
messages.

##### `add_handler(key: Hashable, handler: Callable, auth_plugin: AuthPluginProtocol = None, cipher_plugin: CipherPluginProtocol = None):`

Register a handler for a specific key. The handler must accept a MessageProtocol
object as an argument and return a MessageProtocol, None, or a Coroutine that
resolves to MessageProtocol | None. If an auth plugin is provided, it will be
used to check the message in addition to any auth plugin that is set on the
server. If a cipher plugin is provided, it will be used to decrypt the message
in addition to any cipher plugin that is set on the server. These plugins will
also be used for preparing any response message sent by the handler.

##### `on(key: Hashable, auth_plugin: AuthPluginProtocol = None, cipher_plugin: CipherPluginProtocol = None):`

Decorator to register a handler for a specific key. The handler must accept a
MessageProtocol object as an argument and return a MessageProtocol, None, or a
Coroutine that resolves to a MessageProtocol or None. If an auth plugin is
provided, it will be used to check the message in addition to any auth plugin
that is set on the server. If a cipher plugin is provided, it will be used to
decrypt the message in addition to any cipher plugin that is set on the server.
These plugins will also be used for preparing any response message sent by the
handler.

##### `subscribe(key: Hashable, writer: StreamWriter):`

Subscribe a client to a specific key. The key must be a Hashable object.

##### `unsubscribe(key: Hashable, writer: StreamWriter):`

Unsubscribe a client from a specific key. If no subscribers are left, the key
will be removed from the subscriptions dictionary.

##### `async handle_client(reader: StreamReader, writer: StreamWriter, use_auth: bool = True, use_cipher: bool = True):`

Handle a client connection. When a client connects, it is added to the clients
set. The client is then read from until the connection is lost, and the proper
handlers are called if they are defined and the message is valid. If use_auth is
False, the auth plugin set on the server will not be used. If use_cipher is
False, the cipher plugin set on the server will not be used.

##### `async start(use_auth: bool = True, use_cipher: bool = True):`

Start the server.

##### `async send(client: StreamWriter, message: MessageProtocol, collection: set = None, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None):`

Helper coroutine to send a message to a client. On error, it logs the exception
and removes the client from the given collection. If an auth plugin is provided,
it will be used to authorize the message in addition to any auth plugin that is
set on the server. If a cipher plugin is provided, it will be used to encrypt
the message in addition to any cipher plugin that is set on the server. If
use_auth is False, the auth plugin set on the server will not be used. If
use_cipher is False, the cipher plugin set on the server will not be used.

##### `async broadcast(message: MessageProtocol, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None):`

Send the message to all connected clients concurrently using asyncio.gather. If
an auth plugin is provided, it will be used to authorize the message in addition
to any auth plugin that is set on the server. If a cipher plugin is provided, it
will be used to encrypt the message in addition to any cipher plugin that is set
on the server. If use_auth is False, the auth plugin set on the server will not
be used. If use_cipher is False, the cipher plugin set on the server will not be
used.

##### `async notify(key: Hashable, message: MessageProtocol, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None):`

Send the message to all subscribed clients for the given key concurrently using
asyncio.gather. If an auth plugin is provided, it will be used to authorize the
message in addition to any auth plugin that is set on the server. If a cipher
plugin is provided, it will be used to encrypt the message in addition to any
cipher plugin that is set on the server. If use_auth is False, the auth plugin
set on the server will not be used. If use_cipher is False, the cipher plugin
set on the server will not be used.

##### `set_logger(logger: Logger):`

Replace the current logger.

### `UDPNode(DatagramProtocol)`

UDP node class.

#### Annotations

- peers: set[netaio.common.Peer]
- port: <class 'int'>
- interface: <class 'str'>
- multicast_group: <class 'str'>
- header_class: type[netaio.common.HeaderProtocol]
- body_class: type[netaio.common.BodyProtocol]
- message_class: type[netaio.common.MessageProtocol]
- handlers: dict[typing.Hashable,
tuple[typing.Callable[[netaio.common.MessageProtocol, tuple[str, int]],
netaio.common.MessageProtocol | None], netaio.auth.AuthPluginProtocol | None,
netaio.cipher.CipherPluginProtocol | None]]
- default_handler: typing.Callable[[netaio.common.MessageProtocol, tuple[str,
int]], netaio.common.MessageProtocol | None]
- extract_keys: typing.Callable[[netaio.common.MessageProtocol],
list[typing.Hashable]]
- make_error: typing.Callable[[str], netaio.common.MessageProtocol]
- subscriptions: dict[typing.Hashable, set[tuple[str, int]]]
- logger: <class 'logging.Logger'>
- transport: <class 'asyncio.transports.DatagramTransport'>
- auth_plugin: <class 'netaio.auth.AuthPluginProtocol'>
- cipher_plugin: <class 'netaio.cipher.CipherPluginProtocol'>

#### Methods

##### `__init__(port: int = 8888, interface: str = '0.0.0.0', multicast_group: str = '224.0.0.1', header_class: type = Header, body_class: type = Body, message_class: type = Message, default_handler: Callable = <function not_found_handler at 0x7ec1d8bb0790>, extract_keys: Callable = <function keys_extractor at 0x7ec1d9222680>, make_error_response: Callable = <function make_error_response at 0x7ec1d8b82440>, logger: Logger = <Logger netaio.node (INFO)>, auth_plugin: AuthPluginProtocol = None, cipher_plugin: CipherPluginProtocol = None):`

Initialize the UDPNode. `port` is the port to listen on. `interface` is the
interface to listen on. `multicast_group` is the multicast group to join.
`header_class`, `body_class`, and `message_class` will be used for sending and
parsing messages. `default_handler` is the default handler to use for messages
that do not match any registered handler keys. `extract_keys` is a function that
extracts the keys from a message. `make_error_response` is a function that makes
an error response. If `auth_plugin` is provided, it will be used to check the
set the auth_fields of every sent message and check authenticity/authorization
of all received messages. If `cipher_plugin` is provided, it will be used to
encrypt and decrypt all messages.

##### `connection_made(transport: DatagramTransport):`

Called when a connection is made. The argument is the transport representing the
pipe connection. When the connection is closed, connection_lost() is called.
This is called when the UDPNode successfully joins the multicast group.

##### `datagram_received(data: bytes, addr: tuple):`

Called when a datagram is received. The arguments are the data received and the
address of the sender. This method will parse the message and call the
appropriate handler, calling plugins as necessary.

##### `error_received(exc: Exception):`

Called when a send or receive operation raises an OSError. (Other than
BlockingIOError or InterruptedError.)

##### `connection_lost(_: Exception):`

Called when the connection is lost or closed. The argument is an exception
object or None (the latter meaning a regular EOF is received or the connection
was aborted or closed).

##### `add_handler(key: Hashable, handler: Callable, auth_plugin: AuthPluginProtocol = None, cipher_plugin: CipherPluginProtocol = None):`

Register a handler for a specific key. The handler must accept a MessageProtocol
object as an argument and return a MessageProtocol or None. If an auth plugin is
provided, it will be used to check the message in addition to any auth plugin
that is set on the node. If a cipher plugin is provided, it will be used to
decrypt the message in addition to any cipher plugin that is set on the node.
These plugins will also be used for preparing any response message sent by the
handler.

##### `on(key: Hashable, auth_plugin: AuthPluginProtocol = None, cipher_plugin: CipherPluginProtocol = None):`

Decorator to register a handler for a specific key. The handler must accept a
MessageProtocol object as an argument and return a MessageProtocol or None. If
an auth plugin is provided, it will be used to check the message in addition to
any auth plugin that is set on the node. If a cipher plugin is provided, it will
be used to decrypt the message in addition to any cipher plugin that is set on
the node. These plugins will also be used for preparing any response message
sent by the handler.

##### `subscribe(key: Hashable, addr: tuple):`

Subscribe a peer to a specific key. The key must be a Hashable object.

##### `unsubscribe(key: Hashable, addr: tuple):`

Unsubscribe a peer from a specific key. If no subscribers are left, the key will
be removed from the subscriptions dictionary.

##### `async start():`

Start the UDPNode. When a datagram is received, the datagram_received method is
called.

##### `send(message: MessageProtocol, addr: tuple, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None):`

Send a message to a given address (unicast or multicast). If an auth plugin is
provided, it will be used to authorize the message in addition to any auth
plugin that is set on the node. If a cipher plugin is provided, it will be used
to encrypt the message in addition to any cipher plugin that is set on the node.
If use_auth is False, the auth plugin set on the node will not be used. If
use_cipher is False, the cipher plugin set on the node will not be used.

##### `broadcast(message: MessageProtocol, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None):`

Send the message to all known peers. If an auth plugin is provided, it will be
used to authorize the message in addition to any auth plugin that is set on the
node. If a cipher plugin is provided, it will be used to encrypt the message in
addition to any cipher plugin that is set on the node. If use_auth is False, the
auth plugin set on the node will not be used. If use_cipher is False, the cipher
plugin set on the node will not be used.

##### `multicast(message: MessageProtocol, port: int | None = None, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None):`

Send the message to the multicast group. If an auth plugin is provided, it will
be used to authorize the message in addition to any auth plugin that is set on
the node. If a cipher plugin is provided, it will be used to encrypt the message
in addition to any cipher plugin that is set on the node. If use_auth is False,
the auth plugin set on the node will not be used. If use_cipher is False, the
cipher plugin set on the node will not be used.

##### `notify(key: Hashable, message: MessageProtocol, use_auth: bool = True, use_cipher: bool = True, auth_plugin: netaio.auth.AuthPluginProtocol | None = None, cipher_plugin: netaio.cipher.CipherPluginProtocol | None = None):`

Send the message to all subscribed peers for the given key concurrently using
asyncio.gather. If an auth plugin is provided, it will be used to authorize the
message in addition to any auth plugin that is set on the node. If a cipher
plugin is provided, it will be used to encrypt the message in addition to any
cipher plugin that is set on the node. If use_auth is False, the auth plugin set
on the node will not be used. If use_cipher is False, the cipher plugin set on
the node will not be used.

##### `stop():`

Stop the UDPNode.

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
DELETE_URI, SUBSCRIBE_URI, UNSUBSCRIBE_URI, PUBLISH_URI, NOTIFY_URI,
ADVERTISE_PEER, OK, CONFIRM_SUBSCRIBE, CONFIRM_UNSUBSCRIBE, ERROR, AUTH_ERROR,
NOT_FOUND, DISCONNECT.

### `HeaderProtocol(Protocol)`

Shows what a Header class should have and do.

#### Properties

- body_length: At a minimum, a Header must have body_length, auth_length,
message_type, and checksum properties.
- auth_length: At a minimum, a Header must have body_length, auth_length,
message_type, and checksum properties.
- message_type: At a minimum, a Header must have body_length, auth_length,
message_type, and checksum properties.
- checksum: At a minimum, a Header must have body_length, auth_length,
message_type, and checksum properties.

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

### `Peer`

Class for storing peer information.

#### Annotations

- addr: tuple[str, int]
- peer_id: bytes | None
- peer_data: bytes | None

#### Methods

##### `__init__(addr: tuple[str, int], peer_id: bytes | None = None, peer_data: bytes | None = None):`

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
- `UDPHandler`: _CallableGenericAlias
- `default_server_logger`: Logger
- `default_client_logger`: Logger
- `default_node_logger`: Logger

