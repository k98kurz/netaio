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
No explicit linting/formatting configuration currently exists. Follow the style guidelines below.

---

## Code Style Guidelines

### Imports
- Always start with `from __future__ import annotations` for forward compatibility
- Group imports: standard library → third-party → local (netaio) modules
- Use explicit imports from typing instead of `*` (e.g., `from typing import Callable, Protocol`)

### Type Hints
- Use type hints on all functions, methods, and class variables
- Use `type[SomeType]` for class references (not `Type[SomeType]`)
- Use `|` for union types (Python 3.10+), e.g., `str | bytes` instead of `Union[str, bytes]`
- Use `typing.Protocol` with `@runtime_checkable` decorator for interfaces

### Classes and Data Structures
- Use `@dataclass` for simple data containers
- Type annotate all class variables
- Use `@classmethod` for factory methods: `decode`, `prepare`, `from_*`
- Use `@staticmethod` for utility methods independent of instance state
- Docstrings describe parameters and return values

### Naming Conventions
- Classes: `PascalCase` (e.g., `TCPServer`, `HMACAuthPlugin`)
- Functions/methods: `snake_case` (e.g., `keys_extractor`, `make_error_response`)
- Constants/enum values: `UPPER_SNAKE_CASE` (e.g., `MessageType.REQUEST_URI`)
- Private members: single underscore prefix (e.g., `_internal_method`)

### Error Handling
- Raise `ValueError` for invalid inputs with descriptive messages
- Use logging via `self.logger.debug()`, `.info()`, `.warning()`, `.error()`
- Default loggers available: `default_server_logger`, `default_client_logger`, `default_node_logger`

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
- Define protocols for plugins: `AuthPluginProtocol`, `CipherPluginProtocol`, `PeerPluginProtocol`
- Implement required methods: `make`, `check`, `encrypt`, `decrypt`, `encode`, `decode`
- Plugin `__init__` accepts `config: dict` parameter
- Add static method `is_peer_specific() -> bool` for optimization

### Message and Data Flow
- Messages composed of: `Header`, `AuthFields`, `Body`
- Use `Message.prepare(body, message_type, auth_data)` for construction
- Use `Message.decode(data)` and `Message.encode()` for serialization
- Checksum validation via `crc32(body.encode())`
- Max message size: 2**16 bytes (64KB)

### File Organization
- Main source: `netaio/*.py` (common, server, client, node, auth, cipher, crypto)
- Tests: `tests/test_*.py` with `context.py` for path setup
- Entry point: `netaio/__init__.py` exports public API

### Miscellaneous
- Try to keep lines close to 80 chars maximum
- Split up calls, statements, etc into multi-line where necessary, following existing style conventions
