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

    def insert_rewards_points(
        self,
        *,
        conn,
        cursor,
        user_id: int,
        source_account_id: int,
        target_account_id: int,
        transfer_amount: float,
    ) -> bool:
        """Attempt to insert rewards points; never fail the core transfer (exact copy of current implementation)."""
        from db_flags import is_demo_rollout_feature_enabled
        from models import (
            _resolve_rewards_schema_state,
            _compute_reward_points,
            _sql,
            logger,
        )

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
            logger.warning(
                "rewards.rollout.write_failed reason=%s", exc.__class__.__name__
            )
            return False
