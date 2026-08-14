# Handoff: DAO Refactor Part 2 (Fresh Builder)

**Current State:** CHUNK_0 committed, waiting for judge review  
**Branch:** feature/quantum-dao-part-2  
**Your Role:** Monitor STEER.md for judge verdict, then execute CHUNK_1-4  

---

## What's Been Done

### Part 1 ✅ Complete
- 8 read-only functions extracted to DAO layer (UserDAO, AccountDAO, TransactionDAO)
- All 98 tests pass on SQLite + PostgreSQL
- Merged to main (commit 695d8d17, linting fixes cherry-picked)

### Part 2 🔄 In Progress

**Plan:** DAO-REFACTOR-PART-2-PLAN-V5.md (realistic, all blockers resolved)

**CHUNK_0 ✅ Executed & Committed:**
- Created `dao/schema_dao.py` (SchemaDAO class)
- Extracted `init_db()`, `create_sample_data()`, `ensure_rewards_ledger_schema()` to SchemaDAO
- Updated `models.py` wrappers to delegate to SchemaDAO
- Commit: 2d115b18
- Tests: 102 expected (same as baseline, no new tests yet)

**CHUNK_1-4 📝 Specs Written (Not Yet Coded):**
- CHUNK_1: HelperDAO (schema validation + state machine)
- CHUNK_2: WriteDAO.create_transaction()
- CHUNK_3: WriteDAO.insert_rewards_points()
- CHUNK_4: WriteDAO.transfer() + 4 new edge-case tests (102 → 106)

---

## The Loop: Your Job

### Monitor STEER.md (Source of Truth)

**File location:** `/Users/m3racbookpro/Work/QuantumBank/STEER.md` (local, NOT pushed)

**Current state in STEER.md:**
```
CHUNK_0: Awaiting Judge Verdict
Judge: [PENDING - Judge to fill in]
```

### What to Watch For

1. **Judge fills in verdict:** ACCEPT / BLOCKER / ACCEPT-WITH-NITS
2. **If ACCEPT:** Execute CHUNK_1-4 (specs are ready in V5 plan)
3. **If BLOCKER:** Wait for executor (previous Claude) to fix, then re-review
4. **If ACCEPT-WITH-NITS:** Proceed but note issues for CHUNK_4 cleanup

### Your Workflow (Once Judge Says ACCEPT)

1. **Read specs:** DAO-REFACTOR-PART-2-PLAN-V5.md (CHUNK_1-4 sections)
2. **Code CHUNK_1:** HelperDAO
   - Commit + test locally
   - Update STEER.md (CHUNK_1: commit hash, "Awaiting Judge")
   - Push
3. **Wait for judge verdict on CHUNK_1**
4. **If ACCEPT:** Repeat for CHUNK_2, CHUNK_3, CHUNK_4
5. **Final:** CHUNK_4 adds 4 new tests (expect 106 pass)

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `DAO-REFACTOR-PART-2-PLAN-V5.md` | Complete spec for all 5 chunks |
| `JUDGE-COMMS-PLAN.md` | Explains async ping-pong loop |
| `REVIEWER-PROMPT.md` | Checklist for judge (per-chunk) |
| `STEER.md` | **WATCH THIS** - Judge updates here with verdict |

---

## Test Baseline

**Commit 695d8d17 (main):** 102 tests  
**After CHUNK_0:** 102 tests (no new tests)  
**After CHUNK_1-3:** 102 tests (no new tests)  
**After CHUNK_4:** 106 tests (102 + 4 new edge cases)

---

## Connection Ownership Pattern (Important)

**Part 2 uses:**
- **Models wrappers:** Open connection, own lifecycle (commit/rollback/close)
- **DAO methods:** Receive connection, agnostic (never commit/close/open own)

**Example:**
```python
# models.py wrapper (owns connection)
def transfer_money(...):
    conn = get_db()
    try:
        dao = WriteDAO()
        success, msg = dao.transfer_internal(conn, ...)
        conn.commit()
        return success, msg
    except:
        conn.rollback()
    finally:
        conn.close()

# DAO method (doesn't own)
class WriteDAO(BaseDAO):
    def transfer_internal(self, conn, ...):
        cursor = conn.cursor()
        # Do work, don't commit/close
        return success, msg
```

---

## Checklist: Ready to Execute?

Before you start CHUNK_1, verify:

- [ ] STEER.md shows "CHUNK_0: ACCEPT"
- [ ] Branch is feature/quantum-dao-part-2
- [ ] Baseline tests (102) still pass
- [ ] V5 plan is your spec (don't deviate)
- [ ] Connection ownership pattern clear
- [ ] No new tests until CHUNK_4

---

## Current Commits

| Hash | Message |
|------|---------|
| 8b5da8ab | Part 2 plan V5 (final, ready for execution) |
| 2d115b18 | CHUNK_0: Schema DAO layer (waiting for judge) |
| 9ea2f3f0 | Add reviewer prompt for CHUNK_0 |
| 25eac64b | Add judge communications plan |

---

## You're Up When...

**STEER.md shows:** `CHUNK_0: ✅ ACCEPT`

Then:
1. Read CHUNK_1 spec in V5 plan
2. Code `dao/helper_dao.py`
3. Update `models.py` wrappers
4. Commit + test (expect 102 pass)
5. Update STEER.md
6. Wait for judge
7. Repeat for CHUNK_2-4

---

**Status:** 🛌 Previous builder sleeping. You're monitoring STEER.md.  
**Timeline:** Async (judge updates when ready, you execute immediately after ACCEPT)  
**Goal:** CHUNK_0 → CHUNK_1 → CHUNK_2 → CHUNK_3 → CHUNK_4 (102 → 106 tests)
