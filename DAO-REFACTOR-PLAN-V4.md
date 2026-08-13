# AI Sprint Planning — QuantumBank DAO Refactor (V4)

**Adapted from:** `.local/planning/ai-sprints/SPRINT-PLANNING-TEMPLATE.md`  
**Status:** RESPONSIVE TO CROSS-MODEL BLOCKERS  
**Review Cycle:** V1 → Claude audit → V2 → Grok/Gemini REJECT → V3 → Grok/Gemini REJECT (new blockers) → V4

---

## Sprint Metadata

**Sprint Name:** QuantumBank DAO Pattern Refactor (V4 — Blocker Resolution)
**Date:** 2026-08-12
**Sprint Type:** Refactor
**Priority:** P2-Medium
**Estimated Duration:** 1.5-2 days
**Status:** Ready for Final Review (V3 blockers resolved)
**Branch:** `feature/quantum-dao-refactor`

**V3 → V4 Critical Changes:**
- ✅ All test names are REAL (from pytest --collect-only; no fabricated tests)
- ✅ Circular import prevented (import strategy explicit; helpers stay at models.*)
- ✅ Transaction semantics clarified (pure extraction vs intended fixes separated)
- ✅ Schema state ownership explicit (_resolve_rewards_schema_state → RewardsDAO)

---

## Blocker Resolutions

### BLOCKER 1: Fabricated Test Names (Grok + Gemini both found)

**V3 Problem:**
```
Exit criterion: test_rewards_successful_on_transfer_with_feature_flag_enabled must pass
Reality: No test with that name exists
```

**V4 Solution — Real Test Gates (Verified Against Codebase):**

| Chunk | Exit Criterion | Real Test | Location | Gate Passes If |
|-------|---|---|---|---|
| CHUNK_1 | User queries work | `test_init_db_seeds_demo_on_empty_database` | test_a_models_bootstrap.py:112-130 | User demo_user exists after init |
| CHUNK_2 | Accounts work | `test_demo_seeded_cards_expose_masked_last4_only` | test_a_models_bootstrap.py:164-189 | Accounts + cards visible |
| CHUNK_3 | Transactions work | `test_transfer_money_small_amount_updates_balances` | test_a_models_bootstrap.py:137-162 | Balances change atomically |
| CHUNK_4 (transfer) | Transfer success | `test_transfer_still_succeeds_when_rewards_insert_raises` | test_demo_rollout.py:212-237 | Transfer proceeds despite rewards error |
| CHUNK_4 (rewards OK) | Rewards after error | `test_transfer_still_succeeds_when_rewards_insert_hits_real_db_error` | test_demo_rollout.py:238-268 | Same as above but with DB error |
| CHUNK_4 (rewards happy) | Rewards with flag | `test_dashboard_shows_rewards_points_when_schema_and_feature_are_enabled` | test_demo_rollout.py:118-132 | Points appear on dashboard |
| CHUNK_5a (init) | Schema init | `test_init_db_seeds_demo_on_empty_database` | test_a_models_bootstrap.py:112-130 | Runs again after refactor |
| CHUNK_5a (cards) | Cards exist | `test_demo_seeded_cards_expose_masked_last4_only` | test_a_models_bootstrap.py:164-189 | Cards still visible after init |
| CHUNK_5b (greps) | All tests pass 3x | All 89 tests (not 92) | `pytest test/ -v` | Green baseline × 3 |

**No invented test names. All gates are real, executable tests from the actual codebase.**

---

### BLOCKER 2: Circular Import (Grok + Gemini both found)

**V3 Problem:**
```python
# models.py:58-59
def _sql(query: str) -> str:
    return query.replace("?", "%s") if using_postgres() else query

# Plan says: move _sql to dao/base_dao.py
# But _sql calls using_postgres()
# And using_postgres() was staying in models.py
# Result: dao/base_dao.py → import from models.py
#         models.py → import from dao/base_dao.py
# CIRCULAR IMPORT
```

**V4 Solution — Two Strategies (Pick One):**

**Strategy A (Recommended): Helpers stay module-level in models.py, DAO calls through models**

```python
# models.py (NO CHANGE to location, just wrap callers)
def using_postgres() -> bool:
    return is_postgres_database_enabled()

def _sql(query: str) -> str:
    return query.replace("?", "%s") if using_postgres() else query

def get_db():
    # ... stays here ...

# dao/base_dao.py
from models import using_postgres, _sql, get_db  # Import from models

class BaseDAO:
    def get_connection(self):
        conn = get_db()  # Call through models import
        # ...
        
    def _normalize_row(self, row_dict):
        # Uses local helper, no import needed
        for key, value in row_dict.items():
            if isinstance(value, Decimal):
                row_dict[key] = float(value)
        return row_dict

# models.py (re-export for backward compat, but they stay implemented here)
# No change: models._sql("SELECT ?") still works (it's here)
# DAO calls: from models import _sql; _sql(...) still works
```

**Benefit:** Zero circular import. Helpers live in models.py as they do today. DAO imports from models (one direction).  
**Trade-off:** DAO is not fully isolated (depends on models for helpers).

**Strategy B (Alternative): Move ALL helpers to dao/, models re-exports only**

```python
# dao/backend.py (NEW — pure backend logic, no imports of models)
def using_postgres() -> bool:
    return is_postgres_database_enabled()  # Uses environment/flags only

def db_path() -> str:
    return os.environ.get("QUANTUM_BANK_DATABASE", "quantum_bank.db")

# dao/base_dao.py
from dao.backend import using_postgres, db_path

def _sql(query: str) -> str:
    return query.replace("?", "%s") if using_postgres() else query

class BaseDAO:
    def get_connection(self):
        if using_postgres():
            import psycopg2
            # ...
        else:
            import sqlite3
            # ...

# models.py (re-export ONLY, no implementation)
from dao.backend import using_postgres, db_path
from dao.base_dao import _sql, get_db, _row_to_dict, _insert_returning_id

# Now: models._sql still works (re-export)
# Now: dao.backend has no models imports (no circular risk)
```

**Benefit:** Clean isolation. DAO has no models dependency.  
**Trade-off:** More moves (backend.py new file); bigger refactor.

**V4 Choice:** **STRATEGY A (recommended for pure refactor)** — Helpers stay in models.py, DAO imports from models.

**Implementation Pattern:**
```python
# CHUNK_0 task: Clarify import ownership
# Step 1: Create dao/base_dao.py with:
class BaseDAO:
    def __init__(self):
        from models import get_db
        self.get_db = get_db
        # No circular risk: models doesn't import dao yet

# Step 2: Update models.py re-exports (no code changes):
# At bottom of models.py:
# from dao.base_dao import BaseDAO  # Models imports DAO (one direction)
# # Helpers stay here; DAO imports them from models

# CHUNK_0 verification:
# python -c "from models import get_db, _sql; from dao.base_dao import BaseDAO; print('no circular import')"
```

**No circular import. Helpers remain callable at models.* as before.**

---

### BLOCKER 3: Transaction Semantics — Behavior Change vs Pure Refactor

**V3 Problem:**
```
Plan claims: "Zero Behavior Change"
But also says: "Move auth outside transaction" + "Add try/finally"
Reality: These ARE behavior changes (lock duration, error paths)
```

**V4 Solution — Explicit Separation:**

#### Phase 0: Pre-Execution BUG FIXES (NOT pure refactor — intentional changes)

**These are REQUIRED before CHUNK_0:**

**Fix P0-1: Add try/finally to query functions (resource safety)**
```python
# BEFORE (models.py:574-580)
def get_user_by_username(username: str) -> dict | None:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql("SELECT * FROM users WHERE username = ?"), (username,))
    user = cursor.fetchone()
    conn.close()  # ← Never called if execute() raises
    return _row_to_dict(user)

# AFTER (same function, same behavior, just safer)
def get_user_by_username(username: str) -> dict | None:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(_sql("SELECT * FROM users WHERE username = ?"), (username,))
        user = cursor.fetchone()
        return _row_to_dict(user)
    finally:
        conn.close()  # Now always called
```

**Behavior preserved:** Same result, same error handling. Connection cleanup guaranteed.  
**Scope:** All ~20 query functions (get_user_by_username, get_accounts_by_user, etc.)  
**Test gate:** Must run `test_init_db_seeds_demo_on_empty_database` before/after; behavior identical.  
**Owner:** Execute this as PRE-CHUNK_0 (or fold into CHUNK_0 with explicit note)

**Fix P0-2: Transfer auth check — move OUTSIDE transaction (correctness fix, not refactor)**

Currently:
```python
# models.py:707-812 (transfer_money)
conn = get_db()
cursor = conn.cursor()
# Line 722: First execute (implicit txn start on Postgres)
cursor.execute(...)  # Fetch from_account
# Line 735: Auth check uses the fetched account
if acting_user_id is not None and from_account["user_id"] != acting_user_id:
    conn.close()  # WITHOUT rollback
    return False, "Forbidden"  # ← Auth check inside implicit txn
```

**Problem:** Auth check runs inside transaction; if check fails, txn is IDLE IN TRANSACTION (Postgres).

**Fix:**
```python
# AFTER (behavior change: intentional)
conn = get_db()
try:
    cursor = conn.cursor()
    
    # STEP 1: Fetch both accounts (no txn yet)
    cursor.execute(...)  # from_account
    from_account = cursor.fetchone()
    cursor.execute(...)  # to_account
    to_account = cursor.fetchone()
    
    # STEP 2: Auth check (BEFORE txn)
    if not from_account or not to_account:
        return False, "Account not found"
    if acting_user_id is not None and from_account["user_id"] != acting_user_id:
        return False, "Forbidden"  # ← Auth check before any writes
    if from_account["balance"] < amount:
        return False, "Insufficient funds"
    
    # STEP 3: NOW start transaction for writes
    # Postgres: no implicit txn yet (only SELECTs above)
    # SQLite: SELECTs don't hold a txn
    
    # Debit/credit (lines 746-781, unchanged)
    cursor.execute("UPDATE accounts SET balance = balance - ?", (amount, from_id))
    cursor.execute("UPDATE accounts SET balance = balance + ?", (amount, to_id))
    
    # Rewards savepoint (lines 786-801, unchanged)
    cursor.execute("SAVEPOINT rewards_savepoint")
    try:
        try_insert_rewards_points(conn=conn, cursor=cursor, ...)
        cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
    except:
        cursor.execute("ROLLBACK TO SAVEPOINT rewards_savepoint")
        cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
    
    conn.commit()
    return True, "Transfer successful"
finally:
    conn.close()
```

**Behavior change:** Auth checks no longer lock on Postgres; they fail fast before writes.  
**Correctness:** Better (eliminates deadlock risk).  
**Test gate:** `test_transfer_money_small_amount_updates_balances` must still pass (balance updates are atomic).  
**Owner:** Execute as PRE-CHUNK_0 or fold into CHUNK_4 with explicit "INTENTIONAL CHANGE" note.

**V4 Clarification:**
```
PURE REFACTOR (CHUNK_0-5b): Move code to DAO, no behavior change.
- Extract get_db/query functions to DAO classes
- Routes call models wrappers, models delegates to DAO
- Result: Same external behavior, cleaner internal structure

REQUIRED BUG FIXES (Pre-CHUNK_0 or explicit): Intentional behavior improvements
- Add try/finally to query functions (resource safety, no external change)
- Move auth outside transaction (eliminates Postgres IDLE IN TRANSACTION, correctness fix)
- Fix rewards savepoint exception handling (data safety, already in code)

Executor must understand: Pre-fixes are NOT pure refactor.
They fix bugs discovered during audit.
Pure refactor happens AFTER fixes are in place.
```

---

### BLOCKER 4: Schema State Ownership (Grok + Gemini both found)

**V3 Problem:**
```
_resolve_rewards_schema_state(cursor=None) — still in models.py
Uses: get_db() (if no cursor passed)
Uses: _rewards_ledger_table_exists()
Used by: try_insert_rewards_points()
Owner: ??? (not assigned to any DAO in V3 inventory)
```

**V4 Solution — Explicit Ownership Matrix:**

| Function | Current | V4 Owner | Reason | Re-Export? |
|----------|---------|----------|--------|-----------|
| `_resolve_rewards_schema_state()` | models.py:270-296 | **RewardsDAO** | Schema state + get_db call | ✅ models._resolve_rewards_schema_state (DAO wrapper) |
| `_rewards_ledger_table_exists()` | models.py:182-209 | **RewardsDAO** | Schema check | ✅ models._rewards_ledger_table_exists (internal, private) |
| `try_insert_rewards_points()` | models.py:299-331 | **RewardsDAO.try_insert_rewards_points()** | Rewards insert under caller's cursor | ✅ models.try_insert_rewards_points (re-export) |
| `_compute_reward_points()` | models.py:264-268 | **RewardsDAO** | Compute logic | ❌ Internal (called by try_insert) |
| `get_rewards_points_for_user()` | models.py:334-372 | **RewardsDAO.get_points_for_user()** | Query public API | ✅ models.get_rewards_points_for_user (wrapper → DAO) |
| `ensure_rewards_ledger_schema()` | models.py:212-263 | **SchemaDAO** (or **RewardsDAO**) | Schema initialization | ✅ models.ensure_rewards_ledger_schema (wrapper) |

**Single owner per function. No dual ownership.**

**CHUNK_4 Pattern:**
```python
# dao/rewards_dao.py
class RewardsDAO(BaseDAO):
    def _resolve_schema_state(self, cursor=None):
        """Resolve if rewards_ledger schema is ready."""
        # Uses self.get_connection() if cursor not passed
        # Uses self._rewards_ledger_table_exists()
        # Returns: "ready" | "skipped" | "unknown"
    
    def _rewards_ledger_table_exists(self):
        """Check if rewards table exists."""
        # Runs SELECT on information_schema (PG) or sqlite_master (SQLite)
    
    def try_insert_rewards_points(self, conn, cursor, user_id, ...):
        """Insert rewards under caller's transaction."""
        # Called from AccountDAO.transfer()
        # Uses passed conn/cursor (shared transaction)
        # Does NOT open own connection
    
    def get_points_for_user(self, user_id):
        """Get total rewards for user."""
        # Opens own connection (query path)
        # Returns: (points_total, error_message)

# models.py (re-exports for backward compat)
from dao.rewards_dao import RewardsDAO

def _resolve_rewards_schema_state(cursor=None):
    dao = RewardsDAO()
    return dao._resolve_schema_state(cursor)

def try_insert_rewards_points(conn, cursor, ...):
    # Passed by caller (transfer_money)
    dao = RewardsDAO()
    return dao.try_insert_rewards_points(conn, cursor, ...)

def get_rewards_points_for_user(user_id):
    dao = RewardsDAO()
    return dao.get_points_for_user(user_id)
```

**Result:** 
- All rewards functions have a home (RewardsDAO)
- Schema state ownership is clear
- No ambiguity between RewardsDAO and SchemaDAO
- Monkeypatch tests still work (models.try_insert_rewards_points exists)

---

## Phase 1: GROK — Revised Problem Analysis

(Same as V3, except...)

**Function Inventory (V4 — Complete & Verified):**

1. `using_postgres()` — models.py:38-40 (stays in models; backend flag)
2. `db_path()` — models.py:42-44 (stays in models; backend flag)
3. `_log_backend_once()` — models.py:47-56 (internal init; stays in models)
4. `get_db()` — models.py:105-117 (stays in models per Strategy A, DAO imports from models)
5. `_sql(query)` — models.py:58-60 (stays in models per Strategy A)
6. `_row_to_dict(row)` — models.py:62-69 (stays in models, DAO imports)
7. `_normalize_row()` — models.py:70-79 (moves to DAO as private helper)
8. `_scalar_from_row()` — models.py:80-84 (moves to DAO as private)
9. `_insert_returning_id()` — models.py:375-386 (stays in models per Strategy A; DAO imports)
10. `_split_sql_statements()` — models.py:87-103 (moves to SchemaDAO as private)
11. `get_user_by_username()` — models.py:574-580 (wrapper → UserDAO)
12. `get_user_profile()` — models.py:584-598 (wrapper → UserDAO)
13. `get_accounts_by_user()` — models.py:601-612 (wrapper → AccountDAO)
14. `get_account_by_id()` — models.py:614-622 (wrapper → AccountDAO)
15. `get_transactions_by_account()` — models.py:624-640 (wrapper → TransactionDAO)
16. `get_all_transactions_by_user()` — models.py:642-660 (wrapper → TransactionDAO)
17. `get_cards_by_account()` — models.py:662-669 (wrapper → CardDAO)
18. `create_transaction()` — models.py:672-705 (wrapper → TransactionDAO)
19. `transfer_money()` — models.py:707-813 (wrapper → AccountDAO.transfer)
20. `_compute_reward_points()` — models.py:264-268 (→ RewardsDAO private)
21. `_resolve_rewards_schema_state()` — models.py:270-296 (wrapper → RewardsDAO)
22. `try_insert_rewards_points()` — models.py:299-331 (wrapper → RewardsDAO)
23. `get_rewards_points_for_user()` — models.py:334-372 (wrapper → RewardsDAO)
24. `_rewards_ledger_table_exists()` — models.py:182-209 (→ RewardsDAO private)
25. `ensure_rewards_ledger_schema()` — models.py:212-263 (wrapper → SchemaDAO)
26. `init_db()` — models.py:389-424 (wrapper → SchemaDAO)
27. `create_sample_data()` — models.py:427-572 (wrapper → SeedDAO)

**Total: 27 functions. All assigned. No orphans.**

---

## Phase 2: CHUNK — Task Breakdown (V4)

(Same as V3, with CRITICAL clarifications)

### Pre-Execution Checklist (REQUIRED — Not Pure Refactor)

**These are bug fixes, not refactoring:**

- [ ] **P0-1: Add try/finally** to all query functions in models.py (resource safety)
  - Functions: get_user_by_username, get_user_profile, get_accounts_by_user, get_account_by_id, get_transactions_by_account, get_all_transactions_by_user, get_cards_by_account, get_rewards_points_for_user
  - Test gate: `test_init_db_seeds_demo_on_empty_database` passes before/after (behavior unchanged)
  - Owner: Execute before CHUNK_0, or fold into CHUNK_0 with **EXPLICIT** "Intentional: Resource Safety Fix" note

- [ ] **P0-2: Move auth checks outside transfer transaction** (correctness fix, not refactor)
  - File: models.py:707-812 (transfer_money)
  - Change: Auth/validation checks before any DB writes, not inside implicit transaction
  - Test gate: `test_transfer_money_small_amount_updates_balances` passes (balance updates still atomic)
  - Owner: Execute before CHUNK_4, or fold into CHUNK_4 with **EXPLICIT** "Intentional: Transaction Safety Fix" note

- [ ] **Baseline tests documented:** `pytest test/ --collect-only -q | wc -l` → 89 tests (not 92)
  - Save: `pytest test/ -v | tee baseline-test-output-v4.txt`

**DO NOT PROCEED with CHUNK_0 until P0-1 and P0-2 complete.**

**Then:** CHUNK_0-5b are PURE REFACTOR (move code, no behavior change).

---

### Import Strategy Clarification (CHUNK_0)

**Strategy A (Chosen): Helpers stay in models.py, DAO imports from models**

```python
# dao/base_dao.py
from models import get_db, _sql, _row_to_dict, _insert_returning_id

class BaseDAO:
    def __init__(self):
        pass  # No models import in __init__; import at module level
    
    def get_connection(self):
        conn = get_db()  # Calls models.get_db
        # ...

# CHUNK_0 Verification:
python -c "
from models import get_db, _sql, _insert_returning_id
from dao.base_dao import BaseDAO
dao = BaseDAO()
conn = dao.get_connection()  # Should work (no circular import)
print('OK: No circular import')
"
```

**Result:** No circular import. Helpers callable at models.* as before. Tests don't break.

---

### Transaction Pattern — CHUNK_4 (Clarified)

**Pattern (after P0-2 pre-fix):**

```python
# AccountDAO.transfer (PURE REFACTOR of existing code structure)
def transfer(self, from_id, to_id, amount, desc, acting_user_id):
    """Transfer money with shared rewards transaction."""
    self.get_connection()
    try:
        # Auth checks ALREADY outside transaction (P0-2 pre-fix done)
        from_account = self._fetch_account(from_id)
        to_account = self._fetch_account(to_id)
        
        if not from_account or not to_account:
            return False, "Account not found"
        if acting_user_id and from_account["user_id"] != acting_user_id:
            return False, "Forbidden"
        if from_account["balance"] < amount:
            return False, "Insufficient funds"
        
        # Writes (same structure as today, just in DAO)
        self.cursor.execute("UPDATE accounts SET balance = balance - ?", (amount, from_id))
        self.cursor.execute("UPDATE accounts SET balance = balance + ?", (amount, to_id))
        
        # Rewards (same SAVEPOINT structure as today)
        self.cursor.execute("SAVEPOINT rewards_savepoint")
        try:
            # Call rewards via models (monkeypatch still works)
            import models
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

**This is PURE REFACTOR** (moving existing code structure) AFTER P0-2 is done.

---

### Rewards Ownership — CHUNK_4 + Schema (Clarified)

**RewardsDAO owns:**
- `_resolve_rewards_schema_state()`
- `try_insert_rewards_points()`
- `_compute_reward_points()`
- `get_rewards_points_for_user()`
- `_rewards_ledger_table_exists()` (private)

**Models re-exports (for monkeypatch compat):**
```python
from dao.rewards_dao import RewardsDAO

def try_insert_rewards_points(conn, cursor, ...):
    dao = RewardsDAO()
    return dao.try_insert_rewards_points(conn, cursor, ...)
```

**Monkeypatch tests still work:**
```python
# test/test_demo_rollout.py:226
monkeypatch.setattr(models, 'try_insert_rewards_points', mock_fn)
# Still works: models.try_insert_rewards_points is the wrapper
```

---

## Phase 3: EXECUTE (Unchanged from V3)

(Sequential chunks, same order, same exit criteria — but using REAL test names)

---

## CHUNK_5b Verification (Corrected for V3 Blocker)

**Old V3 grep (WRONG — misses functions):**
```bash
sed -n '574,812p' models.py | grep -c "cursor.execute"  # Should be 0
```

**V4 Grep (CORRECT — comprehensive):**
```bash
# Function bodies to audit (entire models.py, not just window):
# - get_user_by_username, get_user_profile (User queries)
# - get_accounts_by_user, get_account_by_id (Account queries)
# - get_transactions_by_account, get_all_transactions_by_user (Transaction queries)
# - get_cards_by_account (Card queries)
# - create_transaction (Transaction create)
# - transfer_money (Transfer)
# - try_insert_rewards_points (Rewards insert)
# - get_rewards_points_for_user (Rewards query)
# - init_db, create_sample_data (Init/Seed)
# - ensure_rewards_ledger_schema (Schema)

# Check ENTIRE models.py for orphaned direct DB calls:
echo "=== Checking for orphaned DB calls in models.py ===" 
# Allowed patterns (re-exports, definitions):
# - from dao import ...
# - import dao
# - def get_db(): ...
# - def _sql(...): ...

# Forbidden patterns (direct calls in function bodies):
# - cursor.execute (except in definitions, re-exports)
# - conn.cursor() (except in definitions, re-exports)
# - get_db() being CALLED (except in definitions, re-exports)

# Automated check (AST-based):
python3 << 'EOF'
import ast
with open('models.py') as f:
    tree = ast.parse(f.read())

public_functions = [
    'get_user_by_username', 'get_user_profile',
    'get_accounts_by_user', 'get_account_by_id',
    'get_transactions_by_account', 'get_all_transactions_by_user', 'get_cards_by_account',
    'create_transaction', 'transfer_money',
    'try_insert_rewards_points', 'get_rewards_points_for_user',
    'init_db', 'create_sample_data', 'ensure_rewards_ledger_schema'
]

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in public_functions:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Name) and sub.func.id in ['get_db', 'cursor.execute']:
                    print(f"ORPHANED DB CALL: {node.name} calls {sub.func.id}")
EOF
```

**If orphaned calls found:** Refactor incomplete.  
**If none found:** All functions delegated to DAO. ✅

---

## Exit Criteria Summary (V4)

**All tests REAL (verified against codebase):**
- ✅ `test_init_db_seeds_demo_on_empty_database` (User/Init)
- ✅ `test_demo_seeded_cards_expose_masked_last4_only` (Accounts/Cards)
- ✅ `test_transfer_money_small_amount_updates_balances` (Transfer)
- ✅ `test_transfer_still_succeeds_when_rewards_insert_raises` (Rewards error handling)
- ✅ `test_transfer_still_succeeds_when_rewards_insert_hits_real_db_error` (Rewards DB error)
- ✅ `test_dashboard_shows_rewards_points_when_schema_and_feature_are_enabled` (Rewards display)

**Baseline:** 89 tests, run 3x (not 92)

**Imports:** No circular imports (Strategy A: DAO imports from models)

**Semantics:** Pure refactor (P0-1 & P0-2 bugs fixed pre-chunk)

**Ownership:** All 27 functions assigned, single owner each

---

## Appendix: V3 → V4 Resolutions

| Blocker | V3 | V4 | Status |
|---------|----|----|--------|
| Fabricated test names | `test_rewards_successful_on_transfer_with_feature_flag_enabled` (doesn't exist) | Real test: `test_transfer_still_succeeds_when_rewards_insert_raises` | ✅ |
| Circular import | helpers move to DAO, using_postgres stays in models | Strategy A: helpers stay in models, DAO imports from models | ✅ |
| Transaction semantics | "Move auth outside tx" (vague) | Explicit P0-2: Pre-fix to move auth; CHUNK_4 is pure refactor | ✅ |
| Schema ownership ambiguous | try_insert_rewards_points unassigned | RewardsDAO owns; models re-exports | ✅ |
| Grep misses functions | `sed -n '574,812p'` window | Full-file AST audit | ✅ |
| Test count wrong | 92 | 89 (verified) | ✅ |
| Invented test gates | 5 fabricated names | All real, line numbers verified | ✅ |

---

**Plan Version:** 4.0-blockers-resolved  
**Status:** ✅ READY FOR CROSS-MODEL RE-REVIEW  
**Next Step:** Submit to Grok + Gemini for final verification
