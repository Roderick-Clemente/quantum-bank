# DAO Refactor Part 2: Write Operations & Schema (V1)

**Status:** 🟡 READY FOR REVIEW (plan stage, no execution)  
**Prerequisites:** Part 1 merged to main ✅  
**Complexity:** Medium (write ops + transactions + shared conn lifecycle)  
**Estimated execution:** 2-3 hours (4 chunks)

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

| Function | Current Sig | Extract To | Risk |
|----------|-------------|------------|------|
| `transfer_money()` | `(from_acct, to_acct, amount, user_id)` → `int` | `WriteDAO.transfer()` | HIGH: multi-step, rewards insert, rollback |
| `create_transaction()` | `(account_id, type, amount, description)` → `int` | `WriteDAO.create_transaction()` | MEDIUM: INSERT returning ID |
| `try_insert_rewards_points()` | `(cursor, user_id, points)` → None | `WriteDAO.insert_rewards_points()` | HIGH: expects **caller's cursor**, not standalone |

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

### 2. Monkeypatch Binding for Tests

**Challenge:** Tests monkeypatch `models.try_insert_rewards_points()`, but now it lives in `WriteDAO.insert_rewards_points()`.

**Solution:** Keep wrapper in models.py:
```python
def try_insert_rewards_points(cursor, user_id, points):
    from dao.write_dao import WriteDAO
    return WriteDAO().insert_rewards_points(cursor, user_id, points)
```

Tests can still monkeypatch `models.try_insert_rewards_points`. DAO stays internal.

### 3. Transaction Lifecycle

**transfer_money() flow:**
```python
def transfer_money(from_acct, to_acct, amount, user_id):
    conn = get_db()
    try:
        # Auth check (outside tx for speed)
        auth_check(user_id, from_acct)
        
        # Write DAO uses caller's connection
        from dao.write_dao import WriteDAO
        dao = WriteDAO()
        
        # Debit + credit in same tx
        from_tx_id = dao.create_transaction(conn, from_acct, "debit", amount, ...)
        to_tx_id = dao.create_transaction(conn, to_acct, "credit", amount, ...)
        
        # Rewards insertion (if enabled)
        if feature_enabled():
            dao.insert_rewards_points(conn.cursor(), user_id, calculate_points(amount))
        
        conn.commit()
        return from_tx_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**Result:** Single connection, multi-step atomicity, clean rollback.

---

## Success Criteria

### Functional
- [ ] All 102 tests pass (98 from Part 1 + 4 new schema tests)
- [ ] `transfer_money()` maintains atomicity (debit + credit + rewards in one tx)
- [ ] Schema DAO idempotent (re-running `init_db()` doesn't break)
- [ ] Monkeypatch still works (test isolation preserved)

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

## Part 2 Chunks

### CHUNK_0: Schema DAO (init + seed)
- Create `dao/schema_dao.py` (SchemaDAO class)
- Implement: `init()`, `seed()`, `ensure_rewards_ledger()`
- Update `models.py`: `init_db()`, `create_sample_data()` delegate to SchemaDAO
- Run tests (must pass)
- Commit

### CHUNK_1: Helper DAO (schema introspection)
- Create `dao/helper_dao.py` (HelperDAO class)
- Implement: `rewards_ledger_exists()`, `resolve_rewards_schema_state()`
- Update `models.py`: `_rewards_ledger_table_exists()` delegates
- Update `dao/transaction_dao.py`: use HelperDAO
- Run tests (must pass)
- Commit

### CHUNK_2: Write DAO (create_transaction + rewards)
- Create `dao/write_dao.py` (WriteDAO class)
- Add `BaseDAO.set_connection(conn)` method
- Implement: `create_transaction()`, `insert_rewards_points()`
- Update `models.py`: wrappers delegate to WriteDAO
- Run tests (102 must pass)
- Commit

### CHUNK_3: Transfer DAO (multi-step transaction)
- Extend `dao/write_dao.py`: `transfer()`
- Update `models.py`: `transfer_money()` delegates
- Implement atomic flow: auth → debit → credit → rewards → commit
- Run tests (102 must pass)
- Commit

### CHUNK_4: Validation & Dual-DB Test
- Run 102 tests on SQLite (must pass)
- Run 102 tests on PostgreSQL (must pass)
- Verify monkeypatch binding (test injection still works)
- Create validation artifacts
- Commit

---

## Risk Mitigation

### Risk: Shared Connection Lifecycle
**Problem:** DAO receives connection; if test forgets to close, leak.  
**Mitigation:** Add `owns_connection` flag to BaseDAO. Close only if `owns_connection=True`.

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
