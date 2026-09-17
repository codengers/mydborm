import os
# =============================================================================
# File        : tests/test_check_constraints.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Tests for CHECK constraints — Field(check=...) for a
#               single-column constraint, __checks__ for table-level
#               (multi-column) constraints. MySQL + SQLite always run;
#               YugabyteDB is skipped if unavailable.
# =============================================================================

import socket

import pytest
from mydborm import db, BaseModel, IntField, StrField, FloatField
from mydborm.db import ConnectionManager
from tests.test_db_migration import YB_CONFIG


def _is_available(port: int) -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=2)
        s.close()
        return True
    except OSError:
        return False


yb_skip = pytest.mark.skipif(not _is_available(5433), reason="YugabyteDB not running on port 5433")


class CKProduct(BaseModel):
    __tablename__ = "ck_products"
    __checks__    = ["start_qty <= max_qty"]
    id        = IntField(primary_key=True)
    name      = StrField(max_length=50, nullable=False)
    price     = FloatField(nullable=False, check="price > 0")
    start_qty = IntField(nullable=False, default=0)
    max_qty   = IntField(nullable=False, default=100)


# ------------------------------------------------------------------ #
#  MySQL                                                               #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def mysql_db():
    db.configure(
        dialect="mysql", host="127.0.0.1", port=3307,
        user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb",
    )
    CKProduct.drop_table()
    CKProduct.create_table()
    yield
    CKProduct.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean_mysql(mysql_db):
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM ck_products")
    yield


def test_field_check_definition_includes_check_clause():
    sql_def = CKProduct._fields["price"].to_sql_def("mysql")
    assert "CHECK (price > 0)" in sql_def


def test_valid_row_is_accepted():
    pid = CKProduct.create(name="Widget", price=9.99, start_qty=1, max_qty=10)
    assert CKProduct.get(id=pid)["name"] == "Widget"


def test_field_level_check_rejects_violation():
    with pytest.raises(Exception):
        CKProduct.create(name="Bad", price=-5, start_qty=1, max_qty=10)


def test_table_level_check_rejects_violation():
    with pytest.raises(Exception):
        CKProduct.create(name="Bad", price=5, start_qty=50, max_qty=10)


# ------------------------------------------------------------------ #
#  SQLite                                                              #
# ------------------------------------------------------------------ #

def test_sqlite_field_level_check_rejects_violation(monkeypatch):
    mgr = ConnectionManager()
    mgr.configure(dialect="sqlite", database=":memory:")
    monkeypatch.setattr("mydborm.model.db", mgr)

    class SLCKProduct(BaseModel):
        __tablename__ = "slck_products"
        id    = IntField(primary_key=True)
        price = FloatField(nullable=False, check="price > 0")

    SLCKProduct.create_table()
    SLCKProduct.create(price=9.99)
    with pytest.raises(Exception):
        SLCKProduct.create(price=-1)
    mgr.close()


def test_sqlite_table_level_check_rejects_violation(monkeypatch):
    mgr = ConnectionManager()
    mgr.configure(dialect="sqlite", database=":memory:")
    monkeypatch.setattr("mydborm.model.db", mgr)

    class SLCKOrder(BaseModel):
        __tablename__ = "slck_orders"
        __checks__    = ["start_qty <= max_qty"]
        id        = IntField(primary_key=True)
        start_qty = IntField(nullable=False, default=0)
        max_qty   = IntField(nullable=False, default=100)

    SLCKOrder.create_table()
    SLCKOrder.create(start_qty=1, max_qty=10)
    with pytest.raises(Exception):
        SLCKOrder.create(start_qty=50, max_qty=10)
    mgr.close()


# ------------------------------------------------------------------ #
#  YugabyteDB                                                          #
# ------------------------------------------------------------------ #

@yb_skip
def test_yugabyte_check_constraints(monkeypatch):
    mgr = ConnectionManager()
    mgr.configure(**YB_CONFIG)
    monkeypatch.setattr("mydborm.model.db", mgr)

    class YBCKProduct(BaseModel):
        __tablename__ = "ybck_products"
        __checks__    = ["start_qty <= max_qty"]
        id        = IntField(primary_key=True)
        price     = FloatField(nullable=False, check="price > 0")
        start_qty = IntField(nullable=False, default=0)
        max_qty   = IntField(nullable=False, default=100)

    YBCKProduct.drop_table()
    YBCKProduct.create_table()
    YBCKProduct.create(price=9.99, start_qty=1, max_qty=10)
    with pytest.raises(Exception):
        YBCKProduct.create(price=-5, start_qty=1, max_qty=10)
    with pytest.raises(Exception):
        YBCKProduct.create(price=5, start_qty=50, max_qty=10)
    YBCKProduct.drop_table()
    mgr.close()
