# DAO Refactor Part 2: Transaction & Schema Layer

**Planned for:** After Part 1 (read-only DAO layer) ships and validates  
**Prerequisites:** Part 1 complete and passing in production (2-3 days post-Part1-merge)  
**Estimated duration:** 1 day (4-5 hours, using Part 1 patterns)

---

## What Part 2 Tackles

**Transfer refactoring:**
- `transfer_money()` with atomic balance updates + rewards on shared connection
- Complex transaction semantics (auth check outside tx, savepoint for rewards)
- Monkeypatch binding for test isolation

**Schema/Initialization:**
- `init_db()` orchestration
- `create_sample_data()` seeding
- `ensure_rewards_ledger_schema()` idempotent setup

**Rewards ledger:**
- `try_insert_rewards_points()` under caller's transaction
- `get_rewards_points_for_user()` query (read-only)
- `_resolve_rewards_schema_state()` schema state tracking

---

## What We Learned From Part 1 (Template for Part 2)

### DAO Pattern (reuse in Part 2)

**From Part 1, we know works:**
```python
# Keep helpers in models, DAO imports them
from models import _sql, _row_to_dict, _normalize_row

class BaseDAO:
    def get_connection(self):
        from models import get_db  # Import at call time
        self.conn = get_db()
        return self.conn.cursor()
    
    def close(self):
        if self.conn:
            self.conn.close()
```

**One-way imports:** DAO imports from models; models doesn't import DAO (at module level).  
**Result:** No circular imports. Safe to extend in Part 2.

### Query Wrapper Pattern (reuse in Part 2)

**From Part 1, we know works:**
```python
# In models.py
def get_user_by_username(username: str):
    from dao.user_dao import UserDAO  # Lazy import
    return UserDAO().get_by_username(username)
```

**Why this works:**
- Lazy import (inside function) avoids module-level cycles
- Per-call instantiation (no singleton state)
- Tests can monkeypatch the DAO class if needed
- Backward compat: models.get_user_by_username still callable

**Apply to Part 2:**
```python
# In models.py
def transfer_money(from_id, to_id, amount, desc, acting_user_id):
    from dao.account_dao import AccountDAO  # Lazy import
    return AccountDAO().transfer(from_id, to_id, amount, desc, acting_user_id)
```

### Monkeypatch Binding Pattern (learned for Part 2)

**What broke in V4:**
```python
# test_demo_rollout.py
monkeypatch.setattr(models, 'try_insert_rewards_points', mock_fn)

# But DAO did: from models import try_insert_rewards_points
# Binding resolved at import time, before monkeypatch applied
```

**Solution (Part 2 will use):**
```python
# DAO code (Part 2):
def transfer(self, ...):
    # INSTEAD OF: from models import try_insert_rewards_points
    # DO THIS:
    import models  # Module import
    models.try_insert_rewards_points(conn, cursor, ...)  # Call via module
    # Monkeypatch now intercepts (runtime lookup on models.try_insert_rewards_points)
```

**Result:** Monkeypatch tests work correctly in Part 2.

---

## Part 2 Risk Map (Learned From Part 1-4 Reviews)

### High Risk Areas (Lessons From V4)

**1. Transaction semantics:**
- ❌ Don't assume auth-outside-tx is pure refactor (it changes lock duration)
- ✅ Document it as intentional change with test gate
- ✅ Separate: pre-fixes (bug) vs refactor (code move)

**2. Shared connection across DAOs:**
- ❌ Don't split reward insertion to separate RewardsDAO connection (ACID breaks)
- ✅ Pass connection explicitly: `rewards_dao.try_insert(conn=self.conn, cursor=self.cursor)`
- ✅ Single owner of transaction boundary (AccountDAO)

**3. Monkeypatch bindings:**
- ❌ Don't use `from models import try_insert_rewards_points` in DAO
- ✅ Use `import models; models.try_insert_rewards_points(...)` (runtime lookup)
- ✅ Verify Part 2 monkeypatch tests still pass

**4. Circular imports:**
- ❌ Don't move `using_postgres()` to DAO if `_sql()` calls it
- ✅ Keep backend flags in models.py
- ✅ DAO imports them from models (one-way)

---

## Part 2 Structure (Provisional)

### CHUNK_5: Transfer with Atomic Transaction

**Scope:** AccountDAO.transfer() with all balance/rewards atomicity

**Current code location:** models.py:707-812

**Challenges:**
- Auth checks must run OUTSIDE transaction (correctness fix, not pure refactor)
- Rewards insertion on same connection (not separate DAO)
- Savepoint/rollback for rewards error resilience
- Test gates must cover all paths (error scenarios)

**Implementation pattern (learned from Part 1):**
```python
# dao/account_dao.py (CHUNK_5, Part 2)
class AccountDAO(BaseDAO):
    def transfer(self, from_id, to_id, amount, desc, acting_user_id):
        """Transfer with atomic updates + rewards."""
        self.get_connection()
        try:
            # Auth checks OUTSIDE transaction (Grok found this must be intentional)
            from_account = self._fetch_account(from_id)
            if not from_account or from_account["user_id"] != acting_user_id:
                return False, "Forbidden"
            
            # Writes with savepoint
            self.cursor.execute("UPDATE accounts SET balance = ... - ?")
            self.cursor.execute("UPDATE accounts SET balance = ... + ?")
            
            # Rewards on same cursor (shared transaction)
            self.cursor.execute("SAVEPOINT rewards_savepoint")
            try:
                import models  # Runtime lookup for monkeypatch
                models.try_insert_rewards_points(
                    conn=self.conn,
                    cursor=self.cursor,
                    user_id=acting_user_id,
                    ...
                )
                self.cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
            except:
                self.cursor.execute("ROLLBACK TO SAVEPOINT rewards_savepoint")
                self.cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
            
            self.commit()
            return True, "Transfer successful"
        except Exception as e:
            self.rollback()
            return False, str(e)
        finally:
            self.close()
```

**Test gates (real tests from Part 1 baseline):**
- ✅ `test_transfer_money_small_amount_updates_balances` (CHUNK_5 gate)
- ✅ `test_transfer_still_succeeds_when_rewards_insert_raises` (error resilience)
- ✅ `test_transfer_still_succeeds_when_rewards_insert_hits_real_db_error` (DB error path)

---

### CHUNK_6: Rewards DAO (if not in CHUNK_5)

**Scope:** Separate RewardsDAO for ledger queries + insertion helpers

**Note:** May merge with CHUNK_5 since rewards is tightly bound to transfer.

**Functions:**
- `try_insert_rewards_points(conn, cursor, ...)` — re-export from models
- `_compute_reward_points(amount)` — private helper
- `_resolve_rewards_schema_state(cursor)` — schema state check
- `get_rewards_points_for_user(user_id)` — read-only query

**Implementation note:**
- Rewards DAO will NOT open its own connection (called by transfer)
- Models keeps re-export wrappers (monkeypatch compat)

---

### CHUNK_7: Schema DAO

**Scope:** init_db, create_sample_data, schema setup

**Functions:**
- `init_db()` → SchemaDAO.init_db() (orchestration)
- `create_sample_data(conn)` → SeedDAO.create_sample_data() (seeding)
- `ensure_rewards_ledger_schema()` → SchemaDAO (if not in rewards)

**Simpler than transfer:** Just move code, no complex transaction semantics.

---

## Part 2 Validation Criteria

**Before Part 2 starts:**
- Part 1 merged and passing in production (3+ days)
- No production issues from Part 1 DAO layer

**Part 2 exit criteria:**
- [ ] All 98 tests pass (baseline) + new Part 2 tests
- [ ] Monkeypatch tests pass (test_demo_rollout.py:212-268)
- [ ] Transfer balances atomic (no partial updates)
- [ ] Rewards error doesn't break core transfer
- [ ] Manual smoke: Transfer works end-to-end
- [ ] Postgres backend verified (if available)

---

## Risk Mitigation (Part 2)

**What Part 1 validated:**
- DAO import pattern is safe (no circles)
- Lazy imports work (avoid module-level cycles)
- Per-call instantiation is correct (no state leaks)
- Query wrapper pattern is maintainable

**What Part 2 must watch:**
- Monkeypatch binding (use `import models; models.func()` not `from models import func`)
- Transaction atomicity (shared connection across DAOs)
- Savepoint error handling (doesn't silently fail)
- Auth check semantics (intentional behavior change)

**Strategy:** Use Part 1 patterns exactly. Don't invent new patterns.

---

## Success Metrics

**Part 2 complete when:**
- All 98 + new tests passing
- No monkeypatch failures
- Transfer+rewards atomicity verified
- Postgres backend works (if applicable)
- Code review passes (familiar with Part 1 pattern)
- Total DAO refactor DONE: read-only + writes + schema

**Expected timeline:**
- Part 2 CHUNK_5: 60 min (transfer + rewards together)
- Part 2 CHUNK_6-7: 30 min (schema, simpler)
- Part 2 CHUNK_4: 30 min (cleanup, validation)
- Total: ~2 hours

---

## When to Start Part 2

**Trigger:**
- Part 1 merged to main
- 2-3 days of production validation
- No bugs reported
- Team ready to tackle transaction complexity

**Not before:**
- Part 1 is fully tested and deployed
- Developers comfortable with Part 1 DAO pattern
- Part 2 plan reviewed and team aligned

---

**End of Part 2 outline. Part 2 will be a separate sprint, using this as starting template.**
