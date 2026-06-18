# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_upsert_joins.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.5.0
# License     : MIT
# Description : pytest tests for bulk_upsert and JOIN support in
#               QueryBuilder — inner_join, left_join, right_join,
#               chained joins and where clauses.
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class Category(BaseModel):
    __tablename__ = "uj_categories"
    id   = IntField(primary_key=True)
    name = StrField(max_length=50, nullable=False)


class Product(BaseModel):
    __tablename__ = "uj_products"
    id          = IntField(primary_key=True)
    sku         = StrField(max_length=50, nullable=False)
    name        = StrField(max_length=100, nullable=False)
    price       = FloatField(nullable=False)
    category_id = IntField(nullable=True)
    active      = BoolField(default=True)


class Order(BaseModel):
    __tablename__ = "uj_orders"
    id         = IntField(primary_key=True)
    product_id = IntField(nullable=False)
    qty        = IntField(nullable=False)
    shipped    = BoolField(default=False)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect  = "mysql",
        host     = "127.0.0.1",
        port     = 3307,
        user     = "root",
        password = os.environ.get("DB_PASSWORD", "root"),
        database = "testdb",
        charset  = "utf8mb4",
        encoding = "utf-8",
    )
    Category.create_table()
    Product.create_table()
    Order.create_table()
    yield
    Order.drop_table()
    Product.drop_table()
    Category.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM uj_orders")
        cur.execute("DELETE FROM uj_products")
        cur.execute("DELETE FROM uj_categories")
    yield


# ------------------------------------------------------------------ #
#  bulk_upsert — insert                                                #
# ------------------------------------------------------------------ #

def test_upsert_inserts_new_records():
    count = Product.bulk_upsert([
        {"sku": "P001", "name": "Widget",  "price": 9.99,  "active": True},
        {"sku": "P002", "name": "Gadget",  "price": 19.99, "active": True},
    ], conflict_key="sku", update_fields=["name", "price"])
    assert Product.count() == 2


def test_upsert_updates_existing():
    Product.bulk_upsert([
        {"sku": "U001", "name": "Original", "price": 10.0, "active": True}
    ], conflict_key="sku", update_fields=["name", "price"])

    Product.bulk_upsert([
        {"sku": "U001", "name": "Updated", "price": 20.0, "active": True}
    ], conflict_key="sku", update_fields=["name", "price"])

    assert Product.count() == 1
    row = Product.query().where("sku", "U001").first()
    assert row["name"]  == "Updated"
    assert abs(row["price"] - 20.0) < 0.01


def test_upsert_mixed_insert_and_update():
    Product.bulk_upsert([
        {"sku": "M001", "name": "Existing", "price": 5.0, "active": True}
    ], conflict_key="sku", update_fields=["name", "price"])

    Product.bulk_upsert([
        {"sku": "M001", "name": "Updated",  "price": 10.0, "active": True},
        {"sku": "M002", "name": "New Item", "price": 15.0, "active": True},
    ], conflict_key="sku", update_fields=["name", "price"])

    assert Product.count() == 2
    m001 = Product.query().where("sku", "M001").first()
    assert m001["name"] == "Updated"


def test_upsert_empty_list():
    result = Product.bulk_upsert([], conflict_key="sku")
    assert result == 0
    assert Product.count() == 0


def test_upsert_specific_update_fields():
    Product.bulk_upsert([
        {"sku": "F001", "name": "Original", "price": 5.0, "active": True}
    ], conflict_key="sku", update_fields=["price"])

    Product.bulk_upsert([
        {"sku": "F001", "name": "Changed", "price": 99.0, "active": False}
    ], conflict_key="sku", update_fields=["price"])

    row = Product.query().where("sku", "F001").first()
    assert row["name"]   == "Original"  # not updated
    assert abs(row["price"] - 99.0) < 0.01  # updated


def test_upsert_multiple_records():
    skus = [f"BULK{i:03d}" for i in range(10)]
    Product.bulk_upsert([
        {"sku": s, "name": f"Item {s}", "price": float(i), "active": True}
        for i, s in enumerate(skus)
    ], conflict_key="sku", update_fields=["name", "price"])
    assert Product.count() == 10

    Product.bulk_upsert([
        {"sku": s, "name": f"Updated {s}", "price": float(i) * 2, "active": True}
        for i, s in enumerate(skus)
    ], conflict_key="sku", update_fields=["name", "price"])
    assert Product.count() == 10


# ------------------------------------------------------------------ #
#  JOIN support                                                        #
# ------------------------------------------------------------------ #

@pytest.fixture()
def seeded_data():
    """Seed categories, products and orders for JOIN tests."""
    c1 = Category.create(name="Electronics")
    c2 = Category.create(name="Books")

    p1 = Product.create(name="Laptop",  sku="E001",
                        price=999.0, category_id=c1, active=True)
    p2 = Product.create(name="Phone",   sku="E002",
                        price=499.0, category_id=c1, active=True)
    p3 = Product.create(name="Python",  sku="B001",
                        price=39.0,  category_id=c2, active=True)
    p4 = Product.create(name="No Cat",  sku="X001",
                        price=9.0,   category_id=None, active=False)

    Order.create(product_id=p1, qty=2, shipped=True)
    Order.create(product_id=p1, qty=1, shipped=False)
    Order.create(product_id=p2, qty=3, shipped=True)

    return {"c1": c1, "c2": c2, "p1": p1, "p2": p2, "p3": p3, "p4": p4}


def test_inner_join(seeded_data):
    rows = (Product.query()
            .inner_join("uj_categories",
                        "uj_products.category_id = uj_categories.id")
            .all())
    assert len(rows) == 3


def test_left_join_includes_nulls(seeded_data):
    rows = (Product.query()
            .left_join("uj_categories",
                       "uj_products.category_id = uj_categories.id")
            .all())
    assert len(rows) == 4


def test_join_with_where(seeded_data):
    rows = (Product.query()
            .inner_join("uj_categories",
                        "uj_products.category_id = uj_categories.id")
            .where("uj_categories.name", "Electronics")
            .all())
    assert len(rows) == 2


def test_join_with_order_by(seeded_data):
    rows = (Product.query()
            .inner_join("uj_categories",
                        "uj_products.category_id = uj_categories.id")
            .order_by("uj_products.price", desc=True)
            .all())
    assert rows[0]["price"] == 999.0


def test_join_with_limit(seeded_data):
    rows = (Product.query()
            .inner_join("uj_categories",
                        "uj_products.category_id = uj_categories.id")
            .limit(2)
            .all())
    assert len(rows) == 2


def test_join_count(seeded_data):
    count = (Product.query()
             .inner_join("uj_categories",
                         "uj_products.category_id = uj_categories.id")
             .count())
    assert count == 3


def test_multiple_joins(seeded_data):
    rows = (Product.query()
            .inner_join("uj_categories",
                        "uj_products.category_id = uj_categories.id")
            .inner_join("uj_orders",
                        "uj_products.id = uj_orders.product_id")
            .all())
    assert len(rows) == 3


def test_join_invalid_type():
    with pytest.raises(ValueError, match="join_type must be"):
        Product.query().join("uj_categories",
                             "uj_products.category_id = uj_categories.id",
                             join_type="CROSS")


def test_join_repr():
    q = (Product.query()
         .inner_join("uj_categories",
                     "uj_products.category_id = uj_categories.id"))
    assert "INNER JOIN" in repr(q)
    assert "uj_categories" in repr(q)


def test_left_join_shortcut(seeded_data):
    rows = (Product.query()
            .left_join("uj_categories",
                       "uj_products.category_id = uj_categories.id")
            .where("uj_products.active", False)
            .all())
    assert len(rows) == 1


def test_join_chained_with_where_and_limit(seeded_data):
    rows = (Product.query()
            .inner_join("uj_categories",
                        "uj_products.category_id = uj_categories.id")
            .where("uj_categories.name", "Electronics")
            .order_by("uj_products.price")
            .limit(1)
            .all())
    assert len(rows) == 1
    assert rows[0]["price"] == 499.0