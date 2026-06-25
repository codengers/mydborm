# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_postgresql.py
# Project     : mydborm
# Version     : 1.4.0
# License     : MIT
# Description : Tests for PostgreSQL dialect — SQL generation + live DB tests
#               (skipped if PostgreSQL is not running on port 5432)
# =============================================================================

import os
import socket
import pytest
from mydborm.dialects.postgres import PostgreSQLDialect
from mydborm.dialects.yugabyte import YugabyteDialect
from mydborm.dialects         import get_dialect


# ------------------------------------------------------------------ #
#  Availability check                                                  #
# ------------------------------------------------------------------ #

def _pg_available():
    try:
        s = socket.create_connection(("127.0.0.1", 5432), timeout=2)
        s.close()
        return True
    except OSError:
        return False

pg_skip = pytest.mark.skipif(not _pg_available(), reason="PostgreSQL not running on port 5432")


# ------------------------------------------------------------------ #
#  Dialect registration                                                #
# ------------------------------------------------------------------ #

def test_get_dialect_postgres():
    assert get_dialect("postgres") is PostgreSQLDialect


def test_get_dialect_postgresql():
    assert get_dialect("postgresql") is PostgreSQLDialect


def test_postgres_not_yugabyte():
    assert PostgreSQLDialect is not YugabyteDialect


def test_postgres_name():
    assert PostgreSQLDialect.name == "postgres"


def test_postgres_default_port():
    assert PostgreSQLDialect.default_port == 5432


def test_yugabyte_default_port_unchanged():
    assert YugabyteDialect.default_port == 5433


# ------------------------------------------------------------------ #
#  SQL generation                                                      #
# ------------------------------------------------------------------ #

def test_postgres_create_table():
    sql = PostgreSQLDialect.create_table_sql(
        "users", ["id SERIAL PRIMARY KEY", "name VARCHAR(100) NOT NULL"]
    )
    assert 'CREATE TABLE IF NOT EXISTS "users"' in sql
    assert "SERIAL PRIMARY KEY" in sql


def test_postgres_create_table_no_exists():
    sql = PostgreSQLDialect.create_table_sql(
        "users", ["id SERIAL PRIMARY KEY"], if_not_exists=False
    )
    assert "IF NOT EXISTS" not in sql


def test_postgres_drop_table():
    sql = PostgreSQLDialect.drop_table_sql("users")
    assert 'DROP TABLE IF EXISTS "users"' in sql


def test_postgres_add_column():
    sql = PostgreSQLDialect.add_column_sql("users", "phone", "VARCHAR(20)")
    assert '"phone"' in sql
    assert "ALTER TABLE" in sql


def test_postgres_drop_column():
    sql = PostgreSQLDialect.drop_column_sql("users", "phone")
    assert "DROP COLUMN" in sql
    assert '"phone"' in sql


def test_postgres_insert_returning():
    sql = PostgreSQLDialect.insert_sql("users", ["name", "email"])
    assert 'INSERT INTO "users"' in sql
    assert "RETURNING id" in sql
    assert "%s" in sql


def test_postgres_select():
    sql = PostgreSQLDialect.select_sql("users")
    assert 'SELECT * FROM "users"' in sql


def test_postgres_select_where():
    sql = PostgreSQLDialect.select_sql("users", where="active = %s")
    assert "WHERE active = %s" in sql


def test_postgres_select_limit():
    sql = PostgreSQLDialect.select_sql("users", limit=10)
    assert "LIMIT 10" in sql


def test_postgres_update():
    sql = PostgreSQLDialect.update_sql("users", "name = %s", "id = %s")
    assert 'UPDATE "users"' in sql
    assert "SET name = %s" in sql


def test_postgres_delete():
    sql = PostgreSQLDialect.delete_sql("users", "id = %s")
    assert 'DELETE FROM "users"' in sql


def test_postgres_pk_definition():
    assert PostgreSQLDialect.pk_definition() == "SERIAL PRIMARY KEY"


def test_postgres_json_type():
    assert PostgreSQLDialect.json_type() == "JSONB"


def test_postgres_bool_type():
    assert PostgreSQLDialect.bool_type() == "BOOLEAN"


def test_postgres_uses_double_quotes():
    sql = PostgreSQLDialect.select_sql("products")
    assert '"products"' in sql
    assert "`products`" not in sql


def test_postgres_same_sql_as_yugabyte():
    """PostgreSQL and YugabyteDB should generate identical SQL."""
    tables = ["users", "orders", "products"]
    for t in tables:
        assert (PostgreSQLDialect.select_sql(t) ==
                YugabyteDialect.select_sql(t))
        assert (PostgreSQLDialect.drop_table_sql(t) ==
                YugabyteDialect.drop_table_sql(t))
        assert (PostgreSQLDialect.delete_sql(t, "id = %s") ==
                YugabyteDialect.delete_sql(t, "id = %s"))


# ------------------------------------------------------------------ #
#  Live PostgreSQL tests (skipped if not running)                      #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def pg_db():
    if not _pg_available():
        pytest.skip("PostgreSQL not running on port 5432")
    from mydborm import db, BaseModel, IntField, StrField, BoolField
    db.configure(
        dialect  = "postgres",
        host     = "127.0.0.1",
        port     = 5432,
        user     = os.environ.get("PG_USER", "postgres"),
        password = os.environ.get("PG_PASSWORD", "postgres"),
        database = os.environ.get("PG_DATABASE", "postgres"),
    )
    yield db
    db.close()
    # Restore MySQL
    db.configure(
        dialect  = "mysql",
        host     = "127.0.0.1",
        port     = 3307,
        user     = "root",
        password = os.environ.get("DB_PASSWORD", "root"),
        database = "testdb",
        charset  = "utf8mb4",
    )


@pg_skip
def test_pg_connect(pg_db):
    assert pg_db.ping() is True


@pg_skip
def test_pg_dialect_name(pg_db):
    assert pg_db.dialect == "postgres"


@pg_skip
def test_pg_create_table(pg_db):
    from mydborm import BaseModel, IntField, StrField
    class PGUser(BaseModel):
        __tablename__ = "pg_test_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=50, nullable=False)

    with pg_db.connect() as conn:
        conn.cursor().execute('DROP TABLE IF EXISTS "pg_test_users"')
    PGUser.create_table()
    uid = PGUser.create(username="alice")
    assert uid > 0
    user = PGUser.get(id=uid)
    assert user["username"] == "alice"
    with pg_db.connect() as conn:
        conn.cursor().execute('DROP TABLE IF EXISTS "pg_test_users"')


@pg_skip
def test_pg_crud(pg_db):
    from mydborm import BaseModel, IntField, StrField, BoolField
    class PGProduct(BaseModel):
        __tablename__ = "pg_test_products"
        id     = IntField(primary_key=True)
        name   = StrField(max_length=100, nullable=False)
        active = BoolField(default=True)

    with pg_db.connect() as conn:
        conn.cursor().execute('DROP TABLE IF EXISTS "pg_test_products"')
    PGProduct.create_table()

    pid = PGProduct.create(name="Widget", active=True)
    p   = PGProduct.get(id=pid)
    assert p["name"] == "Widget"

    PGProduct.update({"name": "Updated Widget"}, id=pid)
    p2 = PGProduct.get(id=pid)
    assert p2["name"] == "Updated Widget"

    PGProduct.delete(id=pid)
    assert PGProduct.get(id=pid) is None

    with pg_db.connect() as conn:
        conn.cursor().execute('DROP TABLE IF EXISTS "pg_test_products"')