import os
# =============================================================================
# File        : tests/test_replicas.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : pytest tests for read/write splitting — configure_replicas(),
#               connect_read() round-robin, primary fallback (no replicas,
#               inside a transaction), and writes always hitting the primary.
# =============================================================================

import pytest
from mydborm.db import ConnectionManager
from mydborm import BaseModel, IntField, StrField

MYSQL_CONFIG = dict(
    dialect="mysql", host="127.0.0.1", port=3307,
    user="root", password=os.environ.get("DB_PASSWORD", "root"),
)


class RWMarker(BaseModel):
    __tablename__ = "rw_markers"
    id  = IntField(primary_key=True)
    src = StrField(max_length=50, nullable=False)


@pytest.fixture(scope="module")
def rw_db():
    """A dedicated ConnectionManager (not the global `db` singleton) so
    this module's replica configuration can't leak into other test
    files that import the shared `db` object."""
    bootstrap = ConnectionManager()
    bootstrap.configure(database="testdb", **MYSQL_CONFIG)
    with bootstrap.connect() as conn:
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_rw_replica1")
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_rw_replica2")
    bootstrap.close()

    manager = ConnectionManager()
    manager.configure(database="testdb", **MYSQL_CONFIG)
    yield manager
    manager.close()


@pytest.fixture(autouse=True)
def seed_all(rw_db):
    """Seed the primary and both replica-target databases with a single
    row each, distinguishable by `src`, then point the model at each in
    turn via a scratch ConnectionManager — bypassing rw_db/replica
    routing entirely for the seeding itself."""
    for database, src in (
        ("testdb", "primary"),
        ("testdb_rw_replica1", "replica1"),
        ("testdb_rw_replica2", "replica2"),
    ):
        seeder = ConnectionManager()
        seeder.configure(database=database, **MYSQL_CONFIG)
        with seeder.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS rw_markers")
            cur.execute(
                "CREATE TABLE rw_markers (id INT AUTO_INCREMENT PRIMARY KEY, "
                "src VARCHAR(50) NOT NULL)"
            )
            cur.execute("INSERT INTO rw_markers (src) VALUES (%s)", [src])
        seeder.close()
    yield


@pytest.fixture(autouse=True)
def bind_model_db(rw_db, monkeypatch):
    monkeypatch.setattr("mydborm.model.db", rw_db)
    yield


# ------------------------------------------------------------------ #
#  No replicas configured — reads and writes both use the primary     #
# ------------------------------------------------------------------ #

def test_no_replicas_reads_hit_primary(rw_db):
    rw_db._replicas = []
    rows = RWMarker.all()
    assert rows[0]["src"] == "primary"


# ------------------------------------------------------------------ #
#  One replica — every read routes to it                              #
# ------------------------------------------------------------------ #

def test_single_replica_always_serves_reads(rw_db):
    rw_db.configure_replicas(
        dict(database="testdb_rw_replica1", **MYSQL_CONFIG),
    )
    try:
        for _ in range(3):
            rows = RWMarker.all()
            assert rows[0]["src"] == "replica1"
    finally:
        rw_db._replicas = []


def test_writes_always_hit_primary_even_with_replicas_configured(rw_db):
    rw_db.configure_replicas(
        dict(database="testdb_rw_replica1", **MYSQL_CONFIG),
    )
    try:
        RWMarker.create(src="primary-write")
        with rw_db.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT src FROM rw_markers")
            primary_rows = [r[0] for r in cur.fetchall()]
        assert "primary-write" in primary_rows
    finally:
        rw_db._replicas = []


# ------------------------------------------------------------------ #
#  Two replicas — round robin                                         #
# ------------------------------------------------------------------ #

def test_two_replicas_round_robin(rw_db):
    rw_db.configure_replicas(
        dict(database="testdb_rw_replica1", **MYSQL_CONFIG),
        dict(database="testdb_rw_replica2", **MYSQL_CONFIG),
    )
    try:
        seen = [RWMarker.all()[0]["src"] for _ in range(4)]
        assert seen == ["replica1", "replica2", "replica1", "replica2"]
    finally:
        rw_db._replicas = []


# ------------------------------------------------------------------ #
#  Inside a transaction — falls back to primary                       #
# ------------------------------------------------------------------ #

def test_transaction_falls_back_to_primary(rw_db):
    rw_db.configure_replicas(
        dict(database="testdb_rw_replica1", **MYSQL_CONFIG),
    )
    try:
        with rw_db.transaction():
            rows = RWMarker.query().all()
            assert rows[0]["src"] == "primary"
    finally:
        rw_db._replicas = []


# ------------------------------------------------------------------ #
#  db.fetchall() also routes through replicas                         #
# ------------------------------------------------------------------ #

def test_raw_fetchall_routes_through_replica(rw_db):
    rw_db.configure_replicas(
        dict(database="testdb_rw_replica1", **MYSQL_CONFIG),
    )
    try:
        rows = rw_db.fetchall("SELECT src FROM rw_markers LIMIT 1")
        assert rows[0]["src"] == "replica1"
    finally:
        rw_db._replicas = []


# ------------------------------------------------------------------ #
#  close() also closes replica connections                            #
# ------------------------------------------------------------------ #

def test_close_closes_replica_connections(rw_db):
    rw_db.configure_replicas(
        dict(database="testdb_rw_replica1", **MYSQL_CONFIG),
    )
    try:
        RWMarker.all()  # opens a connection on the replica
        replica = rw_db._replicas[0]
        assert getattr(replica._local, "conn", None) is not None
        rw_db.close()
        assert getattr(replica._local, "conn", None) is None
    finally:
        rw_db._replicas = []
