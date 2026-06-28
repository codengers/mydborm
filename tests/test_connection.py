import os
# =============================================================================
# File        : tests/test_connection.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : pytest tests for ConnectionManager � covers configure,
#               connect, dialect validation, and error handling.
# =============================================================================
"""
test_connection.py — Connection manager tests.
"""
import pytest
from mydborm.db import db


def test_configure_mysql():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
    )
    assert db.dialect == "mysql"


def test_mysql_connect():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
    )
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
    db.close()


def test_missing_dialect_raises():
    with pytest.raises(ValueError, match="dialect is required"):
        db.configure(host="localhost", user="root")


def test_missing_dialect_raises_typed_exception():
    from mydborm.exceptions import UnsupportedDialectError
    with pytest.raises(UnsupportedDialectError, match="dialect is required"):
        db.configure(host="localhost", user="root")


def test_not_configured_raises():
    db._config = {}
    with pytest.raises(RuntimeError, match="not configured"):
        with db.connect() as conn:
            pass


def test_not_configured_raises_typed_exception():
    from mydborm.exceptions import NotConfiguredError
    db._config = {}
    with pytest.raises(NotConfiguredError, match="not configured"):
        with db.connect() as conn:
            pass


# ------------------------------------------------------------------ #
#  _parse_url — dialect detection (lines 50-60)                       #
# ------------------------------------------------------------------ #

def test_parse_url_yugabyte():
    from mydborm.db import _parse_url
    cfg = _parse_url("yugabyte://yugabyte:yugabyte@localhost:5433/yugabyte")
    assert cfg["dialect"] == "yugabyte"  # lines 53-54
    assert cfg["port"] == 5433


def test_parse_url_postgres():
    from mydborm.db import _parse_url
    cfg = _parse_url("postgres://user:pass@localhost:5432/mydb")
    assert cfg["dialect"] == "postgres"  # lines 55-56
    assert cfg["port"] == 5432


def test_parse_url_mysql_default():
    from mydborm.db import _parse_url
    cfg = _parse_url("mysql://root:root@localhost:3306/testdb")
    assert cfg["dialect"] == "mysql"  # lines 57-60
    assert cfg["database"] == "testdb"


# ------------------------------------------------------------------ #
#  from_env raises when variable not set (lines 125-133)              #
# ------------------------------------------------------------------ #

def test_from_env_raises_when_not_set():
    import os
    from mydborm.db import ConnectionManager
    os.environ.pop("DATABASE_URL", None)
    mgr = ConnectionManager()
    with pytest.raises(EnvironmentError, match="DATABASE_URL"):
        mgr.from_env()  # lines 126-132


# ------------------------------------------------------------------ #
#  Unsupported dialect raises ValueError (lines 179-182)              #
# ------------------------------------------------------------------ #

def test_unsupported_dialect_raises():
    from mydborm.db import ConnectionManager
    mgr = ConnectionManager()
    mgr._config = {"dialect": "sqlite", "host": "x", "user": "x",
                   "password": "x", "database": "x"}
    with pytest.raises(ValueError, match="Unsupported dialect"):
        mgr._make_connection()  # lines 179-182


def test_unsupported_dialect_raises_typed_exception():
    from mydborm.db import ConnectionManager
    from mydborm.exceptions import UnsupportedDialectError
    mgr = ConnectionManager()
    mgr._config = {"dialect": "sqlite", "host": "x", "user": "x",
                   "password": "x", "database": "x"}
    with pytest.raises(UnsupportedDialectError) as exc_info:
        mgr._make_connection()
    assert exc_info.value.dialect == "sqlite"


# ------------------------------------------------------------------ #
#  Not-configured RuntimeErrors (lines 240, 324, 360)                 #
# ------------------------------------------------------------------ #

def test_fetchall_not_configured_raises():
    from mydborm.db import ConnectionManager
    mgr = ConnectionManager()
    with pytest.raises(RuntimeError, match="not configured"):
        mgr.fetchall("SELECT 1")  # line 240


def test_transaction_not_configured_raises():
    from mydborm.db import ConnectionManager
    mgr = ConnectionManager()
    with pytest.raises(RuntimeError, match="not configured"):
        with mgr.transaction():
            pass  # line 324


def test_execute_not_configured_raises():
    from mydborm.db import ConnectionManager
    mgr = ConnectionManager()
    with pytest.raises(RuntimeError, match="not configured"):
        mgr.execute("SELECT 1")  # line 360


def test_fetchall_transaction_execute_raise_typed_not_configured():
    """fetchall/transaction/execute all raise NotConfiguredError specifically,
    not just a generic RuntimeError, when called before configure()."""
    from mydborm.db import ConnectionManager
    from mydborm.exceptions import NotConfiguredError
    mgr = ConnectionManager()

    with pytest.raises(NotConfiguredError):
        mgr.fetchall("SELECT 1")

    with pytest.raises(NotConfiguredError):
        with mgr.transaction():
            pass

    with pytest.raises(NotConfiguredError):
        mgr.execute("SELECT 1")


# ------------------------------------------------------------------ #
#  ConnectionManager.__repr__ (lines 606-608)                         #
# ------------------------------------------------------------------ #

def test_repr_not_configured():
    from mydborm.db import ConnectionManager
    mgr = ConnectionManager()
    assert "not configured" in repr(mgr)  # line 607


def test_repr_configured():
    from mydborm.db import ConnectionManager
    mgr = ConnectionManager()
    mgr.configure(dialect="mysql", host="127.0.0.1", port=3307,
                  user="root", password="root", database="testdb")
    assert "mysql" in repr(mgr)  # lines 608+


# ------------------------------------------------------------------ #
#  nested_transaction without outer connection (lines 521-522)        #
# ------------------------------------------------------------------ #

def test_nested_transaction_without_outer():
    db.configure(
        dialect="mysql", host="127.0.0.1", port=3307,
        user="root", password=os.environ.get("DB_PASSWORD", "root"),
        database="testdb",
    )
    db.close()  # ensure no _local.conn
    results = []
    with db.nested_transaction():  # lines 521-522: starts fresh transaction
        results.append(db.fetchone("SELECT 1 AS v")["v"])
    assert results == [1]
    db.close()


