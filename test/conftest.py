import os
import tempfile

import pytest


def pytest_configure(config):
    """Stable env before lazy `from app import app` in the client fixture."""
    os.environ.setdefault("SECRET_KEY", "pytest-secret-key")
    os.environ.setdefault("POSTGRES_DATABASE", "off")
    if "QUANTUM_BANK_DATABASE" not in os.environ:
        _fd, path = tempfile.mkstemp(suffix=".sqlite")
        os.close(_fd)
        os.environ["QUANTUM_BANK_DATABASE"] = path


@pytest.fixture
def split_unavailable(monkeypatch):
    """Flag logic tests use env only — Split is an external boundary."""
    monkeypatch.setattr("db_flags.get_split_client", lambda: None)


@pytest.fixture
def client():
    """HTTP client against the Flask app (same process, no network)."""
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
