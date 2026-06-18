# -*- coding: utf-8 -*-
import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm import migrations as mg

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

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(dialect="mysql", host="127.0.0.1", port=3307, user="root",
                 password=os.environ.get("DB_PASSWORD","root"), database="testdb", charset="utf8mb4")
    yield
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS mig_users")
        cur.execute("DROP TABLE IF EXISTS mig_products")
    db.close()

@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS mig_users")
        cur.execute("DROP TABLE IF EXISTS mig_products")
        cur.execute("DELETE FROM `_mydborm_migrations` WHERE description LIKE '%mig_%'")
    yield

def test_table_exists_false():
    assert mg.table_exists("mig_users") is False

def test_table_exists_true():
    MigUser.create_table()
    assert mg.table_exists("mig_users") is True

def test_table_exists_nonexistent():
    assert mg.table_exists("nonexistent_xyz") is False

def test_get_live_schema_empty():
    assert mg.get_live_schema("nonexistent_xyz") == {}

def test_get_live_schema_columns():
    MigUser.create_table()
    schema = mg.get_live_schema("mig_users")
    assert "id" in schema
    assert "username" in schema

def test_get_live_schema_pk():
    MigUser.create_table()
    schema = mg.get_live_schema("mig_users")
    assert schema["id"]["key"] == "PRI"

def test_diff_new_table():
    diff = mg.diff_schema(MigUser)
    assert diff["new_table"] is True
    assert len(diff["add_columns"]) > 0

def test_diff_no_changes():
    MigUser.create_table()
    diff = mg.diff_schema(MigUser)
    assert diff["new_table"] is False
    assert diff["add_columns"] == {}

def test_diff_detects_new_column():
    MigUser.create_table()
    class Extended(BaseModel):
        __tablename__ = "mig_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=100, nullable=False)
        email    = StrField(max_length=255, nullable=False)
        active   = BoolField(default=True)
        phone    = StrField(max_length=20, nullable=True)
    diff = mg.diff_schema(Extended)
    assert "phone" in diff["add_columns"]

def test_diff_detects_dropped_column():
    MigUser.create_table()
    class Reduced(BaseModel):
        __tablename__ = "mig_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=100, nullable=False)
    diff = mg.diff_schema(Reduced)
    assert "email" in diff["drop_columns"]

def test_generate_sql_create():
    sqls = mg.generate_migration_sql(MigUser)
    assert len(sqls) == 1
    assert "CREATE TABLE" in sqls[0]

def test_generate_sql_empty_when_uptodate():
    MigUser.create_table()
    assert mg.generate_migration_sql(MigUser) == []

def test_migrate_creates_table():
    result = mg.migrate(MigUser, description="create mig_users")
    assert result["applied"] is True
    assert mg.table_exists("mig_users") is True

def test_migrate_result_dict():
    result = mg.migrate(MigUser)
    for key in ["table","sqls","applied","message"]:
        assert key in result

def test_migrate_not_applied_when_uptodate():
    mg.migrate(MigUser)
    result = mg.migrate(MigUser)
    assert result["applied"] is False

def test_migrate_multiple_models():
    assert mg.migrate(MigUser,    description="create mig_users")["applied"] is True
    assert mg.migrate(MigProduct, description="create mig_products")["applied"] is True

def test_migration_status_list():
    assert isinstance(mg.migration_status(), list)

def test_migration_status_after_migrate():
    mg.migrate(MigUser,    description="mig_users status")
    mg.migrate(MigProduct, description="mig_products status")
    assert len(mg.migration_status()) >= 2

def test_migration_status_fields():
    mg.migrate(MigUser, description="mig_users fields")
    records = [s for s in mg.migration_status() if "mig_users" in s["description"]]
    assert len(records) > 0
    for key in ["id","version","description","applied_at","rolled_back"]:
        assert key in records[0]

def test_rollback_drops_table():
    mg.migrate(MigUser, description="mig_users rollback")
    assert mg.table_exists("mig_users") is True
    result = mg.rollback(MigUser)
    assert result["applied"] is True
    assert mg.table_exists("mig_users") is False

def test_rollback_nonexistent():
    result = mg.rollback(MigUser)
    assert result["applied"] is False

def test_checksum_consistent():
    from mydborm.migrations import _checksum
    assert _checksum("SELECT 1") == _checksum("SELECT 1")

def test_checksum_differs():
    from mydborm.migrations import _checksum
    assert _checksum("SELECT 1") != _checksum("SELECT 2")

def test_checksum_length():
    from mydborm.migrations import _checksum
    assert len(_checksum("test")) == 16
