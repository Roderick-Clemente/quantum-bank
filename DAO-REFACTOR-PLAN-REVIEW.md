# Adversarial Review: DAO Refactor Plan

**Date:** 2026-08-12  
**Branch:** `feature/quantum-dao-refactor`  
**Plan:** `DAO-REFACTOR-PLAN.md`  
**Reviewers:** 3 independent agents (Completeness, Correctness, Test Coverage)  
**Review Method:** Parallel audit with independent prompts, no plan bias

---

## Executive Summary

**Plan Status:** SOUND IN STRUCTURE, INCOMPLETE IN SCOPE

The DAO refactor plan is well-designed for its stated 6 chunks (User → Account → Transaction → Transfer/Rewards → Cleanup). However:

- ⚠️ **Scope Gap:** Plan misses ~260 lines of initialization/schema setup code
- 🚩 **Hidden Contradictions:** Plan claims "zero test changes" but tests import models functions that may move
- 🔴 **Existing Bugs:** Current codebase has resource leaks and transaction safety issues that refactor could surface
- ✅ **Fixable:** All gaps are addressable with plan revisions before execution

**Recommendation:** Revise plan to clarify scope boundary and test helper lifecycle, then re-review before execution.

---

## REVIEWER 1: Completeness & Call Sites Audit

**Agent:** a2c1733f55a55639f  
**Duration:** 152 min  
**Method:** Grep all DB patterns, map functions to chunks, identify edge cases

### Critical Findings

#### FINDING 1.1: CRITICAL — Missed Function: `create_sample_data()`

**Category:** Completeness | Call Site  
**Severity:** CRITICAL

**Issue:** Function `create_sample_data()` (models.py:427-572) contains **145 lines + ~30 direct `cursor.execute()` calls**. Called during app initialization (app.py:58 → init_db).

**Evidence:**
```python
# models.py:427
def create_sample_data(conn):
    # Line 429: conn.cursor()
    # Lines 434, 443, 452, 461, 497, 526, 549, 563: cursor.execute()
    # Creates sample users, accounts, transactions, cards
```

**Impact:** After executing all 5 chunks, this function will still bypass DAO layer entirely. Violates core success criterion: "zero direct `conn.cursor()` calls outside DAO."

**Plan Claim vs. Reality:**
- Plan line 45: "All database calls routed through DAO interface (zero direct calls outside DAO)"
- Reality: `create_sample_data()` orphaned, ~30 calls unrouted
- **Verdict:** Success criterion NOT achievable as written

---

#### FINDING 1.2: HIGH — Initialization Functions Not Covered

**Category:** Completeness | Call Site  
**Severity:** HIGH

**Missed Functions:**
- `ensure_rewards_ledger_schema()` (models.py:212-296, 85 lines)
- `_apply_postgres_schema()` (models.py:120-129)
- `_create_sqlite_schema()` (models.py:132-180)
- `_rewards_ledger_table_exists()` (models.py:182-209)
- `init_db()` (models.py:389-424) — orchestration only

**Impact:** Schema initialization happens at app startup, bypasses DAO. These functions called once per app boot, not per request, but still violate scope.

**Evidence:**
```python
# models.py:120-129 (_apply_postgres_schema)
def _apply_postgres_schema(conn) -> None:
    path = os.path.join(MIGRATIONS_DIR, "001_initial.sql")
    # ...
    cursor = conn.cursor()  # Direct cursor
    for statement in _split_sql_statements(sql):
        cursor.execute(statement)  # Direct execution
    conn.commit()
```

**Total orphaned DB calls:** ~260 lines across initialization functions.

---

#### FINDING 1.3: HIGH — Unclear Helper Function Placement

**Category:** Completeness | Architectural Clarity  
**Severity:** HIGH

**Issue:** Plan says helpers like `_insert_returning_id()` will be "reused" (plan line 881) but doesn't specify where they live after refactor.

**Functions Affected:**
- `_insert_returning_id(cursor, sql, params)` (models.py:375-386) — makes direct `cursor.execute()` calls
- `_row_to_dict(row)` (models.py:62-69)
- `_normalize_row(row_dict)` (models.py:70-79)
- `_sql(query)` (models.py:58-60)

**Current Usage:**
```python
# models.py:683-690 (in create_transaction)
transaction_id = _insert_returning_id(
    cursor,
    "INSERT INTO transactions (...) VALUES (...)",
    (account_id, transaction_type, amount, description, recipient),
)

# test/test_banking_routes.py:342, 350 (tests use it)
attacker_user_id = models._insert_returning_id(cursor, sql, params)
```

**Questions Plan Doesn't Answer:**
- Does `_insert_returning_id()` move into TransactionDAO?
- Or stay in models.py and get called by DAO?
- If it moves to DAO, will tests importing `models._insert_returning_id` break?
- If it stays, do we still have direct `cursor.execute()` calls in models.py?

**Verdict:** Architectural unclear; creates import/circular dependency risk.

---

#### FINDING 1.4: HIGH — Test Fixtures Use Direct DB Calls

**Category:** Completeness | Test Risk  
**Severity:** HIGH

**Issue:** Test files make direct DB calls NOT covered in any chunk:

**Evidence:**
```python
# test/conftest.py:69-73 (Postgres backend)
with conn.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS rewards_ledger")

# test/test_banking_routes.py:339-360 (test setup)
conn = models.get_db()
cursor = conn.cursor()
# ...
attacker_user_id = models._insert_returning_id(cursor, sql, params)

# test/test_a_models_bootstrap.py:195-232 (schema introspection)
conn = models.get_db()
cursor = conn.cursor()
cursor.execute(...)  # PRAGMA / information_schema queries
```

**Impact:** Tests bypass models.py functions entirely, go straight to `get_db()` and `cursor.execute()`. Plan says "test isolation maintained" but doesn't address this.

**Tests Using Direct DB Calls:**
- `test/conftest.py` (cleanup fixture)
- `test/test_banking_routes.py` (auth bypass test setup)
- `test/test_api_routes.py` (auth bypass test setup)
- `test/test_a_models_bootstrap.py` (schema tests)
- `test/test_profile_route.py` (fixture setup)

---

### Verdict: Completeness Review

**Status:** ⚠️ PLAN INCOMPLETE

Plan is **85% complete** but misses critical edge cases:
- Chunks 1-4 correctly identify main query/mutation functions (~92 lines refactored properly)
- Initialization and schema setup (~260 lines) orphaned
- Test fixtures bypass DAO (not breaking, but architectural gap)
- Helper functions' final location unclear

**Executing plan as written will NOT achieve stated goal** of "zero direct `conn.cursor()` calls outside DAO."

---

## REVIEWER 2: Correctness & State Bug Audit

**Agent:** adce6f398f7d0f124  
**Duration:** 88 min  
**Method:** Read actual code, analyze transaction safety, connection lifecycle, authorization checks

### Critical Findings

#### FINDING 2.1: CRITICAL — Resource Leak in Query Functions

**Category:** Connection Safety  
**Severity:** CRITICAL

**Issue:** ~20 simple query functions have no try/finally; if `cursor.execute()` raises exception, `conn.close()` never called.

**Evidence:**
```python
# models.py:574-580 (get_user_by_username)
def get_user_by_username(username: str) -> dict | None:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql("SELECT * FROM users WHERE username = ?"), (username,))
    user = cursor.fetchone()
    conn.close()  # ← NOT in try/finally
    return _row_to_dict(user)
```

**Affected Functions:** get_user_profile, get_accounts_by_user, get_account_by_id, get_transactions_by_account, get_all_transactions_by_user, get_cards_by_account, and ~15 more.

**Scenario:** Network flake, DB connection timeout, SQL syntax error mid-query → exception raised → `conn.close()` skipped → connection stays open → connection pool exhaustion (if pooling added later) → cascading failures.

**Current Workaround:** This "works" in production because:
- SQLite (local) rarely times out
- Postgres connections have statement_timeout
- Low concurrency masks resource leak

**Refactor Impact:** If DAO extraction doesn't add try/finally blocks, bugs persist or worsen.

---

#### FINDING 2.2: CRITICAL — Transaction Safety: Auth Check Inside Transaction

**Category:** Transaction Safety  
**Severity:** CRITICAL

**Issue:** In `transfer_money()`, authorization check happens INSIDE transaction scope without explicit rollback on auth failure.

**Evidence:**
```python
# models.py:721-744
try:
    cursor.execute(...)  # Fetch from_account
    from_account = _normalize_row(_row_to_dict(cursor.fetchone()))
    
    cursor.execute(...)  # Fetch to_account
    to_account = _row_to_dict(cursor.fetchone())
    
    if not from_account or not to_account:
        conn.close()  # Line 735: NO ROLLBACK
        return False, "Account not found"
    
    if acting_user_id is not None and from_account["user_id"] != acting_user_id:
        conn.close()  # Line 739: NO ROLLBACK
        return False, "Forbidden"
    
    if from_account["balance"] < amount:
        conn.close()  # Line 743: NO ROLLBACK
        return False, "Insufficient funds"
    
    # THEN start actual writes (lines 746-782)
    cursor.execute("UPDATE accounts SET balance = balance - ?")
    cursor.execute("UPDATE accounts SET balance = balance + ?")
```

**Scenario (Postgres):**
1. Transaction starts implicitly when first `execute()` runs (line 722)
2. Auth check fails at line 738
3. Calls `conn.close()` WITHOUT explicit rollback
4. **Result:** PostgreSQL keeps IDLE IN TRANSACTION state visible in `pg_stat_activity` → blocking locks → cascading failures

**Why It "Works" Today:**
- SQLite autocommits after each statement, so implicit rollback happens
- Postgres behavior hidden (doesn't visibly fail, just locks)

**Refactor Hazard:** If DAO uses explicit connection management or connection pooling, this pattern surfaces as deadlock.

---

#### FINDING 2.3: HIGH — Rewards Savepoint Exception Handling Fragile

**Category:** Transaction Safety  
**Severity:** HIGH

**Issue:** Rewards insertion uses savepoints but exception handling can fail.

**Evidence:**
```python
# models.py:786-801
cursor.execute("SAVEPOINT rewards_savepoint")
try:
    try_insert_rewards_points(...)
    cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
except Exception:
    cursor.execute("ROLLBACK TO SAVEPOINT rewards_savepoint")
    cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
conn.commit()  # ← Commits even if savepoint handling failed
```

**Scenario:** If inner exception block itself fails (e.g., `ROLLBACK TO SAVEPOINT` rejected), outer `conn.commit()` still executes → commits partial transfer + corrupt rewards state.

---

#### FINDING 2.4: HIGH — Authorization Check No Defense-in-Depth

**Category:** Data Corruption | Security  
**Severity:** HIGH

**Issue:** `get_account_by_id()` returns account info without user_id verification. Routes check ownership themselves.

**Evidence:**
```python
# models.py:614-621
def get_account_by_id(account_id: int) -> dict | None:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql("SELECT * FROM accounts WHERE id = ?"), (account_id,))
    account = cursor.fetchone()
    conn.close()
    return _normalize_row(_row_to_dict(account))
```

**Risk:** If route handler forgets to check `account["user_id"] == session["user_id"]`, attacker can view/transfer other users' accounts.

**Test Evidence:** Explicit test exists (`test_transfer_post_rejects_cross_user_source_account`), meaning route DOES check, but DAO doesn't enforce it.

---

#### FINDING 2.5: MEDIUM — Global Race Condition in Rewards Schema State

**Category:** Data Corruption  
**Severity:** MEDIUM

**Issue:** `_rewards_schema_state` global variable has race condition on concurrent requests.

**Evidence:**
```python
# models.py:34-35
_rewards_schema_state = "unknown"

# models.py:275-296
def _resolve_rewards_schema_state(cursor=None) -> str:
    global _rewards_schema_state
    if _rewards_schema_state != "unknown":
        return _rewards_schema_state  # ← Uses potentially stale value
    # ... expensive check ...
    _rewards_schema_state = "ready" or "skipped"
    return _rewards_schema_state
```

**Scenario:** Two concurrent requests both see `_rewards_schema_state == "unknown"` → both run expensive check → race on global update → one overwrites other → stale state.

---

### Mandatory Refactor Changes (To Pass Audit)

Before DAO extraction, code must be fixed:

1. **Add try/finally to all query functions:**
   ```python
   def get_user_by_username(username: str) -> dict | None:
       conn = get_db()
       try:
           cursor = conn.cursor()
           cursor.execute(_sql("SELECT * FROM users WHERE username = ?"), (username,))
           return _row_to_dict(cursor.fetchone())
       finally:
           conn.close()
   ```

2. **Move auth checks OUTSIDE transaction:**
   ```python
   # Step 1: Auth check (no transaction)
   if not _check_ownership(...):
       return False, "Forbidden"
   
   # Step 2: Start transaction for writes
   conn.begin()
   try:
       cursor.execute("UPDATE ...")
       conn.commit()
   except Exception:
       conn.rollback()
       raise
   ```

3. **Add explicit rollback on rewards savepoint failure**

4. **Fix global race condition** (use thread-local or connection-scoped state)

---

### Verdict: Correctness Review

**Status:** 🚩 CRITICAL BUGS FOUND

The refactor CAN succeed, but **CHUNK_4 (transfer) requires extreme care**. Current code has:
- **CRITICAL:** Resource leaks in 20+ functions
- **CRITICAL:** Transaction safety issues in transfer path
- **HIGH:** Data corruption scenarios (savepoint, authorization, race condition)

**Implementation Risk: MEDIUM-HIGH**

Recommendation: Before executing CHUNK_4, either:
1. Fix these bugs in current code (bigger refactor, safer)
2. Fix them during DAO extraction (smaller chunks, but more careful)
3. Add explicit test for each scenario (verify fixes work)

---

## REVIEWER 3: Test Coverage & Verification Gaps Audit

**Agent:** a6d4bf59112bbe9c6  
**Duration:** 136 min  
**Method:** Inventory tests, audit critical paths, identify contradictions, check isolation

### Critical Findings

#### FINDING 3.1: CRITICAL — Plan Claims "Zero Test Changes" But Tests Import Models Functions Directly

**Category:** Contradiction | Test Risk  
**Severity:** CRITICAL

**Issue:** Plan line 56 says "Only modify tests if they break due to import changes (should be rare)." But tests import models functions that plan may move to DAO.

**Functions Tests Import:**
- `models.get_db()` (used in 4 test files directly)
- `models._insert_returning_id()` (used in 2 test files)
- `models._sql()` (monkeypatched in test_demo_rollout.py)
- `models._row_to_dict()` (used in 1 test file)

**Evidence:**
```python
# test/test_banking_routes.py:339-360
conn = models.get_db()  # ← Direct import
cursor = conn.cursor()
attacker_user_id = models._insert_returning_id(cursor, sql, params)  # ← Direct import

# test/test_api_routes.py:286-307
conn = models.get_db()  # ← Direct import

# test/test_profile_route.py:18
from models import _row_to_dict
result = _row_to_dict(row)  # ← Direct import

# test/test_demo_rollout.py:226-258
with unittest.mock.patch("models._sql") as mock_sql:  # ← Monkeypatched
```

**Contradiction:** If these functions move to DAO layer (to be called by DAO), tests will break:
- `test_banking_routes.py:339` will fail with `AttributeError: module models has no attribute get_db`
- Test setup will fail, cascading to all dependent tests

**Plan's Hidden Assumption:** These functions stay as public wrappers in models.py.

**Verdict:** Plan needs explicit clarification: Do helpers stay public or move to DAO? This determines test changes needed.

---

#### FINDING 3.2: HIGH — Missing Critical Test: Transfer Rollback

**Category:** Coverage Gap | Safety  
**Severity:** HIGH

**Issue:** Plan mentions (line 109) "Test rollback paths explicitly" but **zero tests exist** for transfer rollback scenario.

**What's Tested:**
- Happy path transfer ✓
- Insufficient funds ✓
- Invalid amount ✓
- Cross-user rejection ✓
- Same account rejection ✓

**What's NOT Tested:**
- Transfer fails mid-execution (simulated DB error) ✓ ✗
- Verify balances unchanged if transaction rolls back ✗
- Verify rewards ledger not partially written ✗

**Impact:** After refactor, if DAO transaction handling is wrong, test won't catch it. Silent data corruption risk.

**Recommended Test:**
```python
def test_transfer_rollback_on_db_error(client):
    # Mock cursor.execute to fail on second UPDATE
    # Verify: from_account balance unchanged, to_account balance unchanged
```

---

#### FINDING 3.3: HIGH — Missing Test: SQL Backend Compatibility

**Category:** Coverage Gap | Backend Risk  
**Severity:** HIGH

**Issue:** Plan claims (line 109) "Test both backends (local SQLite + CI Postgres)" but tests only check **flag detection**, not **query behavior differences**.

**Test Evidence:**
```python
# test/test_a_models_bootstrap.py:73-94
# Tests: is_postgres_database_enabled() returns correct flag
# Does NOT test: SELECT with different syntax works on both
```

**Risk:** Refactored DAO could have query differences that pass SQLite but fail Postgres (or vice versa):
- `_sql()` helper converts `?` to `%s`
- `RealDictCursor` vs `sqlite3.Row` row type differences
- `RETURNING` clause syntax differences

**Missing test:**
```python
def test_account_queries_work_on_both_sqlite_and_postgres():
    # Run query on both backends, verify same results
```

---

#### FINDING 3.4: HIGH — Test Isolation: Module-Scoped Fixtures Create Race Risk

**Category:** Isolation Issue | Flakiness Risk  
**Severity:** HIGH

**Issue:** Two test files use `scope="module"` fixtures that run initialization once for entire module:

**Evidence:**
```python
# test/test_profile_model.py:8-11
@pytest.fixture(scope="module", autouse=True)
def seeded_demo_user():
    models.init_db()  # ← Runs ONCE for all tests in module

# test/test_profile_seed.py:10-13
@pytest.fixture(scope="module", autouse=True)
def seeded_demo_user():
    models.init_db()  # ← Runs ONCE for all tests in module
```

**Refactor Risk:** If DAO connection caching has a bug, or if `init_db()` behavior changes, module-scoped fixture runs it once and all tests in module share state.

**Failure Scenario:**
- Test A (module scope) initializes with DAO
- Test B (in same module) expects fresh schema
- Schema cache persists across tests
- Test B fails in suite, passes when run alone (order-dependent flakiness)

---

#### FINDING 3.5: HIGH — Test Authorization Checks Use Direct DB (Not Through DAO)

**Category:** Coverage Gap | Architectural  
**Severity:** HIGH

**Issue:** Security tests that verify authorization bypass directly use `models.get_db()`, bypassing the DAO they're supposed to test.

**Evidence:**
```python
# test/test_banking_routes.py:331
def test_transfer_post_rejects_cross_user_source_account(client):
    # Setup: Create attacker user via DIRECT DB
    conn = models.get_db()
    attacker_user_id = models._insert_returning_id(...)
    
    # Test: Transfer from attacker account should fail
    response = client.post("/transfer", ...)
    assert response.status_code == 403
```

**Issue:** Test seeds data via direct DB call, but tests authorization check through DAO (implicitly, via route). If DAO has different authorization logic, test might pass but DAO is broken.

**Verdict:** Tests check route logic, not DAO logic. After refactor, need DAO-layer tests for authorization.

---

#### FINDING 3.6: MEDIUM — Verification Grep Checks Miss Test Files

**Category:** Verification Gap  
**Severity:** MEDIUM

**Issue:** Plan's grep verification (lines 559-578) searches only `models.py` and `api/`, not `test/`:

**Plan's Checks:**
```bash
grep -n "get_db()" models.py  # Should only appear in definition
grep -rn "cursor.execute" models.py  # Should not appear
```

**What They Miss:**
```python
# test/test_banking_routes.py:339 — NOT caught
conn = models.get_db()

# test/test_a_models_bootstrap.py:195 — NOT caught
models.get_db()

# test/conftest.py:69 — NOT caught
cursor.execute("DROP TABLE...")
```

**Missing Verification:**
```bash
# Check DB calls outside dao/ AND models.py:
grep -rn "\.execute(" test/ --include="*.py" | grep -v "# expected" 
grep -rn "conn = models.get_db()" test/  # Allowed if intentional
```

---

### Verdict: Test Coverage Review

**Status:** ⚠️ CONTRADICTIONS + GAPS

**Baseline Coverage:** Excellent ✓
- 92 total tests across 9 files
- Good HTTP integration coverage via Flask client
- Critical paths tested (login, dashboard, transfer, profile)

**Plan Contradictions:** Confirmed
- Claims "zero test changes" but tests import functions that may move
- Claims test helpers "reused" but location ambiguous
- Claims "helpers in DAO" but tests call `models._insert_returning_id()` directly

**Coverage Gaps:** Confirmed
- No transfer rollback test
- No SQL backend compatibility test (query behavior)
- No schema-missing fallback test
- Module-scoped fixtures risk order-dependent flakiness

**Execution Safety Risk:** MEDIUM
- Sequential chunk execution helps catch issues early
- But module-scoped fixtures + DAO connection caching could mask bugs
- No explicit "abort if tests fail" rule (should be added to plan)

---

## CONSOLIDATED RISK MATRIX

| # | Category | Finding | Severity | Current Impact | Refactor Impact | Blocker? |
|----|----------|---------|----------|---------------|----|----------|
| **1.1** | Completeness | Missed `create_sample_data()` function (~145 lines) | CRITICAL | None (boot-time) | Orphaned ~30 DB calls | YES |
| **1.2** | Completeness | Schema setup functions not in plan (~85 lines) | HIGH | None (boot-time) | Orphaned DB calls | YES |
| **1.3** | Clarity | Helper function placement unclear (`_insert_returning_id()`) | HIGH | None | Import/dependency risk | YES |
| **1.4** | Coverage | Test fixtures bypass DAO | HIGH | Tests work | Tests skip DAO layer | NO |
| **2.1** | Connection Safety | Resource leak (~20 functions, no try/finally) | CRITICAL | Connection exhaustion on error | Persistent/worsened | YES |
| **2.2** | Transaction Safety | Auth check inside transaction, no rollback | CRITICAL | Locks on auth failure | Data corruption risk | YES |
| **2.3** | Transaction Safety | Rewards savepoint exception handling fragile | HIGH | Rare data corruption | Cascading failure | YES |
| **2.4** | Security | No defense-in-depth auth in `get_account_by_id()` | HIGH | Cross-user access if route forgets check | DAO layer doesn't enforce | NO |
| **2.5** | Race Condition | Global `_rewards_schema_state` variable | MEDIUM | Stale schema state (rare) | Worse with connection pooling | NO |
| **3.1** | Contradiction | "Zero test changes" but tests import models functions | CRITICAL | Tests work today | Tests break if functions move | YES |
| **3.2** | Coverage Gap | No transfer rollback test | HIGH | Can't verify transaction safety | Can't verify DAO rollback | NO |
| **3.3** | Coverage Gap | No SQL backend compatibility test | HIGH | Hidden bugs on Postgres | Can't verify DAO query diffs | NO |
| **3.4** | Isolation | Module-scoped fixtures create flakiness risk | HIGH | Order-dependent test failures | Worse with connection caching | NO |
| **3.5** | Coverage Gap | Auth tests use direct DB, not DAO | MEDIUM | Tests check routes, not DAO | Need DAO-layer auth tests | NO |
| **3.6** | Verification | Grep checks miss test files | MEDIUM | Silent pass on orphaned calls | Incomplete verification | NO |

---

## Key Questions for Plan Revision

### Scope Boundary (Reviewer 1)
1. Should `create_sample_data()` move into a DataSeedDAO?
2. Should schema functions (init_db, ensure_rewards_ledger) be in a separate chunk?
3. Are test fixtures intentionally excluded from DAO scope?

### Test Helper Lifecycle (Reviewers 1 & 3)
1. Where does `_insert_returning_id()` live after refactor?
2. Do helper functions (`_row_to_dict`, `_sql`, etc.) move to DAO or stay in models.py?
3. If they stay in models.py, do tests update import paths or keep using `models.`?

### Existing Bugs (Reviewer 2)
1. Should refactor also FIX resource leaks (add try/finally) or just move code?
2. Should transaction safety bugs be fixed before CHUNK_0 or during CHUNK_4?
3. Should global race condition be addressed in DAO layer or models.py?

### Test Strategy (Reviewer 3)
1. Which tests need updates (tests importing moved functions)?
2. Should we add 3 new tests (rollback, backend compatibility, schema resilience)?
3. Should module-scoped fixtures be changed to function-scoped?

---

## Recommendations (Priority Order)

### CRITICAL (Must do before execution)
1. **Clarify scope:** Add CHUNK_5a for initialization, or explicitly exclude it with rationale
2. **Document helper lifecycle:** Create table showing where each helper function lives (models vs. DAO)
3. **Fix test contradiction:** Specify whether tests will need changes or helpers stay public

### HIGH (Should do before execution)
4. **Fix existing bugs:** Add try/finally to query functions before DAO extraction
5. **Revise transaction logic:** Move auth checks outside transaction scope
6. **Add test strategy:** Specify which tests need updates, add 3 critical missing tests

### MEDIUM (Nice to have)
7. **Fix module-scoped fixtures:** Change to function-scoped to prevent flakiness
8. **Update grep verification:** Add test file checks to catch orphaned calls
9. **Document rollback procedure:** Detail how to rollback partial refactor safely

---

## Reviewers' Collective Verdict

**Plan Structure:** ✅ Sound (6 chunks well-sequenced, dependencies clear)

**Plan Scope:** ⚠️ Incomplete (misses initialization, schema setup)

**Plan Accuracy:** ⚠️ Contains hidden assumptions (helper location, test changes)

**Code Quality:** 🚩 Current codebase has bugs that refactor could surface

**Test Strategy:** ⚠️ Good baseline, but gaps in critical scenarios

---

**RECOMMENDATION:** Revise plan based on findings, then re-review before execution.

**ESTIMATED REVISION EFFORT:** 2-4 hours (clarify scope, document helpers, add tests)

**EXECUTION SAFETY AFTER REVISION:** Medium-High (can be mitigated with careful chunking + frequent test runs)

---

**End of Adversarial Review**
