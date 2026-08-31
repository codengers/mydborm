# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_sqlite_async.py
# Project     : mydborm
# License     : MIT
# Description : pytest-asyncio tests for AsyncConnectionManager and
#               AsyncBaseModel against SQLite (aiosqlite). SQLite is
#               stdlib + aiosqlite, no external service, so these tests
#               are never skipped.
# =============================================================================

import os
import tempfile

import pytest
import pytest_asyncio

from mydborm.async_db import AsyncBaseModel, async_db
from mydborm.fields import BoolField, FloatField, IntField, StrField

# ------------------------------------------------------------------ #
#  Async test model                                                    #
# ------------------------------------------------------------------ #

class AsyncSLProduct(AsyncBaseModel):
    __tablename__ = "async_sl_products"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=100, nullable=False)
    price  = FloatField(nullable=False)
    active = BoolField(default=True)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture(autouse=True)
async def setup_async_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)

    await async_db.configure(dialect="sqlite", database=path)
    await AsyncSLProduct.create_table()
    yield
    await async_db.close()
    if os.path.exists(path):
        os.remove(path)


# ------------------------------------------------------------------ #
#  AsyncConnectionManager                                              #
# ------------------------------------------------------------------ #

async def test_async_db_repr_sqlite():
    r = repr(async_db)
    assert "AsyncConnectionManager" in r
    assert "sqlite" in r


async def test_async_connect_sqlite():
    async with async_db.connect() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            row = await cur.fetchone()
            assert row[0] == 1


async def test_async_fetchall_sqlite():
    rows = await async_db.fetchall("SELECT 1 AS num, 'hello' AS msg")
    assert len(rows) == 1
    assert rows[0]["num"] == 1
    assert rows[0]["msg"] == "hello"


async def test_async_fetchone_sqlite():
    row = await async_db.fetchone("SELECT 42 AS answer")
    assert row is not None
    assert row["answer"] == 42


async def test_async_fetchone_none_sqlite():
    row = await async_db.fetchone(
        "SELECT * FROM async_sl_products WHERE id = %s", [99999]
    )
    assert row is None


async def test_async_execute_sqlite():
    affected = await async_db.execute(
        "INSERT INTO async_sl_products (name, price, active) "
        "VALUES (%s, %s, %s)",
        ["Test", 9.99, True]
    )
    assert affected == 1


# ------------------------------------------------------------------ #
#  AsyncBaseModel — create                                             #
# ------------------------------------------------------------------ #

async def test_async_create_sqlite():
    pid = await AsyncSLProduct.create(name="Widget", price=9.99, active=True)
    assert isinstance(pid, int)
    assert pid > 0


async def test_async_create_multiple_sqlite():
    p1 = await AsyncSLProduct.create(name="A", price=1.0, active=True)
    p2 = await AsyncSLProduct.create(name="B", price=2.0, active=True)
    assert p1 != p2


# ------------------------------------------------------------------ #
#  AsyncBaseModel — read                                               #
# ------------------------------------------------------------------ #

async def test_async_all_sqlite():
    await AsyncSLProduct.create(name="P1", price=1.0, active=True)
    await AsyncSLProduct.create(name="P2", price=2.0, active=True)
    rows = await AsyncSLProduct.all()
    assert len(rows) == 2


async def test_async_get_sqlite():
    pid = await AsyncSLProduct.create(name="Findme", price=5.0, active=True)
    row = await AsyncSLProduct.get(id=pid)
    assert row is not None
    assert row["name"] == "Findme"


async def test_async_get_none_sqlite():
    row = await AsyncSLProduct.get(id=99999)
    assert row is None


async def test_async_filter_sqlite():
    await AsyncSLProduct.create(name="Active1", price=1.0, active=True)
    await AsyncSLProduct.create(name="Active2", price=2.0, active=True)
    await AsyncSLProduct.create(name="Inactive", price=3.0, active=False)
    rows = await AsyncSLProduct.filter(active=True)
    assert len(rows) == 2


async def test_async_count_sqlite():
    await AsyncSLProduct.create(name="C1", price=1.0, active=True)
    await AsyncSLProduct.create(name="C2", price=2.0, active=True)
    assert await AsyncSLProduct.count() == 2


# ------------------------------------------------------------------ #
#  AsyncBaseModel — update / delete                                    #
# ------------------------------------------------------------------ #

async def test_async_update_sqlite():
    pid = await AsyncSLProduct.create(name="Old", price=1.0, active=True)
    await AsyncSLProduct.update({"price": 2.5}, id=pid)
    row = await AsyncSLProduct.get(id=pid)
    assert row["price"] == 2.5


async def test_async_delete_sqlite():
    pid = await AsyncSLProduct.create(name="ToDelete", price=1.0, active=True)
    await AsyncSLProduct.delete(id=pid)
    row = await AsyncSLProduct.get(id=pid)
    assert row is None


# ------------------------------------------------------------------ #
#  Pool close / reconnect                                              #
# ------------------------------------------------------------------ #

async def test_async_close_and_reuse_sqlite():
    await AsyncSLProduct.create(name="BeforeClose", price=1.0, active=True)
    await async_db.close()
    # configure() re-creates the pool/connection transparently
    await async_db.configure(dialect="sqlite", database=async_db._config["database"])
    rows = await AsyncSLProduct.all()
    assert len(rows) == 1


# ------------------------------------------------------------------ #
#  AsyncQueryBuilder                                                    #
# ------------------------------------------------------------------ #

async def _seed_sl_products():
    await AsyncSLProduct.create(name="Apple",  price=1.50, active=True)
    await AsyncSLProduct.create(name="Banana", price=0.75, active=True)
    await AsyncSLProduct.create(name="Cherry", price=3.00, active=False)


async def test_async_query_where_sqlite():
    await _seed_sl_products()
    rows = await AsyncSLProduct.query().where("active", True).order_by("price").all()
    assert [r["name"] for r in rows] == ["Banana", "Apple"]


async def test_async_query_aggregates_sqlite():
    await _seed_sl_products()
    assert await AsyncSLProduct.query().count() == 3
    total = await AsyncSLProduct.query().sum("price")
    assert abs(total - 5.25) < 0.01


async def test_async_query_update_delete_sqlite():
    await _seed_sl_products()
    affected = await AsyncSLProduct.query().where("active", False).update(active=True)
    assert affected == 1
    deleted = await AsyncSLProduct.query().where("name", "Banana").delete()
    assert deleted == 1
    assert await AsyncSLProduct.count() == 2


async def test_async_query_paginate_sqlite():
    await _seed_sl_products()
    page = await AsyncSLProduct.query().order_by("price").paginate(page=2, per_page=2)
    assert page["total"] == 3
    assert page["pages"] == 2
    assert len(page["data"]) == 1


async def test_async_query_subquery_escapes_quote_sqlite():
    await _seed_sl_products()
    await AsyncSLProduct.create(name="O'Brien", price=2.0, active=True)
    sq = AsyncSLProduct.query().where("name", "O'Brien").subquery("id")
    assert "O''Brien" in sq
    rows = await AsyncSLProduct.query().where("id__in", sq).all()
    assert len(rows) == 1
    assert rows[0]["name"] == "O'Brien"


async def test_async_query_invalid_identifier_rejected_sqlite():
    with pytest.raises(ValueError, match="Invalid field name"):
        AsyncSLProduct.query().order_by("id; DROP TABLE async_sl_products; --")


# ------------------------------------------------------------------ #
#  Async transactions                                                   #
# ------------------------------------------------------------------ #

async def test_async_transaction_commits_sqlite():
    async with async_db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO async_sl_products (name, price, active) VALUES (%s,%s,%s)",
                ["TxCommit", 1.0, True],
            )
    rows = await AsyncSLProduct.filter(name="TxCommit")
    assert len(rows) == 1


async def test_async_transaction_rolls_back_sqlite():
    with pytest.raises(ValueError):
        async with async_db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO async_sl_products (name, price, active) VALUES (%s,%s,%s)",
                    ["TxRollback", 1.0, True],
                )
            raise ValueError("boom")
    rows = await AsyncSLProduct.filter(name="TxRollback")
    assert len(rows) == 0


async def test_async_savepoint_partial_rollback_sqlite():
    async with async_db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO async_sl_products (name, price, active) VALUES (%s,%s,%s)",
                ["Alice", 1.0, True],
            )
        try:
            async with async_db.savepoint(conn):
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO async_sl_products (name, price, active) VALUES (%s,%s,%s)",
                        ["Bob", 1.0, True],
                    )
                raise ValueError("bob failed")
        except ValueError:
            pass
    assert len(await AsyncSLProduct.filter(name="Alice")) == 1
    assert len(await AsyncSLProduct.filter(name="Bob")) == 0


# ------------------------------------------------------------------ #
#  Async bulk operations                                               #
# ------------------------------------------------------------------ #

async def test_async_bulk_create_update_delete_sqlite():
    n = await AsyncSLProduct.bulk_create([
        {"name": "A", "price": 1.0, "active": True},
        {"name": "B", "price": 2.0, "active": True},
    ])
    assert n == 2
    rows = await AsyncSLProduct.all()
    ids = [r["id"] for r in rows]
    n = await AsyncSLProduct.bulk_update([{"id": ids[0], "price": 9.0}])
    assert n == 1
    n = await AsyncSLProduct.bulk_delete(ids)
    assert n == 2
