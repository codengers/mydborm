# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_lifecycle_hooks.py
# Project     : mydborm
# Version     : 1.4.0
# License     : MIT
# Description : Tests for lifecycle hooks — before/after create/update/delete
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField


# ------------------------------------------------------------------ #
#  Hook log helper                                                     #
# ------------------------------------------------------------------ #

class HookLog:
    """Captures hook calls for assertion."""
    def __init__(self):
        self.calls = []

    def record(self, event, **kwargs):
        self.calls.append({"event": event, **kwargs})

    def events(self):
        return [c["event"] for c in self.calls]

    def last(self):
        return self.calls[-1] if self.calls else None

    def clear(self):
        self.calls.clear()


log = HookLog()


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class HookUser(BaseModel):
    __tablename__ = "hk_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50,  nullable=False)
    email    = StrField(max_length=255, nullable=False)
    active   = BoolField(default=True)

    @classmethod
    def before_create(cls, data: dict) -> dict:
        log.record("before_create", data=dict(data))
        data["username"] = data["username"].lower().strip()
        return data

    @classmethod
    def after_create(cls, record_id: int, data: dict):
        log.record("after_create", record_id=record_id, data=dict(data))

    @classmethod
    def before_update(cls, data: dict, filters: dict) -> dict:
        log.record("before_update", data=dict(data), filters=dict(filters))
        if "username" in data:
            data["username"] = data["username"].lower()
        return data

    @classmethod
    def after_update(cls, rows_affected: int, data: dict, filters: dict):
        log.record("after_update", rows_affected=rows_affected,
                   data=dict(data), filters=dict(filters))

    @classmethod
    def before_delete(cls, filters: dict):
        log.record("before_delete", filters=dict(filters))

    @classmethod
    def after_delete(cls, rows_deleted: int, filters: dict):
        log.record("after_delete", rows_deleted=rows_deleted,
                   filters=dict(filters))


class NoHookUser(BaseModel):
    """Model with no hooks — verify hooks are optional."""
    __tablename__ = "hk_nohook"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50, nullable=False)


class MutationModel(BaseModel):
    """Model that modifies data in before hooks."""
    __tablename__ = "hk_mutation"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)
    score = FloatField(nullable=True)

    @classmethod
    def before_create(cls, data: dict) -> dict:
        data["name"]  = data["name"].title()
        data["score"] = round(data.get("score", 0.0) or 0.0, 2)
        return data

    @classmethod
    def before_update(cls, data: dict, filters: dict) -> dict:
        if "name" in data:
            data["name"] = data["name"].title()
        return data


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
    HookUser.create_table()
    NoHookUser.create_table()
    MutationModel.create_table()
    yield
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS hk_users")
        cur.execute("DROP TABLE IF EXISTS hk_nohook")
        cur.execute("DROP TABLE IF EXISTS hk_mutation")
    db.close()


@pytest.fixture(autouse=True)
def clean():
    log.clear()
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM hk_users")
        cur.execute("DELETE FROM hk_nohook")
        cur.execute("DELETE FROM hk_mutation")
    yield


# ------------------------------------------------------------------ #
#  before_create                                                       #
# ------------------------------------------------------------------ #

def test_before_create_fires():
    HookUser.create(username="alice", email="a@x.com")
    assert "before_create" in log.events()


def test_before_create_receives_data():
    HookUser.create(username="alice", email="a@x.com")
    call = next(c for c in log.calls if c["event"] == "before_create")
    assert "username" in call["data"]


def test_before_create_can_mutate_data():
    uid  = HookUser.create(username="  ALICE  ", email="a@x.com")
    user = HookUser.get(id=uid)
    assert user["username"] == "alice"


def test_before_create_mutation_persisted():
    uid  = HookUser.create(username="BOB", email="b@x.com")
    user = HookUser.get(id=uid)
    assert user["username"] == "bob"


def test_before_create_none_return_uses_original():
    class NoneReturnModel(BaseModel):
        __tablename__ = "hk_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=50, nullable=False)
        email    = StrField(max_length=255, nullable=False)
        active   = BoolField(default=True)

        @classmethod
        def before_create(cls, data):
            return None   # returning None should not crash

    uid = NoneReturnModel.create(username="test", email="t@x.com")
    assert uid > 0


# ------------------------------------------------------------------ #
#  after_create                                                        #
# ------------------------------------------------------------------ #

def test_after_create_fires():
    HookUser.create(username="alice", email="a@x.com")
    assert "after_create" in log.events()


def test_after_create_receives_record_id():
    uid = HookUser.create(username="alice", email="a@x.com")
    call = next(c for c in log.calls if c["event"] == "after_create")
    assert call["record_id"] == uid


def test_after_create_receives_data():
    HookUser.create(username="alice", email="a@x.com")
    call = next(c for c in log.calls if c["event"] == "after_create")
    assert "username" in call["data"]


def test_after_create_fires_after_insert():
    """after_create should fire only after DB insert succeeds."""
    uid = HookUser.create(username="carol", email="c@x.com")
    after_call = next(c for c in log.calls if c["event"] == "after_create")
    assert after_call["record_id"] > 0


# ------------------------------------------------------------------ #
#  before_update                                                       #
# ------------------------------------------------------------------ #

def test_before_update_fires():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.update({"username": "alice2"}, id=uid)
    assert "before_update" in log.events()


def test_before_update_receives_data_and_filters():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.update({"username": "UPDATED"}, id=uid)
    call = next(c for c in log.calls if c["event"] == "before_update")
    assert "username" in call["data"]
    assert "id" in call["filters"]


def test_before_update_can_mutate_data():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.update({"username": "ALICE_UPDATED"}, id=uid)
    user = HookUser.get(id=uid)
    assert user["username"] == "alice_updated"


# ------------------------------------------------------------------ #
#  after_update                                                        #
# ------------------------------------------------------------------ #

def test_after_update_fires():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.update({"username": "alice2"}, id=uid)
    assert "after_update" in log.events()


def test_after_update_receives_rows_affected():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.update({"active": False}, id=uid)
    call = next(c for c in log.calls if c["event"] == "after_update")
    assert call["rows_affected"] == 1


def test_after_update_zero_rows_when_no_match():
    log.clear()
    HookUser.update({"username": "ghost"}, id=99999)
    call = next(c for c in log.calls if c["event"] == "after_update")
    assert call["rows_affected"] == 0


# ------------------------------------------------------------------ #
#  before_delete                                                       #
# ------------------------------------------------------------------ #

def test_before_delete_fires():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.delete(id=uid)
    assert "before_delete" in log.events()


def test_before_delete_receives_filters():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.delete(id=uid)
    call = next(c for c in log.calls if c["event"] == "before_delete")
    assert call["filters"]["id"] == uid


# ------------------------------------------------------------------ #
#  after_delete                                                        #
# ------------------------------------------------------------------ #

def test_after_delete_fires():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.delete(id=uid)
    assert "after_delete" in log.events()


def test_after_delete_receives_rows_deleted():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.delete(id=uid)
    call = next(c for c in log.calls if c["event"] == "after_delete")
    assert call["rows_deleted"] == 1


def test_after_delete_zero_rows_when_no_match():
    log.clear()
    HookUser.delete(id=99999)
    call = next(c for c in log.calls if c["event"] == "after_delete")
    assert call["rows_deleted"] == 0


# ------------------------------------------------------------------ #
#  Hook order                                                          #
# ------------------------------------------------------------------ #

def test_hook_order_on_create():
    HookUser.create(username="alice", email="a@x.com")
    events = log.events()
    assert events.index("before_create") < events.index("after_create")


def test_hook_order_on_update():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.update({"active": False}, id=uid)
    events = log.events()
    assert events.index("before_update") < events.index("after_update")


def test_hook_order_on_delete():
    uid = HookUser.create(username="alice", email="a@x.com")
    log.clear()
    HookUser.delete(id=uid)
    events = log.events()
    assert events.index("before_delete") < events.index("after_delete")


# ------------------------------------------------------------------ #
#  Hooks are optional                                                  #
# ------------------------------------------------------------------ #

def test_no_hooks_model_works():
    uid = NoHookUser.create(username="alice")
    assert uid > 0
    NoHookUser.update({"username": "bob"}, id=uid)
    NoHookUser.delete(id=uid)
    assert NoHookUser.count() == 0


def test_partial_hooks_work():
    """Model with only some hooks defined should not crash."""
    class PartialHook(BaseModel):
        __tablename__ = "hk_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=50, nullable=False)
        email    = StrField(max_length=255, nullable=False)
        active   = BoolField(default=True)

        @classmethod
        def after_create(cls, record_id, data):
            log.record("partial_after_create", record_id=record_id)

    uid = PartialHook.create(username="alice", email="a@x.com")
    assert uid > 0
    assert "partial_after_create" in log.events()


# ------------------------------------------------------------------ #
#  Data mutation in hooks                                              #
# ------------------------------------------------------------------ #

def test_mutation_model_before_create():
    mid = MutationModel.create(name="john doe", score=3.14159)
    m   = MutationModel.get(id=mid)
    assert m["name"]  == "John Doe"
    assert m["score"] == 3.14


def test_mutation_model_before_update():
    mid = MutationModel.create(name="john doe", score=1.0)
    MutationModel.update({"name": "jane doe"}, id=mid)
    m = MutationModel.get(id=mid)
    assert m["name"] == "Jane Doe"


def test_multiple_creates_all_fire_hooks():
    for i in range(5):
        HookUser.create(username=f"user{i}", email=f"u{i}@x.com")
    before_events = [c for c in log.calls if c["event"] == "before_create"]
    after_events  = [c for c in log.calls if c["event"] == "after_create"]
    assert len(before_events) == 5
    assert len(after_events)  == 5