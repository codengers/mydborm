# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_dialects.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.7.0
# License     : MIT
# Description : pytest tests for MySQL and YugabyteDB dialect classes —
#               DDL, DML, type overrides, and dialect registry.
# =============================================================================

import pytest
from mydborm.dialects import get_dialect
from mydborm.dialects.mysql    import MySQLDialect
from mydborm.dialects.yugabyte import YugabyteDialect
from mydborm.dialects.postgres import PostgreSQLDialect


# ------------------------------------------------------------------ #
#  Dialect registry                                                    #
# ------------------------------------------------------------------ #

def test_get_mysql_dialect():
    d = get_dialect("mysql")
    assert d is MySQLDialect


def test_get_yugabyte_dialect():
    d = get_dialect("yugabyte")
    assert d is YugabyteDialect


def test_get_postgres_alias():
    d = get_dialect("postgres")
    assert d is PostgreSQLDialect


def test_get_unknown_dialect_raises():
    with pytest.raises(ValueError, match="Unknown dialect"):
        get_dialect("oracle")


def test_dialect_names():
    assert MySQLDialect.name    == "mysql"
    assert YugabyteDialect.name == "yugabyte"


def test_dialect_ports():
    assert MySQLDialect.default_port    == 3306
    assert YugabyteDialect.default_port == 5433


# ------------------------------------------------------------------ #
#  MySQLDialect — DDL                                                  #
# ------------------------------------------------------------------ #

def test_mysql_create_table_if_not_exists():
    sql = MySQLDialect.create_table_sql(
        "users", ["id INT PRIMARY KEY", "name VARCHAR(100)"]
    )
    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert "`users`"                    in sql
    assert "InnoDB"                     in sql
    assert "utf8mb4"                    in sql


def test_mysql_create_table_without_exists():
    sql = MySQLDialect.create_table_sql(
        "users", ["id INT"], if_not_exists=False
    )
    assert "IF NOT EXISTS" not in sql
    assert "`users`"              in sql


def test_mysql_create_table_columns():
    sql = MySQLDialect.create_table_sql(
        "users",
        ["id INT PRIMARY KEY AUTO_INCREMENT",
         "name VARCHAR(100) NOT NULL"]
    )
    assert "id INT PRIMARY KEY AUTO_INCREMENT" in sql
    assert "name VARCHAR(100) NOT NULL"        in sql


def test_mysql_drop_table_if_exists():
    sql = MySQLDialect.drop_table_sql("users")
    assert "DROP TABLE IF EXISTS" in sql
    assert "`users`"              in sql


def test_mysql_drop_table_without_exists():
    sql = MySQLDialect.drop_table_sql("users", if_exists=False)
    assert "IF EXISTS" not in sql


def test_mysql_add_column():
    sql = MySQLDialect.add_column_sql("users", "phone", "VARCHAR(20)")
    assert "ALTER TABLE"  in sql
    assert "`users`"      in sql
    assert "`phone`"      in sql
    assert "VARCHAR(20)"  in sql


def test_mysql_drop_column():
    sql = MySQLDialect.drop_column_sql("users", "phone")
    assert "DROP COLUMN" in sql
    assert "`users`"     in sql
    assert "`phone`"     in sql


# ------------------------------------------------------------------ #
#  MySQLDialect — DML                                                  #
# ------------------------------------------------------------------ #

def test_mysql_insert_sql():
    sql = MySQLDialect.insert_sql("users", ["name", "email"])
    assert "INSERT INTO `users`" in sql
    assert "name"                in sql
    assert "email"               in sql
    assert "%s"                  in sql


def test_mysql_select_sql_basic():
    sql = MySQLDialect.select_sql("users")
    assert "SELECT * FROM `users`" in sql


def test_mysql_select_sql_with_where():
    sql = MySQLDialect.select_sql("users", where="active = %s")
    assert "WHERE active = %s" in sql


def test_mysql_select_sql_with_order():
    sql = MySQLDialect.select_sql("users", order_by="name")
    assert "ORDER BY name" in sql


def test_mysql_select_sql_with_limit():
    sql = MySQLDialect.select_sql("users", limit=10)
    assert "LIMIT 10" in sql


def test_mysql_update_sql():
    sql = MySQLDialect.update_sql(
        "users", "name = %s", "id = %s"
    )
    assert "UPDATE `users`"  in sql
    assert "SET name = %s"   in sql
    assert "WHERE id = %s"   in sql


def test_mysql_delete_sql():
    sql = MySQLDialect.delete_sql("users", "id = %s")
    assert "DELETE FROM `users`" in sql
    assert "WHERE id = %s"       in sql


# ------------------------------------------------------------------ #
#  MySQLDialect — Type overrides                                       #
# ------------------------------------------------------------------ #

def test_mysql_pk_definition():
    pk = MySQLDialect.pk_definition()
    assert "AUTO_INCREMENT"  in pk
    assert "PRIMARY KEY"     in pk


def test_mysql_json_type():
    assert MySQLDialect.json_type() == "JSON"


def test_mysql_bool_type():
    assert MySQLDialect.bool_type() == "TINYINT(1)"


# ------------------------------------------------------------------ #
#  YugabyteDialect — DDL                                               #
# ------------------------------------------------------------------ #

def test_yugabyte_create_table_if_not_exists():
    sql = YugabyteDialect.create_table_sql(
        "users", ["id SERIAL PRIMARY KEY", "name VARCHAR(100)"]
    )
    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert '"users"'                    in sql
    assert "InnoDB"                     not in sql


def test_yugabyte_create_table_without_exists():
    sql = YugabyteDialect.create_table_sql(
        "users", ["id SERIAL"], if_not_exists=False
    )
    assert "IF NOT EXISTS" not in sql
    assert '"users"'              in sql


def test_yugabyte_drop_table():
    sql = YugabyteDialect.drop_table_sql("users")
    assert "DROP TABLE IF EXISTS" in sql
    assert '"users"'              in sql


def test_yugabyte_add_column():
    sql = YugabyteDialect.add_column_sql("users", "phone", "VARCHAR(20)")
    assert "ALTER TABLE"  in sql
    assert '"users"'      in sql
    assert '"phone"'      in sql
    assert "VARCHAR(20)"  in sql


def test_yugabyte_drop_column():
    sql = YugabyteDialect.drop_column_sql("users", "phone")
    assert "DROP COLUMN" in sql
    assert '"users"'     in sql
    assert '"phone"'     in sql


# ------------------------------------------------------------------ #
#  YugabyteDialect — DML                                               #
# ------------------------------------------------------------------ #

def test_yugabyte_insert_sql():
    sql = YugabyteDialect.insert_sql("users", ["name", "email"])
    assert 'INSERT INTO "users"' in sql
    assert "RETURNING id"        in sql
    assert "%s"                  in sql


def test_yugabyte_select_sql_basic():
    sql = YugabyteDialect.select_sql("users")
    assert 'SELECT * FROM "users"' in sql


def test_yugabyte_select_with_where():
    sql = YugabyteDialect.select_sql("users", where="active = %s")
    assert "WHERE active = %s" in sql


def test_yugabyte_select_with_limit():
    sql = YugabyteDialect.select_sql("users", limit=5)
    assert "LIMIT 5" in sql


def test_yugabyte_update_sql():
    sql = YugabyteDialect.update_sql("users", "name = %s", "id = %s")
    assert 'UPDATE "users"' in sql
    assert "SET name = %s"  in sql
    assert "WHERE id = %s"  in sql


def test_yugabyte_delete_sql():
    sql = YugabyteDialect.delete_sql("users", "id = %s")
    assert 'DELETE FROM "users"' in sql
    assert "WHERE id = %s"       in sql


# ------------------------------------------------------------------ #
#  YugabyteDialect — Type overrides                                    #
# ------------------------------------------------------------------ #

def test_yugabyte_pk_definition():
    pk = YugabyteDialect.pk_definition()
    assert "SERIAL"      in pk
    assert "PRIMARY KEY" in pk


def test_yugabyte_json_type():
    assert YugabyteDialect.json_type() == "JSONB"


def test_yugabyte_bool_type():
    assert YugabyteDialect.bool_type() == "BOOLEAN"


# ------------------------------------------------------------------ #
#  Dialect differences                                                 #
# ------------------------------------------------------------------ #

def test_dialects_differ_on_pk():
    assert MySQLDialect.pk_definition() != YugabyteDialect.pk_definition()


def test_dialects_differ_on_json():
    assert MySQLDialect.json_type() != YugabyteDialect.json_type()


def test_dialects_differ_on_bool():
    assert MySQLDialect.bool_type() != YugabyteDialect.bool_type()


def test_mysql_uses_backticks():
    sql = MySQLDialect.select_sql("users")
    assert "`users`" in sql
    assert '"users"' not in sql


def test_yugabyte_uses_double_quotes():
    sql = YugabyteDialect.select_sql("users")
    assert '"users"' in sql
    assert "`users`" not in sql