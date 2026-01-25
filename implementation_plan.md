# Implementation Plan

## Tasks

### TASK 6: Add Timeout Handler Infrastructure to UDPNode (CRITICAL)

- Status: Done
- Description: Implement timeout error handler support in UDPNode class (same as TCPClient)
- **Priority**: CRITICAL - implementation completely missing
- Acceptance Criteria:
    - Import TimeoutErrorHandler from common module
    - Add timeout_error_handler parameter to __init__ with default None
    - Initialize _timeout_error_handler, _timeout_handler_tasks set, and _timeout_handler_lock
    - Implement set_timeout_handler(handler) method
    - Implement async _invoke_timeout_handler(timeout_type, server, error, context) method
    - Implement async cancel_timeout_handler_tasks() method
    - Call _invoke_timeout_handler() before raising TimeoutError in request() with descriptive timeout_type and relevant context dict
    - Handlers executed with proper sync/async handling and task tracking
    - **Important**: TimeoutError is always raised after the handler completes; handlers run for side effects only
    - No AutoReconnectTimeoutHandler added (UDP is connectionless)

### TASK 2: Fix Type Hints for keys_extractor

- Status: Done
- Description: Update keys_extractor type hints to accept tuple[str, int] | None as second parameter
- **Priority**: HIGH - type annotations are incorrect despite function signature being correct
- Acceptance Criteria:
    - NetworkNodeProtocol.extract_keys property in common.py (line 240) type changed from `Callable[[MessageProtocol], list[Hashable]]` to `Callable[[MessageProtocol, tuple[str, int] | None], list[Hashable]]`
    - TCPClient class attribute in netaio/client.py (line 44) updated
    - TCPClient __init__ parameter in netaio/client.py (line 63) updated
    - UDPNode class attribute in netaio/node.py (line 53) updated
    - UDPNode __init__ parameter in netaio/node.py (line 75) updated

### TASK 4: Fix Timeout Handler Invocation Bug

- Status: Done
- Description: Fix the unreachable timeout handler code in TCPClient.request()
- Acceptance Criteria:
    - Wrap `await asyncio.wait_for(event.wait(), timeout=timeout)` in try/except block
    - Catch `asyncio.TimeoutError` exception
    - Convert to `TimeoutError` and call `_invoke_timeout_handler()` before raising
    - Ensure timeout handler is actually invoked when timeout occurs
    - All existing tests continue to pass

### TASK 5: Implement AutoReconnectTimeoutHandler for TCPClient

- Status: Done
- Description: Create bundled auto-reconnect timeout handler at bottom of client.py
- Acceptance Criteria:
    - Class defined at bottom of netaio/client.py
    - Constructor accepts connect_timeout, max_retries, delay, on_reconnect parameters
    - __call__ method implements async reconnect logic with retry loop
    - Attempts to reconnect and invokes on_reconnect callback on success
    - Returns None (the TimeoutError is always raised by request() after handler completes)
    - Handler runs for side effects: prepares connection for subsequent requests after the current one fails
    - Proper error handling and logging throughout

### TASK 7: Update Module Exports

- Status: Done
- Description: Export new types and handlers from netaio/__init__.py
- Acceptance Criteria:
    - TimeoutErrorHandler exported from netaio.__init__
    - AutoReconnectTimeoutHandler exported from netaio.__init__
    - Exports accessible via `from netaio import TimeoutErrorHandler, AutoReconnectTimeoutHandler`

## Dependencies

- **Task 6 (CRITICAL)** is DONE - UDPNode timeout handler infrastructure completed
- **Task 2 (HIGH)** should be completed next - type annotations are still incorrect
- **Task 4** (Critical Bug Fix) is DONE - blocking issue resolved
- **Task 1** (TimeoutErrorHandler type) is DONE
- **Task 3** (Race condition fix) is DONE
- **Task 5** (AutoReconnectTimeoutHandler) is DONE
- **Task 7** (Exports) is DONE

## Notes

- Task 1 is COMPLETE (TimeoutErrorHandler type definition)
- Task 2 is COMPLETE (Type hint fixes - FIXED all 5 locations)
- Task 3 is COMPLETE (Race condition fix)
- Task 4 is COMPLETE (Timeout handler invocation bug fixed)
- Task 5 is COMPLETE (AutoReconnectTimeoutHandler implementation)
- Task 6 is COMPLETE (UDPNode timeout handler infrastructure)
- Task 7 is COMPLETE (Module exports updated)
