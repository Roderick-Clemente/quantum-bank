# Quantum Bank

A small **Flask** demo app styled as a bank, built to showcase **Split.io** feature flags (instant variant switching vs. traditional server-rendered mode), plus a thin **SQLite**-backed “logged-in” flow (dashboard, accounts, transfers).

## Documentation

| Doc | What it is |
|-----|------------|
| [demo-fun.md](demo-fun.md) | **Why the app is shaped this way** — demo spectacle vs. “real site” for testers and AITs |
| [TECHSUMMARY.md](TECHSUMMARY.md) | Architecture, flags, templates, metrics, file map |
| [SPLITIO_SETUP.md](SPLITIO_SETUP.md) | Split.io keys and `home_page_variant` setup |
| [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) | Deploying to Render.com (Docker, env vars, custom domain) |

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

**Harness + Kubernetes (lab / alternate path)**  
- Under [`.harness/`](.harness/) there are **Harness service definitions** and **Kubernetes manifests** (e.g. `.harness/kubernetes/hsaab-quantum-bank-backend-deployment.yaml`) wired to a Harness org/project (`SE_Sandbox` / `devX_super_team` in the service YAML) and a GitHub connector.  
- That pipeline targets a **real K8s cluster** (image placeholder in [`hsaab-values.yaml`](.harness/kubernetes/hsaab-values.yaml)), **not** Render’s control plane.  
- If that org, connector, or cluster was only for a lab, the YAML may still be in the repo while the **live pipeline** is gone or idle — check the Harness UI for that project, or treat `.harness/` as a template and re-point org/connector/cluster.

**If you want a “new” pipeline today**  
- **Render-only:** Often no extra CI is required beyond GitHub → Render auto-deploy; optionally add **GitHub Actions** for tests on PR and keep Render as deploy target.  
- **K8s again:** Re-create a Harness (or GitHub Actions + `kubectl`/Helm) pipeline that builds/pushes the image and applies the manifests, updating org/project/connector values to match your current accounts.

## Stack (short)

- **App:** Flask, Gunicorn in production (`Dockerfile`)
- **DB:** SQLite file `quantum_bank.db` (no migration framework in repo yet — see `demo-fun.md` roadmap)
- **Flags:** Split server SDK (`split_config.py`) + browser SDK (`static/js/split-client.js`) in demo wrappers
- **Metrics:** Prometheus `/metrics` (see `app.py`)
