# Agent Guidelines for netaio

## Build, Test, and Lint Commands

### Running Tests
```bash
# Pre-requisite for all tests is loading the environment
source venv/bin/activate

# Run all tests
python -m unittest discover -s tests

# Run a single test file
python tests/test_misc.py
python tests/test_plugins.py
python tests/test_tcp_e2e.py
python tests/test_udp_e2e.py

# Run individual test class
python -m unittest tests.test_misc.TestMisc

# Run specific test method
python -m unittest tests.test_misc.TestMisc.test_message_type_class_monkey_patch
```

### Building
Do not attempt to build the project.

### Code Quality
No explicit linting/formatting configuration currently exists. Follow the style
    guidelines below.

---

## Code Style Guidelines

### Python Version
- Minimum: Python 3.10+
- Use Python 3.10+ built-in types (PEP 604 style)

### Line Lengths
- Soft-max line length of 80 chars for normal code and 72 chars for docstrings
- Hard-max line length of 85 chars for normal code and 76 chars for docstrings
- Docstrings should look like the following:
```python
def something():
    """This is the docstring for something(). It will wrap around onto
        the next line indented in one additional tab length, then it
        will end with the closing triple quotes on a new line.
    """
    ...
```
- If a piece of code calling a function will be too long, start the args on a new
    line:
```python
        # some indented code
        thing = some_class.some_method(
            "this is the first thing" if some_param > some_threshold else
            "this is the alternate",
            123
        )
```
- If a print statement is too long, break apart the string:
```python
        # some indented code
        print(
            "This is a very long print statement with f-string: "
            f"{some_dict['some_key'] if 'some_key' in some_dict else 'nope'}"
        )
```
- If a conditional is too long, use a backslash to continue on the next line:
```python
        # some indented code
        if something.value < threshold and something_else in whatever \
            and one_more_condition:
            ...
```
- If a function/method signature is too long, format as follows:
```python
        def some_method(
                self, first_param: str, second_param: int,
                third_param: dict[str, Any]|None = None
            ) -> list[str]:
            """Brief docstring."""
            ...
```

### Type Hints
- Use type hints on all functions, methods, and class variables
- Use `type[SomeType]` for class references (not `Type[SomeType]`)
- Use `|` for union types (Python 3.10+), e.g., `str | bytes` instead of
    `Union[str, bytes]`
- Use built-in generics: `list[str]` instead of `List[str]`, `dict[str, Any]`
    instead of `Dict[str, Any]`
- Import from `typing` only for special cases: `Any`, `cast`, `NoReturn`
- Use `typing.Protocol` with `@runtime_checkable` decorator for interfaces

### Imports
- Always start with `from __future__ import annotations` for forward compatibility
- **All `from x import y` style imports first, alphabetized**
- **All `import x` style imports last, alphabetized**
- Group by: standard library, third-party (with fallback handling for optional
    deps), then local

Example:
```python
# From imports (alphabetized)
from argparse import ArgumentParser
from dataclasses import dataclass
from typing import Any, cast

# Optional third-party with fallback
try:
    from tapescript import Script, make_single_sig_lock
    from nacl.public import PrivateKey, PublicKey
except ImportError:
    Script = None
    make_single_sig_lock = None
    PrivateKey = None
    PublicKey = None

# Local from imports (alphabetized)
from .common import Message
from .asymmetric import TapescriptAuthPlugin, X25519CipherPlugin

# Bare imports (alphabetized)
import asyncio
import logging
```

### Documentation Style
- **Concise docstrings preferred** - maximum 6 lines, paragraph format
- Describe purpose and critical details only
- **No** line-by-line parameter descriptions for non-`__init__` methods
(Args:, Returns:, Raises: sections)
- **No** lengthy usage examples or novels
- Just 1-6 lines (soft-max 72 chars per line) with most important information
- Lines beyond the first are indented
- The final triple quote goes on its own line

Example:
```python
def prepare(
        body: BodyProtocol, message_type: MessageType,
        auth_data: AuthFields|None = None
    ) -> Message:
    """Create message from body, type, and optional auth fields."""
```

### Classes and Data Structures
- Use `@dataclass` for simple data containers
- Type annotate all class variables
- Use `@classmethod` for factory methods: `decode`, `prepare`, `from_*`
- Use `@staticmethod` for utility methods independent of instance state
- Docstrings describe purpose (follow Documentation Style guidelines above)

### Naming Conventions
- Classes: `PascalCase` (e.g., `TCPServer`, `HMACAuthPlugin`)
- Functions/methods: `snake_case` (e.g., `keys_extractor`, `make_error_response`)
- Constants/enum values: `UPPER_SNAKE_CASE` (e.g., `MessageType.REQUEST_URI`)
- Private members: single underscore prefix (e.g., `_internal_method`)

### Error Handling
- Raise `ValueError` for invalid inputs with descriptive messages
- Use logging via `self.logger.debug()`, `.info()`, `.warning()`, `.error()`
- Default loggers available: `default_server_logger`, `default_client_logger`,
    `default_node_logger`

### Async/Await
- All async methods use `async def`
- Use `asyncio.run()` to execute async code from sync context
- Use `asyncio.create_task()` for concurrent execution
- Use `await asyncio.sleep()` for delays

### Testing
- Use `unittest.TestCase` as base class
- Define random port as class attribute: `PORT = randint(10000, 65535)`
- Use `setUpClass()` for class-level setup (e.g., logging configuration)
- Run async tests with `asyncio.run()` wrapper functions
- Test files import netaio via `from context import netaio, asymmetric`

### Protocol Interfaces
- Define protocols for plugins: `AuthPluginProtocol`, `CipherPluginProtocol`,
    `PeerPluginProtocol`
- Implement required methods: `make`, `check`, `encrypt`, `decrypt`, `encode`,
    `decode`
- Plugin `__init__` accepts `config: dict` parameter
- Add static method `is_peer_specific() -> bool` for optimization

### Message and Data Flow
- Messages composed of: `Header`, `AuthFields`, `Body`
- Use `Message.prepare(body, message_type, auth_data)` for construction
- Use `Message.decode(data)` and `Message.encode()` for serialization
- Checksum validation via `crc32(body.encode())`
- Max message size: 2**16 bytes (64KB)

### File Organization
- Main source: `netaio/*.py` (common, server, client, node, auth, cipher,
    crypto)
- Tests: `tests/test_*.py` with `context.py` for path setup
- Entry point: `netaio/__init__.py` exports public API
