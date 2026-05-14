"""Runs before other test modules (name sorts first): fresh DB."""

import importlib

import pytest


@pytest.mark.models
def test_init_db_seeds_demo_on_empty_database(monkeypatch, tmp_path):
    """Fresh SQLite file exercises create_sample_data and create_transaction."""
    monkeypatch.setenv("QUANTUM_BANK_DATABASE", str(tmp_path / "qb.sqlite"))

    import models

    importlib.reload(models)
    models.init_db()

    user = models.get_user_by_username("demo")
    assert user is not None

    accounts = models.get_accounts_by_user(user["id"])
    assert len(accounts) >= 1

    cid = accounts[0]["id"]
    tid = models.create_transaction(cid, "deposit", 1.0, "bootstrap", "pytest")
    assert tid is not None
