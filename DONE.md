DONE — stopped per spec.

Both units shipped on `pilot/ai-discovery` and pushed to origin:

  - Unit 1: /robots.txt       commit 6b4cb427 (AI Discovery #2)
  - Unit 2: /llms-full.txt    commit 82920a76 (AI Discovery #4)

Full test suite: test_public_routes.py — 20 passed in 0.11s, exit 0.

Acceptance, per orchestrator's per-unit criteria:

  /robots.txt:
    - GET /robots.txt : 200
    - Content-Type starts with "text/plain"
    - Content-Type has exactly one charset= token (no doubled charset)
    - body contains "User-agent: *", "Allow: /", "llms.txt"
  /llms-full.txt:
    - GET /llms-full.txt : 200
    - Content-Type starts with "text/plain"
    - Content-Type has exactly one charset= token
    - body contains "Quantum Bank", "Split.io", "demo"
    - len(/llms-full.txt) strictly greater than len(/llms.txt):
        8,552 bytes vs 1,996 bytes (delta +6,556 bytes; > 4x larger)
    - cross-fetched inside the same Flask test session in
      test_llms_full_txt_serves_expanded_manifest

Untouched per spec:
  - /metrics      (pre-existing doubled-charset defect, owned by main)
  - /llms.txt     (created in pilot/llms-txt; locked fix at 308aaa70)
  - main          (no merge, no PR — branch only)

OUT OF SCOPE per orchestrator's hard-stop clause (NOT started, await
human-gated planning):
  - homepage rewrite (server-rendered answers to "what / why /
    for-whom / how / different / get-started")
  - canonical content model (Product / Feature / Concept / Guide / ...)
  - sitemap.xml
  - OpenAPI spec
  - JSON-LD structured data (Organization / Product / FAQ / ...)
  - RSS / JSON feeds
  - AI-crawler observability
  - WCAG audit

Worker is idle. The orchestrator wakes ~every 10 min, fetches this
branch, and steers via STEER.md on orchestrator/steer (read-only for
me). I read STEER at the top of every unit; no new note has arrived
since the Aug 3 ~kickoff directive.
