# Rewards Rollout Demo Script

This script is for a live walkthrough of progressive delivery for the rewards ledger rollout.
It is optimized for one presenter terminal + one browser window.

## Audience Goal

Show that we can:
- roll out schema and feature in safe order,
- survive a forced migration failure without breaking transfers,
- recover without losing previously earned points.

## What this demonstrates

A safe, reversible **progressive delivery** rollout of a rewards-points feature on a live banking app, exercising five production-grade patterns:

- **Schema-before-feature ordering** — `rewards_rollout_schema` / `rewards_rollout_feature` in Harness FME (env: `DEMO_ROLLOUT_SCHEMA` / `DEMO_ROLLOUT_FEATURE`) are independent, so the feature can be dark-launched and turned on only after the table exists.
- **Feature flags as a kill switch** — `DEMO_FORCE_ROLLOUT_MIGRATION_FAIL` simulates a failed migration and instantly rolls the UI back to a safe banner with zero redeploy.
- **Contract testing** — the UI and the test suite agree on stable tokens (`data-testid="rewards-points"`, `data-kind="..."`); a deliberate rename of one token turned CI **red** (proof below), so the contract can't silently drift.
- **Graceful degradation** — a rewards write that fails at the DB layer is contained by a transaction savepoint ([models.py:748-761](../../models.py#L748-L761)); the core money transfer still commits. The transfer never loses money because of a rewards bug.
- **CI gating** — both backends (SQLite + Postgres) run the full rollout contract on every push; the gate was empirically drilled red, not assumed.

## Prerequisites

- Run from repo root.
- Use SQLite for the recording (no Postgres setup required).
- Start from a clean local DB file so the flow is predictable.
- **Harness FME (primary):** `SPLIT_API_KEY` in `.env` (Quantum-Dev server key) and client key in `static/js/split-client.js`. Flags `rewards_rollout_schema` and `rewards_rollout_feature` should exist in the workspace with default treatment `off` in Dev.
- **Env vars (fallback):** `DEMO_ROLLOUT_SCHEMA`, `DEMO_ROLLOUT_FEATURE`, and `DEMO_FORCE_ROLLOUT_MIGRATION_FAIL` still work when Split is unavailable (`control`, SDK error, or no key). CI and local pytest use env only.

### Flag resolution (server)

For schema and feature, `db_flags.py` resolves: **Split treatment → env var → default(`off`)**. An explicit FME `off` wins over a shell `export ...=on` when the SDK is live.

Rollout flags evaluate as user `__system__` (global rollout for the demo, not per logged-in user).

**Restart rule:** `rewards_rollout_schema` is applied in `init_db()` at app startup. After turning schema **on** in Harness, **restart the app** so `rewards_ledger` is created. The feature flag is re-read on each request, but schema migration does not re-run until restart.

`DEMO_FORCE_ROLLOUT_MIGRATION_FAIL` stays **env-only** (presenter kill-switch; no FME flag).

## Terminal 1: app + logs

```bash
rm -f quantum_bank.db app.log

export SECRET_KEY="quantum-bank-demo-key-not-for-prod"
# Optional fallback if Split is not configured:
export DEMO_ROLLOUT_SCHEMA=off
export DEMO_ROLLOUT_FEATURE=off
export DEMO_FORCE_ROLLOUT_MIGRATION_FAIL=off

venv/bin/python app.py 2>&1 | tee app.log
```

For the live recording, drive **schema** and **feature** from the Harness FME UI instead of exports. Keep `DEMO_FORCE_ROLLOUT_MIGRATION_FAIL` as an env toggle for the forced-fail beat.

In a second terminal, keep this running during the whole demo:

```bash
tail -F app.log | grep rewards.rollout
```

Open the app and log in as `demo`:

- <http://localhost:5001/login>

## Walkthrough

Each step below includes:
- what to change,
- what to click,
- what the audience should see.

## Rollout state machine

What the dashboard shows is a pure function of the three flags (resolved in `get_rewards_points_for_user` -> `_resolve_rewards_schema_state`). Note the precedence: **force-fail is checked before schema**.

```mermaid
flowchart TD
    A[Dashboard load] --> B{rewards_rollout_feature on?}
    B -- no --> N["No card, no banner<br/>(baseline / legacy UI)"]
    B -- yes --> C{FORCE_ROLLOUT_MIGRATION_FAIL on?}
    C -- yes --> FF["banner: rollback_forced_fail<br/>rollout failed - points paused,<br/>balances safe"]
    C -- no --> D{ROLLOUT_SCHEMA on<br/>AND rewards_ledger table exists?}
    D -- "no (off / table missing)" --> LG["banner: legacy_no_schema<br/>temporarily unavailable -<br/>legacy mode"]
    D -- "table check raised" --> RE["banner: rollback_runtime_error<br/>lookup hit an error -<br/>points paused"]
    D -- yes --> RDY{SUM(points) read ok?}
    RDY -- yes --> PTS["points card shown<br/>data-testid=rewards-points<br/>(1 pt per $10 transferred)"]
    RDY -- "read raised" --> RE
```

| Phase | FEATURE | SCHEMA | FORCE_FAIL | On screen |
|---|---|---|---|---|
| 1 — Baseline | off | off | off | No rewards card, no banner |
| 2 — Feature before schema | on | off | off | Banner `legacy_no_schema` |
| 3 — Schema ready | on | on | off | Points card (data-testid=`rewards-points`) |
| 4 — Forced-fail rollback | on | on | **on** | Banner `rollback_forced_fail` |
| 5 — Recovery | on | on | off | Points card returns |

> **Presenter note:** points are 1 per $10, floored - use **$10+** transfers, or `try_insert_rewards_points` returns early (no points, no `write_succeeded` log line).

### 1) Baseline (all rollout flags off)

**Harness:** `rewards_rollout_schema` = off, `rewards_rollout_feature` = off.

In browser:
- make a transfer (for example checking -> savings, amount `10.00`).

Audience-visible signals:
- transfer succeeds,
- no rewards points card,
- no rewards banner.

### 2) Feature on before schema (safe fallback)

**Harness:** `rewards_rollout_feature` = on, `rewards_rollout_schema` = off (no restart required — feature is read per request).

In browser:
- log in as `demo` if needed,
- make another transfer,
- open dashboard.

Audience-visible signals:
- banner rendered with `data-testid="rewards-banner"` and `data-kind="legacy_no_schema"`,
- transfer still succeeds,
- log includes: `rewards.rollout.schema state=skipped`.

### 3) Schema lands (correct order)

**Harness:** `rewards_rollout_schema` = on, `rewards_rollout_feature` = on.

**Restart the app** after schema goes on so `init_db()` creates `rewards_ledger`:

```bash
venv/bin/python app.py 2>&1 | tee app.log
```

In browser:
- make a transfer,
- open dashboard.

Audience-visible signals:
- rewards points appear (`data-testid="rewards-points"`),
- no rollback banner,
- log includes: `rewards.rollout.schema state=ready`,
- log includes: `rewards.rollout.write_succeeded points=<n>`.

### 4) Forced migration failure (rollback behavior)

**Harness:** schema and feature stay on. **Terminal:** enable the env-only kill-switch and restart:

```bash
export DEMO_FORCE_ROLLOUT_MIGRATION_FAIL=on
venv/bin/python app.py 2>&1 | tee app.log
```

In browser:
- make a transfer,
- open dashboard.

Audience-visible signals:
- transfer still succeeds,
- banner rendered with `data-kind="rollback_forced_fail"`,
- points card hidden while failure is active,
- log includes: `rewards.rollout.schema state=forced_fail`.

### 5) Recovery after failure clears

**Harness:** unchanged (schema + feature on). **Terminal:** clear the kill-switch and restart:

```bash
export DEMO_FORCE_ROLLOUT_MIGRATION_FAIL=off
venv/bin/python app.py 2>&1 | tee app.log
```

In browser:
- make another transfer,
- open dashboard.

Audience-visible signals:
- rewards points visible again,
- points continue from pre-failure history (no loss),
- log returns to `rewards.rollout.schema state=ready`.

## Log Lines To Narrate

Use this as a presenter checklist while tailing logs:

- `rewards.rollout.schema state=<state>`
- `rewards.rollout.write_succeeded points=<n>`
- `rewards.rollout.write_failed reason=<exc>`
- `rewards.rollout.read_failed reason=<exc>`

## Proof CI gates this rollout

The contract is enforced, not assumed:

- **Baseline (green):** Harness execution `50IVGI23SjyI-S0GLUVyJg` — full suite passes on both lanes.
- **Deliberate break (red):** removing the `data-kind` attribute on a throwaway branch turned CI **red** — Harness execution `QT66s6tZSNmik6m9f-lQGA`, failing under the `Test_SQLite` lane (fail-fast).
- Self-certify locally in one second: `venv/bin/python -m pytest test/test_demo_rollout.py -q`

> **Scope note (honest):** the red drill fired under `Test_SQLite` and the stage fails fast, so the **Postgres lane's** gating was not *independently* drilled red in CI. Postgres-lane money-safety is verified by a local with/without-savepoint balance experiment (balance moves -$10 with the savepoint; silently unchanged without). A real-PG-failure CI drill is the natural next step.

