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

from datetime import date, datetime
from typing import Any, Optional


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
                raise ValueError(
                    f"Field '{self.name}' cannot be None."
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
            raise TypeError(
                f"Field '{self.name}' expects int, got {type(value).__name__}."
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
                raise TypeError(
                    f"Field '{self.name}' expects str, "
                    f"got {type(value).__name__}."
                )
            if len(value) > self.max_length:
                raise ValueError(
                    f"Field '{self.name}' max length is "
                    f"{self.max_length}, got {len(value)}."
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
            raise TypeError(
                f"Field '{self.name}' expects bool, "
                f"got {type(value).__name__}."
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
            raise TypeError(
                f"Field '{self.name}' expects float, "
                f"got {type(value).__name__}."
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
            raise TypeError(
                f"Field '{self.name}' expects date or str, "
                f"got {type(value).__name__}."
            )
        return value

class DateTimeField(Field):
    """Date + time — DATETIME column."""
    sql_type = "DATETIME"

    def validate(self, value: Any) -> Any:
        value = super().validate(value)
        if value is not None and not isinstance(value, (datetime, str)):
            raise TypeError(
                f"Field '{self.name}' expects datetime or str, "
                f"got {type(value).__name__}."
            )
        return value

class JSONField(Field):
    """
    JSON column.
    MySQL  → JSON
    YugabyteDB → JSONB
    """
    sql_type = "JSON"

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

    Usage:
        author = ForeignKeyField(to="Author", nullable=False)
    """
    sql_type = "INT"

    def __init__(self, to: str, **kwargs):
        super().__init__(**kwargs)
        self.to = to   # referenced model name as string

    def to_sql_def(self) -> str:
        base = super().to_sql_def()
        return f"{base}  -- FK -> {self.to}"

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
                raise TypeError(
                    f"Field '{self.name}' expects int, "
                    f"got {type(value).__name__}."
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
                raise TypeError(
                    f"Field '{self.name}' expects int, "
                    f"got {type(value).__name__}."
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
                raise TypeError(
                    f"Field '{self.name}' expects int, "
                    f"got {type(value).__name__}."
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
                raise TypeError(
                    f"Field '{self.name}' expects int, "
                    f"got {type(value).__name__}."
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
                raise TypeError(
                    f"Field '{self.name}' expects float, "
                    f"got {type(value).__name__}."
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
                raise ValueError(
                    f"Field '{self.name}' CHAR({self.length}) — "
                    f"value too long: {len(value)} chars. Got: {value!r}"
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
                raise TypeError(
                    f"Field '{self.name}' expects datetime.time or str, "
                    f"got {type(value).__name__}."
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
                raise TypeError(
                    f"Field '{self.name}' expects datetime.datetime or str, "
                    f"got {type(value).__name__}."
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
                raise TypeError(
                    f"Field '{self.name}' expects str or list, "
                    f"got {type(value).__name__}."
                )
            invalid = [i for i in items if i not in self.choices]
            if invalid:
                raise ValueError(
                    f"Field '{self.name}' invalid values: {invalid}. "
                    f"Allowed: {self.choices}"
                )
        return value