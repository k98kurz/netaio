# Progress

## Task 2: Fix Type Hints for keys_extractor (HIGH)

### Completed
- Fixed NetworkNodeProtocol.extract_keys type annotation in common.py (line 240)
- Fixed TCPClient class attribute type annotation in netaio/client.py (line 44)
- Fixed TCPClient __init__ parameter type annotation in netaio/client.py (line 63)
- Fixed UDPNode class attribute type annotation in netaio/node.py (line 54)
- Fixed UDPNode __init__ parameter type annotation in netaio/node.py (line 79)
- All type hints now correctly accept `tuple[str, int] | None` as second parameter

### Acceptance Criteria Met
✓ NetworkNodeProtocol.extract_keys property in common.py (line 240) type changed from `Callable[[MessageProtocol], list[Hashable]]` to `Callable[[MessageProtocol, tuple[str, int] | None], list[Hashable]]`
✓ TCPClient class attribute in netaio/client.py (line 44) updated
✓ TCPClient __init__ parameter in netaio/client.py (line 63) updated
✓ UDPNode class attribute in netaio/node.py (line 53) updated
✓ UDPNode __init__ parameter in netaio/node.py (line 75) updated

### Learnings
- The original type hints only accepted a single MessageProtocol parameter
- The actual keys_extractor function signature includes an optional `host: tuple[str, int] | None` parameter
- This mismatch between type hints and implementation caused type checking issues
- All 28 existing tests continue to pass after the fix

### Status
**COMPLETE** - Task 2 can be marked as "In Review"

---

## Task 4: Fix Timeout Handler Invocation Bug (CRITICAL)

### Completed
- Fixed critical bug in `request()` where timeout handler code was unreachable
- Wrapped `await asyncio.wait_for(event.wait(), timeout=timeout)` in try/except block
- Catches `asyncio.TimeoutError` and converts to `TimeoutError`
- Calls `_invoke_timeout_handler()` before raising `TimeoutError`
- Verified timeout handler is invoked correctly with test showing handler was called with proper context

### Acceptance Criteria Met
✓ Wrap `await asyncio.wait_for(event.wait(), timeout=timeout)` in try/except block
✓ Catch `asyncio.TimeoutError` exception
✓ Convert to `TimeoutError` and call `_invoke_timeout_handler()` before raising
✓ Ensure timeout handler is actually invoked when timeout occurs
✓ All existing tests continue to pass

### Learnings
- The original code had timeout handler invocation AFTER the try/finally block that wrapped `asyncio.wait_for()`
- When `asyncio.TimeoutError` was raised, it bubbled up before reaching the handler invocation code
- Moving the timeout handling inside the try block and catching `asyncio.TimeoutError` ensures handler is called

### Status
**COMPLETE** - Task 4 can be marked as "In Review"

---

## Task 1: Add TimeoutErrorHandler Type Definition

### Completed
- Added `Awaitable` to typing imports in netaio/common.py
- Added `TimeoutErrorHandler` type definition after `AuthErrorHandler` at line 724-727 in netaio/common.py
- Type signature: `Callable[[NetworkNodeProtocol, str, tuple[str, int] | None, TimeoutError, dict[str, Any]], Awaitable[None] | None]`

### Acceptance Criteria Met
✓ TimeoutErrorHandler type defined with correct signature accepting NetworkNodeProtocol, timeout_type, server, error, and context
✓ Type accepts both sync (None) and async (Awaitable[None]) return types
✓ Located after AuthErrorHandler definition in common.py

### Status
**COMPLETE** - Task 1 can be marked as "In Review"

---

## Task 3: Fix Race Condition in TCPClient.receive_loop()

### Completed
- Added `_receive_loop_task: asyncio.Task | None` class attribute to TCPClient
- Initialized `_receive_loop_task = None` in `__init__` method
- Modified `receive_loop()` to set `self._receive_loop_task = asyncio.current_task()` at start and `= None` in finally block
- Modified `request()` to use `was_running` variable to track if receive_loop was already running
- Modified `request()` to check if receive_loop is already running: `was_running = (self._receive_loop_task is not None and not self._receive_loop_task.done())`
- Modified `request()` to only create new task if not already running
- Modified `request()` to only cancel task in finally block if it was created during the call (i.e., not was_running)

### Acceptance Criteria Met
✓ _receive_loop_task: asyncio.Task | None instance variable added to TCPClient class
✓ receive_loop() sets self._receive_loop_task = asyncio.current_task() at start
✓ receive_loop() sets self._receive_loop_task = None in finally block
✓ request() uses local variable `was_running` to track if receive_loop was already running
✓ request() checks if receive_loop is already running: `was_running = (self._receive_loop_task is not None and not self._receive_loop_task.done())`
✓ request() only creates new task if not already running
✓ request() only cancels task in finally block if it was created during the call (i.e., not was_running)

### Status
**IN REVIEW** - All acceptance criteria met; 28 tests pass including 8 TCP e2e tests

---

## Task 5: Implement AutoReconnectTimeoutHandler for TCPClient

### Completed
- Added `AutoReconnectTimeoutHandler` class at bottom of netaio/client.py (line 749-825)
- Constructor accepts connect_timeout, max_retries, delay, on_reconnect parameters
- `__call__` method implements async reconnect logic with retry loop
- Attempts to reconnect with configurable timeout and max retries
- Invokes on_reconnect callback (sync or async) on successful reconnect
- Returns None - TimeoutError is always raised by request() after handler completes
- Proper error handling and logging for timeout, connection, and generic exceptions
- Added `Awaitable` import to typing imports in client.py
- Exported `AutoReconnectTimeoutHandler` and `TimeoutErrorHandler` from netaio/__init__.py
- All 28 existing tests continue to pass
- Imports verified: `from netaio import AutoReconnectTimeoutHandler, TimeoutErrorHandler`

### Acceptance Criteria Met
✓ Class defined at bottom of netaio/client.py
✓ Constructor accepts connect_timeout, max_retries, delay, on_reconnect parameters
✓ __call__ method implements async reconnect logic with retry loop
✓ Attempts to reconnect and invokes on_reconnect callback on success
✓ Returns None (the TimeoutError is always raised by request() after handler completes)
✓ Handler runs for side effects: prepares connection for subsequent requests after the current one fails
✓ Proper error handling and logging throughout

### Learnings
- The handler only runs for 'request_timeout' type, ignores other timeout types
- Uses asyncio.wait_for with connect_timeout for each connection attempt
- Properly handles both sync and async on_reconnect callbacks
- Logs at info/warning/error levels appropriately for different scenarios
- Implements exponential backoff via configurable delay between retries

###     Status
**IN REVIEW** - Task 5 complete with exports (Task 7 also completed)

---

## Task 6: Add Timeout Handler Infrastructure to UDPNode (CRITICAL)

### Completed
- Added `TimeoutErrorHandler` to imports from common module in netaio/node.py
- Added `Coroutine` to typing imports
- Added class attributes: `timeout_error_handler`, `_timeout_handler_tasks`, `_timeout_handler_lock`
- Added `timeout_error_handler` parameter to `__init__` with default None
- Updated docstring to describe timeout_error_handler parameter
- Initialized `self.timeout_error_handler = timeout_error_handler` in `__init__`
- Initialized `self._timeout_handler_tasks = set()` in `__init__`
- Initialized `self._timeout_handler_lock = asyncio.Lock()` in `__init__`
- Implemented `set_timeout_handler(handler)` method at line 585-586
- Implemented `async _invoke_timeout_handler(timeout_type, server, error, context)` method at lines 589-605
- Implemented `async cancel_timeout_handler_tasks()` method at lines 608-613
- Modified `request()` method to call `_invoke_timeout_handler()` before raising TimeoutError (lines 579-582)
- Added `await self.cancel_timeout_handler_tasks()` call to `stop()` method for proper cleanup

### Acceptance Criteria Met
✓ Import TimeoutErrorHandler from common module
✓ Add timeout_error_handler parameter to __init__ with default None
✓ Initialize _timeout_error_handler, _timeout_handler_tasks set, and _timeout_handler_lock
✓ Implement set_timeout_handler(handler) method
✓ Implement async _invoke_timeout_handler(timeout_type, server, error, context) method
✓ Implement async cancel_timeout_handler_tasks() method
✓ Call _invoke_timeout_handler() before raising TimeoutError in request() with descriptive timeout_type and relevant context dict
✓ Handlers executed with proper sync/async handling and task tracking
✓ TimeoutError is always raised after the handler completes; handlers run for side effects only
✓ No AutoReconnectTimeoutHandler added (UDP is connectionless)

### Learnings
- UDP is connectionless so no AutoReconnectTimeoutHandler is needed
- Sync handlers execute synchronously before TimeoutError is re-raised
- Async handlers are tracked as tasks and cleaned up via `cancel_timeout_handler_tasks()`
- The `_invoke_timeout_handler` pattern from TCPClient works identically for UDP
- The context dict includes uri, timeout, server, and key for debugging
- Both sync and async handlers tested successfully

### Status
**IN REVIEW** - All acceptance criteria met; 28 tests pass including 7 UDP e2e tests

---

## Task 7: Update Module Exports

### Completed
- Added `TimeoutErrorHandler` to imports from common module in netaio/__init__.py
- Added `AutoReconnectTimeoutHandler` to imports from client module in netaio/__init__.py
- Verified imports work: `from netaio import AutoReconnectTimeoutHandler, TimeoutErrorHandler`
- All 28 existing tests continue to pass

### Acceptance Criteria Met
✓ TimeoutErrorHandler exported from netaio.__init__
✓ AutoReconnectTimeoutHandler exported from netaio.__init__
✓ Exports accessible via `from netaio import TimeoutErrorHandler, AutoReconnectTimeoutHandler`

### Status
**IN REVIEW** - All acceptance criteria met
