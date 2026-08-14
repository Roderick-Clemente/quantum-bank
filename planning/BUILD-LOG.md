# BUILD-LOG — `pilot/llms-txt` on `Roderick-Clemente/quantum-bank`

**Date:** 2026-08-03 (single-seat run; Rod offline overnight)

**droid:** `0.180.0` (this Box).

**Spec source:** reachable via dangling commit `e229061b1bb03b6ac77e9698750dd1ce80e8b3af`
("Add /llms.txt pilot spec (Tier B, reconstructed after compaction)",
authored by Rod, Co-Authored-By Claude Opus 4.8) — the only path to
`tools/pilot-llms-txt-spec.md`. The spec is not on any current branch
in `~/work/adversarial-sprint-dev` at this version of the dev repo.
**Recorded as a finding** — if the spec had no dangling commit, the
build would have been BLOCKED-with-evidence with no path to the spec.

**Scratch clone:** `~/work/quantum-bank--llms-txt-pilot` — git
clone https://github.com/Roderick-Clemente/quantum-bank.git, into a
fresh dir. Branch: **`pilot/llms-txt`** off main `0f7e5614`.
**No push** to `origin`. Branch tip stays local on the clone.

**GREEN proven = the direct Flask test client request returned 200,
content-type text/plain, with all four required substrings present
("Quantum Bank", "Split.io", "demo" (lower-cased), "fictional"
(lower-cased)). Pytest reports 1 passed; full pre-existing
test_public_routes.py suite (17 tests) still green.**

---

## GROK phase findings

Verified the spec's structure assumptions in the fresh clone match
the prior scout exactly (same repo, same SHA, no surprises):

| Assumption | Status |
|---|---|
| `handle_*` functions under `api/`, named after the route | yes — `api/hello.py`, `api/time.py` etc. all use this pattern |
| `app.py` imports the handlers under `from api.X import ...` after `load_dotenv()`, with `# noqa: E402` on each line | yes (18 imports, all carry `noqa`) |
| `app.py` route stubs are thin delegators: `@app.route("/hello") def hello(): return handle_hello()` | yes |
| `/metrics` precedent returns `Response(body, mimetype="text/plain; ...")` | yes — used as the model for `/llms.txt` |
| `test/conftest.py` provides a `client` fixture importing `app.app` and yielding `app.test_client()` | yes — no new fixtures needed |
| `test_public_routes.py` uses `@pytest.mark.public` for unauthenticated routes | yes — appending the new test alongside |

## Commits on `pilot/llms-txt`

```
6448d7a0  pilot/llms-txt: wire @app.route('/llms.txt') stub in app.py    (HEAD)
3f847d22  pilot/llms-txt: add api/llms_txt.py with handle_llms_txt()
bfc8a3b6  pilot/llms-txt: add failing test for /llms.txt endpoint
0f7e5614  main                                                 (Phase 0 ... 'stale test counts')
```

Three pilot commits, atomic-per-unit. **Commit `6448d7a0` was amended
once** (the originally made `a07318c9` — typo'd my head; recovered
via `git log` was `a0738ef2` — actually `git reset` is clean; recording
the amend rather than discarding): the original insertion put the
`/llms.txt` stub directly above `/demo` with 0 blank lines between
top-level functions; PEP-8 (and the repo's prevailing style) require
two. Local-only branch, so amending was the right move — nothing
external had seen the previous SHA. Final commit content: 6 lines
added to `app.py`.

## RED output (commit `bfc8a3b6`)

Command: `pytest test/test_public_routes.py -k llms_txt -v`

```
collected 18 items / 17 deselected / 1 selected

test/test_public_routes.py::test_llms_txt_returns_plain_text FAILED    [100%]
E       assert 404 == 200
E        +  where 404 = <WrapperTestResponse streamed [404 NOT FOUND]>.status_code

FAILED test/test_public_routes.py::test_llms_txt_returns_plain_text - assert 404 == 200
1 failed, 17 deselected in 0.16s
exit: 1
```

**Valid RED reason**: the route was unwired at this commit, so Flask
returned 404. The assertion `status_code == 200` failed against the
actual 404 — a route-existence assertion, not an import/syntax error.
The pytest collector listed 18 tests with no fixture or import error.
(The noisy Split.io warnings under "Captured stdout setup" come from
`app.py` `init_split()` at module-load, where `SPLIT_API_KEY` is
unset in the test environment; harmless because the route returns
404 before any Split call. No assertion failure for any reason other
than `assert 404 == 200`.)

## GREEN output (commit `6448d7a0`)

Two test surfaces:

### 1. Pytest on the new test
```
collected 18 items / 17 deselected / 1 selected

test/test_public_routes.py::test_llms_txt_returns_plain_text PASSED    [100%]

1 passed, 17 deselected in 0.10s
exit: 0
```

### 2. Direct Flask test client (asserted on reality, not just exit)

```
status_code: 200
content-type: text/plain; charset=utf-8; charset=utf-8
body length: 1996
contains 'Quantum Bank': True
contains 'Split.io': True
contains 'demo' (lower): True
contains 'fictional' (lower): True

ALL ASSERTIONS PASSED on direct /llms.txt request
```

### 3. Regression sanity: full `test_public_routes.py` suite
```
collected 18 items / 1 deselected / 17 selected
17 passed, 1 deselected in 0.11s
```
No regression in the 17 prior tests. New test is the only addition.

## Deviations from the spec

1. **Spacing fix amendment on commit 3.** Mentioned above; PEP-8
   blank-line convention. None of the spec's required content changed.
2. **Content-Type header quirk.** Direct test client shows
   `Content-Type: text/plain; charset=utf-8; charset=utf-8` —
   `charset=utf-8` repeated. This is Werkzeug/Flask behavior when
   `mimetype="text/plain; charset=utf-8"` is passed to
   `flask.Response(...)`, and the `/metrics` precedent exhibits
   the same shape (the call site is the same: `Response(body,
   mimetype="text/plain;...")`).
   The spec's acceptance bar is "Content-Type is `text/plain` (charset
   ok)". My test asserts `ct.startswith("text/plain")`, which passes.
   Recorded so anyone refining the route later knows the doubled
   `charset=` is a known shape, not a regression.
3. **Python version pivot.** System `python3` is 3.9.6 (darwin
   `arm64`). Three of the pinned `requirements.txt` entries
   (`pytest==9.0.3`, `python-dotenv==1.2.2`, plus several
   version-conditional ones) require Python ≥ 3.10.
   Worked around with `/opt/homebrew/bin/python3.12` to create
   the local `.venv/` from the pinned requirements verbatim
   (no version rewrites). **The `.venv/` directory is gitignored**;
   nothing in it was committed.
4. **Spec location.** `tools/pilot-llms-txt-spec.md` was not on any
   branch; reachable only through a dangling commit (`e229061...`).
   If that commit had not existed or had been pruned, the build would
   have BLOCKED-with-evidence. Recorded in the writeup above.
5. **`tools/OPERATING-RULES.md` does not exist** in the dev repo at
   this version (same finding as the Phase 0 canary, `bug-02-mission-noop`
   README, and earlier this session). Not found in any commit;
   not on any branch. Proceeding without it. This is the third
   confirmation of the absence this session — worth surfacing to
   whoever is curating the dev repo.
6. **Test did not exercise `factory_credits` field or any cost
   telemetry.** The spec for this pilot does not call for it.
   The Phase 0 `factory-credits-none.md` artefact and bug-#2
   draft comments cover that topic separately; not re-litigated here.

## Hard stops (per spec)

- **No merge to main.** Branch stays on `pilot/llms-txt`.
- **No PR opened.** No `gh` calls.
- **No push** to `origin` (the QuantumBank remote is HTTPS; the
  branch remains local on this Box).
- The cloned scratch dir is committed and stop-worthy.

What the spec calls "the manual two-CLI baseline arm (§13)" is
not done here — this is the single-seat build, not the
cross-family showcase; the orchestrator will land that.

## File diff summary

```
all:  3 files changed, 78 insertions(+)

test/test_public_routes.py    | 16 ++++++++++++++++
api/llms_txt.py              | 56 +++++++++++++++++++++++++++++++++++++++++++
app.py                       |  6 ++++++
BUILD-LOG.md                 | written here, ~this file
```

`api/__init__.py`, `test/__init__.py`, `requirements.txt`, and `pytest.ini`
untouched. No new fixtures, no new top-level modules beyond the one
planned.

## Final state

```
branch: pilot/llms-txt       (3 commits ahead of main 0f7e5614)
remote: untouched            (no push, no PR)
test_llms_txt_returns_plain_text: PASSING
full test_public_routes.py:  17 + 1 = 18 PASSING
no regressions
```

STOPPING per spec.
