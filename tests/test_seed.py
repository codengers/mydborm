# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_seed.py
# Project     : mydborm
# Description : Tests for mydborm.seed — seed()/seed_from_file() (sync) and
#               seed_async()/seed_from_file_async() (async). Uses SQLite —
#               the feature is pure Python (bulk_create + a JSON file read),
#               no dialect-specific behavior to verify.
# =============================================================================

import json
import os
import tempfile

import pytest
import pytest_asyncio

from mydborm import db, BaseModel, IntField, StrField
from mydborm.seed import seed, seed_from_file, seed_async, seed_from_file_async
from mydborm.async_db import async_db, AsyncBaseModel


class SeedUser(BaseModel):
    __tablename__ = "seed_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50, nullable=False)


@pytest.fixture(autouse=True)
def _setup():
    db.configure(dialect="sqlite", database=":memory:")
    SeedUser.create_table()
    yield
    db.close()


def test_seed_inserts_records():
    n = seed(SeedUser, [{"username": "alice"}, {"username": "bob"}])
    assert n == 2
    assert SeedUser.count() == 2


def test_seed_skips_when_table_not_empty():
    SeedUser.create(username="existing")
    n = seed(SeedUser, [{"username": "alice"}])
    assert n == 0
    assert SeedUser.count() == 1


def test_seed_force_when_not_empty():
    SeedUser.create(username="existing")
    n = seed(SeedUser, [{"username": "alice"}], if_empty=False)
    assert n == 1
    assert SeedUser.count() == 2


def test_seed_from_file():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"username": "alice"}, {"username": "bob"}], f)
        n = seed_from_file(SeedUser, path)
        assert n == 2
        assert SeedUser.count() == 2
    finally:
        os.remove(path)


def test_seed_from_file_rejects_non_list():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"username": "alice"}, f)
        with pytest.raises(ValueError, match="JSON list"):
            seed_from_file(SeedUser, path)
    finally:
        os.remove(path)


# ------------------------------------------------------------------ #
#  Async                                                                #
# ------------------------------------------------------------------ #

class AsyncSeedUser(AsyncBaseModel):
    __tablename__ = "async_seed_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50, nullable=False)


@pytest_asyncio.fixture(autouse=True)
async def _setup_async():
    await async_db.configure(dialect="sqlite", database=":memory:")
    await AsyncSeedUser.create_table()
    yield
    await async_db.close()


async def test_seed_async_inserts_records():
    n = await seed_async(AsyncSeedUser, [{"username": "alice"}, {"username": "bob"}])
    assert n == 2
    assert await AsyncSeedUser.count() == 2


async def test_seed_async_skips_when_not_empty():
    await AsyncSeedUser.create(username="existing")
    n = await seed_async(AsyncSeedUser, [{"username": "alice"}])
    assert n == 0
    assert await AsyncSeedUser.count() == 1


async def test_seed_from_file_async():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"username": "alice"}], f)
        n = await seed_from_file_async(AsyncSeedUser, path)
        assert n == 1
    finally:
        os.remove(path)
