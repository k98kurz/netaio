# Plan: Investigating TCP E2E Test Hang in Python 3.12

## Objective

Identify why `tests/test_tcp_e2e.py::TestTCPE2E::test_e2e` hangs indefinitely (>20s timeout) in Python 3.12 on Linux while completing successfully in ~2 seconds in Python 3.11.

---

## Phase 1: Environment & Baseline Verification

### 1.1 Confirm Environment Setup
- Verify Python versions: `python --version` (3.11), `python3.12 --version` (3.12)
- Activate venvs and confirm dependency parity: `pip list | sort > deps_311.txt` vs `deps_312.txt`
- `diff deps_311.txt deps_312.txt` - note any version differences

### 1.2 Establish Python 3.11 Baseline
```bash
source venv/bin/activate
timeout 20 python -m unittest tests.test_tcp_e2e.TestTCPE2E.test_e2e -v 2>&1 | tee baseline_311.log
```
- Note exact completion time and output
- Verify no warnings or errors
- Capture successful execution pattern

---

## Phase 2: Reproduce Hang in Python 3.12

### 2.1 Confirm the Hang
```bash
source venv-3.12/bin/activate
timeout 20 python -m unittest tests.test_tcp_e2e.TestTCPE2E.test_e2e -v 2>&1 | tee hang_312.log
```

### 2.2 Characterize the Hang
- Check if test times out at exactly 20 seconds
- Look for partial output before hang
- Identify last successful operation logged

---

## Phase 3: Asyncio Debug Mode Investigation

### 3.1 Run with Debug Enabled
```bash
source venv-3.12/bin/activate
PYTHONASYNCIODEBUG=1 timeout 20 python -m unittest tests.test_tcp_e2e.TestTCPE2E.test_e2e -v 2>&1 | tee debug_312.log
```

### 3.2 Analyze Debug Output
- Search for: "Task was destroyed but it is pending"
- Look for "Task is still pending after timeout"
- Check for "Slow callback" warnings (>2s would be suspicious)
- Note any "socket closed" or "connection lost" messages

---

## Phase 4: Targeted Hypothesis Testing

### Hypothesis A: Eager Task Factory (Python 3.12 feature)
```bash
source venv-3.12/bin/activate
PYTHONASYNCIO_TASK_FACTORY=none timeout 20 python -m unittest tests.test_tcp_e2e.TestTCPE2E.test_e2e -v
```
- If test passes: Eager task factory causing race condition

### Hypothesis B: Child Watcher Changes (Linux-specific)
```bash
source venv-3.12/bin/activate
PYTHONDEV=1 timeout 20 python -m unittest tests.test_tcp_e2e.TestTCPE2E.test_e2e -v
```
- Monitor for child watcher-related warnings

### Hypothesis C: Socket Buffering/Flow Control Changes
```bash
source venv-3.12/bin/activate
# Run with strace to see system calls
strace -f -e trace=network,read,write -o strace_312.log timeout 20 python -m unittest tests.test_tcp_e2e.TestTCPE2E.test_e2e
```
- Compare system call patterns between 3.11 and 3.12
- Look for differences in `sendmsg()` vs `send()` usage

### Hypothesis D: Server Task Cancellation Behavior
```bash
source venv-3.12/bin/activate
# Add explicit delay before server cancel to see pattern
PYTHONASYNCIODEBUG=1 timeout 25 python -m unittest tests.test_tcp_e2e.TestTCPE2E.test_e2e -v
```
- Note if server actually stops or hangs on cancellation

---

## Phase 5: Minimal Reproduction Test

### 5.1 Create Simplified Test Script
Create `test_minimal_tcp.py` with only:
- Server start
- Client connect
- Single message exchange
- Cleanup sequence

### 5.2 Run Both Versions
```bash
source venv/bin/activate && timeout 10 python test_minimal_tcp.py
source venv-3.12/bin/activate && timeout 10 python test_minimal_tcp.py
```

### 5.3 Analysis
- If minimal test works: Issue is in specific test sequence
- If minimal test hangs: Issue is in core client/server logic

---

## Phase 6: Code Path Analysis

### 6.1 Inspect Client Code
Read `netaio/client.py` focusing on:
- `connect()` method - connection establishment
- `send()` method - message sending logic
- `receive_once()` method - message receiving logic (most likely hang point)
- `close()` method - cleanup sequence

### 6.2 Inspect Server Code
Read `netaio/server.py` focusing on:
- `start()` method - server startup
- `handle_client()` method - client request handling
- `stop()` method - server shutdown

### 6.3 Identify Async/Await Points
Map all `await` statements in critical path to find blocking points

---

## Phase 7: Comparative Log Analysis

### 7.1 Side-by-Side Comparison
```bash
diff baseline_311.log hang_312.log | head -100
```

### 7.2 Key Comparison Points
- Last matching line before divergence
- Any Python 3.12 specific warnings
- Timing information differences
- Asyncio event sequence differences

---

## Phase 8: Final Report Structure

### 8.1 Executive Summary
- Problem description
- Root cause identified
- Impact assessment

### 8.2 Test Results
| Metric | Python 3.11 | Python 3.12 |
|--------|-------------|--------------|
| Test duration | ~2s | >20s (timeout) |
| Result | PASS | TIMEOUT |

### 8.3 Root Cause Analysis
- Specific Python 3.12 asyncio change
- Code location causing issue
- Why it hangs vs. why it worked in 3.11

### 8.4 Detailed Findings
- Hypothesis test results (pass/fail each)
- Relevant asyncio configuration findings
- System call differences (if applicable)

### 8.5 Recommended Fix
- Code change required
- Python 3.12+ compatibility approach
- Backward compatibility considerations

---

## Deliverables

1. **Log files:** `baseline_311.log`, `hang_312.log`, `debug_312.log`, `strace_312.log`
2. **Comparison analysis:** Diff outputs and divergence points
3. **Minimal reproduction script:** `test_minimal_tcp.py` if needed
4. **Final report:** Markdown document with findings and recommendations
