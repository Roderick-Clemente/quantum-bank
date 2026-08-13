# DAO Refactor Part 2: Write Operations & Schema (V5 - Final, No Contradictions)

**Status:** ✅ READY FOR EXECUTION (contradictions removed, facts grounded)  
**Baseline commit:** 695d8d17 (main, after Part 1 + linting fixes)  
**Baseline test count:** 102 tests  
**Prerequisites:** Part 1 merged to main ✅  
**Complexity:** High (write ops + savepoint + multi-DB + state machine)  
**Estimated execution:** 3-4 hours  
**Chunks:** 5 (CHUNK_0 → CHUNK_4)

---

## V5: Contradictions Fixed

### 1. try_insert_rewards_points() - ACTUAL Implementation

**Exact signature (keyword-only, uses caller's cursor):**
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

**ACTUAL code (models.py:299-331, no pseudocode):**
```python
def try_insert_rewards_points(...) -> bool:
    if not is_demo_rollout_feature_enabled():
        return False

    conn = get_db()  # ← Opens NEW connection (despite receiving conn + cursor params)
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
        points = _compute_reward_points(transfer_amount)
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
    finally:
        conn.close()
```

**Contradiction found:** Function receives `conn` + `cursor` params but **ignores them and creates own connection**. This breaks savepoint atomicity (separate connection = separate transaction).

**V5 fix:** Extract EXACTLY as-is (preserve behavior). **Don't fix the logic—preserve it.** Extraction goal is move, not refactor.

**DAO version (EXACT COPY of current code, no changes):**
```python
class WriteDAO(BaseDAO):
    def insert_rewards_points(
        self,
        *,
        conn,
        cursor,
        user_id: int,
        source_account_id: int,
        target_account_id: int,
        transfer_amount: float,
    ) -> bool:
        """Exact copy of current implementation (opens own connection despite receiving params)."""
        if not is_demo_rollout_feature_enabled():
            return False

        own_conn = get_db()
        own_cursor = own_conn.cursor()
        schema_state = _resolve_rewards_schema_state(own_cursor)

        if schema_state == "forced_fail":
            own_conn.close()
            return False  # Changed: return bool, not tuple
        if schema_state in {"skipped", "unknown"}:
            own_conn.close()
            return False
        if schema_state == "runtime_error":
            own_conn.close()
            return False

        try:
            points = _compute_reward_points(transfer_amount)
            own_cursor.execute(
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
        finally:
            own_conn.close()
```

**Note:** This creates its own connection. Savepoint logic in transfer_money() will ALSO call try_insert_rewards_points, which creates another connection. This means rewards writes happen in **separate transaction** from transfer debit/credit. Current behavior.

---

### 2. Connection Ownership - ONE Model (Chosen)

**Choice: Models wrapper owns connection. DAO never owns.**

**Pattern (final, consistent):**

**Public API (models.py):**
```python
def transfer_money(from_account_id, to_account_id, amount, description, acting_user_id):
    """Public API. Owns connection lifecycle."""
    conn = get_db()
    try:
        from dao.write_dao import WriteDAO
        dao = WriteDAO()
        success, message = dao.transfer_internal(conn, from_account_id, to_account_id, amount, description, acting_user_id)
        conn.commit()
        return success, message
    except Exception:
        conn.rollback()
        return False, "Transfer failed"
    finally:
        conn.close()

def create_transaction(account_id, transaction_type, amount, description, recipient):
    """Public API. Owns connection lifecycle."""
    conn = get_db()
    try:
        from dao.write_dao import WriteDAO
        dao = WriteDAO()
        transaction_id = dao.create_transaction_internal(conn, account_id, transaction_type, amount, description, recipient)
        conn.commit()
        return transaction_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**DAO (dao/write_dao.py):**
```python
class WriteDAO(BaseDAO):
    def transfer_internal(self, conn, from_account_id, ...):
        """DAO method. Never commits/closes. Caller (wrapper) does."""
        cursor = conn.cursor()
        # ... do work ...
        return success, message  # No commit/close

    def create_transaction_internal(self, conn, account_id, ...):
        """DAO method. Never commits/closes. Caller (wrapper) does."""
        cursor = conn.cursor()
        # ... do INSERT + UPDATE ...
        return transaction_id  # No commit/close
```

**Result:** Clear separation. No ambiguity. ✅

---

### 3. init_db() and create_sample_data() - Explicit Scope

**Decision: INCLUDE in Part 2.**

**Functions to extract:**
- `init_db()` → SchemaDAO.init()
- `create_sample_data()` → SchemaDAO.seed()
- `ensure_rewards_ledger_schema()` → SchemaDAO.ensure_rewards_ledger()

**Reasoning:** Part 1 was read-only (no schema mutations). Part 2 is natural place for schema + seed. Both are called during tests + initialization.

**Extraction (CHUNK_0):**
- Move lines 357-393 (init_db) to SchemaDAO.init()
- Move lines 395-430 (create_sample_data) to SchemaDAO.seed()
- Models wrappers delegate to SchemaDAO

---

### 4. Rollback - Safe, Precise

**Before CHUNK_0:**
```bash
echo "Part 2 baseline: $(git rev-parse HEAD)" > /tmp/part2_rollback.txt
echo "Recording Part 2 start commit"
```

**If any CHUNK fails (working tree must be clean first):**
```bash
git status --porcelain | grep -v "^??" && echo "ERROR: Uncommitted changes" && exit 1

start_commit=$(cat /tmp/part2_rollback.txt | cut -d' ' -f3)

# Revert in REVERSE order (newest first)
git log $start_commit..HEAD --pretty=format:"%H" | while read commit; do
    echo "Reverting $commit"
    git revert --no-edit $commit
done

echo "Rollback complete. Verify: git log --oneline -10"
```

**Result:** Safe. Reversible. No data loss. ✅

---

### 5. Test Baseline & Count (Grounded in Fact)

**Baseline (commit 695d8d17, main):**
- Collected: 102 tests
- All pass

**Part 2 will add:** 4 new tests (in CHUNK_4)
- `test_transfer_debit_credit_both_succeed`
- `test_transfer_debit_fails_credit_not_inserted`
- `test_transfer_succeeds_when_rewards_insert_fails`
- `test_transfer_both_databases_savepoint`

**Expected after Part 2:**
- 102 (baseline) + 4 (new) = 106 tests
- All 106 must pass

**Verification command (CHUNK_4):**
```bash
source venv/bin/activate
python -m pytest test/ -q 2>&1 | tail -1
# Expected: "106 passed in X.XXs"
```

---

## Part 2 Chunks - Consistent & Grounded

### CHUNK_0: SchemaDAO (init + seed + rewards schema)
- Create `dao/schema_dao.py`
- Extract: `init_db()`, `create_sample_data()`, `ensure_rewards_ledger_schema()`
- Models wrappers delegate
- Run 102 tests (must pass)

### CHUNK_1: HelperDAO (state machine + validation)
- Create `dao/helper_dao.py`
- Extract: `_rewards_ledger_table_exists()`, `_resolve_rewards_schema_state()`
- Models wrappers delegate (keep for state machine global updates)
- Run 102 tests (must pass)

### CHUNK_2: WriteDAO Part 1 (transaction creation)
- Create `dao/write_dao.py`
- Extract: `create_transaction()` → `create_transaction_internal(conn, ...)`
- Models wrapper owns conn lifecycle
- DAO never owns
- Run 102 tests (must pass)

### CHUNK_3: WriteDAO Part 2 (rewards insertion)
- Extend `dao/write_dao.py`: `insert_rewards_points()` → exact copy
- Preserves behavior: opens own connection, returns bool
- Models wrapper is injectable seam for monkeypatch
- Run 102 tests (must pass)

### CHUNK_4: WriteDAO Part 3 (transfer atomicity) + 4 New Tests
- Extend `dao/write_dao.py`: `transfer_internal(conn, ...)`
- Models wrapper owns conn, commits/rollbacks
- Add 4 new edge-case tests (commit them in this chunk)
- Run 106 tests (102 baseline + 4 new, all must pass)
- Verify on SQLite + PostgreSQL

---

## Success Criteria (V5 - Grounded)

- [ ] 102 baseline tests pass after CHUNK_0-3
- [ ] 106 tests pass after CHUNK_4 (102 + 4 new)
- [ ] Both SQLite + PostgreSQL: 106/106 green
- [ ] Monkeypatch binding works (test_demo_rollout.py still passes)
- [ ] Connection ownership clear: wrapper owns, DAO doesn't
- [ ] Savepoint semantics preserved (rewards separate transaction, as current code does)
- [ ] No circular imports
- [ ] Rollback plan verified (safe, no data loss)

---

**Plan Version:** 5.0 (contradictions removed, facts grounded, ready for CHUNK_0)  
**Next step:** Execute CHUNK_0 (SchemaDAO)
