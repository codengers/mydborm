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