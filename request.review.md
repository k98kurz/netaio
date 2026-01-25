# Request Review - Task 6: Add Timeout Handler Infrastructure to UDPNode

## Summary

Implemented timeout error handler infrastructure in `UDPNode` class, matching the pattern already used in `TCPClient`. This allows users to register custom handlers that are invoked when a `request()` call times out.

## Changes Made

### netaio/node.py
- Added `TimeoutErrorHandler` to imports from common module (line 21)
- Added `Coroutine` to typing imports (line 28)
- Added class attributes:
  - `timeout_error_handler: TimeoutErrorHandler` (line 62)
  - `_timeout_handler_tasks: set[asyncio.Task]` (line 63)
  - `_timeout_handler_lock: asyncio.Lock` (line 64)
- Added `timeout_error_handler` parameter to `__init__` with default None (line 86)
- Updated docstring to describe `timeout_error_handler` parameter (lines 119-122)
- Initialized `self.timeout_error_handler = timeout_error_handler` in `__init__` (line 147)
- Initialized `self._timeout_handler_tasks = set()` in `__init__` (line 153)
- Initialized `self._timeout_handler_lock = asyncio.Lock()` in `__init__` (line 154)
- Implemented `set_timeout_handler(handler)` method (lines 585-586)
- Implemented `async _invoke_timeout_handler(timeout_type, server, error, context)` method (lines 589-605)
  - Checks if handler is None and returns early if so
  - Invokes handler with node, timeout_type, server, error, and context
  - For async handlers, creates tracked task and adds to `_timeout_handler_tasks`
  - Sync handlers execute synchronously before TimeoutError is re-raised
- Implemented `async cancel_timeout_handler_tasks()` method (lines 608-613)
  - Uses `_timeout_handler_lock` for thread safety
  - Cancels all running timeout handler tasks
  - Waits for tasks to complete with `return_exceptions=True`
  - Clears the task set
- Modified `request()` method to call `_invoke_timeout_handler()` before raising TimeoutError (lines 579-582)
  - Creates descriptive context dict with uri, timeout, server, and key
  - Passes 'request_timeout' as timeout_type
  - Always raises TimeoutError after handler completes
- Added `await self.cancel_timeout_handler_tasks()` call to `stop()` method (line 1012) for proper cleanup

## Testing

- All 28 existing tests pass (including 7 UDP e2e tests)
- Created test script to verify:
  - Async timeout handler is called with correct parameters
  - Sync timeout handler works correctly
  - Default behavior (no handler) works correctly
  - TimeoutError is always raised after handler completes

## Acceptance Criteria Met

- ✓ Import TimeoutErrorHandler from common module
- ✓ Add timeout_error_handler parameter to __init__ with default None
- ✓ Initialize _timeout_error_handler, _timeout_handler_tasks set, and _timeout_handler_lock
- ✓ Implement set_timeout_handler(handler) method
- ✓ Implement async _invoke_timeout_handler(timeout_type, server, error, context) method
- ✓ Implement async cancel_timeout_handler_tasks() method
- ✓ Call _invoke_timeout_handler() before raising TimeoutError in request() with descriptive timeout_type and relevant context dict
- ✓ Handlers executed with proper sync/async handling and task tracking
- ✓ TimeoutError is always raised after the handler completes; handlers run for side effects only
- ✓ No AutoReconnectTimeoutHandler added (UDP is connectionless)

## Remaining Work

Task 2 remains:
- Task 2: Fix Type Hints for keys_extractor
