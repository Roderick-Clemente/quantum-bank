# AI Sprint Planning — QuantumBank DAO Refactor

**Adapted from:** `.local/planning/ai-sprints/SPRINT-PLANNING-TEMPLATE.md` (v1.0-qb)

---

## Sprint Metadata

**Sprint Name:** QuantumBank DAO Pattern Refactor
**Date:** 2026-08-12
**Sprint Type:** Refactor
**Priority:** P2-Medium
**Estimated Duration:** 1 day
**Status:** Planning
**Branch:** `feature/quantum-dao-refactor` off `feat/user-profile`

## Sprint Principles

- **Low-token execution:** Plan once, execute in small chunks with minimal context.
- **Standardized practice:** Embed testing, flagging, and release discipline in the plan.
- **Audit trail:** Each chunk leaves clear evidence for review and future reference.
- **TDD-first (Red-Green-Refactor):** Write failing tests before implementation when behavior changes.
- **Zero Behavior Change:** This is a pure refactor — all existing tests must pass unchanged.

### Refactor Principles

```
1. TEST BASELINE → Ensure all existing tests pass (green)
2. EXTRACT → Extract DAO interface and implementations (tests stay green)
3. MIGRATE → Route calls through DAO one entity at a time (tests stay green)
4. VERIFY → Run full test suite + manual smoke test after each chunk
5. CLEANUP → Remove old direct DB code once fully migrated
```

**Exception to TDD:** This is a pure refactor with no behavior change. Existing tests are the "Red" baseline — they describe expected behavior. Our job is to keep them green while restructuring internals.

---

## Sprint Objectives

### Primary Goal
Extract all database interactions from `models.py` into a clean DAO layer, improving testability and maintainability without changing any external behavior.

### Success Criteria
- [ ] All database calls routed through DAO interface (zero direct `conn.cursor()` calls outside DAO or test fixtures)
- [ ] All existing tests pass unchanged (pytest test/ -v shows 100% green)
- [ ] Manual smoke test confirms login, dashboard, transfer, profile all work
- [ ] DAO layer supports both SQLite and PostgreSQL backends (existing flag still works)
- [ ] Connection management centralized in DAO (no scattered `conn.close()` calls)
- [ ] Test helpers documented: `_insert_returning_id`, `_row_to_dict`, `_sql` locations clarified

### Scope (Revised After Adversarial Review)
**IN SCOPE:**
- User, Account, Transaction, Transfer+Rewards query/mutation functions (CHUNK_1-4)
- Schema initialization and seed data functions (CHUNK_5a — NEW)
- All helper functions: `_insert_returning_id`, `_row_to_dict`, `_normalize_row`, `_sql` → move to DAO
- Fix existing resource leaks (add try/finally to all DAO functions)

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

**Current State:**
- **File:** `models.py` (813 lines) contains all database logic
- **Pattern:** Each function opens connection → executes SQL → closes connection
- **Example pattern:**
  ```python
  def get_user_by_username(username: str) -> dict | None:
      conn = get_db()              # Direct connection
      cursor = conn.cursor()        # Direct cursor
      cursor.execute(_sql("SELECT * FROM users WHERE username = ?"), (username,))
      user = cursor.fetchone()
      conn.close()                  # Manual cleanup
      return _row_to_dict(user)
  ```
- **Coupling:** Route handlers → `models.py` functions → raw SQL
- **Testing:** Tests must mock at the `models` level or use real DB
- **Count:** ~28 public functions that follow this pattern

**Why Refactor Now:**
- **Testability:** Hard to unit test business logic without hitting real DB
- **Maintainability:** DB logic scattered across 813-line file
- **Future flexibility:** Difficult to swap persistence layer (e.g., add Redis cache, change ORMs)
- **Code smell:** Connection management duplicated ~30 times
- **Adversarial review trigger:** Independent model families (Grok/Gemini) will audit for missed call sites, state bugs, and test gaps

### Root Cause Analysis

**Core Problem:** Violation of Single Responsibility Principle
- `models.py` does THREE things: connection management, SQL execution, business domain modeling
- No abstraction boundary between "what data to fetch" (business logic) and "how to fetch it" (data access)
- Tight coupling makes testing require full DB integration

**Cascade Effects:**
- Routes can't be unit tested without DB
- Changing DB backends requires touching all query functions
- Adding metrics/logging to DB calls requires ~30 edits
- Mock-heavy tests that are brittle and hard to maintain

### Risk Assessment

| Risk | Severity | Probability | Impact | Mitigation |
|------|----------|-------------|--------|------------|
| **Refactor breakage** | HIGH | MEDIUM | Routes return wrong data, users see errors | • Run full test suite after each chunk<br>• Manual smoke test dashboard/transfer<br>• Keep git history clean for fast rollback |
| **Missed call sites** | HIGH | LOW | Some code still calls old pattern, causing inconsistency | • grep for `get_db()` after migration<br>• grep for `conn.cursor()` outside DAO<br>• Code review by independent models |
| **State bugs** | MEDIUM | LOW | Transaction rollback breaks, rewards ledger corrupts | • Focus on `transfer_money` (has transaction)<br>• Test rollback paths explicitly<br>• Verify commit/rollback in DAO |
| **Test flakiness** | MEDIUM | MEDIUM | Tests pass locally but fail in CI due to DB state | • Ensure test isolation (conftest.py DB fixture)<br>• No shared state between tests<br>• Run tests multiple times before commit |
| **PostgreSQL regressions** | MEDIUM | MEDIUM | SQLite works but Postgres queries fail (_sql helper) | • Test both backends (local SQLite + CI Postgres)<br>• Keep `_sql()` helper in DAO layer<br>• Verify `using_postgres()` flag respected |
| **Import cycles** | LOW | MEDIUM | Circular imports between models.py and new DAO | • DAO depends on nothing except stdlib + db drivers<br>• Models imports DAO (one direction only)<br>• Use dependency injection if needed |
| **Performance regression** | LOW | LOW | Connection overhead or N+1 queries introduced | • Out of scope for this sprint<br>• Monitor /metrics endpoint if deployed<br>• Note any obvious issues for future sprint |

### Helper Function Lifecycle (Resolved After Adversarial Review)

Adversarial review flagged ambiguity about where helper functions live after refactor. Clarified:

| Helper | Current Location | After Refactor | Test Compatibility |
|--------|------------------|-----------------|-------------------|
| `get_db()` | models.py:45-55 | Move to `dao/connection_manager.py`, re-export from models.py | ✅ Tests call `models.get_db()` — still works |
| `_sql(query)` | models.py:58-60 | Move to `dao/base_dao.py`, re-export from models.py | ✅ Tests call `models._sql()` — still works |
| `_insert_returning_id()` | models.py:375-386 | Move to `dao/base_dao.py`, re-export from models.py | ✅ Tests call `models._insert_returning_id()` — still works |
| `_row_to_dict()` | models.py:62-69 | Move to `dao/base_dao.py`, re-export from models.py | ✅ Tests call `models._row_to_dict()` — still works |
| `_normalize_row()` | models.py:70-79 | Move to `dao/base_dao.py` (private, used only inside DAO) | ✅ Internal only |

**Key point:** All helpers move to DAO layer, but `models.py` re-exports them for backward compatibility. **Zero test changes required.**

### Affected Systems

- **Core data layer:** `models.py` (813 lines) — refactor target
- **Routes (read-only, should not change):**
  - `api/dashboard.py` — calls `get_accounts_by_user`, `get_all_transactions_by_user`, `get_rewards_points_for_user`
  - `api/profile.py` — calls `get_user_profile`
  - `api/transfer.py` — calls `get_accounts_by_user`, `transfer_money`
  - `api/login.py` — calls `get_user_by_username`
  - `api/accounts.py` — calls `get_account_by_id`, `get_transactions_by_account`, `get_cards_by_account`
  - `api/api_endpoints.py` — calls `get_accounts_by_user`, `get_all_transactions_by_user`, `get_account_by_id`
- **Tests (baseline, must stay green):**
  - `test/test_a_models_bootstrap.py` — DB initialization tests
  - `test/test_banking_routes.py` — Login, dashboard, transfer integration tests
  - `test/test_api_routes.py` — API endpoint tests
  - `test/test_profile_*.py` — Profile route and model tests
  - `test/test_demo_rollout.py` — Rewards feature flag tests
- **Dependencies:** No new dependencies (pure refactor using stdlib)
- **Database backends:** SQLite (local) + PostgreSQL (CI/prod)
- **Flags:** `is_postgres_database_enabled()` from `db_flags.py` — must continue to work

### Test Strategy (Refactor-First)

**Baseline Test Philosophy:**
- **Existing tests are the specification** — they define correct behavior
- **Zero new behavior tests** — only structural tests for DAO itself
- **Keep tests green always** — refactor is safe only if tests stay passing

**Test Approach:**
1. **Establish baseline:** Run `pytest test/ -v` before any changes (should be 100% green)
2. **DAO structural tests:** Add minimal tests for DAO layer itself (connection, cursor, close)
3. **Regression detection:** Run full suite after each chunk
4. **Manual smoke tests:** Test critical paths (login → dashboard → transfer → logout)

**Test Types:**
- **Unit (new):** DAO connection/cursor management (mock drivers)
- **Integration (existing):** HTTP routes via Flask `client` fixture — MUST stay green
- **System (manual):** Browser test of login/dashboard/transfer/profile

**Expected Test Modifications:**
- **Zero changes to test logic** — assertions should not change
- **Possible import changes** — if tests directly import from models.py (rare)
- **No new tests for existing behavior** — refactor preserves behavior

**Baseline Test Run (Pre-Refactor):**
```bash
# CRITICAL: Document current test state before starting
pytest test/ -v --tb=short | tee baseline-test-output.txt
pytest test/ -m banking -v
pytest test/ -m api -v
```

### Test Quality Standards

Follow `.cursor/skills/review-tests/SKILL.md`:
- Behavior-driven test names
- Arrange-Act-Assert structure
- Test public HTTP/DB behavior, not internals
- Mock at boundaries only (DB driver if needed, not DAO)
- No tautological assertions (avoid testing implementation details)

**For DAO-Specific Tests (New):**
- Test connection acquisition/release
- Test cursor management
- Test transaction commit/rollback
- Mock `psycopg2` / `sqlite3` at driver level, not application level

### Flags & Release Strategy

**No New Flags:**
- This is pure refactor — no feature flags needed
- Existing flag `is_postgres_database_enabled()` must continue working

**Deployment:**
- Local dev: SQLite (`quantum_bank.db`)
- CI: PostgreSQL (via DATABASE_URL env var)
- Render: PostgreSQL (existing DATABASE_URL)

**Metrics:**
- `/metrics` endpoint: Monitor for error rate spikes (existing counters)
- No new metrics for this sprint (out of scope)

---

## Phase 2: CHUNK — Task Breakdown

### Chunking Guidance

**Sequential Execution Only:**
- Each chunk depends on previous chunk passing tests
- NO parallel chunks — risk of merge conflicts in models.py
- Validate after each chunk before proceeding

**Chunk Size:**
- Small enough to revert easily (~100-200 lines changed)
- Large enough to be meaningful (one entity at a time)
- Each chunk is independently reviewable

### Dependency Graph

```
CHUNK_0 (DAO interface + base)
    ↓
CHUNK_1 (User entity)
    ↓
CHUNK_2 (Account entity)
    ↓
CHUNK_3 (Transaction entity)
    ↓
CHUNK_4 (Transfer + rewards)
    ↓
CHUNK_5 (Cleanup + validation)
```

### Chunk Definitions

---

#### CHUNK_0: Extract DAO Interface and Base Implementation

**Type:** Code (new file)
**Dependencies:** None
**Parallelizable:** No
**Risk Level:** Low
**Est. Duration:** 30 minutes

**Goal:** Create DAO foundation without breaking existing code.

**Tasks:**
1. Create `dao/base_dao.py` with abstract interface
2. Create `dao/connection_manager.py` with `get_connection()` method
3. Implement `close()`, `commit()`, `rollback()` in base class
4. Keep `models.py` unchanged — parallel implementation
5. Write structural tests for DAO base class

**Files Created:**
- `dao/__init__.py`
- `dao/base_dao.py`
- `dao/connection_manager.py`

**Files Modified:**
- None (yet)

**Test-First Notes:**
- Add `test/test_dao_base.py` to verify connection lifecycle
- Mock `sqlite3.connect` and `psycopg2.connect`
- Verify `get_connection()` returns proper cursor
- Verify `close()` is called on context exit

**Interface Design:**
```python
# dao/base_dao.py
class BaseDAO:
    """Base Data Access Object with connection management."""
    
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def get_connection(self):
        """Get database connection (SQLite or Postgres based on flag)."""
        # Implementation using existing get_db() pattern
        pass
    
    def close(self):
        """Close connection."""
        pass
    
    def commit(self):
        """Commit transaction."""
        pass
    
    def rollback(self):
        """Rollback transaction."""
        pass
    
    def _sql(self, query: str) -> str:
        """Convert ? to %s for Postgres (keep existing _sql logic)."""
        pass
```

**Verification:**
- [ ] `pytest test/test_dao_base.py -v` passes
- [ ] `pytest test/ -v` still 100% green (no changes to existing code)
- [ ] Import `from dao.base_dao import BaseDAO` works

**Audit Trail Artifacts:**
- [ ] DAO base implementation code
- [ ] DAO base unit tests
- [ ] No regressions in existing tests

---

#### CHUNK_1: Migrate User Entity Functions to DAO

**Type:** Code (refactor)
**Dependencies:** CHUNK_0
**Parallelizable:** No
**Risk Level:** Medium
**Est. Duration:** 45 minutes

**Goal:** Route all user-related queries through DAO.

**Tasks:**
1. Create `dao/user_dao.py` extending `BaseDAO`
2. Implement `get_by_username(username: str) -> dict | None`
3. Implement `get_profile(user_id: int) -> dict | None`
4. Update `models.py`: `get_user_by_username()` → call `UserDAO.get_by_username()`
5. Update `models.py`: `get_user_profile()` → call `UserDAO.get_profile()`
6. Keep function signatures identical (zero API change)

**Files Created:**
- `dao/user_dao.py`

**Files Modified:**
- `models.py` (lines ~574-599): Refactor user functions to delegate to DAO

**Migration Pattern:**
```python
# OLD (models.py)
def get_user_by_username(username: str) -> dict | None:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql("SELECT * FROM users WHERE username = ?"), (username,))
    user = cursor.fetchone()
    conn.close()
    return _row_to_dict(user)

# NEW (models.py)
def get_user_by_username(username: str) -> dict | None:
    dao = UserDAO()
    return dao.get_by_username(username)

# NEW (dao/user_dao.py)
class UserDAO(BaseDAO):
    def get_by_username(self, username: str) -> dict | None:
        self.get_connection()
        self.cursor.execute(self._sql("SELECT * FROM users WHERE username = ?"), (username,))
        user = self.cursor.fetchone()
        self.close()
        return _row_to_dict(user)  # Reuse existing helper
```

**Critical Routes Affected:**
- `api/login.py` → `get_user_by_username()` (login flow)
- `api/profile.py` → `get_user_profile()` (profile page)

**Test-First Notes:**
- No new tests needed (existing tests cover behavior)
- `test/test_banking_routes.py::test_login_post_demo_redirects_to_dashboard` must pass
- `test/test_profile_route.py` must pass

**Verification:**
- [ ] `pytest test/test_banking_routes.py -v` passes
- [ ] `pytest test/test_profile_route.py -v` passes
- [ ] `pytest test/ -v` still 100% green
- [ ] Manual test: Login as "demo" user succeeds
- [ ] Manual test: View /profile page shows user info

**Audit Trail Artifacts:**
- [ ] UserDAO implementation
- [ ] models.py diff showing delegation
- [ ] Test output showing green

---

#### CHUNK_2: Migrate Account Entity Functions to DAO

**Type:** Code (refactor)
**Dependencies:** CHUNK_1
**Parallelizable:** No
**Risk Level:** Medium
**Est. Duration:** 45 minutes

**Goal:** Route all account-related queries through DAO.

**Tasks:**
1. Create `dao/account_dao.py` extending `BaseDAO`
2. Implement `get_by_user(user_id: int) -> list[dict]`
3. Implement `get_by_id(account_id: int) -> dict | None`
4. Implement `update_balance(account_id: int, amount: float) -> None`
5. Update `models.py`: `get_accounts_by_user()` → call `AccountDAO.get_by_user()`
6. Update `models.py`: `get_account_by_id()` → call `AccountDAO.get_by_id()`

**Files Created:**
- `dao/account_dao.py`

**Files Modified:**
- `models.py` (lines ~601-622): Refactor account functions to delegate to DAO

**Critical Routes Affected:**
- `api/dashboard.py` → `get_accounts_by_user()` (main dashboard)
- `api/transfer.py` → `get_accounts_by_user()` (transfer page)
- `api/accounts.py` → `get_account_by_id()` (account detail)
- `api/api_endpoints.py` → `get_accounts_by_user()` (API)

**Test-First Notes:**
- `test/test_banking_routes.py::test_login_post_demo_followed_renders_dashboard` must pass
- `test/test_api_routes.py::test_api_accounts_requires_login` must pass

**Verification:**
- [ ] `pytest test/test_banking_routes.py -v` passes
- [ ] `pytest test/test_api_routes.py -v` passes
- [ ] `pytest test/ -v` still 100% green
- [ ] Manual test: Dashboard shows accounts with balances
- [ ] Manual test: /api/accounts returns JSON

**Audit Trail Artifacts:**
- [ ] AccountDAO implementation
- [ ] models.py diff showing delegation
- [ ] Test output showing green

---

#### CHUNK_3: Migrate Transaction Entity Functions to DAO

**Type:** Code (refactor)
**Dependencies:** CHUNK_2
**Parallelizable:** No
**Risk Level:** Medium
**Est. Duration:** 45 minutes

**Goal:** Route all transaction-related queries through DAO.

**Tasks:**
1. Create `dao/transaction_dao.py` extending `BaseDAO`
2. Implement `get_by_account(account_id: int, limit: int) -> list[dict]`
3. Implement `get_by_user(user_id: int, limit: int) -> list[dict]`
4. Implement `create(account_id, type, amount, desc, recipient) -> int`
5. Update `models.py`: `get_transactions_by_account()` → call `TransactionDAO.get_by_account()`
6. Update `models.py`: `get_all_transactions_by_user()` → call `TransactionDAO.get_by_user()`
7. Update `models.py`: `create_transaction()` → call `TransactionDAO.create()`

**Files Created:**
- `dao/transaction_dao.py`

**Files Modified:**
- `models.py` (lines ~624-705): Refactor transaction functions to delegate to DAO

**Critical Routes Affected:**
- `api/dashboard.py` → `get_all_transactions_by_user()` (recent transactions widget)
- `api/transactions.py` → `get_all_transactions_by_user()` (transactions page)
- `api/accounts.py` → `get_transactions_by_account()` (account detail)
- `api/api_endpoints.py` → `get_all_transactions_by_user()` (API)

**Test-First Notes:**
- `test/test_banking_routes.py::test_dashboard_shows_recent_transactions` (if exists) must pass
- `test/test_api_routes.py::test_api_transactions_*` must pass

**Verification:**
- [ ] `pytest test/test_banking_routes.py -v` passes
- [ ] `pytest test/test_api_routes.py -v` passes
- [ ] `pytest test/ -v` still 100% green
- [ ] Manual test: Dashboard shows recent transactions
- [ ] Manual test: /transactions page loads

**Audit Trail Artifacts:**
- [ ] TransactionDAO implementation
- [ ] models.py diff showing delegation
- [ ] Test output showing green

---

#### CHUNK_4: Migrate Transfer + Rewards (Transaction Management)

**Type:** Code (refactor)
**Dependencies:** CHUNK_3
**Parallelizable:** No
**Risk Level:** HIGH
**Est. Duration:** 60 minutes

**Goal:** Route complex transfer logic (with transaction commit/rollback) through DAO.

**Tasks:**
1. Extend `AccountDAO` with `transfer(from_id, to_id, amount, desc) -> bool`
2. Move `transfer_money()` transaction logic into DAO
3. Move rewards ledger logic into `dao/rewards_dao.py`
4. Implement `RewardsDAO.insert_points()` and `get_points_for_user()`
5. Update `models.py`: `transfer_money()` → call `AccountDAO.transfer()`
6. Update `models.py`: `get_rewards_points_for_user()` → call `RewardsDAO.get_points_for_user()`
7. Ensure transaction commit/rollback works correctly in DAO

**Files Created:**
- `dao/rewards_dao.py`

**Files Modified:**
- `dao/account_dao.py` (add transfer method)
- `models.py` (lines ~707-813): Refactor transfer and rewards to delegate to DAO

**Critical Logic:**
- **Transaction management:** Transfer must commit on success, rollback on error
- **Authorization check:** `acting_user_id` must own `from_account_id`
- **Rewards points:** Insert into rewards_ledger if feature enabled
- **Balance updates:** Debit from_account, credit to_account atomically

**Critical Routes Affected:**
- `api/transfer.py` → `transfer_money()` (HTML transfer form)
- `api/transfer.py` → `handle_api_transfer()` (API transfer)
- `api/dashboard.py` → `get_rewards_points_for_user()` (rewards banner)

**Test-First Notes:**
- `test/test_banking_routes.py::test_transfer_*` must all pass
- `test/test_demo_rollout.py` (rewards flag tests) must pass
- Test rollback scenario: insufficient funds should not corrupt DB

**Verification:**
- [ ] `pytest test/test_banking_routes.py -v` passes
- [ ] `pytest test/test_demo_rollout.py -v` passes
- [ ] `pytest test/ -v` still 100% green
- [ ] Manual test: Transfer money between accounts works
- [ ] Manual test: Transfer with invalid amount shows error
- [ ] Manual test: Transfer from wrong user's account fails (403)
- [ ] Manual test: Rewards points appear if flag enabled

**Audit Trail Artifacts:**
- [ ] AccountDAO.transfer() implementation
- [ ] RewardsDAO implementation
- [ ] models.py diff showing delegation
- [ ] Test output showing green

---

#### CHUNK_5: Cleanup and Final Validation

**Type:** Cleanup + verification
**Dependencies:** CHUNK_4
**Parallelizable:** No
**Risk Level:** Low
**Est. Duration:** 30 minutes

**Goal:** Remove dead code, verify no direct DB calls remain outside DAO, final smoke test.

**Tasks:**
1. Search for orphaned `get_db()` calls in models.py
2. Search for orphaned `conn.cursor()` calls outside DAO
3. Remove unused helper functions if any (e.g., old `_insert_returning_id` if moved to DAO)
4. Update docstrings in models.py to indicate "delegates to DAO"
5. Run full test suite 3 times to check for flakiness
6. Run manual smoke test of entire app
7. Check PostgreSQL backend if possible (CI or local Postgres)

**Files Modified:**
- `models.py` (cleanup, docstrings)
- `dao/*.py` (docstrings, type hints)

**Verification Commands:**
```bash
# Check for missed DB calls
grep -n "get_db()" models.py           # Should only appear in get_db() definition
grep -n "conn.cursor()" models.py      # Should not appear
grep -rn "conn = get_db()" api/        # Should not appear
grep -rn "cursor.execute" models.py    # Should not appear (moved to DAO)

# Full test suite (run 3x to catch flakiness)
pytest test/ -v
pytest test/ -v
pytest test/ -v

# Coverage check (optional)
pytest test/ --cov=dao --cov=models --cov-report=term-missing

# Manual smoke test
python app.py
# Browser: http://127.0.0.1:5001/login → dashboard → transfer → profile → logout
```

**Test-First Notes:**
- No new tests (pure cleanup)
- All existing tests must stay green

**Verification:**
- [ ] No `conn.cursor()` outside `dao/` directory
- [ ] No `get_db()` calls in `api/` or route handlers
- [ ] All tests pass 3 times in a row
- [ ] Manual smoke test: login → dashboard → transfer → profile → logout
- [ ] PostgreSQL backend works (if testable)

**Audit Trail Artifacts:**
- [ ] grep output showing clean separation
- [ ] Test output (3 runs)
- [ ] Manual test checklist
- [ ] Coverage report (optional)

---

## Phase 3: EXECUTE — Execution Plan

### Sequential Dependencies

```
1. Execute CHUNK_0 → Validate (tests green, DAO imports work)
2. Execute CHUNK_1 → Validate (login/profile routes work)
3. Execute CHUNK_2 → Validate (dashboard/accounts work)
4. Execute CHUNK_3 → Validate (transactions work)
5. Execute CHUNK_4 → Validate (transfer/rewards work)
6. Execute CHUNK_5 → Validate (full smoke test + grep checks)
```

**Between Each Chunk:**
- Run `pytest test/ -v` (must be 100% green)
- Git commit with clear message: `"CHUNK_X: <description> (all tests green)"`
- Manual test critical path if chunk touched login/dashboard/transfer

### Rollback Strategy

| Chunk | Rollback | Recovery |
|-------|----------|----------|
| CHUNK_0 | `git reset --hard HEAD~1` | ~10s (delete dao/ dir) |
| CHUNK_1 | `git reset --hard HEAD~1` | ~10s (revert models.py user functions) |
| CHUNK_2 | `git reset --hard HEAD~1` | ~10s (revert models.py account functions) |
| CHUNK_3 | `git reset --hard HEAD~1` | ~10s (revert models.py transaction functions) |
| CHUNK_4 | `git reset --hard HEAD~1` | ~30s (complex, may need to revert 2 commits) |
| CHUNK_5 | `git reset --hard HEAD~1` | ~10s (cleanup only) |

**Rollback Trigger:**
- Any test failures that can't be fixed in < 5 minutes
- Manual smoke test fails (e.g., can't login, can't transfer)
- Merge conflict or unexpected side effects

**Recovery Plan:**
- Keep each commit small and atomic
- Commit message includes "all tests green" confirmation
- Document any unexpected issues in commit message
- Can cherry-pick good chunks if later chunk fails

---

## Critical Files Reference

### Files to Create
1. `dao/__init__.py` — Package init
2. `dao/base_dao.py` — Base DAO with connection management
3. `dao/connection_manager.py` — Connection factory (optional, may inline in base)
4. `dao/user_dao.py` — User queries
5. `dao/account_dao.py` — Account queries + transfer
6. `dao/transaction_dao.py` — Transaction queries + create
7. `dao/rewards_dao.py` — Rewards ledger queries
8. `test/test_dao_base.py` — DAO base unit tests

### Files to Modify
1. `models.py` — Refactor all functions to delegate to DAO (keep function signatures)

### Files to Verify (Read-Only)
1. `api/login.py` — Should NOT need changes (imports from models)
2. `api/dashboard.py` — Should NOT need changes
3. `api/transfer.py` — Should NOT need changes
4. `api/profile.py` — Should NOT need changes
5. `test/test_banking_routes.py` — Should NOT need changes (tests behavior)
6. `test/test_api_routes.py` — Should NOT need changes
7. `test/conftest.py` — Should NOT need changes (DB fixture)

### Files to Ignore
- `venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`
- `*.db`, `.env`, `.coverage`
- `node_modules/`, `static/`, `templates/` (frontend)
- `.local/planning/` (this plan file is in branch root, not .local)

---

## Testing & Verification

### Test Harness
- **Command:** `pytest test/ -v`
- **Markers:** `pytest test/ -m banking`, `pytest test/ -m api`
- **Coverage:** `pytest test/ --cov=dao --cov=models --cov-report=term-missing`
- **CI:** Harness pipeline (see `HARNESS.md`) runs on push to `main`
- **DB Isolation:** `test/conftest.py` sets `QUANTUM_BANK_DATABASE` env for test isolation

### Pre-Execution Checks
- [x] Clean `main` → switched to `feature/quantum-dao-refactor`
- [ ] `pip install -r requirements.txt` (should be no new deps)
- [ ] `pytest test/ -v` passes on branch baseline (CRITICAL)
- [ ] Document baseline test output: `pytest test/ -v | tee baseline-test-output.txt`

### Post-Execution Checks
- [ ] All tests pass: `pytest test/ -v`
- [ ] No direct DB calls outside DAO: `grep -rn "conn.cursor()" models.py api/`
- [ ] Manual smoke test: login → dashboard → transfer → profile → logout
- [ ] PostgreSQL flag still works (test locally or CI)
- [ ] No secrets committed: `git diff main --name-only | xargs grep -i "password\|secret\|token"` (should be empty)

### Manual Test Plan
| Case | Steps | Expected | Pass |
|------|-------|----------|------|
| **Login** | Navigate to /login, enter "demo", submit | Redirect to /dashboard | ☐ |
| **Dashboard** | After login, view dashboard | Shows accounts, balance, recent transactions | ☐ |
| **Account List** | Dashboard shows accounts | At least 2 accounts visible (checking, savings) | ☐ |
| **Recent Transactions** | Dashboard shows transactions | At least 1 transaction visible | ☐ |
| **Transfer Form** | Navigate to /transfer | Form renders with account dropdowns | ☐ |
| **Transfer Submit** | Fill form: from=checking, to=savings, amount=50, submit | Success message appears, balances update | ☐ |
| **Transfer Validation** | Try transfer with negative amount | Error message "Invalid amount" | ☐ |
| **Profile Page** | Navigate to /profile | Shows username, email, full_name, address | ☐ |
| **API Accounts** | GET /api/accounts (logged in) | Returns JSON array of accounts | ☐ |
| **API Transactions** | GET /api/transactions (logged in) | Returns JSON array of transactions | ☐ |
| **Logout** | Click logout | Redirect to /, session cleared | ☐ |

---

## Adversarial Review Checklist

**For Independent Model Review (Grok/Gemini):**

### Completeness
- [ ] Are ALL database calls routed through DAO? (grep verification)
- [ ] Are there any orphaned `conn.cursor()` calls in non-DAO code?
- [ ] Are helper functions like `_row_to_dict`, `_normalize_row` properly reused?
- [ ] Is `_sql()` query converter available in DAO for Postgres support?

### Correctness
- [ ] Does `transfer_money()` still enforce authorization (`acting_user_id` check)?
- [ ] Are transactions committed/rolled back correctly in DAO?
- [ ] Does rewards ledger insertion still respect feature flags?
- [ ] Are all function signatures preserved (no breaking API changes)?

### Test Coverage
- [ ] Do all existing tests pass unchanged?
- [ ] Are there tests for DAO connection lifecycle?
- [ ] Are there tests for transaction rollback scenarios?
- [ ] Is test isolation maintained (no cross-test state leaks)?

### Error Handling
- [ ] Are exceptions propagated correctly from DAO to models to routes?
- [ ] Is connection cleanup (`close()`) guaranteed even on exceptions?
- [ ] Are error messages preserved (no UX regressions)?

### Performance
- [ ] Are there any obvious N+1 query patterns introduced?
- [ ] Is connection management overhead acceptable? (out of scope, but flag if obvious)

### Security
- [ ] Are SQL queries still parameterized (no injection risk)?
- [ ] Is authorization check still present in transfer flow?
- [ ] Are password/secret fields properly excluded from profile queries?

### PostgreSQL Compatibility
- [ ] Does `_sql()` helper work for both SQLite (?) and Postgres (%s)?
- [ ] Are `RETURNING` clauses handled for both backends?
- [ ] Does `using_postgres()` flag still control backend choice?

---

## Post-Sprint Validation

**After all chunks complete:**

1. **Full test suite:** `pytest test/ -v` (must be 100% green)
2. **Grep audit:** No `conn.cursor()` outside `dao/`, no `get_db()` in `api/`
3. **Manual smoke test:** All 12 test cases in manual test plan pass
4. **Coverage report:** `pytest test/ --cov=dao --cov=models --cov-report=html`
5. **Git history:** Clean commits, each with "all tests green" message
6. **PR ready:** Branch ready for review, CI will run on push to main

**Document in RESULTS.md:**
- Actual time spent per chunk
- Any unexpected issues or deviations from plan
- Test pass rate (should be 100%)
- Manual test results
- Lessons learned
- Follow-up work (if any)

---

## Out of Scope (Defer to Future Sprints)

### Performance Optimization Sprint
- Connection pooling (e.g., `psycopg2.pool` or SQLAlchemy pool)
- Query optimization (indexes, EXPLAIN analysis)
- N+1 query elimination
- Redis caching layer
- Read replicas

### ORM Migration Sprint
- Replace raw SQL with SQLAlchemy or similar ORM
- Type-safe query builders
- Automatic schema migrations

### Enhanced Error Handling Sprint
- Custom exception hierarchy (`DAOException`, `NotFoundError`, etc.)
- Retry logic for transient DB errors
- Circuit breaker for DB unavailability
- Better error messages for users

### Testing Infrastructure Sprint
- Pytest fixtures for DAO mocking
- Factory pattern for test data
- Contract tests for DAO interface
- Property-based testing (Hypothesis)

### Monitoring & Observability Sprint
- Query timing metrics per DAO method
- Slow query logging
- Connection pool metrics
- Distributed tracing (OpenTelemetry)

---

## Appendix: DAO Design Patterns

### Chosen Pattern: Simple DAO with Delegation

**Why:**
- Minimal disruption to existing code
- Function signatures in `models.py` stay the same (API compatible)
- Routes don't need to change imports
- Easy to review (clear before/after in each chunk)

**Trade-offs:**
- `models.py` becomes a thin wrapper (could be removed later)
- Two layers to navigate during debugging (models → DAO)
- Not using full Repository pattern (no interface for swapping implementations)

**Future Evolution Path:**
1. **This sprint:** models.py delegates to DAO (thin wrapper)
2. **Future sprint:** Routes import DAO directly, deprecate models.py wrappers
3. **Future sprint:** Introduce Repository interface for swappable backends

### Alternative Patterns Considered (Not Used)

**Repository Pattern:**
- Pros: Clean interface, easy to swap implementations (SQL vs NoSQL)
- Cons: More upfront design, more files, overkill for this refactor
- Decision: Defer to future sprint if needed

**Active Record Pattern (ORM):**
- Pros: Objects handle their own persistence, less boilerplate
- Cons: Requires ORM (SQLAlchemy), large refactor, out of scope
- Decision: Defer to ORM migration sprint

**Service Layer + DAO:**
- Pros: Clean separation of business logic (service) and data access (DAO)
- Cons: Adds another layer, more refactoring needed
- Decision: Business logic is simple enough to stay in routes for now

---

## Appendix: Key Code Locations

### Current Database Call Sites (Pre-Refactor)

**User Queries:**
- `models.py:574` — `get_user_by_username(username)` → used by login
- `models.py:584` — `get_user_profile(user_id)` → used by profile page

**Account Queries:**
- `models.py:601` — `get_accounts_by_user(user_id)` → used by dashboard, transfer, API
- `models.py:614` — `get_account_by_id(account_id)` → used by account detail

**Transaction Queries:**
- `models.py:624` — `get_transactions_by_account(account_id, limit)` → used by account detail
- `models.py:642` — `get_all_transactions_by_user(user_id, limit)` → used by dashboard, API
- `models.py:672` — `create_transaction(...)` → used by transfer

**Transfer Logic:**
- `models.py:707` — `transfer_money(from, to, amount, desc, acting_user_id)` → complex transaction

**Rewards Queries:**
- `models.py:334` — `get_rewards_points_for_user(user_id)` → used by dashboard
- `models.py:299` — `try_insert_rewards_points(...)` → used by transfer

**Cards Queries:**
- `models.py:662` — `get_cards_by_account(account_id)` → used by account detail (might be dead code)

### Helper Functions to Reuse
- `models.py:62` — `_row_to_dict(row)` → convert DB row to dict
- `models.py:70` — `_normalize_row(row_dict)` → normalize Decimal/types
- `models.py:58` — `_sql(query)` → convert ? to %s for Postgres
- `models.py:87` — `_split_sql_statements(sql)` → parse migration files
- `models.py:375` — `_insert_returning_id(cursor, sql, params)` → INSERT RETURNING id

---

**END OF PLAN**

---

## Next Steps (for Execution Agent)

1. **Read this plan fully** before starting any chunk
2. **Establish test baseline:** `pytest test/ -v | tee baseline-test-output.txt`
3. **Execute CHUNK_0:** Create DAO base classes
4. **Validate:** Tests still green
5. **Execute CHUNK_1:** Migrate user functions
6. **Validate:** Tests still green, login works
7. **Continue sequentially** through CHUNK_2, 3, 4, 5
8. **Final validation:** Full smoke test + grep audit
9. **Commit with clear message:** Each chunk is one commit
10. **PR to main:** Ready for independent model review (Grok/Gemini)

**DO NOT PROCEED until all tests are green after each chunk.**
**DO NOT skip manual smoke tests for critical paths.**
**DO NOT commit code that breaks existing tests.**

---

**Plan Version:** 1.0
**Created:** 2026-08-12
**Author:** Claude Sonnet 4.5 (adversarial sprint method)
**Review Status:** Ready for independent review (Grok/Gemini)
