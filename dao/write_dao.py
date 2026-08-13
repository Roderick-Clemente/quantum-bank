"""Write Data Access Object for transaction creation and management."""

from dao.base_dao import BaseDAO


class WriteDAO(BaseDAO):
    """Write operations: transaction creation, rewards insertion, transfers."""

    def create_transaction_internal(
        self,
        conn,
        account_id: int,
        transaction_type: str,
        amount: float,
        description: str,
        recipient: str = "",
    ) -> int:
        """Create a new transaction (DAO method, receives caller's connection)."""
        from models import _insert_returning_id, _sql

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

        return transaction_id
