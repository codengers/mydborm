# =============================================================================
# File        : dialects/__init__.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Dialect registry. Use get_dialect(name) to retrieve the
#               correct SQL generation class for MySQL or YugabyteDB.
#               Supports alias: postgres maps to YugabyteDialect.
# =============================================================================

# =============================================================================
# File        : dialects/__init__.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Dialect registry. Use get_dialect(name) to retrieve the
#               correct SQL generation class for MySQL or YugabyteDB.
#               Supports aliases: "postgres" maps to YugabyteDialect.
# =============================================================================

"""
dialects/ — Database-specific SQL generation.
"""

from .mysql import MySQLDialect
from .yugabyte import YugabyteDialect


def get_dialect(name: str):
    """
    Return the correct dialect class for a given name.

    get_dialect("mysql")     → MySQLDialect
    get_dialect("yugabyte")  → YugabyteDialect
    """
    dialects = {
        "mysql":    MySQLDialect,
        "yugabyte": YugabyteDialect,
        "postgres": YugabyteDialect,   # alias
    }
    if name not in dialects:
        raise ValueError(
            f"Unknown dialect: {name!r}. "
            f"Choose from: {list(dialects.keys())}"
        )
    return dialects[name]


__all__ = ["MySQLDialect", "YugabyteDialect", "get_dialect"]
