# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_sqlite_migrate_engine.py
# Project     : mydborm
# License     : MIT
# Description : Tests for SQLite support in the cross-database migration
#               engine (migrate.py) — TypeMapper, SchemaExtractor,
#               DDLGenerator, DataTransfer, ObjectMigrator, MigrationEngine.
#               SQLite needs no external service, so these tests are never
#               skipped (a live MySQL <-> SQLite round trip is included,
#               skipped only if MySQL isn't running on port 3307).
# =============================================================================

import os
import socket
import tempfile

import pytest

from mydborm import BaseModel, BoolField, IntField, StrField
from mydborm.db import ConnectionManager
from mydborm.migrate import (
    DataTransfer,
    DDLGenerator,
    MigrationEngine,
    ObjectMigrator,
    SchemaExtractor,
    TypeMapper,
)


def _is_available(port: int) -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=2)
        s.close()
        return True
    except OSError:
        return False


mysql_skip = pytest.mark.skipif(
    not _is_available(3307), reason="MySQL not running on port 3307"
)

MYSQL_CONFIG = dict(
    dialect="mysql", host="127.0.0.1", port=3307,
    user="root", password=os.environ.get("DB_PASSWORD", "root"),
    database="testdb", charset="utf8mb4",
)


@pytest.fixture
def sqlite_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def sqlite_path2():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


# ------------------------------------------------------------------ #
#  TypeMapper — mysql <-> sqlite                                       #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("mysql_type,expected", [
    ("int", "INTEGER"),
    ("int(11)", "INTEGER"),
    ("mediumint", "INTEGER"),
    ("varchar(100)", "VARCHAR(100)"),
    ("tinyint(1)", "TINYINT(1)"),
    ("text", "TEXT"),
    ("tinytext", "TEXT"),
    ("longblob", "BLOB"),
    ("decimal(10,2)", "DECIMAL(10,2)"),
    ("datetime", "DATETIME"),
    ("enum('a','b')", "VARCHAR(255)"),
    ("set('a','b')", "TEXT"),
])
def test_mysql_to_sqlite_type_mapping(mysql_type, expected):
    assert TypeMapper.mysql_to_sqlite(mysql_type) == expected


@pytest.mark.parametrize("sqlite_type,expected", [
    ("INTEGER", "INT"),
    ("VARCHAR(100)", "VARCHAR(100)"),
    ("TEXT", "TEXT"),
    ("REAL", "DOUBLE"),
    ("BOOLEAN", "TINYINT(1)"),
    ("BLOB", "BLOB"),
    ("DECIMAL(10,2)", "DECIMAL(10,2)"),
])
def test_sqlite_to_mysql_type_mapping(sqlite_type, expected):
    assert TypeMapper.sqlite_to_mysql(sqlite_type) == expected


def test_sqlite_to_yugabyte_type_mapping():
    assert TypeMapper.sqlite_to_yugabyte("INTEGER") == "INTEGER"
    assert TypeMapper.sqlite_to_yugabyte("VARCHAR(100)") == "VARCHAR(100)"
    assert TypeMapper.sqlite_to_yugabyte("TINYINT(1)") == "BOOLEAN"


def test_yugabyte_to_sqlite_type_mapping():
    assert TypeMapper.yugabyte_to_sqlite("BOOLEAN") == "TINYINT(1)"
    assert TypeMapper.yugabyte_to_sqlite("INTEGER") == "INTEGER"


def test_map_dispatches_mysql_sqlite_pairs():
    assert TypeMapper.map("int", "mysql", "sqlite") == "INTEGER"
    assert TypeMapper.map("INTEGER", "sqlite", "mysql") == "INT"


def test_map_dispatches_postgres_sqlite_pairs():
    assert TypeMapper.map("boolean", "yugabyte", "sqlite") == "TINYINT(1)"
    assert TypeMapper.map("TINYINT(1)", "sqlite", "postgres") == "BOOLEAN"


def test_map_sqlite_to_sqlite_is_identity():
    assert TypeMapper.map("VARCHAR(50)", "sqlite", "sqlite") == "VARCHAR(50)"


def test_is_known_type_sqlite():
    assert TypeMapper.is_known_type("INTEGER", "sqlite") is True
    assert TypeMapper.is_known_type("VARCHAR(100)", "sqlite") is True
    assert TypeMapper.is_known_type("some_made_up_type", "sqlite") is False


# ------------------------------------------------------------------ #
#  SchemaExtractor — live SQLite                                       #
# ------------------------------------------------------------------ #

class TestSchemaExtractorSQLite:
    @pytest.fixture(autouse=True)
    def setup_table(self, sqlite_path):
        self.mgr = ConnectionManager()
        self.mgr.configure(dialect="sqlite", database=sqlite_path)
        with self.mgr.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE migration_test_users (
                  id         INTEGER PRIMARY KEY AUTOINCREMENT,
                  username   VARCHAR(100) NOT NULL,
                  email      VARCHAR(255) NOT NULL,
                  is_active  TINYINT(1) DEFAULT 1,
                  created_at DATETIME
                );
            """)
            cur.execute(
                "CREATE UNIQUE INDEX uq_mtu_email ON migration_test_users (email);"
            )
        yield
        self.mgr.close()

    def test_list_tables_includes_test_table(self):
        extractor = SchemaExtractor(self.mgr)
        assert "migration_test_users" in extractor.list_tables()

    def test_extract_table_columns(self):
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_table("migration_test_users")
        names = [c["name"] for c in schema["columns"]]
        assert names == ["id", "username", "email", "is_active", "created_at"]

    def test_extract_table_column_nullability(self):
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_table("migration_test_users")
        by_name = {c["name"]: c for c in schema["columns"]}
        assert by_name["username"]["nullable"] is False
        assert by_name["created_at"]["nullable"] is True

    def test_extract_table_primary_key(self):
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_table("migration_test_users")
        assert schema["primary_key"] == ["id"]
        by_name = {c["name"]: c for c in schema["columns"]}
        assert by_name["id"]["is_primary_key"] is True

    def test_extract_table_unique_index(self):
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_table("migration_test_users")
        index_names = {idx["name"] for idx in schema["indexes"]}
        assert "uq_mtu_email" in index_names
        uq = next(i for i in schema["indexes"] if i["name"] == "uq_mtu_email")
        assert uq["unique"] is True
        assert uq["columns"] == ["email"]

    def test_extract_table_foreign_key(self):
        with self.mgr.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE migration_test_orders (
                  id      INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INT NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES migration_test_users (id)
                );
            """)
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_table("migration_test_orders")
        assert len(schema["foreign_keys"]) == 1
        fk = schema["foreign_keys"][0]
        assert fk["column"] == "user_id"
        assert fk["ref_table"] == "migration_test_users"
        assert fk["ref_column"] == "id"


# ------------------------------------------------------------------ #
#  DDLGenerator — sqlite target                                        #
# ------------------------------------------------------------------ #

def test_ddl_generator_mysql_to_sqlite_create_table():
    ddl = DDLGenerator("mysql", "sqlite")
    schema = {
        "table": "users",
        "columns": [
            {"name": "id", "type": "int", "nullable": False, "is_primary_key": True},
            {"name": "name", "type": "varchar(100)", "nullable": False},
        ],
        "primary_key": ["id"],
        "indexes": [],
    }
    result = ddl.generate(schema)
    assert "CREATE TABLE IF NOT EXISTS `users`" in result["create_table"]
    assert "`id` INTEGER" in result["create_table"]
    assert "PRIMARY KEY (`id`)" in result["create_table"]
    assert "ENGINE" not in result["create_table"]


def test_ddl_generator_create_indexes_namespaced_for_sqlite():
    ddl = DDLGenerator("mysql", "sqlite")
    schema = {
        "table": "products",
        "columns": [{"name": "sku", "type": "varchar(20)", "nullable": False}],
        "primary_key": [],
        "indexes": [{"name": "idx_sku", "columns": ["sku"], "unique": True}],
    }
    result = ddl.generate(schema)
    assert len(result["create_indexes"]) == 1
    assert "products_idx_sku" in result["create_indexes"][0]
    assert "IF NOT EXISTS" in result["create_indexes"][0]


# ------------------------------------------------------------------ #
#  DataTransfer.transform_row — sqlite target                          #
# ------------------------------------------------------------------ #

def test_transform_row_converts_tinyint_to_bool_for_sqlite_target():
    columns = [{"name": "active", "type": "tinyint(1)"}]
    result = DataTransfer.transform_row({"active": 1}, columns, "sqlite")
    assert result == (True,)


def test_transform_row_converts_tinyint_bytes_to_bool_for_sqlite_target():
    columns = [{"name": "active", "type": "bit(1)"}]
    result = DataTransfer.transform_row({"active": b"\x01"}, columns, "sqlite")
    assert result == (True,)


# ------------------------------------------------------------------ #
#  ObjectMigrator — sqlite target (SQL generation only, no live DB)    #
# ------------------------------------------------------------------ #

class OMSLUser(BaseModel):
    __tablename__ = "om_sl_users"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=100, nullable=False)
    active = BoolField(default=True)


def test_object_migrator_create_table_sql_sqlite_target():
    target = ConnectionManager()
    target.configure(dialect="sqlite", database=":memory:")
    migrator = ObjectMigrator(ConnectionManager(), target)

    sql = migrator.create_table_sql(OMSLUser)

    assert "CREATE TABLE IF NOT EXISTS `om_sl_users`" in sql
    assert "`id` INTEGER PRIMARY KEY AUTOINCREMENT" in sql
    assert "`name` VARCHAR(100) NOT NULL" in sql
    assert "`active` TINYINT(1)" in sql
    assert "ENGINE" not in sql


# ------------------------------------------------------------------ #
#  MigrationEngine — live SQLite -> SQLite (two temp files)            #
# ------------------------------------------------------------------ #

class TestMigrationEngineSQLite:
    @pytest.fixture(autouse=True)
    def setup_dbs(self, sqlite_path, sqlite_path2):
        self.source_path = sqlite_path
        self.target_path = sqlite_path2

        self.source = ConnectionManager()
        self.source.configure(dialect="sqlite", database=self.source_path)
        self.target = ConnectionManager()
        self.target.configure(dialect="sqlite", database=self.target_path)

        with self.source.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE migration_test_users (
                  id       INTEGER PRIMARY KEY AUTOINCREMENT,
                  username VARCHAR(100) NOT NULL,
                  active   TINYINT(1) DEFAULT 1
                );
            """)
            cur.execute(
                "CREATE UNIQUE INDEX uq_me_username ON migration_test_users (username);"
            )
            cur.executemany(
                "INSERT INTO migration_test_users (username, active) VALUES (%s, %s)",
                [(f"user{i}", i % 2) for i in range(1, 11)],
            )
        yield
        self.source.close()
        self.target.close()

    def _make_engine(self):
        return MigrationEngine(
            source={"dialect": "sqlite", "database": self.source_path},
            target={"dialect": "sqlite", "database": self.target_path},
        )

    def test_dry_run_returns_report_without_writing(self):
        engine = self._make_engine()
        report = engine.dry_run(tables=["migration_test_users"])

        assert len(report["tables"]) == 1
        table_report = report["tables"][0]
        assert table_report["table"] == "migration_test_users"
        assert table_report["rows"] == 10
        assert "CREATE TABLE IF NOT EXISTS" in table_report["create_table_sql"]

        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name='migration_test_users'"
            )
            assert cur.fetchone()[0] == 0

    def test_run_full_migration_transfers_all_rows(self):
        engine = self._make_engine()
        result = engine.run(tables=["migration_test_users"])

        assert result.is_success()
        assert result.tables_migrated == 1
        assert result.total_rows == 10
        assert result.rows_transferred == 10

        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM migration_test_users")
            assert cur.fetchone()[0] == 10

    def test_run_preserves_unique_index(self):
        engine = self._make_engine()
        engine.run(tables=["migration_test_users"])

        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='migration_test_users'"
            )
            index_names = [r[0] for r in cur.fetchall()]
        assert any("uq_me_username" in n for n in index_names)


# ------------------------------------------------------------------ #
#  Live MySQL <-> SQLite round trip                                    #
# ------------------------------------------------------------------ #

@mysql_skip
class TestMigrationEngineMySQLToSQLite:
    @pytest.fixture(autouse=True)
    def setup_dbs(self, sqlite_path):
        self.target_path = sqlite_path
        self.source = ConnectionManager()
        self.source.configure(**MYSQL_CONFIG)
        self.target = ConnectionManager()
        self.target.configure(dialect="sqlite", database=self.target_path)

        with self.source.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS migration_test_ms_users")
            cur.execute("""
                CREATE TABLE migration_test_ms_users (
                  id       INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  username VARCHAR(100) NOT NULL,
                  active   TINYINT(1) DEFAULT 1
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.executemany(
                "INSERT INTO migration_test_ms_users "
                "(username, active) VALUES (%s, %s)",
                [(f"user{i}", i % 2) for i in range(1, 6)],
            )
        yield
        with self.source.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS migration_test_ms_users")
        self.source.close()
        self.target.close()

    def test_run_migrates_mysql_to_sqlite(self):
        engine = MigrationEngine(
            source=MYSQL_CONFIG,
            target={"dialect": "sqlite", "database": self.target_path},
        )
        result = engine.run(tables=["migration_test_ms_users"])

        assert result.is_success()
        assert result.rows_transferred == 5

        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM migration_test_ms_users WHERE active = 1")
            assert cur.fetchone()[0] == 3
