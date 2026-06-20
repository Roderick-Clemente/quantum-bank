# Rewards Rollout Demo Script

This script is for a live walkthrough of progressive delivery for the rewards ledger rollout.
It is optimized for one presenter terminal + one browser window.

## Audience Goal

Show that we can:
- roll out schema and feature in safe order,
- survive a forced migration failure without breaking transfers,
- recover without losing previously earned points.

## Prerequisites

- Run from repo root.
- Use SQLite for the recording (no Postgres setup required).
- Start from a clean local DB file so the flow is predictable.

## Terminal 1: app + logs

```bash
rm -f quantum_bank.db app.log

export SECRET_KEY="quantum-bank-demo-key-not-for-prod"
export DEMO_ROLLOUT_SCHEMA=off
export DEMO_ROLLOUT_FEATURE=off
export DEMO_FORCE_ROLLOUT_MIGRATION_FAIL=off

venv/bin/python app.py 2>&1 | tee app.log
```

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

### 1) Baseline (all rollout flags off)

Flags already set:

```bash
export DEMO_ROLLOUT_SCHEMA=off
export DEMO_ROLLOUT_FEATURE=off
export DEMO_FORCE_ROLLOUT_MIGRATION_FAIL=off
```

In browser:
- make a transfer (for example checking -> savings, amount `10.00`).

Audience-visible signals:
- transfer succeeds,
- no rewards points card,
- no rewards banner.

### 2) Feature on before schema (safe fallback)

Restart app with:

```bash
export DEMO_ROLLOUT_SCHEMA=off
export DEMO_ROLLOUT_FEATURE=on
export DEMO_FORCE_ROLLOUT_MIGRATION_FAIL=off
venv/bin/python app.py 2>&1 | tee app.log
```

In browser:
- log in as `demo` if needed,
- make another transfer,
- open dashboard.

Audience-visible signals:
- banner rendered with `data-testid="rewards-banner"` and `data-kind="legacy_no_schema"`,
- transfer still succeeds,
- log includes: `rewards.rollout.schema state=skipped`.

### 3) Schema lands (correct order)

Restart app with:

```bash
export DEMO_ROLLOUT_SCHEMA=on
export DEMO_ROLLOUT_FEATURE=on
export DEMO_FORCE_ROLLOUT_MIGRATION_FAIL=off
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

Restart app with:

```bash
export DEMO_ROLLOUT_SCHEMA=on
export DEMO_ROLLOUT_FEATURE=on
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

Restart app with:

```bash
export DEMO_ROLLOUT_SCHEMA=on
export DEMO_ROLLOUT_FEATURE=on
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

