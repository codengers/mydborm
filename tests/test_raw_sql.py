# =============================================================================
# File        : tests/test_raw_sql.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.4.0
# License     : MIT
# Description : pytest tests for raw SQL — db.execute, db.fetchall,
#               db.fetchone, db.table_exists, db.list_tables,
#               and db.transaction context manager.
# =============================================================================

import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class Order(BaseModel):
    __tablename__ = "orders"
    id      = IntField(primary_key=True)
    item    = StrField(max_length=100, nullable=False)
    qty     = IntField(nullable=False)
    shipped = BoolField(default=False)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password="root", database="testdb"
    )
    Order.create_table()
    yield
    Order.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean_table():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM orders")
    yield


# ------------------------------------------------------------------ #
#  fetchall                                                            #
# ------------------------------------------------------------------ #

def test_fetchall_returns_list():
    rows = db.fetchall("SELECT 1 AS num, 'hello' AS msg")
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["num"] == 1
    assert rows[0]["msg"] == "hello"


def test_fetchall_with_params():
    Order.bulk_create([
        {"item": "Widget", "qty": 10, "shipped": True},
        {"item": "Gadget", "qty": 5,  "shipped": False},
        {"item": "Donut",  "qty": 20, "shipped": True},
    ])
    rows = db.fetchall(
        "SELECT * FROM orders WHERE shipped = %s", [True]
    )
    assert len(rows) == 2
    assert all(r["shipped"] for r in rows)


def test_fetchall_empty_result():
    rows = db.fetchall(
        "SELECT * FROM orders WHERE qty > %s", [9999]
    )
    assert rows == []


def test_fetchall_multiple_rows():
    Order.bulk_create([
        {"item": "A", "qty": 1, "shipped": False},
        {"item": "B", "qty": 2, "shipped": False},
        {"item": "C", "qty": 3, "shipped": False},
    ])
    rows = db.fetchall("SELECT * FROM orders ORDER BY qty ASC")
    assert len(rows) == 3
    assert rows[0]["item"] == "A"
    assert rows[2]["item"] == "C"


# ------------------------------------------------------------------ #
#  fetchone                                                            #
# ------------------------------------------------------------------ #

def test_fetchone_returns_dict():
    row = db.fetchone("SELECT 42 AS answer")
    assert isinstance(row, dict)
    assert row["answer"] == 42


def test_fetchone_with_params():
    Order.create(item="Solo", qty=1, shipped=False)
    row = db.fetchone(
        "SELECT * FROM orders WHERE item = %s", ["Solo"]
    )
    assert row is not None
    assert row["item"] == "Solo"
    assert row["qty"] == 1


def test_fetchone_returns_none_when_missing():
    row = db.fetchone(
        "SELECT * FROM orders WHERE item = %s", ["Ghost"]
    )
    assert row is None


def test_fetchone_returns_first_row():
    Order.bulk_create([
        {"item": "First",  "qty": 1, "shipped": False},
        {"item": "Second", "qty": 2, "shipped": False},
    ])
    row = db.fetchone("SELECT * FROM orders ORDER BY qty ASC")
    assert row["item"] == "First"


# ------------------------------------------------------------------ #
#  execute                                                             #
# ------------------------------------------------------------------ #

def test_execute_update():
    Order.bulk_create([
        {"item": "Box", "qty": 5, "shipped": False},
        {"item": "Bag", "qty": 3, "shipped": False},
    ])
    affected = db.execute(
        "UPDATE orders SET shipped = %s WHERE qty > %s", [True, 4]
    )
    assert affected == 1
    row = db.fetchone("SELECT * FROM orders WHERE item = %s", ["Box"])
    assert row["shipped"] == 1


def test_execute_delete():
    Order.bulk_create([
        {"item": "Del1", "qty": 1, "shipped": False},
        {"item": "Del2", "qty": 2, "shipped": False},
        {"item": "Keep", "qty": 3, "shipped": False},
    ])
    affected = db.execute(
        "DELETE FROM orders WHERE qty < %s", [3]
    )
    assert affected == 2
    assert Order.count() == 1


def test_execute_returns_rowcount():
    Order.create(item="One", qty=1, shipped=False)
    affected = db.execute(
        "UPDATE orders SET qty = %s", [99]
    )
    assert affected == 1


# ------------------------------------------------------------------ #
#  table_exists                                                        #
# ------------------------------------------------------------------ #

def test_table_exists_true():
    assert db.table_exists("orders") is True


def test_table_exists_false():
    assert db.table_exists("nonexistent_table_xyz") is False


def test_table_exists_orders_table():
    assert db.table_exists("orders") is True


# ------------------------------------------------------------------ #
#  list_tables                                                         #
# ------------------------------------------------------------------ #

def test_list_tables_returns_list():
    tables = db.list_tables()
    assert isinstance(tables, list)
    assert len(tables) > 0


def test_list_tables_contains_orders():
    tables = db.list_tables()
    assert "orders" in tables


def test_list_tables_contains_strings():
    tables = db.list_tables()
    assert all(isinstance(t, str) for t in tables)


# ------------------------------------------------------------------ #
#  transaction                                                         #
# ------------------------------------------------------------------ #

def test_transaction_commits_on_success():
    with db.transaction():
        db.execute(
            "INSERT INTO orders (item, qty, shipped) VALUES (%s,%s,%s)",
            ["TxItem1", 5, False]
        )
        db.execute(
            "INSERT INTO orders (item, qty, shipped) VALUES (%s,%s,%s)",
            ["TxItem2", 10, False]
        )
    rows = db.fetchall("SELECT * FROM orders WHERE item LIKE 'TxItem%'")
    assert len(rows) == 2


def test_transaction_rollback_on_exception():
    initial_count = Order.count()
    try:
        with db.transaction():
            db.execute(
                "INSERT INTO orders (item, qty, shipped) VALUES (%s,%s,%s)",
                ["RollbackItem", 1, False]
            )
            raise ValueError("Simulated error — should rollback")
    except ValueError:
        pass
    assert Order.count() == initial_count


def test_transaction_multiple_operations():
    with db.transaction():
        db.execute(
            "INSERT INTO orders (item, qty, shipped) VALUES (%s,%s,%s)",
            ["Multi1", 1, False]
        )
        db.execute(
            "UPDATE orders SET qty = %s WHERE item = %s",
            [99, "Multi1"]
        )
    row = db.fetchone(
        "SELECT * FROM orders WHERE item = %s", ["Multi1"]
    )
    assert row["qty"] == 99