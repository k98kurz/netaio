Implement two fixes for the netaio library:

## Fix 1: Race Condition in TCPClient.request()

Add task tracking to prevent concurrent `receive_loop` tasks from corrupting the TCP stream:

1. Add `_receive_loop_task: asyncio.Task | None` instance variable to TCPClient
2. In `receive_loop()`, set `self._receive_loop_task = asyncio.current_task()` at start and `= None` in finally block
3. In `request()`, check if receive_loop is already running before creating new task:
   - `was_running = (self._receive_loop_task is not None and not self._receive_loop_task.done())`
   - Only create new task if not already running
   - Cancel task in finally block only if we created it

## Fix 2: Timeout Error Handler Feature

Add centralized timeout recovery to both TCPClient and UDPNode:

### Type Definition (netaio/common.py):
Add `TimeoutErrorHandler` type after `AuthErrorHandler`:
```python
TimeoutErrorHandler = Callable[
    [NetworkNodeProtocol, str, tuple[str, int] | None, TimeoutError, dict[str, Any]],
    Awaitable[None] | None
]
```

### TCPClient Changes (netaio/client.py):
1. Import `TimeoutErrorHandler` from common
2. Add `timeout_error_handler: TimeoutErrorHandler = None` parameter to `__init__`
3. Initialize: `self._timeout_error_handler`, `self._timeout_handler_tasks: set[asyncio.Task]`, `self._timeout_handler_lock: asyncio.Lock`
4. Add `set_timeout_handler(handler)` method
5. Add `async _invoke_timeout_handler(timeout_type, server, error, context)` method
6. Add `async cancel_timeout_handler_tasks()` method
7. In `request()`, call `await self._invoke_timeout_handler(...)` before raising TimeoutError

### UDPNode Changes (netaio/node.py):
Same as TCPClient (steps 1-7) but without AutoReconnectTimeoutHandler

### AutoReconnectTimeoutHandler (netaio/client.py):
Add at bottom of file - bundled handler that auto-reconnects on timeout:
- Constructor params: `connect_timeout`, `max_retries`, `delay`, `on_reconnect` callback
- `async __call__` method implements reconnect logic with retry loop

### Exports (netaio/__init__.py):
Export `TimeoutErrorHandler` and `AutoReconnectTimeoutHandler`

## Type Hint Fixes:

`keys_extractor` type hints should accept `tuple[str, int] | None` as second parameter:
- `netaio/common.py` line 239: Protocol definition
- `netaio/client.py` line 43 (class attribute), line 58 (`__init__` param)
- `netaio/node.py` line 53 (class attribute), line 75 (`__init__` param)

## Code Style:

- Try to keep lines around 80-85 characters maximum
- Use multi-line for long statements
- Follow existing conventions

## Key Design Decisions:

1. Sync handlers execute synchronously (blocking before re-raise)
2. Async handlers run as tracked tasks, cleanup via `cancel_timeout_handler_tasks()`
3. No AutoReconnectTimeoutHandler for UDP (connectionless)
4. Timeout handler only for `request()` method
5. AutoReconnectTimeoutHandler lives at bottom of client.py (not separate file)
