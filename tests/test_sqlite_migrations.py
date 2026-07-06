# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_sqlite_migrations.py
# Project     : mydborm
# License     : MIT
# Description : Tests for the SQLite auto-migration engine — get_live_schema,
#               table_exists, diff_schema, generate_migration_sql, migrate,
#               migration_status, rollback, generate(), apply_migration_file().
#               SQLite is stdlib (no external service), so these tests are
#               never skipped.
# =============================================================================

import os
import shutil
import tempfile

import pytest

from mydborm import BaseModel, BoolField, FloatField, IntField, StrField, db
from mydborm import migrations as mg
from mydborm.migrations import apply_migration_file, generate, list_migration_files

OUTPUT_DIR = "test_sqlite_mig_output"


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class SMUser(BaseModel):
    __tablename__ = "sm_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False)
    active   = BoolField(default=True)


class SMProduct(BaseModel):
    __tablename__ = "sm_products"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)
    price = FloatField(nullable=False)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    db.configure(dialect="sqlite", database=path)
    yield path
    db.close()
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(autouse=True)
def clean_tables():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS sm_users")
        cur.execute("DROP TABLE IF EXISTS sm_products")
        cur.execute("DROP TABLE IF EXISTS sm_temp")
        cur.execute("DROP TABLE IF EXISTS _mydborm_migrations")
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    yield
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)


# ------------------------------------------------------------------ #
#  get_live_schema / table_exists                                      #
# ------------------------------------------------------------------ #

def test_table_exists_false_for_missing_table():
    assert mg.table_exists("sm_users") is False


def test_get_live_schema_empty_for_missing_table():
    assert mg.get_live_schema("sm_users") == {}


def test_get_live_schema_reflects_columns():
    SMUser.create_table()
    schema = mg.get_live_schema("sm_users")
    assert "id" in schema
    assert "username" in schema
    assert "email" in schema
    assert schema["id"]["key"] == "PRI"
    assert schema["username"]["nullable"] == "NO"


def test_table_exists_true_after_create():
    SMUser.create_table()
    assert mg.table_exists("sm_users") is True


# ------------------------------------------------------------------ #
#  diff_schema / generate_migration_sql                                #
# ------------------------------------------------------------------ #

def test_diff_schema_new_table():
    diff = mg.diff_schema(SMUser)
    assert diff["new_table"] is True
    assert "id" in diff["add_columns"]


def test_diff_schema_add_and_drop_columns():
    SMUser.create_table()
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("ALTER TABLE sm_users ADD COLUMN legacy_col TEXT")

    diff = mg.diff_schema(SMUser)
    assert diff["new_table"] is False
    assert "legacy_col" in diff["drop_columns"]


def test_generate_migration_sql_new_table_no_engine_clause():
    sqls = mg.generate_migration_sql(SMUser)
    assert len(sqls) == 1
    assert "CREATE TABLE" in sqls[0]
    assert "ENGINE" not in sqls[0]
    assert "AUTO_INCREMENT" not in sqls[0]


def test_generate_migration_sql_add_column():
    SMProduct.create_table()
    with db.connect() as conn:
        conn.cursor().execute("ALTER TABLE sm_products DROP COLUMN price")

    sqls = mg.generate_migration_sql(SMProduct)
    assert any("ADD COLUMN" in s and "price" in s for s in sqls)


# ------------------------------------------------------------------ #
#  migrate() / migration_status()                                      #
# ------------------------------------------------------------------ #

def test_migrate_creates_table():
    result = mg.migrate(SMUser, description="create sm_users")
    assert result["applied"] is True
    assert mg.table_exists("sm_users") is True


def test_migrate_twice_is_noop():
    mg.migrate(SMUser)
    result = mg.migrate(SMUser)
    assert result["applied"] is False
    # Second call has no diff (table already matches), so migrate() short-
    # circuits with "up to date" rather than reaching the "already applied"
    # version-check branch.
    assert "up to date" in result["message"].lower()


def test_migration_status_lists_applied():
    mg.migrate(SMUser, description="create sm_users")
    status = mg.migration_status()
    assert len(status) >= 1
    assert any("sm_users" in s["description"] for s in status)


# ------------------------------------------------------------------ #
#  rollback()                                                          #
# ------------------------------------------------------------------ #

def test_rollback_drops_table():
    mg.migrate(SMUser)
    assert mg.table_exists("sm_users") is True

    result = mg.rollback(SMUser)
    assert result["applied"] is True
    assert mg.table_exists("sm_users") is False


def test_rollback_missing_table_reports_not_applied():
    result = mg.rollback(SMUser)
    assert result["applied"] is False


# ------------------------------------------------------------------ #
#  generate() / apply_migration_file()                                 #
# ------------------------------------------------------------------ #

def test_generate_creates_and_applies_file():
    result = generate(SMUser, output_dir=OUTPUT_DIR, apply=True)
    assert result["file"] is not None
    assert result["applied"] is True
    assert db.table_exists("sm_users") is True


def test_generate_uptodate_after_apply():
    generate(SMUser, output_dir=OUTPUT_DIR, apply=True)
    result = generate(SMUser, output_dir=OUTPUT_DIR)
    assert result["file"] is None
    assert "up to date" in result["message"].lower()


def test_apply_migration_file_directly():
    result = generate(SMProduct, output_dir=OUTPUT_DIR)
    apply_result = apply_migration_file(result["file"])
    assert apply_result["applied"] is True
    assert db.table_exists("sm_products") is True


def test_list_migration_files_after_generate():
    generate(SMUser,    output_dir=OUTPUT_DIR)
    generate(SMProduct, output_dir=OUTPUT_DIR)
    files = list_migration_files(OUTPUT_DIR)
    assert len(files) == 2
    assert files[0]["version"] == "0001"
    assert files[1]["version"] == "0002"
