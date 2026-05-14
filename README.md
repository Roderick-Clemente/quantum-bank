# Quantum Bank

A small **Flask** demo app styled as a bank, built to showcase **Split.io** feature flags (instant variant switching vs. traditional server-rendered mode), plus a thin **SQLite**-backed “logged-in” flow (dashboard, accounts, transfers).

## Documentation

| Doc | What it is |
|-----|------------|
| [demo-fun.md](demo-fun.md) | **Why the app is shaped this way** — demo spectacle vs. “real site” for testers and AITs |
| [TECHSUMMARY.md](TECHSUMMARY.md) | Architecture, flags, templates, metrics, file map |
| [SPLITIO_SETUP.md](SPLITIO_SETUP.md) | Split.io keys and `home_page_variant` setup |
| [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) | Deploying to Render.com (Docker, env vars, custom domain) |
| [HARNESS.md](HARNESS.md) | **Harness CI** — GitHub connector, `rod-bank-pipeline`, reference execution, handoff prompt for SCA triage |

## Quick start (local)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         # add SPLIT_API_KEY, SECRET_KEY, etc.
python app.py                # default in app: http://0.0.0.0:5001
```

Demo login uses seeded user **`demo`** (see `models.py` / `RENDER_DEPLOYMENT.md`).

## Deployment: Render vs. Kubernetes

**Render (this repo’s primary PaaS path)**  
- Config: [`render.yaml`](render.yaml) + [`Dockerfile`](Dockerfile).  
- **Not Kubernetes.** Render runs your image as a **managed web service** (Docker on their platform).  
- Typical flow: connect the GitHub repo in the Render dashboard, set `SPLIT_API_KEY` and `SECRET_KEY`, push to `main` → auto-deploy (see `RENDER_DEPLOYMENT.md`).

**Harness**  
- **CI (GitHub → tests + SCA):** see **[HARNESS.md](HARNESS.md)** — pipeline `rod-bank-pipeline` in org **`sandbox`**, project **`devX_super_team`**, plus a **green reference execution** id you can paste into follow-up chats.  
- **CD / Kubernetes (lab YAML):** under [`.harness/kubernetes/`](.harness/kubernetes/) — older manifests may use labels like `SE_Sandbox`; live CI for this story uses org **`sandbox`**. CD is separate from the CI pipeline above.

**If you want a “new” deploy pipeline**  
- **Render:** connect repo → auto-deploy from `main` ([RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)).  
- **K8s / Harness CD:** re-point `.harness/kubernetes/*` + Harness services to your cluster and registry (see [HARNESS.md](HARNESS.md) for CI vs CD split).

## Stack (short)

- **App:** Flask, Gunicorn in production (`Dockerfile`)
- **DB:** SQLite file `quantum_bank.db` (no migration framework in repo yet — see `demo-fun.md` roadmap)
- **Flags:** Split server SDK (`split_config.py`) + browser SDK (`static/js/split-client.js`) in demo wrappers
- **Metrics:** Prometheus `/metrics` (see `app.py`)
