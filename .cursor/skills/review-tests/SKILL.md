---
name: review-tests
description: |
  Black-box, behavior-driven tests for this repo (Flask + pytest). Use when writing
  or reviewing tests under test/, adding routes, or doing TDD on HTTP behavior.
---

# Review tests (QuantumBank)

Tests describe **what the system does**, not how it does it. Prefer the Flask test client and stable, user-visible outcomes (status, redirect `Location`, JSON shape, small substrings). Avoid full HTML snapshots and implementation imports.

## Project conventions

- **Layout:** `test/test_*.py` only; shared **`client`** fixture in `test/conftest.py` (`app.test_client()`, lazy `from app import app`). **`pytest.ini`** sets `testpaths`, **`pythonpath = .`**, and markers **`public`**, **`banking`**, **`api`**.
- **Markers:** `public` (no session), `banking` (login and HTML banking pages), `api` (JSON under `/api/`). Use the right marker on new tests.
- **Split.io:** CI often has no `SPLIT_API_KEY`. Do not assert copy that exists only on one home/pricing variant unless you gate the env; prefer broad markers (see `test_home_root_200_has_known_shell`) or JSON keys.
- **SQLite sample data:** `demo` user has checking / savings / credit. Transfers in tests use small amounts; avoid asserting exact balances unless you reset state.

## Core principles (short)

1. **Behavior-shaped names** — e.g. “transfer to same account shows error”, not `test_transfer_1`.
2. **Public surface only** — assert routes, status codes, redirects, JSON, and short substrings; do not import private helpers to assert behavior.
3. **AAA** — minimal arrange (often `client.post("/login", ...)`), one primary act, clear asserts.
4. **Determinism** — no real network, sleeps, or wall-clock assertions; use substring markers stable in this codebase.

## Review checklist

- [ ] Name states the behavior; file uses correct pytest marker.
- [ ] One primary action per test (unless the behavior is explicitly a short flow).
- [ ] Assertions would fail on a real regression; not tautological.
- [ ] No coupling to private functions or fragile HTML dumps.
- [ ] New banking/API tests work without Split and without extra secrets.

## Red flags

| Problem | Example |
|--------|---------|
| Huge HTML golden files | Entire `response.data` compared to fixture |
| Variant-only copy | Single word that appears only on one Split treatment |
| Importing `models` in route tests | Bypasses HTTP contract (unless testing pure unit elsewhere) |
| `to_account` == `from_account` in success test | Corrupts intent; use distinct accounts |

## Rationale

HTTP-level tests here are **living specs** for regressions and CI. Keep them readable to someone who has not read the handler source; if the test needs a comment longer than the assert, simplify the assert or split the case.

When in doubt, match the style of `test_public_routes.py`, `test_banking_routes.py`, and `test_api_routes.py`.
