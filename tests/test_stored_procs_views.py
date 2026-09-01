# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_stored_procs_views.py
# Project     : mydborm
# Description : Tests for db.call_procedure() and ViewModel (sync, MySQL +
#               SQLite + YugabyteDB where available).
# =============================================================================

import os
import socket

import pytest

from mydborm import db, BaseModel, IntField, StrField, BoolField, ViewModel
from mydborm.exceptions import ViewReadOnlyError, UnsupportedDialectError


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


class SPUser(BaseModel):
    __tablename__ = "sp_users"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=50, nullable=False)
    active = BoolField(default=True)


@pytest.fixture(autouse=True)
def _setup_mysql():
    db.configure(
        dialect="mysql", host="127.0.0.1", port=3307, user="root",
        password=os.environ.get("DB_PASSWORD", "root"), database="testdb",
    )
    SPUser.drop_table()
    SPUser.create_table()
    SPUser.create(name="Alice", active=True)
    SPUser.create(name="Bob", active=False)
    yield
    SPUser.drop_table()
    with db.connect() as conn:
        conn.cursor().execute("DROP PROCEDURE IF EXISTS sp_get_active")
    db.close()


# ------------------------------------------------------------------ #
#  call_procedure() — MySQL                                            #
# ------------------------------------------------------------------ #

def test_call_procedure_mysql_returns_rows():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP PROCEDURE IF EXISTS sp_get_active")
        cur.execute(
            "CREATE PROCEDURE sp_get_active() "
            "BEGIN SELECT * FROM sp_users WHERE active = 1; END"
        )
    rows = db.call_procedure("sp_get_active")
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice"


def test_call_procedure_mysql_with_params():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP PROCEDURE IF EXISTS sp_get_by_name")
        cur.execute(
            "CREATE PROCEDURE sp_get_by_name(IN uname VARCHAR(50)) "
            "BEGIN SELECT * FROM sp_users WHERE name = uname; END"
        )
    rows = db.call_procedure("sp_get_by_name", ["Bob"])
    assert len(rows) == 1
    assert rows[0]["name"] == "Bob"
    with db.connect() as conn:
        conn.cursor().execute("DROP PROCEDURE IF EXISTS sp_get_by_name")


def test_call_procedure_does_not_corrupt_next_query():
    """Regression: mysql-connector's CALL leaves trailing result-set state
    that must be drained via callproc()+stored_results(), or the very next
    query's cursor.description silently comes back None."""
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP PROCEDURE IF EXISTS sp_get_active")
        cur.execute(
            "CREATE PROCEDURE sp_get_active() "
            "BEGIN SELECT * FROM sp_users WHERE active = 1; END"
        )
    db.call_procedure("sp_get_active")
    assert SPUser.count() == 2  # a normal query right after must work


def test_call_procedure_invalid_name_rejected():
    with pytest.raises(ValueError, match="Invalid procedure name"):
        db.call_procedure("sp_users; DROP TABLE sp_users; --")


# ------------------------------------------------------------------ #
#  call_procedure() — SQLite (unsupported)                             #
# ------------------------------------------------------------------ #

def test_call_procedure_sqlite_raises():
    db.configure(dialect="sqlite", database=":memory:")
    with pytest.raises(UnsupportedDialectError):
        db.call_procedure("anything")
    db.configure(
        dialect="mysql", host="127.0.0.1", port=3307, user="root",
        password=os.environ.get("DB_PASSWORD", "root"), database="testdb",
    )


# ------------------------------------------------------------------ #
#  call_procedure() — YugabyteDB                                       #
# ------------------------------------------------------------------ #

@yb_skip
def test_call_procedure_yugabyte():
    db.close()  # drop the mysql connection from the autouse fixture first
    db.configure(
        dialect="yugabyte", host="127.0.0.1", port=5433, user="yugabyte",
        password=os.environ.get("YB_PASSWORD", "yugabyte"), database="yugabyte",
    )
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS sp_yb_users")
        cur.execute('CREATE TABLE sp_yb_users (id SERIAL PRIMARY KEY, name TEXT)')
        cur.execute("INSERT INTO sp_yb_users (name) VALUES ('Carl')")
        cur.execute("DROP PROCEDURE IF EXISTS sp_yb_noop")
        cur.execute(
            "CREATE OR REPLACE PROCEDURE sp_yb_noop() "
            "LANGUAGE plpgsql AS $$ BEGIN NULL; END; $$"
        )
    db.call_procedure("sp_yb_noop")
    rows = db.fetchall("SELECT * FROM sp_yb_users")
    assert len(rows) == 1  # connection still usable after the CALL
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP PROCEDURE IF EXISTS sp_yb_noop")
        cur.execute("DROP TABLE IF EXISTS sp_yb_users")
    db.close()  # drop the yugabyte connection before switching back
    db.configure(
        dialect="mysql", host="127.0.0.1", port=3307, user="root",
        password=os.environ.get("DB_PASSWORD", "root"), database="testdb",
    )


# ------------------------------------------------------------------ #
#  ViewModel                                                            #
# ------------------------------------------------------------------ #

class ActiveSPUser(BaseModel, ViewModel):
    __tablename__  = "sp_active_users"
    __view_query__ = "SELECT * FROM sp_users WHERE active = 1"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=50)
    active = BoolField(default=True)


@pytest.fixture(autouse=True)
def _view_table():
    yield
    with db.connect() as conn:
        conn.cursor().execute("DROP VIEW IF EXISTS sp_active_users")


def test_view_model_reads():
    ActiveSPUser.create_table()
    rows = ActiveSPUser.all()
    assert [r["name"] for r in rows] == ["Alice"]
    assert ActiveSPUser.count() == 1
    assert ActiveSPUser.get(name="Alice") is not None


def test_view_model_create_table_idempotent():
    ActiveSPUser.create_table()
    ActiveSPUser.create_table()  # must not raise (DROP+CREATE under the hood)
    assert ActiveSPUser.count() == 1


def test_view_model_blocks_writes():
    ActiveSPUser.create_table()
    with pytest.raises(ViewReadOnlyError):
        ActiveSPUser.create(name="Eve", active=True)
    with pytest.raises(ViewReadOnlyError):
        ActiveSPUser.update({"name": "x"}, id=1)
    with pytest.raises(ViewReadOnlyError):
        ActiveSPUser.delete(id=1)
    with pytest.raises(ViewReadOnlyError):
        ActiveSPUser.bulk_create([{"name": "x"}])
    with pytest.raises(ViewReadOnlyError):
        ActiveSPUser.bulk_update([{"id": 1, "name": "x"}])
    with pytest.raises(ViewReadOnlyError):
        ActiveSPUser.bulk_upsert([{"id": 1, "name": "x"}])
    with pytest.raises(ViewReadOnlyError):
        ActiveSPUser.bulk_delete([1])


def test_view_model_drop_table():
    ActiveSPUser.create_table()
    ActiveSPUser.drop_table()
    with pytest.raises(Exception):
        ActiveSPUser.all()


def test_view_model_requires_view_query():
    class NoQueryView(BaseModel, ViewModel):
        __tablename__ = "sp_no_query_view"
        id = IntField(primary_key=True)

    with pytest.raises(ValueError, match="__view_query__"):
        NoQueryView.create_table()
