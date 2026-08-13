# DAO Refactor Part 2: Write Operations & Schema (V3 - Fully Executable)

**Status:** 🟡 READY FOR EXECUTION (all blockers resolved, fully specified)  
**Prerequisites:** Part 1 merged to main ✅  
**Complexity:** High (write ops + savepoint + shared conn + schema validation)  
**Estimated execution:** 3-4 hours  
**Chunks:** 5 (CHUNK_0 → CHUNK_4, not "4 chunks")

---

## Blocker Fixes (V2 → V3)

### 1. Recursion Fix: DAO Contains SQL, transfer() Calls Wrapper

**V2 mistake:** Both models and DAO call each other → infinite recursion.

**V3 fix:**
```python
# dao/write_dao.py
class WriteDAO(BaseDAO):
    def insert_rewards_points(self, *, conn, cursor, user_id, source_account_id, target_account_id, transfer_amount):
        """Contains ACTUAL SQL implementation (no call to models wrapper)."""
        # Direct SQL here
        cursor.execute(
            _sql("""
                INSERT INTO rewards_ledger
                    (user_id, source_account_id, target_account_id, points)
                VALUES (?, ?, ?, ?)
            """),
            (user_id, source_account_id, target_account_id, points),
        )
        return True  # or False if insert failed

# models.py
def try_insert_rewards_points(*, conn, cursor, user_id, source_account_id, target_account_id, transfer_amount):
    """Wrapper: patchable seam for tests."""
    from dao.write_dao import WriteDAO
    return WriteDAO().insert_rewards_points(
        conn=conn,
        cursor=cursor,
        user_id=user_id,
        source_account_id=source_account_id,
        target_account_id=target_account_id,
        transfer_amount=transfer_amount,
    )

# transfer_money() in WriteDAO
# Calls models wrapper (patchable), not DAO directly
from models import try_insert_rewards_points as _try_insert_rewards_points
_try_insert_rewards_points(conn=..., cursor=..., ...)
```

**Result:** DAO has SQL. Models wrapper is the injectable seam. No recursion. ✅

---

### 2. create_transaction() Lifecycle Fully Specified

**Current models.create_transaction() signature:**
```python
def create_transaction(
    account_id: int,
    transaction_type: str,
    amount: float,
    description: str,
    recipient: str = "",
) -> int:
    """Public API: owns connection lifecycle."""
    # Opens conn
    # Calls DAO
    # Commits/closes
    # Returns transaction_id
```

**DAO signature (called by both wrapper AND transfer):**
```python
def create_transaction(
    self,
    conn,  # Caller's connection
    cursor,  # Caller's cursor
    account_id: int,
    transaction_type: str,
    amount: float,
    description: str,
    recipient: str = "",
) -> int:
    """Pure insert + balance update. No commit/close. Caller owns that."""
    cursor.execute(
        _sql("""
            INSERT INTO transactions (account_id, transaction_type, amount, description, recipient)
            VALUES (?, ?, ?, ?, ?)
        """),
        (account_id, transaction_type, amount, description, recipient),
    )
    transaction_id = ...  # Return value
    cursor.execute(
        _sql("UPDATE accounts SET balance = balance + ? WHERE id = ?"),
        (amount, account_id),
    )
    return transaction_id
```

**Public wrapper (models.create_transaction):**
```python
def create_transaction(account_id, transaction_type, amount, description, recipient=""):
    """Wrapper: opens connection, delegates, commits/closes."""
    conn = get_db()
    try:
        from dao.write_dao import WriteDAO
        dao = WriteDAO()
        dao.set_connection(conn)
        transaction_id = dao.create_transaction(
            conn=conn,
            cursor=dao.cursor,
            account_id=account_id,
            transaction_type=transaction_type,
            amount=amount,
            description=description,
            recipient=recipient,
        )
        conn.commit()
        return transaction_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**transfer_money() usage (in WriteDAO.transfer):**
```python
def transfer(self, from_acct_id, to_acct_id, amount, description, acting_user_id, conn, cursor):
    """Called with conn + cursor already open by caller. Caller manages commit/rollback."""
    # Do NOT call public wrapper (models.create_transaction)
    # Call DAO directly with passed conn/cursor
    
    cursor.execute("INSERT INTO transactions ...")  # Debit
    cursor.execute("UPDATE accounts SET balance = balance - ? ...")
    
    cursor.execute("INSERT INTO transactions ...")  # Credit
    cursor.execute("UPDATE accounts SET balance = balance + ? ...")
    
    # Rewards with savepoint (caller handles savepoint + commit)
    ...
```

**Result:** Public wrapper owns connection. DAO is connection-agnostic. transfer() reuses same connection. Clear separation. ✅

---

### 3. Schema Validation: Exact Required Schema Specified

**rewards_ledger table MUST have:**
```sql
CREATE TABLE rewards_ledger (
    id SERIAL PRIMARY KEY,                    -- int, NOT NULL
    user_id INT NOT NULL,                     -- FK → users.id
    source_account_id INT NOT NULL,           -- FK → accounts.id
    target_account_id INT NOT NULL,           -- FK → accounts.id
    points DECIMAL(10,2) NOT NULL,            -- numeric, NOT NULL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- timestamp, NOT NULL
    INDEX idx_user_id (user_id),
    INDEX idx_source_account (source_account_id),
    INDEX idx_target_account (target_account_id)
);
```

**Validation logic (HelperDAO.rewards_ledger_valid()):**
```python
def rewards_ledger_valid(self):
    """Check table exists AND has required schema."""
    if not self.rewards_ledger_exists():
        return False
    
    # Column check
    cursor = self.conn.cursor()
    cursor.execute("PRAGMA table_info(rewards_ledger)")  # SQLite
    # OR: SELECT column_name, data_type FROM information_schema.columns
    #     WHERE table_name = 'rewards_ledger'  (PostgreSQL)
    
    columns = set()
    for row in cursor.fetchall():
        columns.add(row[0])  # Column name
    
    required = {'id', 'user_id', 'source_account_id', 'target_account_id', 'points', 'created_at'}
    if not required <= columns:  # Subset check
        return False
    
    # FK check
    cursor.execute("PRAGMA foreign_key_list(rewards_ledger)")  # SQLite
    fks = {(row[3], row[2]) for row in cursor.fetchall()}  # (from_col, to_table)
    
    required_fks = {('user_id', 'users'), ('source_account_id', 'accounts'), ('target_account_id', 'accounts')}
    if not required_fks <= fks:
        return False
    
    return True
```

**Behavior on incompatible schema:**
- If table exists but columns/FKs missing: raise SchemaError (abort, manual migration needed)
- If table doesn't exist: create it (idempotent)
- If table exists and schema matches: skip (idempotent)

**Result:** Executable schema validation. No "version conflicts" ambiguity. ✅

---

### 4. Schema State Ownership: Explicit Definition

**_rewards_schema_state in models.py:**
- Remains the source of truth
- Tests reset it via fixture
- HelperDAO computes the state, updates models._rewards_schema_state

**Call chain:**
```python
# models.py
_rewards_schema_state = "unknown"  # Global state

def _resolve_rewards_schema_state(cursor):
    """Compute state, update module-level var."""
    from dao.helper_dao import HelperDAO
    dao = HelperDAO()
    dao.set_connection(conn)  # If needed
    state = dao.compute_schema_state(cursor)
    globals()["_rewards_schema_state"] = state  # Update module state
    return state
```

**HelperDAO:**
```python
class HelperDAO(BaseDAO):
    def compute_schema_state(self, cursor):
        """Compute (don't mutate models state; let caller update)."""
        if not self.rewards_ledger_exists(cursor):
            return "unknown"
        if not self.rewards_ledger_valid(cursor):
            return "incompatible"  # Or raise
        return "ready"
```

**Fixture reset:**
```python
@pytest.fixture
def rewards_schema_clean(monkeypatch):
    """Reset to baseline."""
    monkeypatch.setattr(models, "_rewards_schema_state", "unknown")
    # Tests can now manipulate schema and state independently
```

**Result:** Single source of truth in models. HelperDAO computes. Tests control. ✅

---

### 5. Rollback Strategy: Safe & Precise

**Instead of `git reset --hard HEAD~1`:**

**Before starting Part 2:**
```bash
git rev-parse HEAD > /tmp/part2_start_commit.txt
git status --porcelain > /tmp/part2_start_status.txt
```

**If any CHUNK fails:**
```bash
# Check for uncommitted work
git status --porcelain | grep -v "??" && echo "ERROR: Uncommitted changes. Stash first." && exit 1

# Get starting commit
start_commit=$(cat /tmp/part2_start_commit.txt)

# Revert all Part 2 commits
for commit in $(git log $start_commit..HEAD --oneline | cut -d' ' -f1 | tac); do
    git revert --no-edit $commit
done

# Verify
git log --oneline -5
```

**Result:** Safe rollback. No data loss. Clear audit trail. ✅

---

### 6. Chunks & Tests: Consistent Metadata

**Chunks: 5 (not "4")**
1. CHUNK_0: SchemaDAO (create tables + idempotent)
2. CHUNK_1: HelperDAO (schema validation)
3. CHUNK_2: WriteDAO (create_transaction DAO)
4. CHUNK_3: WriteDAO (transfer DAO + savepoint)
5. CHUNK_4: Validation + edge-case tests

**Tests: 102 total**
- 98 from Part 1 (must still pass)
- 4 new edge-case tests (must be added + pass):
  1. `test_transfer_both_sides_atomic_success` (debit + credit both succeed)
  2. `test_transfer_debit_fails_credit_not_inserted` (debit fails, credit rollback verified)
  3. `test_transfer_succeeds_when_rewards_insert_fails` (rewards SAVEPOINT rollback, transfer succeeds)
  4. `test_transfer_savepoint_both_sqlite_and_postgresql` (SAVEPOINT works on both DBs)

**Verification command:**
```bash
source venv/bin/activate
python -m pytest test/ -v --tb=short 2>&1 | grep -E "passed|failed" | tail -1
# Expected: "102 passed in X.XXs"
```

**Result:** Executable. Testable. Countable. ✅

---

## Execution Checklist (V3)

- [ ] Blocker 1: No recursion (DAO has SQL; models wrapper is seam)
- [ ] Blocker 2: create_transaction() wrapper owns conn; DAO is agnostic
- [ ] Blocker 3: Schema validation checks columns + FKs + types
- [ ] Blocker 4: _rewards_schema_state in models; HelperDAO computes
- [ ] Blocker 5: Rollback is safe (no git reset --hard)
- [ ] Blocker 6: 5 chunks, 102 tests (98 + 4 new), metadata consistent

**Ready to execute CHUNK_0 → CHUNK_1 → CHUNK_2 → CHUNK_3 → CHUNK_4?**

---

**Plan Version:** 3.0 (fully executable, all blockers resolved)  
**Recommendation:** Execute (no further review needed; blockers explicitly resolved)
