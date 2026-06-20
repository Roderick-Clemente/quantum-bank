"""Runs before other test modules (name sorts first): fresh DB."""

import importlib
import logging
import os

import pytest

_EXPECTED_SCHEMA = {
    "users": {"id", "username", "email", "full_name", "created_at"},
    "accounts": {
        "id",
        "user_id",
        "account_type",
        "account_number",
        "balance",
        "currency",
        "status",
        "created_at",
    },
    "transactions": {
        "id",
        "account_id",
        "transaction_type",
        "amount",
        "description",
        "recipient",
        "status",
        "created_at",
    },
    "cards": {
        "id",
        "account_id",
        "card_type",
        "card_last4",
        "expiry_date",
        "status",
        "created_at",
    },
}

_FORBIDDEN_CARD_COLUMNS = {"card_number", "cvv"}


def _postgres_env_enabled() -> bool:
    url = os.environ.get("DATABASE_URL")
    flag = os.environ.get("POSTGRES_DATABASE", "off").lower()
    return bool(url) and flag in ("on", "true", "1", "yes")


def _configure_backend(monkeypatch, tmp_path):
    """Use CI Postgres when configured; otherwise isolated SQLite file."""
    if _postgres_env_enabled():
        monkeypatch.setenv("DATABASE_URL", os.environ["DATABASE_URL"])
        monkeypatch.setenv("POSTGRES_DATABASE", "on")
        monkeypatch.delenv("QUANTUM_BANK_DATABASE", raising=False)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("POSTGRES_DATABASE", "off")
        monkeypatch.setenv("QUANTUM_BANK_DATABASE", str(tmp_path / "qb.sqlite"))


def _reload_models():
    import db_flags
    import models

    importlib.reload(db_flags)
    importlib.reload(models)
    return models


@pytest.mark.models
def test_postgres_backend_disabled_when_flag_off_even_with_database_url(
    monkeypatch, split_unavailable, tmp_path
):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setenv("POSTGRES_DATABASE", "off")
    monkeypatch.setenv("QUANTUM_BANK_DATABASE", str(tmp_path / "qb.sqlite"))

    models = _reload_models()
    assert models.using_postgres() is False


@pytest.mark.models
def test_postgres_backend_enabled_when_flag_on_and_database_url_set(
    monkeypatch, split_unavailable, tmp_path
):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/test")
    monkeypatch.setenv("POSTGRES_DATABASE", "on")
    monkeypatch.setenv("QUANTUM_BANK_DATABASE", str(tmp_path / "qb.sqlite"))

    models = _reload_models()
    assert models.using_postgres() is True


@pytest.mark.models
def test_postgres_backend_stays_sqlite_when_flag_on_but_database_url_missing(
    monkeypatch, split_unavailable, caplog, tmp_path
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_DATABASE", "on")
    monkeypatch.setenv("QUANTUM_BANK_DATABASE", str(tmp_path / "qb.sqlite"))

    with caplog.at_level(logging.WARNING):
        models = _reload_models()
        assert models.using_postgres() is False

    assert any("DATABASE_URL is not set" in record.message for record in caplog.records)


@pytest.mark.models
def test_init_db_seeds_demo_on_empty_database(monkeypatch, split_unavailable, tmp_path):
    """Fresh SQLite file exercises create_sample_data and create_transaction."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_DATABASE", "off")
    monkeypatch.setenv("QUANTUM_BANK_DATABASE", str(tmp_path / "qb.sqlite"))

    models = _reload_models()
    models.init_db()

    user = models.get_user_by_username("demo")
    assert user is not None
    assert user["username"] == "demo"

    accounts = models.get_accounts_by_user(user["id"])
    assert len(accounts) >= 1

    account_id = accounts[0]["id"]
    transaction_id = models.create_transaction(
        account_id, "deposit", 1.0, "bootstrap", "pytest"
    )
    assert isinstance(transaction_id, int)
    assert transaction_id > 0


@pytest.mark.models
def test_transfer_money_small_amount_updates_balances(
    monkeypatch, split_unavailable, tmp_path
):
    _configure_backend(monkeypatch, tmp_path)
    models = _reload_models()
    models.init_db()

    user = models.get_user_by_username("demo")
    accounts = models.get_accounts_by_user(user["id"])
    checking = next(a for a in accounts if a["account_type"] == "checking")
    savings = next(a for a in accounts if a["account_type"] == "savings")

    before_checking = checking["balance"]
    before_savings = savings["balance"]
    amount = 10.0

    ok, message = models.transfer_money(checking["id"], savings["id"], amount, "pytest")

    assert ok is True
    assert message == "Transfer successful"
    checking_after = models.get_account_by_id(checking["id"])
    savings_after = models.get_account_by_id(savings["id"])
    assert checking_after["balance"] == pytest.approx(before_checking - amount)
    assert savings_after["balance"] == pytest.approx(before_savings + amount)


@pytest.mark.models
def test_demo_seeded_cards_expose_masked_last4_only(
    monkeypatch, split_unavailable, tmp_path
):
    _configure_backend(monkeypatch, tmp_path)
    models = _reload_models()
    models.init_db()

    user = models.get_user_by_username("demo")
    checking = next(
        a
        for a in models.get_accounts_by_user(user["id"])
        if a["account_type"] == "checking"
    )

    cards = models.get_cards_by_account(checking["id"])

    assert cards
    assert cards[0]["card_last4"] == "1234"
    assert "card_number" not in cards[0]
    assert "cvv" not in cards[0]


@pytest.mark.models
def test_database_schema_matches_expected_columns(
    monkeypatch, split_unavailable, tmp_path
):
    """Drift guard: both backends expose the same logical column set (D3/D8)."""
    _configure_backend(monkeypatch, tmp_path)
    models = _reload_models()
    models.init_db()

    conn = models.get_db()
    cursor = conn.cursor()
    try:
        sqlite_table_info_sql = {
            "users": "PRAGMA table_info(users)",
            "accounts": "PRAGMA table_info(accounts)",
            "transactions": "PRAGMA table_info(transactions)",
            "cards": "PRAGMA table_info(cards)",
        }
        if models.using_postgres():
            for table, expected_columns in _EXPECTED_SCHEMA.items():
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table,),
                )
                actual = {row["column_name"] for row in cursor.fetchall()}
                missing = expected_columns - actual
                assert not missing, f"{table} missing columns: {missing}"
                assert not (
                    _FORBIDDEN_CARD_COLUMNS & actual
                ), f"{table} has forbidden card columns"
        else:
            for table, expected_columns in _EXPECTED_SCHEMA.items():
                cursor.execute(sqlite_table_info_sql[table])
                actual = {row[1] for row in cursor.fetchall()}
                missing = expected_columns - actual
                assert not missing, f"{table} missing columns: {missing}"
                assert not (
                    _FORBIDDEN_CARD_COLUMNS & actual
                ), f"{table} has forbidden card columns"
    finally:
        conn.close()
