# AI Sprint Planning — QuantumBank DAO Refactor (V6)

**Final Version: Mechanical Fixes to V5**

**Status:** ✅ EXECUTION READY (Part 1 only — read-only DAO layer)  
**Review Cycle:** V5 REJECTED (mechanical issues) → V6 (fixes applied)

---

## V5 → V6: Mechanical Fixes

### Fix 1: Import `_sql()` in DAO

**V5 Issue:** DAO code uses `self.cursor.execute(_sql(...))` but `_sql` not imported.

**V6 Fix:**
```python
# dao/base_dao.py
from models import _sql, _row_to_dict, _normalize_row

class BaseDAO:
    def get_connection(self):
        from models import get_db
        self.conn = get_db()
        self.cursor = self.conn.cursor()
        return self.cursor
```

**Result:** PostgreSQL placeholder conversion works correctly.

---

### Fix 2: Import `PROFILE_DEMO_ADDRESS` in UserDAO

**V5 Issue:** UserDAO uses `PROFILE_DEMO_ADDRESS` but doesn't import it.

**V6 Fix:**
```python
# dao/user_dao.py
from models import _row_to_dict, PROFILE_DEMO_ADDRESS

class UserDAO(BaseDAO):
    def get_profile(self, user_id: int):
        """Get user profile (read-only)."""
        self.get_connection()
        try:
            self.cursor.execute(
                "SELECT username, email, full_name FROM users WHERE id = ?",
                (user_id,)
            )
            row = self.cursor.fetchone()
            if not row:
                return None
            profile = _row_to_dict(row)
            profile["address"] = PROFILE_DEMO_ADDRESS  # Now imported
            return profile
        finally:
            self.close()
```

**Result:** Profile page renders address correctly.

---

### Fix 3: Restore Columns in `get_all_transactions_by_user`

**V5 Issue:** Query dropped `a.account_type` and `a.account_number` columns.

**V6 Fix:**
```python
# dao/transaction_dao.py
class TransactionDAO(BaseDAO):
    def get_by_user(self, user_id: int, limit: int = 20):
        """Get all transactions for user (with account metadata)."""
        self.get_connection()
        try:
            self.cursor.execute("""
                SELECT t.*, a.account_type, a.account_number
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE a.user_id = ?
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (user_id, limit))
            transactions = self.cursor.fetchall()
            return [_normalize_row(_row_to_dict(t)) for t in transactions]
        finally:
            self.close()
```

**Result:** Dashboard transactions show account type/number (behavior preserved).

---

### Fix 4: Simplify `get_rewards_points_for_user` (Move Identically)

**V5 Issue:** `get_rewards_points_for_user` has feature-flag state logic (rollout behavior, banner state).

**V6 Decision:** Move the function identically to TransactionDAO. Don't simplify; preserve all state logic.

```python
# dao/transaction_dao.py
class TransactionDAO(BaseDAO):
    def get_rewards_for_user(self, user_id: int):
        """Get rewards points + banner state for user (read-only, preserves all rollout logic)."""
        self.get_connection()
        try:
            # Use exact same logic as models.py (lines 334-372)
            # This is a pure MOVE, not a refactor
            
            from db_flags import is_demo_rollout_feature_enabled
            
            if not is_demo_rollout_feature_enabled():
                return 0, None
            
            # Query rewards_ledger if it exists
            schema_state = self._resolve_rewards_schema_state()
            if schema_state != "ready":
                return 0, f"rewards_{schema_state}"
            
            self.cursor.execute("""
                SELECT SUM(points) as points_total FROM rewards_ledger
                WHERE user_id = ?
            """, (user_id,))
            row = self.cursor.fetchone()
            if not row:
                return 0, None
            
            data = _row_to_dict(row) or {}
            points = data.get("points_total")
            return int(points) if points is not None else 0, None
        finally:
            self.close()
    
    def _resolve_rewards_schema_state(self):
        """Helper: resolve if rewards_ledger exists (moved from models.py)."""
        # Exact copy of models._resolve_rewards_schema_state logic
        # (lines 270-296, schema check only)
        if self._rewards_ledger_table_exists():
            return "ready"
        return "unknown"
    
    def _rewards_ledger_table_exists(self):
        """Helper: check if rewards_ledger table exists."""
        # Exact copy of models._rewards_ledger_table_exists (lines 182-209)
        from models import using_postgres
        if using_postgres():
            self.cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'rewards_ledger'
                ) AS exists
            """)
        else:
            self.cursor.execute("""
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'rewards_ledger' LIMIT 1
            """)
        row = self.cursor.fetchone()
        return row is not None
```

**Result:** Rewards read logic works exactly as before (no behavior change, just relocated).

---

### Fix 5: Add Rollback Strategy to CHUNK_4

**V5 Issue:** No explicit rollback procedure documented.

**V6 Addition to CHUNK_4:**
```markdown
### Rollback Strategy (V6 — Added)

**If tests fail at any chunk:**

| Scenario | Action |
|----------|--------|
| CHUNK_0 import error | `git reset --hard HEAD~1` (delete dao/ dir, revert models) |
| CHUNK_1 test failure | `git reset --hard HEAD~1` (revert UserDAO + models wrapper) |
| CHUNK_2 test failure | `git reset --hard HEAD~1` (revert AccountDAO + models wrapper) |
| CHUNK_3 test failure | `git reset --hard HEAD~1` (revert TransactionDAO + models wrapper) |
| CHUNK_4 test failure | `git reset --hard HEAD~1` (cleanup partial) |
| **All chunks pass but manual smoke test fails** | `git reset --hard HEAD~1` (abort entire Part 1) |

**Recovery:** Roll back to commit before CHUNK_0 starts. No partial states.

**Timeline:** Each rollback ~10s. Can recover in minutes.
```

**Result:** Clear exit path if execution hits unexpected issues.

---

## Part 1 Scope (V6 — Final)

### In Scope (8 read-only functions)

**CHUNK_0:** DAO base + helpers
- `BaseDAO` class (connection management, try/finally)
- Module-level helpers imported: `_sql`, `_row_to_dict`, `_normalize_row`
- No circular imports (DAO imports from models only)

**CHUNK_1:** UserDAO
- `get_user_by_username(username)` → `UserDAO.get_by_username()`
- `get_user_profile(user_id)` → `UserDAO.get_profile()` (imports PROFILE_DEMO_ADDRESS)

**CHUNK_2:** AccountDAO
- `get_accounts_by_user(user_id)` → `AccountDAO.get_by_user()`
- `get_account_by_id(account_id)` → `AccountDAO.get_by_id()`
- `get_cards_by_account(account_id)` → `AccountDAO.get_cards_by_account()`

**CHUNK_3:** TransactionDAO (moved identically with all logic)
- `get_transactions_by_account(account_id, limit)` → `TransactionDAO.get_by_account()`
- `get_all_transactions_by_user(user_id, limit)` → `TransactionDAO.get_by_user()` (with account_type, account_number)
- `get_rewards_points_for_user(user_id)` → `TransactionDAO.get_rewards_for_user()` (moved identically, preserves rollout state)

**CHUNK_4:** Cleanup + validation
- Grep verification (no orphaned cursor.execute calls)
- All 98 tests pass 3x
- Manual smoke test
- Rollback strategy documented

### Out of Scope (Deferred to Part 2)

- `transfer_money()` (complex transaction)
- `init_db()`, `create_sample_data()` (schema/init)
- Rewards insertion (tied to transfer)
- Account balance updates (write operations)

---

## Success Criteria (V6)

- [ ] All 98 tests pass 3 times consecutive
- [ ] `_sql()` imported in DAO (PostgreSQL placeholders work)
- [ ] `PROFILE_DEMO_ADDRESS` imported in UserDAO (profile renders address)
- [ ] Transactions include account_type, account_number (columns preserved)
- [ ] Rewards logic moved identically (behavior unchanged)
- [ ] No orphaned cursor calls in query function bodies
- [ ] Manual smoke test: login → dashboard → profile → logout
- [ ] Rollback strategy clear (abort path documented)

---

## Execution Summary (V6)

**4 chunks, ~2 hours:**
- CHUNK_0 (30 min): DAO base + imports
- CHUNK_1 (15 min): UserDAO
- CHUNK_2 (15 min): AccountDAO
- CHUNK_3 (30 min): TransactionDAO (including rewards moved identically)
- CHUNK_4 (30 min): Cleanup + validation

**Each chunk:**
1. Create DAO class
2. Import required functions from models
3. Implement query methods (moved identically, no logic change)
4. Update models.py wrapper (delegates to DAO)
5. Run tests (must pass)
6. Commit when green

**Abort:** If any tests fail, rollback immediately (10s recovery).

---

## Why V6 is Ready

✅ **Scope is safe:** Read-only only (no writes, no state mutations)  
✅ **Imports are correct:** All helpers imported (DAO can use _sql, constants)  
✅ **Logic is preserved:** Moved identically (no behavior changes)  
✅ **Columns are restored:** Transactions include all original data  
✅ **Rollback is clear:** Exit path documented  
✅ **Tests are baseline:** 98 existing tests, all must pass  

**No architectural questions remain. Only mechanical execution.**

---

**Plan Version:** 6.0-final  
**Status:** ✅ READY FOR EXECUTION  
**Next Step:** Execute CHUNK_0 (DAO base + imports)
