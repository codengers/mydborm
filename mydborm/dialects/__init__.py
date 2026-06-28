# =============================================================================
# File        : dialects/__init__.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Version     : 1.4.0
# License     : MIT
# Description : Dialect registry.
# =============================================================================

from .mysql    import MySQLDialect
from .yugabyte import YugabyteDialect
from .postgres import PostgreSQLDialect
from ..exceptions import UnsupportedDialectError


def get_dialect(name: str):
    """
    Return the correct dialect class for a given name.

    Usage:
        get_dialect("mysql")      → MySQLDialect
        get_dialect("yugabyte")   → YugabyteDialect
        get_dialect("postgres")   → PostgreSQLDialect
        get_dialect("postgresql") → PostgreSQLDialect

    Args:
        name: dialect name string

    Raises:
        UnsupportedDialectError: if dialect name is not recognised
            (also a ValueError, for backward compatibility)
    """
    dialects = {
        "mysql"      : MySQLDialect,
        "yugabyte"   : YugabyteDialect,
        "postgres"   : PostgreSQLDialect,
        "postgresql" : PostgreSQLDialect,
    }
    if name not in dialects:
        raise UnsupportedDialectError(
            f"Unknown dialect: {name!r}. "
            f"Supported: {list(dialects.keys())}",
            dialect=name,
            supported=list(dialects.keys()),
        )
    return dialects[name]


__all__ = [
    "MySQLDialect",
    "YugabyteDialect",
    "PostgreSQLDialect",
    "get_dialect",
]