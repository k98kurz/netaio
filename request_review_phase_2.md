# Phase 2 - Message/Body/Header Classes Alignment Review

## Status: Complete

## Summary

Aligned concrete class implementations (Header, Message, Body, AuthFields) with updated protocols to support optional message type factories and proper type conformance.

## Changes Made

### 1. Header.decode() (netaio/common.py:436-466)
- Added `message_type_factory: Callable[[int], MessageTypeVar]|None = None` parameter
- Added type cast for `message_type_class` factory assignment
- Added `# type: ignore[arg-type]` for `message_type_factory()` call

### 2. Header.message_type (netaio/common.py:419)
- Changed from `MessageType` to `IntEnum` for broader compatibility
- Dataclass fields cannot use TypeVar directly

### 3. Message.decode() (netaio/common.py:560-585)
- Added `message_type_factory: Callable[[int], MessageTypeVar]|None = None` parameter
- Passes factory to `Header.decode()` call

### 4. Message.prepare() (netaio/common.py:600-617)
- Changed `message_type` from `MessageType|IntEnum` to `MessageTypeVar`
- Changed `auth_data` from `AuthFields|None` to `AuthFieldsProtocol|None`
- Added `# type: ignore[arg-type]` for Header construction with concrete types

### 5. Message.body (netaio/common.py:554)
- Changed from `Body` to `BodyProtocol` for protocol compatibility

## Test Results

✅ All 28 tests pass
✅ Runtime behavior unchanged (only type hints modified)

## Linter Results

| Linter  | Phase 1 | Phase 2 | Change |
|---------|-----------|-----------|--------|
| Mypy    | 276       | 273       | -3     |
| Pyright  | 447       | 439       | -8     |
| **Total**| **723**  | **712**   | **-11** |

## Why Reduction Was Lower Than Expected

Expected: ~50-80 errors reduced
Actual: 11 errors reduced

### Root Causes:

1. **TypeVar Limitations in Dataclasses**
   - Dataclass fields cannot use TypeVar directly
   - Must use concrete types like `IntEnum` or `Body`
   - This creates unavoidable type mismatches with protocols that use TypeVar

2. **Protocol vs Concrete Type Mismatches**
   - Protocol methods return `MessageProtocol`, concrete methods return `Message`
   - Protocol accepts `AuthFieldsProtocol|None`, concrete accepts `AuthFields|None`
   - These require `# type: ignore` annotations as they're unavoidable without breaking changes

3. **Most Errors in Implementation Files**
   - Remaining errors are predominantly in server.py, client.py, node.py
   - These will be addressed in Phases 3-5 (TCPServer, TCPClient, UDPNode fixes)
   - Phase 2 focused only on common.py message classes

4. **Type Inference Complexity**
   - TypeVar bound to IntEnum creates complex type inference scenarios
   - Linters struggle with generic message types across protocol/concrete boundaries

## Learnings

1. **TypeVar Usage Patterns**
   - Use TypeVar in protocol method signatures for genericity
   - Use concrete types in dataclass fields
   - Cast with `cast(Callable[[int], MessageTypeVar], cls.some_class)` when needed

2. **Protocol Conformance Trade-offs**
   - Concrete implementations may not perfectly match protocol types
   - Use `# type: ignore[arg-type]` with comments where unavoidable
   - Document rationale in verification docs

3. **Phase Dependency Chain**
   - Phase 2 established foundation (protocols aligned with concrete types)
   - Phases 3-5 will use this foundation to fix implementation-level issues
   - Error reduction is cumulative across phases

## Next Steps

**Phase 3 - TCPServer Implementation Fixes** (expected ~100-150 error reduction)

This phase will address:
- Type annotations for optional plugin fields
- None checks before plugin method access
- Handler method signatures
- Implementation-specific type issues

## Verification

See `findings/phase_2_verification.md` for detailed analysis.
