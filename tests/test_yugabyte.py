# =============================================================================
# File        : tests/test_yugabyte.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.4.0
# License     : MIT
# Description : Integration tests for YugabyteDB (YSQL) dialect.
#               Tests SERIAL PK, BOOLEAN, JSONB, double-quote identifiers,
#               RETURNING id on INSERT, and full CRUD operations.
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm.fields import JSONField


# ------------------------------------------------------------------ #
#  YugabyteDB models                                                   #
# ------------------------------------------------------------------ #

class YBProduct(BaseModel):
    __tablename__ = "yb_products"
    id      = IntField(primary_key=True)
    name    = StrField(max_length=100, nullable=False)
    price   = FloatField(nullable=False)
    active  = BoolField(default=True)


class YBOrder(BaseModel):
    __tablename__ = "yb_orders"
    id         = IntField(primary_key=True)
    product_id = IntField(nullable=False)
    qty        = IntField(nullable=False)
    shipped    = BoolField(default=False)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_yb():
    db.configure(
        dialect  = "yugabyte",
        host     = "127.0.0.1",
        port     = 5433,
        user     = "yugabyte",
        password = os.environ.get("YB_PASSWORD", "yugabyte"),
        database = "yugabyte",
    )
    YBProduct.create_table()
    YBOrder.create_table()
    yield
    YBOrder.drop_table()
    YBProduct.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean_tables():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute('DELETE FROM "yb_orders"')
        cur.execute('DELETE FROM "yb_products"')
    yield


# ------------------------------------------------------------------ #
#  Dialect verification                                                #
# ------------------------------------------------------------------ #

def test_dialect_is_yugabyte():
    assert db.dialect == "yugabyte"


def test_ping():
    assert db.ping() is True


def test_tables_exist():
    tables = db.list_tables()
    assert "yb_products" in tables
    assert "yb_orders"   in tables


# ------------------------------------------------------------------ #
#  Field types                                                         #
# ------------------------------------------------------------------ #

def test_bool_field_sql_type():
    f = BoolField(default=True)
    f.name = "active"
    assert f.to_sql_def("yugabyte") == "BOOLEAN DEFAULT TRUE"

def test_bool_field_sql_type_no_default():
    f = BoolField()
    f.name = "active"
    assert f.to_sql_def("yugabyte") == "BOOLEAN"

def test_bool_field_mysql_sql_type():
    f = BoolField(default=True)
    f.name = "active"
    assert f.to_sql_def("mysql") == "TINYINT(1) DEFAULT 1"


def test_int_field_pk_serial():
    f = IntField(primary_key=True)
    f.name = "id"
    assert "SERIAL" in f.to_sql_def("yugabyte")


def test_bool_returns_native_boolean():
    pid = YBProduct.create(name="Test", price=1.0, active=True)
    row = YBProduct.get(id=pid)
    assert row["active"] is True
    assert isinstance(row["active"], bool)


def test_bool_false_returns_native_boolean():
    pid = YBProduct.create(name="Test", price=1.0, active=False)
    row = YBProduct.get(id=pid)
    assert row["active"] is False
    assert isinstance(row["active"], bool)


# ------------------------------------------------------------------ #
#  CRUD operations                                                     #
# ------------------------------------------------------------------ #

def test_create_returns_id():
    pid = YBProduct.create(name="Widget", price=9.99, active=True)
    assert isinstance(pid, int)
    assert pid > 0


def test_create_and_get():
    pid = YBProduct.create(name="Gadget", price=19.99, active=True)
    row = YBProduct.get(id=pid)
    assert row is not None
    assert row["name"]  == "Gadget"
    assert abs(row["price"] - 19.99) < 0.01


def test_all():
    YBProduct.create(name="A", price=1.0, active=True)
    YBProduct.create(name="B", price=2.0, active=True)
    rows = YBProduct.all()
    assert len(rows) == 2


def test_filter():
    YBProduct.create(name="Active",   price=1.0, active=True)
    YBProduct.create(name="Inactive", price=2.0, active=False)
    rows = YBProduct.filter(active=True)
    assert len(rows) == 1
    assert rows[0]["name"] == "Active"


def test_update():
    pid = YBProduct.create(name="Old", price=5.0, active=True)
    affected = YBProduct.update({"name": "New", "price": 10.0}, id=pid)
    assert affected == 1
    row = YBProduct.get(id=pid)
    assert row["name"] == "New"
    assert abs(row["price"] - 10.0) < 0.01


def test_delete():
    pid     = YBProduct.create(name="Del", price=1.0, active=True)
    deleted = YBProduct.delete(id=pid)
    assert deleted == 1
    assert YBProduct.get(id=pid) is None


def test_count():
    YBProduct.create(name="C1", price=1.0, active=True)
    YBProduct.create(name="C2", price=2.0, active=True)
    assert YBProduct.count() == 2


def test_exists():
    YBProduct.create(name="Exists", price=1.0, active=True)
    assert YBProduct.exists(name="Exists") is True
    assert YBProduct.exists(name="Ghost")  is False


# ------------------------------------------------------------------ #
#  Query builder on YugabyteDB                                         #
# ------------------------------------------------------------------ #

def test_query_where():
    YBProduct.create(name="Cheap",     price=1.0,  active=True)
    YBProduct.create(name="Expensive", price=99.0, active=True)
    rows = YBProduct.query().where("price__gt", 50).all()
    assert len(rows) == 1
    assert rows[0]["name"] == "Expensive"


def test_query_order_by():
    YBProduct.create(name="B", price=2.0, active=True)
    YBProduct.create(name="A", price=1.0, active=True)
    rows = YBProduct.query().order_by("name").all()
    assert rows[0]["name"] == "A"
    assert rows[1]["name"] == "B"


def test_query_limit():
    for i in range(5):
        YBProduct.create(name=f"P{i}", price=float(i), active=True)
    rows = YBProduct.query().limit(3).all()
    assert len(rows) == 3


def test_query_count():
    YBProduct.create(name="X", price=1.0, active=True)
    YBProduct.create(name="Y", price=2.0, active=True)
    assert YBProduct.query().count() == 2


# ------------------------------------------------------------------ #
#  Bulk operations on YugabyteDB                                       #
# ------------------------------------------------------------------ #

def test_bulk_create():
    count = YBProduct.bulk_create([
        {"name": "BC1", "price": 1.0, "active": True},
        {"name": "BC2", "price": 2.0, "active": True},
        {"name": "BC3", "price": 3.0, "active": False},
    ])
    assert count == 3
    assert YBProduct.count() == 3


def test_bulk_delete():
    YBProduct.bulk_create([
        {"name": "BD1", "price": 1.0, "active": True},
        {"name": "BD2", "price": 2.0, "active": True},
    ])
    rows    = YBProduct.all()
    del_ids = [r["id"] for r in rows]
    deleted = YBProduct.bulk_delete(del_ids)
    assert deleted == 2
    assert YBProduct.count() == 0


# ------------------------------------------------------------------ #
#  Raw SQL on YugabyteDB                                               #
# ------------------------------------------------------------------ #

def test_raw_fetchall():
    rows = db.fetchall("SELECT 1 AS num, 'hello' AS msg")
    assert rows[0]["num"] == 1
    assert rows[0]["msg"] == "hello"


def test_raw_execute():
    YBProduct.create(name="Raw", price=5.0, active=True)
    affected = db.execute(
        'UPDATE "yb_products" SET price = %s WHERE name = %s',
        [99.9, "Raw"]
    )
    assert affected == 1
    row = YBProduct.query().where("name", "Raw").first()
    assert abs(row["price"] - 99.9) < 0.01


def test_table_exists():
    assert db.table_exists("yb_products") is True
    assert db.table_exists("nonexistent") is False


# ------------------------------------------------------------------ #
#  Full workflow                                                        #
# ------------------------------------------------------------------ #

def test_full_yugabyte_workflow():
    pid = YBProduct.create(name="Flow", price=10.0, active=True)
    assert YBProduct.count() == 1

    row = YBProduct.get(id=pid)
    assert row["name"] == "Flow"
    assert row["active"] is True

    YBProduct.update({"price": 20.0, "active": False}, id=pid)
    updated = YBProduct.get(id=pid)
    assert abs(updated["price"] - 20.0) < 0.01
    assert updated["active"] is False

    YBProduct.delete(id=pid)
    assert YBProduct.count() == 0