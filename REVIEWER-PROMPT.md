# Judge Prompt: DAO Refactor Part 2, CHUNK_0

**Context:** Continuing DAO extraction from Part 1 (read-only, completed) to Part 2 (write operations + schema).

**Plan:** DAO-REFACTOR-PART-2-PLAN-V5.md (commit 8b5da8ab, feature/quantum-dao-part-2)

**Execution:** CHUNK_0 committed (commit 2d115b18)

---

## What CHUNK_0 Did

Extracted schema initialization + seeding to SchemaDAO:

1. **Created `dao/schema_dao.py`:**
   - `SchemaDAO.init()` (replaces models.init_db)
   - `SchemaDAO.seed(conn)` (replaces models.create_sample_data)
   - `SchemaDAO.ensure_rewards_ledger_schema(conn, cursor, commit)` (replaces function in models)

2. **Updated models.py wrappers:**
   - `init_db()` now calls `SchemaDAO().init()`
   - `create_sample_data(conn)` now calls `SchemaDAO().seed(conn)`
   - Both maintain same signatures (backward compat)

3. **Connection ownership:**
   - Models wrappers open/close connections (own lifecycle)
   - SchemaDAO methods receive connection from wrapper (agnostic)

4. **Behavior preservation:**
   - Code moved identically (no logic changes)
   - Idempotence preserved (CREATE TABLE IF NOT EXISTS)
   - State machine preserved (_rewards_schema_state updated in models.py)

---

## Review Checklist

### Functional
- [ ] Verify CHUNK_0 commit hash: 2d115b18
- [ ] Run tests: `python -m pytest test/ -q` → expect 102 passed
- [ ] Check no behavior changes (tests all pass same as before)

### Code Quality
- [ ] SchemaDAO uses caller's connection (doesn't open own)
- [ ] Models wrappers own connection lifecycle
- [ ] No circular imports (DAO imports models; models wrapper imports DAO)
- [ ] Code is identical to original (pure move, no refactoring)

### Architecture
- [ ] BaseDAO pattern extended correctly (SchemaDAO inherits BaseDAO)
- [ ] Monkeypatch binding preserved (models wrappers are injectable seams)
- [ ] Part 1 tests still pass (98 tests, no regressions)

---

## Next Step (If CHUNK_0 Passes)

**If all tests pass → Judge: ACCEPT**
- Executor proceeds to CHUNK_1 (HelperDAO: schema validation + state machine)
- Continue same flow

**If tests fail → Judge: BLOCKER**
- Specify which test failed + error message
- Executor fixes in place or defers to CHUNK_4

---

## Executor Status

**Session:** 06948b04-2d19-4aef-8ccc-325f348ca99d  
**Branch:** feature/quantum-dao-part-2  
**Baseline:** 695d8d17 (main, 102 tests)  
**Current:** 2d115b18 (CHUNK_0 committed)

**Waiting for:** Judge review + test results

---

**Plan:** Reality-based, all 5 blockers resolved (V5)  
**Timeline:** CHUNK_0 → CHUNK_1 → CHUNK_2 → CHUNK_3 → CHUNK_4 (102 → 106 tests)
