# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_async_query_logging.py
# Project     : mydborm
# License     : MIT
# Description : Tests for async query/SQL logging — async_db.configure
#               (echo=True), the "mydborm.sql" logger, and
#               async_db.queries / clear_queries(). Uses SQLite (no
#               external service, no skip guard).
# =============================================================================

import logging

import pytest_asyncio

from mydborm.async_db import AsyncBaseModel, async_db
from mydborm.fields import IntField, StrField


class AsyncQLProduct(AsyncBaseModel):
    __tablename__ = "async_ql_products"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    yield
    await async_db.close()


async def _configure(echo):
    await async_db.configure(dialect="sqlite", database=":memory:", echo=echo)
    await AsyncQLProduct.create_table()
    async_db.clear_queries()


async def test_echo_false_by_default_no_queries_tracked():
    await _configure(echo=False)
    await AsyncQLProduct.create(name="Widget")
    assert async_db.queries == []


async def test_echo_true_tracks_queries():
    await _configure(echo=True)
    await AsyncQLProduct.create(name="Widget")
    inserts = [q for q in async_db.queries if "INSERT" in q["sql"]]
    assert len(inserts) == 1
    assert inserts[0]["params"] == ["Widget"]
    assert isinstance(inserts[0]["duration_ms"], float)


async def test_echo_true_emits_debug_log_records(caplog):
    await _configure(echo=True)
    with caplog.at_level(logging.DEBUG, logger="mydborm.sql"):
        await AsyncQLProduct.create(name="Gadget")
    messages = [r.message for r in caplog.records if r.name == "mydborm.sql"]
    assert any("INSERT" in m and "Gadget" in m for m in messages)


async def test_echo_false_emits_no_log_records(caplog):
    await _configure(echo=False)
    with caplog.at_level(logging.DEBUG, logger="mydborm.sql"):
        await AsyncQLProduct.create(name="Silent")
    messages = [r.message for r in caplog.records if r.name == "mydborm.sql"]
    assert messages == []


async def test_clear_queries_empties_the_log():
    await _configure(echo=True)
    await AsyncQLProduct.create(name="A")
    assert len(async_db.queries) > 0
    async_db.clear_queries()
    assert async_db.queries == []


async def test_async_db_execute_is_logged():
    await _configure(echo=True)
    pid = await AsyncQLProduct.create(name="First")
    async_db.clear_queries()
    await async_db.execute(
        "UPDATE async_ql_products SET name = %s WHERE id = %s", ["Second", pid]
    )
    updates = [q for q in async_db.queries if "UPDATE" in q["sql"]]
    assert len(updates) == 1


async def test_async_get_is_logged():
    await _configure(echo=True)
    pid = await AsyncQLProduct.create(name="Findme")
    async_db.clear_queries()
    await AsyncQLProduct.get(id=pid)
    selects = [q for q in async_db.queries if "SELECT" in q["sql"]]
    assert len(selects) == 1


# ------------------------------------------------------------------ #
#  Slow-query monitoring                                               #
# ------------------------------------------------------------------ #

async def test_slow_query_threshold_fires_callback_independent_of_echo():
    calls = []
    await async_db.configure(
        dialect="sqlite", database=":memory:",
        echo=False, slow_query_ms=0, on_slow_query=lambda sql, params, ms: calls.append((sql, ms)),
    )
    await AsyncQLProduct.create_table()
    async_db.clear_queries()
    calls.clear()
    await AsyncQLProduct.create(name="Widget")

    assert len(calls) >= 1
    assert async_db.queries == []  # echo is off — no .queries tracking


async def test_slow_query_threshold_not_met_no_callback():
    calls = []
    await async_db.configure(
        dialect="sqlite", database=":memory:",
        slow_query_ms=100_000, on_slow_query=lambda sql, params, ms: calls.append((sql, ms)),
    )
    await AsyncQLProduct.create_table()
    calls.clear()
    await AsyncQLProduct.create(name="Widget")

    assert calls == []


async def test_slow_query_disabled_by_default():
    calls = []
    await async_db.configure(
        dialect="sqlite", database=":memory:",
        on_slow_query=lambda sql, params, ms: calls.append((sql, ms)),
    )
    await AsyncQLProduct.create_table()
    calls.clear()
    await AsyncQLProduct.create(name="Widget")

    assert calls == []


async def test_slow_query_logs_at_warning_level(caplog):
    await async_db.configure(dialect="sqlite", database=":memory:", slow_query_ms=0)
    await AsyncQLProduct.create_table()
    with caplog.at_level(logging.WARNING, logger="mydborm.slow_query"):
        await AsyncQLProduct.create(name="Widget")
    messages = [r.message for r in caplog.records if r.name == "mydborm.slow_query"]
    assert any("INSERT" in m for m in messages)


async def test_slow_query_callback_exception_does_not_break_query():
    def bad_callback(sql, params, ms):
        raise RuntimeError("boom")

    await async_db.configure(
        dialect="sqlite", database=":memory:",
        slow_query_ms=0, on_slow_query=bad_callback,
    )
    await AsyncQLProduct.create_table()
    pid = await AsyncQLProduct.create(name="Widget")
    assert pid is not None
    row = await AsyncQLProduct.get(id=pid)
    assert row["name"] == "Widget"
