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