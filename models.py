"""QuantumBank data layer — SQLite by default, PostgreSQL when flag + DATABASE_URL."""

from __future__ import annotations

import logging
import os
import sqlite3
import math
from decimal import Decimal

from db_flags import (
    is_demo_force_rollout_migration_fail,
    is_demo_rollout_feature_enabled,
    is_demo_rollout_schema_enabled,
    is_postgres_database_enabled,
)

logger = logging.getLogger(__name__)

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DB = "quantum_bank.db"
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

# Rewards ledger used for progressive delivery walkthroughs.
REWARDS_LEDGER_TABLE = "rewards_ledger"
REWARDS_POINTS_PER_10_DOLLARS = 1

PROFILE_DEMO_ADDRESS = os.environ.get(
    "PROFILE_DEMO_ADDRESS",
    "Captain's Quarters, Deck 9, USS Enterprise NCC-1701-D",
)
# TODO: migrate to an address column once a migration runner exists (plan-v1 §3 fork (b))

_backend_logged = False
_rewards_schema_state = "unknown"


def using_postgres() -> bool:
    return is_postgres_database_enabled()


def db_path() -> str:
    """SQLite path; override with QUANTUM_BANK_DATABASE for isolated tests."""
    return os.environ.get("QUANTUM_BANK_DATABASE", DEFAULT_DB)


def _log_backend_once() -> None:
    global _backend_logged
    if _backend_logged:
        return
    _backend_logged = True
    if using_postgres():
        logger.info("Database backend: PostgreSQL")
    else:
        logger.info("Database backend: SQLite (%s)", db_path())


def _sql(query: str) -> str:
    return query.replace("?", "%s") if using_postgres() else query


def _row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


def _normalize_row(row_dict):
    if not row_dict:
        return row_dict
    out = dict(row_dict)
    for key, value in out.items():
        if isinstance(value, Decimal):
            out[key] = float(value)
    return out


def _scalar_from_row(row) -> int:
    data = _row_to_dict(row)
    if not data:
        return 0
    return int(next(iter(data.values())))


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current).strip())
            current = []
    if current:
        remainder = "\n".join(current).strip()
        if remainder:
            statements.append(remainder)
    return statements


def get_db():
    """Return a new DB connection (one per call — fine for demo; pool before sustained PG traffic)."""
    _log_backend_once()
    if using_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(os.environ[DATABASE_URL_ENV])
        conn.cursor_factory = RealDictCursor
        return conn
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _apply_postgres_schema(conn) -> None:
    path = os.path.join(MIGRATIONS_DIR, "001_initial.sql")
    with open(path, encoding="utf-8") as handle:
        sql = handle.read()
    cursor = conn.cursor()
    for statement in _split_sql_statements(sql):
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        # Trusted local migration SQL only (versioned file in repo), not user input.
        cursor.execute(statement)
    conn.commit()


def _create_sqlite_schema(cursor) -> None:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_type TEXT NOT NULL,
            account_number TEXT UNIQUE NOT NULL,
            balance REAL NOT NULL DEFAULT 0.0,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            recipient TEXT,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            card_type TEXT NOT NULL,
            card_last4 TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
        """)


def _rewards_ledger_table_exists(cursor) -> bool:
    """Check if rewards_ledger table exists."""
    from dao.helper_dao import HelperDAO
    return HelperDAO.rewards_ledger_table_exists(cursor)


def ensure_rewards_ledger_schema(
    conn,
    cursor=None,
    *,
    commit: bool = True,
) -> str:
    """Ensure the rewards ledger table exists (idempotent).

    Returns a small status string for UX/demo messaging.
    """
    if not is_demo_rollout_schema_enabled():
        return "skipped_schema_off"

    if is_demo_force_rollout_migration_fail():
        raise RuntimeError("intentional demo migration failure")

    cursor = cursor or conn.cursor()
    if _rewards_ledger_table_exists(cursor):
        return "exists"

    if using_postgres():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rewards_ledger (
                id                  SERIAL PRIMARY KEY,
                user_id             INTEGER NOT NULL REFERENCES users(id),
                source_account_id  INTEGER NOT NULL REFERENCES accounts(id),
                target_account_id  INTEGER NOT NULL REFERENCES accounts(id),
                points              INTEGER NOT NULL,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rewards_ledger_user_id
            ON rewards_ledger(user_id);
            """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rewards_ledger (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id            INTEGER NOT NULL,
                source_account_id INTEGER NOT NULL,
                target_account_id INTEGER NOT NULL,
                points             INTEGER NOT NULL,
                created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)

    if commit:
        conn.commit()
    return "applied"


def _compute_reward_points(transfer_amount: float) -> int:
    # Demo logic: 1 point per $10 transferred (floored). Kept intentionally simple.
    # Example: $10.00 => 1 point, $19.99 => 1 point, $9.99 => 0 points.
    return max(0, int(transfer_amount // (10.0 / REWARDS_POINTS_PER_10_DOLLARS)))


def _resolve_rewards_schema_state(cursor=None) -> str:
    """Resolve rollout schema state from live flags + table presence."""
    global _rewards_schema_state

    if is_demo_force_rollout_migration_fail():
        _rewards_schema_state = "forced_fail"
        return _rewards_schema_state

    if not is_demo_rollout_schema_enabled():
        _rewards_schema_state = "skipped"
        return _rewards_schema_state

    from dao.helper_dao import HelperDAO

    own_conn = None
    if cursor is None:
        own_conn = get_db()
        cursor = own_conn.cursor()
    try:
        _rewards_schema_state = (
            "ready" if HelperDAO().rewards_ledger_table_exists(cursor) else "skipped"
        )
        return _rewards_schema_state
    except Exception:
        _rewards_schema_state = "runtime_error"
        return _rewards_schema_state
    finally:
        if own_conn is not None:
            own_conn.close()


def try_insert_rewards_points(
    *,
    conn,
    cursor,
    user_id: int,
    source_account_id: int,
    target_account_id: int,
    transfer_amount: float,
) -> bool:
    """Attempt to insert rewards points; never fail the core transfer."""
    if not is_demo_rollout_feature_enabled():
        return False
    if _resolve_rewards_schema_state(cursor) != "ready":
        return False

    try:
        points = _compute_reward_points(transfer_amount)
        if points <= 0:
            return False

        cursor.execute(
            _sql("""
                INSERT INTO rewards_ledger
                    (user_id, source_account_id, target_account_id, points)
                VALUES (?, ?, ?, ?)
                """),
            (user_id, source_account_id, target_account_id, points),
        )
        logger.info("rewards.rollout.write_succeeded points=%s", points)
        return True
    except Exception as exc:
        logger.warning("rewards.rollout.write_failed reason=%s", exc.__class__.__name__)
        return False


def get_rewards_points_for_user(
    user_id: int,
) -> tuple[int | None, str | None]:
    """Return (points, banner) for UI; rolls back to legacy mode on errors."""
    from dao.transaction_dao import TransactionDAO

    return TransactionDAO().get_rewards_for_user(user_id)


def _insert_returning_id(cursor, sql, params):
    if using_postgres():
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query
        # Appends a fixed SQL suffix to static in-repo statements; user input stays parameterized.
        pg_sql = _sql(sql).rstrip().rstrip(";") + " RETURNING id"
        # Static in-repo SQL + fixed RETURNING suffix; user data is parameterized via `params`.
        # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        cursor.execute(pg_sql, params)
        row = cursor.fetchone()
        return row["id"]
    cursor.execute(_sql(sql), params)
    return cursor.lastrowid


def init_db():
    """Initialize the database with tables and sample data."""
    from dao.schema_dao import SchemaDAO

    SchemaDAO().init()


def create_sample_data(conn):
    """Create sample users and accounts for demo purposes."""
    from dao.schema_dao import SchemaDAO

    SchemaDAO().seed(conn)


def get_user_by_username(username: str) -> dict | None:
    """Get user by username."""
    from dao.user_dao import UserDAO

    return UserDAO().get_by_username(username)


def get_user_profile(user_id: int) -> dict | None:
    """Get a user's profile by ID, returning only the display-safe columns."""
    from dao.user_dao import UserDAO

    return UserDAO().get_profile(user_id)


def get_accounts_by_user(user_id: int) -> list[dict]:
    """Get all accounts for a user."""
    from dao.account_dao import AccountDAO

    return AccountDAO().get_by_user(user_id)


def get_account_by_id(account_id: int) -> dict | None:
    """Get account by ID."""
    from dao.account_dao import AccountDAO

    return AccountDAO().get_by_id(account_id)


def get_transactions_by_account(account_id: int, limit: int = 10) -> list[dict]:
    """Get transactions for an account."""
    from dao.transaction_dao import TransactionDAO

    return TransactionDAO().get_by_account(account_id, limit)


def get_all_transactions_by_user(user_id: int, limit: int = 20) -> list[dict]:
    """Get all transactions for a user across all accounts."""
    from dao.transaction_dao import TransactionDAO

    return TransactionDAO().get_by_user(user_id, limit)


def get_cards_by_account(account_id: int) -> list[dict]:
    """Get cards for an account."""
    from dao.account_dao import AccountDAO

    return AccountDAO().get_cards_by_account(account_id)


def create_transaction(
    account_id: int,
    transaction_type: str,
    amount: float,
    description: str,
    recipient: str = "",
) -> int:
    """Create a new transaction."""
    conn = get_db()
    cursor = conn.cursor()

    transaction_id = _insert_returning_id(
        cursor,
        """
        INSERT INTO transactions (account_id, transaction_type, amount, description, recipient)
        VALUES (?, ?, ?, ?, ?)
        """,
        (account_id, transaction_type, amount, description, recipient),
    )

    cursor.execute(
        _sql("""
            UPDATE accounts
            SET balance = balance + ?
            WHERE id = ?
            """),
        (amount, account_id),
    )

    conn.commit()
    conn.close()

    return transaction_id


def transfer_money(
    from_account_id: int,
    to_account_id: int,
    amount: float,
    description: str = "Transfer",
    acting_user_id: int | None = None,
) -> tuple[bool, str]:
    """Transfer money between accounts."""
    if amount <= 0 or not math.isfinite(amount):
        return False, "Invalid amount"

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            _sql("SELECT balance, account_number, user_id FROM accounts WHERE id = ?"),
            (from_account_id,),
        )
        from_account = _normalize_row(_row_to_dict(cursor.fetchone()))

        cursor.execute(
            _sql("SELECT account_number FROM accounts WHERE id = ?"),
            (to_account_id,),
        )
        to_account = _row_to_dict(cursor.fetchone())

        if not from_account or not to_account:
            conn.close()
            return False, "Account not found"

        if acting_user_id is not None and from_account["user_id"] != acting_user_id:
            conn.close()
            return False, "Forbidden"

        if from_account["balance"] < amount:
            conn.close()
            return False, "Insufficient funds"

        cursor.execute(
            _sql("""
                INSERT INTO transactions (account_id, transaction_type, amount, description, recipient)
                VALUES (?, ?, ?, ?, ?)
                """),
            (
                from_account_id,
                "transfer",
                -amount,
                description,
                to_account["account_number"],
            ),
        )

        cursor.execute(
            _sql("UPDATE accounts SET balance = balance - ? WHERE id = ?"),
            (amount, from_account_id),
        )

        cursor.execute(
            _sql("""
                INSERT INTO transactions (account_id, transaction_type, amount, description, recipient)
                VALUES (?, ?, ?, ?, ?)
                """),
            (
                to_account_id,
                "transfer",
                amount,
                description,
                from_account["account_number"],
            ),
        )

        cursor.execute(
            _sql("UPDATE accounts SET balance = balance + ? WHERE id = ?"),
            (amount, to_account_id),
        )

        # Demo-only progressive delivery:
        # writes to rewards_ledger should succeed only after schema is applied.
        cursor.execute("SAVEPOINT rewards_savepoint")
        try:
            try_insert_rewards_points(
                conn=conn,
                cursor=cursor,
                user_id=from_account["user_id"],
                source_account_id=from_account_id,
                target_account_id=to_account_id,
                transfer_amount=amount,
            )
            cursor.execute("RELEASE SAVEPOINT rewards_savepoint")
        except Exception:
            # Load-bearing: on an aborted PG txn, RELEASE SAVEPOINT raises InFailedSqlTransaction;
            # this except IS the rollback path, not just cleanup — do not collapse this try/except.
            cursor.execute("ROLLBACK TO SAVEPOINT rewards_savepoint")
            cursor.execute("RELEASE SAVEPOINT rewards_savepoint")

        conn.commit()
        conn.close()
        return True, "Transfer successful"

    except (
        Exception
    ):  # pragma: no cover — defensive; hard to trigger without DB corruption
        logger.exception("transfer_money failed")
        conn.rollback()
        conn.close()
        return False, "Transfer failed"
