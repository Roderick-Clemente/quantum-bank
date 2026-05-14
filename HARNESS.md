# Quantum Bank — Harness CI & DevOps notes

This doc captures **Harness Continuous Integration** wired to **GitHub** for this repo, plus a **reference execution** you can use in follow-up work (e.g. SCA triage).

---

## Scope (where things live)

| Item | Value |
|------|--------|
| **Harness account** | `EeRjnXTnS4GrLG5VNNJZUw` (in UI URLs) |
| **Organization** | `sandbox` |
| **Project** | `devX_super_team` |
| **Pipeline** | `rod-bank-pipeline` (`identifier: rodbankpipeline`) |
| **GitHub repo** | `Roderick-Clemente/quantum-bank` (public) |
| **Git connector (identifier)** | `quantumplatformdemo` (display name e.g. *Quantum-platform-demo*) |

> **Note:** Older `.harness/*.yaml` CD samples may mention `SE_Sandbox`; the **live** org identifier for this CI work is **`sandbox`**.

---

## What we set up

1. **GitHub fine-grained PAT** — read-only on `quantum-bank` (Contents read), used by a **Harness GitHub connector** (test repo `quantum-bank` / full HTTPS URL as per wizard).

2. **Pipeline codebase** — `connectorRef: quantumplatformdemo`, `repoName: quantum-bank`, `build: <+input>` (pass **`main`** when running).

3. **CI stage “Build”** (order matters in YAML):
   - **`Test_Intelligence`** — `pip install -r requirements.txt` then `pytest test/ -v --junit-xml=out_report.xml`; **JUnit reports** configured so Harness can ingest `out_report.xml`. Test Intelligence remains enabled.
   - **SCA step group** (parallel): **OWASP** + **OSV Scanner** on the repository (orchestration / auto target).

4. **Failure strategy** — stage uses **`MarkAsSuccess`** on failure (intentional for some demos); pipeline can still end **Success** when all steps pass.

5. **Repo reference YAML** — checked in at [`.harness/pipelines/rodbank-pipeline-ci-reference.yaml`](.harness/pipelines/rodbank-pipeline-ci-reference.yaml) as an export of the “known good” CI shape (keep in sync when you change Studio).

---

## Reference execution (green CI + SCA logs)

Use this run when you want another agent to **inspect SCA output** and drive dependency / code fixes.

| Field | Value |
|--------|--------|
| **Plan execution id** | `4_G6mG4gS5WQmsnrqQhQqw` |
| **Run sequence** | `5` |
| **Branch** | `main` |
| **Result** | **Success** (Build **SUCCEEDED**; clone from `https://github.com/Roderick-Clemente/quantum-bank.git`) |

**Open in Harness (deployments / execution):**  
https://app.harness.io/ng/account/EeRjnXTnS4GrLG5VNNJZUw/all/orgs/sandbox/projects/devX_super_team/pipelines/rodbankpipeline/deployments/4_G6mG4gS5WQmsnrqQhQqw/pipeline

**Studio (edit pipeline):**  
https://app.harness.io/ng/account/EeRjnXTnS4GrLG5VNNJZUw/all/orgs/sandbox/projects/devX_super_team/pipelines/rodbankpipeline/pipeline-studio?storeType=INLINE

---

## Operational tips

- **Run from API / MCP:** `harness_execute` with pipeline URL + `inputs: { branch: "main" }`.
- **Poll status:** `harness_get` on the execution URL; avoid long blocking sleeps in chat—**60s** cadence is enough for this pipeline size.
- **Drift:** If Studio YAML diverges from [`.harness/pipelines/rodbank-pipeline-ci-reference.yaml`](.harness/pipelines/rodbank-pipeline-ci-reference.yaml), refresh the file or re-import from Harness.

---

## Handoff: prompt for a **new chat** (SCA vuln remediation)

Copy everything inside the block below into a **new Cursor chat** (or task) after you have Harness access / MCP if the bot should call Harness APIs.

```text
You are working in the local repo: /Users/m3racbookpro/Work/QuantumBank (GitHub: Roderick-Clemente/quantum-bank, Flask app).

Context: We have Harness CI on pipeline `rod-bank-pipeline` in org `sandbox`, project `devX_super_team`. A successful run that executed pytest + OWASP + OSV is:

- Plan execution id: 4_G6mG4gS5WQmsnrqQhQqw
- Harness UI: https://app.harness.io/ng/account/EeRjnXTnS4GrLG5VNNJZUw/all/orgs/sandbox/projects/devX_super_team/pipelines/rodbankpipeline/deployments/4_G6mG4gS5WQmsnrqQhQqw/pipeline

Goals:
1. Use Harness MCP (user-harness-work) to pull logs / diagnostics for that execution: OWASP and OsvScanner steps, and any STO/SCS outputs. Use harness_diagnose(execution_id=4_G6mG4gS5WQmsnrqQhQqw, include_logs: true) and harness_get execution with the deployment URL above as needed.
2. Summarize findings: CVEs, vulnerable packages, file locations, severity.
3. In THIS repo, implement minimal fixes: upgrade pins in requirements.txt where safe, patch code only if required, re-run pytest locally (`pytest test/ -v`).
4. Do not commit secrets. If Harness needs no code change, document “no action” with rationale.

Constraints: small diffs, match existing style, run tests before finishing. If MCP cannot read SCA detail, tell me exactly what to export from the Harness UI (screenshot or copy-paste) and continue from that.
```

---

## Related files

| Path | Role |
|------|------|
| [`.harness/pipelines/rodbank-pipeline-ci-reference.yaml`](.harness/pipelines/rodbank-pipeline-ci-reference.yaml) | Inline pipeline YAML snapshot |
| [`.harness/kubernetes/`](.harness/kubernetes/) | Separate CD/K8s lab artifacts (not the same as this CI-only flow) |
| [`README.md`](README.md) | Project entry + links |
| [`demo-fun.md`](demo-fun.md) | Product / demo narrative |
| [`RENDER_DEPLOYMENT.md`](RENDER_DEPLOYMENT.md) | Render.com deploy |

---

## Pytest layout and markers

Tests live under `test/` as `test_*.py` only (see `pytest.ini`: `testpaths = test`). Shared HTTP fixtures are in `test/conftest.py` (`client` uses `app.test_client()`). Markers: **`public`** (unauthenticated pages and static routes), **`banking`** (login and session-backed pages), **`api`** (JSON under `/api/`). Examples: `pytest test/ -v`, `pytest test/ -m public`, `pytest test/ -m banking`, `pytest test/ -m api`.
