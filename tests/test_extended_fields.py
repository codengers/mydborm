# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_extended_fields.py
# Project     : mydborm
# Author      : Atikrant Upadhye
# Created     : 2026-06-19
# Version     : 1.1.0
# License     : MIT
# Description : Tests for extended field types — TinyIntField, SmallIntField,
#               BigIntField, UnsignedBigIntField, DoubleField, BitField,
#               CharField, TinyTextField, MediumTextField, LongTextField,
#               BinaryField, VarBinaryField, BlobField, TimeField,
#               TimestampField, EnumField, SetField
# =============================================================================

import os
import pytest
from mydborm import (
    db, BaseModel,
    IntField, StrField,
    TinyIntField, SmallIntField, BigIntField, UnsignedBigIntField,
    DoubleField, BitField, CharField,
    TinyTextField, MediumTextField, LongTextField,
    BinaryField, VarBinaryField, BlobField,
    TimeField, TimestampField,
    EnumField, SetField,
)


# ------------------------------------------------------------------ #
#  Test model                                                          #
# ------------------------------------------------------------------ #

class ExtModel(BaseModel):
    __tablename__ = "ext_field_test"
    id           = IntField(primary_key=True)
    tiny         = TinyIntField(nullable=True)
    small        = SmallIntField(nullable=True)
    big          = BigIntField(nullable=True)
    unsigned_big = UnsignedBigIntField(nullable=True)
    dbl          = DoubleField(nullable=True)
    bits         = BitField(length=8, nullable=True)
    char_code    = CharField(length=3, nullable=True)
    tiny_txt     = TinyTextField(nullable=True)
    medium_txt   = MediumTextField(nullable=True)
    long_txt     = LongTextField(nullable=True)
    time_col     = TimeField(nullable=True)
    ts_col       = TimestampField(nullable=True)
    status       = EnumField(choices=["active","inactive","pending"],
                             nullable=True)
    tags         = SetField(choices=["python","java","go","rust"],
                            nullable=True)


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
    )
    ExtModel.create_table()
    yield
    ExtModel.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM ext_field_test")
    yield


# ------------------------------------------------------------------ #
#  SQL type generation — MySQL dialect                                 #
# ------------------------------------------------------------------ #

def test_tinyint_mysql_sql():
    f = TinyIntField()
    f.name = "t"
    assert "TINYINT" in f.to_sql_def("mysql")


def test_smallint_mysql_sql():
    f = SmallIntField()
    f.name = "s"
    assert "SMALLINT" in f.to_sql_def("mysql")


def test_bigint_mysql_sql():
    f = BigIntField()
    f.name = "b"
    assert "BIGINT" in f.to_sql_def("mysql")


def test_unsigned_bigint_mysql_sql():
    f = UnsignedBigIntField()
    f.name = "u"
    assert "BIGINT UNSIGNED" in f.to_sql_def("mysql")


def test_double_mysql_sql():
    f = DoubleField()
    f.name = "d"
    assert f.to_sql_def("mysql") == "DOUBLE"


def test_bit_mysql_sql():
    f = BitField(length=8)
    f.name = "b"
    assert "BIT(8)" in f.to_sql_def("mysql")


def test_char_mysql_sql():
    f = CharField(length=3)
    f.name = "c"
    assert "CHAR(3)" in f.to_sql_def("mysql")


def test_tinytext_mysql_sql():
    f = TinyTextField()
    f.name = "t"
    assert "TINYTEXT" in f.to_sql_def("mysql")


def test_mediumtext_mysql_sql():
    f = MediumTextField()
    f.name = "m"
    assert "MEDIUMTEXT" in f.to_sql_def("mysql")


def test_longtext_mysql_sql():
    f = LongTextField()
    f.name = "l"
    assert "LONGTEXT" in f.to_sql_def("mysql")


def test_enum_mysql_sql():
    f = EnumField(choices=["a", "b", "c"])
    f.name = "e"
    sql = f.to_sql_def("mysql")
    assert "ENUM" in sql
    assert "'a'" in sql
    assert "'b'" in sql


def test_set_mysql_sql():
    f = SetField(choices=["x", "y"])
    f.name = "s"
    sql = f.to_sql_def("mysql")
    assert "SET" in sql
    assert "'x'" in sql


def test_blob_mysql_sql():
    f = BlobField()
    f.name = "b"
    assert "BLOB" in f.to_sql_def("mysql")


def test_blob_longblob_mysql_sql():
    f = BlobField(blob_type="LONGBLOB")
    f.name = "b"
    assert "LONGBLOB" in f.to_sql_def("mysql")


def test_timestamp_mysql_sql():
    f = TimestampField()
    f.name = "ts"
    assert "TIMESTAMP" in f.to_sql_def("mysql")


# ------------------------------------------------------------------ #
#  SQL type generation — YugabyteDB dialect                            #
# ------------------------------------------------------------------ #

def test_tinyint_yugabyte_sql():
    f = TinyIntField()
    f.name = "t"
    assert f.to_sql_def("yugabyte") == "SMALLINT"


def test_unsigned_bigint_yugabyte_sql():
    f = UnsignedBigIntField()
    f.name = "u"
    assert "NUMERIC(20)" in f.to_sql_def("yugabyte")


def test_double_yugabyte_sql():
    f = DoubleField()
    f.name = "d"
    assert "DOUBLE PRECISION" in f.to_sql_def("yugabyte")


def test_tinytext_yugabyte_sql():
    f = TinyTextField()
    f.name = "t"
    assert f.to_sql_def("yugabyte") == "TEXT"


def test_mediumtext_yugabyte_sql():
    f = MediumTextField()
    f.name = "m"
    assert f.to_sql_def("yugabyte") == "TEXT"


def test_longtext_yugabyte_sql():
    f = LongTextField()
    f.name = "l"
    assert f.to_sql_def("yugabyte") == "TEXT"


def test_binary_yugabyte_sql():
    f = BinaryField(length=32)
    f.name = "b"
    assert f.to_sql_def("yugabyte") == "BYTEA"


def test_varbinary_yugabyte_sql():
    f = VarBinaryField(max_length=256)
    f.name = "v"
    assert f.to_sql_def("yugabyte") == "BYTEA"


def test_blob_yugabyte_sql():
    f = BlobField()
    f.name = "b"
    assert f.to_sql_def("yugabyte") == "BYTEA"


def test_timestamp_yugabyte_sql():
    f = TimestampField()
    f.name = "ts"
    assert "TIMESTAMPTZ" in f.to_sql_def("yugabyte")


def test_enum_yugabyte_sql():
    f = EnumField(choices=["active", "inactive"])
    f.name = "e"
    sql = f.to_sql_def("yugabyte")
    assert "VARCHAR" in sql
    assert "ENUM" not in sql


def test_set_yugabyte_sql():
    f = SetField(choices=["a", "b"])
    f.name = "s"
    assert f.to_sql_def("yugabyte") == "TEXT[]"


# ------------------------------------------------------------------ #
#  Validation                                                          #
# ------------------------------------------------------------------ #

def test_tinyint_valid_range():
    f = TinyIntField()
    f.name = "t"
    assert f.validate(-128) == -128
    assert f.validate(127)  == 127
    assert f.validate(0)    == 0


def test_tinyint_out_of_range():
    f = TinyIntField()
    f.name = "t"
    with pytest.raises(ValueError, match="range is -128 to 127"):
        f.validate(128)
    with pytest.raises(ValueError, match="range is -128 to 127"):
        f.validate(-129)


def test_smallint_valid_range():
    f = SmallIntField()
    f.name = "s"
    assert f.validate(-32768) == -32768
    assert f.validate(32767)  == 32767


def test_smallint_out_of_range():
    f = SmallIntField()
    f.name = "s"
    with pytest.raises(ValueError, match="SMALLINT range"):
        f.validate(32768)


def test_bigint_large_value():
    f = BigIntField()
    f.name = "b"
    assert f.validate(9223372036854775807) == 9223372036854775807


def test_unsigned_bigint_negative_raises():
    f = UnsignedBigIntField()
    f.name = "u"
    with pytest.raises(ValueError, match="must be >= 0"):
        f.validate(-1)


def test_double_precision():
    f = DoubleField()
    f.name = "d"
    assert f.validate(3.141592653589793) == 3.141592653589793


def test_char_valid():
    f = CharField(length=3)
    f.name = "code"
    assert f.validate("US") == "US"
    assert f.validate("GBR") == "GBR"


def test_char_too_long():
    f = CharField(length=3)
    f.name = "code"
    with pytest.raises(ValueError, match="too long"):
        f.validate("TOOLONG")


def test_enum_valid():
    f = EnumField(choices=["active", "inactive", "pending"])
    f.name = "status"
    assert f.validate("active")   == "active"
    assert f.validate("inactive") == "inactive"


def test_enum_invalid():
    f = EnumField(choices=["active", "inactive"])
    f.name = "status"
    with pytest.raises(ValueError, match="must be one of"):
        f.validate("deleted")


def test_enum_none_passes():
    f = EnumField(choices=["a", "b"], nullable=True)
    f.name = "e"
    assert f.validate(None) is None


def test_set_valid_list():
    f = SetField(choices=["python", "java", "go"])
    f.name = "tags"
    result = f.validate(["python", "go"])
    assert result == ["python", "go"]


def test_set_valid_string():
    f = SetField(choices=["python", "java", "go"])
    f.name = "tags"
    result = f.validate("python,java")
    assert result == "python,java"


def test_set_invalid_value():
    f = SetField(choices=["python", "java"])
    f.name = "tags"
    with pytest.raises(ValueError, match="invalid values"):
        f.validate(["ruby"])


def test_set_empty_choices_raises():
    with pytest.raises(ValueError, match="at least one choice"):
        SetField(choices=[])


def test_enum_empty_choices_raises():
    with pytest.raises(ValueError, match="at least one choice"):
        EnumField(choices=[])


def test_blob_invalid_type_raises():
    with pytest.raises(ValueError, match="blob_type must be"):
        BlobField(blob_type="INVALID")


# ------------------------------------------------------------------ #
#  DB round-trip                                                       #
# ------------------------------------------------------------------ #

def test_create_and_get_extended():
    rid = ExtModel.create(
        tiny       = 100,
        small      = 1000,
        big        = 9999999999,
        unsigned_big = 123456789,
        dbl        = 3.14159265,
        char_code  = "US",
        tiny_txt   = "hello",
        medium_txt = "medium content",
        long_txt   = "long content",
        status     = "active",
        tags       = "python,java",
    )
    assert rid > 0
    row = ExtModel.get(id=rid)
    assert row["tiny"]      == 100
    assert row["small"]     == 1000
    assert row["big"]       == 9999999999
    assert row["char_code"].strip() == "US"
    assert row["tiny_txt"]  == "hello"
    assert row["status"]    == "active"


def test_enum_db_roundtrip():
    rid = ExtModel.create(status="pending", tiny=1, small=1,
                          big=1, unsigned_big=1, dbl=1.0,
                          char_code="GB")
    row = ExtModel.get(id=rid)
    assert row["status"] == "pending"


def test_filter_by_enum():
    ExtModel.create(status="active",   tiny=1, small=1, big=1,
                    unsigned_big=1, dbl=1.0, char_code="US")
    ExtModel.create(status="inactive", tiny=2, small=2, big=2,
                    unsigned_big=2, dbl=2.0, char_code="GB")
    rows = ExtModel.filter(status="active")
    assert len(rows) == 1
    assert rows[0]["status"] == "active"


def test_bigint_large_value_db():
    rid = ExtModel.create(
        tiny=1, small=1, big=9223372036854775000,
        unsigned_big=1, dbl=1.0, char_code="US"
    )
    row = ExtModel.get(id=rid)
    assert row["big"] == 9223372036854775000


def test_double_precision_db():
    rid = ExtModel.create(
        tiny=1, small=1, big=1, unsigned_big=1,
        dbl=3.141592653589793, char_code="US"
    )
    row = ExtModel.get(id=rid)
    assert abs(row["dbl"] - 3.141592653589793) < 1e-10


def test_exported_from_package():
    import mydborm
    for name in [
        "TinyIntField", "SmallIntField", "BigIntField",
        "UnsignedBigIntField", "DoubleField", "BitField",
        "CharField", "TinyTextField", "MediumTextField",
        "LongTextField", "BinaryField", "VarBinaryField",
        "BlobField", "TimeField", "TimestampField",
        "EnumField", "SetField",
    ]:
        assert hasattr(mydborm, name), f"{name} not exported"

# ------------------------------------------------------------------ #
#  TimeField tests                                                     #
# ------------------------------------------------------------------ #

def test_time_mysql_sql():
    f = TimeField()
    f.name = "t"
    assert f.to_sql_def("mysql") == "TIME"


def test_time_yugabyte_sql():
    f = TimeField()
    f.name = "t"
    assert f.to_sql_def("yugabyte") == "TIME"


def test_time_valid():
    import datetime
    f = TimeField()
    f.name = "opens_at"
    t = datetime.time(9, 30, 0)
    assert f.validate(t) == t


def test_time_string_valid():
    f = TimeField()
    f.name = "opens_at"
    assert f.validate("09:30:00") == "09:30:00"


def test_time_none_passes():
    f = TimeField(nullable=True)
    f.name = "opens_at"
    assert f.validate(None) is None


def test_time_db_roundtrip():
    import datetime
    rid = ExtModel.create(
        tiny=1, small=1, big=1, unsigned_big=1,
        dbl=1.0, char_code="US",
        time_col=datetime.time(9, 30, 0),
        status="active"
    )
    row = ExtModel.get(id=rid)
    assert row["time_col"] is not None


# ------------------------------------------------------------------ #
#  TimestampField tests                                                #
# ------------------------------------------------------------------ #

def test_timestamp_mysql_sql():
    f = TimestampField()
    f.name = "ts"
    assert "TIMESTAMP" in f.to_sql_def("mysql")
    assert "TIMESTAMPTZ" not in f.to_sql_def("mysql")


def test_timestamp_yugabyte_sql():
    f = TimestampField()
    f.name = "ts"
    assert "TIMESTAMPTZ" in f.to_sql_def("yugabyte")


def test_timestamp_valid():
    import datetime
    f = TimestampField()
    f.name = "created_at"
    dt = datetime.datetime.now()
    assert f.validate(dt) == dt


def test_timestamp_string_valid():
    f = TimestampField()
    f.name = "created_at"
    assert f.validate("2024-06-19 10:30:00") == "2024-06-19 10:30:00"


def test_timestamp_none_passes():
    f = TimestampField(nullable=True)
    f.name = "created_at"
    assert f.validate(None) is None


def test_timestamp_db_roundtrip():
    import datetime
    now = datetime.datetime.now().replace(microsecond=0)
    rid = ExtModel.create(
        tiny=1, small=1, big=1, unsigned_big=1,
        dbl=1.0, char_code="US",
        ts_col=now,
        status="active"
    )
    row = ExtModel.get(id=rid)
    assert row["ts_col"] is not None


def test_timestamp_differs_from_datetimefield():
    from mydborm import DateTimeField
    ts = TimestampField()
    dt = DateTimeField()
    ts.name = "ts"
    dt.name = "dt"
    # MySQL: both TIMESTAMP vs DATETIME
    assert ts.to_sql_def("mysql") != dt.to_sql_def("mysql")
    # YugabyteDB: TIMESTAMPTZ vs TIMESTAMP
    assert ts.to_sql_def("yugabyte") != dt.to_sql_def("yugabyte")
    assert "TIMESTAMPTZ" in ts.to_sql_def("yugabyte")
    assert "TIMESTAMPTZ" not in dt.to_sql_def("yugabyte")