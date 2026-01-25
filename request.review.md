# Review Request: Task 3 - Fix Race Condition in TCPClient.receive_loop()

## Summary

Fixed a race condition in `TCPClient.request()` where concurrent calls could create multiple `receive_loop` tasks, causing TCP stream corruption. The fix adds task tracking to prevent concurrent receive_loop tasks.

## Changes Made

### netaio/client.py

1. **Added class attribute** (line 50):
   ```python
   _receive_loop_task: asyncio.Task | None
   ```

2. **Initialized attribute in __init__** (line 112):
   ```python
   self._receive_loop_task = None
   ```

3. **Modified receive_loop()** (lines 446-466):
   - Set `self._receive_loop_task = asyncio.current_task()` at start
   - Set `self._receive_loop_task = None` in finally block
   - Wrapped entire method body in try/finally to ensure cleanup

4. **Modified request()** (lines 293-310):
   - Added `was_running` variable to check if receive_loop was already running
   - Only create new task if `not was_running`
   - Only cancel task in finally block if `not was_running`

### implementation_plan.md
Updated Task 3 status from "Pending" to "In Review"

## Acceptance Criteria Met
✓ _receive_loop_task: asyncio.Task | None instance variable added to TCPClient class
✓ receive_loop() sets self._receive_loop_task = asyncio.current_task() at start
✓ receive_loop() sets self._receive_loop_task = None in finally block
✓ request() uses local variable `was_running` to track if receive_loop was already running
✓ request() checks if receive_loop is already running: `was_running = (self._receive_loop_task is not None and not self._receive_loop_task.done())`
✓ request() only creates new task if not already running
✓ request() only cancels task in finally block if it was created during the call (i.e., not was_running)

## Test Results

All 28 tests pass, including all 8 TCP e2e tests:
```
Ran 28 tests in 9.785s
OK
```

## Design Notes

- The `was_running` pattern ensures that if a receive_loop is already active (e.g., from another concurrent request), we don't create a duplicate task
- If receive_loop was already running, we don't cancel it in the finally block since we didn't create it
- The finally block in receive_loop ensures `_receive_loop_task` is always reset to None when the task exits
