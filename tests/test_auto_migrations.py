# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_auto_migrations.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-19
# Version     : 0.8.0
# License     : MIT
# Description : pytest tests for auto-migration generation — generate(),
#               apply_migration_file(), list_migration_files().
# =============================================================================

import os
import shutil
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm.migrations import (
    generate,
    apply_migration_file,
    list_migration_files,
)

OUTPUT_DIR = "test_mig_output"


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class AutoUser(BaseModel):
    __tablename__ = "auto_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False)
    active   = BoolField(default=True)


class AutoProduct(BaseModel):
    __tablename__ = "auto_products"
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
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS auto_users")
        cur.execute("DROP TABLE IF EXISTS auto_products")
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS auto_users")
        cur.execute("DROP TABLE IF EXISTS auto_products")
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    yield
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)


# ------------------------------------------------------------------ #
#  generate()                                                          #
# ------------------------------------------------------------------ #

def test_generate_creates_file():
    result = generate(AutoUser, output_dir=OUTPUT_DIR)
    assert result["file"] is not None
    assert os.path.exists(result["file"])


def test_generate_returns_correct_version():
    result = generate(AutoUser, output_dir=OUTPUT_DIR)
    assert result["version"] == "0001"


def test_generate_increments_version():
    generate(AutoUser,    output_dir=OUTPUT_DIR)
    generate(AutoProduct, output_dir=OUTPUT_DIR)
    files = list_migration_files(OUTPUT_DIR)
    assert files[0]["version"] == "0001"
    assert files[1]["version"] == "0002"


def test_generate_sql_contains_create_table():
    result = generate(AutoUser, output_dir=OUTPUT_DIR)
    assert len(result["sqls"]) == 1
    assert "CREATE TABLE" in result["sqls"][0]


def test_generate_sql_contains_table_name():
    result = generate(AutoUser, output_dir=OUTPUT_DIR)
    assert "auto_users" in result["sqls"][0]


def test_generate_file_has_header_comments():
    result = generate(AutoUser, output_dir=OUTPUT_DIR,
                      description="create auto_users")
    with open(result["file"]) as f:
        content = f.read()
    assert "-- mydborm auto-generated migration" in content
    assert "-- version" in content
    assert "-- table"   in content
    assert "-- generated" in content


def test_generate_file_has_sql():
    result = generate(AutoUser, output_dir=OUTPUT_DIR)
    with open(result["file"]) as f:
        content = f.read()
    assert "CREATE TABLE" in content


def test_generate_uptodate_returns_none_file():
    r1 = generate(AutoUser, output_dir=OUTPUT_DIR, apply=True)
    assert r1["applied"] is True
    assert db.table_exists("auto_users") is True
    result = generate(AutoUser, output_dir=OUTPUT_DIR)
    assert result["file"]    is None
    assert result["applied"] is False
    assert "up to date"      in result["message"].lower()


def test_generate_creates_output_dir():
    new_dir = OUTPUT_DIR + "_new"
    try:
        generate(AutoUser, output_dir=new_dir)
        assert os.path.exists(new_dir)
    finally:
        if os.path.exists(new_dir):
            shutil.rmtree(new_dir)


def test_generate_with_description():
    result = generate(AutoUser, output_dir=OUTPUT_DIR,
                      description="initial setup")
    assert "initial_setup" in result["file"]


def test_generate_with_apply():
    result = generate(AutoUser, output_dir=OUTPUT_DIR, apply=True)
    assert result["file"]    is not None
    assert result["applied"] is True
    assert db.table_exists("auto_users") is True


def test_generate_not_applied_by_default():
    result = generate(AutoUser, output_dir=OUTPUT_DIR)
    assert result["applied"] is False
    assert result["file"] is not None


def test_generate_multiple_models():
    r1 = generate(AutoUser,    output_dir=OUTPUT_DIR)
    r2 = generate(AutoProduct, output_dir=OUTPUT_DIR)
    assert r1["version"] == "0001"
    assert r2["version"] == "0002"
    assert os.path.exists(r1["file"])
    assert os.path.exists(r2["file"])


# ------------------------------------------------------------------ #
#  apply_migration_file()                                              #
# ------------------------------------------------------------------ #

def test_apply_creates_table():
    result  = generate(AutoUser, output_dir=OUTPUT_DIR)
    applied = apply_migration_file(result["file"])
    assert applied["applied"] is True
    assert db.table_exists("auto_users") is True


def test_apply_returns_result_dict():
    result  = generate(AutoUser, output_dir=OUTPUT_DIR)
    applied = apply_migration_file(result["file"])
    assert "file"    in applied
    assert "applied" in applied
    assert "sqls"    in applied
    assert "message" in applied


def test_apply_returns_sql_count():
    result  = generate(AutoUser, output_dir=OUTPUT_DIR)
    applied = apply_migration_file(result["file"])
    assert len(applied["sqls"]) == 1


def test_apply_nonexistent_file():
    result = apply_migration_file("nonexistent/path/0001.sql")
    assert result["applied"] is False
    assert "not found" in result["message"].lower()


def test_apply_file_path_in_result():
    result  = generate(AutoUser, output_dir=OUTPUT_DIR)
    applied = apply_migration_file(result["file"])
    assert applied["file"] == result["file"]


# ------------------------------------------------------------------ #
#  list_migration_files()                                              #
# ------------------------------------------------------------------ #

def test_list_empty_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = list_migration_files(OUTPUT_DIR)
    assert files == []


def test_list_nonexistent_dir():
    files = list_migration_files("nonexistent_xyz_dir")
    assert files == []


def test_list_returns_list():
    generate(AutoUser, output_dir=OUTPUT_DIR)
    files = list_migration_files(OUTPUT_DIR)
    assert isinstance(files, list)


def test_list_count():
    generate(AutoUser,    output_dir=OUTPUT_DIR)
    generate(AutoProduct, output_dir=OUTPUT_DIR)
    files = list_migration_files(OUTPUT_DIR)
    assert len(files) == 2


def test_list_sorted_by_version():
    generate(AutoUser,    output_dir=OUTPUT_DIR)
    generate(AutoProduct, output_dir=OUTPUT_DIR)
    files = list_migration_files(OUTPUT_DIR)
    assert files[0]["version"] < files[1]["version"]


def test_list_file_fields():
    generate(AutoUser, output_dir=OUTPUT_DIR)
    files = list_migration_files(OUTPUT_DIR)
    assert "file"     in files[0]
    assert "version"  in files[0]
    assert "name"     in files[0]
    assert "filename" in files[0]


def test_list_version_format():
    generate(AutoUser, output_dir=OUTPUT_DIR)
    files = list_migration_files(OUTPUT_DIR)
    assert files[0]["version"] == "0001"


def test_list_only_sql_files():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "readme.txt"), "w") as f:
        f.write("not a migration")
    generate(AutoUser, output_dir=OUTPUT_DIR)
    files = list_migration_files(OUTPUT_DIR)
    assert all(f["filename"].endswith(".sql") for f in files)