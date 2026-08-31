# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_transactions.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.5.0
# License     : MIT
# Description : pytest tests for transaction management — savepoints,
#               nested transactions, bulk transactions, retry logic,
#               and UTF-8 encoding support.
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField
from mydborm.exceptions import RetryExhaustedError


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class Account(BaseModel):
    __tablename__ = "tx_accounts"
    id      = IntField(primary_key=True)
    name    = StrField(max_length=100, nullable=False)
    balance = IntField(nullable=False)
    active  = BoolField(default=True)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect  = "mysql",
        host     = "127.0.0.1",
        port     = 3307,
        user     = "root",
        password = os.environ.get("DB_PASSWORD", "root"),
        database = "testdb",
        charset  = "utf8mb4",
        encoding = "utf-8",
    )
    Account.create_table()
    yield
    Account.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM tx_accounts")
    yield


# ------------------------------------------------------------------ #
#  Encoding                                                            #
# ------------------------------------------------------------------ #

def test_encoding_property():
    assert db.encoding == "utf-8"


def test_charset_in_config():
    assert db._config.get("charset") == "utf8mb4"


def test_unicode_insert_and_retrieve():
    uid = Account.create(name="Atikrant Upadhye", balance=1000)
    row = Account.get(id=uid)
    assert row["name"] == "Atikrant Upadhye"


def test_unicode_special_characters():
    uid = Account.create(name="Jose Garcia", balance=500)
    row = Account.get(id=uid)
    assert row["name"] == "Jose Garcia"


def test_unicode_filter():
    Account.create(name="Alice Smith", balance=100)
    Account.create(name="Bob Jones",  balance=200)
    rows = Account.query().where("name__like", "Alice%").all()
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice Smith"


# ------------------------------------------------------------------ #
#  bulk_transaction                                                    #
# ------------------------------------------------------------------ #

def test_bulk_transaction_commits():
    with db.bulk_transaction():
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["alice", 1000]
        )
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["bob", 500]
        )
    assert Account.count() == 2


def test_bulk_transaction_rollback_on_error():
    initial = Account.count()
    try:
        with db.bulk_transaction():
            db.execute(
                "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
                ["carol", 200]
            )
            raise ValueError("simulated failure")
    except ValueError:
        pass
    assert Account.count() == initial


def test_bulk_transaction_multiple_models():
    with db.bulk_transaction():
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["dave", 300]
        )
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["eve", 400]
        )
        db.execute(
            "UPDATE tx_accounts SET balance = %s WHERE name = %s",
            [999, "dave"]
        )
    assert Account.count() == 2
    dave = Account.query().where("name", "dave").first()
    assert dave["balance"] == 999


# ------------------------------------------------------------------ #
#  Savepoints                                                          #
# ------------------------------------------------------------------ #

def test_savepoint_partial_rollback():
    with db.transaction():
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["alice", 100]
        )
        try:
            with db.savepoint("sp1"):
                db.execute(
                    "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
                    ["bob", 200]
                )
                raise ValueError("bob failed")
        except ValueError:
            pass
    assert Account.exists(name="alice") is True
    assert Account.exists(name="bob")   is False


def test_savepoint_commits_on_success():
    with db.transaction():
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["carol", 300]
        )
        with db.savepoint("sp2"):
            db.execute(
                "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
                ["dave", 400]
            )
    assert Account.exists(name="carol") is True
    assert Account.exists(name="dave")  is True


def test_savepoint_named():
    with db.transaction():
        with db.savepoint("my_savepoint") as sp:
            assert sp == "my_savepoint"
            db.execute(
                "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
                ["eve", 500]
            )
    assert Account.exists(name="eve") is True


def test_savepoint_auto_named():
    with db.transaction():
        with db.savepoint() as sp:
            assert sp.startswith("sp_")
            db.execute(
                "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
                ["frank", 600]
            )
    assert Account.exists(name="frank") is True


def test_multiple_savepoints():
    with db.transaction():
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["base", 100]
        )
        try:
            with db.savepoint("sp_a"):
                db.execute(
                    "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
                    ["sp_a_row", 200]
                )
                raise ValueError("rollback sp_a")
        except ValueError:
            pass
        with db.savepoint("sp_b"):
            db.execute(
                "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
                ["sp_b_row", 300]
            )
    assert Account.exists(name="base")    is True
    assert Account.exists(name="sp_a_row") is False
    assert Account.exists(name="sp_b_row") is True


def test_savepoint_outside_transaction_raises():
    db.close()
    with pytest.raises(RuntimeError, match="savepoint.*transaction"):
        with db.savepoint("bad"):
            pass


def test_savepoint_outside_transaction_raises_typed_exception():
    from mydborm.exceptions import SavepointError
    db.close()
    with pytest.raises(SavepointError, match="savepoint.*transaction"):
        with db.savepoint("bad"):
            pass


# ------------------------------------------------------------------ #
#  Nested transactions                                                 #
# ------------------------------------------------------------------ #

def test_nested_transaction_inside_transaction():
    with db.transaction():
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["outer", 100]
        )
        with db.nested_transaction():
            db.execute(
                "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
                ["inner", 200]
            )
    assert Account.exists(name="outer") is True
    assert Account.exists(name="inner") is True


def test_nested_transaction_rollback_inner():
    with db.transaction():
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["outer2", 100]
        )
        try:
            with db.nested_transaction():
                db.execute(
                    "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
                    ["inner2", 200]
                )
                raise ValueError("inner failed")
        except ValueError:
            pass
    assert Account.exists(name="outer2") is True
    assert Account.exists(name="inner2") is False


def test_nested_transaction_without_outer():
    with db.nested_transaction():
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["standalone", 100]
        )
    assert Account.exists(name="standalone") is True


# ------------------------------------------------------------------ #
#  transaction_with_retry                                              #
# ------------------------------------------------------------------ #

def test_transaction_with_retry_success():
    def do_insert(conn):
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["retry_user", 100]
        )

    db.transaction_with_retry(do_insert, retries=3)
    assert Account.exists(name="retry_user") is True


def test_transaction_with_retry_raises_on_non_deadlock():
    """Non-deadlock errors should propagate without retry."""
    def do_fail(conn):
        raise ValueError("not a deadlock")

    raised = False
    try:
        db.transaction_with_retry(do_fail, retries=2)
    except ValueError as e:
        raised = True
        assert str(e) == "not a deadlock"
    except Exception:
        raised = True
    assert raised is True


def test_transaction_with_retry_recovers_from_deadlock_in_body():
    """
    Regression test: previously transaction_with_retry was a single-yield
    @contextmanager, so retrying an error raised by the caller's own
    statements (the realistic deadlock case) required yielding a second
    time from the same generator — contextlib forbids that and raised
    RuntimeError("generator didn't stop after throw()") instead of
    retrying. fn(conn) is a plain callable now, so it's re-invoked from
    scratch on each attempt.
    """
    attempts = []

    def do_transfer(conn):
        attempts.append(1)
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["deadlock_user", 100]
        )
        if len(attempts) < 3:
            raise RuntimeError(
                "Deadlock found when trying to get lock; try restarting transaction"
            )

    db.transaction_with_retry(do_transfer, retries=3, retry_delay=0.01)

    assert len(attempts) == 3
    assert Account.count(name="deadlock_user") == 1


def test_transaction_with_retry_exhausted_raises_retry_exhausted_error():
    def always_deadlocks(conn):
        raise RuntimeError(
            "Deadlock found when trying to get lock; try restarting transaction"
        )

    with pytest.raises(RetryExhaustedError) as exc_info:
        db.transaction_with_retry(always_deadlocks, retries=2, retry_delay=0.01)

    assert exc_info.value.attempts == 3


def test_transaction_with_retry_recovers_from_connection_loss():
    """transaction_with_retry() must also retry transient connection-loss
    errors (e.g. a server restart mid-transaction), not just deadlocks —
    it already gets a fresh connection each attempt via self.close(),
    which is exactly the recovery a dropped connection needs."""
    attempts = []

    def do_transfer(conn):
        attempts.append(1)
        db.execute(
            "INSERT INTO tx_accounts (name, balance) VALUES (%s,%s)",
            ["gone_away_user", 100]
        )
        if len(attempts) < 3:
            raise RuntimeError("MySQL server has gone away")

    db.transaction_with_retry(do_transfer, retries=3, retry_delay=0.01)

    assert len(attempts) == 3
    assert Account.count(name="gone_away_user") == 1


def test_transaction_with_retry_connection_loss_exhausted_raises():
    def always_drops(conn):
        raise RuntimeError("Lost connection to MySQL server during query")

    with pytest.raises(RetryExhaustedError) as exc_info:
        db.transaction_with_retry(always_drops, retries=2, retry_delay=0.01)

    assert exc_info.value.attempts == 3
    assert isinstance(exc_info.value.last_error, RuntimeError)