from flask import Flask, request, session, Response, g
from dotenv import load_dotenv

from prometheus_minimal import Counter, Histogram, format_metrics
import os
import time as t
import atexit

from api.hello import handle_hello
from api.home import handle_home
from api.home_content import handle_home_content
from api.home_static import (
    handle_old_home_static,
    handle_new_home_static,
    handle_v3_home_static,
)
from api.time import handle_time
from api.about import handle_about
from api.pricing import handle_pricing
from api.pricing_static import (
    handle_old_pricing_static,
    handle_new_pricing_static,
    handle_v3_pricing_static,
)
from api.four_o_four import handle_404
from api.login import handle_login, handle_logout
from api.dashboard import handle_dashboard
from api.accounts import handle_account_detail
from api.transfer import handle_transfer, handle_api_transfer
from api.transactions import handle_transactions
from api.api_endpoints import (
    handle_api_accounts,
    handle_api_transactions,
    handle_api_account_detail,
)
from models import init_db
from split_config import init_split, destroy_split

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "quantum-bank-secret-key-change-in-production"
)


@app.template_filter("currency")
def currency_filter(value):
    """Format number as currency with commas and 2 decimal places"""
    return "{:,.2f}".format(float(value))


init_db()
init_split()
atexit.register(destroy_split)


REQUEST_COUNT = Counter(
    "app_request_count",
    "Application Request Count",
    ["method", "endpoint", "http_status"],
)
REQUEST_LATENCY = Histogram(
    "app_request_latency_seconds",
    "Application Request Latency",
    ["method", "endpoint"],
)


@app.before_request
def _record_request_start():
    # Skip /metrics so Prometheus scrapes don't inflate their own series.
    if request.endpoint == "metrics":
        return
    g._start_time = t.time()


@app.after_request
def _record_request_metrics(response):
    if request.endpoint == "metrics":
        return response
    rule = request.url_rule.rule if request.url_rule else "unknown"
    REQUEST_COUNT.labels(request.method, rule, response.status_code).inc()
    start = getattr(g, "_start_time", None)
    if start is not None:
        REQUEST_LATENCY.labels(request.method, rule).observe(t.time() - start)
    return response


@app.route("/metrics")
def metrics():
    return Response(
        format_metrics(),
        mimetype="text/plain; version=0.0.4; charset=utf-8",
    )


@app.route("/demo")
def demo():
    """Demo entry point - forces demo mode ON"""
    try:
        session["entry_path"] = "/demo"
    except Exception as e:  # pragma: no cover
        print(f"[Demo] Warning: Could not set session: {e}")
    return handle_home()


@app.route("/")
def home():
    try:
        session["entry_path"] = request.path
    except Exception as e:  # pragma: no cover
        print(f"[Home] Warning: Could not set session: {e}")
    return handle_home()


@app.route("/api/home-content")
def home_content():
    return handle_home_content()


@app.route("/old-home-static")
def old_home_static():
    return handle_old_home_static()


@app.route("/new-home-static")
def new_home_static():
    return handle_new_home_static()


@app.route("/v3-home-static")
def v3_home_static():
    return handle_v3_home_static()


@app.route("/hello")
def hello():
    return handle_hello()


@app.route("/time")
def time():
    return handle_time()


@app.route("/about")
def about():
    return handle_about()


@app.route("/pricing")
def pricing():
    return handle_pricing()


@app.route("/old-pricing-static")
def old_pricing_static():
    return handle_old_pricing_static()


@app.route("/new-pricing-static")
def new_pricing_static():
    return handle_new_pricing_static()


@app.route("/v3-pricing-static")
def v3_pricing_static():
    return handle_v3_pricing_static()


@app.errorhandler(404)
def page_not_found(e):
    return handle_404()


# Banking routes
@app.route("/login", methods=["GET", "POST"])
def login():
    return handle_login()


@app.route("/logout")
def logout():
    return handle_logout()


@app.route("/dashboard")
def dashboard():
    return handle_dashboard()


@app.route("/account")
def account():
    return handle_account_detail()


@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    return handle_transfer()


@app.route("/transactions")
def transactions():
    return handle_transactions()


# API routes
@app.route("/api/accounts")
def api_accounts():
    return handle_api_accounts()


@app.route("/api/transactions")
def api_transactions():
    return handle_api_transactions()


@app.route("/api/account/<int:account_id>")
def api_account_detail(account_id):
    return handle_api_account_detail(account_id)


@app.route("/api/transfer", methods=["POST"])
def api_transfer():
    return handle_api_transfer()


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=5001, debug=True)
