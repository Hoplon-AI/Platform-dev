# Silver Processor Dependency Injection

## Overview

The silver processor has been refactored to support **dependency injection** for database connections, making it testable and consistent with the rest of the codebase.

## Changes Made

### Before (No Dependency Injection)
```python
async def process_features_to_silver(event: Dict[str, Any]) -> Dict[str, Any]:
    # Direct connection creation - not mockable
    conn = await _db_connect()
    try:
        # ... processing ...
    finally:
        await conn.close()
```

**Problems:**
- ❌ Database connection created internally - not mockable
- ❌ Tests had to mock internal `_db_connect()` function
- ❌ Not consistent with rest of codebase (uses `DatabasePool`)
- ❌ Hard to test with different database configurations

### After (With Dependency Injection)
```python
async def process_features_to_silver(
    event: Dict[str, Any],
    *,
    db_conn: Optional[asyncpg.Connection] = None,
    db_pool: Optional[asyncpg.Pool] = None,
    upload_service: Optional[UploadService] = None,
) -> Dict[str, Any]:
    # Connection obtained via dependency injection
    conn, should_release = await _get_db_connection(conn=db_conn, pool=db_pool)
    try:
        # ... processing ...
    finally:
        # Proper cleanup based on connection source
        if should_release:
            await pool.release(conn)
        elif should_close_conn:
            await conn.close()
```

**Benefits:**
- ✅ Database connection can be injected (mockable)
- ✅ Supports connection pool injection
- ✅ Falls back to `DatabasePool` (like rest of codebase)
- ✅ Still works in Lambda (creates direct connection if pool unavailable)
- ✅ Tests can inject mock connections directly

## Usage

### Production Usage (Default)
```python
# Uses DatabasePool (if initialized) or creates direct connection
result = await process_features_to_silver(event)
```

### With Connection Pool Injection
```python
from backend.core.database.db_pool import DatabasePool

pool = DatabasePool.get_pool()
result = await process_features_to_silver(event, db_pool=pool)
```

### With Direct Connection Injection
```python
conn = await asyncpg.connect(...)
result = await process_features_to_silver(event, db_conn=conn)
# Note: Connection won't be closed automatically if injected
```

### Testing with Mock Connection
```python
from unittest.mock import AsyncMock

mock_conn = AsyncMock()
mock_conn.execute = AsyncMock()

result = await process_features_to_silver(
    event,
    db_conn=mock_conn,  # Inject mock connection
    upload_service=mock_upload_service
)
```

## Connection Management

The `_get_db_connection()` function handles connection lifecycle:

1. **Injected connection** (`db_conn` provided):
   - Uses provided connection
   - Does NOT close or release it (caller responsible)

2. **Injected pool** (`db_pool` provided):
   - Acquires connection from pool
   - Returns `(conn, True)` - should be released back to pool

3. **DatabasePool** (default, if initialized):
   - Acquires from global `DatabasePool`
   - Returns `(conn, True)` - should be released back to pool

4. **Direct connection** (fallback for Lambda):
   - Creates new connection via `asyncpg.connect()`
   - Returns `(conn, False)` - should be closed

## Testing

### Before (Mocking Internal Function)
```python
with patch("backend.workers.silver_processor._db_connect") as mock_db_connect:
    mock_conn = AsyncMock()
    mock_db_connect.return_value = mock_conn
    result = await process_features_to_silver(event)
```

### After (Dependency Injection)
```python
mock_conn = AsyncMock()
mock_conn.execute = AsyncMock()

result = await process_features_to_silver(
    event,
    db_conn=mock_conn  # Direct injection - cleaner!
)
```

## Consistency with Codebase

The silver processor now follows the same patterns as the rest of the codebase:

- **DatabasePool**: Uses `DatabasePool` as default (like `audit_logger`, `lineage_tracker`)
- **Dependency Injection**: Accepts connections/pools as parameters (like `IDatabaseAdapter` pattern)
- **Testability**: Can inject mocks directly (like other services)

## Backward Compatibility

The `handler()` function maintains backward compatibility:
```python
def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Lambda-compatible synchronous handler."""
    return asyncio.run(process_features_to_silver(event))
```

This ensures existing Lambda deployments continue to work without changes.
