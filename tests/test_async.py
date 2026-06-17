# =============================================================================
# File        : tests/test_async.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.4.0
# License     : MIT
# Description : pytest-asyncio tests for AsyncConnectionManager and
#               AsyncBaseModel — covers configure, connect, raw SQL,
#               and full async CRUD operations.
# =============================================================================

import pytest
import pytest_asyncio
from mydborm.async_db import async_db, AsyncBaseModel
from mydborm.fields import IntField, StrField, BoolField, FloatField


# ------------------------------------------------------------------ #
#  Async test model                                                    #
# ------------------------------------------------------------------ #

class AsyncProduct(AsyncBaseModel):
    __tablename__ = "async_products"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=100, nullable=False)
    price  = FloatField(nullable=False)
    active = BoolField(default=True)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest_asyncio.fixture(autouse=True)
async def setup_async_db():
    await async_db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password="root", database="testdb"
    )
    await AsyncProduct.create_table()
    await async_db.execute("DELETE FROM async_products")
    yield
    await AsyncProduct.drop_table()
    await async_db.close()


# ------------------------------------------------------------------ #
#  AsyncConnectionManager                                              #
# ------------------------------------------------------------------ #

async def test_async_db_repr():
    r = repr(async_db)
    assert "AsyncConnectionManager" in r
    assert "mysql" in r


async def test_async_connect():
    async with async_db.connect() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            row = await cur.fetchone()
            assert row[0] == 1


async def test_async_fetchall():
    rows = await async_db.fetchall("SELECT 1 AS num, 'hello' AS msg")
    assert len(rows) == 1
    assert rows[0]["num"] == 1
    assert rows[0]["msg"] == "hello"


async def test_async_fetchone():
    row = await async_db.fetchone("SELECT 42 AS answer")
    assert row is not None
    assert row["answer"] == 42


async def test_async_fetchone_none():
    row = await async_db.fetchone(
        "SELECT * FROM async_products WHERE id = %s", [99999]
    )
    assert row is None


async def test_async_execute():
    affected = await async_db.execute(
        "INSERT INTO async_products (name, price, active) "
        "VALUES (%s, %s, %s)",
        ["Test", 9.99, True]
    )
    assert affected == 1


# ------------------------------------------------------------------ #
#  AsyncBaseModel — create                                             #
# ------------------------------------------------------------------ #

async def test_async_create():
    pid = await AsyncProduct.create(
        name="Widget", price=9.99, active=True
    )
    assert isinstance(pid, int)
    assert pid > 0


async def test_async_create_multiple():
    p1 = await AsyncProduct.create(name="A", price=1.0, active=True)
    p2 = await AsyncProduct.create(name="B", price=2.0, active=True)
    assert p1 != p2


# ------------------------------------------------------------------ #
#  AsyncBaseModel — read                                               #
# ------------------------------------------------------------------ #

async def test_async_all():
    await AsyncProduct.create(name="P1", price=1.0, active=True)
    await AsyncProduct.create(name="P2", price=2.0, active=True)
    rows = await AsyncProduct.all()
    assert len(rows) == 2


async def test_async_all_empty():
    rows = await AsyncProduct.all()
    assert rows == []


async def test_async_get():
    pid = await AsyncProduct.create(
        name="Findme", price=5.0, active=True
    )
    row = await AsyncProduct.get(id=pid)
    assert row is not None
    assert row["name"] == "Findme"


async def test_async_get_none():
    row = await AsyncProduct.get(id=99999)
    assert row is None


async def test_async_filter():
    await AsyncProduct.create(name="Active1", price=1.0, active=True)
    await AsyncProduct.create(name="Active2", price=2.0, active=True)
    await AsyncProduct.create(name="Inactive", price=3.0, active=False)
    rows = await AsyncProduct.filter(active=True)
    assert len(rows) == 2
    assert all(r["active"] for r in rows)


async def test_async_count():
    await AsyncProduct.create(name="C1", price=1.0, active=True)
    await AsyncProduct.create(name="C2", price=2.0, active=True)
    assert await AsyncProduct.count() == 2


async def test_async_count_filtered():
    await AsyncProduct.create(name="X1", price=1.0, active=True)
    await AsyncProduct.create(name="X2", price=2.0, active=False)
    assert await AsyncProduct.count(active=True) == 1


# ------------------------------------------------------------------ #
#  AsyncBaseModel — update                                             #
# ------------------------------------------------------------------ #

async def test_async_update():
    pid = await AsyncProduct.create(
        name="Old", price=5.0, active=True
    )
    affected = await AsyncProduct.update({"name": "New"}, id=pid)
    assert affected == 1
    row = await AsyncProduct.get(id=pid)
    assert row["name"] == "New"


async def test_async_update_multiple_fields():
    pid = await AsyncProduct.create(
        name="Before", price=1.0, active=True
    )
    await AsyncProduct.update(
        {"name": "After", "price": 99.9, "active": False},
        id=pid
    )
    row = await AsyncProduct.get(id=pid)
    assert row["name"] == "After"
    assert abs(row["price"] - 99.9) < 0.01
    assert not row["active"]


# ------------------------------------------------------------------ #
#  AsyncBaseModel — delete                                             #
# ------------------------------------------------------------------ #

async def test_async_delete():
    pid = await AsyncProduct.create(
        name="DeleteMe", price=1.0, active=True
    )
    deleted = await AsyncProduct.delete(id=pid)
    assert deleted == 1
    assert await AsyncProduct.get(id=pid) is None


async def test_async_delete_nonexistent():
    deleted = await AsyncProduct.delete(id=99999)
    assert deleted == 0


# ------------------------------------------------------------------ #
#  Full async workflow                                                  #
# ------------------------------------------------------------------ #

async def test_async_full_workflow():
    """End-to-end async CRUD in one test."""
    pid = await AsyncProduct.create(
        name="Flow", price=10.0, active=True
    )
    assert await AsyncProduct.count() == 1

    row = await AsyncProduct.get(id=pid)
    assert row["name"] == "Flow"

    await AsyncProduct.update({"price": 20.0}, id=pid)
    updated = await AsyncProduct.get(id=pid)
    assert abs(updated["price"] - 20.0) < 0.01

    await AsyncProduct.delete(id=pid)
    assert await AsyncProduct.count() == 0
