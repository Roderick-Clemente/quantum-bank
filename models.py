"""QuantumBank data layer — SQLite by default, PostgreSQL when flag + DATABASE_URL."""

from __future__ import annotations

import logging
import os
import sqlite3
from decimal import Decimal

from db_flags import is_postgres_database_enabled

logger = logging.getLogger(__name__)

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DB = "quantum_bank.db"
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

_backend_logged = False


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


def _insert_returning_id(cursor, sql, params):
    if using_postgres():
        pg_sql = _sql(sql).rstrip().rstrip(";") + " RETURNING id"
        cursor.execute(pg_sql, params)
        row = cursor.fetchone()
        return row["id"]
    cursor.execute(_sql(sql), params)
    return cursor.lastrowid


def init_db():
    """Initialize the database with tables and sample data."""
    conn = get_db()
    cursor = conn.cursor()

    if using_postgres():
        _apply_postgres_schema(conn)
    else:
        _create_sqlite_schema(cursor)
        conn.commit()

    cursor.execute(_sql("SELECT COUNT(*) FROM users"))
    if _scalar_from_row(cursor.fetchone()) == 0:
        create_sample_data(conn)

    conn.close()


def create_sample_data(conn):
    """Create sample users and accounts for demo purposes."""
    cursor = conn.cursor()

    user_id = _insert_returning_id(
        cursor,
        """
        INSERT INTO users (username, email, full_name)
        VALUES (?, ?, ?)
        """,
        ("demo", "demo@quantumbank.com", "Demo User"),
    )

    checking_id = _insert_returning_id(
        cursor,
        """
        INSERT INTO accounts (user_id, account_type, account_number, balance)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, "checking", "QB-CHK-100001", 5420.50),
    )

    savings_id = _insert_returning_id(
        cursor,
        """
        INSERT INTO accounts (user_id, account_type, account_number, balance)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, "savings", "QB-SAV-200001", 12850.75),
    )

    credit_id = _insert_returning_id(
        cursor,
        """
        INSERT INTO accounts (user_id, account_type, account_number, balance)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, "credit", "QB-CC-300001", -1234.20),
    )

    transactions = [
        (checking_id, "deposit", 1500.00, "Payroll Deposit", "Acme Corp", "completed"),
        (
            checking_id,
            "withdrawal",
            -45.20,
            "Coffee Shop",
            "Blue Bottle Coffee",
            "completed",
        ),
        (
            checking_id,
            "withdrawal",
            -125.00,
            "Grocery Shopping",
            "Whole Foods",
            "completed",
        ),
        (checking_id, "withdrawal", -89.99, "Online Purchase", "Amazon", "completed"),
        (
            checking_id,
            "transfer",
            -500.00,
            "Transfer to Savings",
            "Savings Account",
            "completed",
        ),
    ]

    for trans in transactions:
        cursor.execute(
            _sql("""
                INSERT INTO transactions (account_id, transaction_type, amount, description, recipient, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """),
            trans,
        )

    savings_transactions = [
        (savings_id, "deposit", 5000.00, "Initial Deposit", "Self", "completed"),
        (
            savings_id,
            "transfer",
            500.00,
            "Transfer from Checking",
            "Checking Account",
            "completed",
        ),
        (
            savings_id,
            "interest",
            25.75,
            "Monthly Interest",
            "Quantum Bank",
            "completed",
        ),
    ]

    for trans in savings_transactions:
        cursor.execute(
            _sql("""
                INSERT INTO transactions (account_id, transaction_type, amount, description, recipient, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """),
            trans,
        )

    credit_transactions = [
        (credit_id, "charge", -234.50, "Restaurant", "Chez Pierre", "completed"),
        (credit_id, "charge", -89.99, "Gas Station", "Shell", "completed"),
        (credit_id, "charge", -599.99, "Electronics", "Best Buy", "completed"),
        (
            credit_id,
            "payment",
            500.00,
            "Credit Card Payment",
            "Online Payment",
            "completed",
        ),
    ]

    for trans in credit_transactions:
        cursor.execute(
            _sql("""
                INSERT INTO transactions (account_id, transaction_type, amount, description, recipient, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """),
            trans,
        )

    cards = [
        (checking_id, "debit", "1234", "12/2026"),
        (credit_id, "credit", "5678", "09/2027"),
    ]

    for card in cards:
        cursor.execute(
            _sql("""
                INSERT INTO cards (account_id, card_type, card_last4, expiry_date)
                VALUES (?, ?, ?, ?)
                """),
            card,
        )

    conn.commit()


def get_user_by_username(username: str) -> dict | None:
    """Get user by username."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql("SELECT * FROM users WHERE username = ?"), (username,))
    user = cursor.fetchone()
    conn.close()
    return _row_to_dict(user)


def get_accounts_by_user(user_id: int) -> list[dict]:
    """Get all accounts for a user."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        _sql("SELECT * FROM accounts WHERE user_id = ? ORDER BY created_at"),
        (user_id,),
    )
    accounts = cursor.fetchall()
    conn.close()
    return [_normalize_row(_row_to_dict(account)) for account in accounts]


def get_account_by_id(account_id: int) -> dict | None:
    """Get account by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql("SELECT * FROM accounts WHERE id = ?"), (account_id,))
    account = cursor.fetchone()
    conn.close()
    return _normalize_row(_row_to_dict(account))


def get_transactions_by_account(account_id: int, limit: int = 10) -> list[dict]:
    """Get transactions for an account."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        _sql("""
            SELECT * FROM transactions
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """),
        (account_id, limit),
    )
    transactions = cursor.fetchall()
    conn.close()
    return [_normalize_row(_row_to_dict(trans)) for trans in transactions]


def get_all_transactions_by_user(user_id: int, limit: int = 20) -> list[dict]:
    """Get all transactions for a user across all accounts."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        _sql("""
            SELECT t.*, a.account_type, a.account_number
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            WHERE a.user_id = ?
            ORDER BY t.created_at DESC
            LIMIT ?
            """),
        (user_id, limit),
    )
    transactions = cursor.fetchall()
    conn.close()
    return [_normalize_row(_row_to_dict(trans)) for trans in transactions]


def get_cards_by_account(account_id: int) -> list[dict]:
    """Get cards for an account."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql("SELECT * FROM cards WHERE account_id = ?"), (account_id,))
    cards = cursor.fetchall()
    conn.close()
    return [_normalize_row(_row_to_dict(card)) for card in cards]


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
) -> tuple[bool, str]:
    """Transfer money between accounts."""
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            _sql("SELECT balance, account_number FROM accounts WHERE id = ?"),
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
