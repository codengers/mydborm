"""
test_connection.py — Connection manager tests.
"""
import pytest
from mydborm.db import db


def test_configure_mysql():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password="root", database="testdb"
    )
    assert db.dialect == "mysql"


def test_mysql_connect():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password="root", database="testdb"
    )
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
    db.close()


def test_missing_dialect_raises():
    with pytest.raises(ValueError, match="dialect is required"):
        db.configure(host="localhost", user="root")


def test_not_configured_raises():
    db._config = {}
    with pytest.raises(RuntimeError, match="not configured"):
        with db.connect() as conn:
            pass