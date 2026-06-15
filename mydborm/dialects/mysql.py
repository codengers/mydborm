# =============================================================================
# File        : dialects/mysql.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : MySQL-specific SQL dialect. Generates DDL and DML
#               using backtick quoting, InnoDB engine, utf8mb4 charset
#               AUTO_INCREMENT primary keys, TINYINT(1) for booleans
#               and JSON column type.
# =============================================================================

# =============================================================================
# File        : dialects/mysql.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : MySQL-specific SQL dialect. Generates DDL and DML
#               statements using backtick quoting, InnoDB engine,
#               utf8mb4 charset, AUTO_INCREMENT primary keys,
#               TINYINT(1) for booleans, and JSON column type.
# =============================================================================

"""
dialects/mysql.py — MySQL-specific SQL generation.
"""


class MySQLDialect:
    name = "mysql"
    param_style = "%s"          # mysql-connector uses %s
    default_port = 3306

    # ── DDL ──────────────────────────────────────────────────────── #

    @staticmethod
    def create_table_sql(table: str, columns: list[str],
                         if_not_exists: bool = True) -> str:
        exist = "IF NOT EXISTS " if if_not_exists else ""
        col_block = ",\n  ".join(columns)
        return (
            f"CREATE TABLE {exist}`{table}` (\n"
            f"  {col_block}\n"
            f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
        )

    @staticmethod
    def drop_table_sql(table: str, if_exists: bool = True) -> str:
        exist = "IF EXISTS " if if_exists else ""
        return f"DROP TABLE {exist}`{table}`;"

    @staticmethod
    def add_column_sql(table: str, column: str, definition: str) -> str:
        return f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition};"

    @staticmethod
    def drop_column_sql(table: str, column: str) -> str:
        return f"ALTER TABLE `{table}` DROP COLUMN `{column}`;"

    # ── DML ──────────────────────────────────────────────────────── #

    @staticmethod
    def insert_sql(table: str, columns: list[str]) -> str:
        cols = ", ".join(f"`{c}`" for c in columns)
        vals = ", ".join(["%s"] * len(columns))
        return f"INSERT INTO `{table}` ({cols}) VALUES ({vals});"

    @staticmethod
    def select_sql(table: str, where: str = None,
                   order_by: str = None, limit: int = None) -> str:
        sql = f"SELECT * FROM `{table}`"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        return sql + ";"

    @staticmethod
    def update_sql(table: str, set_clause: str, where: str) -> str:
        return f"UPDATE `{table}` SET {set_clause} WHERE {where};"

    @staticmethod
    def delete_sql(table: str, where: str) -> str:
        return f"DELETE FROM `{table}` WHERE {where};"

    # ── Type overrides ────────────────────────────────────────────── #

    @staticmethod
    def pk_definition() -> str:
        """Primary key definition for MySQL."""
        return "INT NOT NULL AUTO_INCREMENT PRIMARY KEY"

    @staticmethod
    def json_type() -> str:
        return "JSON"

    @staticmethod
    def bool_type() -> str:
        return "TINYINT(1)"
