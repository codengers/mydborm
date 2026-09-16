import os
# =============================================================================
# File        : tests/test_cache.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : pytest tests for query-result caching — .cache(), automatic
#               invalidation on writes, clear_cache(), and interaction with
#               for_update().
# =============================================================================

import time

import pytest
from mydborm import db, BaseModel, IntField, StrField, query_cache


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class CacheItem(BaseModel):
    __tablename__ = "cache_items"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
    )
    CacheItem.create_table()
    yield
    CacheItem.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def seed_table():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM cache_items")
    query_cache.clear()
    CacheItem.create(name="Alice")
    CacheItem.create(name="Bob")
    yield
    query_cache.clear()


# ------------------------------------------------------------------ #
#  .cache() — hit/miss                                                 #
# ------------------------------------------------------------------ #

def test_cache_serves_stale_result_until_invalidated():
    first = CacheItem.query().cache(ttl=60).all()
    assert len(first) == 2

    # Direct SQL write bypasses ORM invalidation — cache should still
    # serve the stale (pre-write) result.
    with db.connect() as conn:
        conn.cursor().execute("INSERT INTO cache_items (name) VALUES ('Carol')")

    second = CacheItem.query().cache(ttl=60).all()
    assert len(second) == 2


def test_cache_first_hits_and_returns_same_row():
    first = CacheItem.query().where("name", "Alice").cache(ttl=60).first()
    assert first["name"] == "Alice"

    with db.connect() as conn:
        conn.cursor().execute("UPDATE cache_items SET name='Changed' WHERE name='Alice'")

    second = CacheItem.query().where("name", "Alice").cache(ttl=60).first()
    assert second["name"] == "Alice"


def test_cache_expires_after_ttl():
    CacheItem.query().cache(ttl=1).all()
    with db.connect() as conn:
        conn.cursor().execute("INSERT INTO cache_items (name) VALUES ('Carol')")
    time.sleep(1.2)

    rows = CacheItem.query().cache(ttl=1).all()
    assert len(rows) == 3


# ------------------------------------------------------------------ #
#  Automatic invalidation on ORM writes                                #
# ------------------------------------------------------------------ #

def test_orm_create_invalidates_cache():
    first = CacheItem.query().cache(ttl=60).all()
    assert len(first) == 2

    CacheItem.create(name="Carol")

    second = CacheItem.query().cache(ttl=60).all()
    assert len(second) == 3


def test_orm_update_invalidates_cache():
    CacheItem.query().cache(ttl=60).all()
    CacheItem.update({"name": "Updated"}, name="Alice")

    result = CacheItem.query().where("name", "Updated").cache(ttl=60).first()
    assert result is not None
    assert result["name"] == "Updated"


def test_orm_delete_invalidates_cache():
    CacheItem.query().cache(ttl=60).all()
    CacheItem.delete(name="Alice")

    rows = CacheItem.query().cache(ttl=60).all()
    assert len(rows) == 1


def test_bulk_create_invalidates_cache():
    CacheItem.query().cache(ttl=60).all()
    CacheItem.bulk_create([{"name": "Carol"}, {"name": "Dave"}])

    rows = CacheItem.query().cache(ttl=60).all()
    assert len(rows) == 4


# ------------------------------------------------------------------ #
#  Manual clear_cache()                                                #
# ------------------------------------------------------------------ #

def test_clear_cache_forces_refresh_after_raw_sql_write():
    first = CacheItem.query().cache(ttl=60).all()
    assert len(first) == 2

    with db.connect() as conn:
        conn.cursor().execute("INSERT INTO cache_items (name) VALUES ('Carol')")

    CacheItem.clear_cache()

    second = CacheItem.query().cache(ttl=60).all()
    assert len(second) == 3


# ------------------------------------------------------------------ #
#  for_update() takes precedence over cache()                          #
# ------------------------------------------------------------------ #

def test_for_update_bypasses_cache():
    CacheItem.query().cache(ttl=60).all()
    with db.connect() as conn:
        conn.cursor().execute("INSERT INTO cache_items (name) VALUES ('Carol')")

    with db.transaction() as conn:
        rows = CacheItem.query().cache(ttl=60).for_update().all()
    assert len(rows) == 3


# ------------------------------------------------------------------ #
#  Queries without .cache() are never cached                           #
# ------------------------------------------------------------------ #

def test_uncached_query_always_hits_db():
    CacheItem.query().all()
    with db.connect() as conn:
        conn.cursor().execute("INSERT INTO cache_items (name) VALUES ('Carol')")

    rows = CacheItem.query().all()
    assert len(rows) == 3
