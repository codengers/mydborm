# =============================================================================
# File        : tests/test_chunked_bulk.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.5.0
# License     : MIT
# Description : pytest tests for chunked bulk operations — BulkResult,
#               chunked_bulk_create, chunked_bulk_update,
#               chunked_bulk_delete with retry and progress callback.
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm.bulk import (
    BulkResult,
    chunked_bulk_create,
    chunked_bulk_update,
    chunked_bulk_delete,
    _chunks,
)
from mydborm.exceptions import BulkInsertError, BulkUpdateError


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class Widget(BaseModel):
    __tablename__ = "widgets"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=50, nullable=False)
    price  = FloatField(nullable=False)
    active = BoolField(default=True)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1", port=3307,
        user="root",
        password=os.environ.get("DB_PASSWORD", "root"),
        database="testdb"
    )
    Widget.create_table()
    yield
    Widget.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM widgets")
    yield


# ------------------------------------------------------------------ #
#  _chunks helper                                                      #
# ------------------------------------------------------------------ #

def test_chunks_even():
    result = list(_chunks([1, 2, 3, 4, 6], 2))
    assert len(result) == 3
    assert result[0]   == [1, 2]
    assert result[2]   == [6]


def test_chunks_exact():
    result = list(_chunks([1, 2, 3, 4], 2))
    assert len(result) == 2


def test_chunks_larger_than_list():
    result = list(_chunks([1, 2, 3], 10))
    assert len(result) == 1
    assert result[0]   == [1, 2, 3]


def test_chunks_empty():
    result = list(_chunks([], 10))
    assert result == []


# ------------------------------------------------------------------ #
#  BulkResult                                                          #
# ------------------------------------------------------------------ #

def test_bulk_result_init():
    r = BulkResult("insert", 100)
    assert r.operation == "insert"
    assert r.total     == 100
    assert r.inserted  == 0
    assert r.failed    == 0
    assert r.chunks    == 0
    assert r.retries   == 0
    assert r.errors    == []


def test_bulk_result_success_rate_full():
    r = BulkResult("insert", 100)
    r.inserted = 100
    assert r.success_rate == 100.0


def test_bulk_result_success_rate_partial():
    r = BulkResult("insert", 100)
    r.inserted = 90
    r.failed   = 10
    assert r.success_rate == 90.0


def test_bulk_result_success_rate_zero_total():
    r = BulkResult("insert", 0)
    assert r.success_rate == 100.0


def test_bulk_result_has_errors_false():
    r = BulkResult("insert", 10)
    assert r.has_errors is False


def test_bulk_result_has_errors_true():
    r = BulkResult("insert", 10)
    r.add_error(1, [{"name": "x"}], Exception("failed"))
    assert r.has_errors is True
    assert r.failed     == 1


def test_bulk_result_repr():
    r = BulkResult("insert", 100)
    r.inserted = 100
    r.finish()
    assert "BulkResult" in repr(r)
    assert "insert"     in repr(r)


def test_bulk_result_summary():
    r = BulkResult("insert", 100)
    r.inserted = 98
    r.failed   = 2
    r.chunks   = 2
    r.finish()
    s = r.summary()
    assert "Total     : 100" in s
    assert "Inserted  : 98"  in s
    assert "Failed    : 2"   in s


# ------------------------------------------------------------------ #
#  chunked_bulk_create                                                 #
# ------------------------------------------------------------------ #

def test_chunked_create_basic():
    records = [{"name": f"w{i}", "price": float(i), "active": True}
               for i in range(10)]
    result  = chunked_bulk_create(Widget, records, chunk_size=5)
    assert result.inserted    == 10
    assert result.failed      == 0
    assert result.chunks      == 2
    assert result.success_rate == 100.0
    assert Widget.count()     == 10


def test_chunked_create_single_chunk():
    records = [{"name": f"w{i}", "price": float(i), "active": True}
               for i in range(5)]
    result  = chunked_bulk_create(Widget, records, chunk_size=100)
    assert result.chunks   == 1
    assert result.inserted == 5


def test_chunked_create_empty():
    result = chunked_bulk_create(Widget, [], chunk_size=100)
    assert result.inserted == 0
    assert result.total    == 0
    assert result.chunks   == 0


def test_chunked_create_large_batch():
    records = [{"name": f"item{i}", "price": float(i), "active": True}
               for i in range(1000)]
    result  = chunked_bulk_create(Widget, records, chunk_size=200)
    assert result.inserted == 1000
    assert result.chunks   == 5
    assert Widget.count()  == 1000


def test_chunked_create_progress_callback():
    records   = [{"name": f"w{i}", "price": float(i), "active": True}
                 for i in range(50)]
    progress  = []

    def on_progress(done, total):
        progress.append((done, total))

    chunked_bulk_create(Widget, records, chunk_size=20,
                        on_progress=on_progress)
    assert len(progress) == 3
    assert progress[-1]  == (50, 50)


def test_chunked_create_duration_recorded():
    records = [{"name": f"w{i}", "price": float(i), "active": True}
               for i in range(10)]
    result  = chunked_bulk_create(Widget, records)
    assert result.duration > 0


# ------------------------------------------------------------------ #
#  chunked_bulk_update                                                 #
# ------------------------------------------------------------------ #

def test_chunked_update_basic():
    Widget.bulk_create([
        {"name": f"w{i}", "price": float(i), "active": True}
        for i in range(10)
    ])
    rows    = Widget.all()
    updates = [{"id": r["id"], "active": False} for r in rows]
    result  = chunked_bulk_update(Widget, updates, chunk_size=5)
    assert result.updated      == 10
    assert result.failed       == 0
    assert result.chunks       == 2
    assert result.success_rate == 100.0


def test_chunked_update_empty():
    result = chunked_bulk_update(Widget, [], chunk_size=100)
    assert result.updated == 0
    assert result.total   == 0


def test_chunked_update_progress_callback():
    Widget.bulk_create([
        {"name": f"u{i}", "price": float(i), "active": True}
        for i in range(30)
    ])
    rows     = Widget.all()
    updates  = [{"id": r["id"], "price": 99.9} for r in rows]
    progress = []

    def on_progress(done, total):
        progress.append((done, total))

    chunked_bulk_update(Widget, updates, chunk_size=10,
                        on_progress=on_progress)
    assert len(progress) == 3
    assert progress[-1]  == (30, 30)


# ------------------------------------------------------------------ #
#  chunked_bulk_delete                                                 #
# ------------------------------------------------------------------ #

def test_chunked_delete_basic():
    Widget.bulk_create([
        {"name": f"d{i}", "price": float(i), "active": True}
        for i in range(10)
    ])
    ids    = [r["id"] for r in Widget.all()]
    result = chunked_bulk_delete(Widget, ids, chunk_size=5)
    assert result.deleted      == 10
    assert result.failed       == 0
    assert result.chunks       == 2
    assert result.success_rate == 100.0
    assert Widget.count()      == 0


def test_chunked_delete_empty():
    result = chunked_bulk_delete(Widget, [], chunk_size=100)
    assert result.deleted == 0
    assert result.total   == 0


def test_chunked_delete_partial():
    Widget.bulk_create([
        {"name": f"p{i}", "price": float(i), "active": True}
        for i in range(6)
    ])
    rows   = Widget.all()
    del_ids = [r["id"] for r in rows[:3]]
    result  = chunked_bulk_delete(Widget, del_ids, chunk_size=10)
    assert result.deleted  == 3
    assert Widget.count()  == 3


def test_chunked_delete_progress_callback():
    Widget.bulk_create([
        {"name": f"dp{i}", "price": float(i), "active": True}
        for i in range(20)
    ])
    ids      = [r["id"] for r in Widget.all()]
    progress = []

    def on_progress(done, total):
        progress.append((done, total))

    chunked_bulk_delete(Widget, ids, chunk_size=10,
                        on_progress=on_progress)
    assert len(progress) == 2
    assert progress[-1]  == (20, 20)


# ------------------------------------------------------------------ #
#  Retry logic                                                         #
# ------------------------------------------------------------------ #

def test_retry_succeeds_on_second_attempt():
    """Simulate a function that fails once then succeeds."""
    from mydborm.bulk import _with_retry
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 2:
            raise Exception("temporary failure")
        return "success"

    result = _with_retry(flaky, retries=2, retry_delay=0.01)
    assert result      == "success"
    assert len(attempts) == 2


def test_retry_exhausted_raises():
    from mydborm.bulk import _with_retry

    def always_fails():
        raise Exception("always fails")

    with pytest.raises(Exception, match="always fails"):
        _with_retry(always_fails, retries=2, retry_delay=0.01)


def test_no_retry_raises_immediately():
    from mydborm.bulk import _with_retry
    attempts = []

    def fails():
        attempts.append(1)
        raise Exception("fail")

    with pytest.raises(Exception):
        _with_retry(fails, retries=0, retry_delay=0.01)

    assert len(attempts) == 1