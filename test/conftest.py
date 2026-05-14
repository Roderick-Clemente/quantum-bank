import os

import pytest


def pytest_configure(config):
    """Stable env before lazy `from app import app` in the client fixture."""
    os.environ.setdefault("SECRET_KEY", "pytest-secret-key")


@pytest.fixture
def client():
    """HTTP client against the Flask app (same process, no network)."""
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
