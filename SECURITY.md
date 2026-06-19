# Security Policy

## This is a demonstration application

Quantum Bank is a **demo app** built to showcase Split.io feature flags and a
flag-gated SQLite ↔ PostgreSQL backend switch. It is **not** a real bank and
**not** a reference implementation for security or banking systems.

- **All data is synthetic.** Accounts, balances, transactions, and cards are
  fake and seeded at startup.
- **No real money, no real customers, no real card data.** Card records store a
  masked last-4 only — no PAN, no CVV, no expiry beyond a display string.
- **Auth is intentionally trivial.** Login is username-only (`demo`) with no
  password. The session and login handling are demo conveniences and must not
  be reused in production.
- The default `SECRET_KEY` is a development fallback. Any shared or public
  deployment must set a real, secret `SECRET_KEY`.

## Reporting a vulnerability

Because this is a demonstration project with no real users or data, there is no
formal security response process or SLA.

If you spot something worth fixing — for example a way the demo could leak the
synthetic data store, an unsafe default, or a dependency advisory — please open
a GitHub issue (or a pull request) on
[Roderick-Clemente/quantum-bank](https://github.com/Roderick-Clemente/quantum-bank).
For anything you'd prefer not to disclose publicly, use GitHub's private
**Security advisories** feature on the repository.

## Scope notes

- Dependency/SCA scanning (OWASP Dependency-Check, OSV) runs in the Harness CI
  pipeline — see [HARNESS.md](HARNESS.md).
- Do not deploy this app as a real financial service.
