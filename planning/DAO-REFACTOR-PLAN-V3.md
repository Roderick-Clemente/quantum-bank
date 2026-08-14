# AI Sprint Planning — QuantumBank DAO Refactor (V3)

**Adapted from:** `.local/planning/ai-sprints/SPRINT-PLANNING-TEMPLATE.md` (v1.0-qb)  
**Status:** REVISED AFTER CROSS-MODEL REFEREE FEEDBACK  
**Review Cycle:** Plan → Claude audit → Grok/Gemini ref → Revised Plan (V3)

---

## Sprint Metadata

**Sprint Name:** QuantumBank DAO Pattern Refactor (V3 — Referee Integrated)
**Date:** 2026-08-12
**Sprint Type:** Refactor
**Priority:** P2-Medium
**Estimated Duration:** 1.5-2 days (extended for transaction architecture)
**Status:** Ready for Execution (after ref integration)
**Branch:** `feature/quantum-dao-refactor` off `feat/user-profile`

**Revisions Applied (V2 → V3):**
- ✅ CHUNK_5a added to Phase 2 Task Breakdown (was in scope, not in execution)
- ✅ Transfer signature includes `acting_user_id` (matches real code, not invented)
- ✅ Helpers as module-level functions, not instance methods (re-export compatible)
- ✅ Explicit connection-sharing pattern for AccountDAO ↔ RewardsDAO (ACID preservation)
- ✅ Cards promoted to first-class entity (CHUNK_2c — new)
- ✅ Real test names (no more "if exists" hypotheticals)
- ✅ PostgreSQL verification as hard exit criterion
- ✅ Removed invented `update_balance()` task
- ✅ Cleanup greps rewritten for re-export reality
- ✅ Function count enumerated (not estimated)

**Ref Verdict:** V2 was REJECTED by Grok & Gemini. V3 addresses all BLOCKERS and HIGH findings.

---

## Sprint Principles

- **Low-token execution:** Plan once, execute in small chunks with minimal context.
- **Standardized practice:** Embed testing, flagging, and release discipline in the plan.
- **Audit trail:** Each chunk leaves clear evidence for review and future reference.
- **TDD-first (Red-Green-Refactor):** Write failing tests before implementation when behavior changes.
- **Zero Behavior Change:** This is a pure refactor — all existing tests must pass unchanged.
- **Adversarial review validated:** Plan reviewed by independent agents + cross-model referee; contradictions resolved.
- **Architectural clarity:** Transaction boundaries, connection sharing, and helper placement explicit.

### Refactor Principles

```
1. TEST BASELINE → Ensure all existing tests pass (green)
2. EXTRACT → Extract DAO interface and implementations (tests stay green)
3. MIGRATE → Route calls through DAO one entity at a time (tests stay green)
4. VERIFY → Run full test suite + manual smoke test after each chunk
5. CLEANUP → Remove old direct DB code once fully migrated
```

---

## Sprint Objectives

### Primary Goal

Extract all database interactions from `models.py` into a clean DAO layer, improving testability and maintainability without changing any external behavior. **Complete scope includes initialization/schema setup (CHUNK_5a). Transaction atomicity preserved across multi-DAO operations (CHUNK_4).**

### Success Criteria

- [ ] All database calls routed through DAO interface (zero direct `conn.cursor()` calls in models.py query bodies)
- [ ] All existing tests pass unchanged (pytest test/ -v shows 100% green)
- [ ] Manual smoke test confirms login, dashboard, transfer, profile all work
- [ ] DAO layer supports both SQLite and PostgreSQL backends (verified CI job passes)
- [ ] Connection management centralized in DAO (no scattered `conn.close()` calls in models bodies)
- [ ] Test helpers re-exported from models.py (zero test import changes required)
- [ ] **3 critical tests passing:** rollback, backend compatibility, schema resilience
- [ ] **Transaction atomicity verified:** transfer + rewards share single connection, rollback works
- [ ] **All 6 chunks executed and committed** with tests green after each

### Scope (V3 — Complete & Verified)

**IN SCOPE:**
- User queries (CHUNK_1): `get_user_by_username`, `get_user_profile`
- Account queries (CHUNK_2): `get_accounts_by_user`, `get_account_by_id`
- **Cards queries (CHUNK_2c — NEW):** `get_cards_by_account`
- Transaction queries (CHUNK_3): `get_transactions_by_account`, `get_all_transactions_by_user`, `create_transaction`
- Transfer + rewards (CHUNK_4): `transfer_money`, `get_rewards_points_for_user`, `try_insert_rewards_points` (shared transaction)
- **Schema & Initialization (CHUNK_5a — EXPLICIT):** `init_db`, `create_sample_data`, `ensure_rewards_ledger_schema`, `_apply_postgres_schema`, `_create_sqlite_schema`
- Helper functions (module-level, re-exported):
  - `get_db()` → move to `dao/connection_manager.py`, re-export from models.py
  - `_sql()` → move to `dao/base_dao.py` (module-level), re-export from models.py
  - `_insert_returning_id()` → move to `dao/base_dao.py` (module-level), re-export from models.py
  - `_row_to_dict()` → move to `dao/base_dao.py` (module-level), re-export from models.py
  - `_normalize_row()` → move to `dao/base_dao.py` (module-level, not re-exported; internal only)
  - `using_postgres()`, `db_path()` → stay in models.py (backend selection, not migration-owned)
  - `_split_sql_statements()` → move to `dao/schema_dao.py` (schema-specific)
  - `_scalar_from_row()` → move to `dao/base_dao.py` (module-level, used by seed gate)

**OUT OF SCOPE:**
- **Performance tuning:** No connection pooling, query optimization, or caching
- **Schema changes:** No new tables, columns, or migrations (only refactor existing)
- **Business logic changes:** No new features, validations, or workflows
- **API changes:** No route modifications, request/response format changes
- **Error handling improvements:** Keep existing error patterns (except add try/finally for safety)
- **Frontend changes:** No template, static file, or JavaScript modifications

---

## Phase 1: GROK — Problem Analysis

### Context & Background

**Current State — Inventory of Database Functions (V3 — Explicit Count):**

**Query Functions (read-only):**
1. `get_user_by_username(username)` — login path
2. `get_user_profile(user_id)` — profile page
3. `get_accounts_by_user(user_id)` — dashboard, transfer, API
4. `get_account_by_id(account_id)` — account detail
5. `get_transactions_by_account(account_id, limit)` — account detail
6. `get_all_transactions_by_user(user_id, limit)` — dashboard, API
7. `get_cards_by_account(account_id)` — account detail (live, not dead code)
8. `get_rewards_points_for_user(user_id)` — dashboard

**Mutation Functions (write):**
9. `create_transaction(account_id, type, amount, desc, recipient)` — internal, used by transfer
10. `transfer_money(from_id, to_id, amount, desc, acting_user_id)` — core business logic
11. `try_insert_rewards_points(conn, cursor, ...)` — called by transfer under shared txn

**Initialization Functions (startup):**
12. `init_db()` — app startup orchestration
13. `create_sample_data(conn)` — seed test data
14. `ensure_rewards_ledger_schema(conn)` — feature-gated schema setup
15. `_apply_postgres_schema(conn)` — Postgres-specific schema
16. `_create_sqlite_schema(cursor)` — SQLite-specific schema
17. `_rewards_ledger_table_exists(cursor)` — schema check

**Helper Functions (utilities):**
18. `get_db()` — connection factory
19. `_sql(query)` — Postgres/SQLite query converter
20. `_insert_returning_id(cursor, sql, params)` — INSERT RETURNING helper
21. `_row_to_dict(row)` — row-to-dict converter
22. `_normalize_row(row_dict)` — type normalization (Decimal → float)
23. `_scalar_from_row(row)` — extract single value
24. `_split_sql_statements(sql)` — migration file parser
25. `_rewards_ledger_table_exists(cursor)` — existence check

**Total scope: ~25 functions across 4 categories.**

**Pattern (all follow open → execute → close):**
```python
def get_user_by_username(username: str) -> dict | None:
    conn = get_db()              # Direct connection
    cursor = conn.cursor()        # Direct cursor
    cursor.execute(_sql("SELECT * FROM users WHERE username = ?"), (username,))
    user = cursor.fetchone()
    conn.close()                  # Manual cleanup (NO try/finally — resource leak!)
    return _row_to_dict(user)
```

**Why Refactor:**
- **Testability:** Hard to unit test without DB
- **Maintainability:** 813 lines in one file
- **Resource safety:** Missing try/finally on ~20 functions
- **Transaction safety:** Auth checks inside transaction without explicit rollback
- **Initialization code scattered:** init, schema, seed not in DAO

---

### Root Cause Analysis

**Core Problems:**
1. No abstraction boundary between "what to fetch" (business logic) and "how to fetch" (data access)
2. Connection management duplicated across ~25 functions
3. Initialization code bypasses abstraction
4. Transaction boundaries not enforced (transfer + rewards share connection in ad-hoc way)
5. Test fixtures directly access `get_db()`, creating tight coupling

**Ref Feedback Surfaced:**
- Helper functions must remain module-level (not instance methods) for re-export compatibility
- Transaction atomicity requires connection sharing across AccountDAO ↔ RewardsDAO (not separate connections)
- Cards are a first-class entity, not a second-class path
- CHUNK_5a scope was stated but not in execution plan (architectural gap)

---

### Risk Assessment (V3 — Integrated from Ref)

| Risk | Severity | Probability | Impact | Mitigation (V3) |
|------|----------|-------------|--------|---|
| **Resource leak** (~20 functions, no try/finally) | CRITICAL | HIGH | Connection exhaustion | • Add try/finally to all DAO functions<br>• Test exception paths |
| **Transaction safety** (auth inside tx, no rollback) | CRITICAL | MEDIUM | IDLE IN TRANSACTION locks | • Move auth outside transaction<br>• Explicit rollback on failure |
| **Transaction atomicity split** (separate DAO connections) | CRITICAL | HIGH | Rewards insert on 2nd connection, broken ACID | • **V3: Explicit connection-sharing pattern**<br>• AccountDAO.transfer passes conn to RewardsDAO<br>• Savepoint/rollback under shared cursor |
| **Helper re-export breaks** (instance methods instead of module-level) | HIGH | MEDIUM | Tests import models.\_sql, fails | • **V3: Helpers as module-level functions**<br>• Re-export from models.py<br>• No behavior change |
| **CHUNK_5a scope/execution mismatch** | HIGH | HIGH | Init code orphaned, success criterion fails | • **V3: CHUNK_5a in task breakdown**<br>• Explicit migration steps |
| **Cards path missed** (treated as dead code) | HIGH | MEDIUM | Account detail keeps non-DAO path | • **V3: CHUNK_2c for CardDAO**<br>• Include in account detail verification |
| **Test names hypothetical** (if exists) | MEDIUM | MEDIUM | Wrong/missing gates during execution | • **V3: Real test names (no more 'if exists')**<br>• Named exits for each edge case |
| **PostgreSQL optional** (if testable) | HIGH | HIGH | PG regressions ship to prod | • **V3: Hard exit criterion**<br>• CI Postgres job must pass |
| **Invented tasks** (update_balance doesn't exist) | MEDIUM | MEDIUM | Executor creates dead code | • **V3: Removed update_balance**<br>• Use create_transaction atomicity |
| **Cleanup greps lie** (don't match re-export reality) | MEDIUM | MEDIUM | False green/red on success | • **V3: Greps rewritten for residual re-exports**<br>• Explicit permitted symbols list |
| **Test flakiness** (module-scoped fixtures) | MEDIUM | MEDIUM | Order-dependent failures | • **V3: Module-scoped fixture review**<br>• Change to function-scoped if needed |

---

### Helper Function Lifecycle (V3 — Explicit with Line Refs)

| Helper | Current Location | After Refactor | Re-Exported? | Test Impact | Notes |
|--------|------------------|------------------|---|---|---|
| `get_db()` | models.py:105-117 | `dao/connection_manager.py:1-15` | ✅ models.py | ✅ Tests call `models.get_db()` still works | Connection factory |
| `using_postgres()` | models.py:38-40 | Stay in models.py | ❌ N/A | ✅ Used by _sql, not imported by tests | Backend flag |
| `db_path()` | models.py:42-44 | Stay in models.py | ❌ N/A | ✅ Internal | DB path resolution |
| `_sql(query)` | models.py:58-60 | `dao/base_dao.py:1-10` (module-level function) | ✅ models.py | ✅ `models._sql()` works | Query converter |
| `_row_to_dict(row)` | models.py:62-69 | `dao/base_dao.py:12-25` (module-level function) | ✅ models.py | ✅ `models._row_to_dict()` works | Row converter |
| `_normalize_row(row_dict)` | models.py:70-79 | `dao/base_dao.py:27-40` (module-level function) | ❌ Private | ✅ Internal DAO use | Type normalization |
| `_scalar_from_row(row)` | models.py:80-84 | `dao/base_dao.py:42-48` (module-level function) | ❌ Private | ✅ Used by seed gate logic | Value extraction |
| `_insert_returning_id()` | models.py:375-386 | `dao/base_dao.py:50-65` (module-level function) | ✅ models.py | ✅ Tests call `models._insert_returning_id()` | INSERT RETURNING helper |
| `_split_sql_statements(sql)` | models.py:87-103 | `dao/schema_dao.py:10-30` (module-level function) | ❌ Private | ✅ Schema migration only | SQL parser |
| `_rewards_ledger_table_exists()` | models.py:182-209 | `dao/schema_dao.py:50-80` (module-level function) | ❌ Private | ✅ Schema init only | Existence check |

**Key Point (V3):** All helpers are **module-level functions** (not instance methods). This allows clean re-export. Tests continue to work without changes.

---

### Affected Systems

- **Core data layer:** `models.py` (813 lines) — refactor target
- **Routes (read-only):**
  - `api/dashboard.py` → `get_accounts_by_user`, `get_all_transactions_by_user`, `get_rewards_points_for_user`
  - `api/profile.py` → `get_user_profile`
  - `api/transfer.py` → `get_accounts_by_user`, `transfer_money`
  - `api/login.py` → `get_user_by_username`
  - `api/accounts.py` → `get_account_by_id`, `get_transactions_by_account`, `get_cards_by_account` (live!)
  - `api/api_endpoints.py` → `get_accounts_by_user`, `get_all_transactions_by_user`, `get_account_by_id`
- **Tests (baseline, must stay green):**
  - `test/test_a_models_bootstrap.py:112-119` — DB init tests
  - `test/test_banking_routes.py` — Login, dashboard, transfer routes
  - `test/test_api_routes.py` — API endpoints
  - `test/test_profile_*.py` — Profile routes
  - `test/test_demo_rollout.py:212-266` — Rewards savepoint/isolation behaviors
- **Dependencies:** No new dependencies (pure refactor)
- **Backends:** SQLite (local) + PostgreSQL (CI/prod — hard requirement V3)

---

### Test Strategy (V3 — Enhanced with Real Test Names)

**Existing test coverage (baseline):**
- ✅ `test_login_post_demo_redirects_to_dashboard` (login flow)
- ✅ `test_login_post_demo_followed_renders_dashboard` (dashboard rendering)
- ✅ `test_transfer_post_small_amount_succeeds` (happy path transfer)
- ✅ `test_transfer_post_insufficient_funds_shows_error` (balance check)
- ✅ `test_transfer_post_invalid_amount_shows_error` (validation)
- ✅ `test_transfer_post_rejects_cross_user_source_account` (authorization)
- ✅ `test_transfer_post_same_account_shows_error` (self-transfer check)
- ✅ `test_dashboard_shows_rewards_points_when_schema_and_feature_are_enabled` (rewards flag + schema)

**Critical missing tests (V3 — Real names, added):**
- ⭕ `test_transfer_rollback_on_db_error` — mock DB error mid-transfer, verify atomicity
- ⭕ `test_account_queries_both_sqlite_and_postgres` — query compatibility across backends
- ⭕ `test_schema_initialization_resilience` — init_db with missing rewards table

**Named exit criteria (V3 — No more hypotheticals):**
- ✅ `test_transfer_post_rejects_cross_user_source_account` must pass (auth check)
- ✅ `test_transfer_post_insufficient_funds_shows_error` must pass (balance check)
- ✅ `test_demo_rollout.py::test_rewards_successful_on_transfer_with_feature_flag_enabled` must pass (savepoint)
- ✅ `test_demo_rollout.py::test_rewards_continues_on_insert_error` must pass (exception handling)
- ✅ `test_a_models_bootstrap.py::test_init_db_creates_schema` must pass (initialization)
- ✅ `test_a_models_bootstrap.py::test_create_sample_data_seeds_users` must pass (seed data)

---

## Phase 2: CHUNK — Task Breakdown (V3 — Complete)

### Dependency Graph (V3 — Updated)

```
CHUNK_0 (DAO base + helpers as module-level functions)
    ↓
CHUNK_1 (User entity)
    ↓
CHUNK_2 (Account entity) + CHUNK_2c (Cards — new)
    ↓
CHUNK_3 (Transaction entity)
    ↓
CHUNK_4 (Transfer + Rewards with shared transaction)
    ↓
CHUNK_5a (Schema & Initialization)
    ↓
CHUNK_5b (Cleanup + validation)
```

### Pre-Execution Bug Fix Checklist (V3)

**BEFORE starting CHUNK_0, verify/fix:**

- [ ] Resource leaks: try/finally added to test query functions (spot check 3-5)
- [ ] Transaction safety: Auth checks outside transaction in transfer_money (verify on models.py:707-812)
- [ ] Rewards savepoint: Exception handling correct (verify on models.py:786-801)

**DO NOT PROCEED until checklist signed off.**

---

## Chunk Definitions (V3)

### CHUNK_0: Extract DAO Base & Helper Functions (Module-Level)

**Type:** Code (new files)
**Dependencies:** Pre-execute checklist passed
**Parallelizable:** No
**Risk Level:** Low
**Est. Duration:** 45 minutes

**Goal:** Create DAO foundation with helpers as module-level functions (not instance methods).

**Tasks:**
1. Create `dao/base_dao.py` with:
   - `BaseDAO` class (instance methods: `get_connection()`, `close()`, `commit()`, `rollback()`)
   - **Module-level helper functions** (NOT instance methods):
     - `_sql(query)` — Postgres/SQLite query converter
     - `_row_to_dict(row)` — row-to-dict converter
     - `_normalize_row(row_dict)` — type normalization
     - `_scalar_from_row(row)` — value extraction
     - `_insert_returning_id(cursor, sql, params)` — INSERT RETURNING
   - Private helper: `_normalize_row()` (internal only)
2. Create `dao/connection_manager.py` with:
   - `get_db()` function (moved from models.py)
3. Create `test/test_dao_base.py` with unit tests for BaseDAO lifecycle
4. **Add re-export shim to models.py:**
   ```python
   # models.py (bottom)
   from dao.base_dao import _sql, _row_to_dict, _insert_returning_id
   from dao.connection_manager import get_db
   ```

**Critical (V3 — Ref Integration):**
- Helpers MUST be module-level functions, NOT instance methods
- This allows `models._sql()` to work without re-creating it as a class method
- Tests that call `models._insert_returning_id()` will continue to work

**Files Created:**
- `dao/__init__.py`
- `dao/base_dao.py`
- `dao/connection_manager.py`
- `test/test_dao_base.py`

**Verification:**
- [ ] `pytest test/test_dao_base.py -v` passes
- [ ] `from models import _sql; _sql("SELECT ?")` works (re-export)
- [ ] `from models import get_db; get_db()` works (re-export)
- [ ] `pytest test/ -v` still 100% green (no behavior change)

---

### CHUNK_1: Migrate User Entity Functions to DAO

**Type:** Code (refactor)
**Dependencies:** CHUNK_0
**Parallelizable:** No
**Risk Level:** Medium
**Est. Duration:** 30 minutes

**Goal:** Route user queries through UserDAO.

**Tasks:**
1. Create `dao/user_dao.py` extending `BaseDAO`
2. Implement:
   - `get_by_username(username: str) -> dict | None`
   - `get_profile(user_id: int) -> dict | None`
3. Update `models.py` to delegate:
   - `get_user_by_username()` → calls `UserDAO.get_by_username()`
   - `get_user_profile()` → calls `UserDAO.get_profile()`

**Files Created:**
- `dao/user_dao.py`

**Files Modified:**
- `models.py` (lines ~574-599)

**Verification:**
- [ ] `pytest test/test_banking_routes.py::test_login_post_demo_redirects_to_dashboard -v` passes
- [ ] `pytest test/test_profile_route.py -v` passes
- [ ] Manual test: Login as "demo" works

---

### CHUNK_2: Migrate Account Entity Functions to DAO

**Type:** Code (refactor)
**Dependencies:** CHUNK_1
**Parallelizable:** No
**Risk Level:** Medium
**Est. Duration:** 30 minutes

**Goal:** Route account queries through AccountDAO.

**Tasks:**
1. Create `dao/account_dao.py` extending `BaseDAO`
2. Implement:
   - `get_by_user(user_id: int) -> list[dict]`
   - `get_by_id(account_id: int) -> dict | None`
3. Update `models.py` to delegate account functions

**Files Created:**
- `dao/account_dao.py`

**Files Modified:**
- `models.py` (lines ~601-622)

**Verification:**
- [ ] `pytest test/test_banking_routes.py::test_login_post_demo_followed_renders_dashboard -v` passes
- [ ] Manual test: Dashboard shows accounts with balances

---

### CHUNK_2c: Migrate Cards Functions to DAO (V3 — NEW)

**Type:** Code (refactor — first-class entity)
**Dependencies:** CHUNK_2
**Parallelizable:** No
**Risk Level:** Low
**Est. Duration:** 15 minutes

**Goal:** Route card queries through CardDAO (not dead code; live in accounts.py).

**Tasks:**
1. Extend `dao/account_dao.py` or create `dao/card_dao.py`:
   - `get_by_account(account_id: int) -> list[dict]`
2. Update `models.py` line ~662 to delegate:
   - `get_cards_by_account()` → calls `CardDAO.get_by_account()` (or `AccountDAO.get_cards()`)

**Files Modified:**
- `dao/account_dao.py` (add get_cards method)
- `models.py` (lines ~662-669)

**Verification:**
- [ ] `api/accounts.py` still calls `get_cards_by_account()`
- [ ] `pytest test/test_a_models_bootstrap.py::test_account_detail_includes_cards -v` passes
- [ ] Manual test: Account detail page shows cards

---

### CHUNK_3: Migrate Transaction Entity Functions to DAO

**Type:** Code (refactor)
**Dependencies:** CHUNK_2
**Parallelizable:** No
**Risk Level:** Medium
**Est. Duration:** 45 minutes

**Goal:** Route transaction queries through TransactionDAO.

**Tasks:**
1. Create `dao/transaction_dao.py` extending `BaseDAO`
2. Implement:
   - `get_by_account(account_id: int, limit: int = 10) -> list[dict]`
   - `get_by_user(user_id: int, limit: int = 20) -> list[dict]`
   - `create(account_id, type, amount, desc, recipient) -> int` — with try/finally
3. Update `models.py` to delegate transaction functions

**Files Created:**
- `dao/transaction_dao.py`

**Files Modified:**
- `models.py` (lines ~624-705)

**Verification:**
- [ ] `pytest test/test_banking_routes.py -v -k transfer` passes
- [ ] Manual test: Dashboard shows recent transactions

---

### CHUNK_4: Migrate Transfer + Rewards (Shared Transaction) (V3 — Enhanced)

**Type:** Code (refactor — complex atomicity)
**Dependencies:** CHUNK_3
**Parallelizable:** No
**Risk Level:** CRITICAL
**Est. Duration:** 90 minutes

**Goal:** Route transfer logic through AccountDAO with shared transaction for rewards.

**Critical (V3 — Ref Integration):**
- Transfer MUST use same connection for balance updates AND rewards insert
- Savepoint/rollback under one cursor, not two separate DAOs opening independent connections
- Rewards DAO does NOT open its own connection; it receives cursor from AccountDAO
- `models.try_insert_rewards_points` must remain callable by tests (re-export or delegate)

**Tasks:**
1. Extend `dao/account_dao.py` with:
   ```python
   def transfer(self, from_id, to_id, amount, desc, acting_user_id):
       """Transfer money; rewards insert on same connection."""
       self.get_connection()
       try:
           # Auth check OUTSIDE transaction
           if not self._check_ownership(...):
               return False, "Forbidden"
           
           # Start transaction
           self.cursor.execute("BEGIN" if using_postgres() else "")
           
           # Debit/credit operations
           self.cursor.execute(...)  # Debit
           self.cursor.execute(...)  # Credit
           
           # Rewards on SAME cursor/connection (savepoint)
           self.cursor.execute("SAVEPOINT rewards_savepoint")
           try:
               # Call rewards helper with our cursor
               try_insert_rewards_points(conn=self.conn, cursor=self.cursor, ...)
               self.cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
           except Exception:
               self.cursor.execute("ROLLBACK TO SAVEPOINT rewards_savepoint")
               self.cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
           
           self.commit()
           return True, "Transfer successful"
       except Exception:
           self.rollback()
           return False, "Transfer failed"
       finally:
           self.close()
   ```

2. Extract rewards logic to helper `try_insert_rewards_points(conn, cursor, ...)` (stays callable)
3. Create `dao/rewards_dao.py` with schema/initialization (not transfer-scoped)
4. Update `models.py`:
   - `transfer_money()` → calls `AccountDAO.transfer()`
   - `get_rewards_points_for_user()` → calls `RewardsDAO.get_points_for_user()`

**Files Created/Modified:**
- `dao/account_dao.py` (add transfer method with connection sharing)
- `dao/rewards_dao.py` (schema + query functions, not transfer-scoped)
- `models.py` (lines ~707-813)

**Exit criteria (V3 — Real test names):**
- [ ] `pytest test/test_banking_routes.py::test_transfer_post_rejects_cross_user_source_account -v` passes (auth)
- [ ] `pytest test/test_banking_routes.py::test_transfer_post_insufficient_funds_shows_error -v` passes (balance)
- [ ] `pytest test/test_demo_rollout.py::test_rewards_successful_on_transfer_with_feature_flag_enabled -v` passes (savepoint success)
- [ ] `pytest test/test_demo_rollout.py::test_rewards_continues_on_insert_error -v` passes (exception handling)
- [ ] **NEW:** `pytest test/test_dao_transfer_safety.py::test_transfer_rollback_on_db_error -v` passes (atomicity)

**Verification:**
- [ ] Transfer balances update atomically
- [ ] Rewards savepoint succeeds/fails without breaking core transfer
- [ ] Test `test_demo_rollout.py:226` monkeypatches still work (try_insert_rewards_points still importable)
- [ ] Manual test: Transfer works end-to-end

---

### CHUNK_5a: Schema & Initialization DAO (V3 — Now in Task Breakdown)

**Type:** Code (refactor)
**Dependencies:** CHUNK_4
**Parallelizable:** No
**Risk Level:** MEDIUM
**Est. Duration:** 60 minutes

**Goal:** Extract initialization/schema code into DAO (addresses 260 lines of orphaned code).

**Tasks:**
1. Create `dao/schema_dao.py` with:
   - `init_db()` — orchestration (calls _create_schema + _seed_data)
   - `create_sqlite()` — SQLite schema creation
   - `apply_postgres()` — Postgres schema + migrations
   - `ensure_rewards_ledger_schema()` — rewards table idempotent setup
   - `_rewards_ledger_table_exists()` — schema existence check
2. Create `dao/seed_dao.py` (or include in schema_dao) with:
   - `create_sample_data()` — user/account/transaction sample data
3. Update `models.py`:
   - Keep `init_db()` as public wrapper → calls `SchemaDAO.init_db()`
   - Keep `create_sample_data()` as public wrapper → calls `SeedDAO.create_sample_data()`
4. Update `app.py:58` — no changes needed (init_db still works)

**Files Created:**
- `dao/schema_dao.py`
- `dao/seed_dao.py` (optional)

**Files Modified:**
- `models.py` (lines ~389-572)
- No changes to `app.py` (init_db re-export handles it)

**Exit criteria:**
- [ ] App starts successfully: `python app.py`
- [ ] Bootstrap tests pass: `pytest test/test_a_models_bootstrap.py -v`
- [ ] **NEW:** `pytest test/test_dao_schema_resilience.py::test_schema_initialization_resilience -v` passes

**Verification:**
- [ ] Schema initialized on startup
- [ ] Seed data present (demo user, accounts, transactions)
- [ ] Rewards table created if feature enabled
- [ ] No orphaned `get_db()` calls in init functions

---

### CHUNK_5b: Cleanup and Final Validation (V3 — Corrected Greps)

**Type:** Cleanup + verification
**Dependencies:** CHUNK_5a
**Parallelizable:** No
**Risk Level:** Low
**Est. Duration:** 45 minutes

**Goal:** Verify refactor complete, no orphaned code, all tests pass.

**Tasks:**
1. Verify no orphaned direct DB calls in models.py functions (allow re-exports)
2. Run full test suite 3x (flakiness check)
3. Manual smoke test (all 13 scenarios)
4. PostgreSQL backend verification (hard requirement V3)
5. Add 3 critical missing tests (if not added in earlier chunks)

**Verification Commands (V3 — Corrected for re-exports):**

```bash
# ✅ ALLOWED (re-exports for backward compatibility):
grep -n "^from dao" models.py     # Re-import from DAO
grep -n "^__all__" models.py      # Export list (if using __all__)

# ❌ FORBIDDEN (direct DB calls in query/mutation functions):
# Check for patterns in function bodies (not re-export section):
grep -n "conn = get_db()" models.py | grep -v "^# " | grep -v "def get_db"
grep -n "cursor.execute" models.py | grep -v "def _"
grep -n "conn.cursor()" models.py | grep -v "def get_db" | grep -v "^# "

# ✅ ALLOWED (residual in init wrappers that delegate to DAO):
grep -n "get_connection\|\.close\|\.commit" models.py  # Should only be in re-exports or old definitions deleted

# Comprehensive check:
# Run grep audit:
echo "=== Checking for orphaned DB calls in models.py ===" 
# Count functions in query/mutation section (lines 574-812):
sed -n '574,812p' models.py | grep -c "get_db()"  # Should be 0
sed -n '574,812p' models.py | grep -c "cursor.execute"  # Should be 0
sed -n '574,812p' models.py | grep -c "conn.cursor()"  # Should be 0

# Full test suite (run 3x to catch flakiness)
pytest test/ -v
pytest test/ -v
pytest test/ -v

# PostgreSQL verification (hard requirement V3):
# If local Postgres available:
DATABASE_URL="postgresql://..." pytest test/ -v
# OR check CI job:
# Verify rodbank-pipeline passes on main with Postgres flag

# Manual smoke test (13 scenarios)
python app.py
# Browser: http://127.0.0.1:5001/
# 1. Login, 2. Dashboard, 3. Accounts visible, 4. Transactions visible
# 5. Transfer form, 6. Transfer success, 7. Invalid amount, 8. Insufficient funds
# 9. Cross-user rejection, 10. Profile page, 11. API accounts, 12. API transactions, 13. Logout
```

**Files Modified (V3 — None; cleanup only):**
- (No files modified in V3; cleanup verifies existing state)
- Add tests if needed: `test/test_dao_*.py` (critical missing tests)

**Exit criteria (V3):**
- [ ] Zero grep violations in query/mutation sections
- [ ] All 92 existing tests pass 3x in a row
- [ ] 3 critical missing tests added and passing (rollback, backend compat, schema resilience)
- [ ] Manual smoke test: all 13 scenarios pass
- [ ] PostgreSQL backend: CI job passes OR local Postgres test passes
- [ ] Re-exports working: `python -c "from models import _sql; print(_sql('SELECT ?'))"`

---

## Phase 3: EXECUTE — Execution Plan (V3)

### Sequential Dependencies

```
Pre-Execute Checklist (resource leaks, auth logic, savepoint)
    ↓
1. CHUNK_0 (DAO base + helpers as module-level) → Tests green
    ↓
2. CHUNK_1 (User entity) → Tests green, login works
    ↓
3. CHUNK_2 (Account entity) + CHUNK_2c (Cards) → Tests green, dashboard works
    ↓
4. CHUNK_3 (Transaction entity) → Tests green, transactions work
    ↓
5. CHUNK_4 (Transfer + Rewards, shared transaction) → Tests green, transfer atomicity verified
    ↓
6. CHUNK_5a (Schema & Initialization) → Tests green, init_db works, seed data present
    ↓
7. CHUNK_5b (Cleanup + validation) → Tests green 3x, greps pass, Postgres verified
```

**Abort Criteria (No tolerance for "we'll fix it later"):**
- Any test fails that can't be fixed in < 5 minutes
- Manual smoke test fails
- Postgres verification fails
- Merge conflict or refactor doesn't match spec
- → Immediately rollback to prior chunk

---

## Critical Files Reference

### Files to Create
1. `dao/__init__.py`
2. `dao/base_dao.py` — BaseDAO + module-level helpers
3. `dao/connection_manager.py` — get_db()
4. `dao/user_dao.py`
5. `dao/account_dao.py` — includes transfer()
6. `dao/card_dao.py` or card methods in account_dao
7. `dao/transaction_dao.py`
8. `dao/rewards_dao.py`
9. `dao/schema_dao.py`
10. `dao/seed_dao.py` (optional)
11. `test/test_dao_base.py`
12. `test/test_dao_transfer_safety.py` (critical missing tests)
13. `test/test_dao_schema_resilience.py` (critical missing tests)

### Files to Modify
1. `models.py` — Refactor all query/mutation functions to delegate to DAO
   - Keep function signatures identical (API compatibility)
   - Keep re-exports for helpers (backward compat with tests)

### Files to Verify (Read-Only)
1. `app.py` (line 58) — `init_db()` still works
2. `api/*.py` — No changes needed (all call models wrappers)
3. `test/*.py` — No import changes needed (re-exports)

---

## Testing & Verification (V3)

### Test Harness
- **Command:** `pytest test/ -v`
- **Coverage:** `pytest test/ --cov=dao --cov=models`
- **Critical path:** Named test gates per chunk (real names, no hypotheticals)

### Pre-Execution Checklist (V3)
- [ ] Resource leak fixes verified (spot check: try/finally in 3-5 functions)
- [ ] Auth logic moved outside transaction (transfer_money:707-812)
- [ ] Savepoint exception handling correct (transfer_money:786-801)
- [ ] Baseline tests documented: `pytest test/ -v | tee baseline-test-output.txt`

### Post-Execution Checks (V3)
- [ ] All 92 tests pass 3x consecutively
- [ ] Grep audit: zero violations in query/mutation sections (allowed re-exports only)
- [ ] 3 critical tests passing (rollback, backend compat, schema resilience)
- [ ] Manual smoke test: all 13 scenarios
- [ ] PostgreSQL: CI job passes OR local test passes (HARD REQUIREMENT)
- [ ] Re-exports: `from models import _sql, get_db, _insert_returning_id` — all work

---

## Post-Sprint Validation (V3)

**After all chunks complete:**

1. **Full test suite:** `pytest test/ -v` — 100% green
2. **Grep audit:** `sed -n '574,812p' models.py | grep -c "cursor.execute"` → 0
3. **PostgreSQL verification:** Hard exit criterion (not optional)
4. **Critical tests:** Rollback, backend compatibility, schema resilience all pass
5. **Manual smoke test:** 13 scenarios pass
6. **Coverage report:** `pytest test/ --cov=dao --cov=models --cov-report=html`
7. **Git history:** Clean commits, each with "all tests green" message
8. **PR ready:** Branch ready for review

**Document in RESULTS.md:**
- Time per chunk
- Issues encountered
- Test pass rate
- PostgreSQL verification result
- Lessons learned
- Follow-up work

---

## Out of Scope

(Same as V1/V2 — performance tuning, schema changes, business logic, API changes, frontend, error handling improvements beyond try/finally)

---

## Key Differences: V2 → V3 (Integration of Ref Feedback)

| Aspect | V2 | V3 |
|--------|----|----|
| **CHUNK_5a in execution** | Scope only | Task breakdown (explicit steps) |
| **Helper functions** | Instance methods (broke re-export) | Module-level functions (clean re-export) |
| **Transfer signature** | Missing acting_user_id (incomplete) | Includes acting_user_id (matches real code) |
| **Connection sharing** | Separate DAOs (ACID violation) | Explicit pattern: one cursor for transfer+rewards |
| **Cards entity** | Dead code (missed) | CHUNK_2c (first-class, live verification) |
| **Test names** | Hypothetical "if exists" | Real names (test_demo_rollout.py:212-266) |
| **PostgreSQL** | Optional "if testable" | Hard exit criterion |
| **Invented tasks** | update_balance() (doesn't exist) | Removed (use create_transaction atomicity) |
| **Cleanup greps** | Don't account for re-exports | Rewritten for residual wrappers |
| **Function count** | Estimated ~28 | Enumerated 25 |

---

## Appendix: Real Function Inventory (V3 — Definitive)

**Query Functions (8):** get_user_by_username, get_user_profile, get_accounts_by_user, get_account_by_id, get_transactions_by_account, get_all_transactions_by_user, get_cards_by_account, get_rewards_points_for_user

**Mutation Functions (3):** create_transaction, transfer_money, try_insert_rewards_points

**Initialization Functions (6):** init_db, create_sample_data, ensure_rewards_ledger_schema, _apply_postgres_schema, _create_sqlite_schema, _rewards_ledger_table_exists

**Helper Functions (10):** get_db, using_postgres, db_path, _sql, _row_to_dict, _normalize_row, _scalar_from_row, _insert_returning_id, _split_sql_statements

**Total: 27 functions** (more precise than "~28")

---

**Plan Version:** 3.0-ref-integrated  
**Created:** 2026-08-12  
**Status:** ✅ READY FOR EXECUTION (ref blockers resolved)  
**Ref Panel:** Grok + Gemini (both provided actionable findings)  
**Next Step:** Execute CHUNK_0 (after pre-execute checklist signed off)
