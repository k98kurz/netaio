# netaio

This is designed to be a simple and easy to use asyncio-based TCP client and
server library inspired by fastapi but for non-HTTP use cases.

## Status

This is currently a work-in-progress. Remaining work before the v0.1.0 release:

- [x] Authorization plugin system
- [x] Cipher plugin system
- [x] Optional authorization plugin using HMAC
- [x] Optional cipher plugin using simple symmetric stream cipher
- [x] UDP node with multicast
- [ ] Automatic peer advertisement/discovery/management for UDP node
- [ ] Error/errored message handling system
- [ ] Optional authorization plugin using tapescript
- [ ] Optional cipher plugin using Curve25519 asymmetric encryption
- [ ] Optional authorization plugin using Hashcash/PoW for anti-spam DoS protection
- [ ] Ephemeral handlers (i.e. handlers that are removed after first use)
- [ ] Core daemon to proxy traffic for local apps
- [ ] E2e encrypted chat app example

After that, issues will be tracked [here](https://github.com/k98kurz/netaio/issues).

## Usage

Install with `pip install netaio`. Brief examples are shown below. For more
documentation, see the
[dox.md](https://github.com/k98kurz/netaio/blob/master/dox.md) file generated by
[autodox](https://pypi.org/project/autodox/).

### TCPServer

```python
from netaio import TCPServer, Body, Message, MessageType, HMACAuthPlugin
import asyncio


server = TCPServer(port=8888, auth_plugin=HMACAuthPlugin(config={"secret": "test"}))

@server.on((MessageType.REQUEST_URI, b'something'))
async def something(msg: Message, writer: asyncio.StreamWriter):
    body = Body.prepare(b'This is it.', uri=b'something')
    return Message.prepare(body, MessageType.RESPOND_URI)

@server.on(MessageType.SUBSCRIBE_URI)
async def subscribe(msg: Message, writer: asyncio.StreamWriter):
    server.subscribe(msg.body.uri, writer)
    return Message.prepare(Body.prepare(b'', uri=msg.body.uri), MessageType.CONFIRM_SUBSCRIBE)

@server.on(MessageType.UNSUBSCRIBE_URI)
async def unsubscribe(msg: Message, writer: asyncio.StreamWriter):
    server.unsubscribe(msg.body.uri, writer)
    return Message.prepare(Body.prepare(b'', uri=msg.body.uri), MessageType.CONFIRM_UNSUBSCRIBE)

asyncio.run(server.start())
```

### TCPClient

```python
from netaio import TCPClient, Body, Message, MessageType, HMACAuthPlugin
import asyncio


client = TCPClient("127.0.0.1", 8888, auth_plugin=HMACAuthPlugin(config={"secret": "test"}))
received_resources = {}

@client.on(MessageType.RESPOND_URI)
def echo(msg: Message, writer: asyncio.StreamWriter):
    received_resources[msg.body.uri] = msg.body.content

async def run_client():
    request_body = Body.prepare(b'pls gibs me dat', uri=b'something')
    request_message = Message.prepare(request_body, MessageType.REQUEST_URI)
    await client.connect()
    await client.send(request_message)
    await client.receive_once()

asyncio.run(run_client())

print(received_resources)
```

### UDPNode

```python
from netaio import UDPNode, Body, Message, MessageType, HMACAuthPlugin
import asyncio

echo_node = UDPNode(auth_plugin=HMACAuthPlugin(config={"secret": "test"}))

def default_handler(msg: Message, addr: tuple[str, int]):
    echo_node.logger.info("Sending echo to %s...", addr)
    return Message.prepare(msg.body, MessageType.OK)

@echo_node.on(MessageType.OK)
def echo(msg: Message, addr: tuple[str, int]):
    echo_node.logger.info("Received echo from %s.", addr)

echo_node.default_handler = default_handler
echo_msg = Message.prepare(Body.prepare(b'echo'), MessageType.REQUEST_URI)

async def main(local_addr: tuple[str, int], remote_addr: tuple[str, int]|None = None):
    echo_node.interface = local_addr[0]
    echo_node.port = local_addr[1]
    await echo_node.start()
    while True:
        await asyncio.sleep(1)
        if remote_addr:
            echo_node.send(echo_msg, remote_addr)
        else:
            echo_node.multicast(echo_msg)

local_addr = ("127.0.0.1", 8888)
remote_addr = None
asyncio.run(main(local_addr, remote_addr))
```

Note that to run this example on a single machine, the port must be different
in the second node instance, e.g. `local_addr = ("127.0.0.1", 8889)`, and then
the remote address must be set to the first node's address, e.g.
`remote_addr = ("127.0.0.1", 8888)`. Multicast will not work locally because of
the different ports.

### Authentication/Authorization

The server and client support an optional authentication/authorization plugin.
Each plugin is instantiated with a dict of configuration parameters, and it must
implement the `AuthPluginProtocol` (i.e. have `make`, `check`, and `error`
methods). Once the plugin has been instantiated, it can be passed to the
`TCPServer` and `TCPClient` constructors or set on the client or server
instances themselves. An auth plugin can also be set on a per-handler basis by
passing the plugin as a second argument to the `on` method. Currently, if an
auth plugin is set both on the instance and per-handler, both will be checked
before the handler function is called, and both will be applied to the response
body; the per-handler plugin will be able to overwrite any auth fields set by
the instance plugin.

Currently, netaio includes an `HMACAuthPlugin` that can be used by the server
and client to authenticate and authorize requests. This uses a shared secret to
generate and check HMACs over message bodies.

<details>
<summary>Example</summary>

```python
from netaio import TCPServer, TCPClient, HMACAuthPlugin, MessageType, Body, Message

outer_auth_plugin = HMACAuthPlugin(config={"secret": "test"})
inner_auth_plugin = HMACAuthPlugin(config={"secret": "tset", "hmac_field": "camh"})
server = TCPServer(port=8888, auth_plugin=outer_auth_plugin)
client = TCPClient(host="127.0.0.1", port=8888, auth_plugin=outer_auth_plugin)

@server.on(MessageType.CREATE_URI, inner_auth_plugin)
async def put_uri(msg: Message, writer: asyncio.StreamWriter):
    body = Body.prepare(b'Resource saved.', uri=msg.body.uri)
    return Message.prepare(body, MessageType.OK)
```
</details>

### Cipher (encryption/decryption)

The server and client support an optional cipher plugin. Each plugin is
instantiated with a dict of configuration parameters, and it must implement the
`CipherPluginProtocol` (i.e. have `encrypt` and `decrypt` methods). Once the
plugin has been instantiated, it can be passed to the `TCPServer` and
`TCPClient` constructors or set on the client or server instances themselves.
a cipher plugin can also be set on a per-handler basis by passing the plugin
as a third argument to the `on` method. If a cipher plugin is set both on the
instance and per-handler, both will be applied to the message.

Currently, netaio includes a `Sha256StreamCipherPlugin` that can be used by
the server and client to encrypt and decrypt messages using a simple symmetric
stream cipher. This uses a shared secret key and per-message IVs.

<details>
<summary>Example</summary>

```python
from netaio import TCPServer, TCPClient, Sha256StreamCipherPlugin, MessageType, Body, Message

outer_cipher_plugin = Sha256StreamCipherPlugin(config={"key": "test"})
inner_cipher_plugin = Sha256StreamCipherPlugin(config={"key": "tset", "iv_field": "iv2"})
server = TCPServer(port=8888, cipher_plugin=outer_cipher_plugin)
client = TCPClient(host="127.0.0.1", port=8888, cipher_plugin=outer_cipher_plugin)

@server.on(MessageType.REQUEST_URI, inner_cipher_plugin)
async def request_uri(msg: Message, writer: asyncio.StreamWriter):
    body = Body.prepare(b'Super secret data.', uri=msg.body.uri)
    return Message.prepare(body, MessageType.RESPOND_URI)
```
</details>

### Encapsulation

The encapsulation model for plugin interactions with messages is as follows:

#### Send

1. Per-handler/injected `cipher_plugin.encrypt`
2. Per-handler/injected `auth_plugin.make`
3. Instance `cipher_plugin.encrypt`
4. Instance `auth_plugin.make`

#### Receive

1. Instance `auth_plugin.check`
2. Instance `cipher_plugin.decrypt`
3. Per-handler/injected `auth_plugin.check`
4. Per-handler/injected `cipher_plugin.decrypt`


## Testing

To test, clone the repo and run `python -m unittest discover -s tests`. Or to
run the individual tests and see the output separated by test file, instead run
`find tests/ -name test_*.py -print -exec python {} \;`.

Currently, there are 4 unit tests and 7 e2e tests. The unit tests cover the
bundled plugins. The e2e tests start a server and client, then send messages
from the client to the server and receive responses; the UDP e2e test suite
starts 2 nodes and treats them like a server and client to make testing a bit
simpler and easier to follow. The bundled plugins are used for the e2e tests,
and authentication failure cases are also tested.

## License

Copyright (c) 2025 Jonathan Voss (k98kurz)

Permission to use, copy, modify, and/or distribute this software
for any purpose with or without fee is hereby granted, provided
that the above copyright notice and this permission notice appear in
all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR
CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
