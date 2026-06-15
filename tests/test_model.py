"""
test_model.py — BaseModel CRUD tests against live MySQL.
"""
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class Product(BaseModel):
    __tablename__ = "products"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)
    price = StrField(max_length=20, nullable=False)
    active = BoolField(default=True)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password="root", database="testdb"
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
    pid = Product.create(name="Widget", price="9.99", active=True)
    assert pid == 1
    row = Product.get(id=pid)
    assert row["name"] == "Widget"
    assert row["price"] == "9.99"


def test_all_returns_list():
    Product.create(name="Alpha", price="1.00", active=True)
    Product.create(name="Beta",  price="2.00", active=True)
    rows = Product.all()
    assert len(rows) == 2


def test_filter():
    Product.create(name="Active",   price="1.00", active=True)
    Product.create(name="Inactive", price="2.00", active=False)
    rows = Product.filter(active=True)
    assert len(rows) == 1
    assert rows[0]["name"] == "Active"


def test_update():
    pid = Product.create(name="Old", price="5.00", active=True)
    affected = Product.update({"name": "New"}, id=pid)
    assert affected == 1
    assert Product.get(id=pid)["name"] == "New"


def test_delete():
    pid = Product.create(name="ToDelete", price="0.00", active=True)
    deleted = Product.delete(id=pid)
    assert deleted == 1
    assert Product.get(id=pid) is None


def test_count():
    Product.create(name="A", price="1.00", active=True)
    Product.create(name="B", price="2.00", active=True)
    assert Product.count() == 2


def test_exists():
    Product.create(name="Exists", price="1.00", active=True)
    assert Product.exists(name="Exists") is True
    assert Product.exists(name="Ghost")  is False


def test_get_returns_none_when_missing():
    assert Product.get(id=9999) is None