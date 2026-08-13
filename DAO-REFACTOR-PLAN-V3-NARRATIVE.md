# Plan Narrative: From V2 to V3

**Cross-Model Referee Review Synthesis**

Date: 2026-08-12  
Plan Evolution: V1 (original) → V2 (Claude audit) → **V3 (Grok + Gemini referee)**  
Ref Verdict: REJECT on V2 (11 findings, 5 BLOCKER-severity)  
Current Status: V3 READY FOR EXECUTION (all blockers resolved)

---

## What Happened

### The Process

1. **V1 Plan Created** (911 lines)
   - 6 chunks: User → Account → Transaction → Transfer/Rewards → Cleanup
   - Risk matrix, test strategy, rollback procedures
   - Ready for review

2. **Claude Audit** (3 independent agents, ~6 hours)
   - **Agent 1 (Completeness):** Found ~260 lines of orphaned init/schema code
   - **Agent 2 (Correctness):** Found resource leaks, transaction safety bugs
   - **Agent 3 (Test Coverage):** Found 3 critical missing tests, contradiction on test changes
   - **Verdict:** Plan 85% complete, has gaps but addressable

3. **V2 Plan Revised** (based on Claude findings)
   - Added CHUNK_5a to scope (schema/init)
   - Added helper lifecycle table (resolve test import ambiguity)
   - Added 3 critical missing tests
   - **Problem:** Cosmetic revision — scope bullets added but execution plan unchanged

4. **Grok + Gemini Ref Review** (cross-model panel, ~4 hours)
   - **Finding 1 (BLOCKER):** CHUNK_5a in scope but not in task breakdown — execution agent can't find it
   - **Finding 2 (BLOCKER):** Transfer signature missing `acting_user_id` parameter
   - **Finding 3 (BLOCKER):** Helpers as instance methods break re-export pattern (tests fail)
   - **Finding 4 (BLOCKER):** Transaction atomicity split — separate DAO instances each get own connection
   - **Finding 5 (HIGH):** Cards marked dead code but actually live (`get_cards_by_account` in api/accounts.py)
   - **Plus 6 more HIGH/MEDIUM findings**
   - **Verdict:** REJECT — blockers must be resolved before execution

5. **V3 Plan Fully Revised** (responding to ref blockers)
   - CHUNK_5a added to Phase 2 Task Breakdown (explicit execution steps)
   - Transfer signature corrected (includes `acting_user_id`)
   - Helpers changed to module-level functions (not instance methods)
   - Explicit connection-sharing pattern for transfer+rewards
   - Cards promoted to CHUNK_2c (first-class entity)
   - Test names replaced with real test file references (no hypotheticals)
   - PostgreSQL as hard exit criterion (not optional)
   - Cleanup greps rewritten for re-export reality
   - **Verdict:** READY FOR EXECUTION (all blockers resolved)

---

## Key Differences: What Ref Found That Claude Missed

### 1. Transaction Architecture (CRITICAL)

**Claude saw:** Transfer and rewards need to be in the same chunk  
**Ref saw:** If each DAO opens its own connection, transaction atomicity BREAKS

**The problem:**
```python
# WRONG (V2 implicit design):
class AccountDAO:
    def transfer(self, from_id, to_id, amount):
        self.get_connection()  # Connection A
        # Debit/credit
        rewards_dao = RewardsDAO()
        rewards_dao.get_connection()  # Connection B (SEPARATE!)
        # Rewards insert on connection B
        # If this fails, balance changes on A already committed

# CORRECT (V3 explicit design):
class AccountDAO:
    def transfer(self, from_id, to_id, amount):
        self.get_connection()  # Connection A
        # Debit/credit on A
        # Rewards on SAME cursor:
        self.cursor.execute("SAVEPOINT rewards_savepoint")
        try:
            try_insert_rewards_points(conn=self.conn, cursor=self.cursor)
            # SUCCESS: both changes atomic
        except:
            self.cursor.execute("ROLLBACK TO SAVEPOINT")
            # FAILURE: both changes rolled back
```

**Ref finding:** This is load-bearing. Silent behavior change if done wrong. Claude got close but didn't specify the connection-sharing pattern explicitly.

---

### 2. Helper Functions (CRITICAL)

**Claude saw:** Helpers need to be re-exported from models.py for backward compat  
**Ref saw:** If helpers are INSTANCE METHODS, re-export breaks

**V2 plan said:**
```python
# dao/base_dao.py
class BaseDAO:
    def _sql(self, query: str) -> str:  # ← INSTANCE METHOD
        return query.replace("?", "%s")
```

**Tests call:** `models._sql("SELECT ?")` — this is a module-level function call  
**Problem:** You can't re-export an instance method and have it work as a function

**V3 fix:**
```python
# dao/base_dao.py
def _sql(query: str) -> str:  # ← MODULE-LEVEL FUNCTION
    return query.replace("?", "%s")

# models.py (re-export)
from dao.base_dao import _sql
# Now tests work: models._sql("SELECT ?")
```

**Ref finding:** Gemini caught this immediately. Claude mentioned re-exports but didn't specify the distinction between instance methods and module-level functions.

---

### 3. Cards Are Live (HIGH)

**Claude assumption:** `get_cards_by_account()` might be dead code (mentioned in appendix)  
**Ref finding:** NO — it's imported and called in `api/accounts.py:28`

**Evidence:**
```python
# api/accounts.py (live code)
from models import get_cards_by_account
cards = get_cards_by_account(account_id)  # Line 28
```

**Impact:** If cards path isn't migrated to DAO, success criterion "zero direct calls outside DAO" fails silently.

**V3 fix:** Added CHUNK_2c as explicit task (not optional).

---

### 4. Scope/Execution Mismatch (HIGH)

**V2 said:**
- Scope: "CHUNK_5a — Schema & Initialization (NEW)" ← Listed as in-scope
- Phase 2 Task Breakdown: [No CHUNK_5a — went straight from CHUNK_4 to CHUNK_5]

**Ref finding (both Grok & Gemini):** Execution agent reads task breakdown, doesn't see CHUNK_5a, skips it. Success criterion fails (260 lines of init code orphaned).

**V3 fix:** CHUNK_5a now in Phase 2 with explicit tasks:
- init_db migration
- create_sample_data migration
- ensure_rewards_ledger_schema migration
- Est. 60 min, before CHUNK_5b

---

### 5. Function Inventory (MEDIUM)

**Claude:** "~28 public functions"  
**Ref:** Enumerated actual count = 27 (8 query, 3 mutation, 6 init, 10 helper)

**Why it matters:** Underestimating scope can miss functions. V3 makes it explicit so execution checklist is complete.

---

## What Claude Got Right (That Ref Didn't Emphasize)

### 1. Completeness Gap

Claude agents found that ~260 lines of init/schema code weren't assigned to any chunk. Ref agreed but didn't surface it as the PRIMARY finding; Claude did.

### 2. Test Coverage

Claude identified 3 critical missing tests (rollback, backend compat, schema resilience). Ref didn't audit test coverage in detail; took Claude's findings as-is.

### 3. Resource Leak Fixes

Claude flagged missing try/finally blocks in ~20 functions. Ref didn't dig into existing bugs; assumed plan fixes them.

### 4. Helper Lifecycle Clarity

Claude created a table mapping helpers to their new locations. Ref said "fix it" but Claude's table was the right format.

---

## How V3 Is Different From V2

| Aspect | V1/V2 | V3 |
|--------|-------|-----|
| **CHUNK_5a execution** | Scope only | Explicit Phase 2 tasks (init_db, create_sample_data, etc.) |
| **Helper methods** | Instance methods (breaks re-export) | Module-level functions (clean re-export) |
| **Transfer signature** | `transfer(from_id, to_id, amount, desc)` | `transfer(from_id, to_id, amount, desc, acting_user_id)` |
| **Connection sharing** | Separate DAOs (ACID violation) | Explicit pattern: one conn for transfer+rewards, savepoint on same cursor |
| **Cards** | Dead code hedge | CHUNK_2c explicit task |
| **Test names** | "if exists" hypotheticals | Real names: test_demo_rollout.py:212-266 |
| **PostgreSQL** | Optional "if testable" | Hard exit: DATABASE_URL=... pytest must pass |
| **Invented tasks** | update_balance() | Removed (create_transaction is atomic) |
| **Greps** | Assume no re-exports | Explicit allowed (re-imports) vs forbidden (direct DB in bodies) |
| **Function count** | ~28 (estimated) | 27 (enumerated) |

---

## Synthesis: What Different Model Families See

### Claude (Single Family — 3 Independent Agents)

**Strengths:**
- Thorough scope analysis (found init gap)
- Test/verification thinking (found missing tests)
- Existing code audit (found bugs: resource leaks, transaction safety)
- Plan structure (chunking, dependencies, rollback)

**Blindspots:**
- Didn't catch that instance methods ≠ module-level functions (method visibility)
- Didn't catch transaction split problem (connection semantics)
- Didn't verify that supposedly-dead code is actually live (codebase familiarity)
- Assumed architectural patterns would work (didn't model connection flow)

### Grok + Gemini (Cross-Family — Referee Panel)

**Strengths:**
- Architectural pattern validation (caught transaction split immediately)
- Type/method semantics (instance vs module-level)
- Code tracing (cards ARE used; update_balance DOESN'T exist)
- Execution-order thinking (scope vs task breakdown mismatch)

**Blindspots:**
- Didn't find resource leak bugs (lower-level code inspection)
- Didn't find test coverage gaps (less investment in existing tests)
- Didn't propose specific fixes for found bugs (said "fix it" but not "how")

---

## Why This Matters for Framework

**The adversarial-sprint framework works because:**

1. **Different angles catch different bugs** — not redundant, complementary
2. **Same-family review finds breadth** — one model family audits thoroughly within its domain
3. **Cross-family review validates architecture** — different models catch semantic contradictions
4. **Iteration tightens the plan** — feedback loop converges to executable design

**Result:** V3 is better than V2 not because one review was "better," but because both revealed different gaps.

---

## What Execution Needs to Know

**V3 is READY when:**
- [ ] All 4 BLOCKERs from ref are resolved (they are in V3)
- [ ] Connection-sharing pattern is explicit (it is: see CHUNK_4)
- [ ] Test names are real (they are: test_demo_rollout.py line numbers included)
- [ ] Scope and execution match (they do: CHUNK_5a in task breakdown)
- [ ] Helper functions are module-level (they are: all helpers in base_dao.py)

**V3 will NOT execute safely if:**
- Instance methods replace module-level helpers (would break tests)
- Each DAO opens separate connection (would break atomicity)
- CHUNK_5a skipped (success criterion fails)
- Cards path missed (account detail fails)

---

## Conclusion

V2 looked revised but wasn't — just cosmetic scope additions. V3 is a TRUE revision: architectural decisions clarified, connection semantics explicit, execution checklist complete.

**This is the value of cross-model review:** Same problem, different model families, different blindspots. Together = comprehensive coverage. Alone = gaps.

---

**Next:** Execute V3 (CHUNK_0 start after pre-execute checklist)
