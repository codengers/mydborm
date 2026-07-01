# =============================================================================
# File        : fields.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Field definitions for declarative model schemas.
#               Includes IntField, StrField, TextField, BoolField,
#               FloatField, DecimalField, DateField, DateTimeField,
#               JSONField and ForeignKeyField with validation and
#               SQL column definition generation.
# =============================================================================

# =============================================================================
# File        : fields.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Field definitions for declarative model schemas.
#               Includes IntField, StrField, TextField, BoolField,
#               FloatField, DecimalField, DateField, DateTimeField,
#               JSONField, and ForeignKeyField with validation and
#               SQL column definition generation.
# =============================================================================
"""
fields.py — Field definitions for mydborm models.
Supports MySQL and YugabyteDB (YSQL) column types.
"""

import json
from datetime import date, datetime
from typing import Any, Optional

from .exceptions import FieldRequiredError, FieldTypeError, FieldLengthError


class Field:
    """
    Base class for all field types.
    Every field maps to a database column.
    """

    # Subclasses override this with their SQL type string
    sql_type: str = "TEXT"

    def __init__(
        self,
        primary_key: bool = False,
        nullable: bool = True,
        default: Any = None,
        unique: bool = False,
        index: bool = False,
        validators: list = None,
    ):
        self.primary_key = primary_key
        self.nullable    = nullable
        self.default     = default
        self.unique      = unique
        self.index       = index
        self.validators  = validators or []
        self.name: Optional[str] = None   # set by ModelMeta

    def validate(self, value: Any) -> Any:
        """Validate and coerce value before insert/update."""
        if value is None:
            if not self.nullable and self.default is None \
                    and not self.primary_key:
                raise FieldRequiredError(
                    f"Field '{self.name}' cannot be None.",
                    field=self.name,
                )
            return self.default if value is None else value
        # Run custom validators
        _apply_validators(self, value)
        return value

    def to_sql_def(self, dialect: str = "mysql") -> str:
        """Return the SQL column definition string."""
        parts = [self.sql_type]
        if self.primary_key:
            if dialect in ("yugabyte", "postgres"):
                parts = ["SERIAL PRIMARY KEY"]
            else:
                parts.append("PRIMARY KEY AUTO_INCREMENT")
        elif not self.nullable:
            parts.append("NOT NULL")
        if self.unique and not self.primary_key:
            parts.append("UNIQUE")
        if self.default is not None and not self.primary_key:
            parts.append(f"DEFAULT {self._format_default()}")
        return " ".join(parts)

    def _format_default(self) -> str:
        if isinstance(self.default, str):
            return f"'{self.default}'"
        if isinstance(self.default, bool):
            return "1" if self.default else "0"
        return str(self.default)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"name={self.name!r} "
            f"sql_type={self.sql_type!r}>"
        )


# ------------------------------------------------------------------ #
#  Concrete field types                                                #
# ------------------------------------------------------------------ #

class IntField(Field):
    """Integer column — INT in MySQL, INTEGER in YSQL."""
    sql_type = "INT"

    def validate(self, value: Any) -> Any:
        value = super().validate(value)
        if value is not None and not isinstance(value, int):
            raise FieldTypeError(
                f"Field '{self.name}' expects int, got {type(value).__name__}.",
                field=self.name, value=value,
            )
        return value


class StrField(Field):
    """Variable-length string — VARCHAR(n)."""
    def __init__(self, max_length: int = 255, **kwargs):
        super().__init__(**kwargs)
        self.max_length = max_length
        self.sql_type   = f"VARCHAR({max_length})"

    def validate(self, value: Any) -> Any:
        value = super().validate(value)
        if value is not None:
            if not isinstance(value, str):
                raise FieldTypeError(
                    f"Field '{self.name}' expects str, "
                    f"got {type(value).__name__}.",
                    field=self.name, value=value,
                )
            if len(value) > self.max_length:
                raise FieldLengthError(
                    f"Field '{self.name}' max length is "
                    f"{self.max_length}, got {len(value)}.",
                    field=self.name, value=value,
                )
        return value

class TextField(Field):
    """Unlimited text — TEXT column."""
    sql_type = "TEXT"

class BoolField(Field):
    """Boolean — TINYINT(1) in MySQL, BOOLEAN in PostgreSQL/Yugabyte."""

    sql_type = "TINYINT(1)"

    def validate(self, value):
        value = super().validate(value)
        if value is not None and not isinstance(value, bool):
            raise FieldTypeError(
                f"Field '{self.name}' expects bool, "
                f"got {type(value).__name__}.",
                field=self.name, value=value,
            )
        return value

    def to_sql_def(self, dialect: str = "mysql") -> str:
        if dialect in ("yugabyte", "postgres"):
            sql = "BOOLEAN"
        else:
            sql = "TINYINT(1)"

        if self.primary_key:
            sql += " PRIMARY KEY"

        if not self.nullable:
            sql += " NOT NULL"

        if self.default is not None:
            if dialect in ("yugabyte", "postgres"):
                default = "TRUE" if self.default else "FALSE"
            else:
                default = "1" if self.default else "0"
            sql += f" DEFAULT {default}"

        return sql

class FloatField(Field):
    """Floating point — FLOAT column."""
    sql_type = "FLOAT"

    def validate(self, value: Any) -> Any:
        value = super().validate(value)
        if value is not None and not isinstance(value, (int, float)):
            raise FieldTypeError(
                f"Field '{self.name}' expects float, "
                f"got {type(value).__name__}.",
                field=self.name, value=value,
            )
        return float(value) if value is not None else None

class DecimalField(Field):
    """Fixed precision — DECIMAL(p, s)."""
    def __init__(self, precision: int = 10, scale: int = 2, **kwargs):
        super().__init__(**kwargs)
        self.sql_type = f"DECIMAL({precision},{scale})"

class DateField(Field):
    """Date only — DATE column."""
    sql_type = "DATE"

    def validate(self, value: Any) -> Any:
        value = super().validate(value)
        if value is not None and not isinstance(value, (date, str)):
            raise FieldTypeError(
                f"Field '{self.name}' expects date or str, "
                f"got {type(value).__name__}.",
                field=self.name, value=value,
            )
        return value

class DateTimeField(Field):
    """Date + time — DATETIME column."""
    sql_type = "DATETIME"

    def validate(self, value: Any) -> Any:
        value = super().validate(value)
        if value is not None and not isinstance(value, (datetime, str)):
            raise FieldTypeError(
                f"Field '{self.name}' expects datetime or str, "
                f"got {type(value).__name__}.",
                field=self.name, value=value,
            )
        return value

class JSONField(Field):
    """
    JSON column.
    MySQL  → JSON
    YugabyteDB → JSONB

    Accepts a Python dict/list and stores it as JSON text — you don't
    need to call json.dumps() yourself. Reading it back is handled by
    BaseModel._fetch(), which parses the stored JSON text back into a
    dict/list (skipping values the driver already parsed itself, which
    psycopg2 does automatically for JSONB columns).
    """
    sql_type = "JSON"

    def validate(self, value):
        value = super().validate(value)
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "JSONB"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result

class ForeignKeyField(Field):
    """
    Foreign key reference to another model's primary key.

    BaseModel.create_table() resolves `to` against every defined
    BaseModel subclass and adds a real `FOREIGN KEY (...) REFERENCES
    ...` table constraint for this column. The referenced model must
    already exist as a table (create it first) and must have a
    single-column primary key.

    Usage:
        author = ForeignKeyField(to="Author", nullable=False)
    """
    sql_type = "INT"

    def __init__(self, to: str, **kwargs):
        super().__init__(**kwargs)
        self.to = to   # referenced model name as string

    def to_sql_def(self, dialect: str = "mysql") -> str:
        return super().to_sql_def(dialect)

# ------------------------------------------------------------------ #
#  Built-in validators                                                 #
# ------------------------------------------------------------------ #

import re as _re


class ValidationRule:
    """
    A reusable validation rule attached to a field.

    Usage:
        email   = StrField(validators=[EmailValidator()])
        age     = IntField(validators=[RangeValidator(min_val=0, max_val=150)])
        website = StrField(validators=[UrlValidator()])
        code    = StrField(validators=[RegexValidator(r'^[A-Z]{3}$')])
    """

    def validate(self, value, field_name: str):
        """Override in subclass. Raise ValueError on failure."""
        raise NotImplementedError


class EmailValidator(ValidationRule):
    """Validates email address format."""
    PATTERN = _re.compile(
        r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    )

    def validate(self, value, field_name: str):
        if value is not None and not self.PATTERN.match(str(value)):
            raise ValueError(
                f"Field '{field_name}' must be a valid email address. "
                f"Got: {value!r}"
            )


class UrlValidator(ValidationRule):
    """Validates URL format (http/https)."""
    PATTERN = _re.compile(
        r'^https?://[^\s/$.?#].[^\s]*$'
    )

    def validate(self, value, field_name: str):
        if value is not None and not self.PATTERN.match(str(value)):
            raise ValueError(
                f"Field '{field_name}' must be a valid URL. "
                f"Got: {value!r}"
            )


class RegexValidator(ValidationRule):
    """Validates value matches a regex pattern."""

    def __init__(self, pattern: str, message: str = None):
        self.pattern = _re.compile(pattern)
        self.message = message

    def validate(self, value, field_name: str):
        if value is not None and not self.pattern.match(str(value)):
            raise ValueError(
                self.message or
                f"Field '{field_name}' does not match "
                f"pattern {self.pattern.pattern!r}. Got: {value!r}"
            )


class RangeValidator(ValidationRule):
    """Validates numeric value is within a range."""

    def __init__(self, min_val=None, max_val=None):
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, value, field_name: str):
        if value is None:
            return
        if self.min_val is not None and value < self.min_val:
            raise ValueError(
                f"Field '{field_name}' must be >= {self.min_val}. "
                f"Got: {value}"
            )
        if self.max_val is not None and value > self.max_val:
            raise ValueError(
                f"Field '{field_name}' must be <= {self.max_val}. "
                f"Got: {value}"
            )


class MinLengthValidator(ValidationRule):
    """Validates string has minimum length."""

    def __init__(self, min_length: int):
        self.min_length = min_length

    def validate(self, value, field_name: str):
        if value is not None and len(str(value)) < self.min_length:
            raise ValueError(
                f"Field '{field_name}' must be at least "
                f"{self.min_length} characters. Got: {len(str(value))}"
            )


class ChoiceValidator(ValidationRule):
    """Validates value is one of the allowed choices."""

    def __init__(self, choices: list):
        self.choices = choices

    def validate(self, value, field_name: str):
        if value is not None and value not in self.choices:
            raise ValueError(
                f"Field '{field_name}' must be one of "
                f"{self.choices}. Got: {value!r}"
            )


# ------------------------------------------------------------------ #
#  Field validators support                                            #
# ------------------------------------------------------------------ #

def _apply_validators(field, value):
    """Run all ValidationRule instances attached to a field."""
    validators = getattr(field, "validators", [])
    for v in validators:
        v.validate(value, field.name)
    return value

# ================================================================== #
#  Extended field types — v1.1.0                                      #
#  Full MySQL ↔ YugabyteDB type mapping                              #
# ================================================================== #


# ------------------------------------------------------------------ #
#  Integer variants                                                    #
# ------------------------------------------------------------------ #

class TinyIntField(Field):
    """
    1-byte signed integer.
    MySQL: TINYINT (-128 to 127)
    YugabyteDB: SMALLINT (mapped up — no native TINYINT)

    Usage:
        age_group = TinyIntField(default=0)
        priority  = TinyIntField(nullable=False)
    """
    sql_type = "TINYINT"

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "SMALLINT"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise FieldTypeError(
                    f"Field '{self.name}' expects int, "
                    f"got {type(value).__name__}.",
                    field=self.name, value=value,
                )
            if not (-128 <= value <= 127):
                raise ValueError(
                    f"Field '{self.name}' TINYINT range is -128 to 127. "
                    f"Got: {value}"
                )
        return value


class SmallIntField(Field):
    """
    2-byte signed integer.
    MySQL: SMALLINT (-32768 to 32767)
    YugabyteDB: SMALLINT

    Usage:
        year      = SmallIntField(nullable=False)
        sort_order = SmallIntField(default=0)
    """
    sql_type = "SMALLINT"

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise FieldTypeError(
                    f"Field '{self.name}' expects int, "
                    f"got {type(value).__name__}.",
                    field=self.name, value=value,
                )
            if not (-32768 <= value <= 32767):
                raise ValueError(
                    f"Field '{self.name}' SMALLINT range is -32768 to 32767. "
                    f"Got: {value}"
                )
        return value


class BigIntField(Field):
    """
    8-byte signed integer.
    MySQL: BIGINT (-9223372036854775808 to 9223372036854775807)
    YugabyteDB: BIGINT

    Usage:
        file_size  = BigIntField(nullable=True)   # bytes
        view_count = BigIntField(default=0)
        user_id    = BigIntField(nullable=False)  # large-scale systems
    """
    sql_type = "BIGINT"

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise FieldTypeError(
                    f"Field '{self.name}' expects int, "
                    f"got {type(value).__name__}.",
                    field=self.name, value=value,
                )
        return value


class UnsignedBigIntField(Field):
    """
    8-byte unsigned integer.
    MySQL: BIGINT UNSIGNED (0 to 18446744073709551615)
    YugabyteDB: NUMERIC(20) — to prevent out-of-bounds errors

    Usage:
        checksum = UnsignedBigIntField(nullable=True)
        token_id = UnsignedBigIntField(nullable=False)
    """
    sql_type = "BIGINT UNSIGNED"

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "NUMERIC(20)"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise FieldTypeError(
                    f"Field '{self.name}' expects int, "
                    f"got {type(value).__name__}.",
                    field=self.name, value=value,
                )
            if value < 0:
                raise ValueError(
                    f"Field '{self.name}' UNSIGNED — value must be >= 0. "
                    f"Got: {value}"
                )
        return value


# ------------------------------------------------------------------ #
#  Floating-point variants                                             #
# ------------------------------------------------------------------ #

class DoubleField(Field):
    """
    8-byte double-precision floating-point.
    MySQL: DOUBLE (up to 17 significant digits)
    YugabyteDB: DOUBLE PRECISION (up to 15 significant digits)

    Usage:
        latitude  = DoubleField(nullable=True)
        longitude = DoubleField(nullable=True)
        score     = DoubleField(nullable=False, default=0.0)
    """
    sql_type = "DOUBLE"

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "DOUBLE PRECISION"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise FieldTypeError(
                    f"Field '{self.name}' expects float, "
                    f"got {type(value).__name__}.",
                    field=self.name, value=value,
                )
        return value


# ------------------------------------------------------------------ #
#  Bit field                                                           #
# ------------------------------------------------------------------ #

class BitField(Field):
    """
    Fixed-length bit string.
    MySQL: BIT(n) — stores n bits (1 to 64)
    YugabyteDB: BIT(n) / VARBIT

    Usage:
        flags      = BitField(length=8,  nullable=True)   # 8-bit flags
        permissions = BitField(length=16, nullable=False)  # 16-bit permissions
    """

    def __init__(self, length: int = 1, **kwargs):
        self.length  = length
        self.sql_type = f"BIT({length})"
        super().__init__(**kwargs)

    def to_sql_def(self, dialect: str = "mysql") -> str:
        self.sql_type = f"BIT({self.length})"
        return super().to_sql_def(dialect)


# ------------------------------------------------------------------ #
#  Fixed-length character field                                        #
# ------------------------------------------------------------------ #

class CharField(Field):
    """
    Fixed-length space-padded character string.
    MySQL: CHAR(n)
    YugabyteDB: CHAR(n)

    Use CHAR for fixed-width codes (country codes, currency codes, etc.)
    Use StrField (VARCHAR) for variable-length strings.

    Usage:
        country_code = CharField(length=2,  nullable=False)  # "US", "GB"
        currency     = CharField(length=3,  nullable=True)   # "USD", "EUR"
        status_code  = CharField(length=10, nullable=False)
    """

    def __init__(self, length: int = 1, **kwargs):
        self.length   = length
        self.sql_type = f"CHAR({length})"
        super().__init__(**kwargs)

    def to_sql_def(self, dialect: str = "mysql") -> str:
        self.sql_type = f"CHAR({self.length})"
        return super().to_sql_def(dialect)

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            value = str(value)
            if len(value) > self.length:
                raise FieldLengthError(
                    f"Field '{self.name}' CHAR({self.length}) — "
                    f"value too long: {len(value)} chars. Got: {value!r}",
                    field=self.name, value=value,
                )
        return value


# ------------------------------------------------------------------ #
#  Text variants                                                       #
# ------------------------------------------------------------------ #

class TinyTextField(Field):
    """
    Very short text — up to 255 bytes.
    MySQL: TINYTEXT
    YugabyteDB: TEXT (no native TINYTEXT)

    Usage:
        tagline = TinyTextField(nullable=True)
        note    = TinyTextField(nullable=True)
    """
    sql_type = "TINYTEXT"

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "TEXT"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result


class MediumTextField(Field):
    """
    Medium text — up to 16 MB.
    MySQL: MEDIUMTEXT
    YugabyteDB: TEXT

    Usage:
        article_body = MediumTextField(nullable=False)
        log_data     = MediumTextField(nullable=True)
    """
    sql_type = "MEDIUMTEXT"

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "TEXT"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result


class LongTextField(Field):
    """
    Very long text — up to 4 GB.
    MySQL: LONGTEXT
    YugabyteDB: TEXT

    Usage:
        book_content = LongTextField(nullable=True)
        raw_html     = LongTextField(nullable=True)
    """
    sql_type = "LONGTEXT"

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "TEXT"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result


# ------------------------------------------------------------------ #
#  Binary fields                                                       #
# ------------------------------------------------------------------ #

class BinaryField(Field):
    """
    Fixed-length binary string.
    MySQL: BINARY(n)
    YugabyteDB: BYTEA

    Usage:
        hash_value = BinaryField(length=32, nullable=True)   # SHA-256 = 32 bytes
        uuid_bytes = BinaryField(length=16, nullable=False)  # UUID = 16 bytes
    """

    def __init__(self, length: int = 1, **kwargs):
        self.length   = length
        self.sql_type = f"BINARY({length})"
        super().__init__(**kwargs)

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "BYTEA"
        else:
            self.sql_type = f"BINARY({self.length})"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result


class VarBinaryField(Field):
    """
    Variable-length binary string.
    MySQL: VARBINARY(n)
    YugabyteDB: BYTEA

    Usage:
        signature  = VarBinaryField(max_length=256, nullable=True)
        public_key = VarBinaryField(max_length=512, nullable=False)
    """

    def __init__(self, max_length: int = 255, **kwargs):
        self.max_length = max_length
        self.sql_type   = f"VARBINARY({max_length})"
        super().__init__(**kwargs)

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "BYTEA"
        else:
            self.sql_type = f"VARBINARY({self.max_length})"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result


class BlobField(Field):
    """
    Binary large object — for images, files, audio, etc.
    MySQL: BLOB (up to 65 KB) / MEDIUMBLOB (16 MB) / LONGBLOB (4 GB)
    YugabyteDB: BYTEA

    Usage:
        thumbnail  = BlobField(nullable=True)
        attachment = BlobField(blob_type="LONGBLOB", nullable=True)
    """
    VALID_TYPES = ("TINYBLOB", "BLOB", "MEDIUMBLOB", "LONGBLOB")

    def __init__(self, blob_type: str = "BLOB", **kwargs):
        if blob_type not in self.VALID_TYPES:
            raise ValueError(
                f"blob_type must be one of {self.VALID_TYPES}. "
                f"Got: {blob_type!r}"
            )
        self.blob_type = blob_type
        self.sql_type  = blob_type
        super().__init__(**kwargs)

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "BYTEA"
        else:
            self.sql_type = self.blob_type
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result


# ------------------------------------------------------------------ #
#  Time fields                                                         #
# ------------------------------------------------------------------ #

class TimeField(Field):
    """
    Time of day without date or timezone.
    MySQL: TIME (-838:59:59 to 838:59:59)
    YugabyteDB: TIME

    Usage:
        opens_at  = TimeField(nullable=True)
        closes_at = TimeField(nullable=True)
        duration  = TimeField(nullable=True)
    """
    sql_type = "TIME"

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            import datetime
            if not isinstance(value, (datetime.time, str)):
                raise FieldTypeError(
                    f"Field '{self.name}' expects datetime.time or str, "
                    f"got {type(value).__name__}.",
                    field=self.name, value=value,
                )
        return value


class TimestampField(Field):
    """
    Date + time with timezone support.
    MySQL: TIMESTAMP (stored as UTC, displayed in server timezone)
    YugabyteDB: TIMESTAMPTZ (timezone-aware)

    Use TimestampField for created_at/updated_at columns that need
    timezone awareness. Use DateTimeField for timezone-naive datetimes.

    Usage:
        created_at = TimestampField(nullable=True)
        updated_at = TimestampField(nullable=True)
        expires_at = TimestampField(nullable=True)
    """
    sql_type = "TIMESTAMP"

    def to_sql_def(self, dialect: str = "mysql") -> str:
        original = self.sql_type
        if dialect in ("yugabyte", "postgres"):
            self.sql_type = "TIMESTAMPTZ"
        result = super().to_sql_def(dialect)
        self.sql_type = original
        return result

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            import datetime
            if not isinstance(value, (datetime.datetime, str)):
                raise FieldTypeError(
                    f"Field '{self.name}' expects datetime.datetime or str, "
                    f"got {type(value).__name__}.",
                    field=self.name, value=value,
                )
        return value


# ------------------------------------------------------------------ #
#  Enum field                                                          #
# ------------------------------------------------------------------ #

class EnumField(Field):
    """
    Enumerated type — only allows a fixed set of string values.
    MySQL: ENUM('val1', 'val2', ...)
    YugabyteDB: VARCHAR with CHECK constraint (or native ENUM type)

    Usage:
        status   = EnumField(choices=["pending","processing","shipped","delivered"])
        priority = EnumField(choices=["low","medium","high","critical"])
        size     = EnumField(choices=["XS","S","M","L","XL","XXL"])
    """

    def __init__(self, choices: list, **kwargs):
        if not choices:
            raise ValueError("EnumField requires at least one choice.")
        self.choices  = choices
        self.sql_type = (
            "ENUM(" + ", ".join(f"'{c}'" for c in choices) + ")"
        )
        super().__init__(**kwargs)

    def to_sql_def(self, dialect: str = "mysql") -> str:
        if dialect in ("yugabyte", "postgres"):
            # YugabyteDB: use VARCHAR with max length of longest choice
            max_len       = max(len(c) for c in self.choices)
            original      = self.sql_type
            self.sql_type = f"VARCHAR({max_len})"
            result        = super().to_sql_def(dialect)
            self.sql_type = original
            return result
        return super().to_sql_def(dialect)

    def validate(self, value):
        value = super().validate(value)
        if value is not None and value not in self.choices:
            raise ValueError(
                f"Field '{self.name}' must be one of {self.choices}. "
                f"Got: {value!r}"
            )
        return value


# ------------------------------------------------------------------ #
#  Set field                                                           #
# ------------------------------------------------------------------ #

class SetField(Field):
    """
    A set of string values — stores multiple choices from a fixed list.
    MySQL: SET('val1','val2',...) — comma-separated string
    YugabyteDB: TEXT[] (native array)

    Usage:
        tags        = SetField(choices=["python","java","go","rust"])
        permissions = SetField(choices=["read","write","admin","delete"])
        days        = SetField(choices=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"])
    """

    def __init__(self, choices: list, **kwargs):
        if not choices:
            raise ValueError("SetField requires at least one choice.")
        self.choices  = choices
        self.sql_type = (
            "SET(" + ", ".join(f"'{c}'" for c in choices) + ")"
        )
        super().__init__(**kwargs)

    def to_sql_def(self, dialect: str = "mysql") -> str:
        if dialect in ("yugabyte", "postgres"):
            original      = self.sql_type
            self.sql_type = "TEXT[]"
            result        = super().to_sql_def(dialect)
            self.sql_type = original
            return result
        return super().to_sql_def(dialect)

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            # Accept comma-separated string or list
            if isinstance(value, str):
                items = [v.strip() for v in value.split(",")]
            elif isinstance(value, (list, set, tuple)):
                items = list(value)
            else:
                raise FieldTypeError(
                    f"Field '{self.name}' expects str or list, "
                    f"got {type(value).__name__}.",
                    field=self.name, value=value,
                )
            invalid = [i for i in items if i not in self.choices]
            if invalid:
                raise ValueError(
                    f"Field '{self.name}' invalid values: {invalid}. "
                    f"Allowed: {self.choices}"
                )
        return value
    
# ================================================================== #
#  Password and Encrypted fields — v1.2.0                             #
# ================================================================== #


# ------------------------------------------------------------------ #
#  PasswordField — one-way hashing (bcrypt)                           #
# ------------------------------------------------------------------ #

class PasswordField(Field):
    """
    One-way password hashing using bcrypt.
    Stores a bcrypt hash — CANNOT be decrypted.
    Use .verify(plain, hashed) to check passwords.

    MySQL:      VARCHAR(255)
    YugabyteDB: VARCHAR(255)

    Usage:
        class User(BaseModel):
            __tablename__ = "users"
            id       = IntField(primary_key=True)
            username = StrField(max_length=50, nullable=False)
            password = PasswordField(nullable=False)

        # Create user — password auto-hashed
        uid = User.create(username="alice", password="mysecretpass")

        # Verify password
        user = User.get(id=uid)
        ok   = PasswordField.verify("mysecretpass", user["password"])
        print(ok)   # True

        # Wrong password
        ok = PasswordField.verify("wrongpass", user["password"])
        print(ok)   # False
    """
    sql_type = "VARCHAR(255)"

    def __init__(self, rounds: int = 12, **kwargs):
        """
        Args:
            rounds: bcrypt work factor (4-31). Higher = slower = more secure.
                    Default 12 is a good balance for production.
        """
        self.rounds = rounds
        super().__init__(**kwargs)

    def validate(self, value):
        """Hash the password before storing."""
        value = super().validate(value)
        if value is None:
            return None

        # Already hashed — don't double-hash
        if isinstance(value, str) and value.startswith("$2b$"):
            return value
        if isinstance(value, bytes) and value.startswith(b"$2b$"):
            return value.decode("utf-8")

        try:
            import bcrypt
        except ImportError:
            raise ImportError(
                "PasswordField requires bcrypt. "
                "Install it: pip install bcrypt"
            )

        if isinstance(value, str):
            value = value.encode("utf-8")
        elif not isinstance(value, bytes):
            raise FieldTypeError(
                f"Field '{self.name}' expects str or bytes password, "
                f"got {type(value).__name__}.",
                field=self.name, value=value,
            )

        hashed = bcrypt.hashpw(value, bcrypt.gensalt(rounds=self.rounds))
        return hashed.decode("utf-8")

    @staticmethod
    def verify(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain-text password against a stored bcrypt hash.

        Args:
            plain_password  : the password the user typed
            hashed_password : the stored hash from the database

        Returns:
            True if password matches, False otherwise

        Usage:
            user = User.get(id=1)
            if PasswordField.verify("mysecret", user["password"]):
                print("Login successful!")
            else:
                print("Wrong password")
        """
        try:
            import bcrypt
        except ImportError:
            raise ImportError(
                "PasswordField requires bcrypt. "
                "Install it: pip install bcrypt"
            )

        if isinstance(plain_password, str):
            plain_password = plain_password.encode("utf-8")
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode("utf-8")

        try:
            return bcrypt.checkpw(plain_password, hashed_password)
        except Exception:
            return False

    @staticmethod
    def hash(plain_password: str, rounds: int = 12) -> str:
        """
        Hash a password manually without storing.

        Usage:
            hashed = PasswordField.hash("mysecret")
        """
        try:
            import bcrypt
        except ImportError:
            raise ImportError("pip install bcrypt")

        if isinstance(plain_password, str):
            plain_password = plain_password.encode("utf-8")
        return bcrypt.hashpw(
            plain_password,
            bcrypt.gensalt(rounds=rounds)
        ).decode("utf-8")

    def needs_rehash(self, hashed_password: str) -> bool:
        """
        Check if a stored hash needs to be upgraded — true when the hash's
        own encoded cost factor differs from this field's current `rounds`
        (e.g. rounds was raised from 10 to 12 after the hash was created).

        Usage:
            user = User.get(id=1)
            if pwd_field.needs_rehash(user["password"]):
                # Update with new hash on next login
                User.update({"password": new_plain}, id=user["id"])
        """
        if isinstance(hashed_password, bytes):
            hashed_password = hashed_password.decode("utf-8")

        # bcrypt hash format: $<algorithm>$<cost>$<salt+hash>
        parts = hashed_password.split("$")
        if len(parts) < 3:
            return True  # not a recognizable bcrypt hash — needs rehashing

        try:
            current_rounds = int(parts[2])
        except ValueError:
            return True

        return current_rounds != self.rounds


# ------------------------------------------------------------------ #
#  EncryptedField — two-way AES encryption (Fernet)                   #
# ------------------------------------------------------------------ #

class EncryptedField(Field):
    """
    Two-way AES encryption using Fernet (AES-128-CBC + HMAC-SHA256).
    Stores encrypted ciphertext — can be decrypted with the same key.

    Use for: API keys, tokens, SSNs, credit card numbers,
             sensitive config, personal data requiring retrieval.

    MySQL:      TEXT
    YugabyteDB: TEXT

    IMPORTANT: Store your encryption key securely!
    Never hardcode it — use environment variables.

    Usage:
        import os
        from mydborm.fields import EncryptedField

        # Generate a key (do this once, store securely)
        key = EncryptedField.generate_key()
        print(key)  # store in environment variable

        class APICredential(BaseModel):
            __tablename__ = "api_credentials"
            id          = IntField(primary_key=True)
            service     = StrField(max_length=50, nullable=False)
            api_key     = EncryptedField(
                              secret_key=os.environ["ENCRYPTION_KEY"],
                              nullable=False
                          )
            api_secret  = EncryptedField(
                              secret_key=os.environ["ENCRYPTION_KEY"],
                              nullable=True
                          )

        # Store — auto-encrypted
        cid = APICredential.create(
            service    = "stripe",
            api_key    = "sk_live_abc123xyz",
            api_secret = "whsec_secret456",
        )

        # Retrieve — still encrypted in DB
        cred = APICredential.get(id=cid)
        print(cred["api_key"])   # gAAAAAB... (ciphertext)

        # Decrypt
        plain = EncryptedField.decrypt(
            cred["api_key"],
            secret_key=os.environ["ENCRYPTION_KEY"]
        )
        print(plain)   # sk_live_abc123xyz
    """
    sql_type = "TEXT"

    def __init__(self, secret_key: str = None, **kwargs):
        """
        Args:
            secret_key: Fernet key (32 bytes, base64-encoded).
                        Generate with EncryptedField.generate_key()
                        Store in environment variable — never hardcode!
        """
        if secret_key is None:
            import os
            secret_key = os.environ.get("MYDBORM_ENCRYPTION_KEY")
        if secret_key is None:
            raise ValueError(
                "EncryptedField requires a secret_key. "
                "Pass it directly or set MYDBORM_ENCRYPTION_KEY env var. "
                "Generate a key with: EncryptedField.generate_key()"
            )
        self._secret_key = secret_key
        super().__init__(**kwargs)

    def _get_fernet(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError(
                "EncryptedField requires cryptography. "
                "Install it: pip install cryptography"
            )
        key = self._secret_key
        if isinstance(key, str):
            key = key.encode("utf-8")
        return Fernet(key)

    def validate(self, value):
        """Encrypt the value before storing."""
        value = super().validate(value)
        if value is None:
            return None

        # Already encrypted (starts with gAAAAA)
        if isinstance(value, str) and value.startswith("gAAAAA"):
            return value

        fernet = self._get_fernet()
        if isinstance(value, str):
            value = value.encode("utf-8")
        elif not isinstance(value, bytes):
            value = str(value).encode("utf-8")

        return fernet.encrypt(value).decode("utf-8")

    def decrypt_value(self, encrypted_value: str) -> str:
        """
        Decrypt a stored encrypted value.

        Usage:
            field = APICredential._fields["api_key"]
            plain = field.decrypt_value(cred["api_key"])
        """
        if encrypted_value is None:
            return None
        fernet = self._get_fernet()
        if isinstance(encrypted_value, str):
            encrypted_value = encrypted_value.encode("utf-8")
        return fernet.decrypt(encrypted_value).decode("utf-8")

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.
        Store this key securely — losing it means losing all encrypted data!

        Usage:
            key = EncryptedField.generate_key()
            print(key)   # store in .env or secrets manager
        """
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError("pip install cryptography")
        return Fernet.generate_key().decode("utf-8")

    @staticmethod
    def encrypt(plain_value: str, secret_key: str) -> str:
        """
        Encrypt a value with a given key.

        Usage:
            cipher = EncryptedField.encrypt("my-api-key", secret_key=key)
        """
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError("pip install cryptography")
        if isinstance(secret_key, str):
            secret_key = secret_key.encode("utf-8")
        if isinstance(plain_value, str):
            plain_value = plain_value.encode("utf-8")
        return Fernet(secret_key).encrypt(plain_value).decode("utf-8")

    @staticmethod
    def decrypt(encrypted_value: str, secret_key: str) -> str:
        """
        Decrypt a stored value with a given key.

        Usage:
            plain = EncryptedField.decrypt(cred["api_key"], secret_key=key)
        """
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError("pip install cryptography")
        if isinstance(secret_key, str):
            secret_key = secret_key.encode("utf-8")
        if isinstance(encrypted_value, str):
            encrypted_value = encrypted_value.encode("utf-8")
        return Fernet(secret_key).decrypt(encrypted_value).decode("utf-8")