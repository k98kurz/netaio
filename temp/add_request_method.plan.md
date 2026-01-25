# Plan for Adding `request` Method to TCPClient

## Overview
Add an async `request` method to the `TCPClient` class using the `@self.once()` decorator syntax. The method will:
- Send a `REQUEST_URI` message to a server
- Register an ephemeral handler using `@self.once()` for the expected `RESPOND_URI` response
- Wait for the response with a configurable timeout (default 10 seconds)
- Return the response message or raise `TimeoutError` on timeout

## Implementation Details

**Location:** Add the method to `/home/sithlord/Documents/repos/netaio/netaio/client.py` after the `send` method (around line 263)

**Method Signature:**
```python
async def request(
    self,
    uri: bytes,
    timeout: float = 10.0,
    server: tuple[str, int] = None,
    use_auth: bool = True,
    use_cipher: bool = True,
    auth_plugin: AuthPluginProtocol = None,
    cipher_plugin: CipherPluginProtocol = None
) -> MessageProtocol:
```

**Implementation Steps:**
1. Create an empty list `result = []` to capture the response message
2. Define an ephemeral handler function using `@self.once()` decorator:
   ```python
   @self.once((self.message_type_class.RESPOND_URI, uri), auth_plugin, cipher_plugin)
   def handle_response(message: MessageProtocol, writer: asyncio.StreamWriter):
       result.append(message)
       return None
   ```
3. Create a `REQUEST_URI` message:
   - Body: `self.body_class.prepare(content=b'', uri=uri)`
   - Message: `self.message_class.prepare(body, self.message_type_class.REQUEST_URI)`
4. Send the message using `await self.send(...)`
5. Start a timer and enter a polling loop:
   - Record start time: `deadline = asyncio.get_event_loop().time() + timeout`
   - Loop: `while not len(result) and asyncio.get_event_loop().time() < deadline`
   - Sleep in small intervals: `await asyncio.sleep(0.01)` to avoid busy waiting
6. On timeout:
   - Remove the ephemeral handler using `self.remove_ephemeral_handler((self.message_type_class.RESPOND_URI, uri))`
   - Raise `TimeoutError(f"Request for URI {uri.decode('utf-8', errors='replace')} timed out after {timeout}s")`
7. On success:
   - Return `result[0]` (the received message)

**Key Design Decisions:**
- Uses `@self.once()` decorator syntax as preferred (more maintainable/readable)
- Handler key is `(MessageType.RESPOND_URI, uri)` to match only responses for this specific URI
- Default timeout of 10 seconds as specified
- Uses `asyncio.get_event_loop().time()` for accurate timeout handling (monotonic clock)
- Small sleep interval (0.01s) in polling loop to avoid CPU busy-waiting
- Assumes `receive_loop()` is already running in the background to process incoming messages
- Includes the same optional parameters as `send()` method for consistency

**Why the Decorator Approach is Better:**
- More concise and readable - the intent ("one-time handler") is immediately visible
- Follows existing patterns in the codebase (see `manage_peers_automatically` at client.py:545)
- No need to manually call `add_ephemeral_handler` and track the key separately
- The registration happens at function definition, reducing the chance of bugs

**Error Handling:**
- TimeoutError raised if no response received within timeout period
- Ephemeral handler cleanup on timeout ensures no handlers leak
- Any exceptions during message sending or handling will propagate normally

**Dependencies:**
- Requires `MessageType.RESPOND_URI` to exist (already defined in common.py:339)
- Requires `MessageType.REQUEST_URI` to exist (already defined in common.py:338)
- Requires existing `send()`, `remove_ephemeral_handler()` methods
