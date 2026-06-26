import os
# =============================================================================
# File        : tests/test_query_builder.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.3.0
# License     : MIT
# Description : pytest tests for QueryBuilder — covers where, operators,
#               order_by, limit, offset, aggregates, first, exists, delete.
# =============================================================================

import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class Item(BaseModel):
    __tablename__ = "items"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=100, nullable=False)
    price  = FloatField(nullable=False)
    active = BoolField(default=True)
    stock  = IntField(nullable=False)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
    )
    Item.create_table()
    yield
    Item.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def seed_table():
    """Clean and seed table before each test."""
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM items")

    Item.create(name="Apple",  price=1.50,  active=True,  stock=100)
    Item.create(name="Banana", price=0.75,  active=True,  stock=200)
    Item.create(name="Cherry", price=3.00,  active=False, stock=50)
    Item.create(name="Date",   price=5.00,  active=True,  stock=30)
    Item.create(name="Elderberry", price=8.00, active=False, stock=10)
    yield


# ------------------------------------------------------------------ #
#  Basic query                                                         #
# ------------------------------------------------------------------ #

def test_query_all():
    rows = Item.query().all()
    assert len(rows) == 5


def test_query_where_equality():
    rows = Item.query().where("active", True).all()
    assert len(rows) == 3
    assert all(r["active"] for r in rows)


def test_query_where_multiple():
    rows = (Item.query()
                .where("active", True)
                .where("stock__gt", 50)
                .all())
    assert len(rows) == 2
    names = {r["name"] for r in rows}
    assert names == {"Apple", "Banana"}


# ------------------------------------------------------------------ #
#  Operators                                                           #
# ------------------------------------------------------------------ #

def test_operator_gt():
    rows = Item.query().where("price__gt", 3.00).all()
    assert len(rows) == 2
    assert all(r["price"] > 3.00 for r in rows)


def test_operator_lt():
    rows = Item.query().where("price__lt", 2.00).all()
    assert len(rows) == 2


def test_operator_gte():
    rows = Item.query().where("price__gte", 3.00).all()
    assert len(rows) == 3


def test_operator_lte():
    rows = Item.query().where("price__lte", 1.50).all()
    assert len(rows) == 2


def test_operator_ne():
    rows = Item.query().where("name__ne", "Apple").all()
    assert len(rows) == 4
    assert all(r["name"] != "Apple" for r in rows)


def test_operator_like():
    rows = Item.query().where("name__like", "Che%").all()
    assert len(rows) == 1
    assert rows[0]["name"] == "Cherry"


def test_operator_in():
    rows = Item.query().where("name__in", ["Apple", "Date"]).all()
    assert len(rows) == 2
    names = {r["name"] for r in rows}
    assert names == {"Apple", "Date"}


def test_operator_in_invalid():
    with pytest.raises(ValueError, match="__in requires a list"):
        Item.query().where("name__in", "Apple")


# ------------------------------------------------------------------ #
#  Ordering                                                            #
# ------------------------------------------------------------------ #

def test_order_by_asc():
    rows = Item.query().order_by("price").all()
    prices = [r["price"] for r in rows]
    assert prices == sorted(prices)


def test_order_by_desc():
    rows = Item.query().order_by("price", desc=True).all()
    prices = [r["price"] for r in rows]
    assert prices == sorted(prices, reverse=True)


def test_order_by_name():
    rows = Item.query().order_by("name").all()
    names = [r["name"] for r in rows]
    assert names == sorted(names)


# ------------------------------------------------------------------ #
#  Pagination                                                          #
# ------------------------------------------------------------------ #

def test_limit():
    rows = Item.query().order_by("price").limit(3).all()
    assert len(rows) == 3


def test_offset():
    all_rows    = Item.query().order_by("price").all()
    offset_rows = Item.query().order_by("price").offset(2).all()
    assert offset_rows[0]["name"] == all_rows[2]["name"]


def test_limit_offset():
    rows = Item.query().order_by("price").limit(2).offset(1).all()
    assert len(rows) == 2


# ------------------------------------------------------------------ #
#  First                                                               #
# ------------------------------------------------------------------ #

def test_first():
    row = Item.query().order_by("price").first()
    assert row is not None
    assert row["name"] == "Banana"


def test_first_no_match():
    row = Item.query().where("price__gt", 9999).first()
    assert row is None


# ------------------------------------------------------------------ #
#  Aggregates                                                          #
# ------------------------------------------------------------------ #

def test_count():
    assert Item.query().count() == 5
    assert Item.query().where("active", True).count() == 3


def test_exists_true():
    assert Item.query().where("name", "Apple").exists() is True


def test_exists_false():
    assert Item.query().where("name", "Ghost").exists() is False


def test_sum():
    total = Item.query().sum("price")
    assert abs(total - 18.25) < 0.01


def test_avg():
    avg = Item.query().where("active", True).avg("price")
    expected = (1.50 + 0.75 + 5.00) / 3
    assert abs(avg - expected) < 0.01


def test_min():
    assert Item.query().min("price") == 0.75


def test_max():
    assert Item.query().max("price") == 8.00


# ------------------------------------------------------------------ #
#  Delete via query                                                    #
# ------------------------------------------------------------------ #

# ------------------------------------------------------------------ #
#  or_where()                                                          #
# ------------------------------------------------------------------ #

def test_or_where_basic():
    # Cherry (False) and Elderberry (False) are inactive
    rows = Item.query().or_where("name", "Cherry").or_where("name", "Elderberry").all()
    names = {r["name"] for r in rows}
    assert names == {"Cherry", "Elderberry"}


def test_or_where_combined_with_where():
    # Only Apple is active AND (name=Apple OR name=Cherry)
    rows = (Item.query()
                .where("active", True)
                .or_where("name", "Apple")
                .or_where("name", "Cherry")
                .all())
    names = {r["name"] for r in rows}
    assert "Apple" in names
    assert "Cherry" not in names   # Cherry is inactive — AND filters it out


def test_or_where_with_operator():
    rows = Item.query().or_where("price__lt", 1.0).or_where("price__gt", 7.0).all()
    assert all(r["price"] < 1.0 or r["price"] > 7.0 for r in rows)
    assert len(rows) == 2   # Banana (0.75) and Elderberry (8.00)


def test_or_where_with_in_operator():
    rows = Item.query().or_where("name__in", ["Apple", "Date"]).all()
    names = {r["name"] for r in rows}
    assert names == {"Apple", "Date"}


def test_or_where_count():
    total = Item.query().or_where("active", True).or_where("stock__lt", 20).count()
    assert total >= 3   # at least the 3 active items


def test_or_where_update():
    updated = (Item.query()
                   .or_where("name", "Cherry")
                   .or_where("name", "Elderberry")
                   .update(stock=999))
    assert updated == 2
    assert Item.query().where("stock", 999).count() == 2


def test_or_where_delete():
    deleted = (Item.query()
                   .or_where("name", "Cherry")
                   .or_where("name", "Elderberry")
                   .delete())
    assert deleted == 2
    assert Item.query().count() == 3


def test_or_where_only_no_and():
    # No .where() — just OR conditions
    rows = Item.query().or_where("name", "Apple").all()
    assert len(rows) == 1
    assert rows[0]["name"] == "Apple"


# ------------------------------------------------------------------ #
#  select() — column projection                                        #
# ------------------------------------------------------------------ #

def test_select_single_column():
    rows = Item.query().select("name").all()
    assert len(rows) == 5
    assert "name"  in rows[0]
    assert "price" not in rows[0]


def test_select_multiple_columns():
    rows = Item.query().select("name", "price").all()
    assert len(rows) == 5
    assert "name"   in rows[0]
    assert "price"  in rows[0]
    assert "active" not in rows[0]


def test_select_with_where():
    rows = Item.query().select("name").where("active", True).all()
    assert len(rows) == 3
    assert all("price" not in r for r in rows)


def test_select_with_order_and_limit():
    rows = Item.query().select("name", "price").order_by("price").limit(2).all()
    assert len(rows) == 2
    assert "name" in rows[0]


def test_select_does_not_affect_count():
    # count() always uses COUNT(*) — select() should not break it
    total = Item.query().select("name").where("active", True).count()
    assert total == 3


# ------------------------------------------------------------------ #
#  update() via query                                                  #
# ------------------------------------------------------------------ #

def test_query_update_with_filter():
    updated = Item.query().where("active", False).update(stock=0)
    assert updated == 2
    assert Item.query().where("stock", 0).count() == 2


def test_query_update_multiple_fields():
    updated = Item.query().where("name", "Apple").update(price=99.99, stock=999)
    assert updated == 1
    row = Item.query().where("name", "Apple").first()
    assert row["price"] == 99.99
    assert row["stock"] == 999


def test_query_update_no_filter_updates_all():
    # Set stock=0 for all 5 rows (all have stock > 0 in seed data)
    updated = Item.query().update(stock=0)
    assert updated == 5
    assert Item.query().where("stock", 0).count() == 5


def test_query_update_no_kwargs_returns_zero():
    result = Item.query().update()
    assert result == 0


def test_query_update_no_matching_rows():
    updated = Item.query().where("name", "NonExistent").update(stock=0)
    assert updated == 0


def test_query_delete():
    deleted = Item.query().where("active", False).delete()
    assert deleted == 2
    assert Item.query().count() == 3


def test_query_delete_with_operator():
    deleted = Item.query().where("price__gt", 4.00).delete()
    assert deleted == 2
    assert Item.query().count() == 3


# ------------------------------------------------------------------ #
#  Repr                                                                #
# ------------------------------------------------------------------ #

def test_repr():
    q = Item.query().where("active", True).limit(5)
    assert "QueryBuilder" in repr(q)
    assert "active" in repr(q)


# ------------------------------------------------------------------ #
#  paginate()                                                          #
# ------------------------------------------------------------------ #

def test_paginate_first_page():
    result = Item.query().order_by("id").paginate(page=1, per_page=3)
    assert result["page"]     == 1
    assert result["per_page"] == 3
    assert result["total"]    == 5
    assert result["pages"]    == 2
    assert len(result["data"]) == 3


def test_paginate_second_page():
    result = Item.query().order_by("id").paginate(page=2, per_page=3)
    assert result["page"]     == 2
    assert len(result["data"]) == 2


def test_paginate_last_page_partial():
    result = Item.query().paginate(page=2, per_page=4)
    assert result["total"]    == 5
    assert result["pages"]    == 2
    assert len(result["data"]) == 1


def test_paginate_with_filter():
    result = Item.query().where("active", True).paginate(page=1, per_page=10)
    assert result["total"]    == 3
    assert len(result["data"]) == 3


def test_paginate_default_args():
    result = Item.query().paginate()
    assert result["page"]     == 1
    assert result["per_page"] == 20
    assert result["total"]    == 5
    assert result["pages"]    == 1


def test_paginate_page_below_one_clamped():
    result = Item.query().paginate(page=0, per_page=3)
    assert result["page"]     == 1
    assert len(result["data"]) == 3


def test_paginate_empty_table():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM items")
    result = Item.query().paginate(page=1, per_page=5)
    assert result["total"] == 0
    assert result["pages"] == 1
    assert result["data"]  == []

