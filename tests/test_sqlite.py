# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_sqlite.py
# Project     : mydborm
# License     : MIT
# Description : Tests for the SQLite dialect — SQL generation + live CRUD,
#               query-builder, composite key, index, and FK-cascade tests.
#               SQLite is stdlib (no external service), so unlike
#               test_postgresql.py / test_yugabyte.py these tests are never
#               skipped.
# =============================================================================

import os
import tempfile

import pytest
from typer.testing import CliRunner

from mydborm import (
    BaseModel,
    BoolField,
    FloatField,
    ForeignKeyField,
    IntField,
    StrField,
    db,
)
from mydborm.cli import cli
from mydborm.dialects import get_dialect
from mydborm.dialects.mysql import MySQLDialect
from mydborm.dialects.sqlite import SQLiteDialect

# ------------------------------------------------------------------ #
#  Dialect registration                                                #
# ------------------------------------------------------------------ #

def test_get_dialect_sqlite():
    assert get_dialect("sqlite") is SQLiteDialect


def test_sqlite_name():
    assert SQLiteDialect.name == "sqlite"


def test_sqlite_param_style():
    assert SQLiteDialect.param_style == "?"


def test_sqlite_default_port_is_none():
    assert SQLiteDialect.default_port is None


def test_sqlite_inherits_mysql_dialect():
    assert issubclass(SQLiteDialect, MySQLDialect)


def test_sqlite_pk_definition():
    assert SQLiteDialect.pk_definition() == "INTEGER PRIMARY KEY AUTOINCREMENT"


def test_sqlite_json_type():
    assert SQLiteDialect.json_type() == "TEXT"


def test_sqlite_bool_type():
    assert SQLiteDialect.bool_type() == "INTEGER"


def test_sqlite_create_table_sql_has_no_engine_clause():
    sql = SQLiteDialect.create_table_sql("t", ["id INTEGER"])
    assert "ENGINE" not in sql
    assert "CHARSET" not in sql


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class SLProduct(BaseModel):
    __tablename__ = "sl_products"
    id       = IntField(primary_key=True)
    sku      = StrField(max_length=20,  nullable=False, unique=True)
    name     = StrField(max_length=100, nullable=False)
    category = StrField(max_length=50,  nullable=True, index=True)
    price    = FloatField(nullable=False)
    active   = BoolField(default=True)


class SLOrderItem(BaseModel):
    __tablename__ = "sl_order_items"
    __pk__        = ("order_id", "product_id")
    order_id   = IntField(nullable=False)
    product_id = IntField(nullable=False)
    quantity   = IntField(nullable=False, default=1)


class SLAuthor(BaseModel):
    __tablename__ = "sl_authors"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


class SLBook(BaseModel):
    __tablename__ = "sl_books"
    id        = IntField(primary_key=True)
    title     = StrField(max_length=200, nullable=False)
    author_id = ForeignKeyField(to="SLAuthor", nullable=False, on_delete="CASCADE")


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # sqlite3 creates the file itself on first connect

    db.configure(dialect="sqlite", database=path)
    SLAuthor.create_table()
    SLBook.create_table()
    SLProduct.create_table()
    SLOrderItem.create_table()
    yield path
    db.close()
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(autouse=True)
def clean_tables():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM sl_books")
        cur.execute("DELETE FROM sl_authors")
        cur.execute("DELETE FROM sl_products")
        cur.execute("DELETE FROM sl_order_items")
    yield


# ------------------------------------------------------------------ #
#  Connection — file path and :memory:                                 #
# ------------------------------------------------------------------ #

def test_memory_connection_crud_roundtrip():
    class Scratch(BaseModel):
        __tablename__ = "sl_scratch"
        id   = IntField(primary_key=True)
        name = StrField(max_length=50, nullable=False)

    prev_config = db._config
    try:
        db.configure(dialect="sqlite", database=":memory:")
        Scratch.create_table()
        pid = Scratch.create(name="hello")
        assert pid == 1
        assert Scratch.get(id=pid)["name"] == "hello"
        db.close()
    finally:
        db._config = prev_config
        db.close()


# ------------------------------------------------------------------ #
#  CRUD                                                                #
# ------------------------------------------------------------------ #

def test_create_and_get():
    pid = SLProduct.create(sku="W1", name="Widget", category="tools", price=9.99)
    assert pid == 1
    row = SLProduct.get(id=pid)
    assert row["name"]   == "Widget"
    assert row["price"]  == 9.99
    assert row["active"] in (True, 1)


def test_update():
    pid = SLProduct.create(sku="W2", name="Gadget", category="tools", price=5.0)
    SLProduct.query().where("id", pid).update(price=7.5)
    assert SLProduct.get(id=pid)["price"] == 7.5


def test_delete():
    pid = SLProduct.create(sku="W3", name="Doohickey", category="tools", price=1.0)
    SLProduct.query().where("id", pid).delete()
    assert SLProduct.get(id=pid) is None


def test_count_and_exists():
    SLProduct.create(sku="W4", name="A", category="x", price=1.0)
    SLProduct.create(sku="W5", name="B", category="x", price=2.0)
    assert SLProduct.query().where("category", "x").count() == 2
    assert SLProduct.query().where("category", "x").exists() is True


# ------------------------------------------------------------------ #
#  Query builder                                                       #
# ------------------------------------------------------------------ #

def test_where_order_by_limit():
    SLProduct.create(sku="A1", name="Alpha", category="cat", price=3.0)
    SLProduct.create(sku="A2", name="Beta",  category="cat", price=1.0)
    SLProduct.create(sku="A3", name="Gamma", category="cat", price=2.0)

    rows = (SLProduct.query()
            .where("category", "cat")
            .order_by("price")
            .limit(2)
            .all())
    assert [r["name"] for r in rows] == ["Beta", "Gamma"]


def test_group_by_having():
    SLProduct.create(sku="G1", name="A", category="grp", price=10.0)
    SLProduct.create(sku="G2", name="B", category="grp", price=20.0)

    rows = (SLProduct.query()
            .select("category", "COUNT(*) as cnt")
            .group_by("category")
            .having("COUNT(*) > %s", 1)
            .all())
    assert any(r["cnt"] == 2 for r in rows)


def test_inner_join():
    author_id = SLAuthor.create(name="Ada")
    SLBook.create(title="Book One", author_id=author_id)
    SLBook.create(title="Book Two", author_id=author_id)

    rows = (SLBook.query()
            .inner_join("sl_authors", "sl_books.author_id = sl_authors.id")
            .where("sl_authors.name", "Ada")
            .all())
    assert len(rows) == 2


# ------------------------------------------------------------------ #
#  Composite primary key                                               #
# ------------------------------------------------------------------ #

def test_composite_pk_create_and_get():
    SLOrderItem.create(order_id=1, product_id=1, quantity=3)
    row = SLOrderItem.get(order_id=1, product_id=1)
    assert row["quantity"] == 3


# ------------------------------------------------------------------ #
#  Index management                                                    #
# ------------------------------------------------------------------ #

def test_auto_index_on_indexed_field():
    indexes = SLProduct.list_indexes()
    names   = [i["name"] for i in indexes]
    assert any("category" in n for n in names)


def test_create_and_drop_index():
    idx_name = SLProduct.create_index(["name"], name="idx_sl_products_name_test")
    names = [i["name"] for i in SLProduct.list_indexes()]
    assert idx_name in names
    SLProduct.drop_index(idx_name)
    names = [i["name"] for i in SLProduct.list_indexes()]
    assert idx_name not in names


# ------------------------------------------------------------------ #
#  Foreign keys + cascade                                              #
# ------------------------------------------------------------------ #

def test_fk_cascade_delete():
    author_id = SLAuthor.create(name="Grace")
    SLBook.create(title="Cascade Test", author_id=author_id)

    SLAuthor.query().where("id", author_id).delete()

    remaining = SLBook.query().where("author_id", author_id).all()
    assert remaining == []


# ------------------------------------------------------------------ #
#  db.table_exists / db.list_tables                                    #
# ------------------------------------------------------------------ #

def test_table_exists():
    assert db.table_exists("sl_products") is True
    assert db.table_exists("sl_nonexistent_table") is False


def test_list_tables():
    tables = db.list_tables()
    assert "sl_products" in tables
    assert "sl_authors" in tables


# ------------------------------------------------------------------ #
#  CLI                                                                 #
# ------------------------------------------------------------------ #

runner = CliRunner()


def test_cli_ping_sqlite(setup_db):
    # CliRunner invokes the CLI in-process, so it reconfigures the shared
    # `db` singleton — restore it to the module's fixture path afterward so
    # the autouse clean_tables fixture doesn't hit a deleted temp dir.
    #
    # Also: db.configure() does NOT invalidate an already-open cached
    # connection, so the module's live connection must be closed first —
    # otherwise db.connect() silently keeps reusing it against the *old*
    # database file instead of the new path being configured here.
    db.close()
    try:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cli_ping.db")
            result = runner.invoke(cli, [
                "ping", "--dialect", "sqlite", "--database", path,
            ])
            assert result.exit_code == 0
            assert "Connected" in result.stdout
    finally:
        db.close()
        db.configure(dialect="sqlite", database=setup_db)


def test_cli_inspect_sqlite(setup_db):
    db.close()
    try:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cli_inspect.db")
            db.configure(dialect="sqlite", database=path)
            SLProduct.create_table()
            db.close()

            result = runner.invoke(cli, [
                "inspect", "--dialect", "sqlite", "--database", path,
            ])
            assert result.exit_code == 0
            assert "sl_products" in result.stdout
    finally:
        db.close()
        db.configure(dialect="sqlite", database=setup_db)
