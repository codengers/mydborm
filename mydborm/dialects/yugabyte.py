# =============================================================================
# File        : dialects/yugabyte.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : YugabyteDB (YSQL) dialect. Uses PostgreSQL wire protocol
#               via psycopg2. Key differences from MySQL: double-quote
#               identifiers, SERIAL/UUID primary keys, native BOOLEAN,
#               JSONB for indexable JSON, and RETURNING id on INSERT.
# =============================================================================

"""
dialects/yugabyte.py — YugabyteDB (YSQL) specific SQL generation.
YugabyteDB is PostgreSQL-wire-compatible so we use psycopg2,
but with key differences: UUID PKs, JSONB, BOOLEAN, SERIAL.
"""


class YugabyteDialect:
    name = "yugabyte"
    param_style = "%s"          # psycopg2 also uses %s
    default_port = 5433

    # ── DDL ──────────────────────────────────────────────────────── #

    @staticmethod
    def create_table_sql(table: str, columns: list[str],
                         if_not_exists: bool = True) -> str:
        exist = "IF NOT EXISTS " if if_not_exists else ""
        col_block = ",\n  ".join(columns)
        return (
            f'CREATE TABLE {exist}"{table}" (\n'
            f"  {col_block}\n"
            f");"
        )

    @staticmethod
    def drop_table_sql(table: str, if_exists: bool = True) -> str:
        exist = "IF EXISTS " if if_exists else ""
        return f'DROP TABLE {exist}"{table}";'

    @staticmethod
    def add_column_sql(table: str, column: str, definition: str) -> str:
        return f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition};'

    @staticmethod
    def drop_column_sql(table: str, column: str) -> str:
        return f'ALTER TABLE "{table}" DROP COLUMN "{column}";'

    # ── DML ──────────────────────────────────────────────────────── #

    @staticmethod
    def insert_sql(table: str, columns: list[str]) -> str:
        cols = ", ".join(f'"{c}"' for c in columns)
        vals = ", ".join(["%s"] * len(columns))
        return (
            f'INSERT INTO "{table}" ({cols}) '
            f"VALUES ({vals}) RETURNING id;"
        )

    @staticmethod
    def select_sql(table: str, where: str = None,
                   order_by: str = None, limit: int = None) -> str:
        sql = f'SELECT * FROM "{table}"'
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        return sql + ";"

    @staticmethod
    def update_sql(table: str, set_clause: str, where: str) -> str:
        return f'UPDATE "{table}" SET {set_clause} WHERE {where};'

    @staticmethod
    def delete_sql(table: str, where: str) -> str:
        return f'DELETE FROM "{table}" WHERE {where};'

    # ── Type overrides ────────────────────────────────────────────── #

    @staticmethod
    def pk_definition() -> str:
        """
        YugabyteDB recommends UUID or SERIAL for distributed PKs.
        Using SERIAL here for simplicity; swap to UUID for production.
        """
        return "SERIAL PRIMARY KEY"

    @staticmethod
    def json_type() -> str:
        """JSONB is faster and indexable in YugabyteDB."""
        return "JSONB"

    @staticmethod
    def bool_type() -> str:
        """Native BOOLEAN in YSQL, not TINYINT(1)."""
        return "BOOLEAN"
