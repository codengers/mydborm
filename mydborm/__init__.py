# =============================================================================
# File        : __init__.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Package entry point. Exposes the public API surface:
#               db connection manager, BaseModel, and all field types.
#               Install: pip install mydborm
#               Usage  : from mydborm import db, BaseModel, IntField
# =============================================================================
"""
mydborm — Lightweight ORM for MySQL and YugabyteDB.
"""

from .db import db
from .model import BaseModel
from .fields import (
    Field,
    IntField,
    StrField,
    TextField,
    BoolField,
    FloatField,
    DecimalField,
    DateField,
    DateTimeField,
    JSONField,
    ForeignKeyField,
)
from .exceptions import (
    MydbormError,
    ConnectionError,
    ConnectionTimeoutError,
    NotConfiguredError,
    QueryError,
    RecordNotFoundError,
    MultipleRecordsError,
    ValidationError,
    FieldRequiredError,
    FieldTypeError,
    FieldLengthError,
    BulkOperationError,
    BulkInsertError,
    BulkUpdateError,
    BulkUpsertError,
    TransactionError,
    SavepointError,
    DeadlockError,
    RetryExhaustedError,
    MigrationError,
    MigrationAlreadyAppliedError,
    MigrationNotFoundError,
    SchemaError,
    UnsupportedDialectError,
)
from .bulk import BulkResult, chunked_bulk_create, chunked_bulk_update, chunked_bulk_delete

__version__ = "0.5.0"
__author__  = "Codengers"
__license__ = "MIT"

__all__ = [
    "db",
    "BaseModel",
    "Field",
    "IntField",
    "StrField",
    "TextField",
    "BoolField",
    "FloatField",
    "DecimalField",
    "DateField",
    "DateTimeField",
    "JSONField",
    "ForeignKeyField",
    # Exceptions
    "MydbormError",
    "ConnectionError",
    "ConnectionTimeoutError",
    "NotConfiguredError",
    "QueryError",
    "RecordNotFoundError",
    "MultipleRecordsError",
    "ValidationError",
    "FieldRequiredError",
    "FieldTypeError",
    "FieldLengthError",
    "BulkOperationError",
    "BulkInsertError",
    "BulkUpdateError",
    "BulkUpsertError",
    "TransactionError",
    "SavepointError",
    "DeadlockError",
    "RetryExhaustedError",
    "MigrationError",
    "MigrationAlreadyAppliedError",
    "MigrationNotFoundError",
    "SchemaError",
    "UnsupportedDialectError",
    "BulkResult",
    "chunked_bulk_create",
    "chunked_bulk_update",
    "chunked_bulk_delete",
]

