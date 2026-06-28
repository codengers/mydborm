# =============================================================================
# File        : tests/test_exceptions.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.5.0
# License     : MIT
# Description : pytest tests for custom exception hierarchy — covers
#               instantiation, inheritance, attributes, and __str__.
# =============================================================================

import pytest
import mydborm
from mydborm.exceptions import (
    MydbormError,
    ConnectionError, ConnectionTimeoutError, NotConfiguredError,
    QueryError, RecordNotFoundError, MultipleRecordsError,
    ValidationError, FieldRequiredError, FieldTypeError, FieldLengthError,
    BulkOperationError, BulkInsertError, BulkUpdateError, BulkUpsertError,
    BulkDeleteError,
    TransactionError, SavepointError, DeadlockError, RetryExhaustedError,
    MigrationError, MigrationAlreadyAppliedError, MigrationNotFoundError,
    SchemaError, UnsupportedDialectError,
)


# ------------------------------------------------------------------ #
#  Base exception                                                      #
# ------------------------------------------------------------------ #

def test_mydborm_error_base():
    e = MydbormError("base error")
    assert str(e) == "base error"
    assert e.message == "base error"


def test_mydborm_error_with_context():
    e = MydbormError("error", table="users", dialect="mysql")
    assert "table='users'" in str(e)
    assert "dialect='mysql'" in str(e)


def test_mydborm_error_is_exception():
    with pytest.raises(MydbormError):
        raise MydbormError("test")


# ------------------------------------------------------------------ #
#  Connection exceptions                                               #
# ------------------------------------------------------------------ #

def test_connection_error():
    e = ConnectionError("cannot connect",
                        dialect="mysql", host="127.0.0.1", port=3306)
    assert e.dialect == "mysql"
    assert e.host    == "127.0.0.1"
    assert e.port    == 3306
    assert issubclass(ConnectionError, MydbormError)


def test_connection_timeout_error():
    e = ConnectionTimeoutError("timed out", timeout=30,
                               dialect="mysql", host="127.0.0.1")
    assert e.timeout == 30
    assert issubclass(ConnectionTimeoutError, ConnectionError)


def test_not_configured_error():
    e = NotConfiguredError("db not configured")
    assert issubclass(NotConfiguredError, MydbormError)
    assert str(e) == "db not configured"


# ------------------------------------------------------------------ #
#  Query exceptions                                                    #
# ------------------------------------------------------------------ #

def test_query_error():
    e = QueryError("query failed",
                   sql="SELECT * FROM users",
                   params=[1, 2])
    assert e.sql    == "SELECT * FROM users"
    assert e.params == [1, 2]
    assert issubclass(QueryError, MydbormError)


def test_record_not_found_error():
    e = RecordNotFoundError("not found",
                            model="User",
                            filters={"id": 999})
    assert e.model   == "User"
    assert e.filters == {"id": 999}
    assert issubclass(RecordNotFoundError, MydbormError)


def test_multiple_records_error():
    e = MultipleRecordsError("multiple found", model="User", count=3)
    assert e.model == "User"
    assert e.count == 3
    assert issubclass(MultipleRecordsError, MydbormError)


# ------------------------------------------------------------------ #
#  Validation exceptions                                               #
# ------------------------------------------------------------------ #

def test_validation_error():
    e = ValidationError("invalid", field="email",
                        value="bad", reason="invalid format")
    assert e.field  == "email"
    assert e.value  == "bad"
    assert e.reason == "invalid format"
    assert issubclass(ValidationError, MydbormError)


def test_field_required_error():
    e = FieldRequiredError("required", field="username")
    assert e.field == "username"
    assert issubclass(FieldRequiredError, ValidationError)
    assert issubclass(FieldRequiredError, MydbormError)


def test_field_type_error():
    e = FieldTypeError("wrong type", field="age", value="twenty")
    assert e.field == "age"
    assert issubclass(FieldTypeError, ValidationError)


def test_field_length_error():
    e = FieldLengthError("too long", field="name", value="x" * 300)
    assert e.field == "name"
    assert issubclass(FieldLengthError, ValidationError)


# ------------------------------------------------------------------ #
#  Bulk exceptions                                                     #
# ------------------------------------------------------------------ #

def test_bulk_operation_error():
    e = BulkOperationError("bulk failed",
                           inserted=850, failed=2,
                           errors=[{"chunk": 3, "error": "timeout"}])
    assert e.inserted  == 850
    assert e.failed    == 2
    assert len(e.errors) == 1
    assert "inserted=850" in str(e)
    assert "failed=2"     in str(e)


def test_bulk_insert_error():
    e = BulkInsertError("insert failed", inserted=100, failed=5)
    assert issubclass(BulkInsertError, BulkOperationError)
    assert issubclass(BulkInsertError, MydbormError)
    assert e.inserted == 100
    assert e.failed   == 5


def test_bulk_update_error():
    e = BulkUpdateError("update failed", inserted=0, failed=3)
    assert issubclass(BulkUpdateError, BulkOperationError)


def test_bulk_upsert_error():
    e = BulkUpsertError("upsert failed", inserted=50, failed=2)
    assert issubclass(BulkUpsertError, BulkOperationError)


def test_bulk_delete_error():
    e = BulkDeleteError("delete failed", inserted=0, failed=2)
    assert issubclass(BulkDeleteError, BulkOperationError)


def test_bulk_error_empty_errors_list():
    e = BulkInsertError("failed", inserted=0, failed=10)
    assert e.errors == []


# ------------------------------------------------------------------ #
#  Transaction exceptions                                              #
# ------------------------------------------------------------------ #

def test_transaction_error():
    e = TransactionError("tx failed")
    assert issubclass(TransactionError, MydbormError)


def test_savepoint_error():
    e = SavepointError("savepoint failed", savepoint="sp1")
    assert e.savepoint == "sp1"
    assert issubclass(SavepointError, TransactionError)
    assert issubclass(SavepointError, MydbormError)


def test_deadlock_error():
    e = DeadlockError("deadlock detected")
    assert issubclass(DeadlockError, TransactionError)


def test_retry_exhausted_error():
    original = Exception("connection timeout")
    e = RetryExhaustedError("gave up", attempts=3, last_error=original)
    assert e.attempts   == 3
    assert e.last_error == original
    assert "attempts=3" in str(e)
    assert issubclass(RetryExhaustedError, MydbormError)


# ------------------------------------------------------------------ #
#  Migration exceptions                                                #
# ------------------------------------------------------------------ #

def test_migration_error():
    e = MigrationError("migration failed",
                       version="abc123",
                       sql="ALTER TABLE users ADD COLUMN phone VARCHAR(20)")
    assert e.version == "abc123"
    assert issubclass(MigrationError, MydbormError)


def test_migration_already_applied():
    e = MigrationAlreadyAppliedError("already applied",
                                     version="abc123")
    assert issubclass(MigrationAlreadyAppliedError, MigrationError)


def test_migration_not_found():
    e = MigrationNotFoundError("not found", version="xyz999")
    assert issubclass(MigrationNotFoundError, MigrationError)


# ------------------------------------------------------------------ #
#  Schema exceptions                                                   #
# ------------------------------------------------------------------ #

def test_schema_error():
    e = SchemaError("schema mismatch",
                    table="users",
                    missing_columns=["phone"],
                    extra_columns=["old_field"])
    assert e.table           == "users"
    assert e.missing_columns == ["phone"]
    assert e.extra_columns   == ["old_field"]
    assert "missing in DB: ['phone']"    in str(e)
    assert "extra in DB: ['old_field']"  in str(e)
    assert issubclass(SchemaError, MydbormError)


def test_schema_error_empty():
    e = SchemaError("ok", table="users")
    assert e.missing_columns == []
    assert e.extra_columns   == []


# ------------------------------------------------------------------ #
#  Dialect exceptions                                                  #
# ------------------------------------------------------------------ #

def test_unsupported_dialect_error():
    e = UnsupportedDialectError("bad dialect",
                                dialect="oracle",
                                supported=["mysql", "yugabyte"])
    assert e.dialect   == "oracle"
    assert e.supported == ["mysql", "yugabyte"]
    assert issubclass(UnsupportedDialectError, MydbormError)


# ------------------------------------------------------------------ #
#  Exported from mydborm package                                       #
# ------------------------------------------------------------------ #

def test_exceptions_exported_from_package():
    assert hasattr(mydborm, "MydbormError")
    assert hasattr(mydborm, "BulkInsertError")
    assert hasattr(mydborm, "ValidationError")
    assert hasattr(mydborm, "TransactionError")
    assert hasattr(mydborm, "SchemaError")
    assert hasattr(mydborm, "RetryExhaustedError")


def test_catch_as_base_exception():
    with pytest.raises(MydbormError):
        raise BulkInsertError("test", inserted=0, failed=1)

    with pytest.raises(MydbormError):
        raise ValidationError("test", field="email")

    with pytest.raises(MydbormError):
        raise SchemaError("test", table="users")