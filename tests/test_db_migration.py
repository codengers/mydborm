# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_db_migration.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Version     : 1.10.0
# License     : MIT
# Description : pytest tests for the database migration engine —
#               TypeMapper, SchemaExtractor, DDLGenerator, DataTransfer,
#               Verifier, MigrationEngine, MigrationResult.
# =============================================================================

import os
import socket

import pytest

from mydborm.db import ConnectionManager
from mydborm.migrate import (
    TypeMapper, SchemaExtractor, DDLGenerator, DataTransfer, Verifier,
    MigrationEngine, MigrationResult, _pg_column_type,
)


def _is_available(port: int) -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=2)
        s.close()
        return True
    except OSError:
        return False


MYSQL_AVAILABLE = _is_available(3307)
YB_AVAILABLE = _is_available(5433)

mysql_skip = pytest.mark.skipif(not MYSQL_AVAILABLE, reason="MySQL not running on port 3307")
yb_skip = pytest.mark.skipif(not YB_AVAILABLE, reason="YugabyteDB not running on port 5433")

MYSQL_CONFIG = dict(
    dialect="mysql", host="127.0.0.1", port=3307,
    user="root", password=os.environ.get("DB_PASSWORD", "root"),
    charset="utf8mb4",
)
YB_CONFIG = dict(
    dialect="yugabyte", host="127.0.0.1", port=5433,
    user="yugabyte", password=os.environ.get("YB_PASSWORD", "yugabyte"),
)


# ------------------------------------------------------------------ #
#  TypeMapper.mysql_to_yugabyte                                        #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("mysql_type,expected", [
    ("int", "INTEGER"),
    ("int(11)", "INTEGER"),
    ("integer", "INTEGER"),
    ("tinyint(1)", "BOOLEAN"),
    ("tinyint", "SMALLINT"),
    ("tinyint(4)", "SMALLINT"),
    ("smallint", "SMALLINT"),
    ("bigint", "BIGINT"),
    ("bigint(20) unsigned", "NUMERIC(20)"),
    ("bigint unsigned", "NUMERIC(20)"),
    ("float", "FLOAT"),
    ("double", "DOUBLE PRECISION"),
    ("decimal(10,2)", "DECIMAL(10,2)"),
    ("varchar(100)", "VARCHAR(100)"),
    ("char(10)", "CHAR(10)"),
    ("text", "TEXT"),
    ("tinytext", "TEXT"),
    ("mediumtext", "TEXT"),
    ("longtext", "TEXT"),
    ("blob", "BYTEA"),
    ("mediumblob", "BYTEA"),
    ("longblob", "BYTEA"),
    ("binary(16)", "BYTEA"),
    ("varbinary(16)", "BYTEA"),
    ("date", "DATE"),
    ("datetime", "TIMESTAMP"),
    ("timestamp", "TIMESTAMPTZ"),
    ("time", "TIME"),
    ("json", "JSONB"),
    ("enum('a','b','c')", "VARCHAR(255)"),
    ("set('a','b')", "TEXT"),
])
def test_mysql_to_yugabyte_type_mapping(mysql_type, expected):
    assert TypeMapper.mysql_to_yugabyte(mysql_type) == expected


def test_mysql_to_yugabyte_unknown_type_falls_back_to_text():
    assert TypeMapper.mysql_to_yugabyte("geometry") == "TEXT"


# ------------------------------------------------------------------ #
#  TypeMapper.yugabyte_to_mysql                                        #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("pg_type,expected", [
    ("integer", "INT"),
    ("serial", "INT"),
    ("boolean", "TINYINT(1)"),
    ("smallint", "SMALLINT"),
    ("bigint", "BIGINT"),
    ("numeric(20)", "BIGINT UNSIGNED"),
    ("numeric(20,0)", "DECIMAL(20,0)"),
    ("float", "FLOAT"),
    ("double precision", "DOUBLE"),
    ("decimal(10,2)", "DECIMAL(10,2)"),
    ("varchar(100)", "VARCHAR(100)"),
    ("char(10)", "CHAR(10)"),
    ("text", "TEXT"),
    ("bytea", "BLOB"),
    ("date", "DATE"),
    ("timestamp", "DATETIME"),
    ("timestamptz", "DATETIME"),
    ("time", "TIME"),
    ("jsonb", "JSON"),
    ("json", "JSON"),
])
def test_yugabyte_to_mysql_type_mapping(pg_type, expected):
    assert TypeMapper.yugabyte_to_mysql(pg_type) == expected


def test_yugabyte_to_mysql_long_form_postgres_names():
    assert TypeMapper.yugabyte_to_mysql("character varying(50)") == "VARCHAR(50)"
    assert TypeMapper.yugabyte_to_mysql("timestamp without time zone") == "DATETIME"
    assert TypeMapper.yugabyte_to_mysql("timestamp with time zone") == "DATETIME"


def test_yugabyte_to_mysql_unknown_type_falls_back_to_text():
    assert TypeMapper.yugabyte_to_mysql("uuid") == "TEXT"


# ------------------------------------------------------------------ #
#  TypeMapper.map / is_known_type                                      #
# ------------------------------------------------------------------ #

def test_map_same_dialect_is_identity():
    assert TypeMapper.map("varchar(50)", "mysql", "mysql") == "varchar(50)"


def test_map_mysql_to_postgres_alias():
    assert TypeMapper.map("int(11)", "mysql", "postgres") == "INTEGER"


def test_map_postgres_to_yugabyte_is_identity():
    assert TypeMapper.map("integer", "postgres", "yugabyte") == "integer"


def test_map_unsupported_pair_raises():
    from mydborm.exceptions import UnsupportedDialectError
    with pytest.raises(UnsupportedDialectError):
        TypeMapper.map("int", "mysql", "sqlite")


def test_is_known_type_true_for_mapped():
    assert TypeMapper.is_known_type("varchar(100)", "mysql") is True


def test_is_known_type_false_for_unmapped():
    assert TypeMapper.is_known_type("geometry", "mysql") is False


# ------------------------------------------------------------------ #
#  SchemaExtractor — live MySQL                                        #
# ------------------------------------------------------------------ #

@mysql_skip
class TestSchemaExtractorMySQL:
    @pytest.fixture(autouse=True)
    def setup_table(self):
        self.mgr = ConnectionManager()
        self.mgr.configure(database="testdb", **MYSQL_CONFIG)
        with self.mgr.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS migration_test_users")
            cur.execute("""
                CREATE TABLE migration_test_users (
                  id         INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  username   VARCHAR(100) NOT NULL,
                  email      VARCHAR(255) NOT NULL,
                  is_active  TINYINT(1) DEFAULT 1,
                  balance    DECIMAL(10,2) DEFAULT 0.00,
                  created_at DATETIME,
                  UNIQUE KEY uq_mtu_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
        yield
        with self.mgr.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS migration_test_users")
        self.mgr.close()

    def test_list_tables_includes_test_table(self):
        extractor = SchemaExtractor(self.mgr)
        assert "migration_test_users" in extractor.list_tables()

    def test_extract_table_columns(self):
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_table("migration_test_users")
        names = [c["name"] for c in schema["columns"]]
        assert names == ["id", "username", "email", "is_active", "balance", "created_at"]

    def test_extract_table_column_types(self):
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_table("migration_test_users")
        by_name = {c["name"]: c for c in schema["columns"]}
        assert by_name["username"]["type"] == "varchar(100)"
        assert by_name["is_active"]["type"] == "tinyint(1)"
        assert by_name["balance"]["type"] == "decimal(10,2)"
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

    def test_extract_schema_multiple_tables(self):
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_schema(["migration_test_users"])
        assert set(schema.keys()) == {"migration_test_users"}


# ------------------------------------------------------------------ #
#  SchemaExtractor — live YugabyteDB                                   #
# ------------------------------------------------------------------ #

@yb_skip
class TestSchemaExtractorYugabyte:
    @pytest.fixture(autouse=True)
    def setup_table(self):
        self.mgr = ConnectionManager()
        self.mgr.configure(database="yugabyte", **YB_CONFIG)
        with self.mgr.connect() as conn:
            cur = conn.cursor()
            cur.execute('DROP TABLE IF EXISTS migration_test_yb_users;')
            cur.execute("""
                CREATE TABLE migration_test_yb_users (
                  id       SERIAL PRIMARY KEY,
                  username VARCHAR(100) NOT NULL,
                  active   BOOLEAN DEFAULT TRUE,
                  amount   NUMERIC(20) DEFAULT 0
                );
            """)
        yield
        with self.mgr.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS migration_test_yb_users;")
        self.mgr.close()

    def test_extract_table_columns_and_pk(self):
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_table("migration_test_yb_users")
        names = [c["name"] for c in schema["columns"]]
        assert names == ["id", "username", "active", "amount"]
        assert schema["primary_key"] == ["id"]

    def test_extract_table_canonical_numeric_type(self):
        extractor = SchemaExtractor(self.mgr)
        schema = extractor.extract_table("migration_test_yb_users")
        by_name = {c["name"]: c for c in schema["columns"]}
        assert by_name["amount"]["type"] == "numeric(20)"
        assert by_name["active"]["type"] == "boolean"
        assert by_name["username"]["type"] == "character varying(100)"


# ------------------------------------------------------------------ #
#  DDLGenerator                                                        #
# ------------------------------------------------------------------ #

SAMPLE_MYSQL_SCHEMA = {
    "table": "orders",
    "columns": [
        {"name": "id", "type": "int(11)", "nullable": False, "default": None, "is_primary_key": True},
        {"name": "customer_email", "type": "varchar(255)", "nullable": False, "default": None, "is_primary_key": False},
        {"name": "is_paid", "type": "tinyint(1)", "nullable": False, "default": "0", "is_primary_key": False},
        {"name": "total", "type": "decimal(10,2)", "nullable": True, "default": None, "is_primary_key": False},
        {"name": "notes", "type": "geometry", "nullable": True, "default": None, "is_primary_key": False},
    ],
    "primary_key": ["id"],
    "indexes": [
        {"name": "uq_orders_email", "columns": ["customer_email"], "unique": True},
        {"name": "idx_orders_paid", "columns": ["is_paid"], "unique": False},
    ],
    "foreign_keys": [],
}


def test_ddl_generator_mysql_to_yugabyte_create_table():
    ddl = DDLGenerator("mysql", "yugabyte")
    sql = ddl.create_table_sql(SAMPLE_MYSQL_SCHEMA)
    assert 'CREATE TABLE IF NOT EXISTS "orders"' in sql
    assert '"id" INTEGER NOT NULL' in sql
    assert '"customer_email" VARCHAR(255) NOT NULL' in sql
    assert '"is_paid" BOOLEAN NOT NULL DEFAULT FALSE' in sql
    assert '"total" DECIMAL(10,2)' in sql
    assert 'PRIMARY KEY ("id")' in sql


def test_ddl_generator_unmapped_type_falls_back_and_warns():
    ddl = DDLGenerator("mysql", "yugabyte")
    ddl.create_table_sql(SAMPLE_MYSQL_SCHEMA)
    assert any("notes" in w for w in ddl.warnings)
    assert any("TEXT fallback" in w for w in ddl.warnings)


def test_ddl_generator_create_indexes_namespaced_for_postgres_family():
    ddl = DDLGenerator("mysql", "yugabyte")
    result = ddl.generate(SAMPLE_MYSQL_SCHEMA)
    assert len(result["create_indexes"]) == 2
    unique_sql = next(s for s in result["create_indexes"] if "uq_orders_email" in s)
    assert "UNIQUE INDEX" in unique_sql
    assert '"orders_uq_orders_email"' in unique_sql
    assert '"orders"' in unique_sql
    plain_sql = next(s for s in result["create_indexes"] if "idx_orders_paid" in s)
    assert "UNIQUE" not in plain_sql


def test_ddl_generator_skips_index_matching_primary_key():
    schema = dict(SAMPLE_MYSQL_SCHEMA)
    schema["indexes"] = [{"name": "PRIMARY", "columns": ["id"], "unique": True}]
    ddl = DDLGenerator("mysql", "yugabyte")
    result = ddl.generate(schema)
    assert result["create_indexes"] == []


def test_ddl_generator_yugabyte_to_mysql_create_table():
    schema = {
        "table": "products",
        "columns": [
            {"name": "id", "type": "integer", "nullable": False, "default": None, "is_primary_key": True},
            {"name": "active", "type": "boolean", "nullable": False, "default": "true", "is_primary_key": False},
            {"name": "price", "type": "numeric(8,2)", "nullable": True, "default": None, "is_primary_key": False},
        ],
        "primary_key": ["id"],
        "indexes": [],
        "foreign_keys": [],
    }
    ddl = DDLGenerator("yugabyte", "mysql")
    sql = ddl.create_table_sql(schema)
    assert "CREATE TABLE IF NOT EXISTS `products`" in sql
    assert "`id` INT NOT NULL" in sql
    assert "`active` TINYINT(1) NOT NULL" in sql
    assert "`price` DECIMAL(8,2)" in sql
    assert "PRIMARY KEY (`id`)" in sql
    assert ddl.warnings == []


def test_ddl_generator_mysql_target_index_sql_uses_backticks():
    ddl = DDLGenerator("yugabyte", "mysql")
    sql = ddl.create_index_sql("products", {"name": "idx_active", "columns": ["active"], "unique": False})
    assert sql == "CREATE INDEX `idx_active` ON `products` (`active`);"


# ------------------------------------------------------------------ #
#  DataTransfer — live MySQL, two databases on the same server         #
# ------------------------------------------------------------------ #

DT_COLUMNS = [
    {"name": "id", "type": "int(11)"},
    {"name": "username", "type": "varchar(100)"},
    {"name": "is_active", "type": "tinyint(1)"},
]


@mysql_skip
class TestDataTransferMySQL:
    @pytest.fixture(autouse=True)
    def setup_dbs(self):
        bootstrap = ConnectionManager()
        bootstrap.configure(**MYSQL_CONFIG)
        with bootstrap.connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_source")
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_target")
        bootstrap.close()

        self.source = ConnectionManager()
        self.source.configure(database="testdb_source", **MYSQL_CONFIG)
        self.target = ConnectionManager()
        self.target.configure(database="testdb_target", **MYSQL_CONFIG)

        with self.source.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS dt_users")
            cur.execute("""
                CREATE TABLE dt_users (
                  id INT NOT NULL PRIMARY KEY,
                  username VARCHAR(100) NOT NULL,
                  is_active TINYINT(1) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS dt_users")
            cur.execute("""
                CREATE TABLE dt_users (
                  id INT NOT NULL PRIMARY KEY,
                  username VARCHAR(100) NOT NULL,
                  is_active TINYINT(1) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

        yield

        with self.source.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS dt_users")
        with self.target.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS dt_users")
        self.source.close()
        self.target.close()

    def _insert_source_rows(self, n):
        with self.source.connect() as conn:
            cur = conn.cursor()
            cur.executemany(
                "INSERT INTO dt_users (id, username, is_active) VALUES (%s, %s, %s)",
                [(i, f"user{i}", i % 2) for i in range(1, n + 1)],
            )

    def test_copy_table_transfers_all_rows(self):
        self._insert_source_rows(5)
        transfer = DataTransfer(self.source, self.target, chunk_size=2)
        stats = transfer.copy_table("dt_users", DT_COLUMNS)
        assert stats == {"rows_total": 5, "rows_transferred": 5}
        assert transfer.count_rows(self.target, "dt_users") == 5

    def test_copy_table_chunks_with_progress_callback(self):
        self._insert_source_rows(7)
        progress_calls = []
        transfer = DataTransfer(self.source, self.target, chunk_size=3)
        transfer.copy_table("dt_users", DT_COLUMNS,
                             on_progress=lambda t, done, tot: progress_calls.append((t, done, tot)))
        assert progress_calls == [
            ("dt_users", 3, 7), ("dt_users", 6, 7), ("dt_users", 7, 7),
        ]

    def test_copy_table_empty_source_reports_zero(self):
        calls = []
        transfer = DataTransfer(self.source, self.target)
        stats = transfer.copy_table(
            "dt_users", DT_COLUMNS,
            on_progress=lambda t, done, tot: calls.append((t, done, tot)),
        )
        assert stats == {"rows_total": 0, "rows_transferred": 0}
        assert calls == [("dt_users", 0, 0)]

    def test_target_has_data_false_when_empty(self):
        transfer = DataTransfer(self.source, self.target)
        assert transfer.target_has_data("dt_users") is False

    def test_target_has_data_true_after_copy(self):
        self._insert_source_rows(2)
        transfer = DataTransfer(self.source, self.target)
        transfer.copy_table("dt_users", DT_COLUMNS)
        assert transfer.target_has_data("dt_users") is True

    def test_copy_table_preserves_row_values(self):
        self._insert_source_rows(3)
        transfer = DataTransfer(self.source, self.target)
        transfer.copy_table("dt_users", DT_COLUMNS)
        rows = self.target.fetchall("SELECT id, username, is_active FROM dt_users ORDER BY id")
        assert [r["username"] for r in rows] == ["user1", "user2", "user3"]


def test_transform_row_converts_tinyint_to_bool_for_postgres_family():
    row = {"id": 1, "is_active": 1}
    columns = [
        {"name": "id", "type": "int(11)"},
        {"name": "is_active", "type": "tinyint(1)"},
    ]
    values = DataTransfer.transform_row(row, columns, "yugabyte")
    assert values == (1, True)


def test_transform_row_converts_tinyint_bytes_to_bool_for_postgres_family():
    row = {"id": 1, "is_active": b"\x01"}
    columns = [
        {"name": "id", "type": "int(11)"},
        {"name": "is_active", "type": "tinyint(1)"},
    ]
    values = DataTransfer.transform_row(row, columns, "yugabyte")
    assert values == (1, True)


def test_transform_row_leaves_mysql_target_untouched():
    row = {"id": 1, "is_active": 1}
    columns = [
        {"name": "id", "type": "int(11)"},
        {"name": "is_active", "type": "tinyint(1)"},
    ]
    values = DataTransfer.transform_row(row, columns, "mysql")
    assert values == (1, 1)


# ------------------------------------------------------------------ #
#  Verifier — live MySQL, two databases on the same server             #
# ------------------------------------------------------------------ #

@mysql_skip
class TestVerifierMySQL:
    @pytest.fixture(autouse=True)
    def setup_dbs(self):
        bootstrap = ConnectionManager()
        bootstrap.configure(**MYSQL_CONFIG)
        with bootstrap.connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_source")
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_target")
        bootstrap.close()

        self.source = ConnectionManager()
        self.source.configure(database="testdb_source", **MYSQL_CONFIG)
        self.target = ConnectionManager()
        self.target.configure(database="testdb_target", **MYSQL_CONFIG)

        with self.source.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS v_users")
            cur.execute("CREATE TABLE v_users (id INT PRIMARY KEY) ENGINE=InnoDB;")
            cur.executemany(
                "INSERT INTO v_users (id) VALUES (%s)", [(1,), (2,), (3,)]
            )
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS v_users")

        yield

        with self.source.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS v_users")
        with self.target.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS v_users")
        self.source.close()
        self.target.close()

    def test_verify_table_missing_in_target(self):
        verifier = Verifier(self.source, self.target)
        result = verifier.verify_table("v_users")
        assert result == {
            "table": "v_users", "source_rows": 3, "target_rows": 0,
            "table_exists": False, "match": False,
        }

    def test_verify_table_match_after_copy(self):
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE v_users (id INT PRIMARY KEY) ENGINE=InnoDB;")
            cur.executemany("INSERT INTO v_users (id) VALUES (%s)", [(1,), (2,), (3,)])

        verifier = Verifier(self.source, self.target)
        result = verifier.verify_table("v_users")
        assert result["match"] is True
        assert result["source_rows"] == result["target_rows"] == 3

    def test_verify_table_mismatch_after_partial_copy(self):
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE v_users (id INT PRIMARY KEY) ENGINE=InnoDB;")
            cur.execute("INSERT INTO v_users (id) VALUES (1)")

        verifier = Verifier(self.source, self.target)
        result = verifier.verify_table("v_users")
        assert result["match"] is False
        assert result["source_rows"] == 3
        assert result["target_rows"] == 1

    def test_verify_aggregates_warnings(self):
        verifier = Verifier(self.source, self.target)
        report = verifier.verify(["v_users"])
        assert len(report["results"]) == 1
        assert "missing in the target database" in report["warnings"][0]

    def test_verify_no_warnings_when_matching(self):
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE v_users (id INT PRIMARY KEY) ENGINE=InnoDB;")
            cur.executemany("INSERT INTO v_users (id) VALUES (%s)", [(1,), (2,), (3,)])

        verifier = Verifier(self.source, self.target)
        report = verifier.verify(["v_users"])
        assert report["warnings"] == []


# ------------------------------------------------------------------ #
#  MigrationEngine — live MySQL -> MySQL (same server, different db)  #
# ------------------------------------------------------------------ #

def _source_engine_config():
    return dict(MYSQL_CONFIG, database="testdb_source")


def _target_engine_config():
    return dict(MYSQL_CONFIG, database="testdb_target")


@mysql_skip
class TestMigrationEngineMySQL:
    @pytest.fixture(autouse=True)
    def setup_dbs(self):
        bootstrap = ConnectionManager()
        bootstrap.configure(**MYSQL_CONFIG)
        with bootstrap.connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_source")
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_target")
        bootstrap.close()

        self.source = ConnectionManager()
        self.source.configure(**_source_engine_config())
        self.target = ConnectionManager()
        self.target.configure(**_target_engine_config())

        with self.source.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS migration_test_users")
            cur.execute("""
                CREATE TABLE migration_test_users (
                  id       INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  username VARCHAR(100) NOT NULL,
                  active   TINYINT(1) DEFAULT 1,
                  UNIQUE KEY uq_me_username (username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.executemany(
                "INSERT INTO migration_test_users (username, active) VALUES (%s, %s)",
                [(f"user{i}", i % 2) for i in range(1, 11)],
            )
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS migration_test_users")

        yield

        with self.source.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS migration_test_users")
        with self.target.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS migration_test_users")
        self.source.close()
        self.target.close()

    def _make_engine(self):
        return MigrationEngine(
            source=_source_engine_config(),
            target=_target_engine_config(),
        )

    def test_dry_run_returns_report_without_writing(self):
        engine = self._make_engine()
        report = engine.dry_run(tables=["migration_test_users"])

        assert len(report["tables"]) == 1
        table_report = report["tables"][0]
        assert table_report["table"] == "migration_test_users"
        assert table_report["rows"] == 10
        assert "CREATE TABLE IF NOT EXISTS" in table_report["create_table_sql"]

        # dry_run must not create the table in the target
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'testdb_target' AND table_name = 'migration_test_users'"
            )
            assert cur.fetchone()[0] == 0

    def test_run_full_migration_transfers_all_rows(self):
        engine = self._make_engine()
        result = engine.run(tables=["migration_test_users"])

        assert result.is_success()
        assert result.tables_migrated == 1
        assert result.tables_failed == 0
        assert result.total_rows == 10
        assert result.rows_transferred == 10

        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM migration_test_users")
            assert cur.fetchone()[0] == 10

    def test_run_progress_callback_invoked(self):
        engine = self._make_engine()
        calls = []
        engine.run(
            tables=["migration_test_users"], chunk_size=4,
            on_progress=lambda t, done, total: calls.append((t, done, total)),
        )
        assert calls[-1] == ("migration_test_users", 10, 10)

    def test_run_skips_table_with_existing_target_data(self):
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE migration_test_users (
                  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  username VARCHAR(100) NOT NULL,
                  active TINYINT(1) DEFAULT 1
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute(
                "INSERT INTO migration_test_users (username, active) VALUES ('existing', 1)"
            )

        engine = self._make_engine()
        result = engine.run(tables=["migration_test_users"], overwrite=False)

        assert result.tables_migrated == 0
        assert any("Skipped" in w for w in result.warnings)
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM migration_test_users")
            assert cur.fetchone()[0] == 1  # untouched

    def test_run_overwrite_replaces_existing_target_data(self):
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE migration_test_users (
                  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  username VARCHAR(100) NOT NULL,
                  active TINYINT(1) DEFAULT 1
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute(
                "INSERT INTO migration_test_users (username, active) VALUES ('stale', 1)"
            )

        engine = self._make_engine()
        result = engine.run(tables=["migration_test_users"], overwrite=True)

        assert result.tables_migrated == 1
        assert result.rows_transferred == 10
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM migration_test_users WHERE username = 'stale'")
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT COUNT(*) FROM migration_test_users")
            assert cur.fetchone()[0] == 10

    def test_run_records_failure_for_nonexistent_table(self):
        engine = self._make_engine()
        result = engine.run(tables=["does_not_exist_xyz"])

        assert result.is_success() is False
        assert result.tables_failed == 1
        assert any("does_not_exist_xyz" in e for e in result.errors)

    def test_run_closes_connections_when_done(self):
        engine = self._make_engine()
        engine.run(tables=["migration_test_users"])
        assert getattr(engine.source_db._local, "conn", None) is None
        assert getattr(engine.target_db._local, "conn", None) is None


# ------------------------------------------------------------------ #
#  MigrationResult                                                     #
# ------------------------------------------------------------------ #

def test_migration_result_defaults():
    result = MigrationResult()
    assert result.tables_migrated == 0
    assert result.tables_failed == 0
    assert result.is_success() is True


def test_migration_result_is_success_false_on_failure():
    result = MigrationResult(tables_failed=1, errors=["users: boom"])
    assert result.is_success() is False


def test_migration_result_summary_contains_key_fields():
    result = MigrationResult(
        tables_migrated=2, tables_failed=1, total_rows=100,
        rows_transferred=80, duration=1.234,
        errors=["orders: timeout"], warnings=["products: skipped"],
    )
    summary = result.summary()
    assert "Status            : FAILED" in summary
    assert "Tables migrated   : 2" in summary
    assert "Tables failed     : 1" in summary
    assert "Total rows        : 100" in summary
    assert "Rows transferred  : 80" in summary
    assert "Duration          : 1.234s" in summary
    assert "orders: timeout" in summary
    assert "products: skipped" in summary


def test_migration_result_summary_success_status():
    result = MigrationResult(tables_migrated=1, total_rows=5, rows_transferred=5)
    assert "Status            : SUCCESS" in result.summary()


# ------------------------------------------------------------------ #
#  Extra edge-case coverage                                            #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("mysql_type,expected", [
    ("decimal(10)", "DECIMAL(10)"),
    ("decimal", "DECIMAL"),
    ("bit(1)", "BOOLEAN"),
    ("bit(8)", "BYTEA"),
    ("", "TEXT"),
])
def test_mysql_to_yugabyte_extra_edge_cases(mysql_type, expected):
    assert TypeMapper.mysql_to_yugabyte(mysql_type) == expected


@pytest.mark.parametrize("pg_type,expected", [
    ("numeric", "DECIMAL"),
])
def test_yugabyte_to_mysql_bare_numeric(pg_type, expected):
    assert TypeMapper.yugabyte_to_mysql(pg_type) == expected


def test_pg_column_type_character_with_length():
    assert _pg_column_type("character", 10, None, None) == "character(10)"


def test_pg_column_type_character_without_length():
    assert _pg_column_type("character", None, None, None) == "character"


def test_pg_column_type_numeric_with_scale():
    assert _pg_column_type("numeric", None, 10, 2) == "numeric(10,2)"


def test_pg_column_type_numeric_without_precision():
    assert _pg_column_type("numeric", None, None, None) == "numeric"


def test_ddl_format_default_bool_with_non_boolean_type():
    assert DDLGenerator._format_default(True, "INTEGER") == "TRUE"
    assert DDLGenerator._format_default(False, "INTEGER") == "FALSE"


def test_ddl_format_default_bool_value_with_boolean_mapped_type():
    assert DDLGenerator._format_default(True, "BOOLEAN") == "TRUE"
    assert DDLGenerator._format_default(False, "BOOLEAN") == "FALSE"


def test_ddl_format_default_numeric_value_types():
    assert DDLGenerator._format_default(5, "INTEGER") == "5"
    assert DDLGenerator._format_default(1.5, "FLOAT") == "1.5"


def test_ddl_format_default_current_timestamp_keyword():
    assert DDLGenerator._format_default("CURRENT_TIMESTAMP", "TIMESTAMP") == "CURRENT_TIMESTAMP"


def test_ddl_format_default_numeric_string():
    assert DDLGenerator._format_default("42", "VARCHAR(10)") == "42"


def test_ddl_format_default_string_literal_is_escaped():
    assert DDLGenerator._format_default("O'Brien", "VARCHAR(50)") == "'O''Brien'"


@mysql_skip
def test_data_transfer_target_has_data_false_for_missing_table():
    bootstrap = ConnectionManager()
    bootstrap.configure(**MYSQL_CONFIG)
    with bootstrap.connect() as conn:
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_source")
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_target")
    bootstrap.close()

    source = ConnectionManager()
    source.configure(database="testdb_source", **MYSQL_CONFIG)
    target = ConnectionManager()
    target.configure(database="testdb_target", **MYSQL_CONFIG)
    try:
        with target.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS dt_missing_table")
        transfer = DataTransfer(source, target)
        assert transfer.target_has_data("dt_missing_table") is False
    finally:
        source.close()
        target.close()


@mysql_skip
class TestVerifierAggregateMismatch:
    @pytest.fixture(autouse=True)
    def setup_dbs(self):
        bootstrap = ConnectionManager()
        bootstrap.configure(**MYSQL_CONFIG)
        with bootstrap.connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_source")
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_target")
        bootstrap.close()

        self.source = ConnectionManager()
        self.source.configure(database="testdb_source", **MYSQL_CONFIG)
        self.target = ConnectionManager()
        self.target.configure(database="testdb_target", **MYSQL_CONFIG)

        with self.source.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS v_mismatch")
            cur.execute("CREATE TABLE v_mismatch (id INT PRIMARY KEY) ENGINE=InnoDB;")
            cur.executemany("INSERT INTO v_mismatch (id) VALUES (%s)", [(1,), (2,), (3,)])
        with self.target.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS v_mismatch")
            cur.execute("CREATE TABLE v_mismatch (id INT PRIMARY KEY) ENGINE=InnoDB;")
            cur.execute("INSERT INTO v_mismatch (id) VALUES (1)")

        yield

        with self.source.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS v_mismatch")
        with self.target.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS v_mismatch")
        self.source.close()
        self.target.close()

    def test_verify_aggregate_warns_on_row_count_mismatch(self):
        verifier = Verifier(self.source, self.target)
        report = verifier.verify(["v_mismatch"])
        assert any("Row count mismatch" in w for w in report["warnings"])


@mysql_skip
class TestMigrationEngineRerun:
    @pytest.fixture(autouse=True)
    def setup_dbs(self):
        bootstrap = ConnectionManager()
        bootstrap.configure(**MYSQL_CONFIG)
        with bootstrap.connect() as conn:
            cur = conn.cursor()
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_source")
            cur.execute("CREATE DATABASE IF NOT EXISTS testdb_target")
        bootstrap.close()

        self.source = ConnectionManager()
        self.source.configure(**_source_engine_config())
        self.target = ConnectionManager()
        self.target.configure(**_target_engine_config())

        with self.source.connect() as conn:
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS migration_rerun_users")
            cur.execute("""
                CREATE TABLE migration_rerun_users (
                  id       INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  username VARCHAR(100) NOT NULL,
                  UNIQUE KEY uq_rerun_username (username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.executemany(
                "INSERT INTO migration_rerun_users (username) VALUES (%s)",
                [(f"user{i}",) for i in range(1, 4)],
            )
        with self.target.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS migration_rerun_users")

        yield

        with self.source.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS migration_rerun_users")
        with self.target.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS migration_rerun_users")
        self.source.close()
        self.target.close()

    def test_rerunning_migration_warns_instead_of_failing_on_duplicate_index(self):
        engine1 = MigrationEngine(
            source=_source_engine_config(), target=_target_engine_config()
        )
        first = engine1.run(tables=["migration_rerun_users"])
        assert first.is_success()

        engine2 = MigrationEngine(
            source=_source_engine_config(), target=_target_engine_config()
        )
        second = engine2.run(tables=["migration_rerun_users"], overwrite=True)

        assert second.is_success()
        assert any("Could not create index" in w for w in second.warnings)
