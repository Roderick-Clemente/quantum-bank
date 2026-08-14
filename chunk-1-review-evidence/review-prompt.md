# CHUNK_1 Judge Review: HelperDAO

You are a read-only independent reviewer for QuantumBank.

Repository: /Users/m3racbookpro/Work/QuantumBank
Plan: DAO-REFACTOR-PART-2-PLAN-V5.md
Candidate commit: fbe5c324
Prior CHUNK_1 commit: 5edc0f0a

Review the committed CHUNK_1 extraction against the current repository and
plan. Inspect the candidate diff, models.py callers, BaseDAO/import
boundaries, SQLite and PostgreSQL cursor behavior, and the test suite. Do not
modify files, commit, push, or create files.

Required checks:
1. `rewards_ledger_table_exists()` preserves SQLite and PostgreSQL behavior.
2. PostgreSQL RealDictCursor rows are accessed safely.
3. The models wrapper preserves the state-machine and monkeypatch seam.
4. No circular import or import-time failure exists.
5. The current evidence of 102 passing tests, Ruff passing, and compilation
   passing is consistent with the code.
6. No unrelated production behavior changed.

Report only high-confidence findings. For each finding include severity,
path/line, concrete trigger, and required correction. If no blockers exist,
say so explicitly.

End with exactly one of:
VERDICT: ACCEPT
VERDICT: REJECT
