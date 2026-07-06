# =============================================================================
# File        : dialects/sqlite.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# License     : MIT
# Description : SQLite dialect (stdlib sqlite3). Zero-setup backend for
#               prototyping, tests, and embedded use. Inherits MySQL-style
#               backtick quoting and DDL/DML from MySQLDialect since SQLite's
#               dynamic type affinity accepts MySQL type strings unchanged.
# =============================================================================

from .mysql import MySQLDialect


class SQLiteDialect(MySQLDialect):
    """
    SQLite dialect (stdlib sqlite3 — no external driver required).

    Inherits SQL generation from MySQLDialect: SQLite accepts backtick
    identifier quoting (a documented MySQL-compatibility feature) and its
    dynamic type affinity accepts MySQL-style type strings (VARCHAR(255),
    TINYINT(1), DECIMAL(10,2), ...) without error.

    Key differences from MySQL:
    - No network port (file path or ":memory:" instead of host/port)
    - param_style "?" (qmark) instead of "%s" — translated transparently
      by the connection adapter in db.py, so SQL generation here still
      emits "%s" tokens like the rest of the dialect family
    - No AUTO_INCREMENT keyword; uses INTEGER PRIMARY KEY AUTOINCREMENT
    - No ENGINE=/CHARSET= table options
    - No native JSON type; stored as TEXT

    Usage:
        db.configure(dialect="sqlite", database=":memory:")
        db.configure(dialect="sqlite", database="app.db")
    """
    name         = "sqlite"
    param_style  = "?"
    default_port = None

    # ── DDL ──────────────────────────────────────────────────────── #

    @staticmethod
    def create_table_sql(table: str, columns: list, if_not_exists: bool = True) -> str:
        exist    = "IF NOT EXISTS " if if_not_exists else ""
        col_block = ",\n  ".join(columns)
        return (
            f"CREATE TABLE {exist}`{table}` (\n"
            f"  {col_block}\n"
            f");"
        )

    # ── Type overrides ──────────────────────────────────────────────── #

    @staticmethod
    def pk_definition() -> str:
        """No AUTO_INCREMENT keyword — use INTEGER PRIMARY KEY AUTOINCREMENT."""
        return "INTEGER PRIMARY KEY AUTOINCREMENT"

    @staticmethod
    def json_type() -> str:
        """No native JSON type in SQLite — stored as TEXT."""
        return "TEXT"

    @staticmethod
    def bool_type() -> str:
        """No native BOOLEAN type in SQLite — stored as INTEGER (0/1)."""
        return "INTEGER"
