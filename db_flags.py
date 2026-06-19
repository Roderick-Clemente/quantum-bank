"""Feature-flag resolution for the postgres_database backend switch."""

from __future__ import annotations

import logging
import os

from split_config import get_split_client

logger = logging.getLogger(__name__)

_ON_VALUES = frozenset({"on", "true", "1", "yes"})
_OFF_VALUES = frozenset({"off", "false", "0", "no"})


def _env_postgres_enabled() -> bool:
    return os.environ.get("POSTGRES_DATABASE", "off").lower() in _ON_VALUES


def is_postgres_database_enabled(user_key: str = "__system__") -> bool:
    """Resolve the postgres_database flag: Split → env → default(off).

    Returns True only when the flag is on *and* ``DATABASE_URL`` is set (D1).
    If the flag is on but ``DATABASE_URL`` is missing, logs a warning and returns False.
    """
    flag_on: bool | None = None

    split_client = get_split_client()
    if split_client and user_key:
        try:
            treatment = split_client.get_treatment(user_key, "postgres_database")
            logger.debug(
                "Split.io flag 'postgres_database' = %r (user: %s)",
                treatment,
                user_key,
            )
            if treatment in _ON_VALUES:
                flag_on = True
            elif treatment in _OFF_VALUES:
                return False
            elif treatment == "control":
                logger.debug(
                    "Split.io returned 'control' for postgres_database — using env var"
                )
            else:
                logger.debug(
                    "Unknown Split treatment %r for postgres_database — using env var",
                    treatment,
                )
        except Exception as exc:
            logger.warning(
                "Error getting Split.io treatment for postgres_database: %s — using env var",
                exc,
            )

    if flag_on is None:
        flag_on = _env_postgres_enabled()

    if not flag_on:
        return False

    if not os.environ.get("DATABASE_URL"):
        logger.warning(
            "postgres_database is on but DATABASE_URL is not set — staying on SQLite"
        )
        return False

    return True
