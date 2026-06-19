# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_group_by.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-19
# Version     : 0.8.0
# License     : MIT
# Description : pytest tests for GROUP BY, HAVING, and subquery support
#               in QueryBuilder.
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class Sale(BaseModel):
    __tablename__ = "gb_test_sales"
    id      = IntField(primary_key=True)
    region  = StrField(max_length=50,  nullable=False)
    product = StrField(max_length=50,  nullable=False)
    amount  = FloatField(nullable=False)
    shipped = BoolField(default=True)


class Customer(BaseModel):
    __tablename__ = "gb_test_customers"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=100, nullable=False)
    active = BoolField(default=True)
    region = StrField(max_length=50,  nullable=False)


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
    )
    Sale.create_table()
    Customer.create_table()
    yield
    Customer.drop_table()
    Sale.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM gb_test_sales")
        cur.execute("DELETE FROM gb_test_customers")
    yield


@pytest.fixture()
def seeded():
    Sale.bulk_create([
        {"region": "North", "product": "Widget", "amount": 100.0, "shipped": True},
        {"region": "North", "product": "Gadget", "amount": 200.0, "shipped": True},
        {"region": "South", "product": "Widget", "amount": 150.0, "shipped": False},
        {"region": "South", "product": "Widget", "amount": 250.0, "shipped": True},
        {"region": "East",  "product": "Gadget", "amount": 50.0,  "shipped": True},
    ])
    Customer.bulk_create([
        {"name": "Alice", "active": True,  "region": "North"},
        {"name": "Bob",   "active": True,  "region": "North"},
        {"name": "Carol", "active": False, "region": "South"},
        {"name": "Dave",  "active": True,  "region": "East"},
    ])


# ------------------------------------------------------------------ #
#  GROUP BY                                                            #
# ------------------------------------------------------------------ #

def test_group_by_returns_groups(seeded):
    rows = Sale.query().group_by("region").all()
    assert len(rows) == 3


def test_group_by_single_field(seeded):
    rows = Sale.query().group_by("product").all()
    assert len(rows) == 2


def test_group_by_multiple_fields(seeded):
    rows = Sale.query().group_by("region", "product").all()
    assert len(rows) == 4


def test_group_by_with_where(seeded):
    rows = (Sale.query()
                .where("shipped", True)
                .group_by("region")
                .all())
    assert len(rows) == 3


def test_group_by_with_order(seeded):
    rows = (Sale.query()
                .group_by("region")
                .order_by("region")
                .all())
    assert len(rows) == 3
    regions = [r["region"] for r in rows]
    assert regions == sorted(regions)


def test_group_by_with_limit(seeded):
    rows = Sale.query().group_by("region").limit(2).all()
    assert len(rows) == 2


def test_group_by_chainable(seeded):
    q = Sale.query().group_by("region")
    assert hasattr(q, "_group_by")
    assert "region" in q._group_by


# ------------------------------------------------------------------ #
#  GROUP BY + count                                                    #
# ------------------------------------------------------------------ #

def test_group_by_count(seeded):
    count = Sale.query().group_by("region").count()
    assert count == 3


def test_group_by_count_with_where(seeded):
    count = (Sale.query()
                 .where("shipped", True)
                 .group_by("region")
                 .count())
    assert count == 3


def test_group_by_count_single_group(seeded):
    count = (Sale.query()
                 .where("region", "North")
                 .group_by("region")
                 .count())
    assert count == 1


# ------------------------------------------------------------------ #
#  HAVING                                                              #
# ------------------------------------------------------------------ #

def test_having_count_gt(seeded):
    rows = (Sale.query()
                .group_by("region")
                .having("COUNT(*) > 1")
                .all())
    assert len(rows) == 2


def test_having_count_eq(seeded):
    rows = (Sale.query()
                .group_by("region")
                .having("COUNT(*) = 1")
                .all())
    assert len(rows) == 1
    assert rows[0]["region"] == "East"


def test_having_count_gte(seeded):
    rows = (Sale.query()
                .group_by("region")
                .having("COUNT(*) >= 2")
                .all())
    assert len(rows) == 2


def test_having_with_where(seeded):
    rows = (Sale.query()
                .where("shipped", True)
                .group_by("region")
                .having("COUNT(*) > 1")
                .all())
    assert len(rows) >= 1


def test_having_chainable(seeded):
    q = Sale.query().group_by("region").having("COUNT(*) > 1")
    assert len(q._having) == 1
    assert "COUNT(*) > 1" in q._having


def test_having_product_count_gt_2(seeded):
    rows = (Sale.query()
                .group_by("product")
                .having("COUNT(*) > 2")
                .all())
    assert len(rows) == 1
    assert rows[0]["product"] == "Widget"


# ------------------------------------------------------------------ #
#  Subqueries                                                          #
# ------------------------------------------------------------------ #

def test_subquery_returns_string(seeded):
    sq = Sale.query().where("region", "North").subquery("id")
    assert isinstance(sq, str)
    assert sq.startswith("(SELECT")
    assert sq.endswith(")")


def test_subquery_contains_select(seeded):
    sq = Sale.query().where("region", "North").subquery("id")
    assert "SELECT id FROM" in sq


def test_subquery_inlines_params(seeded):
    sq = Sale.query().where("region", "North").subquery("id")
    assert "'North'" in sq
    assert "%s" not in sq


def test_subquery_with_in(seeded):
    north_ids = Sale.query().where("region", "North").subquery("id")
    rows = Sale.query().where("id__in", north_ids).all()
    assert len(rows) == 2
    assert all(r["region"] == "North" for r in rows)


def test_subquery_cross_model(seeded):
    active_regions = (Customer.query()
                              .where("active", True)
                              .subquery("region"))
    rows = Sale.query().where("region__in", active_regions).all()
    assert len(rows) > 0


def test_subquery_with_limit(seeded):
    sq = Sale.query().limit(2).subquery("id")
    assert "LIMIT 2" in sq


def test_subquery_empty_result(seeded):
    sq    = Sale.query().where("region", "Mars").subquery("id")
    rows  = Sale.query().where("id__in", sq).all()
    assert len(rows) == 0


# ------------------------------------------------------------------ #
#  Combined                                                            #
# ------------------------------------------------------------------ #

def test_group_by_having_order(seeded):
    rows = (Sale.query()
                .group_by("region")
                .having("COUNT(*) > 1")
                .order_by("region")
                .all())
    assert len(rows) == 2
    regions = [r["region"] for r in rows]
    assert regions == sorted(regions)


def test_subquery_in_with_where(seeded):
    north_ids = Sale.query().where("region", "North").subquery("id")
    rows = (Sale.query()
                .where("id__in", north_ids)
                .where("shipped", True)
                .all())
    assert all(r["region"] == "North" for r in rows)
    assert all(r["shipped"] == 1 for r in rows)


def test_group_by_having_subquery_combined(seeded):
    big_regions = (Sale.query()
                       .group_by("region")
                       .having("COUNT(*) > 1")
                       .subquery("region"))
    rows = Sale.query().where("region__in", big_regions).all()
    assert len(rows) == 4