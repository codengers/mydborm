# =============================================================================
# File        : dialects/postgres.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Version     : 1.4.0
# License     : MIT
# Description : Native PostgreSQL dialect (psycopg2).
#               PostgreSQL 12+ compatible. Very similar to YugabyteDB
#               but with postgres-specific defaults and port 5432.
# =============================================================================

from .yugabyte import YugabyteDialect


class PostgreSQLDialect(YugabyteDialect):
    """
    Native PostgreSQL dialect.

    Inherits all SQL generation from YugabyteDialect since both
    use the PostgreSQL wire protocol and psycopg2 driver.

    Key differences from YugabyteDB:
    - Default port: 5432
    - name: "postgres" / "postgresql"
    - SERIAL vs BIGSERIAL for PKs (configurable)
    - Full PostgreSQL feature support (not distributed)

    Usage:
        db.configure(
            dialect  = "postgres",
            host     = "127.0.0.1",
            port     = 5432,
            user     = "postgres",
            password = "yourpassword",
            database = "mydb",
        )
    """
    name         = "postgres"
    default_port = 5432

    @staticmethod
    def pk_definition() -> str:
        """
        PostgreSQL standard SERIAL primary key.
        Use BIGSERIAL for large tables (> 2 billion rows).
        """
        return "SERIAL PRIMARY KEY"

    @staticmethod
    def json_type() -> str:
        """
        JSONB is the recommended JSON type in PostgreSQL.
        Faster queries, supports indexing, binary storage.
        """
        return "JSONB"

    @staticmethod
    def bool_type() -> str:
        """Native BOOLEAN in PostgreSQL."""
        return "BOOLEAN"

    @staticmethod
    def create_table_sql(table: str, columns: list,
                         if_not_exists: bool = True) -> str:
        exist    = "IF NOT EXISTS " if if_not_exists else ""
        col_block = ",\n  ".join(columns)
        return (
            f'CREATE TABLE {exist}"{table}" (\n'
            f"  {col_block}\n"
            f");"
        )

    @staticmethod
    def insert_sql(table: str, columns: list) -> str:
        """PostgreSQL uses RETURNING for lastrowid equivalent."""
        cols = ", ".join(f'"{c}"' for c in columns)
        vals = ", ".join(["%s"] * len(columns))
        return (
            f'INSERT INTO "{table}" ({cols}) '
            f"VALUES ({vals}) RETURNING id;"
        )