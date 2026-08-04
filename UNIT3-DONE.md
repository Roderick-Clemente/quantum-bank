Unit 3 done — stopped per spec.

All three Kimi nits shipped on `pilot/ai-discovery` and pushed to origin:

  - FIX 1 (the important one): builder process-narrative removed from
    the public manifest. New closing: `Last updated: 2026-08-03. \n For
    the short manifest, see /llms.txt.` Internal words audit clean:
    'worker', 'pilot', 'human-gated', 'canonical content model' all
    absent from the body.
  - FIX 2: /metrics doc line in the endpoint inventory now reads as
    `GET /metrics                       Prometheus text exposition`
    (parenthetical charset claim dropped, no mention of the doubled-
    charset detail).
  - FIX 3: test_llms_full_txt_serves_expanded_manifest now asserts
    `"fictional" in body.lower()`, matching the sibling /llms.txt
    test. Prove-cycle shipped in the commit body:
    GREEN → momentarily break body → RED → restore → GREEN.

Final test summary line (`pytest test/test_public_routes.py`):

    20 passed in 0.11s

Direct flask test_client invariants (assert on reality):

    /robots.txt           Content-Type='text/plain; charset=utf-8'  charset=1
    /llms.txt             Content-Type='text/plain; charset=utf-8'  charset=1
    /llms-full.txt        Content-Type='text/plain; charset=utf-8'  charset=1   body=8384 B (was 8552)
    /metrics              Content-Type='text/plain; version=0.0.4; charset=utf-8; charset=utf-8'  charset=2  (UNCHANGED, pre-existing defect)

    len(llms-full)=8384, len(llms)=1996, ratio=4.20x — expanded invariant holds.

Untouched per spec: /metrics, /llms.txt, /robots.txt response
behavior; api/robots_txt.py; app.py; main (no merge, no PR).

Worker is idle. Out-of-scope (still NOT started, per orchestrator):
homepage rewrite, canonical content model, sitemap.xml, OpenAPI,
JSON-LD, RSS/JSON feeds, AI-crawler observability, WCAG. Awaiting
orchestrator's verify and Rod's merge gate.
