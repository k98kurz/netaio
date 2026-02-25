## 0.0.9

- Added ephemeral handlers to UDPNode, TCPClient, and TCPServer:
    - `add_ephemeral_handler(key, handler, auth_plugin, cipher_plugin)` method
    - `remove_ephemeral_handler(key)` method
    - `@once(key, auth_plugin, cipher_plugin)` decorator method
- Added CRUD methods to UDPNode and TCPClient, which use ephemeral handlers
scoped to the requested server/node
    - `.create(...)` sends `CREATE_URI` message
    - `.request(...)` sends `REQUEST_URI` message
    - `.update(...)` sends `UPDATE_URI` message
    - `.delete(...)` sends `DELETE_URI` message
- Updated `Sha256StreamCipher` with a few security improvements
    - Derive unique keys for HMAC and for encryption
    - Include IV in HMAC calculation
    - Small correction to HMAC implementation
- Improved TCPClient's multi-server support and connection life-cycle management
    - `.start_receive_loop(...)` begins an asyncio task to receive from a server
    if one is not already running
    - `.stop_receive_loop(...)` stops specific server receive loop
    - `.stop_all_receive_loops()` stops all receive loops
    - `.get_receive_loops()` queries active receive loops
- Added `NOT_PERMITTED` value to `MessageType`
- Renamed `make_error_response` message generator helper function to `make_error_msg`
- Added new message generator helper functions:
    - `make_respond_uri_msg`
    - `make_ok_msg`
    - `make_not_found_msg`
    - `make_not_permitted_msg`
- Added new `make_message_type_class` function for creating custom message type
classes that comply with default requirements
- Added new `validate_message_type_class` function for validating that a custom
message type class complies with requirements
- Reserved message type values 0-30 for future base protocol updates; enforce no
message type values above 255

## 0.0.8

- Optimized `TCPServer` and `UDPNode`:
  - `broadcast`, `notify`, and `multicast` now invoke plugins only once if they
    are not peer-specific
- Slightly improved usability of `X25519CipherPlugin`

## 0.0.7

- Updated tapescript dependency and plugin

## 0.0.6

- Added new PeerPluginProtocol and DefaultPeerPlugin implementing it
- Refactor to pass Peer and peer plugin to auth and cipher plugin methods
- Updated Sha256StreamCipherPlugin to encrypt URI length if `encrypt_uri` is True
- Added new optional plugins in the `netaio.asymmetric` submodule:
  - TapescriptAuthPlugin: auth plugin using tapescript
  - X25519CipherPlugin: asymmetric cipher plugin using Curve25519 from PyNaCl
- Updated Body.prepare to raise ValueError if content + uri is too long

## 0.0.5

- Added automatic peer discovery/management to UDPNode
- Several refactors:
  - Added dependency injection (message/part classes) to auth plugins
  - Added handler system for failed auth checks on received messages
  - Made MessageType monkey-patchable and injectible where it is used

## 0.0.4

- Added UDPNode class with multicast support
- Small, miscellaneous updates to common, TCPClient, and TCPServer

## 0.0.3

- Added cipher plugin system
- Added Sha256StreamCipherPlugin
- Servers and clients can handle two layers of plugins: an outer layer set on
  the instance itself and an inner layer set on a per-handler basis (or injected
  into relevant methods).

## 0.0.2

- Added authentication/authorization plugin system
- Added HMACAuthPlugin
- Updated Handler syntax to include stream writer arg
- Updated logging: reclassified some info as debug
- Added ability for client to connect to multiple servers; default can be set at
  TCPClient initialization

## 0.0.1

- Initial release
