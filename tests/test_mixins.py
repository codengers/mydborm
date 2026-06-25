# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_mixins.py
# Project     : mydborm
# Version     : 1.3.0
# License     : MIT
# Description : Tests for SoftDeleteMixin, AuditMixin, TimestampMixin
# =============================================================================

import os
import time
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm.mixins import SoftDeleteMixin, AuditMixin, TimestampMixin


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class Post(BaseModel, SoftDeleteMixin):
    __tablename__ = "mx_posts"
    id      = IntField(primary_key=True)
    title   = StrField(max_length=200, nullable=False)
    content = StrField(max_length=500, nullable=True)


class Order(BaseModel, AuditMixin):
    __tablename__ = "mx_orders"
    id    = IntField(primary_key=True)
    total = FloatField(nullable=False)
    note  = StrField(max_length=200, nullable=True)


class Comment(BaseModel, TimestampMixin):
    __tablename__ = "mx_comments"
    id      = IntField(primary_key=True)
    content = StrField(max_length=500, nullable=False)


# Reversed MRO so mixin's create_table is called first (not BaseModel's)
class MixinTestSoft(SoftDeleteMixin, BaseModel):
    __tablename__ = "mx_test_soft"
    id    = IntField(primary_key=True)
    title = StrField(max_length=100)


class MixinTestAudit(AuditMixin, BaseModel):
    __tablename__ = "mx_test_audit"
    id    = IntField(primary_key=True)
    total = FloatField()


class MixinTestTS(TimestampMixin, BaseModel):
    __tablename__ = "mx_test_ts"
    id      = IntField(primary_key=True)
    content = StrField(max_length=100)


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
    Post.create_table()
    Order.create_table()
    Comment.create_table()
    yield
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS mx_posts")
        cur.execute("DROP TABLE IF EXISTS mx_orders")
        cur.execute("DROP TABLE IF EXISTS mx_comments")
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM mx_posts")
        cur.execute("DELETE FROM mx_orders")
        cur.execute("DELETE FROM mx_comments")
    AuditMixin.set_current_user(None)
    yield


# ------------------------------------------------------------------ #
#  SoftDeleteMixin — field injection                                   #
# ------------------------------------------------------------------ #

def test_soft_delete_field_in_model():
    assert "deleted_at" in Post._fields


def test_soft_delete_field_nullable():
    assert Post._fields["deleted_at"].nullable is True


# ------------------------------------------------------------------ #
#  SoftDeleteMixin — create / all                                      #
# ------------------------------------------------------------------ #

def test_soft_delete_all_excludes_deleted():
    p1 = Post.create(title="Post 1")
    p2 = Post.create(title="Post 2")
    Post.soft_delete(id=p1)
    rows = Post.all()
    assert len(rows) == 1
    assert rows[0]["title"] == "Post 2"


def test_soft_delete_all_empty_when_all_deleted():
    p1 = Post.create(title="Post 1")
    Post.soft_delete(id=p1)
    assert Post.all() == []


def test_soft_delete_sets_deleted_at():
    pid = Post.create(title="Test")
    Post.soft_delete(id=pid)
    rows = Post.all_with_deleted()
    post = next(r for r in rows if r["id"] == pid)
    assert post["deleted_at"] is not None


def test_soft_delete_all_with_deleted():
    p1 = Post.create(title="Post 1")
    p2 = Post.create(title="Post 2")
    Post.soft_delete(id=p1)
    rows = Post.all_with_deleted()
    assert len(rows) == 2


def test_soft_delete_only_deleted():
    p1 = Post.create(title="Post 1")
    p2 = Post.create(title="Post 2")
    Post.soft_delete(id=p1)
    rows = Post.only_deleted()
    assert len(rows) == 1
    assert rows[0]["id"] == p1


def test_soft_delete_filter_excludes_deleted():
    p1 = Post.create(title="Alpha")
    p2 = Post.create(title="Beta")
    Post.soft_delete(id=p1)
    rows = Post.filter(title="Alpha")
    assert len(rows) == 0


def test_soft_delete_get_excludes_deleted():
    pid = Post.create(title="Hidden")
    Post.soft_delete(id=pid)
    result = Post.get(id=pid)
    assert result is None


def test_soft_delete_count_excludes_deleted():
    p1 = Post.create(title="Post 1")
    p2 = Post.create(title="Post 2")
    Post.soft_delete(id=p1)
    assert Post.count() == 1


def test_soft_delete_exists_excludes_deleted():
    pid = Post.create(title="Test")
    Post.soft_delete(id=pid)
    assert Post.exists(id=pid) is False


# ------------------------------------------------------------------ #
#  SoftDeleteMixin — restore                                           #
# ------------------------------------------------------------------ #

def test_restore_makes_visible():
    pid = Post.create(title="Test")
    Post.soft_delete(id=pid)
    assert Post.count() == 0
    Post.restore(id=pid)
    assert Post.count() == 1


def test_restore_clears_deleted_at():
    pid = Post.create(title="Test")
    Post.soft_delete(id=pid)
    Post.restore(id=pid)
    post = Post.get(id=pid)
    assert post is not None
    assert post["deleted_at"] is None


def test_restore_multiple():
    p1 = Post.create(title="Post 1")
    p2 = Post.create(title="Post 2")
    Post.soft_delete(id=p1)
    Post.soft_delete(id=p2)
    assert Post.count() == 0
    Post.restore(id=p1)
    assert Post.count() == 1


# ------------------------------------------------------------------ #
#  SoftDeleteMixin — purge                                             #
# ------------------------------------------------------------------ #

def test_purge_permanently_deletes():
    pid = Post.create(title="Test")
    Post.purge(id=pid)
    assert len(Post.all_with_deleted()) == 0


def test_purge_all_deleted():
    p1 = Post.create(title="Post 1")
    p2 = Post.create(title="Post 2")
    p3 = Post.create(title="Post 3")
    Post.soft_delete(id=p1)
    Post.soft_delete(id=p2)
    count = Post.purge_all_deleted()
    assert count == 2
    assert len(Post.all_with_deleted()) == 1
    assert Post.all_with_deleted()[0]["id"] == p3


def test_purge_all_deleted_empty():
    Post.create(title="Active")
    count = Post.purge_all_deleted()
    assert count == 0


# ------------------------------------------------------------------ #
#  SoftDeleteMixin — is_deleted instance method                        #
# ------------------------------------------------------------------ #

def test_is_deleted_false_for_active():
    pid  = Post.create(title="Test")
    post = Post.all_with_deleted()[0]
    assert post.is_deleted() is False


def test_is_deleted_true_for_deleted():
    pid = Post.create(title="Test")
    Post.soft_delete(id=pid)
    post = Post.only_deleted()[0]
    assert post.is_deleted() is True


# ------------------------------------------------------------------ #
#  AuditMixin — auto timestamps                                        #
# ------------------------------------------------------------------ #

def test_audit_fields_in_model():
    for f in ["created_at", "updated_at", "created_by", "updated_by"]:
        assert f in Order._fields


def test_audit_created_at_auto_set():
    oid   = Order.create(total=99.99)
    order = Order.get(id=oid)
    assert order["created_at"] is not None


def test_audit_updated_at_auto_set_on_create():
    oid   = Order.create(total=99.99)
    order = Order.get(id=oid)
    assert order["updated_at"] is not None


def test_audit_created_at_equals_updated_at_on_create():
    oid   = Order.create(total=99.99)
    order = Order.get(id=oid)
    assert str(order["created_at"]) == str(order["updated_at"])


def test_audit_updated_at_changes_on_update():
    oid = Order.create(total=99.99)
    time.sleep(1)
    Order.update({"total": 89.99}, id=oid)
    order = Order.get(id=oid)
    assert str(order["created_at"]) != str(order["updated_at"])


def test_audit_was_updated_false_on_create():
    oid   = Order.create(total=99.99)
    order = Order.get(id=oid)
    assert order.was_updated() is False


def test_audit_was_updated_true_after_update():
    oid = Order.create(total=99.99)
    time.sleep(1)
    Order.update({"total": 89.99}, id=oid)
    order = Order.get(id=oid)
    assert order.was_updated() is True


def test_audit_age_returns_timedelta():
    import datetime
    oid   = Order.create(total=99.99)
    order = Order.get(id=oid)
    age   = order.age()
    assert isinstance(age, datetime.timedelta)
    assert age.total_seconds() >= 0


# ------------------------------------------------------------------ #
#  AuditMixin — user tracking                                          #
# ------------------------------------------------------------------ #

def test_audit_created_by_none_by_default():
    oid   = Order.create(total=99.99)
    order = Order.get(id=oid)
    assert order["created_by"] is None


def test_audit_created_by_set_when_user_set():
    AuditMixin.set_current_user(42)
    oid   = Order.create(total=99.99)
    order = Order.get(id=oid)
    assert order["created_by"] == 42


def test_audit_updated_by_set_on_update():
    AuditMixin.set_current_user(42)
    oid = Order.create(total=99.99)
    AuditMixin.set_current_user(99)
    Order.update({"total": 89.99}, id=oid)
    order = Order.get(id=oid)
    assert order["updated_by"] == 99


def test_audit_user_cleared():
    AuditMixin.set_current_user(42)
    AuditMixin.set_current_user(None)
    oid   = Order.create(total=99.99)
    order = Order.get(id=oid)
    assert order["created_by"] is None


# ------------------------------------------------------------------ #
#  TimestampMixin                                                      #
# ------------------------------------------------------------------ #

def test_timestamp_fields_in_model():
    assert "created_at" in Comment._fields
    assert "updated_at" in Comment._fields


def test_timestamp_created_at_auto_set():
    cid     = Comment.create(content="Hello!")
    comment = Comment.get(id=cid)
    assert comment["created_at"] is not None


def test_timestamp_updated_at_auto_set():
    cid     = Comment.create(content="Hello!")
    comment = Comment.get(id=cid)
    assert comment["updated_at"] is not None


def test_timestamp_updated_at_changes():
    cid = Comment.create(content="Hello!")
    time.sleep(1)
    Comment.update({"content": "Updated!"}, id=cid)
    comment = Comment.get(id=cid)
    assert comment["content"] == "Updated!"


def test_timestamp_no_user_fields():
    assert "created_by" not in Comment._fields
    assert "updated_by" not in Comment._fields


# ------------------------------------------------------------------ #
#  Exports                                                             #
# ------------------------------------------------------------------ #

def test_mixins_exported():
    from mydborm.mixins import SoftDeleteMixin, AuditMixin, TimestampMixin
    assert SoftDeleteMixin is not None
    assert AuditMixin is not None
    assert TimestampMixin is not None

def test_purge_all_deleted_empty():
    count = Post.purge_all_deleted()
    assert count == 0


def test_soft_delete_count_with_filter():
    Post.create(title="Alpha", content="x")
    Post.create(title="Beta",  content="y")
    assert Post.count(title="Alpha") == 1


def test_soft_delete_exists_true():
    pid = Post.create(title="Exists")
    assert Post.exists(id=pid) is True


def test_soft_delete_exists_false_after_delete():
    pid = Post.create(title="Gone")
    Post.soft_delete(id=pid)
    assert Post.exists(id=pid) is False


def test_audit_all_returns_list():
    Order.create(total=10.0)
    Order.create(total=20.0)
    rows = Order.all()
    assert len(rows) >= 2


def test_audit_filter_returns_matching():
    Order.create(total=999.0)
    rows = Order.filter(total=999.0)
    assert len(rows) >= 1


def test_timestamp_filter():
    cid = Comment.create(content="Hello")
    rows = Comment.filter(id=cid)
    assert len(rows) == 1


# ------------------------------------------------------------------ #
#  TimestampMixin.all (lines 383-384)                                 #
# ------------------------------------------------------------------ #

def test_timestamp_all_returns_list():
    """Comment.all() calls TimestampMixin.all (injected via __init_subclass__)."""
    Comment.create(content="First")
    Comment.create(content="Second")
    rows = Comment.all()  # lines 383-384
    assert len(rows) >= 2


# ------------------------------------------------------------------ #
#  AuditMixin.age() / was_updated() edge cases (312, 314, 322)       #
# ------------------------------------------------------------------ #

def test_audit_age_returns_none_when_no_created_at():
    """age() returns None when created_at is None (line 312)."""
    oid = Order.create(total=50.0)
    order = Order.get(id=oid)
    order._data["created_at"] = None
    assert order.age() is None  # line 312


def test_audit_age_with_string_created_at():
    """age() parses string created_at via strptime (line 314)."""
    oid = Order.create(total=50.0)
    order = Order.get(id=oid)
    order._data["created_at"] = "2024-01-01 00:00:00"
    age = order.age()  # line 314
    assert age is not None


def test_audit_was_updated_returns_false_when_none():
    """was_updated() returns False when created_at or updated_at is None (line 322)."""
    oid = Order.create(total=50.0)
    order = Order.get(id=oid)
    order._data["created_at"] = None
    assert order.was_updated() is False  # line 322


# ------------------------------------------------------------------ #
#  _add_col_to_db direct call (lines 26-34)                          #
# ------------------------------------------------------------------ #

def test_add_col_to_db_adds_missing_column():
    """_add_col_to_db adds a column when it's missing from the table."""
    from mydborm.mixins import _add_col_to_db
    table = "mx_bare_col_test"
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        cur.execute(f"CREATE TABLE {table} (id INT PRIMARY KEY)")
    # Column not in schema → should add it (lines 26-34)
    _add_col_to_db(table, "extra_col", "VARCHAR(100) NULL")
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute(f"DESCRIBE {table}")
        cols = [row[0] for row in cur.fetchall()]
    assert "extra_col" in cols
    with db.connect() as conn:
        conn.cursor().execute(f"DROP TABLE IF EXISTS {table}")


# ------------------------------------------------------------------ #
#  Mixin create_table via reversed MRO (90-93, 248-257, 362-365)    #
# ------------------------------------------------------------------ #

def test_soft_delete_mixin_create_table_direct():
    """SoftDeleteMixin.create_table is called when mixin comes first in MRO."""
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mx_test_soft")
    MixinTestSoft.create_table()  # lines 90-93
    assert "deleted_at" in MixinTestSoft._fields
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mx_test_soft")


def test_audit_mixin_create_table_direct():
    """AuditMixin.create_table is called when mixin comes first in MRO."""
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mx_test_audit")
    MixinTestAudit.create_table()  # lines 248-257
    assert "created_at" in MixinTestAudit._fields
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mx_test_audit")


def test_timestamp_mixin_create_table_direct():
    """TimestampMixin.create_table is called when mixin comes first in MRO."""
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mx_test_ts")
    MixinTestTS.create_table()  # lines 362-365
    assert "created_at" in MixinTestTS._fields
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mx_test_ts")