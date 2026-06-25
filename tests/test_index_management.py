# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_index_management.py
# Project     : mydborm
# Version     : 1.4.0
# License     : MIT
# Description : Tests for index management — auto-creation, create_index,
#               drop_index, list_indexes, __indexes__ composite indexes
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class Product(BaseModel):
    __tablename__ = "im_products"
    id       = IntField(primary_key=True)
    sku      = StrField(max_length=20,  nullable=False, unique=True)
    name     = StrField(max_length=100, nullable=False)
    category = StrField(max_length=50,  nullable=True,  index=True)
    price    = FloatField(nullable=False)
    active   = BoolField(default=True,  index=True)

    __indexes__ = [
        {"fields": ["category", "price"], "name": "idx_im_cat_price"},
        {"fields": ["name"],              "unique": True, "name": "idx_im_name_uniq"},
    ]


class SimpleModel(BaseModel):
    __tablename__ = "im_simple"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


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
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS im_products")
        cur.execute("DROP TABLE IF EXISTS im_simple")
    Product.create_table()
    SimpleModel.create_table()
    yield
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS im_products")
        cur.execute("DROP TABLE IF EXISTS im_simple")
    db.close()


# ------------------------------------------------------------------ #
#  Auto index creation from field definitions                          #
# ------------------------------------------------------------------ #

def test_index_true_creates_index():
    indexes = Product.list_indexes()
    names   = [i["name"] for i in indexes]
    assert any("category" in n for n in names)


def test_index_true_multiple_fields():
    indexes = Product.list_indexes()
    names   = [i["name"] for i in indexes]
    assert any("category" in n for n in names)
    assert any("active"   in n for n in names)


def test_unique_field_creates_unique_index():
    indexes = Product.list_indexes()
    sku_idx = next((i for i in indexes if "sku" in i["name"] or
                    "sku" in i.get("columns", [])), None)
    assert sku_idx is not None
    assert sku_idx["unique"] is True


def test_unique_field_no_duplicate_index():
    indexes = Product.list_indexes()
    sku_indexes = [i for i in indexes
                   if "sku" in (i.get("columns") or [i.get("name", "")])]
    assert len(sku_indexes) <= 2  # at most PRIMARY + sku unique


def test_primary_key_auto_indexed():
    indexes = Product.list_indexes()
    pk_idx  = next((i for i in indexes if i.get("primary")), None)
    assert pk_idx is not None


# ------------------------------------------------------------------ #
#  __indexes__ composite indexes                                       #
# ------------------------------------------------------------------ #

def test_composite_index_created():
    indexes = Product.list_indexes()
    names   = [i["name"] for i in indexes]
    assert "idx_im_cat_price" in names


def test_composite_index_columns():
    indexes  = Product.list_indexes()
    cat_idx  = next(i for i in indexes if i["name"] == "idx_im_cat_price")
    assert "category" in cat_idx["columns"]
    assert "price"    in cat_idx["columns"]


def test_composite_index_not_unique():
    indexes = Product.list_indexes()
    cat_idx = next(i for i in indexes if i["name"] == "idx_im_cat_price")
    assert cat_idx["unique"] is False


def test_unique_composite_index():
    indexes  = Product.list_indexes()
    name_idx = next((i for i in indexes if i["name"] == "idx_im_name_uniq"), None)
    assert name_idx is not None
    assert name_idx["unique"] is True


# ------------------------------------------------------------------ #
#  create_index()                                                      #
# ------------------------------------------------------------------ #

def test_create_index_single_field():
    name = SimpleModel.create_index(["name"])
    indexes = SimpleModel.list_indexes()
    assert any(i["name"] == name for i in indexes)
    SimpleModel.drop_index(name)


def test_create_index_returns_name():
    name = SimpleModel.create_index(["name"], name="idx_test_name")
    assert name == "idx_test_name"
    SimpleModel.drop_index("idx_test_name")


def test_create_index_auto_name():
    name = SimpleModel.create_index(["name"])
    assert "name" in name
    SimpleModel.drop_index(name)


def test_create_index_unique():
    name    = SimpleModel.create_index(["name"], unique=True, name="idx_sm_name_u")
    indexes = SimpleModel.list_indexes()
    idx     = next(i for i in indexes if i["name"] == "idx_sm_name_u")
    assert idx["unique"] is True
    SimpleModel.drop_index("idx_sm_name_u")


def test_create_index_empty_fields_raises():
    with pytest.raises(ValueError, match="at least one field"):
        SimpleModel.create_index([])


# ------------------------------------------------------------------ #
#  drop_index()                                                        #
# ------------------------------------------------------------------ #

def test_drop_index_removes_index():
    SimpleModel.create_index(["name"], name="idx_to_drop")
    SimpleModel.drop_index("idx_to_drop")
    indexes = SimpleModel.list_indexes()
    assert not any(i["name"] == "idx_to_drop" for i in indexes)


def test_drop_index_nonexistent_raises():
    with pytest.raises(Exception):
        SimpleModel.drop_index("nonexistent_index_xyz")


# ------------------------------------------------------------------ #
#  list_indexes()                                                      #
# ------------------------------------------------------------------ #

def test_list_indexes_returns_list():
    indexes = Product.list_indexes()
    assert isinstance(indexes, list)


def test_list_indexes_not_empty():
    indexes = Product.list_indexes()
    assert len(indexes) > 0


def test_list_indexes_has_required_fields():
    indexes = Product.list_indexes()
    for idx in indexes:
        assert "name"    in idx
        assert "columns" in idx
        assert "unique"  in idx


def test_list_indexes_simple_model_has_primary():
    indexes = SimpleModel.list_indexes()
    assert any(i.get("primary") or i["name"] == "PRIMARY" for i in indexes)


def test_no_indexes_on_table_with_only_pk():
    indexes = SimpleModel.list_indexes()
    non_pk  = [i for i in indexes if not i.get("primary") and i["name"] != "PRIMARY"]
    assert len(non_pk) == 0


# ------------------------------------------------------------------ #
#  Index performance — data integrity                                  #
# ------------------------------------------------------------------ #

def test_unique_index_prevents_duplicate():
    Product.create(sku="P001", name="Widget", price=9.99)
    with pytest.raises(Exception):
        Product.create(sku="P001", name="Widget2", price=19.99)
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM im_products")


def test_index_does_not_affect_crud():
    pid = Product.create(sku="P002", name="Gadget",
                         category="Electronics", price=29.99)
    p   = Product.get(id=pid)
    assert p["sku"]      == "P002"
    assert p["category"] == "Electronics"
    Product.update({"price": 24.99}, id=pid)
    p2 = Product.get(id=pid)
    assert p2["price"] == 24.99
    Product.delete(id=pid)
    assert Product.get(id=pid) is None

# ------------------------------------------------------------------ #
#  YugabyteDB index tests                                              #
# ------------------------------------------------------------------ #

import socket as _socket

def _yb_available():
    try:
        s = _socket.create_connection(("127.0.0.1", 5433), timeout=2)
        s.close()
        return True
    except OSError:
        return False

yb_skip = pytest.mark.skipif(not _yb_available(), reason="YugabyteDB not running")


def _yb_configure():
    db.close()
    db.configure(
        dialect  = "yugabyte",
        host     = "127.0.0.1",
        port     = 5433,
        user     = "yugabyte",
        password = os.environ.get("YB_PASSWORD", "yugabyte"),
        database = "yugabyte",
        encoding = "utf-8",
    )


def _mysql_configure():
    db.close()
    db.configure(
        dialect  = "mysql",
        host     = "127.0.0.1",
        port     = 3307,
        user     = "root",
        password = os.environ.get("DB_PASSWORD", "root"),
        database = "testdb",
        charset  = "utf8mb4",
    )


def _yb_drop(table: str):
    with db.connect() as conn:
        conn.cursor().execute(f'DROP TABLE IF EXISTS "{table}"')


class YBProduct(BaseModel):
    __tablename__ = "yb_im_products"
    id       = IntField(primary_key=True)
    sku      = StrField(max_length=20,  nullable=False, unique=True)
    name     = StrField(max_length=100, nullable=False)
    category = StrField(max_length=50,  nullable=True,  index=True)
    price    = FloatField(nullable=False)

    __indexes__ = [
        {"fields": ["category", "price"], "name": "idx_yb_cat_price"},
        {"fields": ["name"], "unique": True, "name": "idx_yb_name_uniq"},
    ]


class YBSimple(BaseModel):
    __tablename__ = "yb_im_simple"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


@yb_skip
def test_yb_auto_index_from_field():
    _yb_configure()
    try:
        _yb_drop("yb_im_products")
        YBProduct.create_table()
        indexes = YBProduct.list_indexes()
        names   = [i["name"] for i in indexes]
        assert any("category" in n for n in names)
    finally:
        _yb_drop("yb_im_products")
        _mysql_configure()


@yb_skip
def test_yb_composite_index_created():
    _yb_configure()
    try:
        _yb_drop("yb_im_products")
        YBProduct.create_table()
        indexes = YBProduct.list_indexes()
        names   = [i["name"] for i in indexes]
        assert "idx_yb_cat_price" in names
        assert "idx_yb_name_uniq" in names
    finally:
        _yb_drop("yb_im_products")
        _mysql_configure()


@yb_skip
def test_yb_create_index():
    _yb_configure()
    try:
        _yb_drop("yb_im_simple")
        YBSimple.create_table()
        name    = YBSimple.create_index(["name"], name="idx_yb_simple_name")
        indexes = YBSimple.list_indexes()
        assert any(i["name"] == "idx_yb_simple_name" for i in indexes)
    finally:
        _yb_drop("yb_im_simple")
        _mysql_configure()


@yb_skip
def test_yb_drop_index():
    _yb_configure()
    try:
        _yb_drop("yb_im_simple")
        YBSimple.create_table()
        YBSimple.create_index(["name"], name="idx_yb_to_drop")
        YBSimple.drop_index("idx_yb_to_drop")
        indexes = YBSimple.list_indexes()
        assert not any(i["name"] == "idx_yb_to_drop" for i in indexes)
    finally:
        _yb_drop("yb_im_simple")
        _mysql_configure()


@yb_skip
def test_yb_list_indexes_fields():
    _yb_configure()
    try:
        _yb_drop("yb_im_simple")
        YBSimple.create_table()
        indexes = YBSimple.list_indexes()
        assert isinstance(indexes, list)
        assert len(indexes) > 0
        for idx in indexes:
            assert "name"   in idx
            assert "unique" in idx
    finally:
        _yb_drop("yb_im_simple")
        _mysql_configure()


@yb_skip
def test_yb_unique_index_prevents_duplicate():
    _yb_configure()
    try:
        _yb_drop("yb_im_simple")
        YBSimple.create_table()
        YBSimple.create_index(["name"], unique=True, name="idx_yb_name_u")
        YBSimple.create(name="unique_test")
        with pytest.raises(Exception):
            YBSimple.create(name="unique_test")
    finally:
        _yb_drop("yb_im_simple")
        _mysql_configure()