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
import pytest
from mydborm.db import db, ConnectionManager


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
    assert "dialect"       in status
    assert "host"          in status
    assert "database"      in status
    assert "pool_config"   in status
    assert "connected"     in status
    assert "connection_id" in status


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