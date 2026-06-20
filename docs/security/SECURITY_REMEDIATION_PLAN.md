# Security Remediation Plan (Sprint 1)

## Scope

This stream tracks pre-existing security issues on `main` and in Harness STO findings.
It is separate from the rewards rollout delivery branch.

## Scanner Snapshot

- Source: Harness STO issues list (`security_issue`) in `sandbox/devX_super_team`
- Pipeline context: `rodbankpipeline` (latest successful execution currently `f1K2zBEXQcGV-fJbbH8lkA`)
- SAST tool family observed: Semgrep-based findings (titles prefixed `Semgrep Finding`)
- Snapshot date: 2026-06-19 (local triage run)
- Snapshot totals observed:
  - 15 issues when filtered to `pipeline_ids=rodbankpipeline`
  - 23 issues in project-wide list (includes SCA findings)

## P0 Candidate (Manual + Cross-check)

### Missing ownership check / IDOR in transfer path

- **Status:** Open (manual finding; not yet remediated)
- **Severity:** High (P0 candidate)
- **Category:** Broken object-level authorization / IDOR
- **Location:** `models.py` `transfer_money(...)` (~line 677-776), invoked by transfer handlers
- **Risk:** A logged-in user may be able to debit another user's account by supplying a different `from_account` id.
- **Why this matters:** Unauthorized fund movement is an integrity breach, not just data exposure.

#### Scanner cross-check result

- **Already flagged in latest STO list?** **No direct match found** in the current SAST titles.
- The latest SAST set includes findings like debug-enabled, NaN-injection, raw-query, path traversal, and container/k8s hardening rules, but no explicit IDOR/BOLA ownership-control finding title.
- Therefore this remains a **manual high-priority gap** to track explicitly.

#### Planned remediation (separate themed PR; not in this planning commit)

1. Enforce account ownership: `from_account.user_id == session["user_id"]` before debit path.
2. Return HTTP 403 on ownership mismatch.
3. Add black-box route test for cross-user transfer attempt rejection.
4. Re-run full suite + STO scan and record closure evidence.

## Sprint 1 Execution Order

1. **Auth/session guardrails first** (includes the IDOR fix above).
2. High-severity SAST issues with high confidence (Semgrep Highs).
3. Medium-severity issues triaged into:
   - immediate fix,
   - accepted risk with rationale,
   - false-positive with evidence.

## Exit Criteria (Sprint 1)

- IDOR ownership-control issue fixed and covered by regression test.
- All High severity findings dispositioned (fixed or documented risk acceptance).
- Security triage ledger updated with finding IDs, decisions, and evidence links.
