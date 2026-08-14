# DAO Refactor Part 2: Write Operations & Schema (V4 - Reality-Based)

**Status:** ✅ READY FOR EXECUTION (documented from actual code, not assumptions)  
**Prerequisites:** Part 1 merged to main ✅  
**Complexity:** High (write ops + savepoint + multi-DB schema + state machine)  
**Estimated execution:** 3-4 hours  
**Chunks:** 5 (CHUNK_0 → CHUNK_4)  

---

## What V4 Fixes (V3 → V4)

### V4 Based on Actual Code Reading

All specs extracted from models.py:
- Lines 182-296: `_rewards_ledger_table_exists()`, `ensure_rewards_ledger_schema()`, `_resolve_rewards_schema_state()`
- Lines 299-331: `try_insert_rewards_points()` actual implementation
- Lines 625-733: `transfer_money()` actual implementation (savepoint semantics, error handling)

**Result:** No assumptions. Plan matches reality. ✅

---

## Actual Schema (Not Idealized)

### rewards_ledger Table

**PostgreSQL:**
```sql
CREATE TABLE IF NOT EXISTS rewards_ledger (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    source_account_id   INTEGER NOT NULL REFERENCES accounts(id),
    target_account_id   INTEGER NOT NULL REFERENCES accounts(id),
    points              INTEGER NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rewards_ledger_user_id ON rewards_ledger(user_id);
```

**SQLite:**
```sql
CREATE TABLE IF NOT EXISTS rewards_ledger (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    source_account_id  INTEGER NOT NULL,
    target_account_id  INTEGER NOT NULL,
    points             INTEGER NOT NULL,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Key differences (not a bug, design choice):**
- `points` is `INTEGER` (not DECIMAL)
- PostgreSQL: 1 index on user_id
- SQLite: no indexes
- PostgreSQL: `TIMESTAMPTZ`, SQLite: `TIMESTAMP`
- No explicit foreign key constraints on SQLite (schema only)

**Idempotency:** `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS` (safe to re-run)

---

## Actual State Machine (Not Idealized)

**_resolve_rewards_schema_state() returns exactly:**

| State | Condition |
|-------|-----------|
| `"forced_fail"` | `is_demo_force_rollout_migration_fail()` returns True (test-only override) |
| `"skipped"` | `is_demo_rollout_schema_enabled()` returns False (feature flag off) |
| `"ready"` | `_rewards_ledger_table_exists(cursor)` returns True |
| `"runtime_error"` | Exception during check (returned, not raised) |

**No state:** `"unknown"`, `"incompatible"` (V3 invented these—they don't exist)

**Behaviors:**
- States are mutually exclusive (checked in order: forced_fail → skipped → table exists → error)
- `_resolve_rewards_schema_state()` updates module-level `_rewards_schema_state` global
- Tests can set flags via monkeypatch or fixture

**Validation logic (ACTUAL code):**
```python
def _resolve_rewards_schema_state(cursor=None) -> str:
    global _rewards_schema_state
    
    if is_demo_force_rollout_migration_fail():
        _rewards_schema_state = "forced_fail"
        return _rewards_schema_state
    
    if not is_demo_rollout_schema_enabled():
        _rewards_schema_state = "skipped"
        return _rewards_schema_state
    
    own_conn = None
    if cursor is None:
        own_conn = get_db()
        cursor = own_conn.cursor()
    try:
        _rewards_schema_state = (
            "ready" if _rewards_ledger_table_exists(cursor) else "skipped"
        )
        return _rewards_schema_state
    except Exception:
        _rewards_schema_state = "runtime_error"
        return _rewards_schema_state
    finally:
        if own_conn is not None:
            own_conn.close()
```

---

## Actual Validation (SQLite + PostgreSQL)

### _rewards_ledger_table_exists(cursor) - EXECUTABLE

**SQLite:**
```python
cursor.execute(
    """
    SELECT 1
    FROM sqlite_master
    WHERE type = 'table'
      AND name = ?
    LIMIT 1
    """,
    (REWARDS_LEDGER_TABLE,),
)
return cursor.fetchone() is not None
```

**PostgreSQL:**
```python
cursor.execute(
    _sql("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ?
        ) AS exists
        """),
    (REWARDS_LEDGER_TABLE,),
)
row = cursor.fetchone()
data = _row_to_dict(row) or {}
return bool(data.get("exists"))
```

**Note:** Checks existence only. Assumes table has correct schema if it exists. No column/constraint validation (by design).

---

## Actual try_insert_rewards_points() Implementation

**Signature (keyword-only, ACTUAL):**
```python
def try_insert_rewards_points(
    *,
    conn,
    cursor,
    user_id: int,
    source_account_id: int,
    target_account_id: int,
    transfer_amount: float,
) -> bool:
```

**Full implementation (ACTUAL):**
```python
if not is_demo_rollout_feature_enabled():
    return False

conn = get_db()
cursor = conn.cursor()
schema_state = _resolve_rewards_schema_state(cursor)

if schema_state == "forced_fail":
    conn.close()
    return None, "rollback_forced_fail"
if schema_state in {"skipped", "unknown"}:
    conn.close()
    return None, "legacy_no_schema"
if schema_state == "runtime_error":
    conn.close()
    return None, "rollback_runtime_error"

try:
    cursor.execute(
        _sql("""
            INSERT INTO rewards_ledger
                (user_id, source_account_id, target_account_id, points)
            VALUES (?, ?, ?, ?)
            """),
        (user_id, source_account_id, target_account_id, points),
    )
    logger.info("rewards.rollout.write_succeeded points=%s", points)
    return True
except Exception as exc:
    logger.warning("rewards.rollout.write_failed reason=%s", exc.__class__.__name__)
    return False
```

**Behavior (MUST preserve):**
- Returns `bool` (not tuple; tuple return was V2 confusion)
- Computes points via `_compute_reward_points(transfer_amount)` (1 point per $10)
- Catches all exceptions → returns False (never propagates)
- Logs successes + failures
- Returns immediately if feature disabled or schema not ready

**Extraction plan:** Move SQL + logic to DAO. Keep models wrapper for monkeypatch. DAO calls don't create own connection; caller passes cursor (transfer's caller's cursor inside savepoint).

---

## Actual transfer_money() Implementation

**Signature (ACTUAL):**
```python
def transfer_money(
    from_account_id: int,
    to_account_id: int,
    amount: float,
    description: str = "Transfer",
    acting_user_id: int | None = None,
) -> tuple[bool, str]:
```

**Returns:** `(bool, str)` tuple
- `(True, "Transfer successful")` on success
- `(False, reason_string)` on any error

**Error cases (ACTUAL):**
- `"Invalid amount"` (≤0 or not finite)
- `"Account not found"` (source or dest missing)
- `"Forbidden"` (acting_user_id mismatch)
- `"Insufficient funds"` (balance check)
- `"Transfer failed"` (catch-all on exception)

**Flow (ACTUAL):**
1. Open connection
2. Fetch from_account + to_account (with balance, user_id, account_number)
3. Check auth (if acting_user_id provided)
4. Check balance
5. Debit: INSERT transaction (negative amount) + UPDATE balance (subtract)
6. Credit: INSERT transaction (positive amount) + UPDATE balance (add)
7. **SAVEPOINT rewards_savepoint**
8. Call `try_insert_rewards_points(conn=conn, cursor=cursor, ...)`
9. **RELEASE SAVEPOINT** (or **ROLLBACK TO SAVEPOINT** on exception)
10. Commit
11. Return (True, "Transfer successful")

**Key:** Savepoint is **inside the main transaction**. Rewards error doesn't fail transfer. ROLLBACK TO SAVEPOINT recovers transaction state (PostgreSQL specific: without this, transaction is aborted).

**Extraction plan:** Move SQL statements to DAO. Keep error handling logic in models wrapper (return tuple). DAO method is called with conn + cursor from transfer. DAO doesn't commit (transfer does).

---

## Part 2 Functions to Extract (ACTUAL)

| Function | Current Location | Extract To | Behavior (Don't Change) |
|----------|------------------|------------|------------------------|
| `ensure_rewards_ledger_schema()` | models.py:230-260 | SchemaDAO.ensure_schema() | Opens own conn if needed, commits, idempotent |
| `_rewards_ledger_table_exists()` | models.py:182-209 | HelperDAO.table_exists() | SQLite + PostgreSQL dual-path |
| `_resolve_rewards_schema_state()` | models.py:270-296 | HelperDAO.resolve_state() | Updates global _rewards_schema_state, returns state string |
| `try_insert_rewards_points()` | models.py:299-331 | WriteDAO.insert_rewards_points() | Keyword-only, returns bool, catches all exceptions |
| `transfer_money()` | models.py:625-733 | WriteDAO.transfer() | Opens own conn, returns (bool, str), owns lifecycle |
| `create_transaction()` | models.py:591-622 | WriteDAO.create_transaction() | Opens own conn, commits, returns int ID |

---

## Connection Ownership (ACTUAL Pattern)

**Part 1 (UserDAO, AccountDAO, TransactionDAO):**
- Call `self.get_connection()` → creates connection
- Close in finally block
- Each call: new connection, standalone

**Part 2 (SchemaDAO, HelperDAO, WriteDAO):**
- Public wrapper (models.py): owns connection
  ```python
  def create_transaction(...):
      conn = get_db()
      try:
          dao.set_connection(conn)
          result = dao.create_transaction_internal(...)
          conn.commit()
          return result
      except:
          conn.rollback()
      finally:
          conn.close()
  ```
- DAO.set_connection(conn): `owns_connection=False`
- DAO method doesn't close (wrapper does)

**Exception:** SchemaDAO.ensure_schema() owns its own connection (called from init_db).

---

## Tests: 102 Total (98 + 4 New)

**4 new edge-case tests (must be added):**
1. `test_transfer_debit_credit_both_succeed` (happy path: both inserts + updates work)
2. `test_transfer_debit_fails_rolls_back_to_credit_not_inserted` (debit fails → credit not inserted)
3. `test_transfer_succeeds_when_rewards_insert_fails` (rewards exception caught by SAVEPOINT → transfer succeeds)
4. `test_transfer_dual_db_savepoint_semantics` (SQLite + PostgreSQL both handle SAVEPOINT correctly)

**Existing tests that MUST still pass:**
- 98 from Part 1
- All test_demo_rollout.py tests (including monkeypatch of try_insert_rewards_points)

---

## Chunks: 5 Specific (CHUNK_0-4)

### CHUNK_0: SchemaDAO (schema creation + idempotence)
- Create `dao/schema_dao.py`
- Implement: `ensure_rewards_ledger_schema(conn, cursor, commit)` (moved from models)
- Behavior: identical to current code (CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS)
- Update models.py: `ensure_rewards_ledger_schema()` delegates to DAO
- Run 98 tests (must pass)
- Commit message: "CHUNK_0: Schema DAO layer"

### CHUNK_1: HelperDAO (schema validation + state machine)
- Create `dao/helper_dao.py`
- Implement: `rewards_ledger_table_exists(cursor)` (SQLite + PostgreSQL paths)
- Implement: `resolve_rewards_schema_state(cursor)` (returns forced_fail, skipped, ready, runtime_error)
- Keep models._resolve_rewards_schema_state() wrapper (updates global state)
- Update models.py: wrapper delegates to HelperDAO
- Run 98 tests (must pass)
- Commit message: "CHUNK_1: Helper DAO + schema state machine"

### CHUNK_2: WriteDAO Part 1 (transaction creation)
- Create `dao/write_dao.py`
- Extend BaseDAO: `set_connection(conn)` method (owns_connection=False)
- Implement: `create_transaction_internal(conn, cursor, account_id, type, amount, description, recipient)` (pure SQL, no commit)
- Keep models.create_transaction() wrapper (opens conn, commits, closes)
- Update models.py: wrapper delegates to DAO
- Run 98 tests (must pass)
- Commit message: "CHUNK_2: Write DAO + create_transaction"

### CHUNK_3: WriteDAO Part 2 (rewards insertion)
- Extend `dao/write_dao.py`: `insert_rewards_points_internal(conn, cursor, user_id, source_account_id, target_account_id, transfer_amount)`
- Implement: actual INSERT SQL + exception handling (same logic as current code)
- Keep models.try_insert_rewards_points() wrapper (injectable for monkeypatch)
- Update models.py: wrapper delegates to DAO
- Run 98 tests + test_demo_rollout.py (monkeypatch tests must pass)
- Commit message: "CHUNK_3: Write DAO + rewards insertion"

### CHUNK_4: WriteDAO Part 3 (transfer atomicity)
- Extend `dao/write_dao.py`: `transfer_internal(conn, cursor, from_acct_id, to_acct_id, amount, description, acting_user_id)` → `(bool, str)`
- Implement: debit + credit + SAVEPOINT rewards logic (identical to current transfer_money)
- Keep models.transfer_money() wrapper (opens conn, calls DAO, commits/rollback, closes, returns tuple)
- Add 4 new edge-case tests (committed in this chunk)
- Run 102 tests (98 + 4 new, all must pass)
- Verify on SQLite + PostgreSQL
- Commit message: "CHUNK_4: Write DAO + transfer atomicity + 4 edge-case tests"

---

## Rollback Plan (Safe, Precise)

**Before starting Part 2:**
```bash
git rev-parse HEAD > /tmp/part2_start.txt
```

**If CHUNK_N fails:**
```bash
# Get starting commit
start=$(cat /tmp/part2_start.txt)

# Revert all Part 2 commits (in reverse order)
git log $start..HEAD --oneline --reverse | cut -d' ' -f1 | while read commit; do
    git revert --no-edit $commit
done

# Verify
git log --oneline -10
```

**Result:** Safe. Audit trail. No data loss.

---

## Success Criteria (V4)

- [ ] 102 tests pass (98 + 4 new) on SQLite
- [ ] 102 tests pass (98 + 4 new) on PostgreSQL
- [ ] Schema DAO creates tables idempotently (no errors on re-run)
- [ ] State machine returns exactly: forced_fail, skipped, ready, runtime_error
- [ ] Monkeypatch binding works (test_demo_rollout.py passes with mocked try_insert_rewards_points)
- [ ] transfer_money returns (bool, str) tuple correctly
- [ ] Savepoint semantics preserved (rewards error doesn't fail transfer)
- [ ] No circular imports (DAO imports models; models doesn't import DAO at module level)

---

**Plan Version:** 4.0 (based on actual code, executable, no assumptions)  
**Next step:** Execute CHUNK_0 → CHUNK_1 → CHUNK_2 → CHUNK_3 → CHUNK_4
