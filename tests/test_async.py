import os
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
        port=3307, user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
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


# ------------------------------------------------------------------ #
#  AsyncQueryBuilder                                                    #
# ------------------------------------------------------------------ #

async def _seed_products():
    await AsyncProduct.create(name="Apple",      price=1.50, active=True)
    await AsyncProduct.create(name="Banana",     price=0.75, active=True)
    await AsyncProduct.create(name="Cherry",     price=3.00, active=False)
    await AsyncProduct.create(name="Date",       price=5.00, active=True)
    await AsyncProduct.create(name="Elderberry", price=8.00, active=False)


async def test_async_query_where():
    await _seed_products()
    rows = await AsyncProduct.query().where("active", True).all()
    assert len(rows) == 3
    assert all(r["active"] for r in rows)


async def test_async_query_where_operator():
    await _seed_products()
    rows = await AsyncProduct.query().where("price__gt", 3.0).all()
    names = {r["name"] for r in rows}
    assert names == {"Date", "Elderberry"}


async def test_async_query_where_in():
    await _seed_products()
    rows = await AsyncProduct.query().where("name__in", ["Apple", "Date"]).all()
    assert len(rows) == 2


async def test_async_query_or_where():
    await _seed_products()
    rows = (await AsyncProduct.query()
                  .or_where("name", "Apple")
                  .or_where("name", "Banana")
                  .all())
    names = {r["name"] for r in rows}
    assert names == {"Apple", "Banana"}


async def test_async_query_order_by():
    await _seed_products()
    rows = await AsyncProduct.query().order_by("price", desc=True).all()
    prices = [r["price"] for r in rows]
    assert prices == sorted(prices, reverse=True)


async def test_async_query_limit_offset():
    await _seed_products()
    rows = await AsyncProduct.query().order_by("price").limit(2).offset(1).all()
    assert len(rows) == 2


async def test_async_query_first():
    await _seed_products()
    row = await AsyncProduct.query().order_by("price").first()
    assert row["name"] == "Banana"


async def test_async_query_first_none():
    row = await AsyncProduct.query().where("name", "Nonexistent").first()
    assert row is None


async def test_async_query_count():
    await _seed_products()
    assert await AsyncProduct.query().where("active", True).count() == 3


async def test_async_query_exists():
    await _seed_products()
    assert await AsyncProduct.query().where("name", "Apple").exists() is True
    assert await AsyncProduct.query().where("name", "Nope").exists() is False


async def test_async_query_sum_avg_min_max():
    await _seed_products()
    total = await AsyncProduct.query().sum("price")
    assert abs(total - 18.25) < 0.01
    avg = await AsyncProduct.query().where("active", True).avg("price")
    assert abs(avg - (1.50 + 0.75 + 5.00) / 3) < 0.01
    assert await AsyncProduct.query().min("price") == 0.75
    assert await AsyncProduct.query().max("price") == 8.00


async def test_async_query_update():
    await _seed_products()
    affected = await AsyncProduct.query().where("active", False).update(active=True)
    assert affected == 2
    assert await AsyncProduct.query().where("active", True).count() == 5


async def test_async_query_delete():
    await _seed_products()
    deleted = await AsyncProduct.query().where("active", False).delete()
    assert deleted == 2
    assert await AsyncProduct.count() == 3


async def test_async_query_paginate():
    await _seed_products()
    page = await AsyncProduct.query().order_by("price").paginate(page=1, per_page=2)
    assert page["total"] == 5
    assert page["pages"] == 3
    assert len(page["data"]) == 2


async def test_async_query_select_columns():
    await _seed_products()
    rows = await AsyncProduct.query().select("name").all()
    assert "name" in rows[0]


async def test_async_query_distinct():
    await AsyncProduct.create(name="Dup", price=1.0, active=True)
    await AsyncProduct.create(name="Dup", price=1.0, active=True)
    rows = await AsyncProduct.query().select("name").distinct().all()
    assert len(rows) == 1


async def test_async_query_repr():
    r = repr(AsyncProduct.query().where("active", True))
    assert "AsyncQueryBuilder" in r
    assert "active" in r


async def test_async_query_invalid_identifier_rejected():
    with pytest.raises(ValueError, match="Invalid field name"):
        AsyncProduct.query().where("id; DROP TABLE async_products; --", 1)


async def test_async_query_subquery_escapes_injection():
    await _seed_products()
    payload = "nonexistent' OR '1'='1"
    sq = AsyncProduct.query().where("name", payload).subquery("id")
    assert "''1''=''1" in sq
    rows = await AsyncProduct.query().where("id__in", sq).all()
    assert rows == []


async def test_async_query_include_not_implemented():
    with pytest.raises(NotImplementedError):
        await AsyncProduct.query().include("something").all()


async def test_async_query_count_with_group_by():
    await _seed_products()
    # 2 groups: active=True, active=False
    total = await AsyncProduct.query().group_by("active").count()
    assert total == 2


async def test_async_query_update_with_or_where():
    await _seed_products()
    affected = (await AsyncProduct.query()
                      .or_where("name", "Apple")
                      .or_where("name", "Banana")
                      .update(active=False))
    assert affected == 2


async def test_async_query_delete_with_or_where():
    await _seed_products()
    deleted = (await AsyncProduct.query()
                     .or_where("name", "Apple")
                     .or_where("name", "Banana")
                     .delete())
    assert deleted == 2
    assert await AsyncProduct.count() == 3


async def test_async_query_update_no_kwargs_is_noop():
    await _seed_products()
    affected = await AsyncProduct.query().where("active", True).update()
    assert affected == 0


async def test_async_query_paginate_clamps_page_below_one():
    await _seed_products()
    page = await AsyncProduct.query().order_by("price").paginate(page=0, per_page=2)
    assert page["page"] == 1


# ------------------------------------------------------------------ #
#  Async transactions                                                   #
# ------------------------------------------------------------------ #

async def test_async_transaction_commits():
    async with async_db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                ["TxCommit", 1.0, True],
            )
    assert await AsyncProduct.count(name="TxCommit") == 1


async def test_async_transaction_rolls_back():
    with pytest.raises(ValueError):
        async with async_db.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                    ["TxRollback", 1.0, True],
                )
            raise ValueError("boom")
    assert await AsyncProduct.count(name="TxRollback") == 0


async def test_async_savepoint_partial_rollback():
    async with async_db.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                ["Alice", 1.0, True],
            )
        try:
            async with async_db.savepoint(conn):
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                        ["Bob", 1.0, True],
                    )
                raise ValueError("bob failed")
        except ValueError:
            pass
    assert await AsyncProduct.count(name="Alice") == 1
    assert await AsyncProduct.count(name="Bob") == 0


async def test_async_nested_transaction_with_conn_uses_savepoint():
    async with async_db.transaction() as conn:
        async with async_db.nested_transaction(conn):
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                    ["Nested", 1.0, True],
                )
    assert await AsyncProduct.count(name="Nested") == 1


async def test_async_nested_transaction_without_conn_starts_new():
    async with async_db.nested_transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                ["Fresh", 1.0, True],
            )
    assert await AsyncProduct.count(name="Fresh") == 1


async def test_async_bulk_transaction_commits():
    async with async_db.bulk_transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                ["Bulk1", 1.0, True],
            )
            await cur.execute(
                "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                ["Bulk2", 1.0, True],
            )
    assert await AsyncProduct.count() == 2


async def test_async_transaction_with_retry_success():
    async def do_insert(conn):
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                ["Retried", 1.0, True],
            )
    await async_db.transaction_with_retry(do_insert, retries=3)
    assert await AsyncProduct.count(name="Retried") == 1


async def test_async_transaction_with_retry_raises_on_non_retryable():
    async def do_fail(conn):
        raise ValueError("invalid input")
    with pytest.raises(ValueError, match="invalid input"):
        await async_db.transaction_with_retry(do_fail, retries=2)


async def test_async_transaction_with_retry_recovers_from_connection_loss():
    attempts = []

    async def do_transfer(conn):
        attempts.append(1)
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO async_products (name, price, active) VALUES (%s,%s,%s)",
                ["GoneAway", 1.0, True],
            )
        if len(attempts) < 3:
            raise RuntimeError("MySQL server has gone away")

    await async_db.transaction_with_retry(do_transfer, retries=3, retry_delay=0.01)
    assert len(attempts) == 3
    assert await AsyncProduct.count(name="GoneAway") == 1


async def test_async_transaction_with_retry_exhausted_raises():
    from mydborm.exceptions import RetryExhaustedError

    async def always_fails(conn):
        raise RuntimeError("Deadlock found when trying to get lock")

    with pytest.raises(RetryExhaustedError) as exc_info:
        await async_db.transaction_with_retry(always_fails, retries=2, retry_delay=0.01)
    assert exc_info.value.attempts == 3


# ------------------------------------------------------------------ #
#  Async lifecycle hooks                                                #
# ------------------------------------------------------------------ #

hook_calls = []


class AsyncHookProduct(AsyncBaseModel):
    __tablename__ = "async_hook_products"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=100, nullable=False)
    price  = FloatField(nullable=False)
    active = BoolField(default=True)

    @classmethod
    def before_create(cls, validated):
        hook_calls.append(("before_create", dict(validated)))
        validated["name"] = validated["name"].upper()
        return validated

    @classmethod
    async def after_create(cls, new_id, validated):
        hook_calls.append(("after_create", new_id))

    @classmethod
    def before_update(cls, data, where):
        hook_calls.append(("before_update", dict(data), dict(where)))

    @classmethod
    def after_update(cls, rows_affected, data, where):
        hook_calls.append(("after_update", rows_affected))

    @classmethod
    def before_delete(cls, where):
        hook_calls.append(("before_delete", dict(where)))

    @classmethod
    def after_delete(cls, rows_deleted, where):
        hook_calls.append(("after_delete", rows_deleted))


@pytest_asyncio.fixture(autouse=True)
async def _hook_table(setup_async_db):
    await AsyncHookProduct.create_table()
    hook_calls.clear()
    yield
    await AsyncHookProduct.drop_table()


async def test_async_before_create_hook_transforms_data():
    pid = await AsyncHookProduct.create(name="widget", price=1.0, active=True)
    row = await AsyncHookProduct.get(id=pid)
    assert row["name"] == "WIDGET"
    assert hook_calls[0][0] == "before_create"


async def test_async_after_create_hook_can_be_async():
    pid = await AsyncHookProduct.create(name="gadget", price=1.0, active=True)
    assert ("after_create", pid) in hook_calls


async def test_async_update_hooks_fire():
    pid = await AsyncHookProduct.create(name="a", price=1.0, active=True)
    hook_calls.clear()
    await AsyncHookProduct.update({"price": 2.0}, id=pid)
    events = [c[0] for c in hook_calls]
    assert events == ["before_update", "after_update"]


async def test_async_delete_hooks_fire():
    pid = await AsyncHookProduct.create(name="b", price=1.0, active=True)
    hook_calls.clear()
    await AsyncHookProduct.delete(id=pid)
    events = [c[0] for c in hook_calls]
    assert events == ["before_delete", "after_delete"]
