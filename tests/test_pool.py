# =============================================================================
# File        : tests/test_pool.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.4.0
# License     : MIT
# Description : pytest tests for connection pooling — configure_pool,
#               pool_status, ping, and reconnect.
# =============================================================================

import os
import socket
import threading
import time
import pytest
from mydborm.db import db, ConnectionManager
from mysql.connector.errors import PoolError
from psycopg2.pool import PoolError as PgPoolError


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root",
        password=os.environ.get("DB_PASSWORD", "root"),
        database="testdb"
    )
    yield
    db.close()


def _is_yugabyte_available():
    try:
        s = socket.create_connection(("127.0.0.1", 5433), timeout=2)
        s.close()
        return True
    except OSError:
        return False


yb_skip = pytest.mark.skipif(
    not _is_yugabyte_available(),
    reason="YugabyteDB not available on port 5433 — skipping"
)


def _configure_yugabyte():
    db.configure(
        dialect="yugabyte", host="127.0.0.1",
        port=5433, user="yugabyte",
        password=os.environ.get("YB_PASSWORD", "yugabyte"),
        database="yugabyte",
    )


# ------------------------------------------------------------------ #
#  configure_pool                                                      #
# ------------------------------------------------------------------ #

def test_configure_pool_defaults():
    db.configure_pool()
    status = db.pool_status()
    assert status["pool_config"]["pool_size"]    == 5
    assert status["pool_config"]["max_overflow"] == 10
    assert status["pool_config"]["pool_timeout"] == 30
    assert status["pool_config"]["pool_recycle"] == 3600


def test_configure_pool_custom():
    db.configure_pool(
        pool_size=10, max_overflow=20,
        pool_timeout=60, pool_recycle=7200
    )
    status = db.pool_status()
    assert status["pool_config"]["pool_size"]    == 10
    assert status["pool_config"]["max_overflow"] == 20
    assert status["pool_config"]["pool_timeout"] == 60
    assert status["pool_config"]["pool_recycle"] == 7200


def test_configure_pool_resets_connection():
    with db.connect() as conn:
        assert conn is not None
    db.configure_pool(pool_size=3)
    # After configure_pool, connection should be reset
    status = db.pool_status()
    assert status["connected"] is False


# ------------------------------------------------------------------ #
#  pool_status                                                         #
# ------------------------------------------------------------------ #

def test_pool_status_returns_dict():
    status = db.pool_status()
    assert isinstance(status, dict)


def test_pool_status_keys():
    status = db.pool_status()
    assert "dialect"         in status
    assert "host"            in status
    assert "database"        in status
    assert "pool_config"     in status
    assert "pooling_active"  in status
    assert "connected"       in status
    assert "connection_id"   in status


def test_pool_status_dialect():
    status = db.pool_status()
    assert status["dialect"] == "mysql"


def test_pool_status_host():
    status = db.pool_status()
    assert status["host"] == "127.0.0.1"


def test_pool_status_not_connected_initially():
    status = db.pool_status()
    assert status["connected"] is False
    assert status["connection_id"] is None


def test_pool_status_connected_after_query():
    with db.connect() as conn:
        status = db.pool_status()
        assert status["connected"] is True
        assert status["connection_id"] is not None


# ------------------------------------------------------------------ #
#  Real pooling — MySQL                                                #
# ------------------------------------------------------------------ #

def test_pooling_active_false_before_configure_pool():
    assert db.pool_status()["pooling_active"] is False


def test_pooling_active_true_after_configure_pool():
    db.configure_pool()
    assert db.pool_status()["pooling_active"] is True


def test_mysql_pool_returns_pooled_connection():
    db.configure_pool(pool_size=3)
    with db.connect() as conn:
        assert type(conn).__name__ == "PooledMySQLConnection"


def test_mysql_without_configure_pool_returns_plain_connection():
    with db.connect() as conn:
        assert type(conn).__name__ != "PooledMySQLConnection"


def test_mysql_pool_exhaustion_raises_pool_error():
    db.configure_pool(pool_size=1)
    holder_ready  = threading.Event()
    release_holder = threading.Event()
    result = {}

    def holder():
        with db.connect():
            holder_ready.set()
            release_holder.wait(timeout=5)

    def second():
        holder_ready.wait(timeout=5)
        try:
            with db.connect():
                result["error"] = None
        except Exception as e:
            result["error"] = e

    t1 = threading.Thread(target=holder)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    t2.join(timeout=10)
    release_holder.set()
    t1.join(timeout=10)

    assert isinstance(result.get("error"), PoolError)


# ------------------------------------------------------------------ #
#  Connection recycling                                                #
# ------------------------------------------------------------------ #

def test_recycle_not_triggered_when_fresh():
    with db.connect() as conn:
        first_id = id(conn)
    with db.connect() as conn:
        second_id = id(conn)
    assert first_id == second_id


def test_recycle_creates_fresh_connection_when_stale():
    with db.connect() as conn:
        first_id = id(conn)
    db._local.created_at = time.time() - 4000  # older than the 3600s default
    with db.connect() as conn:
        second_id = id(conn)
    assert first_id != second_id


def test_recycle_respects_configured_pool_recycle():
    db.configure_pool(pool_recycle=1)
    with db.connect() as conn:
        first_id = id(conn)
    time.sleep(1.1)
    with db.connect() as conn:
        second_id = id(conn)
    assert first_id != second_id


# ------------------------------------------------------------------ #
#  Real pooling — YugabyteDB (postgres-family)                         #
# ------------------------------------------------------------------ #

@yb_skip
def test_yugabyte_pooling_active_after_configure_pool():
    _configure_yugabyte()
    db.configure_pool(pool_size=3)
    assert db.pool_status()["pooling_active"] is True
    assert db.ping() is True


@yb_skip
def test_yugabyte_without_configure_pool_pooling_inactive():
    _configure_yugabyte()
    assert db.pool_status()["pooling_active"] is False


@yb_skip
def test_yugabyte_pool_connection_returned_on_close():
    _configure_yugabyte()
    db.configure_pool(pool_size=2)
    with db.connect() as conn:
        assert conn is not None
    db.close()  # putconn() back to the pool
    with db.connect() as conn2:
        assert conn2 is not None


@yb_skip
def test_yugabyte_pool_exhaustion_raises_pool_error():
    _configure_yugabyte()
    db.configure_pool(pool_size=1, max_overflow=0)
    holder_ready   = threading.Event()
    release_holder = threading.Event()
    result = {}

    def holder():
        with db.connect():
            holder_ready.set()
            release_holder.wait(timeout=5)

    def second():
        holder_ready.wait(timeout=5)
        try:
            with db.connect():
                result["error"] = None
        except Exception as e:
            result["error"] = e

    t1 = threading.Thread(target=holder)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    t2.join(timeout=10)
    release_holder.set()
    t1.join(timeout=10)

    assert isinstance(result.get("error"), PgPoolError)


# ------------------------------------------------------------------ #
#  ping                                                                #
# ------------------------------------------------------------------ #

def test_ping_returns_true():
    assert db.ping() is True


def test_ping_returns_bool():
    result = db.ping()
    assert isinstance(result, bool)


def test_ping_unconfigured():
    fresh = ConnectionManager()
    assert fresh.ping() is False


def test_ping_multiple_times():
    for _ in range(3):
        assert db.ping() is True


# ------------------------------------------------------------------ #
#  reconnect                                                           #
# ------------------------------------------------------------------ #

def test_reconnect_succeeds():
    db.reconnect()
    assert db.ping() is True


def test_reconnect_after_close():
    db.close()
    db.reconnect()
    assert db.ping() is True


def test_reconnect_clears_old_connection():
    with db.connect() as conn:
        old_id = id(conn)
    db.reconnect()
    with db.connect() as conn:
        new_id = id(conn)
    assert old_id != new_id


# ------------------------------------------------------------------ #
#  Combined                                                            #
# ------------------------------------------------------------------ #

def test_full_pool_workflow():
    db.configure_pool(pool_size=3, max_overflow=5)
    assert db.ping() is True
    status = db.pool_status()
    assert status["pool_config"]["pool_size"] == 3
    db.reconnect()
    assert db.ping() is True