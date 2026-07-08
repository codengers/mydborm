# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_query_logging.py
# Project     : mydborm
# License     : MIT
# Description : Tests for query/SQL logging — db.configure(echo=True),
#               the "mydborm.sql" logger, and db.queries / clear_queries().
#               Uses SQLite (no external service, no skip guard).
# =============================================================================

import logging

import pytest

from mydborm import BaseModel, IntField, StrField, db


class QLProduct(BaseModel):
    __tablename__ = "ql_products"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


@pytest.fixture(autouse=True)
def reset_db():
    yield
    db.close()


def _configure(echo):
    db.configure(dialect="sqlite", database=":memory:", echo=echo)
    QLProduct.create_table()
    db.clear_queries()


def test_echo_false_by_default_no_queries_tracked():
    _configure(echo=False)
    QLProduct.create(name="Widget")
    assert db.queries == []


def test_echo_true_tracks_queries():
    _configure(echo=True)
    QLProduct.create(name="Widget")
    assert len(db.queries) >= 1
    inserts = [q for q in db.queries if "INSERT" in q["sql"]]
    assert len(inserts) == 1
    assert inserts[0]["params"] == ["Widget"]
    assert isinstance(inserts[0]["duration_ms"], float)


def test_echo_true_emits_debug_log_records(caplog):
    _configure(echo=True)
    with caplog.at_level(logging.DEBUG, logger="mydborm.sql"):
        QLProduct.create(name="Gadget")
    messages = [r.message for r in caplog.records if r.name == "mydborm.sql"]
    assert any("INSERT" in m and "Gadget" in m for m in messages)


def test_echo_false_emits_no_log_records(caplog):
    _configure(echo=False)
    with caplog.at_level(logging.DEBUG, logger="mydborm.sql"):
        QLProduct.create(name="Silent")
    messages = [r.message for r in caplog.records if r.name == "mydborm.sql"]
    assert messages == []


def test_clear_queries_empties_the_log():
    _configure(echo=True)
    QLProduct.create(name="A")
    assert len(db.queries) > 0
    db.clear_queries()
    assert db.queries == []


def test_db_execute_is_logged_after_connection_already_cached():
    # db.execute() has a fast-path that reuses an existing cached
    # connection instead of going through connect() — this must still
    # be wrapped when echo=True (regression guard).
    _configure(echo=True)
    QLProduct.create(name="First")  # establishes + caches a connection
    db.clear_queries()
    db.execute("UPDATE ql_products SET name = %s WHERE name = %s", ["Second", "First"])
    updates = [q for q in db.queries if "UPDATE" in q["sql"]]
    assert len(updates) == 1


def test_executemany_logs_row_count_not_full_param_list():
    _configure(echo=True)
    with db.connect() as conn:
        cur = conn.cursor()
        cur.executemany(
            "INSERT INTO ql_products (name) VALUES (%s)",
            [["A"], ["B"], ["C"]],
        )
    many = [q for q in db.queries if "3 rows" in str(q["params"])]
    assert len(many) == 1


def test_query_builder_get_is_logged():
    _configure(echo=True)
    pid = QLProduct.create(name="Findme")
    db.clear_queries()
    QLProduct.get(id=pid)
    selects = [q for q in db.queries if "SELECT" in q["sql"]]
    assert len(selects) == 1


def test_logging_does_not_suppress_exceptions():
    _configure(echo=True)
    with pytest.raises(Exception):
        db.execute("INSERT INTO nonexistent_table_xyz (col) VALUES (%s)", ["x"])


def test_migration_engine_connection_manager_supports_echo():
    from mydborm.db import ConnectionManager
    mgr = ConnectionManager()
    mgr.configure(dialect="sqlite", database=":memory:", echo=True)
    with mgr.connect() as conn:
        conn.cursor().execute("SELECT 1")
    assert len(mgr.queries) == 1
