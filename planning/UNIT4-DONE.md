Unit 4 done — stopped per spec.

Unit 4 = real /sitemap.xml so the robots.txt + /llms-full.txt promise is
true. Closes Grok's dangling-reference finding. Branch:
`pilot/sitemap` (fresh off origin/main @ a1050a87, NOT off the old
pilot/ai-discovery).

Final test summary line (`pytest test/test_public_routes.py`):

    22 passed in 0.11s

Direct flask test_client invariants (assert on reality):

    /robots.txt        Content-Type='text/plain; charset=utf-8'                charset=1  body=304 B
    /llms.txt          Content-Type='text/plain; charset=utf-8'                charset=1  body=1996 B
    /llms-full.txt     Content-Type='text/plain; charset=utf-8'                charset=1  body=8384 B
    /metrics           Content-Type='text/plain; version=0.0.4; charset=utf-8; charset=utf-8'  charset=2  (UNCHANGED, pre-existing defect)
    /sitemap.xml       Content-Type='application/xml; charset=utf-8'           charset=1  body=500 B

Sitemap body — 8 distinct <loc> entries (canonical public GET pages)
and 14 forbidden substrings absent (/api/*, /dashboard, /account,
/logout, /transactions, /metrics, /robots.txt, /*-static variants).
XML urlset at http://www.sitemaps.org/schemas/sitemap/0.9 — parses
clean in xml.etree.ElementTree.fromstring.

/api/ exclusion lock PROVEN via true-removal mutation: inject
<url><loc>https://qbank.dev/api/sessions</loc></url> ahead of </urlset>,
RED on `'/api/' not in body` assertion, restore from /tmp backup,
GREEN. Disk == HEAD post-cycle.

Robots promise loop CLOSED at the test layer:
    Sitemap: https://qbank.dev/sitemap.xml   in robots.txt
    GET /sitemap.xml                         returns 200

Untouched per spec: /metrics, /llms.txt, /robots.txt, /llms-full.txt
routes and responses; api/robots_txt.py; api/llms_txt.py;
api/llms_full_txt.py; main (no merge, no PR).

Branch cleanup (after Unit 4 GREEN + pushed):
    deleted (was merged via PR #9 -> a1050a87):  pilot/ai-discovery
    deleted (was merged earlier):              pilot/llms-txt
    kept alive (this branch):                  pilot/sitemap
    preserved (orchestrator):                  origin/orchestrator/steer
    preserved (other work):                    feature/rewards-rollout-fme,
                                              pre-security-sca-baseline,
                                              security-*

Branch tip on origin: 8afc6314 (matches local HEAD byte-for-byte).
Pushed-branch URL:
    https://github.com/Roderick-Clemente/quantum-bank/tree/pilot/sitemap

Worker is idle. Out-of-scope items NOT started, awaiting orchestrator
verify + Rod merge gate: homepage rewrite, canonical content model,
OpenAPI, JSON-LD, RSS/JSON feeds, AI-crawler observability, WCAG.
