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

# ------------------------------------------------------------------ #
#  Additional field coverage                                           #
# ------------------------------------------------------------------ #

def test_str_field_type_error():
    from mydborm import StrField
    f = StrField(max_length=50)
    f.name = "name"
    with pytest.raises(TypeError, match="expects str"):
        f.validate(12345)


def test_date_field_type_error():
    from mydborm import DateField
    f = DateField()
    f.name = "dob"
    with pytest.raises(TypeError, match="expects date"):
        f.validate(12345)


def test_datetime_field_type_error():
    from mydborm import DateTimeField
    f = DateTimeField()
    f.name = "created_at"
    with pytest.raises(TypeError):
        f.validate(99999)


def test_json_field_yugabyte_sql():
    from mydborm import JSONField
    f = JSONField()
    f.name = "data"
    assert "JSONB" in f.to_sql_def("yugabyte")


def test_json_field_postgres_sql():
    from mydborm import JSONField
    f = JSONField()
    f.name = "data"
    assert "JSONB" in f.to_sql_def("postgres")


def test_json_field_validate_serializes_dict():
    from mydborm import JSONField
    f = JSONField()
    f.name = "data"
    assert f.validate({"a": 1, "b": [2, 3]}) == '{"a": 1, "b": [2, 3]}'


def test_json_field_validate_serializes_list():
    from mydborm import JSONField
    f = JSONField()
    f.name = "data"
    assert f.validate([1, 2, 3]) == "[1, 2, 3]"


def test_json_field_validate_passes_through_string():
    from mydborm import JSONField
    f = JSONField()
    f.name = "data"
    # Already-serialized JSON text is left as-is, not double-encoded.
    assert f.validate('{"already": "json"}') == '{"already": "json"}'


def test_json_field_validate_passes_through_none():
    from mydborm import JSONField
    f = JSONField(nullable=True)
    f.name = "data"
    assert f.validate(None) is None


def test_field_primary_key_sql():
    from mydborm import IntField
    f = IntField(primary_key=True)
    f.name = "id"
    sql = f.to_sql_def("mysql")
    assert "PRIMARY KEY" in sql


def test_field_not_null_sql():
    from mydborm import StrField
    f = StrField(max_length=50, nullable=False)
    f.name = "name"
    sql = f.to_sql_def("mysql")
    assert "NOT NULL" in sql


def test_set_field_type_error():
    from mydborm.fields import SetField
    f = SetField(choices=["a", "b"])
    f.name = "tags"
    with pytest.raises(TypeError, match="expects str or list"):
        f.validate(12345)

def test_float_field_type_error():
    from mydborm import FloatField
    f = FloatField()
    f.name = "price"
    with pytest.raises(TypeError, match="expects float"):
        f.validate("not_a_float")


def test_decimal_field_sql():
    from mydborm import DecimalField
    f = DecimalField(precision=10, scale=2)
    f.name = "amount"
    sql = f.to_sql_def("mysql")
    assert "DECIMAL(10,2)" in sql


def test_field_not_null_in_sql():
    from mydborm import StrField
    f = StrField(max_length=50, nullable=False)
    f.name = "name"
    sql = f.to_sql_def("mysql")
    assert "NOT NULL" in sql


def test_field_nullable_no_not_null():
    from mydborm import StrField
    f = StrField(max_length=50, nullable=True)
    f.name = "name"
    sql = f.to_sql_def("mysql")
    assert "NOT NULL" not in sql


# ------------------------------------------------------------------ #
#  BoolField sql coverage (lines 171, 174)                            #
# ------------------------------------------------------------------ #

def test_boolfield_primary_key_sql():
    from mydborm.fields import BoolField
    f = BoolField(primary_key=True)
    f.name = "is_pk"
    sql = f.to_sql_def("mysql")
    assert "PRIMARY KEY" in sql  # line 171


def test_boolfield_not_null_sql():
    from mydborm.fields import BoolField
    f = BoolField(nullable=False)
    f.name = "active"
    sql = f.to_sql_def("mysql")
    assert "NOT NULL" in sql  # line 174


# ------------------------------------------------------------------ #
#  DateField valid return (line 215)                                  #
# ------------------------------------------------------------------ #

def test_datefield_valid_date_returns():
    import datetime
    from mydborm import DateField
    f = DateField()
    f.name = "dob"
    result = f.validate(datetime.date(2024, 6, 1))
    assert result == datetime.date(2024, 6, 1)  # line 215


def test_datefield_valid_string_returns():
    from mydborm import DateField
    f = DateField()
    f.name = "dob"
    result = f.validate("2024-06-01")
    assert result == "2024-06-01"  # line 215


# ------------------------------------------------------------------ #
#  BinaryField / VarBinaryField yugabyte path (lines 728, 755)       #
# ------------------------------------------------------------------ #

def test_binary_field_yugabyte_sql():
    from mydborm.fields import BinaryField
    f = BinaryField(length=16)
    f.name = "hash_val"
    sql = f.to_sql_def("yugabyte")
    assert "BYTEA" in sql  # line 728


def test_varbinary_field_yugabyte_sql():
    from mydborm.fields import VarBinaryField
    f = VarBinaryField(max_length=256)
    f.name = "signature"
    sql = f.to_sql_def("yugabyte")
    assert "BYTEA" in sql  # line 755


# ------------------------------------------------------------------ #
#  PasswordField edge cases (lines 1018, 1030-1031)                  #
# ------------------------------------------------------------------ #

def test_password_field_bytes_already_hashed():
    from mydborm.fields import PasswordField
    f = PasswordField()
    f.name = "password"
    # Bytes that start with b"$2b$" are treated as already hashed
    pre_hashed = b"$2b$12$" + b"a" * 53
    result = f.validate(pre_hashed)  # line 1018
    assert isinstance(result, str)
    assert result.startswith("$2b$")


def test_password_field_invalid_type_raises():
    from mydborm.fields import PasswordField
    f = PasswordField()
    f.name = "password"
    with pytest.raises(TypeError, match="expects str or bytes"):
        f.validate(99999)  # lines 1030-1031


# ------------------------------------------------------------------ #
#  EncryptedField edge cases (lines 1222-1223, 1236)                 #
# ------------------------------------------------------------------ #

def test_encrypted_field_non_str_value():
    from mydborm.fields import EncryptedField
    key = EncryptedField.generate_key()
    f = EncryptedField(secret_key=key)
    f.name = "data"
    result = f.validate(42)  # int → str-encoded → encrypted (lines 1222-1223)
    assert result.startswith("gAAAAA")


def test_encrypted_field_decrypt_value_none():
    from mydborm.fields import EncryptedField
    key = EncryptedField.generate_key()
    f = EncryptedField(secret_key=key)
    f.name = "data"
    result = f.decrypt_value(None)  # line 1236
    assert result is None


# ------------------------------------------------------------------ #
#  Field._format_default and __repr__ (lines 94, 96, 100-104)        #
# ------------------------------------------------------------------ #

def test_field_str_default_formatting():
    from mydborm import StrField
    f = StrField(max_length=50, default="hello")
    f.name = "label"
    sql = f.to_sql_def("mysql")
    assert "'hello'" in sql  # line 94


def test_field_bool_default_formatting():
    from mydborm import BoolField
    f = BoolField(default=True)
    f.name = "active"
    sql = f.to_sql_def("mysql")
    assert "DEFAULT 1" in sql  # line 96


def test_field_repr():
    from mydborm import IntField
    f = IntField()
    f.name = "count"
    r = repr(f)  # lines 100-104
    assert "IntField" in r
    assert "count" in r


# ------------------------------------------------------------------ #
#  Extended integer field type errors (lines 426-427, 456-457,        #
#  487-488, 520-521, 563-564, 816, 852)                               #
# ------------------------------------------------------------------ #

def test_tinyint_field_invalid_type():
    from mydborm.fields import TinyIntField
    f = TinyIntField()
    f.name = "tiny"
    with pytest.raises(TypeError):
        f.validate("bad")  # lines 426-427


def test_smallint_field_invalid_type():
    from mydborm.fields import SmallIntField
    f = SmallIntField()
    f.name = "small"
    with pytest.raises(TypeError):
        f.validate("bad")  # lines 456-457


def test_bigint_field_invalid_type():
    from mydborm.fields import BigIntField
    f = BigIntField()
    f.name = "big"
    with pytest.raises(TypeError):
        f.validate("bad")  # lines 487-488


def test_unsigned_bigint_field_invalid_type():
    from mydborm.fields import UnsignedBigIntField
    f = UnsignedBigIntField()
    f.name = "ubig"
    with pytest.raises(TypeError):
        f.validate("bad")  # lines 520-521


def test_double_field_invalid_type():
    from mydborm.fields import DoubleField
    f = DoubleField()
    f.name = "dbl"
    with pytest.raises(TypeError):
        f.validate("bad")  # lines 563-564


def test_time_field_invalid_type():
    from mydborm.fields import TimeField
    f = TimeField()
    f.name = "start_time"
    with pytest.raises(TypeError):
        f.validate(12345)  # line 816


def test_timestamp_field_invalid_type():
    from mydborm.fields import TimestampField
    f = TimestampField()
    f.name = "created_at"
    with pytest.raises(TypeError):
        f.validate(12345)  # line 852


# ------------------------------------------------------------------ #
#  PasswordField.verify exception catch (line 1073-1074)              #
#  PasswordField.needs_rehash (lines 1107-1114)                       #
# ------------------------------------------------------------------ #

def test_password_field_verify_invalid_hash_returns_false():
    from mydborm.fields import PasswordField
    f = PasswordField()
    f.name = "password"
    result = f.verify("plain", b"not_a_valid_hash")  # lines 1073-1074
    assert result is False


def test_password_field_needs_rehash():
    from mydborm.fields import PasswordField
    f = PasswordField()
    f.name = "password"
    hashed = PasswordField.hash("secret")
    result = f.needs_rehash(hashed)  # lines 1107-1114
    assert isinstance(result, bool)


# ------------------------------------------------------------------ #
#  EncryptedField.encrypt / decrypt static methods (1268-1269,        #
#  1286-1287)                                                         #
# ------------------------------------------------------------------ #

def test_encrypted_field_encrypt_static():
    from mydborm.fields import EncryptedField
    key = EncryptedField.generate_key()
    cipher = EncryptedField.encrypt("secret", key)  # lines 1268-1274
    assert cipher.startswith("gAAAAA")


def test_encrypted_field_decrypt_static():
    from mydborm.fields import EncryptedField
    key = EncryptedField.generate_key()
    cipher = EncryptedField.encrypt("secret", key)
    plain = EncryptedField.decrypt(cipher, key)  # lines 1284-1289
    assert plain == "secret"
