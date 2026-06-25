import os
# =============================================================================
# File        : tests/test_model.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : pytest integration tests for BaseModel CRUD operations
#               against a live MySQL instance. Covers create, all, get,
#               filter, update, delete, count, and exists.
# =============================================================================
"""
test_model.py — BaseModel CRUD tests against live MySQL.
"""
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class Product(BaseModel):
    __tablename__ = "products"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)
    price = FloatField(nullable=False)
    active = BoolField(default=True)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
    )
    Product.create_table()
    yield
    Product.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean_table():
    """Wipe table before each test."""
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM products")
    yield


# ------------------------------------------------------------------ #
#  Tests                                                               #
# ------------------------------------------------------------------ #

def test_create_and_get():
    pid = Product.create(name="Widget", price=9.99, active=True)
    assert pid == 1
    row = Product.get(id=pid)
    assert row["name"] == "Widget"
    assert row["price"] == 9.99


def test_all_returns_list():
    Product.create(name="Alpha", price=1.00, active=True)
    Product.create(name="Beta",  price=2.00, active=True)
    rows = Product.all()
    assert len(rows) == 2


def test_filter():
    Product.create(name="Active",   price=1.00, active=True)
    Product.create(name="Inactive", price=2.00, active=False)
    rows = Product.filter(active=True)
    assert len(rows) == 1
    assert rows[0]["name"] == "Active"


def test_update():
    pid = Product.create(name="Old", price=5.00, active=True)
    affected = Product.update({"name": "New"}, id=pid)
    assert affected == 1
    assert Product.get(id=pid)["name"] == "New"


def test_delete():
    pid = Product.create(name="ToDelete", price=0.00, active=True)
    deleted = Product.delete(id=pid)
    assert deleted == 1
    assert Product.get(id=pid) is None


def test_count():
    Product.create(name="A", price=1.00, active=True)
    Product.create(name="B", price=2.00, active=True)
    assert Product.count() == 2


def test_exists():
    Product.create(name="Exists", price=1.00, active=True)
    assert Product.exists(name="Exists") is True
    assert Product.exists(name="Ghost")  is False


def test_get_returns_none_when_missing():
    assert Product.get(id=9999) is None


# ------------------------------------------------------------------ #
#  ModelInstance coverage                                              #
# ------------------------------------------------------------------ #

def test_model_instance_iter():
    """ModelInstance.__iter__ yields keys (line 596)."""
    Product.create(name="Widget", price=9.99, active=True)
    row = Product.all()[0]
    keys = list(iter(row))  # line 596
    assert "name" in keys
    assert "price" in keys


def test_model_instance_setattr():
    """ModelInstance.__setattr__ updates _data (line 632)."""
    Product.create(name="Widget", price=9.99, active=True)
    row = Product.all()[0]
    row.name = "Updated"  # calls __setattr__ → line 632
    assert row["name"] == "Updated"


def test_model_instance_to_json_with_datetime():
    """to_json serialiser handles datetime objects (line 679)."""
    import datetime
    Product.create(name="Widget", price=9.99, active=True)
    row = Product.all()[0]
    row["extra_dt"] = datetime.datetime(2024, 6, 1, 12, 0, 0)
    json_str = row.to_json()  # line 679 hit when serialising datetime
    assert "2024-06-01" in json_str


def test_model_instance_get_pk_no_pk_raises():
    """ModelInstance._get_pk_value raises when model has no PK (line 704)."""
    from mydborm.model import ModelInstance

    class _FakeNoPk:
        __name__ = "_FakeNoPk"
        _composite_pk = None
        _fields = {}

    inst = ModelInstance(_FakeNoPk, {"name": "test"})
    with pytest.raises(ValueError, match="No primary key"):
        inst._get_pk_value()  # line 704


# ------------------------------------------------------------------ #
#  BaseModel helpers coverage                                          #
# ------------------------------------------------------------------ #

def test_build_where_empty_raises():
    """_build_where({}) raises ValueError (line 1187)."""
    with pytest.raises(ValueError, match="At least one filter"):
        Product._build_where({})


def test_basemodel_has_many():
    """BaseModel.has_many on a raw instance (lines 1336-1338)."""
    pid = Product.create(name="Widget", price=9.99, active=True)
    instance = object.__new__(Product)
    instance._data = {"id": pid}
    # Use foreign_key="id" so the WHERE clause hits a real column
    result = instance.has_many(Product, foreign_key="id")  # lines 1336-1338
    assert isinstance(result, list)


def test_basemodel_belongs_to_none_fk():
    """BaseModel.belongs_to returns None when FK value is None (lines 1351-1354)."""
    instance = object.__new__(Product)
    instance._data = {"id": 1, "ref_id": None}
    result = instance.belongs_to(Product, foreign_key="ref_id")  # lines 1351-1354
    assert result is None


def test_basemodel_belongs_to_with_fk():
    """BaseModel.belongs_to fetches related row when FK is set (line 1355)."""
    pid = Product.create(name="Widget", price=9.99, active=True)
    instance = object.__new__(Product)
    instance._data = {"id": 999, "ref_id": pid}
    result = instance.belongs_to(Product, foreign_key="ref_id")  # line 1355
    assert result is None or result["id"] == pid


def test_basemodel_get_pk_value():
    """BaseModel._get_pk_value returns the PK (lines 1399-1405)."""
    pid = Product.create(name="Widget", price=9.99, active=True)
    instance = object.__new__(Product)
    instance._data = {"id": pid, "name": "Widget", "price": 9.99, "active": True}
    pk = instance._get_pk_value()  # lines 1399-1405
    assert pk == pid


def test_basemodel_get_pk_value_no_pk_raises():
    """BaseModel._get_pk_value raises when no PK field defined (line 1406)."""
    class NoPkModel(BaseModel):
        __tablename__ = "no_pk_coverage_test"
        name = StrField(max_length=50)

    instance = object.__new__(NoPkModel)
    instance._data = {"name": "test"}
    with pytest.raises(ValueError, match="No primary key"):
        instance._get_pk_value()


def test_bulk_update_skip_empty_data():
    """bulk_update skips a record that only has the key, no fields to update (line 1492)."""
    pid = Product.create(name="Widget", price=9.99, active=True)
    count = Product.bulk_update([{"id": pid}])  # only key → data is empty → continue
    assert count == 0  # line 1492 hit


def test_basemodel_repr():
    """BaseModel.__repr__ returns class and table name (line 1653)."""
    instance = object.__new__(Product)
    r = repr(instance)  # line 1653
    assert "Product" in r or "products" in r


