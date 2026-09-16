import os
# =============================================================================
# File        : tests/test_replicas_async.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : pytest-asyncio tests for async read/write splitting —
#               AsyncConnectionManager.configure_replicas(), connect_read()
#               round-robin, and primary fallback for writes.
# =============================================================================

import sys
import pytest_asyncio
from mydborm.db import ConnectionManager
from mydborm.async_db import AsyncConnectionManager, AsyncBaseModel
from mydborm.fields import IntField, StrField

# mydborm/__init__.py does `from .async_db import async_db`, which rebinds
# the package attribute `mydborm.async_db` to the *singleton instance* —
# shadowing the submodule of the same name. `import mydborm.async_db as x`
# is sugar for `x = mydborm.async_db` (attribute access) and hits that same
# shadowing, so the real submodule has to come from sys.modules instead.
async_db_module = sys.modules["mydborm.async_db"]

MYSQL_CONFIG = dict(
    dialect="mysql", host="127.0.0.1", port=3307,
    user="root", password=os.environ.get("DB_PASSWORD", "root"),
)


class ARWMarker(AsyncBaseModel):
    __tablename__ = "arw_markers"
    id  = IntField(primary_key=True)
    src = StrField(max_length=50, nullable=False)


@pytest_asyncio.fixture
async def arw_db():
    """A dedicated AsyncConnectionManager (not the shared async_db
    singleton) so this module's replica config can't leak into other
    async test files. Function-scoped (a fresh pool per test) rather
    than module-scoped — pytest-asyncio uses a new event loop per test
    function by default, and an aiomysql pool created under one loop
    can't be reused from another ("attached to a different loop")."""
    bootstrap = ConnectionManager()
    bootstrap.configure(database="testdb", **MYSQL_CONFIG)
    with bootstrap.connect() as conn:
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_arw_replica1")
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_arw_replica2")
    bootstrap.close()

    manager = AsyncConnectionManager()
    await manager.configure(database="testdb", **MYSQL_CONFIG)
    yield manager
    await manager.close()


@pytest_asyncio.fixture(autouse=True)
async def seed_all(arw_db):
    for database, src in (
        ("testdb", "primary"),
        ("testdb_arw_replica1", "replica1"),
        ("testdb_arw_replica2", "replica2"),
    ):
        seeder = ConnectionManager()
        seeder.configure(database=database, **MYSQL_CONFIG)
        with seeder.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS arw_markers")
            cur.execute(
                "CREATE TABLE arw_markers (id INT AUTO_INCREMENT PRIMARY KEY, "
                "src VARCHAR(50) NOT NULL)"
            )
            cur.execute("INSERT INTO arw_markers (src) VALUES (%s)", [src])
        seeder.close()
    yield


@pytest_asyncio.fixture(autouse=True)
async def bind_model_async_db(arw_db, monkeypatch):
    monkeypatch.setattr(async_db_module, "async_db", arw_db)
    yield
    arw_db._replicas = []


# ------------------------------------------------------------------ #
#  No replicas — reads use the primary                                #
# ------------------------------------------------------------------ #

async def test_async_no_replicas_reads_hit_primary(arw_db):
    arw_db._replicas = []
    rows = await ARWMarker.all()
    assert rows[0]["src"] == "primary"


# ------------------------------------------------------------------ #
#  One replica — every read routes to it                              #
# ------------------------------------------------------------------ #

async def test_async_single_replica_always_serves_reads(arw_db):
    await arw_db.configure_replicas(
        dict(database="testdb_arw_replica1", **MYSQL_CONFIG),
    )
    for _ in range(3):
        rows = await ARWMarker.all()
        assert rows[0]["src"] == "replica1"


async def test_async_writes_always_hit_primary(arw_db):
    await arw_db.configure_replicas(
        dict(database="testdb_arw_replica1", **MYSQL_CONFIG),
    )
    await ARWMarker.create(src="primary-write")
    async with arw_db.connect() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT src FROM arw_markers")
            primary_rows = [r[0] for r in await cur.fetchall()]
    assert "primary-write" in primary_rows


# ------------------------------------------------------------------ #
#  Two replicas — round robin                                         #
# ------------------------------------------------------------------ #

async def test_async_two_replicas_round_robin(arw_db):
    await arw_db.configure_replicas(
        dict(database="testdb_arw_replica1", **MYSQL_CONFIG),
        dict(database="testdb_arw_replica2", **MYSQL_CONFIG),
    )
    seen = []
    for _ in range(4):
        rows = await ARWMarker.query().all()
        seen.append(rows[0]["src"])
    assert seen == ["replica1", "replica2", "replica1", "replica2"]


# ------------------------------------------------------------------ #
#  async_db.fetchall() also routes through replicas                   #
# ------------------------------------------------------------------ #

async def test_async_raw_fetchall_routes_through_replica(arw_db):
    await arw_db.configure_replicas(
        dict(database="testdb_arw_replica1", **MYSQL_CONFIG),
    )
    rows = await arw_db.fetchall("SELECT src FROM arw_markers LIMIT 1")
    assert rows[0]["src"] == "replica1"


# ------------------------------------------------------------------ #
#  close() also closes replica pools                                  #
# ------------------------------------------------------------------ #

async def test_async_close_closes_replica_pools(arw_db):
    await arw_db.configure_replicas(
        dict(database="testdb_arw_replica1", **MYSQL_CONFIG),
    )
    await ARWMarker.all()  # opens the replica's pool
    replica = arw_db._replicas[0]
    assert replica._pool is not None
    await arw_db.close()
    assert replica._pool is None
