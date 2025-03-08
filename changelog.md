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
