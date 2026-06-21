# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_composite_keys.py
# Project     : mydborm
# Version     : 1.4.0
# License     : MIT
# Description : Tests for composite primary key support
# =============================================================================

import os
import socket
import pytest
from mydborm import db, BaseModel, IntField, StrField, FloatField, BoolField


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class OrderItem(BaseModel):
    __tablename__ = "cpk_order_items"
    __pk__        = ("order_id", "product_id")
    order_id   = IntField(nullable=False)
    product_id = IntField(nullable=False)
    quantity   = IntField(nullable=False, default=1)
    price      = FloatField(nullable=False)


class StudentCourse(BaseModel):
    __tablename__ = "cpk_student_courses"
    __pk__        = ("student_id", "course_id")
    student_id = IntField(nullable=False)
    course_id  = IntField(nullable=False)
    grade      = StrField(max_length=5, nullable=True)
    enrolled   = BoolField(default=True)


class RolePermission(BaseModel):
    __tablename__ = "cpk_role_permissions"
    __pk__        = ("role_id", "permission_id", "resource")
    role_id       = IntField(nullable=False)
    permission_id = IntField(nullable=False)
    resource      = StrField(max_length=50, nullable=False)
    granted       = BoolField(default=True)


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
        cur.execute("DROP TABLE IF EXISTS cpk_order_items")
        cur.execute("DROP TABLE IF EXISTS cpk_student_courses")
        cur.execute("DROP TABLE IF EXISTS cpk_role_permissions")
    OrderItem.create_table()
    StudentCourse.create_table()
    RolePermission.create_table()
    yield
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS cpk_order_items")
        cur.execute("DROP TABLE IF EXISTS cpk_student_courses")
        cur.execute("DROP TABLE IF EXISTS cpk_role_permissions")
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM cpk_order_items")
        cur.execute("DELETE FROM cpk_student_courses")
        cur.execute("DELETE FROM cpk_role_permissions")
    yield


# ------------------------------------------------------------------ #
#  Model metadata                                                      #
# ------------------------------------------------------------------ #

def test_composite_pk_stored_on_class():
    assert OrderItem._composite_pk == ("order_id", "product_id")


def test_composite_pk_three_fields():
    assert RolePermission._composite_pk == ("role_id", "permission_id", "resource")


def test_regular_model_no_composite_pk():
    class Regular(BaseModel):
        __tablename__ = "regular"
        id   = IntField(primary_key=True)
        name = StrField(max_length=50)
    assert not Regular._composite_pk


# ------------------------------------------------------------------ #
#  create_table — SQL generation                                       #
# ------------------------------------------------------------------ #

def test_create_table_generates_composite_pk():
    sql = db.fetchall(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
        "WHERE TABLE_NAME = %s AND CONSTRAINT_NAME = 'PRIMARY' "
        "AND TABLE_SCHEMA = %s "
        "ORDER BY ORDINAL_POSITION",
        ["cpk_order_items", "testdb"]
    )
    cols = [r["COLUMN_NAME"] for r in sql]
    assert "order_id"   in cols
    assert "product_id" in cols


def test_create_table_three_field_pk():
    sql = db.fetchall(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
        "WHERE TABLE_NAME = %s AND CONSTRAINT_NAME = 'PRIMARY' "
        "AND TABLE_SCHEMA = %s "
        "ORDER BY ORDINAL_POSITION",
        ["cpk_role_permissions", "testdb"]
    )
    cols = [r["COLUMN_NAME"] for r in sql]
    assert "role_id"       in cols
    assert "permission_id" in cols
    assert "resource"      in cols


# ------------------------------------------------------------------ #
#  create()                                                            #
# ------------------------------------------------------------------ #

def test_create_returns_dict():
    result = OrderItem.create(order_id=1, product_id=101, quantity=2, price=9.99)
    assert isinstance(result, dict)
    assert result["order_id"]   == 1
    assert result["product_id"] == 101


def test_create_all_pk_fields_in_result():
    result = OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    for field in OrderItem._composite_pk:
        assert field in result


def test_create_missing_pk_field_raises():
    with pytest.raises(ValueError, match="required"):
        OrderItem.create(order_id=1, quantity=1, price=9.99)


def test_create_multiple_rows():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.create(order_id=1, product_id=102, quantity=2, price=19.99)
    OrderItem.create(order_id=2, product_id=101, quantity=3, price=9.99)
    assert OrderItem.count() == 3


def test_create_three_field_pk():
    result = RolePermission.create(
        role_id=1, permission_id=10, resource="users", granted=True
    )
    assert isinstance(result, dict)
    assert result["role_id"]       == 1
    assert result["permission_id"] == 10
    assert result["resource"]      == "users"


# ------------------------------------------------------------------ #
#  get()                                                               #
# ------------------------------------------------------------------ #

def test_get_by_composite_pk():
    OrderItem.create(order_id=1, product_id=101, quantity=5, price=29.99)
    item = OrderItem.get(order_id=1, product_id=101)
    assert item is not None
    assert item["quantity"] == 5
    assert item["price"]    == 29.99


def test_get_returns_none_for_missing():
    item = OrderItem.get(order_id=999, product_id=999)
    assert item is None


def test_get_partial_pk_returns_first_match():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.create(order_id=1, product_id=102, quantity=2, price=19.99)
    item = OrderItem.get(order_id=1)
    assert item is not None


def test_get_three_field_pk():
    RolePermission.create(
        role_id=1, permission_id=10, resource="posts", granted=True
    )
    perm = RolePermission.get(role_id=1, permission_id=10, resource="posts")
    assert perm is not None
    assert perm["granted"] == 1


# ------------------------------------------------------------------ #
#  all() + filter()                                                    #
# ------------------------------------------------------------------ #

def test_all_returns_all_rows():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.create(order_id=1, product_id=102, quantity=2, price=19.99)
    OrderItem.create(order_id=2, product_id=101, quantity=1, price=9.99)
    assert len(OrderItem.all()) == 3


def test_filter_by_single_pk_field():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.create(order_id=1, product_id=102, quantity=2, price=19.99)
    OrderItem.create(order_id=2, product_id=101, quantity=1, price=9.99)
    items = OrderItem.filter(order_id=1)
    assert len(items) == 2
    assert all(i["order_id"] == 1 for i in items)


def test_filter_by_non_pk_field():
    OrderItem.create(order_id=1, product_id=101, quantity=5, price=9.99)
    OrderItem.create(order_id=1, product_id=102, quantity=1, price=9.99)
    items = OrderItem.filter(quantity=5)
    assert len(items) == 1


# ------------------------------------------------------------------ #
#  update()                                                            #
# ------------------------------------------------------------------ #

def test_update_by_composite_pk():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.update({"quantity": 10}, order_id=1, product_id=101)
    item = OrderItem.get(order_id=1, product_id=101)
    assert item["quantity"] == 10


def test_update_by_single_pk_field_affects_multiple():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.create(order_id=1, product_id=102, quantity=1, price=19.99)
    rows = OrderItem.update({"quantity": 99}, order_id=1)
    assert rows == 2


def test_update_non_pk_field():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.update({"price": 99.99}, order_id=1, product_id=101)
    item = OrderItem.get(order_id=1, product_id=101)
    assert item["price"] == 99.99


# ------------------------------------------------------------------ #
#  delete()                                                            #
# ------------------------------------------------------------------ #

def test_delete_by_composite_pk():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.create(order_id=1, product_id=102, quantity=1, price=9.99)
    OrderItem.delete(order_id=1, product_id=101)
    assert OrderItem.count() == 1
    assert OrderItem.get(order_id=1, product_id=101) is None


def test_delete_by_single_pk_field():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.create(order_id=1, product_id=102, quantity=1, price=9.99)
    OrderItem.create(order_id=2, product_id=101, quantity=1, price=9.99)
    deleted = OrderItem.delete(order_id=1)
    assert deleted == 2
    assert OrderItem.count() == 1


# ------------------------------------------------------------------ #
#  Integrity — duplicate PK rejected                                   #
# ------------------------------------------------------------------ #

def test_duplicate_composite_pk_raises():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    with pytest.raises(Exception):
        OrderItem.create(order_id=1, product_id=101, quantity=5, price=19.99)


def test_same_partial_pk_different_full_pk_ok():
    OrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
    OrderItem.create(order_id=1, product_id=102, quantity=1, price=9.99)
    OrderItem.create(order_id=2, product_id=101, quantity=1, price=9.99)
    assert OrderItem.count() == 3


# ------------------------------------------------------------------ #
#  YugabyteDB                                                          #
# ------------------------------------------------------------------ #

def _yb_available():
    try:
        s = socket.create_connection(("127.0.0.1", 5433), timeout=2)
        s.close()
        return True
    except OSError:
        return False


yb_skip = pytest.mark.skipif(not _yb_available(), reason="YugabyteDB not running")


class YBOrderItem(BaseModel):
    __tablename__ = "yb_cpk_items"
    __pk__        = ("order_id", "product_id")
    order_id   = IntField(nullable=False)
    product_id = IntField(nullable=False)
    quantity   = IntField(nullable=False, default=1)
    price      = FloatField(nullable=False)


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


@yb_skip
def test_yb_composite_pk_create_table():
    _yb_configure()
    try:
        with db.connect() as conn:
            conn.cursor().execute('DROP TABLE IF EXISTS "yb_cpk_items"')
        YBOrderItem.create_table()
        result = YBOrderItem.create(order_id=1, product_id=101,
                                     quantity=2, price=29.99)
        assert isinstance(result, dict)
        assert result["order_id"]   == 1
        assert result["product_id"] == 101
    finally:
        with db.connect() as conn:
            conn.cursor().execute('DROP TABLE IF EXISTS "yb_cpk_items"')
        _mysql_configure()


@yb_skip
def test_yb_composite_pk_get():
    _yb_configure()
    try:
        with db.connect() as conn:
            conn.cursor().execute('DROP TABLE IF EXISTS "yb_cpk_items"')
        YBOrderItem.create_table()
        YBOrderItem.create(order_id=1, product_id=101, quantity=5, price=9.99)
        item = YBOrderItem.get(order_id=1, product_id=101)
        assert item is not None
        assert item["quantity"] == 5
    finally:
        with db.connect() as conn:
            conn.cursor().execute('DROP TABLE IF EXISTS "yb_cpk_items"')
        _mysql_configure()


@yb_skip
def test_yb_composite_pk_duplicate_raises():
    _yb_configure()
    try:
        with db.connect() as conn:
            conn.cursor().execute('DROP TABLE IF EXISTS "yb_cpk_items"')
        YBOrderItem.create_table()
        YBOrderItem.create(order_id=1, product_id=101, quantity=1, price=9.99)
        with pytest.raises(Exception):
            YBOrderItem.create(order_id=1, product_id=101, quantity=2, price=19.99)
    finally:
        with db.connect() as conn:
            conn.cursor().execute('DROP TABLE IF EXISTS "yb_cpk_items"')
        _mysql_configure()