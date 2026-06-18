# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_migrations.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.7.0
# License     : MIT
# Description : pytest tests for migrations engine — get_live_schema,
#               table_exists, diff_schema, generate_migration_sql,
#               migrate, migration_status, rollback.
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm import migrations as mg


# ------------------------------------------------------------------ #
#  Test models                                                         #
# ------------------------------------------------------------------ #

class MigUser(BaseModel):
    __tablename__ = "mig_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False)
    active   = BoolField(default=True)


class MigProduct(BaseModel):
    __tablename__ = "mig_products"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)
    price = FloatField(nullable=False)


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
    yield
    # Clean up migration test tables
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS mig_users")
        cur.execute("DROP TABLE IF EXISTS mig_products")
        cur.execute("DROP TABLE IF EXISTS mig_temp")
    db.close()


@pytest.fixture(autouse=True)
def clean_tables():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS mig_users")
        cur.execute("DROP TABLE IF EXISTS mig_products")
        cur.execute("DROP TABLE IF EXISTS mig_temp")
        cur.execute(
            "DELETE FROM `_mydborm_migrations` "
            "WHERE description LIKE '%mig_%'"
        )
    yield


# ------------------------------------------------------------------ #
#  table_exists                                                        #
# ------------------------------------------------------------------ #

def test_table_exists_false_before_create():
    assert mg.table_exists("mig_users") is False


def test_table_exists_true_after_create():
    MigUser.create_table()
    assert mg.table_exists("mig_users") is True


def test_table_exists_nonexistent():
    assert mg.table_exists("nonexistent_xyz_table") is False


# ------------------------------------------------------------------ #
#  get_live_schema                                                     #
# ------------------------------------------------------------------ #

def test_get_live_schema_empty_for_missing_table():
    schema = mg.get_live_schema("nonexistent_xyz")
    assert schema == {}


def test_get_live_schema_returns_columns():
    MigUser.create_table()
    schema = mg.get_live_schema("mig_users")
    assert "id"       in schema
    assert "username" in schema
    assert "email"    in schema
    assert "active"   in schema


def test_get_live_schema_column_details():
    MigUser.create_table()
    schema = mg.get_live_schema("mig_users")
    assert "type"     in schema["id"]
    assert "nullable" in schema["id"]


def test_get_live_schema_pk_marked():
    MigUser.create_table()
    schema = mg.get_live_schema("mig_users")
    assert schema["id"]["key"] == "PRI"


# ------------------------------------------------------------------ #
#  diff_schema                                                         #
# ------------------------------------------------------------------ #

def test_diff_schema_new_table():
    diff = mg.diff_schema(MigUser)
    assert diff["new_table"]         is True
    assert diff["table"]             == "mig_users"
    assert len(diff["add_columns"])  > 0


def test_diff_schema_existing_table_no_changes():
    MigUser.create_table()
    diff = mg.diff_schema(MigUser)
    assert diff["new_table"]         is False
    assert diff["add_columns"]       == {}
    assert diff["drop_columns"]      == []


def test_diff_schema_detects_new_column():
    MigUser.create_table()

    class MigUserExtended(BaseModel):
        __tablename__ = "mig_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=100, nullable=False)
        email    = StrField(max_length=255, nullable=False)
        active   = BoolField(default=True)
        phone    = StrField(max_length=20,  nullable=True)

    diff = mg.diff_schema(MigUserExtended)
    assert diff["new_table"]        is False
    assert "phone" in diff["add_columns"]


def test_diff_schema_detects_dropped_column():
    MigUser.create_table()

    class MigUserReduced(BaseModel):
        __tablename__ = "mig_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=100, nullable=False)

    diff = mg.diff_schema(MigUserReduced)
    assert "email"  in diff["drop_columns"]
    assert "active" in diff["drop_columns"]


# ------------------------------------------------------------------ #
#  generate_migration_sql                                              #
# ------------------------------------------------------------------ #

def test_generate_migration_sql_create_table():
    sqls = mg.generate_migration_sql(MigUser)
    assert len(sqls) == 1
    assert "CREATE TABLE" in sqls[0]
    assert "mig_users"    in sqls[0]


def test_generate_migration_sql_add_column():
    MigUser.create_table()

    class MigUserPhone(BaseModel):
        __tablename__ = "mig_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=100, nullable=False)
        email    = StrField(max_length=255, nullable=False)
        active   = BoolField(default=True)
        phone    = StrField(max_length=20,  nullable=True)

    sqls = mg.generate_migration_sql(MigUserPhone)
    assert any("ADD COLUMN" in s and "phone" in s for s in sqls)


def test_generate_migration_sql_drop_column():
    MigUser.create_table()

    class MigUserMin(BaseModel):
        __tablename__ = "mig_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=100, nullable=False)

    sqls = mg.generate_migration_sql(MigUserMin)
    assert any("DROP COLUMN" in s for s in sqls)


def test_generate_migration_sql_empty_when_uptodate():
    MigUser.create_table()
    sqls = mg.generate_migration_sql(MigUser)
    assert sqls == []


# ------------------------------------------------------------------ #
#  migrate                                                             #
# ------------------------------------------------------------------ #

def test_migrate_creates_table():
    result = mg.migrate(MigUser, description="create mig_users")
    assert result["applied"]         is True
    assert result["table"]           == "mig_users"
    assert mg.table_exists("mig_users") is True


def test_migrate_returns_result_dict():
    result = mg.migrate(MigUser)
    assert "table"   in result
    assert "sqls"    in result
    assert "applied" in result
    assert "message" in result


def test_migrate_not_applied_when_uptodate():
    mg.migrate(MigUser)
    result = mg.migrate(MigUser)
    assert result["applied"] is False
    assert "up to date" in result["message"].lower() \
        or "already applied" in result["message"].lower()


def test_migrate_multiple_models():
    r1 = mg.migrate(MigUser,    description="create mig_users")
    r2 = mg.migrate(MigProduct, description="create mig_products")
    assert r1["applied"] is True
    assert r2["applied"] is True
    assert mg.table_exists("mig_users")    is True
    assert mg.table_exists("mig_products") is True


def test_migrate_records_in_tracking_table():
    mg.migrate(MigUser, description="mig_users tracking test")
    status = mg.migration_status()
    descriptions = [s["description"] for s in status]
    assert any("mig_users" in d for d in descriptions)


# ------------------------------------------------------------------ #
#  migration_status                                                    #
# ------------------------------------------------------------------ #

def test_migration_status_returns_list():
    status = mg.migration_status()
    assert isinstance(status, list)


def test_migration_status_after_migrate():
    mg.migrate(MigUser,    description="mig_users status test")
    mg.migrate(MigProduct, description="mig_products status test")
    status = mg.migration_status()
    assert len(status) >= 2


def test_migration_status_fields():
    mg.migrate(MigUser, description="mig_users fields test")
    status = mg.migration_status()
    latest = [s for s in status if "mig_users" in s["description"]]
    assert len(latest) > 0
    record = latest[0]
    assert "id"          in record
    assert "version"     in record
    assert "description" in record
    assert "applied_at"  in record
    assert "rolled_back" in record


def test_migration_status_applied_flag():
    mg.migrate(MigUser, description="mig_users applied flag")
    status = mg.migration_status()
    latest = [s for s in status if "mig_users" in s["description"]]
    assert latest[0]["rolled_back"] == 0


# ------------------------------------------------------------------ #
#  rollback                                                            #
# ------------------------------------------------------------------ #

def test_rollback_drops_table():
    mg.migrate(MigUser, description="mig_users rollback test")
    assert mg.table_exists("mig_users") is True
    result = mg.rollback(MigUser)
    assert result["applied"]            is True
    assert mg.table_exists("mig_users") is False


def test_rollback_returns_result():
    mg.migrate(MigUser)
    result = mg.rollback(MigUser)
    assert "table"   in result
    assert "applied" in result
    assert "message" in result


def test_rollback_nonexistent_table():
    result = mg.rollback(MigUser)
    assert result["applied"] is False
    assert "does not exist"  in result["message"].lower()


def test_rollback_marks_as_rolled_back():
    mg.migrate(MigUser, description="mig_users rb mark test")
    mg.rollback(MigUser)
    status  = mg.migration_status()
    records = [s for s in status
               if "mig_users rb mark" in s["description"]]
    if records:
        assert records[0]["rolled_back"] == 1


# ------------------------------------------------------------------ #
#  checksum                                                            #
# ------------------------------------------------------------------ #

def test_checksum_is_consistent():
    from mydborm.migrations import _checksum
    assert _checksum("SELECT 1") == _checksum("SELECT 1")


def test_checksum_differs_for_different_sql():
    from mydborm.migrations import _checksum
    assert _checksum("SELECT 1") != _checksum("SELECT 2")


def test_checksum_length():
    from mydborm.migrations import _checksum
    assert len(_checksum("test")) == 16