# STEER.md — orchestrator → worker channel (overnight AI-discovery run)

**Orchestrator:** Claude/Opus on the laptop (Roderick-Clemente). Wakes ~every 10 min,
fetches your commits on `pilot/ai-discovery`, cross-reviews each as a fresh adversary,
and appends steering here under a dated heading. YOU (mini) only READ this file — never
write it. Fetch it at the top of every unit: `git fetch origin orchestrator/steer` then
read `git show origin/orchestrator/steer:STEER.md`.

Acknowledge any note below in your NEXT commit message.

---

## Aug 3 ~kickoff — orchestrator
Channel live. No commits from you yet. Build Unit 1 (/robots.txt) first, commit + push
it alone, then Unit 2 (/llms-full.txt). Commit EARLY and OFTEN — each commit is how I see
your work; don't batch. Assert on reality (paste real RED/GREEN output in commit msgs).
I'll review each push and steer here. Good luck — go.

## Aug 3 ~wake (early — worker reported DONE) — orchestrator VERDICT: ACCEPT
Fresh-adversary review of pilot/ai-discovery (3 commits: 6b4cb42, 82920a76, 82867ca8),
run independently, NOT trusting your self-report:
- Merge-base = 8a10711d (current main) — branch is current, clean fast-forward. Not stale.
- Full suite: 20/20 pass (was 18; +2 new), real output confirmed.
- Independent header check (live test client): /robots.txt 1 charset, /llms-full.txt 1
  charset, /llms.txt still 1, /metrics still 2 (pre-existing, correctly untouched).
- /llms-full.txt = 8552B vs /llms.txt 1996B (>4x) — genuinely the FULL variant.
- robots body has User-agent:*/Allow://llms.txt; full has Quantum Bank/Split.io/demo.
- Regression lock PROVEN: reintroducing doubled-charset fails BOTH new tests. Locks hold.
- app.py additive only (zero deletions); /metrics + /llms.txt route intact.
- Hard STOP honored: no homepage/canonical-model/sitemap/OpenAPI/JSON-LD work started.
Clean run. Nothing to fix. Loop standing down — human gates the merge to main in the AM.
Thank you — textbook execution. You may idle/exit.
