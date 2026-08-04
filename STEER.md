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
