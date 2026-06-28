# =============================================================================
# File        : exceptions.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.5.0
# License     : MIT
# Description : Custom exception hierarchy for mydborm. Provides specific
#               exception types for connection, query, validation, bulk
#               operations, migration, and transaction errors.
# =============================================================================


# ------------------------------------------------------------------ #
#  Base exception                                                      #
# ------------------------------------------------------------------ #

class MydbormError(Exception):
    """
    Base exception for all mydborm errors.
    Catch this to handle any mydborm-related error.

    Usage:
        try:
            User.create(username="alice")
        except MydbormError as e:
            print(f"ORM error: {e}")
    """
    def __init__(self, message: str = "", **context):
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self):
        if self.context:
            ctx = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} ({ctx})"
        return self.message


# ------------------------------------------------------------------ #
#  Connection exceptions                                               #
# ------------------------------------------------------------------ #

class ConnectionError(MydbormError):
    """
    Raised when a database connection cannot be established
    or an existing connection is lost.

    Usage:
        try:
            db.configure(dialect="mysql", host="bad-host", ...)
            with db.connect() as conn:
                pass
        except ConnectionError as e:
            print(f"Cannot connect: {e}")
    """
    def __init__(self, message: str = "", dialect: str = "",
                 host: str = "", port: int = 0):
        super().__init__(message, dialect=dialect, host=host, port=port)
        self.dialect = dialect
        self.host    = host
        self.port    = port


class ConnectionTimeoutError(ConnectionError):
    """Raised when a connection attempt times out."""
    def __init__(self, message: str = "", timeout: int = 0, **kwargs):
        super().__init__(message, **kwargs)
        self.timeout = timeout


class NotConfiguredError(MydbormError, RuntimeError):
    """
    Raised when a database operation is attempted before
    db.configure() or db.from_env() has been called.

    Also a RuntimeError (its original raised type before this exception
    was wired up), so existing `except RuntimeError` callers keep working.
    """
    pass


# ------------------------------------------------------------------ #
#  Query exceptions                                                    #
# ------------------------------------------------------------------ #

class QueryError(MydbormError):
    """
    Raised when a SQL query fails at the database level.

    Attributes:
        sql    : the SQL statement that failed
        params : the parameters passed to the query
    """
    def __init__(self, message: str = "", sql: str = "",
                 params: list = None):
        super().__init__(message, sql=sql)
        self.sql    = sql
        self.params = params or []


class RecordNotFoundError(MydbormError):
    """
    Raised when get() is called with strict=True and no row matches.

    Usage:
        user = User.get(id=999, strict=True)
        # raises RecordNotFoundError if not found
    """
    def __init__(self, message: str = "", model: str = "",
                 filters: dict = None):
        super().__init__(message, model=model)
        self.model   = model
        self.filters = filters or {}


class MultipleRecordsError(MydbormError):
    """
    Raised when get_one() finds more than one matching row.
    """
    def __init__(self, message: str = "", model: str = "",
                 count: int = 0):
        super().__init__(message, model=model, count=count)
        self.model = model
        self.count = count


# ------------------------------------------------------------------ #
#  Validation exceptions                                               #
# ------------------------------------------------------------------ #

class ValidationError(MydbormError):
    """
    Raised when field validation fails before a DB operation.

    Attributes:
        field   : the field name that failed
        value   : the value that was rejected
        reason  : human-readable reason
    """
    def __init__(self, message: str = "", field: str = "",
                 value=None, reason: str = ""):
        super().__init__(message, field=field)
        self.field  = field
        self.value  = value
        self.reason = reason


class FieldRequiredError(ValidationError, ValueError):
    """
    Raised when a required field is missing or None.
    Also a ValueError (its original raised type), so existing
    `except ValueError` callers keep working.
    """
    pass


class FieldTypeError(ValidationError, TypeError):
    """
    Raised when a field value has the wrong type.
    Also a TypeError (its original raised type), so existing
    `except TypeError` callers keep working.
    """
    pass


class FieldLengthError(ValidationError, ValueError):
    """
    Raised when a string field exceeds max_length.
    Also a ValueError (its original raised type), so existing
    `except ValueError` callers keep working.
    """
    pass


# ------------------------------------------------------------------ #
#  Bulk operation exceptions                                           #
# ------------------------------------------------------------------ #

class BulkOperationError(MydbormError):
    """
    Raised when a bulk operation partially or fully fails.

    Attributes:
        inserted  : number of successfully inserted rows
        failed    : number of failed rows
        errors    : list of error dicts with chunk + message
        result    : the partial BulkResult object if available
    """
    def __init__(self, message: str = "", inserted: int = 0,
                 failed: int = 0, errors: list = None):
        super().__init__(message, inserted=inserted, failed=failed)
        self.inserted = inserted
        self.failed   = failed
        self.errors   = errors or []

    def __str__(self):
        return (
            f"{self.message} "
            f"(inserted={self.inserted}, failed={self.failed}, "
            f"errors={len(self.errors)})"
        )


class BulkInsertError(BulkOperationError):
    """Raised when bulk_create fails on one or more chunks."""
    pass


class BulkUpdateError(BulkOperationError):
    """Raised when bulk_update fails on one or more records."""
    pass


class BulkUpsertError(BulkOperationError):
    """Raised when bulk_upsert fails on one or more records."""
    pass


class BulkDeleteError(BulkOperationError):
    """Raised when bulk_delete fails on one or more chunks."""
    pass


# ------------------------------------------------------------------ #
#  Transaction exceptions                                              #
# ------------------------------------------------------------------ #

class TransactionError(MydbormError):
    """
    Raised when a transaction cannot be started, committed,
    or rolled back.
    """
    pass


class SavepointError(TransactionError, RuntimeError):
    """
    Raised when a savepoint operation fails.
    Also a RuntimeError (its original raised type), so existing
    `except RuntimeError` callers keep working.
    """
    def __init__(self, message: str = "", savepoint: str = ""):
        super().__init__(message, savepoint=savepoint)
        self.savepoint = savepoint


class DeadlockError(TransactionError):
    """
    Raised when the database detects a deadlock.
    Retry the transaction after catching this.
    """
    pass


class RetryExhaustedError(MydbormError):
    """
    Raised when all retry attempts have been exhausted.

    Attributes:
        attempts  : number of attempts made
        last_error: the last exception that caused failure
    """
    def __init__(self, message: str = "", attempts: int = 0,
                 last_error: Exception = None):
        super().__init__(message, attempts=attempts)
        self.attempts   = attempts
        self.last_error = last_error

    def __str__(self):
        return (
            f"{self.message} "
            f"(attempts={self.attempts}, "
            f"last_error={self.last_error!r})"
        )


# ------------------------------------------------------------------ #
#  Migration exceptions                                                #
# ------------------------------------------------------------------ #

class MigrationError(MydbormError):
    """
    Raised when a schema migration fails.

    Attributes:
        version : migration version that failed
        sql     : SQL that caused the failure
    """
    def __init__(self, message: str = "", version: str = "",
                 sql: str = ""):
        super().__init__(message, version=version)
        self.version = version
        self.sql     = sql


class MigrationAlreadyAppliedError(MigrationError):
    """Raised when trying to apply an already-applied migration."""
    pass


class MigrationNotFoundError(MigrationError):
    """Raised when a migration version cannot be found."""
    pass


# ------------------------------------------------------------------ #
#  Schema exceptions                                                   #
# ------------------------------------------------------------------ #

class SchemaError(MydbormError):
    """
    Raised when model schema doesn't match the live database.

    Attributes:
        table           : table name with the mismatch
        missing_columns : columns in model but not in DB
        extra_columns   : columns in DB but not in model
    """
    def __init__(self, message: str = "", table: str = "",
                 missing_columns: list = None,
                 extra_columns: list = None):
        super().__init__(message, table=table)
        self.table           = table
        self.missing_columns = missing_columns or []
        self.extra_columns   = extra_columns   or []

    def __str__(self):
        parts = [self.message]
        if self.missing_columns:
            parts.append(f"missing in DB: {self.missing_columns}")
        if self.extra_columns:
            parts.append(f"extra in DB: {self.extra_columns}")
        return " | ".join(parts)


# ------------------------------------------------------------------ #
#  Dialect exceptions                                                  #
# ------------------------------------------------------------------ #

class UnsupportedDialectError(MydbormError, ValueError):
    """
    Raised when an unsupported database dialect is specified.
    Also a ValueError (its original raised type), so existing
    `except ValueError` callers keep working.
    """
    def __init__(self, message: str = "", dialect: str = "",
                 supported: list = None):
        super().__init__(message, dialect=dialect)
        self.dialect   = dialect
        self.supported = supported or ["mysql", "yugabyte", "postgres"]