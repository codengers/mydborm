# -*- coding: utf-8 -*-
import pytest
from mydborm.dialects import get_dialect
from mydborm.dialects.mysql import MySQLDialect
from mydborm.dialects.yugabyte import YugabyteDialect

def test_get_mysql_dialect():
    assert get_dialect("mysql") is MySQLDialect

def test_get_yugabyte_dialect():
    assert get_dialect("yugabyte") is YugabyteDialect

def test_get_postgres_alias():
    assert get_dialect("postgres") is YugabyteDialect

def test_get_unknown_dialect_raises():
    with pytest.raises(ValueError, match="Unknown dialect"):
        get_dialect("oracle")

def test_dialect_names():
    assert MySQLDialect.name == "mysql"
    assert YugabyteDialect.name == "yugabyte"

def test_dialect_ports():
    assert MySQLDialect.default_port == 3306
    assert YugabyteDialect.default_port == 5433

def test_mysql_create_table():
    sql = MySQLDialect.create_table_sql("users", ["id INT PRIMARY KEY"])
    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert "`users`" in sql
    assert "InnoDB" in sql

def test_mysql_create_table_no_exists():
    sql = MySQLDialect.create_table_sql("users", ["id INT"], if_not_exists=False)
    assert "IF NOT EXISTS" not in sql

def test_mysql_drop_table():
    sql = MySQLDialect.drop_table_sql("users")
    assert "DROP TABLE IF EXISTS" in sql
    assert "`users`" in sql

def test_mysql_drop_table_no_exists():
    sql = MySQLDialect.drop_table_sql("users", if_exists=False)
    assert "IF EXISTS" not in sql

def test_mysql_add_column():
    sql = MySQLDialect.add_column_sql("users", "phone", "VARCHAR(20)")
    assert "ALTER TABLE" in sql
    assert "`phone`" in sql

def test_mysql_drop_column():
    sql = MySQLDialect.drop_column_sql("users", "phone")
    assert "DROP COLUMN" in sql
    assert "`phone`" in sql

def test_mysql_insert_sql():
    sql = MySQLDialect.insert_sql("users", ["name", "email"])
    assert "INSERT INTO `users`" in sql
    assert "%s" in sql

def test_mysql_select_basic():
    sql = MySQLDialect.select_sql("users")
    assert "SELECT * FROM `users`" in sql

def test_mysql_select_where():
    sql = MySQLDialect.select_sql("users", where="active = %s")
    assert "WHERE active = %s" in sql

def test_mysql_select_order():
    sql = MySQLDialect.select_sql("users", order_by="name")
    assert "ORDER BY name" in sql

def test_mysql_select_limit():
    sql = MySQLDialect.select_sql("users", limit=10)
    assert "LIMIT 10" in sql

def test_mysql_update_sql():
    sql = MySQLDialect.update_sql("users", "name = %s", "id = %s")
    assert "UPDATE `users`" in sql
    assert "SET name = %s" in sql

def test_mysql_delete_sql():
    sql = MySQLDialect.delete_sql("users", "id = %s")
    assert "DELETE FROM `users`" in sql

def test_mysql_pk_definition():
    assert "AUTO_INCREMENT" in MySQLDialect.pk_definition()
    assert "PRIMARY KEY" in MySQLDialect.pk_definition()

def test_mysql_json_type():
    assert MySQLDialect.json_type() == "JSON"

def test_mysql_bool_type():
    assert MySQLDialect.bool_type() == "TINYINT(1)"

def test_yugabyte_create_table():
    sql = YugabyteDialect.create_table_sql("users", ["id SERIAL PRIMARY KEY"])
    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert '"users"' in sql
    assert "InnoDB" not in sql

def test_yugabyte_drop_table():
    sql = YugabyteDialect.drop_table_sql("users")
    assert '"users"' in sql

def test_yugabyte_add_column():
    sql = YugabyteDialect.add_column_sql("users", "phone", "VARCHAR(20)")
    assert '"phone"' in sql

def test_yugabyte_drop_column():
    sql = YugabyteDialect.drop_column_sql("users", "phone")
    assert "DROP COLUMN" in sql

def test_yugabyte_insert_sql():
    sql = YugabyteDialect.insert_sql("users", ["name"])
    assert "RETURNING id" in sql

def test_yugabyte_select_basic():
    sql = YugabyteDialect.select_sql("users")
    assert 'SELECT * FROM "users"' in sql

def test_yugabyte_update_sql():
    sql = YugabyteDialect.update_sql("users", "name = %s", "id = %s")
    assert 'UPDATE "users"' in sql

def test_yugabyte_delete_sql():
    sql = YugabyteDialect.delete_sql("users", "id = %s")
    assert 'DELETE FROM "users"' in sql

def test_yugabyte_pk_definition():
    assert "SERIAL" in YugabyteDialect.pk_definition()
    assert "PRIMARY KEY" in YugabyteDialect.pk_definition()

def test_yugabyte_json_type():
    assert YugabyteDialect.json_type() == "JSONB"

def test_yugabyte_bool_type():
    assert YugabyteDialect.bool_type() == "BOOLEAN"

def test_dialects_differ_pk():
    assert MySQLDialect.pk_definition() != YugabyteDialect.pk_definition()

def test_dialects_differ_json():
    assert MySQLDialect.json_type() != YugabyteDialect.json_type()

def test_dialects_differ_bool():
    assert MySQLDialect.bool_type() != YugabyteDialect.bool_type()

def test_mysql_uses_backticks():
    assert "`users`" in MySQLDialect.select_sql("users")

def test_yugabyte_uses_double_quotes():
    assert '"users"' in YugabyteDialect.select_sql("users")
