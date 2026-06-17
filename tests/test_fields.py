# =============================================================================
# File        : tests/test_fields.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : pytest tests for all field types � validates type checking,
#               max length enforcement, nullable constraints, SQL definition
#               generation, and ForeignKeyField output.
# =============================================================================
"""
test_fields.py — Field validation tests.
"""
import pytest
from mydborm.fields import (
    IntField, StrField, BoolField,
    FloatField, DateField, ForeignKeyField
)


def test_intfield_valid():
    f = IntField()
    f.name = "age"
    assert f.validate(25) == 25


def test_intfield_invalid():
    f = IntField()
    f.name = "age"
    with pytest.raises(TypeError, match="expects int"):
        f.validate("twenty")


def test_strfield_max_length():
    f = StrField(max_length=5)
    f.name = "code"
    with pytest.raises(ValueError, match="max length"):
        f.validate("toolongstring")


def test_strfield_valid():
    f = StrField(max_length=100)
    f.name = "username"
    assert f.validate("alice") == "alice"


def test_strfield_sql_def():
    f = StrField(max_length=100, nullable=False, unique=True)
    f.name = "email"
    sql = f.to_sql_def()
    assert "VARCHAR(100)" in sql
    assert "NOT NULL" in sql
    assert "UNIQUE" in sql


def test_boolfield_invalid():
    f = BoolField()
    f.name = "active"
    with pytest.raises(TypeError, match="expects bool"):
        f.validate("yes")


def test_floatfield_coerces_int():
    f = FloatField()
    f.name = "price"
    assert f.validate(10) == 10.0


def test_nullable_false_raises_on_none():
    f = StrField(nullable=False)
    f.name = "username"
    with pytest.raises(ValueError, match="cannot be None"):
        f.validate(None)


def test_foreignkey_sql_def():
    f = ForeignKeyField(to="User")
    f.name = "user_id"
    assert "FK -> User" in f.to_sql_def()

