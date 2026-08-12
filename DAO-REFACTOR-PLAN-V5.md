# AI Sprint Planning — QuantumBank DAO Refactor (V5)

**Scope-Down Strategy: Read-Only First, Complex Transactions Later**

**Status:** Execution-Ready (Part 1 of 2)  
**Review Cycle:** V1-V4 → Scope collapse identified → V5 (safe subset)

---

## Strategic Decision: Staged Refactoring

**Why scope down:**
- V4 accumulated contradictions that create execution risk
- Monkeypatch bindings, circular imports, transaction semantics too tightly coupled
- Easier to ship safe subset, learn, then tackle transfer/rewards separately
- Part 1 validates DAO pattern before applying to complex transactions

**V5 Scope: Read-Only Data Access Layer (Safe, Provable)**

Part 1 (THIS SPRINT — V5):
- ✅ User queries (get_user_by_username, get_user_profile)
- ✅ Account queries (get_accounts_by_user, get_account_by_id)
- ✅ Card queries (get_cards_by_account)
- ✅ Transaction reads (get_all_transactions_by_user, get_transactions_by_account)
- ✅ DAO base layer (connection management, helpers)

Part 2 (FUTURE SPRINT — separate):
- ❌ NOT in V5: transfer_money() (complex transaction, rewards coupling)
- ❌ NOT in V5: Schema/initialization (needs transaction boundary clarity)
- ❌ NOT in V5: Rewards ledger (tied to transfer, monkeypatch complexity)
- ❌ NOT in V5: Mutations (create_transaction)

**Why this split works:**
- Part 1 has zero cross-request state issues (read-only)
- Part 1 has zero transaction boundary questions (no writes)
- Part 1 has zero circular import risk (simple delegation)
- Part 1 can pass validators with confidence
- Part 2 learned from Part 1's patterns

---

## Sprint Metadata

**Sprint Name:** QuantumBank DAO Refactor — Part 1: Read-Only Layer
**Date:** 2026-08-12
**Sprint Type:** Refactor (scoped)
**Priority:** P2-Medium
**Estimated Duration:** 1 day (simplified scope)
**Status:** ✅ Ready for Execution
**Branch:** `feature/quantum-dao-refactor-v5`

---

## Phase 1: GROK — Problem Analysis (Read-Only Scope)

### Current State

**Functions in V5 scope (8 total):**
1. `get_user_by_username(username)` — models.py:574-580
2. `get_user_profile(user_id)` — models.py:584-598
3. `get_accounts_by_user(user_id)` — models.py:601-612
4. `get_account_by_id(account_id)` — models.py:614-622
5. `get_transactions_by_account(account_id, limit)` — models.py:624-640
6. `get_all_transactions_by_user(user_id, limit)` — models.py:642-660
7. `get_cards_by_account(account_id)` — models.py:662-669
8. `get_rewards_points_for_user(user_id)` — models.py:334-372 (READ-ONLY)

**Pattern (all identical):**
```python
def get_X_by_Y(Y_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql("SELECT ..."))
    result = cursor.fetchone/fetchall()
    conn.close()
    return _row_to_dict(result)
```

**Why safe:**
- No state changes (pure SELECT)
- No transaction boundaries (each query is independent)
- No monkeypatch issues (mocking works at query layer)
- No circular dependencies (read helpers stay in models)

### Risk Assessment (V5 Simplified)

| Risk | Severity | Probability | Impact | Mitigation |
|------|----------|-------------|--------|------------|
| **Import cycle** | LOW | LOW | (No cycle: DAO reads from models only) | — |
| **Transaction issues** | N/A | N/A | (No writes, no txn) | — |
| **Monkeypatch break** | LOW | LOW | (Tests use mock at query layer) | Keep query functions in models wrapper |
| **Test isolation** | MEDIUM | MEDIUM | (Fixture state varies) | Use fresh DB per test (existing conftest handles) |
| **Connection leak** | LOW | MEDIUM | (No try/finally yet) | **Add try/finally during CHUNK_0** |

---

## Phase 2: CHUNK — Task Breakdown (V5)

### Dependency Graph

```
CHUNK_0 (DAO base + read-only helpers)
    ↓
CHUNK_1 (UserDAO: get_user_by_username, get_user_profile)
    ↓
CHUNK_2 (AccountDAO: get_accounts_by_user, get_account_by_id, get_cards_by_account)
    ↓
CHUNK_3 (TransactionDAO: get_transactions_by_account, get_all_transactions_by_user, get_rewards_points_for_user)
    ↓
CHUNK_4 (Cleanup + validation)
```

---

## Chunk Definitions

### CHUNK_0: DAO Base + Read-Only Helpers

**Type:** Code (new files)
**Goal:** Create DAO foundation for read-only queries

**Tasks:**
1. Create `dao/__init__.py`
2. Create `dao/base_dao.py` with:
   - `BaseDAO` class (get_connection, close with try/finally)
   - Module-level helpers (re-use existing):
     - `_sql(query)` → imported from models, no copy
     - `_row_to_dict(row)` → imported from models, no copy
     - `_normalize_row()` → imported from models, no copy
3. Create `test/test_dao_base.py` (unit tests for connection lifecycle)
4. Add re-export shim to models.py (no behavioral change)

**Key: Helpers are NOT moved. They stay in models.py. DAO imports them.**

```python
# dao/base_dao.py
from models import _sql, _row_to_dict, _normalize_row  # Import, don't copy

class BaseDAO:
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def get_connection(self):
        from models import get_db
        self.conn = get_db()
        self.cursor = self.conn.cursor()
        return self.cursor
    
    def close(self):
        if self.conn:
            self.conn.close()
```

**No circular imports.** Models doesn't import dao at module level; DAO imports from models at module level. One direction only.

**Verification:**
- [ ] `python -c "import models; from dao.base_dao import BaseDAO; print('OK')"` — no import error
- [ ] `pytest test/test_dao_base.py -v` passes
- [ ] `pytest test/ -v` still 100% green (no behavior change)

**Files Created:**
- `dao/__init__.py`
- `dao/base_dao.py`
- `test/test_dao_base.py`

**Files Modified:**
- None (no changes to models.py yet)

---

### CHUNK_1: UserDAO (Read-Only)

**Type:** Code (refactor)
**Goal:** Route user queries through DAO

**Tasks:**
1. Create `dao/user_dao.py`:
```python
from dao.base_dao import BaseDAO, _row_to_dict

class UserDAO(BaseDAO):
    def get_by_username(self, username: str):
        """Get user by username."""
        self.get_connection()
        try:
            self.cursor.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            )
            user = self.cursor.fetchone()
            return _row_to_dict(user) if user else None
        finally:
            self.close()
    
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
            profile["address"] = PROFILE_DEMO_ADDRESS  # Keep existing logic
            return profile
        finally:
            self.close()
```

2. Update `models.py` (wrapper only):
```python
def get_user_by_username(username: str) -> dict | None:
    """Wrapper — delegates to UserDAO."""
    from dao.user_dao import UserDAO
    return UserDAO().get_by_username(username)

def get_user_profile(user_id: int) -> dict | None:
    """Wrapper — delegates to UserDAO."""
    from dao.user_dao import UserDAO
    return UserDAO().get_profile(user_id)
```

**Verification:**
- [ ] `pytest test/test_banking_routes.py::test_login_post_demo_redirects_to_dashboard -v` passes
- [ ] `pytest test/ -v` still 100% green

---

### CHUNK_2: AccountDAO (Read-Only)

**Type:** Code (refactor)
**Goal:** Route account queries through DAO

**Tasks:**
1. Create `dao/account_dao.py`:
```python
from dao.base_dao import BaseDAO, _row_to_dict, _normalize_row

class AccountDAO(BaseDAO):
    def get_by_user(self, user_id: int):
        """Get all accounts for user."""
        self.get_connection()
        try:
            self.cursor.execute(
                "SELECT * FROM accounts WHERE user_id = ? ORDER BY created_at",
                (user_id,)
            )
            accounts = self.cursor.fetchall()
            return [_normalize_row(_row_to_dict(a)) for a in accounts]
        finally:
            self.close()
    
    def get_by_id(self, account_id: int):
        """Get account by ID."""
        self.get_connection()
        try:
            self.cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
            account = self.cursor.fetchone()
            return _normalize_row(_row_to_dict(account)) if account else None
        finally:
            self.close()
    
    def get_cards_by_account(self, account_id: int):
        """Get cards for account."""
        self.get_connection()
        try:
            self.cursor.execute("SELECT * FROM cards WHERE account_id = ?", (account_id,))
            cards = self.cursor.fetchall()
            return [_normalize_row(_row_to_dict(c)) for c in cards]
        finally:
            self.close()
```

2. Update `models.py`:
```python
def get_accounts_by_user(user_id: int):
    from dao.account_dao import AccountDAO
    return AccountDAO().get_by_user(user_id)

def get_account_by_id(account_id: int):
    from dao.account_dao import AccountDAO
    return AccountDAO().get_by_id(account_id)

def get_cards_by_account(account_id: int):
    from dao.account_dao import AccountDAO
    return AccountDAO().get_cards_by_account(account_id)
```

**Verification:**
- [ ] `pytest test/test_banking_routes.py::test_login_post_demo_followed_renders_dashboard -v` passes
- [ ] Manual test: Dashboard shows accounts + cards
- [ ] `pytest test/ -v` still 100% green

---

### CHUNK_3: TransactionDAO (Read-Only)

**Type:** Code (refactor)
**Goal:** Route transaction queries through DAO

**Tasks:**
1. Create `dao/transaction_dao.py`:
```python
from dao.base_dao import BaseDAO, _row_to_dict, _normalize_row

class TransactionDAO(BaseDAO):
    def get_by_account(self, account_id: int, limit: int = 10):
        """Get transactions for account."""
        self.get_connection()
        try:
            self.cursor.execute(
                "SELECT * FROM transactions WHERE account_id = ? ORDER BY created_at DESC LIMIT ?",
                (account_id, limit)
            )
            transactions = self.cursor.fetchall()
            return [_normalize_row(_row_to_dict(t)) for t in transactions]
        finally:
            self.close()
    
    def get_by_user(self, user_id: int, limit: int = 20):
        """Get all transactions for user."""
        self.get_connection()
        try:
            self.cursor.execute("""
                SELECT t.* FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE a.user_id = ?
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (user_id, limit))
            transactions = self.cursor.fetchall()
            return [_normalize_row(_row_to_dict(t)) for t in transactions]
        finally:
            self.close()
    
    def get_rewards_for_user(self, user_id: int):
        """Get total rewards for user (read-only)."""
        self.get_connection()
        try:
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
```

2. Update `models.py`:
```python
def get_transactions_by_account(account_id: int, limit: int = 10):
    from dao.transaction_dao import TransactionDAO
    return TransactionDAO().get_by_account(account_id, limit)

def get_all_transactions_by_user(user_id: int, limit: int = 20):
    from dao.transaction_dao import TransactionDAO
    return TransactionDAO().get_by_user(user_id, limit)

def get_rewards_points_for_user(user_id: int):
    from dao.transaction_dao import TransactionDAO
    points, error = TransactionDAO().get_rewards_for_user(user_id)
    return points, error
```

**Verification:**
- [ ] `pytest test/ -v` still 100% green
- [ ] Manual test: Dashboard shows recent transactions + rewards points

---

### CHUNK_4: Cleanup + Validation

**Type:** Verification
**Goal:** Confirm refactor complete, all tests pass

**Tasks:**
1. Run full test suite 3x:
```bash
pytest test/ -v
pytest test/ -v
pytest test/ -v
```

2. Grep verification (simplified for read-only scope):
```bash
# Check that query functions in models.py now delegate to DAO
grep -n "def get_user_by_username\|def get_accounts_by_user\|def get_transactions_by_account" models.py
# Each should contain: "from dao.*.py import ...; return DAO().method(...)"

# Verify no direct cursor.execute in query function bodies
# (helpers stay in models, so cursor is OK in helper definitions)
python3 << 'EOF'
import ast
with open('models.py') as f:
    tree = ast.parse(f.read())

query_functions = [
    'get_user_by_username', 'get_user_profile',
    'get_accounts_by_user', 'get_account_by_id', 'get_cards_by_account',
    'get_transactions_by_account', 'get_all_transactions_by_user',
    'get_rewards_points_for_user'
]

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in query_functions:
        # Body should only have: from X import Y; return Y.method()
        # No direct cursor.execute in body
        for sub in ast.walk(node):
            if isinstance(sub, ast.Attribute):
                if sub.attr in ['execute', 'cursor']:
                    print(f"ERROR: {node.name} has direct cursor access")
EOF
```

3. Manual smoke test (simplified):
```bash
python app.py &
# Browser to http://127.0.0.1:5001/
# Test: Login → Dashboard (shows accounts, transactions) → Account detail (shows cards) → Profile
# All pages should load correctly
```

4. Baseline test count (for Part 2 reference):
```bash
pytest test/ --collect-only -q | wc -l  # Should be 98
```

**Verification:**
- [ ] All 98 tests pass
- [ ] Grep shows all 8 query functions delegate to DAO
- [ ] Manual smoke test: login → dashboard → profile → logout all work
- [ ] No direct cursor calls in query function bodies

---

## Test Strategy (V5 — Simple)

**Baseline:** 98 existing tests (verified count)

**Testing approach:**
- Run full suite 3x (flakiness check)
- All existing tests must pass unchanged
- No new tests needed (behavior unchanged)

**Critical paths (must pass):**
- `test_init_db_seeds_demo_on_empty_database` — user queries work
- `test_login_post_demo_redirects_to_dashboard` — login works
- `test_login_post_demo_followed_renders_dashboard` — dashboard queries work
- `test_demo_seeded_cards_expose_masked_last4_only` — account + cards queries work

---

## Success Criteria (V5)

- [ ] All 98 tests pass 3 times consecutively
- [ ] Query functions delegate to DAO (grep verification)
- [ ] Manual smoke test: login → dashboard → profile → logout
- [ ] No direct cursor calls in query function bodies
- [ ] Connection cleanup guaranteed (try/finally in DAO.close)
- [ ] Database queries still work correctly (behavior unchanged)

---

## What's NOT in V5 (Part 2 future sprint)

**Transfer refactoring:**
- ❌ `transfer_money()` stays in models.py (complex transaction)
- ❌ Account balance updates (writes, not reads)
- ❌ Transaction creation (write operation)
- ❌ Rewards insertion (tied to transfer transaction)

**Schema/Initialization:**
- ❌ `init_db()` stays in models.py
- ❌ `create_sample_data()` stays in models.py
- ❌ `ensure_rewards_ledger_schema()` stays in models.py
- ❌ Schema DAO (Part 2 work)

**Why defer:**
- Transfer has complex transaction semantics (multiple DAO writes atomically)
- Schema needs initialization boundary clarity
- Rewards is coupled to transfer
- Part 2 can learn from Part 1's patterns before tackling complexity

---

## Part 2 Outline (Future Sprint)

**Once V5 ships and validates:**

1. **Transfer refactoring (CHUNK_5 Part 2):**
   - Create `AccountDAO.transfer(from_id, to_id, amount, acting_user_id)` with atomic writes
   - Shared transaction: account updates + rewards insert on same connection
   - Savepoint for rewards error resilience

2. **Rewards refactoring (CHUNK_6 Part 2):**
   - Create `RewardsDAO` for ledger queries + insertion
   - Schema initialization under DAO

3. **Schema/Init refactoring (CHUNK_7 Part 2):**
   - Create `SchemaDAO` for init_db, create_sample_data
   - Keep simpler pattern (just move code)

4. **Testing strategy learned from Part 1:**
   - Mock patterns (what works, what doesn't)
   - Monkeypatch bindings
   - Transaction boundary testing

---

## Why This V5 Works

✅ **Safe:** Read-only queries, no state changes, no transaction boundaries  
✅ **Simple:** 8 functions, 3 DAOs, clear delegation pattern  
✅ **Provable:** All existing tests pass unchanged; behavior identical  
✅ **Learnable:** Establishes DAO pattern before complexity  
✅ **Splittable:** Part 2 decoupled; can start independently once Part 1 ships  

---

## Execution Plan

```
Pre-Execution: Document baseline (98 tests, git status clean)
    ↓
CHUNK_0: DAO base (30 min)
    ↓
CHUNK_1: UserDAO (15 min) → Test
    ↓
CHUNK_2: AccountDAO (15 min) → Test
    ↓
CHUNK_3: TransactionDAO (20 min) → Test
    ↓
CHUNK_4: Cleanup + validation (30 min)
    ↓
Total: ~110 min (~2 hours)
```

Each chunk commits when tests green. Sequential only (no parallelization).

---

**Plan Version:** 5.0-scope-down  
**Status:** ✅ READY FOR EXECUTION  
**Scope:** Part 1 (Read-only data layer) only  
**Part 2:** Deferred to future sprint (transfer, schema, rewards)  
**Next Step:** Execute CHUNK_0
