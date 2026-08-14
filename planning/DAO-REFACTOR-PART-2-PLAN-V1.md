# DAO Refactor Part 2: Write Operations & Schema (V2 - Corrected Contracts)

**Status:** ✅ READY FOR EXECUTION (blockers fixed)  
**Prerequisites:** Part 1 merged to main ✅  
**Complexity:** High (write ops + savepoint semantics + shared conn lifecycle)  
**Estimated execution:** 3-4 hours (4 chunks)  

**Blocker fixes applied (v1 → v2):**
- ✅ Corrected API signatures (transfer_money returns `(bool, str)`, not `int`)
- ✅ Savepoint-based rewards failure semantics (transfer succeeds even if rewards fail)
- ✅ Monkeypatch binding preserved (models.try_insert_rewards_points wrapper stays injectable)
- ✅ Connection ownership explicitly defined (owns_connection flag, close only if owner)
- ✅ Schema validation beyond existence (column/constraint checks required)
- ✅ Specific edge-case tests named (4 new tests for atomicity)

---

## Executive Summary

Part 2 extracts **write operations** and **schema initialization** from `models.py` to a new `WriteDAO` and `SchemaDAO`. Unlike Part 1 (read-only queries, one connection per call), Part 2 handles:

- **Caller-managed transactions** (`transfer_money` shares connection with `try_insert_rewards_points`)
- **Shared connection lifecycle** (caller opens, passes to DAO, caller closes)
- **Idempotent schema setup** (`ensure_rewards_ledger_schema`)
- **Monkeypatch binding** (tests must inject shared connections)

---

## Part 2 Functions to Extract

### WriteDAO (Write Operations)

| Function | **ACTUAL** Signature | Extract To | Risk |
|----------|------------|------------|------|
| `transfer_money()` | `(from_acct_id, to_acct_id, amount, description, acting_user_id) → (bool, str)` | `WriteDAO.transfer()` | **HIGH**: multi-step debit+credit atomicity, savepoint-based rewards, shared conn |
| `create_transaction()` | `(account_id, type, amount, description, recipient, conn, cursor) → int` | `WriteDAO.create_transaction()` | MEDIUM: INSERT returning ID, updates balance, **caller's conn** |
| `try_insert_rewards_points()` | `(*, conn, cursor, user_id, src_acct_id, tgt_acct_id, transfer_amt) → bool` | `WriteDAO.insert_rewards_points()` | **HIGH**: keyword-only, **never fails transfer** (savepoint semantics), returns bool |

### SchemaDAO (Schema/Initialization)

| Function | Current Sig | Extract To | Risk |
|----------|-------------|------------|------|
| `init_db()` | `() → None` | `SchemaDAO.init()` | LOW: CREATE TABLE IF NOT EXISTS |
| `create_sample_data()` | `() → None` | `SchemaDAO.seed()` | MEDIUM: fixture setup, test isolation |
| `ensure_rewards_ledger_schema()` | `() → None` | `SchemaDAO.ensure_rewards_ledger()` | MEDIUM: idempotent check + CREATE |

### HelperDAO (Schema State Tracking)

| Function | Current Sig | Extract To | Risk |
|----------|-------------|------------|------|
| `_rewards_ledger_table_exists()` | `() → bool` | `HelperDAO.rewards_ledger_exists()` | LOW: schema introspection only |

---

## Design Decisions

### 1. Shared Connection Pattern (NEW, unlike Part 1)

**Part 1 (read-only):**
```python
class UserDAO(BaseDAO):
    def get_by_username(self, username):
        self.get_connection()  # Create connection
        try:
            self.cursor.execute(...)
        finally:
            self.close()  # Close immediately
```

**Part 2 (write operations):**
```python
class WriteDAO(BaseDAO):
    def transfer(self, conn, from_acct, to_acct, amount):
        # Caller passes connection
        # DAO uses caller's cursor, doesn't close
        cursor = conn.cursor()
        cursor.execute(...)
        # Return; caller commits/rollback
        
    def insert_rewards_points(self, cursor, user_id, points):
        # Accept cursor directly (not connection)
        cursor.execute(...)
```

**Why:** `transfer_money()` must call `try_insert_rewards_points()` within same transaction. If each DAO opened/closed its own connection, the two operations wouldn't be atomic.

**Implementation:** Add to BaseDAO:
```python
class BaseDAO:
    def set_connection(self, conn):
        """Caller injects connection; DAO doesn't close it."""
        self.conn = conn
        self.cursor = conn.cursor()
        self.owns_connection = False  # Don't close in cleanup
```

### 2. Monkeypatch Binding for Tests (CRITICAL - v1 had this wrong)

**Challenge:** Tests monkeypatch `models.try_insert_rewards_points()` (test_demo_rollout.py:226).  
Existing patch: `monkeypatch.setattr(models, "try_insert_rewards_points", mock_fn)`

**V1 mistake:** Plan showed DAO calling DAO directly; monkeypatch never hits.

**V2 fix:** Keep wrapper in models.py:
```python
def try_insert_rewards_points(*, conn, cursor, user_id, source_account_id, target_account_id, transfer_amount):
    """Wrapper: tests patch this, not DAO directly."""
    from dao.write_dao import WriteDAO
    return WriteDAO().insert_rewards_points(
        conn=conn,
        cursor=cursor,
        user_id=user_id,
        source_account_id=source_account_id,
        target_account_id=target_account_id,
        transfer_amount=transfer_amount,
    )
```

Then in `transfer_money()` in WriteDAO:
```python
# Call through models wrapper (injectable seam)
from models import try_insert_rewards_points as _try_insert_rewards_points
_try_insert_rewards_points(conn=conn, cursor=cursor, user_id=..., ...)
```

Tests still patch `models.try_insert_rewards_points` and control behavior. ✅ Monkeypatch stays intact.

### 3. Transaction Lifecycle with Savepoint-Based Rewards (v1 had wrong error handling)

**Current behavior (must preserve):**
- Debit + credit are atomic (both succeed or both fail)
- Rewards insert is **optional** (failures don't fail transfer)
- Uses PostgreSQL SAVEPOINT → ROLLBACK TO SAVEPOINT → RELEASE semantics

**transfer_money() flow (v2 - corrected):**
```python
def transfer_money(from_acct_id, to_acct_id, amount, description, acting_user_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Auth check (outside tx)
        auth_check(acting_user_id, from_acct_id)
        
        # Debit + credit (same tx)
        cursor.execute("INSERT INTO transactions ...")
        cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", ...)
        cursor.execute("INSERT INTO transactions ...")
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", ...)
        
        # SAVEPOINT: rewards failure does NOT fail transfer
        cursor.execute("SAVEPOINT rewards_savepoint")
        try:
            from models import try_insert_rewards_points
            try_insert_rewards_points(
                conn=conn,
                cursor=cursor,
                user_id=...,
                source_account_id=from_acct_id,
                target_account_id=to_acct_id,
                transfer_amount=amount,
            )
            cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
        except Exception:
            # PostgreSQL: on failed tx, RELEASE raises InFailedSqlTransaction
            # ROLLBACK TO is the only valid recovery
            cursor.execute("ROLLBACK TO SAVEPOINT rewards_savepoint")
            cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
        
        conn.commit()
        return True, "Transfer successful"
    except Exception:
        conn.rollback()
        return False, "Transfer failed"
    finally:
        conn.close()
```

**Key:** Rewards failures don't bubble up (caught + rolled back to savepoint). Transfer still succeeds. ✅

---

## Success Criteria (v2 - specific tests named)

### Functional
- [ ] 102 tests pass (98 from Part 1 + 4 new):
  - `test_transfer_debit_credit_atomic_success` (both sides succeed)
  - `test_transfer_debit_fails_rolls_back_credit` (debit fails, credit not inserted)
  - `test_transfer_succeeds_when_rewards_insert_fails` (rewards SAVEPOINT rolls back, transfer succeeds)
  - `test_transfer_savepoint_both_databases` (SQLite + PostgreSQL SAVEPOINT behavior)
- [ ] `transfer_money()` returns `(bool, str)` tuple (not int)
- [ ] Savepoint semantics preserved (ROLLBACK TO SAVEPOINT on rewards error)
- [ ] Schema DAO idempotent (re-running `init_db()` doesn't break)
- [ ] Monkeypatch still works (models.try_insert_rewards_points injectable)

### Code Quality
- [ ] No new circular imports (WriteDAO imports models; models doesn't import WriteDAO at module level)
- [ ] Shared connection pattern clear (BaseDAO.set_connection + owns_connection flag)
- [ ] All imports direct from models (no re-exports)
- [ ] Black + Ruff compliant

### Testing
- [ ] SQLite: 102/102 pass
- [ ] PostgreSQL: 102/102 pass
- [ ] Rewards monkeypatch test: passes
- [ ] Transfer rollback test: passes

---

## Part 2 Chunks (v2 - corrected)

### CHUNK_0: Schema DAO (init + seed + validation)
- Create `dao/schema_dao.py` (SchemaDAO class)
- Implement: `init()`, `seed()`, `ensure_rewards_ledger_schema()`
- **Schema validation:** Not just `EXISTS`, but check columns + constraints (handles version conflicts)
- Update `models.py`: `init_db()`, `create_sample_data()` delegate to SchemaDAO
- Run tests (98 must still pass)
- Commit

### CHUNK_1: Helper DAO (schema introspection with validation)
- Create `dao/helper_dao.py` (HelperDAO class)
- Implement: `rewards_ledger_exists()`, `resolve_rewards_schema_state()` (both with column validation)
- Keep `_resolve_rewards_schema_state()` wrapper in models.py (test fixtures reset it there)
- Update `dao/transaction_dao.py`: use HelperDAO for schema checks
- Run tests (98 must still pass)
- Commit

### CHUNK_2: Write DAO (create_transaction + rewards wrapper)
- Create `dao/write_dao.py` (WriteDAO class)
- Extend `BaseDAO`: add `set_connection(conn)` (sets owns_connection=False), clarify close() behavior
- Implement: `create_transaction(account_id, type, amount, description, recipient, conn, cursor)`
- Implement: wrapper for `insert_rewards_points()` that calls **models.try_insert_rewards_points** (monkeypatch seam)
- Update `models.py`: keep `try_insert_rewards_points()` wrapper at module level (tests patch here)
- Run tests (98 must still pass)
- Commit

### CHUNK_3: Transfer DAO (atomic debit + credit + savepoint rewards)
- Extend `dao/write_dao.py`: `transfer(from_acct_id, to_acct_id, amount, description, acting_user_id, conn, cursor)`
- Implement savepoint semantics: SAVEPOINT → call try_insert_rewards_points → on error: ROLLBACK TO + RELEASE
- Update `models.py`: `transfer_money()` delegates to WriteDAO.transfer(), but still owns conn lifecycle
- Run 98 tests (must pass)
- **Run 4 new edge-case tests** (must pass):
  - `test_transfer_debit_credit_atomic_success`
  - `test_transfer_debit_fails_rolls_back_credit`
  - `test_transfer_succeeds_when_rewards_insert_fails`
  - `test_transfer_savepoint_both_databases`
- Commit

### CHUNK_4: Validation & Dual-DB Test
- Run 102 tests on SQLite (98 + 4 edge cases, all must pass)
- Run 102 tests on PostgreSQL (98 + 4 edge cases, all must pass)
- Verify monkeypatch binding: test_demo_rollout.py still passes (models.try_insert_rewards_points patched)
- Verify schema validation: re-run init_db() doesn't create duplicates
- Create validation artifacts
- Commit

---

## Connection Ownership Model (v2 - explicitly defined)

**BaseDAO behavior:**
```python
class BaseDAO:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.owns_connection = True  # Default: DAO creates and closes
    
    def get_connection(self):
        """DAO creates connection (Part 1 pattern)."""
        self.owns_connection = True
        self.conn = models_get_db()
        self.cursor = self.conn.cursor()
        return self.cursor
    
    def set_connection(self, conn):
        """Caller injects connection (Part 2 pattern)."""
        self.owns_connection = False  # Caller closes
        self.conn = conn
        self.cursor = conn.cursor()
        return self.cursor
    
    def close(self):
        """Close only if DAO created connection."""
        if self.owns_connection and self.conn:
            self.conn.close()
        self.conn = None
        self.cursor = None
```

**Part 1 (UserDAO, AccountDAO, TransactionDAO):**
- Call `self.get_connection()` → owns_connection=True → close() in finally
- Each call: new connection, auto-closed

**Part 2 (WriteDAO):**
- Called with `set_connection(conn)` → owns_connection=False → close() is no-op
- Caller (transfer_money) manages conn lifecycle

**Result:** One pattern, two modes. No connection leaks.

### Risk: Monkeypatch Binding Breaks
**Problem:** Tests monkeypatch `models.try_insert_rewards_points`; DAO has new code path.  
**Mitigation:** Keep models.py wrapper. Tests patch wrapper; wrapper calls DAO. No double-patching needed.

### Risk: Transaction Rollback Incomplete
**Problem:** DAO rolls back its piece; caller doesn't know + tries to continue.  
**Mitigation:** DAO raises on error; caller catches + `conn.rollback()`. Clear contract.

### Risk: Schema Already Exists (idempotent)
**Problem:** Running `init_db()` twice creates duplicate tables (SQLite doesn't have IF NOT EXISTS on all operations).  
**Mitigation:** Query schema state first. Skip if table exists. Log skips.

---

## Success Path (Go / No-Go)

**Go:** Plan review feedback → Execute all 4 chunks → Validation → Merge to main  
**No-Go:** Blocker found during review → Revise plan → Re-review → Then execute

---

## Rollback Strategy

| Failure Point | Action |
|---------------|--------|
| CHUNK_0 test fail | `git reset --hard HEAD~1` (revert SchemaDAO + models wrapper) |
| CHUNK_1 test fail | `git reset --hard HEAD~1` (revert HelperDAO) |
| CHUNK_2 test fail | `git reset --hard HEAD~1` (revert WriteDAO early ops) |
| CHUNK_3 transfer fail | `git reset --hard HEAD~1` (revert transfer + atomicity) |
| CHUNK_4 validation fail | `git reset --hard HEAD~1` (abort entire Part 2) |
| All chunks pass, manual smoke test fails | `git reset --hard HEAD~1` (recover to Part 1 main) |

**Recovery time:** ~2 min per rollback (git + reinstall venv if needed).

---

## Questions for Reviewers

1. **Shared connection pattern:** Is BaseDAO.set_connection() the right abstraction, or should WriteDAO override __init__?
2. **Monkeypatch:** Should we move wrapper logic into DAO or keep wrapper in models.py for backward compat?
3. **Error handling:** Should DAO raise on integrity error (FK violation, unique constraint), or catch + return sentinel?
4. **Schema idempotence:** Should `ensure_rewards_ledger_schema()` check schema version or just EXISTS?

---

**Plan Version:** 1.0 (ready for review)  
**Recommendation:** Review before execution (write ops are riskier than reads)
