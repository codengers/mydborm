# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_session.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.6.0
# License     : MIT
# Description : pytest tests for Session — identity map, change tracking,
#               unit of work, flush, rollback, delete, context manager.
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, Session
from mydborm.session import ObjectState, TrackedInstance


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class Member(BaseModel):
    __tablename__ = "session_members"
    id       = IntField(primary_key=True)
    name     = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False)
    active   = BoolField(default=True)


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
    Member.create_table()
    yield
    Member.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM session_members")
    yield


@pytest.fixture()
def seeded():
    m1 = Member.create(name="Alice", email="alice@x.com", active=True)
    m2 = Member.create(name="Bob",   email="bob@x.com",   active=True)
    m3 = Member.create(name="Carol", email="carol@x.com", active=False)
    return {"m1": m1, "m2": m2, "m3": m3}


# ------------------------------------------------------------------ #
#  Session basics                                                      #
# ------------------------------------------------------------------ #

def test_session_creation():
    s = Session()
    assert s is not None
    assert repr(s) == "<Session tracked=0 new=0 dirty=0 deleted=0>"


def test_session_stats_empty():
    s = Session()
    stats = s.stats()
    assert stats["tracked"] == 0
    assert stats["new"]     == 0
    assert stats["dirty"]   == 0
    assert stats["deleted"] == 0


def test_object_states():
    assert ObjectState.NEW      == "new"
    assert ObjectState.CLEAN    == "clean"
    assert ObjectState.DIRTY    == "dirty"
    assert ObjectState.DELETED  == "deleted"
    assert ObjectState.DETACHED == "detached"


# ------------------------------------------------------------------ #
#  Identity map                                                        #
# ------------------------------------------------------------------ #

def test_identity_map_same_object(seeded):
    s  = Session()
    u1 = s.get(Member, id=seeded["m1"])
    u2 = s.get(Member, id=seeded["m1"])
    assert u1 is u2


def test_identity_map_different_ids(seeded):
    s  = Session()
    u1 = s.get(Member, id=seeded["m1"])
    u2 = s.get(Member, id=seeded["m2"])
    assert u1 is not u2


def test_identity_map_returns_none_for_missing():
    s = Session()
    assert s.get(Member, id=99999) is None


def test_identity_map_cached_after_first_load(seeded):
    s     = Session()
    u1    = s.get(Member, id=seeded["m1"])
    stats = s.stats()
    assert stats["tracked"] == 1
    u2    = s.get(Member, id=seeded["m1"])
    assert s.stats()["tracked"] == 1


def test_all_registers_in_identity_map(seeded):
    s    = Session()
    rows = s.all(Member)
    assert len(rows) == 3
    assert s.stats()["tracked"] == 3


def test_filter_registers_in_identity_map(seeded):
    s    = Session()
    rows = s.filter(Member, active=True)
    assert len(rows) == 2
    assert s.stats()["tracked"] == 2


# ------------------------------------------------------------------ #
#  Change tracking                                                     #
# ------------------------------------------------------------------ #

def test_not_dirty_on_load(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    assert s.is_dirty(u) is False


def test_dirty_after_field_change(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    u["name"] = "Alice Updated"
    assert s.is_dirty(u) is True


def test_dirty_fields_list(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    u["name"]   = "New Name"
    u["active"] = False
    fields = s.dirty_fields(u)
    assert "name"   in fields
    assert "active" in fields


def test_original_value_preserved(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    u["name"] = "Changed"
    assert s.original_value(u, "name") == "Alice"


def test_multiple_field_changes(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    u["name"]   = "X"
    u["email"]  = "x@x.com"
    u["active"] = False
    assert len(s.dirty_fields(u)) == 3


# ------------------------------------------------------------------ #
#  Flush                                                               #
# ------------------------------------------------------------------ #

def test_flush_writes_dirty_to_db(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    u["name"] = "Flushed Name"
    s.flush()
    row = Member.get(id=seeded["m1"])
    assert row["name"] == "Flushed Name"


def test_flush_marks_clean_after_write(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    u["name"] = "Updated"
    s.flush()
    assert s.is_dirty(u) is False


def test_flush_inserts_new(seeded):
    s = Session()
    s.add(Member, name="Dave", email="dave@x.com", active=True)
    s.flush()
    assert Member.count() == 4
    assert Member.exists(name="Dave") is True


def test_flush_multiple_new(seeded):
    s = Session()
    s.add(Member, name="Eve",   email="eve@x.com",   active=True)
    s.add(Member, name="Frank", email="frank@x.com", active=False)
    s.flush()
    assert Member.count() == 5


def test_flush_empty_does_nothing():
    s = Session()
    s.flush()
    assert Member.count() == 0


# ------------------------------------------------------------------ #
#  Rollback                                                            #
# ------------------------------------------------------------------ #

def test_rollback_restores_value(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    u["name"] = "Will be rolled back"
    s.rollback()
    assert u["name"]      == "Alice"
    assert s.is_dirty(u)  is False


def test_rollback_clears_new():
    s = Session()
    s.add(Member, name="Ghost", email="ghost@x.com", active=True)
    s.rollback()
    assert s.stats()["new"] == 0
    assert Member.count()   == 0


def test_rollback_clears_deleted(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    s.delete(u)
    s.rollback()
    assert s.stats()["deleted"] == 0


def test_rollback_multiple_dirty(seeded):
    s = Session()
    u1 = s.get(Member, id=seeded["m1"])
    u2 = s.get(Member, id=seeded["m2"])
    u1["name"] = "Changed1"
    u2["name"] = "Changed2"
    s.rollback()
    assert u1["name"] == "Alice"
    assert u2["name"] == "Bob"


# ------------------------------------------------------------------ #
#  Delete                                                              #
# ------------------------------------------------------------------ #

def test_delete_removes_from_db(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    s.delete(u)
    s.flush()
    assert Member.get(id=seeded["m1"]) is None
    assert Member.count() == 2


def test_delete_removes_from_identity_map(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    s.delete(u)
    s.flush()
    assert s.stats()["tracked"] == 0


# ------------------------------------------------------------------ #
#  Context manager                                                     #
# ------------------------------------------------------------------ #

def test_context_manager_commits(seeded):
    with Session() as s:
        u = s.get(Member, id=seeded["m1"])
        u["name"] = "Context Updated"
    assert Member.get(id=seeded["m1"])["name"] == "Context Updated"


def test_context_manager_rollback_on_exception(seeded):
    try:
        with Session() as s:
            u = s.get(Member, id=seeded["m1"])
            u["name"] = "Will rollback"
            raise ValueError("simulated error")
    except ValueError:
        pass
    assert Member.get(id=seeded["m1"])["name"] == "Alice"


def test_context_manager_add_and_commit():
    with Session() as s:
        s.add(Member, name="CM User",
              email="cm@x.com", active=True)
    assert Member.exists(name="CM User") is True


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def test_expunge_removes_from_session(seeded):
    s = Session()
    u = s.get(Member, id=seeded["m1"])
    assert s.stats()["tracked"] == 1
    s.expunge(u)
    assert s.stats()["tracked"] == 0


def test_expunge_all(seeded):
    s = Session()
    s.all(Member)
    assert s.stats()["tracked"] == 3
    s.expunge_all()
    assert s.stats()["tracked"] == 0


def test_close_clears_session(seeded):
    s = Session()
    s.all(Member)
    s.close()
    assert s.stats()["tracked"] == 0
    assert s.stats()["new"]     == 0


def test_repr_updates_with_state(seeded):
    s = Session()
    s.all(Member)
    assert "tracked=3" in repr(s)