# Plan: TCPClient Race Condition Fix + Timeout Handler Feature

## Overview

This plan addresses two issues in the netaio library:

1. **Race condition in `TCPClient.request()`** - Prevents concurrent `receive_loop` tasks from corrupting the TCP stream
2. **Timeout error handler feature** - Allows centralized timeout recovery logic with support for sync/async handlers

---

## Part 1: Fix Race Condition in `TCPClient.request()`

### Problem

The current implementation always creates a new `receive_loop` task in `request()`. If a receive_loop is already running, this causes two loops to compete for reading from the TCP stream, resulting in interleaved reads and corrupted data.

### Solution

Track whether a `receive_loop` is already running and only create a new one if needed.

### Changes to `netaio/client.py`

#### 1.1 Add instance variable in `__init__`

Add to class attributes (around line 28) and initialize in `__init__` (around line 113):

```python
# Class attributes (around line 28)
_receive_loop_task: asyncio.Task | None

# In __init__ (around line 113)
self._receive_loop_task = None
```

#### 1.2 Modify `receive_loop()` to track the task

Update method (around line 439):

```python
async def receive_loop(
        self, server: tuple[str, int] = None, use_auth: bool = True,
        use_cipher: bool = True, auth_plugin: AuthPluginProtocol|None = None,
        cipher_plugin: CipherPluginProtocol|None = None
    ):
    """Receive messages from the server indefinitely. Use with
        asyncio.create_task() to run concurrently, then use
        task.cancel() to stop. If use_auth is False, the auth plugin
        set on the client will not be used. If use_cipher is
        False, the cipher plugin set on the client will not be
        used. If an auth plugin is provided, it will be used to
        check the message in addition to any auth plugin that is set
        on the client. If a cipher plugin is provided, it will be
        used to decrypt the message in addition to any cipher
        plugin that is set on the client.
    """
    server = server or self.default_host
    self._receive_loop_task = asyncio.current_task()
    try:
        while True:
            await self.receive_once(
                server, use_auth, use_cipher, auth_plugin, cipher_plugin
            )
    except asyncio.CancelledError:
        self.logger.info("Receive loop cancelled")
        break
    except Exception as e:
        self.logger.error("Error in receive_loop", exc_info=True)
        break
    finally:
        self._receive_loop_task = None
```

#### 1.3 Modify `request()` to conditionally start receive_loop

Update method (around line 264):

```python
async def request(
        self, uri: bytes, timeout: float = 10.0,
        server: tuple[str, int] = None,
        use_auth: bool = True, use_cipher: bool = True,
        auth_plugin: AuthPluginProtocol|None = None,
        cipher_plugin: CipherPluginProtocol|None = None
    ) -> MessageProtocol:
    """Send a REQUEST_URI message and wait for a RESPOND_URI response.
        Sets an ephemeral handler for the expected response using the
        `@self.once()` decorator, then sends a REQUEST_URI message to
        the connected server. Waits in a loop until either the response
        is received or the timeout is reached. If it times out, removes
        the ephemeral handler and raises a TimeoutError. If the response
        is received, returns that message.
    """
    result = []

    key = (self.message_type_class.RESPOND_URI, uri,
           server or self.default_host)
    event = asyncio.Event()

    @self.once(key, auth_plugin, cipher_plugin)
    def handle_response(message: MessageProtocol, writer: asyncio.StreamWriter):
        result.append(message)
        event.set()

    request_body = self.body_class.prepare(content=b'', uri=uri)
    request_message = self.message_class.prepare(
        request_body, self.message_type_class.REQUEST_URI
    )
    await self.send(
        request_message, server, use_auth, use_cipher,
        auth_plugin, cipher_plugin
    )

    # Check if receive_loop is already running
    was_running = (
        self._receive_loop_task is not None
        and not self._receive_loop_task.done()
    )

    if not was_running:
        loop_task = asyncio.create_task(
            self.receive_loop(server, use_auth, use_cipher,
                              auth_plugin, cipher_plugin)
        )

    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    finally:
        if not was_running:
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

    if not len(result):
        self.remove_ephemeral_handler(key)
        raise TimeoutError(
            f"Request for URI {uri.decode('utf-8', errors='replace')} "
            f"timed out after {timeout}s"
        )

    return result[0]
```

---

## Part 2: Add Timeout Error Handler Feature to TCPClient

### Problem

Users need to implement timeout recovery logic in every location where `request()` is called, leading to code duplication, especially in decentralized networks with many clients.

### Solution

Add `set_timeout_handler()` method with support for both sync and async handlers, plus a bundled `AutoReconnectTimeoutHandler` utility.

### Changes to `netaio/common.py`

#### 2.1 Add TimeoutErrorHandler type definition

Add after `AuthErrorHandler` definition (around line 722):

```python
TimeoutErrorHandler = Callable[
    [
        NetworkNodeProtocol,
        str,
        tuple[str, int] | None,
        TimeoutError,
        dict[str, Any]
    ],
    Awaitable[None] | None
]
```

### Changes to `netaio/__init__.py`

#### 2.2 Export TimeoutErrorHandler

Add to imports (around line 22):

```python
from .common import (
    ...
    Handler,
    AuthErrorHandler,
    TimeoutErrorHandler,
    ...
)
```

### Changes to `netaio/client.py`

#### 2.3 Import TimeoutErrorHandler

Add to imports at the top:

```python
from .common import (
    ...
    AuthErrorHandler,
    TimeoutErrorHandler,
    ...
)
```

#### 2.4 Modify `__init__` to accept and store timeout handler

Add parameter (around line 63) and instance variables (around line 113):

```python
def __init__(
        self, host: str = "127.0.0.1", port: int = 8888,
        local_peer: Peer = None,
        header_class: type[HeaderProtocol] = Header,
        message_type_class: type[IntEnum] = MessageType,
        auth_fields_class: type[AuthFieldsProtocol] = AuthFields,
        body_class: type[BodyProtocol] = Body,
        message_class: type[MessageProtocol] = Message,
        extract_keys: Callable[[MessageProtocol, tuple[str, int] | None],
                               list[Hashable]] = keys_extractor,
        logger: logging.Logger = default_client_logger,
        auth_plugin: AuthPluginProtocol = None,
        cipher_plugin: CipherPluginProtocol = None,
        peer_plugin: PeerPluginProtocol = None,
        auth_error_handler: AuthErrorHandler = auth_error_handler,
        timeout_error_handler: TimeoutErrorHandler = None,
    ):
    ...
    self._timeout_error_handler = timeout_error_handler
    self._timeout_handler_tasks: set[asyncio.Task] = set()
    self._timeout_handler_lock = asyncio.Lock()
```

#### 2.5 Add `set_timeout_handler()` method

Add after `remove_ephemeral_handler` (around line 197):

```python
def set_timeout_handler(self, handler: TimeoutErrorHandler):
    """Set timeout error handler. Handler receives
        (client, timeout_type, server, error, context).
        Can be sync or async. If async, task is tracked and can
        be cancelled via cancel_timeout_handler_tasks().
    """
    self._timeout_error_handler = handler
```

#### 2.6 Add `_invoke_timeout_handler()` method

Add after `set_timeout_handler`:

```python
async def _invoke_timeout_handler(
        self,
        timeout_type: str,
        server: tuple[str, int] | None,
        error: TimeoutError,
        context: dict[str, Any]
    ):
    """Invoke the timeout handler, tracking async tasks for cleanup."""
    handler = self._timeout_error_handler
    if not handler:
        return

    try:
        result = handler(self, timeout_type, server, error, context)

        if asyncio.iscoroutine(result):
            # Track and run async task
            task = asyncio.create_task(result, name="timeout_handler")
            async with self._timeout_handler_lock:
                self._timeout_handler_tasks.add(task)

            # Remove from tracking when done (success or error)
            def on_done(t):
                async def _remove():
                    async with self._timeout_handler_lock:
                        self._timeout_handler_tasks.discard(t)
                asyncio.create_task(_remove())

            task.add_done_callback(on_done)
        # If sync, already executed

    except Exception:
        self.logger.error(
            "Timeout error handler failed for %s to %s",
            timeout_type, server, exc_info=True
        )
```

#### 2.7 Add `cancel_timeout_handler_tasks()` method

Add after `_invoke_timeout_handler`:

```python
async def cancel_timeout_handler_tasks(self):
    """Cancel all in-progress timeout handler tasks and wait for
        them to complete. Useful for graceful shutdown when using
        async timeout handlers.
    """
    async with self._timeout_handler_lock:
        tasks = list(self._timeout_handler_tasks)
        self._timeout_handler_tasks.clear()

    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```

#### 2.8 Modify `request()` to call timeout handler

Update the timeout exception handling in `request()` (around line 299):

```python
try:
    await asyncio.wait_for(event.wait(), timeout=timeout)
except asyncio.TimeoutError as e:
    # Invoke timeout handler before raising
    await self._invoke_timeout_handler(
        "request",
        server or self.default_host,
        e,
        {"uri": uri, "timeout": timeout}
    )
    raise
```

### Create AutoReconnectTimeoutHandler in `netaio/client.py`

Add at the bottom of the file:

```python
class AutoReconnectTimeoutHandler:
    """Bundled timeout handler that automatically reconnects on timeout.

        Example:
            client = TCPClient(...)
            client.set_timeout_handler(AutoReconnectTimeoutHandler())
    """
    def __init__(
        self,
        connect_timeout: float = 5.0,
        max_retries: int | None = None,
        delay: float = 0.1,
        on_reconnect: Callable[[TCPClient, tuple[str, int]], None] = None
    ):
        self._connect_timeout = connect_timeout
        self._max_retries = max_retries
        self._delay = delay
        self._on_reconnect = on_reconnect

    async def __call__(
        self,
        client: TCPClient,
        timeout_type: str,
        server: tuple[str, int] | None,
        error: TimeoutError,
        context: dict
    ):
        if timeout_type != "request":
            return  # Only handle request timeouts

        server = server or client.default_host
        retries = 0

        while True:
            try:
                await client.close(server)
                await asyncio.wait_for(
                    client.connect(server),
                    timeout=self._connect_timeout
                )

                if self._on_reconnect:
                    self._on_reconnect(client, server)

                client.logger.info(
                    f"Successfully reconnected to {server} after "
                    f"{retries} retries"
                )
                break

            except Exception as e:
                retries += 1
                if (self._max_retries is not None and
                    retries >= self._max_retries):
                    client.logger.error(
                        f"Failed to reconnect to {server} after "
                        f"{self._max_retries} attempts: {e}"
                    )
                    break

                client.logger.warning(
                    f"Reconnect attempt {retries} failed for {server}: "
                    f"{e}, retrying in {self._delay}s"
                )
                await asyncio.sleep(self._delay)
```

### Export AutoReconnectTimeoutHandler from `netaio/__init__.py`

Add to imports (around line 1):

```python
from .client import TCPClient, AutoReconnectTimeoutHandler
```

---

## Part 3: Add Timeout Error Handler to UDPNode

UDPNode also has a `request()` method that can timeout. We should add the same timeout handler functionality but without the AutoReconnectTimeoutHandler (since UDP is connectionless).

### Changes to `netaio/common.py`

No changes - already have TimeoutErrorHandler type.

### Changes to `netaio/node.py`

#### 3.1 Import TimeoutErrorHandler

Add to imports at the top:

```python
from .common import (
    ...
    AuthErrorHandler,
    TimeoutErrorHandler,
    ...
)
```

#### 3.2 Add to class attributes (around line 37)

```python
_timeout_error_handler: TimeoutErrorHandler
_timeout_handler_tasks: set[asyncio.Task]
_timeout_handler_lock: asyncio.Lock
```

#### 3.3 Modify `__init__` to accept and store timeout handler

Add parameter (around line 74) and initialize (around line 126):

```python
def __init__(
        self,
        ...
        auth_error_handler: AuthErrorHandler = auth_error_handler,
        timeout_error_handler: TimeoutErrorHandler = None,
    ):
    ...
    self._timeout_error_handler = timeout_error_handler
    self._timeout_handler_tasks: set[asyncio.Task] = set()
    self._timeout_handler_lock = asyncio.Lock()
```

#### 3.4 Add `set_timeout_handler()` method

Add after `remove_ephemeral_handler` (around line 197):

```python
def set_timeout_handler(self, handler: TimeoutErrorHandler):
    """Set timeout error handler. Handler receives
        (node, timeout_type, server, error, context).
        Can be sync or async. If async, task is tracked and can
        be cancelled via cancel_timeout_handler_tasks().
    """
    self._timeout_error_handler = handler
```

#### 3.5 Add `_invoke_timeout_handler()` method

Add after `set_timeout_handler` (same as TCPClient version):

```python
async def _invoke_timeout_handler(
        self,
        timeout_type: str,
        server: tuple[str, int] | None,
        error: TimeoutError,
        context: dict[str, Any]
):
    """Invoke the timeout handler, tracking async tasks for cleanup."""
    handler = self._timeout_error_handler
    if not handler:
        return

    try:
        result = handler(self, timeout_type, server, error, context)

        if asyncio.iscoroutine(result):
            # Track and run async task
            task = asyncio.create_task(result, name="timeout_handler")
            async with self._timeout_handler_lock:
                self._timeout_handler_tasks.add(task)

            # Remove from tracking when done (success or error)
            def on_done(t):
                async def _remove():
                    async with self._timeout_handler_lock:
                        self._timeout_handler_tasks.discard(t)
                asyncio.create_task(_remove())

            task.add_done_callback(on_done)
        # If sync, already executed

    except Exception:
        self.logger.error(
            "Timeout error handler failed for %s to %s",
            timeout_type, server, exc_info=True
        )
```

#### 3.6 Add `cancel_timeout_handler_tasks()` method

Add after `_invoke_timeout_handler` (same as TCPClient version):

```python
async def cancel_timeout_handler_tasks(self):
    """Cancel all in-progress timeout handler tasks and wait for
        them to complete. Useful for graceful shutdown when using
        async timeout handlers.
    """
    async with self._timeout_handler_lock:
        tasks = list(self._timeout_handler_tasks)
        self._timeout_handler_tasks.clear()

    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```

#### 3.7 Modify `request()` to call timeout handler

Update the timeout exception handling in `request()` (around line 555):

```python
try:
    await asyncio.wait_for(event.wait(), timeout=timeout)
except asyncio.TimeoutError as e:
    # Invoke timeout handler before raising
    await self._invoke_timeout_handler(
        "request",
        server,
        e,
        {"uri": uri, "timeout": timeout}
    )
    self.remove_ephemeral_handler(key)
    raise
```

---

## Part 4: Type Hint Fixes

Update `keys_extractor` type hints across all files that reference it:

### `netaio/common.py` (line 239):

```python
def extract_keys(self) -> Callable[
    [MessageProtocol, tuple[str, int] | None], list[Hashable]
]:
```

### `netaio/client.py`:

- Class attribute (around line 43):
```python
extract_keys: Callable[[MessageProtocol, tuple[str, int] | None],
                       list[Hashable]]
```

- `__init__` parameter (around line 58):
```python
extract_keys: Callable[[MessageProtocol, tuple[str, int] | None],
                       list[Hashable]] = keys_extractor,
```

### `netaio/node.py`:

- Class attribute (around line 53):
```python
extract_keys: Callable[[MessageProtocol, tuple[str, int] | None],
                       list[Hashable]]
```

- `__init__` parameter (around line 75):
```python
extract_keys: Callable[[MessageProtocol, tuple[str, int] | None],
                       list[Hashable]] = keys_extractor,
```

---

## Part 5: Remove Debugging Code

Remove commented line in `netaio/node.py` (line 541):

```python
# Remove this line:
#key = (self.message_type_class.RESPOND_URI, uri)
```

---

## Part 6: Documentation Updates

Update docstrings to document new parameters and methods:

### `TCPClient.__init__`

Document the new `timeout_error_handler` parameter.

### `TCPClient.set_timeout_handler()`

Document usage and behavior (sync vs async).

### `TCPClient.cancel_timeout_handler_tasks()`

Explain when to call this for graceful shutdown.

### `TCPClient._invoke_timeout_handler()`

Internal method, brief documentation.

### `AutoReconnectTimeoutHandler`

Document class, constructor parameters, and usage example.

### `UDPNode` methods

Same documentation updates as TCPClient where applicable.

---

## Part 7: Code Style Notes

- Keep lines around 80-85 characters maximum
- Use multi-line for long statements to stay within limit
- Follow existing code conventions

---

## Summary of Files to Modify

1. `netaio/common.py` - Add TimeoutErrorHandler type, update type hints
2. `netaio/client.py` - Add receive_loop tracking, timeout handler feature, AutoReconnectTimeoutHandler
3. `netaio/node.py` - Add timeout handler feature
4. `netaio/__init__.py` - Export TimeoutErrorHandler and AutoReconnectTimeoutHandler
5. `tests/test_tcp_e2e.py` - Add tests for new functionality (future work)
