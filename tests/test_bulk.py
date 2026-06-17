import os
# =============================================================================
# File        : tests/test_bulk.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.4.0
# License     : MIT
# Description : pytest tests for bulk operations — bulk_create,
#               bulk_update, bulk_delete with edge cases.
# =============================================================================

import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class Tag(BaseModel):
    __tablename__ = "tags"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=50, nullable=False)
    active = BoolField(default=True)
    score  = FloatField(nullable=False)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
    )
    Tag.create_table()
    yield
    Tag.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean_table():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM tags")
    yield


# ------------------------------------------------------------------ #
#  bulk_create                                                         #
# ------------------------------------------------------------------ #

def test_bulk_create_returns_count():
    count = Tag.bulk_create([
        {"name": "python", "active": True,  "score": 9.5},
        {"name": "mysql",  "active": True,  "score": 8.0},
        {"name": "orm",    "active": False, "score": 7.5},
    ])
    assert count == 3


def test_bulk_create_rows_exist():
    Tag.bulk_create([
        {"name": "alpha", "active": True, "score": 1.0},
        {"name": "beta",  "active": True, "score": 2.0},
    ])
    rows = Tag.all()
    assert len(rows) == 2
    names = {r["name"] for r in rows}
    assert names == {"alpha", "beta"}


def test_bulk_create_empty_list():
    count = Tag.bulk_create([])
    assert count == 0
    assert Tag.count() == 0


def test_bulk_create_single_record():
    count = Tag.bulk_create([
        {"name": "solo", "active": True, "score": 5.0}
    ])
    assert count == 1
    assert Tag.get(name="solo") is not None


def test_bulk_create_values_correct():
    Tag.bulk_create([
        {"name": "check", "active": False, "score": 3.14}
    ])
    row = Tag.query().where("name", "check").first()
    assert row["active"] == False
    assert abs(row["score"] - 3.14) < 0.01


def test_bulk_create_large_batch():
    records = [
        {"name": f"tag{i}", "active": True, "score": float(i)}
        for i in range(50)
    ]
    count = Tag.bulk_create(records)
    assert count == 50
    assert Tag.count() == 50


# ------------------------------------------------------------------ #
#  bulk_update                                                         #
# ------------------------------------------------------------------ #

def test_bulk_update_returns_count():
    Tag.bulk_create([
        {"name": "a", "active": True,  "score": 1.0},
        {"name": "b", "active": True,  "score": 2.0},
        {"name": "c", "active": False, "score": 3.0},
    ])
    rows   = Tag.all()
    ids    = [r["id"] for r in rows[:2]]
    updated = Tag.bulk_update([
        {"id": ids[0], "active": False},
        {"id": ids[1], "active": False},
    ])
    assert updated == 2


def test_bulk_update_values_correct():
    Tag.bulk_create([
        {"name": "x", "active": True, "score": 1.0},
        {"name": "y", "active": True, "score": 2.0},
    ])
    rows = Tag.all()
    Tag.bulk_update([
        {"id": rows[0]["id"], "score": 99.9},
        {"id": rows[1]["id"], "score": 88.8},
    ])
    r0 = Tag.get(id=rows[0]["id"])
    r1 = Tag.get(id=rows[1]["id"])
    assert abs(r0["score"] - 99.9) < 0.01
    assert abs(r1["score"] - 88.8) < 0.01


def test_bulk_update_empty_list():
    result = Tag.bulk_update([])
    assert result == 0


def test_bulk_update_missing_key_raises():
    with pytest.raises(ValueError, match="key field"):
        Tag.bulk_update([{"name": "no_id", "score": 1.0}])


def test_bulk_update_custom_key():
    Tag.bulk_create([
        {"name": "update_me", "active": True, "score": 1.0}
    ])
    Tag.bulk_update(
        [{"name": "update_me", "score": 55.5}],
        key="name"
    )
    row = Tag.query().where("name", "update_me").first()
    assert abs(row["score"] - 55.5) < 0.01


# ------------------------------------------------------------------ #
#  bulk_delete                                                         #
# ------------------------------------------------------------------ #

def test_bulk_delete_returns_count():
    Tag.bulk_create([
        {"name": "del1", "active": True, "score": 1.0},
        {"name": "del2", "active": True, "score": 2.0},
        {"name": "keep", "active": True, "score": 3.0},
    ])
    rows    = Tag.all()
    del_ids = [r["id"] for r in rows if r["name"] in ("del1", "del2")]
    deleted = Tag.bulk_delete(del_ids)
    assert deleted == 2


def test_bulk_delete_rows_removed():
    Tag.bulk_create([
        {"name": "gone1", "active": True, "score": 1.0},
        {"name": "gone2", "active": True, "score": 2.0},
        {"name": "stays", "active": True, "score": 3.0},
    ])
    rows    = Tag.all()
    del_ids = [r["id"] for r in rows if r["name"] != "stays"]
    Tag.bulk_delete(del_ids)
    remaining = Tag.all()
    assert len(remaining) == 1
    assert remaining[0]["name"] == "stays"


def test_bulk_delete_empty_list():
    Tag.bulk_create([{"name": "safe", "active": True, "score": 1.0}])
    deleted = Tag.bulk_delete([])
    assert deleted == 0
    assert Tag.count() == 1


def test_bulk_delete_custom_key():
    Tag.bulk_create([
        {"name": "rm1", "active": True, "score": 1.0},
        {"name": "rm2", "active": True, "score": 2.0},
        {"name": "ok",  "active": True, "score": 3.0},
    ])
    deleted = Tag.bulk_delete(["rm1", "rm2"], key="name")
    assert deleted == 2
    assert Tag.count() == 1
    assert Tag.query().where("name", "ok").exists()


def test_bulk_delete_nonexistent_ids():
    deleted = Tag.bulk_delete([99999, 88888])
    assert deleted == 0

