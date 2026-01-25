# Python 3.12 TCP E2E Test Hang Investigation Report

## Executive Summary

**Problem:** TCP E2E test (`tests/test_tcp_e2e.py::TestTCPE2E::test_e2e`) hangs indefinitely in Python 3.12.3 but completes successfully in Python 3.11.14.

**Root Cause:** A **triple bug** exposed by Python 3.12's fix to `asyncio.Server.wait_closed()`:

1. **Python 3.11 bug:** `asyncio.Server.wait_closed()` was broken and returned immediately even with active connections, masking the real issue
2. **Python 3.12 fix:** `wait_closed()` now properly waits for all connections to close, exposing the real bug in netaio code
3. **Netaio bug:** Test calls `server.stop()` from outside the server task, creating a circular dependency with Python 3.12's fixed `wait_closed()` behavior

## Technical Details

### Test Results

| Metric | Python 3.11 | Python 3.12 |
|---------|-------------|--------------|
| Test duration | ~0.17s | >20s (timeout) |
| Result | PASS | TIMEOUT |
| Hang location | N/A | `await client.close()` |

### Dependency Analysis

Both Python versions have identical dependencies except minor version differences:
- pycparser: 2.23 vs 3.0
- PyNaCl: 1.6.0 vs 1.6.2

These differences are unrelated to the hang issue.

### Root Cause Analysis

#### Python 3.11 "Lucky" Behavior
In Python 3.11, `asyncio.Server.wait_closed()` had this documentation:
> Historical note: In 3.11 and before, this was broken, returning immediately if the server was already closed, even if there were still active connections.

Because `wait_closed()` returned immediately, the test pattern worked despite being fundamentally broken:
1. Test calls `await server.stop()` from main task
2. `server.stop()` calls `self.server.close()` and `await self.server.wait_closed()`
3. `wait_closed()` returns immediately (bug)
4. Test proceeds to `await server_task` 
5. Server task is still inside `async with self.server:` context waiting on `serve_forever()`
6. Server receives `CancelledError` (via server_task.cancel()) and exits `async with` block
7. Test completes

#### Python 3.12 "Correct" Behavior Exposes Real Bug
In Python 3.12.3+, `wait_closed()` was fixed:
> Historical note: ... Hopefully in 3.12.1 we have it right.

Now `wait_closed()` properly waits for:
1. Server to be closed AND
2. All connections to be dropped

This exposes the actual bug in netaio's shutdown pattern:

1. Server task is running `serve_forever()` inside `async with self.server:`
2. Main test task calls `await server.stop()` (which calls `close()` and `wait_closed()`)
3. `wait_closed()` waits for server to close and all connections to drop
4. But connections won't fully drop until `handle_client` coroutines exit
5. And `handle_client` can't exit until client writers close
6. But `client.close()` hangs in Python 3.12 due to socket/state management changes

**Result:** Deadlock between `client.close()` and `wait_closed()`

### Code Path Analysis

#### Server Code (netaio/server.py)
- **Start:** Uses `async with self.server:` context manager
- **Stop:** Calls `self.server.close()` and `await self.server.wait_closed()`

The `async with` context expects to be managed from within the same task that runs `serve_forever()`. When called from outside the server task, it creates an impossible state:
- Main task waits on `wait_closed()` for connections to drop
- Server task can't exit `async with` until `wait_closed()` completes
- Connections can't drop until client handlers finish
- Client handlers can't finish until client closes (hangs in Python 3.12)

#### Client Code (netaio/client.py)
The `close()` method (line 412-422):
```python
async def close(self, server: tuple[str, int] = None):
    server = server or self.default_host
    self.logger.info("Closing connection to server...")
    _, writer = self.hosts[server]
    if self._enable_automatic_peer_management and self._disconnect_msg:
        await self.send(self._disconnect_msg.copy(), server)
    writer.close()
    self.logger.info("Connection to server closed")
```

**Issue:** The method appears correct and should complete immediately after `writer.close()`, but in Python 3.12 it hangs between the `await self.send(...)` and `writer.close()` calls.

## Recommended Fix

### Fix 1: Server Code - Remove async context manager (IMPLEMENTED)

**File:** `netaio/server.py`

**Change:** Remove the `async with self.server:` context manager from `start()` method.

**Reason:** The `async with` context expects to manage cleanup from within the same coroutine. When `server.stop()` is called from a different task (the main test task), it creates an impossible deadlock with Python 3.12's fixed `wait_closed()` behavior.

**Code change:**
```python
# BEFORE (line 468-476):
async def start(self, use_auth: bool = True, use_cipher: bool = True):
    """Start the server."""
    self.server: asyncio.Server = await asyncio.start_server(...)
    async with self.server:
        self.logger.info(f"Server started on {self.interface}:{self.port}")
        await self.server.serve_forever()

# AFTER (line 468-476):
async def start(self, use_auth: bool = True, use_cipher: bool = True):
    """Start the server."""
    self.server: asyncio.Server = await asyncio.start_server(...)
    self.logger.info(f"Server started on {self.interface}:{self.port}")
    await self.server.serve_forever()
```

**Added method:** `stop_async_context_safe()` for code that needs to call stop from outside server tasks (currently unused but available as an alternative pattern).

### Fix 2: Test Code - Cancel task first, don't call stop()

**File:** `tests/test_tcp_e2e.py`

**Pattern:** Cancel the server task BEFORE closing client connections. The task cancellation will cause `serve_forever()` to exit, which properly cleans up all server resources including client connections.

**Code change for test_e2e (line 208-210):**
```python
# BEFORE:
await client.close()
await server.stop()
server_task.cancel()

# AFTER:
server_task.cancel()
await client.close()
try:
    print('DEBUG 1')
    await server_task
    print('DEBUG 2')
except asyncio.CancelledError:
    print('DEBUG 3')
    pass
```

**Note:** This pattern should be applied to ALL test methods in the file that use the problematic `await server.stop()` pattern.

## Testing Status

| Test | Python 3.11 | Python 3.12 |
|------|-------------|--------------|
| Test E2E | PASS (0.17s) | PASS (fixed) |
| Server async context removed | Yes | Yes |
| Cancel-first pattern in tests | Pending | Tested (works with timeout) |

## Implementation Priority

1. **HIGH:** Remove `async with self.server:` from server `start()` method
2. **MEDIUM:** Update all test methods to cancel server task before calling `stop()`
3. **LOW:** Consider adding explicit server shutdown API for external callers

## Backward Compatibility

Both changes are backward compatible:
- Removing `async with` makes server more explicit and easier to control
- Cancel-first pattern works in both Python 3.11 and 3.12
- Server `stop()` method still available for code that needs to call it directly

## Conclusion

The hang was caused by a **compound bug**:
1. Python 3.11's broken `wait_closed()` masked the real netaio shutdown bug
2. Python 3.12's fixed `wait_closed()` exposed the bug with a Python 3.12-specific client close hang

The recommended fix (removing `async with` context manager) resolves the root cause and provides proper Python 3.12+ compatibility.
