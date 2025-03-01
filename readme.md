# netaio

This is designed to be a simple and easy to use asyncio-based TCP client and
server library inspired by fastapi but for non-HTTP use cases.

## Status

This is currently a work-in-progress. Remaining work before the v0.1.0 release:

- [x] Add authorization plugin
- [x] Add cipher plugin
- [x] Add optional authorization plugin using HMAC
- [x] Add optional cipher plugin using simple symmetric stream cipher
- [ ] Add optional authorization plugin using tapescript
- [ ] UDP node with multicast peer discovery
- [ ] More thorough test suite
- [ ] Better usage examples/documentation

After that, issues will be tracked [here](https://github.com/k98kurz/netaio/issues).

## Usage

Install with `pip install netaio`. Brief examples are shown below. For more
documentation, see the
[dox.md](https://github.com/k98kurz/netaio/blob/master/dox.md) file generated by
[autodox](https://pypi.org/project/autodox/).

### Server

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

### Client

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

To test, clone the repo and run `python -m unittest discover -s tests`.

Currently, there are 4 unit tests and 3 e2e tests. The unit tests cover the
bundled plugins. The e2e tests start a server and client, then send messages from
the client to the server and receive responses. The bundled plugins are used for
the e2e tests, and an authentication failure case is also tested.

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
