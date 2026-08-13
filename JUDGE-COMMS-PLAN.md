# Judge Communications Plan: DAO Refactor Part 2

**Executor:** Claude (async, commits + sleeps)  
**Judge:** Grok + Gemini (cross-family review, ping-pong loop)  
**Coordinator:** STEER.md (source of truth for state)  
**Branch:** feature/quantum-dao-part-2

---

## The Loop (Work → Review → Work → Review...)

### Executor Flow (This Turn & Beyond)

1. **Execute chunk:** Code + test locally
2. **Commit:** Push to remote with clear message
3. **Signal judge:** Update STEER.md with:
   - Commit hash
   - What was done
   - Test results (pass/fail count)
   - "Waiting for review" status
4. **Sleep/Wait:** Go idle (background check every 5–10 min)
5. **Wake & check:** Read STEER.md for judge verdict
6. **Act:** ACCEPT → next chunk, BLOCKER → fix or defer

### Judge Flow (You, Cross-Family)

1. **Wake & read:** STEER.md shows what executor did
2. **Run checks:** 
   - `git show <commit>` (inspect code)
   - `python -m pytest test/ -q` (verify tests)
   - Review against plan + checklist
3. **Verdict:** Update STEER.md with:
   - ✅ ACCEPT (proceed to next chunk)
   - ❌ BLOCKER (specify fix needed)
   - ⚠️ ACCEPT-WITH-NITS (proceed but note for later)
4. **Signal executor:** Commit verdict to STEER.md + push
5. **Sleep/Wait:** Go idle
6. **Executor wakes, sees verdict, continues**

---

## STEER.md Format (Single Source of Truth)

```markdown
# DAO Refactor Part 2: Execution Loop

**Current Status:** CHUNK_0 (Waiting for judge)

## CHUNK_0: SchemaDAO

**Executor:** 
- Commit: 2d115b18
- What: Extracted init_db, create_sample_data, ensure_rewards_ledger_schema to SchemaDAO
- Tests: 102 passed locally
- Status: Ready for review

**Judge Verdict:** [PENDING / ACCEPT / BLOCKER / ACCEPT-WITH-NITS]
- Comment: [Your feedback here]
- Timestamp: [Date/time]

---

## Next Chunk (If CHUNK_0 Accepted)

**CHUNK_1: HelperDAO**
- Scope: Extract _rewards_ledger_table_exists(), _resolve_rewards_schema_state()
- Expected: 102 tests still pass
- Status: [PENDING / EXECUTING / WAITING]
```

---

## Communication Windows (No Synchronous Waiting)

**Executor works → Commits + sleeps**
- You can review whenever (next 5 min, next hour, next 12 hours—doesn't matter)
- Executor checks STEER.md every 5–10 min (background) + can be woken by you
- No "waiting" blocks

**Judge reviews → Updates STEER.md → Executor wakes**
- Your verdict is the signal
- Executor reads STEER.md, sees verdict, acts immediately
- Loop continues independently of any sync point

---

## Key Commits to Watch

| Chunk | Commit | File(s) | Tests Expected |
|-------|--------|---------|-----------------|
| CHUNK_0 | 2d115b18 | dao/schema_dao.py, models.py | 102 pass |
| CHUNK_1 | (pending) | dao/helper_dao.py, models.py | 102 pass |
| CHUNK_2 | (pending) | dao/write_dao.py, models.py | 102 pass |
| CHUNK_3 | (pending) | dao/write_dao.py, models.py | 102 pass |
| CHUNK_4 | (pending) | dao/write_dao.py, test/*.py, models.py | 106 pass (102 + 4 new) |

---

## Your Role (Judge)

**For each chunk:**

1. **Read the commit:** `git show <hash>` (see exact code)
2. **Verify checklist** (in REVIEWER-PROMPT.md or at top of each commit):
   - No circular imports? ✅
   - Tests pass? ✅
   - Behavior preserved (moved, not refactored)? ✅
   - Connection ownership clear? ✅
3. **Run local test:** `python -m pytest test/ -q` → verify count matches
4. **Verdict:** Update STEER.md with ACCEPT / BLOCKER / ACCEPT-WITH-NITS
5. **Push:** `git add STEER.md && git commit && git push`

**That's it.** No async coordination needed beyond STEER.md.

---

## Blocker Handling

**If tests fail:**
- Update STEER.md: "BLOCKER: test_X failed, error: Y"
- Executor reads, fixes in place (same chunk), re-commits
- Judge re-reviews (same loop)

**If code review finds issue:**
- Update STEER.md: "BLOCKER: circular import in DAO / connection ownership unclear"
- Executor fixes, re-commits
- Judge re-reviews

**No deadlock:** Loop continues until ACCEPT.

---

## Success Criteria (Final)

- [ ] CHUNK_0 → CHUNK_1 → CHUNK_2 → CHUNK_3 → CHUNK_4 all ACCEPT
- [ ] 102 tests pass through CHUNK_3
- [ ] 106 tests pass after CHUNK_4 (102 + 4 new)
- [ ] Both SQLite + PostgreSQL verified
- [ ] Monkeypatch binding preserved (test_demo_rollout.py still passes)

---

## Where to Read / Write

- **Code:** `/Users/m3racbookpro/Work/QuantumBank/` (local clone)
- **Status:** STEER.md (in repo, tracks state)
- **Detailed plan:** DAO-REFACTOR-PART-2-PLAN-V5.md (in repo)
- **Review checklist:** REVIEWER-PROMPT.md (in repo, per chunk)

---

## You're Up

**Current state:**
- CHUNK_0 committed (2d115b18)
- REVIEWER-PROMPT.md ready
- Tests running locally
- STEER.md waiting for your verdict

**Next:** Read REVIEWER-PROMPT.md, run tests locally, update STEER.md with verdict.

Executor will wake every 5–10 min, check STEER.md, and proceed or fix.

---

**Plan:** V5 (reality-based, all blockers resolved)  
**Chunks:** 5 (CHUNK_0 → CHUNK_4)  
**Timeline:** Async (you review when ready, executor continues immediately after verdict)  
**Goal:** 102 → 106 tests, all DAO write ops extracted, merged to main
