# netaio.asymmetric

## Classes

### `TapescriptAuthPlugin`

Tapescript auth plugin.

#### Annotations

- lock: <class 'tapescript.tools.Script'>
- seed: <class 'bytes'>
- nonce_field: <class 'str'>
- ts_field: <class 'str'>
- use_peer_lock: <class 'bool'>
- witness_field: <class 'str'>
- witness_func: typing.Callable[[bytes, dict[str, bytes]],
tapescript.tools.Script | bytes]
- contracts: <class 'dict'>
- plugins: <class 'dict'>

#### Methods

##### `__init__(config: dict):`

Initialize the auth plugin with a config. The config should contain {"lock":
<tapescript.Script>, "seed": <bytes>}. It can contain {"nonce_field": <str>} to
specify the auth field name for the nonce; default is "nonce". It can contain
{"witness_field": <str>} to specify the auth field name for the witness script;
default is "witness". It can contain {"ts_field": <str>} to specify the auth
field name for the Unix epoch timestamp; the default is "ts". It can contain
{"use_peer_lock": <bool>} to specify whether to use the peer's locking script
instead of the plugin's; the default is False. It can contain {"witness_func":
<Callable>} to specify a Callable for making witness scripts, which must accept
the seed and a sigfields dict with the encoded message body as sigfield1, the
nonce as sigfield2, and the timestamp as sigfield3, and it must return a
tapescript.Script or bytes. It can contain {"contracts": <dict>} and/or
{"plugins": <dict>} to pass to the tapescript runtime. By default, this will
assume a single-signature scheme and use the tapescript.make_single_sig_witness
tool to create witnesses.

##### `make(auth_fields: AuthFieldsProtocol, body: BodyProtocol, node: netaio.common.NetworkNodeProtocol | None = None, peer: netaio.common.Peer | None = None, peer_plugin: netaio.common.PeerPluginProtocol | None = None):`

If the nonce and ts fields are not set, generate them. Then, call the witness
function with the seed and the sigfields dict to produce a witness.

##### `check(auth_fields: AuthFieldsProtocol, body: BodyProtocol, node: netaio.common.NetworkNodeProtocol | None = None, peer: netaio.common.Peer | None = None, peer_plugin: netaio.common.PeerPluginProtocol | None = None) -> bool:`

Check the witness script. If the peer is set, and the peer_plugin parses
peer.data to a dict containing a "lock", and self.use_peer_lock is True, that
locking script will be used instead of the plugin's locking script.

##### `error(message_class: type = Message, message_type_class: type = <enum 'MessageType'>, header_class: type = Header, auth_fields_class: type = AuthFields, body_class: type = Body) -> MessageProtocol:`

Make an error message that says "HMAC auth failed".

### `X25519CipherPlugin(CipherPluginProtocol)`

X25519 cipher plugin.

#### Annotations

- key: <class 'nacl.public.PrivateKey'>
- encrypt_uri: <class 'bool'>

#### Methods

##### `__init__(config: dict):`

Initialize the cipher plugin with a config. The config must contain {"seed":
<bytes>}. It can contain {"encrypt_uri": <bool>} to specify whether to encrypt
the uri; the default is False.

##### `encrypt(message: MessageProtocol, node: netaio.common.NetworkNodeProtocol | None = None, peer: netaio.common.Peer | None = None, peer_plugin: netaio.common.PeerPluginProtocol | None = None) -> MessageProtocol:`

Encrypt the message body, setting the self.iv_field in the auth_data. This will
overwrite any existing value in that auth_data field. If the self.encrypt_uri is
True, the uri will be encrypted as well as the content.

##### `decrypt(message: MessageProtocol, node: netaio.common.NetworkNodeProtocol | None = None, peer: netaio.common.Peer | None = None, peer_plugin: netaio.common.PeerPluginProtocol | None = None) -> MessageProtocol:`

Decrypt the message body, reading the self.iv_field from the auth_data. Returns
a new message with the decrypted body.
