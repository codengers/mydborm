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
