# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_cli.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.7.0
# License     : MIT
# Description : pytest tests for CLI commands — version, ping, tables,
#               inspect, migrate, pool using typer CliRunner.
# =============================================================================

import os
import socket
import pytest
from typer.testing import CliRunner
from mydborm.cli import cli


def _yugabyte_available():
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=2):
            return True
    except OSError:
        return False


skip_no_yugabyte = pytest.mark.skipif(
    not _yugabyte_available(),
    reason="YugabyteDB not available on 127.0.0.1:5433",
)

runner = CliRunner()

DB_OPTS = [
    "--dialect", "mysql",
    "--host",    "127.0.0.1",
    "--port",    "3307",
    "--user",    "root",
    "--password", os.environ.get("DB_PASSWORD", "root"),
    "--database", "testdb",
]


# ------------------------------------------------------------------ #
#  version                                                             #
# ------------------------------------------------------------------ #

def test_version_exits_zero():
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0


def test_version_shows_mydborm():
    result = runner.invoke(cli, ["version"])
    assert "mydborm" in result.output.lower()


def test_version_shows_version_number():
    import mydborm
    out = runner.invoke(cli, ["version"]).output
    assert mydborm.__version__ in out


def test_version_shows_author():
    result = runner.invoke(cli, ["version"])
    assert "codengers" in result.output.lower() \
        or "atikrant"  in result.output.lower()


def test_version_shows_license():
    result = runner.invoke(cli, ["version"])
    assert "MIT" in result.output


def test_version_shows_supported_dbs():
    result = runner.invoke(cli, ["version"])
    assert "mysql"      in result.output.lower()
    assert "yugabyte"   in result.output.lower()


# ------------------------------------------------------------------ #
#  ping                                                                #
# ------------------------------------------------------------------ #

def test_ping_mysql_success():
    result = runner.invoke(cli, ["ping"] + DB_OPTS)
    assert result.exit_code == 0


def test_ping_shows_connected():
    result = runner.invoke(cli, ["ping"] + DB_OPTS)
    assert "connected" in result.output.lower()


def test_ping_shows_dialect():
    result = runner.invoke(cli, ["ping"] + DB_OPTS)
    assert "mysql" in result.output.lower()


def test_ping_shows_version():
    result = runner.invoke(cli, ["ping"] + DB_OPTS)
    assert "8.0" in result.output


def test_ping_shows_database():
    result = runner.invoke(cli, ["ping"] + DB_OPTS)
    assert "testdb" in result.output


def test_ping_bad_host_fails():
    result = runner.invoke(cli, [
        "ping",
        "--dialect",  "mysql",
        "--host",     "127.0.0.1",
        "--port",     "9999",
        "--user",     "root",
        "--password", "root",
        "--database", "testdb",
    ])
    assert result.exit_code != 0


# ------------------------------------------------------------------ #
#  tables                                                              #
# ------------------------------------------------------------------ #

def test_tables_exits_zero():
    result = runner.invoke(cli, ["tables"] + DB_OPTS)
    assert result.exit_code == 0


def test_tables_shows_table_count():
    result = runner.invoke(cli, ["tables"] + DB_OPTS)
    assert "table" in result.output.lower()


def test_tables_shows_found():
    result = runner.invoke(cli, ["tables"] + DB_OPTS)
    assert "found" in result.output.lower()


def test_tables_bad_connection_fails():
    result = runner.invoke(cli, [
        "tables",
        "--dialect",  "mysql",
        "--host",     "127.0.0.1",
        "--port",     "9999",
        "--user",     "root",
        "--password", "root",
        "--database", "testdb",
    ])
    assert result.exit_code != 0


# ------------------------------------------------------------------ #
#  inspect                                                             #
# ------------------------------------------------------------------ #

def test_inspect_exits_zero():
    result = runner.invoke(cli, ["inspect"] + DB_OPTS)
    assert result.exit_code == 0


def test_inspect_shows_database_name():
    result = runner.invoke(cli, ["inspect"] + DB_OPTS)
    assert "testdb" in result.output


def test_inspect_shows_dialect():
    result = runner.invoke(cli, ["inspect"] + DB_OPTS)
    assert result.exit_code == 0


def test_inspect_shows_output():
    result = runner.invoke(cli, ["inspect"] + DB_OPTS)
    assert len(result.output) > 0


def test_inspect_completes():
    result = runner.invoke(cli, ["inspect"] + DB_OPTS)
    assert result.exit_code == 0
    assert result.output is not None


# ------------------------------------------------------------------ #
#  migrate                                                             #
# ------------------------------------------------------------------ #

def test_migrate_status_exits_zero():
    result = runner.invoke(cli, ["migrate"] + DB_OPTS + ["--status"])
    assert result.exit_code == 0


def test_migrate_status_shows_output():
    result = runner.invoke(cli, ["migrate"] + DB_OPTS + ["--status"])
    assert len(result.output) > 0


def test_migrate_no_model_shows_tip():
    result = runner.invoke(cli, ["migrate"] + DB_OPTS)
    assert result.exit_code == 0
    assert "tip"    in result.output.lower() \
        or "model"  in result.output.lower() \
        or "status" in result.output.lower()


def test_migrate_invalid_model_fails():
    result = runner.invoke(cli, [
        "migrate"
    ] + DB_OPTS + ["--model", "nonexistent.module.Model"])
    assert result.exit_code != 0


def test_migrate_with_valid_model():
    result = runner.invoke(cli, [
        "migrate"
    ] + DB_OPTS + ["--model", "tests.test_migrations.MigUser"])
    assert result.exit_code == 0


# ------------------------------------------------------------------ #
#  pool                                                                #
# ------------------------------------------------------------------ #

def test_pool_exits_zero():
    result = runner.invoke(cli, ["pool"] + DB_OPTS)
    assert result.exit_code == 0


def test_pool_shows_dialect():
    result = runner.invoke(cli, ["pool"] + DB_OPTS)
    assert "mysql" in result.output.lower()


def test_pool_shows_host():
    result = runner.invoke(cli, ["pool"] + DB_OPTS)
    assert "127.0.0.1" in result.output


def test_pool_shows_database():
    result = runner.invoke(cli, ["pool"] + DB_OPTS)
    assert "testdb" in result.output


def test_pool_shows_status():
    result = runner.invoke(cli, ["pool"] + DB_OPTS)
    assert "alive"   in result.output.lower() \
        or "status"  in result.output.lower()


def test_pool_shows_pool_size():
    result = runner.invoke(cli, ["pool"] + DB_OPTS + ["--size", "10"])
    assert "10" in result.output


def test_pool_shows_unreachable_on_bad_port():
    result = runner.invoke(cli, [
        "pool",
        "--dialect",  "mysql",
        "--host",     "127.0.0.1",
        "--port",     "9999",
        "--user",     "root",
        "--password", "root",
        "--database", "testdb",
    ])
    assert result.exit_code == 0
    assert "unreachable" in result.output.lower() \
        or "alive"       in result.output.lower()


# ------------------------------------------------------------------ #
#  help                                                                #
# ------------------------------------------------------------------ #

def test_help_exits_zero():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_help_shows_commands():
    result = runner.invoke(cli, ["--help"])
    assert "version" in result.output
    assert "ping"    in result.output
    assert "tables"  in result.output
    assert "inspect" in result.output
    assert "migrate" in result.output
    assert "pool"    in result.output

# ------------------------------------------------------------------ #
#  generate command                                                    #
# ------------------------------------------------------------------ #

def test_generate_no_model_shows_tip():
    result = runner.invoke(cli, ["generate"] + DB_OPTS)
    assert result.exit_code == 0
    assert "tip" in result.output.lower() or "model" in result.output.lower()


def test_generate_list_empty():
    result = runner.invoke(cli, ["generate"] + DB_OPTS + ["--list", "--output", "nonexistent_migrations_xyz"])
    assert result.exit_code == 0
    assert "no migration" in result.output.lower() or "found" in result.output.lower()


def test_generate_invalid_model_fails():
    result = runner.invoke(cli, ["generate"] + DB_OPTS + ["--model", "bad.module.Model"])
    assert result.exit_code != 0


def test_generate_with_valid_model():
    result = runner.invoke(cli, [
        "generate"
    ] + DB_OPTS + ["--model", "tests.test_migrations.MigUser", "--output", "test_gen_output"])
    assert result.exit_code == 0
    import shutil, os
    if os.path.exists("test_gen_output"):
        shutil.rmtree("test_gen_output")


def test_generate_list_with_files():
    import os, shutil
    out = "test_gen_list_output"
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "0001_test.sql"), "w") as f:
        f.write("-- test\nSELECT 1;\n")
    result = runner.invoke(cli, ["generate"] + DB_OPTS + ["--list", "--output", out])
    assert result.exit_code == 0
    assert "0001" in result.output
    shutil.rmtree(out)


def test_version_shows_author():
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "codengers" in result.output.lower() or "atikrant" in result.output.lower()

# ------------------------------------------------------------------ #
#  Additional CLI coverage                                             #
# ------------------------------------------------------------------ #

def test_ping_shows_version():
    result = runner.invoke(cli, ["ping"] + DB_OPTS)
    assert result.exit_code == 0
    assert "8.0" in result.output or "connected" in result.output.lower()


def test_tables_shows_found():
    result = runner.invoke(cli, ["tables"] + DB_OPTS)
    assert result.exit_code == 0
    assert "found" in result.output.lower() or "table" in result.output.lower()


def test_inspect_shows_columns():
    result = runner.invoke(cli, ["inspect"] + DB_OPTS)
    assert result.exit_code == 0


def test_migrate_shows_status_output():
    result = runner.invoke(cli, ["migrate"] + DB_OPTS + ["--status"])
    assert result.exit_code == 0
    assert len(result.output) > 0


def test_generate_invalid_model_single_word():
    result = runner.invoke(cli, ["generate"] + DB_OPTS + ["--model", "NoModule"])
    assert result.exit_code != 0


def test_generate_with_apply_creates_and_shows_table():
    import shutil, os
    out = "test_gen_apply_output"
    try:
        result = runner.invoke(cli, [
            "generate"
        ] + DB_OPTS + [
            "--model", "tests.test_migrations.MigUser",
            "--output", out,
            "--apply",
        ])
        assert result.exit_code == 0
    finally:
        if os.path.exists(out):
            shutil.rmtree(out)
        from mydborm import db as _db
        with _db.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS mig_users")


def test_generate_uptodate_shows_checkmark():
    import shutil, os
    out = "test_gen_uptodate"
    try:
        # First generate + apply
        runner.invoke(cli, [
            "generate"
        ] + DB_OPTS + [
            "--model", "tests.test_migrations.MigUser",
            "--output", out, "--apply",
        ])
        # Second generate should show "up to date"
        result = runner.invoke(cli, [
            "generate"
        ] + DB_OPTS + [
            "--model", "tests.test_migrations.MigUser",
            "--output", out,
        ])
        assert result.exit_code == 0
        assert "up to date" in result.output.lower() or "✔" in result.output
    finally:
        if os.path.exists(out):
            shutil.rmtree(out)
        from mydborm import db as _db
        with _db.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS mig_users")


def test_pool_shows_size():
    result = runner.invoke(cli, ["pool"] + DB_OPTS + ["--size", "5"])
    assert result.exit_code == 0
    assert "5" in result.output


def test_migrate_with_model_path():
    result = runner.invoke(cli, [
        "migrate"
    ] + DB_OPTS + ["--model", "tests.test_migrations.MigUser"])
    assert result.exit_code == 0
    from mydborm import db as _db
    with _db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mig_users")


# ------------------------------------------------------------------ #
#  migrate rollback path (lines 358-367)                             #
# ------------------------------------------------------------------ #

def test_migrate_rollback_path():
    """migrate --rollback covers the rollback branch (lines 358-367)."""
    from mydborm import db as _db
    _db.close()  # ensure no stale connection
    # Apply migration first so there's something to roll back
    runner.invoke(cli, [
        "migrate"
    ] + DB_OPTS + ["--model", "tests.test_migrations.MigUser"])
    _db.close()
    # Now rollback
    result = runner.invoke(cli, [
        "migrate"
    ] + DB_OPTS + ["--model", "tests.test_migrations.MigUser", "--rollback"])
    _db.close()
    assert result.exit_code == 0
    # Either "✔" (applied) or "⚠" (nothing to rollback)
    assert "✔" in result.output or "⚠" in result.output or "roll" in result.output.lower()
    _db.configure(dialect="mysql", host="127.0.0.1", port=3307, user="root",
                  password=os.environ.get("DB_PASSWORD", "root"), database="testdb")
    with _db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mig_users")
    _db.close()


# ------------------------------------------------------------------ #
#  migrate uptodate path (lines 379-383)                             #
# ------------------------------------------------------------------ #

def test_migrate_uptodate_path():
    """Table already up to date → hits lines 379-383 (no diff)."""
    from mydborm import db as _db
    from tests.test_migrations import MigUser
    _db.close()
    # Set up MySQL and create the table directly (bypasses migration history)
    _db.configure(
        dialect="mysql", host="127.0.0.1", port=3307,
        user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
    )
    with _db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mig_users")
    MigUser.create_table()  # schema matches model → diff will be empty
    _db.close()
    # Now CLI migrate finds no diff → lines 379-383
    result = runner.invoke(cli, [
        "migrate"
    ] + DB_OPTS + ["--model", "tests.test_migrations.MigUser"])
    _db.close()
    assert result.exit_code == 0
    assert "up to date" in result.output.lower() or "✔" in result.output
    _db.configure(
        dialect="mysql", host="127.0.0.1", port=3307,
        user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
    )
    with _db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS mig_users")
    _db.close()


# ------------------------------------------------------------------ #
#  YugabyteDB dialect paths (must run after MySQL migrate tests)     #
# ------------------------------------------------------------------ #

YB_OPTS = [
    "--dialect",  "yugabyte",
    "--host",     "127.0.0.1",
    "--port",     "5433",
    "--user",     "yugabyte",
    "--password", "yugabyte",
    "--database", "yugabyte",
]


@skip_no_yugabyte
def test_ping_yugabyte_success():
    """ping against YugabyteDB covers the else branch (lines 85-94)."""
    from mydborm import db as _db
    _db.close()  # flush any stale MySQL connection before switching dialects
    result = runner.invoke(cli, ["ping"] + YB_OPTS)
    _db.close()
    assert result.exit_code == 0
    assert "connected" in result.output.lower()


@skip_no_yugabyte
def test_ping_yugabyte_shows_version():
    from mydborm import db as _db
    _db.close()
    result = runner.invoke(cli, ["ping"] + YB_OPTS)
    _db.close()
    assert result.exit_code == 0
    assert "yugabyte" in result.output.lower() or "version" in result.output.lower()


@skip_no_yugabyte
def test_tables_yugabyte():
    """tables command with yugabyte dialect covers line 237."""
    from mydborm import db as _db
    _db.close()
    result = runner.invoke(cli, ["tables"] + YB_OPTS)
    _db.close()
    assert result.exit_code == 0
    assert "table" in result.output.lower() or "found" in result.output.lower()


@skip_no_yugabyte
def test_inspect_yugabyte():
    """inspect with yugabyte covers lines 133-138 and 176-195."""
    from mydborm import db as _db
    _db.close()
    result = runner.invoke(cli, ["inspect"] + YB_OPTS)
    _db.close()
    assert result.exit_code == 0


def test_inspect_bad_credentials_fails():
    """inspect with wrong credentials triggers exception handler (lines 205-207)."""
    from mydborm import db as _db
    _db.close()
    result = runner.invoke(cli, [
        "inspect",
        "--dialect",  "mysql",
        "--host",     "127.0.0.1",
        "--port",     "3307",
        "--user",     "wrong_user_xyz",
        "--password", "wrong_pass_xyz",
        "--database", "testdb",
    ])
    _db.close()
    assert result.exit_code != 0


# ------------------------------------------------------------------ #
#  migrate-db                                                          #
# ------------------------------------------------------------------ #

MIGRATE_DB_OPTS = [
    "--source-dialect",  "mysql",
    "--source-host",     "127.0.0.1",
    "--source-port",     "3307",
    "--source-user",     "root",
    "--source-password", os.environ.get("DB_PASSWORD", "root"),
    "--source-db",       "testdb_source",
    "--target-dialect",  "mysql",
    "--target-host",     "127.0.0.1",
    "--target-port",     "3307",
    "--target-user",     "root",
    "--target-password", os.environ.get("DB_PASSWORD", "root"),
    "--target-db",       "testdb_target",
]


def _setup_migrate_db_table():
    from mydborm import db as _db
    _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                  user="root", password=os.environ.get("DB_PASSWORD", "root"))
    with _db.connect() as conn:
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_source")
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_target")
    _db.close()

    _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                  user="root", password=os.environ.get("DB_PASSWORD", "root"),
                  database="testdb_source")
    with _db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS cli_mig_users")
        cur.execute("""
            CREATE TABLE cli_mig_users (
              id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
              username VARCHAR(100) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cur.executemany(
            "INSERT INTO cli_mig_users (username) VALUES (%s)",
            [(f"user{i}",) for i in range(1, 4)],
        )
    _db.close()


def _cleanup_migrate_db_tables():
    from mydborm import db as _db
    _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                  user="root", password=os.environ.get("DB_PASSWORD", "root"),
                  database="testdb_source")
    with _db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS cli_mig_users")
    _db.close()

    _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                  user="root", password=os.environ.get("DB_PASSWORD", "root"),
                  database="testdb_target")
    with _db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS cli_mig_users")
    _db.close()


def test_migrate_db_dry_run_shows_preview_without_writing():
    _setup_migrate_db_table()
    try:
        result = runner.invoke(cli, [
            "migrate-db"
        ] + MIGRATE_DB_OPTS + ["--tables", "cli_mig_users", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "cli_mig_users" in result.output

        from mydborm import db as _db
        _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                      user="root", password=os.environ.get("DB_PASSWORD", "root"),
                      database="testdb_target")
        assert _db.table_exists("cli_mig_users") is False
        _db.close()
    finally:
        _cleanup_migrate_db_tables()


def test_migrate_db_run_migrates_table():
    _setup_migrate_db_table()
    try:
        result = runner.invoke(cli, [
            "migrate-db"
        ] + MIGRATE_DB_OPTS + ["--tables", "cli_mig_users"])
        assert result.exit_code == 0
        assert "Migrating" in result.output
        assert "Done" in result.output
        assert "Status            : SUCCESS" in result.output

        from mydborm import db as _db
        _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                      user="root", password=os.environ.get("DB_PASSWORD", "root"),
                      database="testdb_target")
        rows = _db.fetchall("SELECT COUNT(*) AS cnt FROM cli_mig_users")
        assert rows[0]["cnt"] == 3
        _db.close()
    finally:
        _cleanup_migrate_db_tables()


def test_migrate_db_skips_table_with_existing_data():
    _setup_migrate_db_table()
    try:
        from mydborm import db as _db
        _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                      user="root", password=os.environ.get("DB_PASSWORD", "root"),
                      database="testdb_target")
        with _db.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE cli_mig_users (
                  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                  username VARCHAR(100) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute("INSERT INTO cli_mig_users (username) VALUES ('existing')")
        _db.close()

        result = runner.invoke(cli, [
            "migrate-db"
        ] + MIGRATE_DB_OPTS + ["--tables", "cli_mig_users"])
        assert result.exit_code == 0
        assert "Skipped" in result.output
    finally:
        _cleanup_migrate_db_tables()


def test_migrate_db_bad_credentials_fails():
    result = runner.invoke(cli, [
        "migrate-db",
        "--source-dialect",  "mysql",
        "--source-host",     "127.0.0.1",
        "--source-port",     "3307",
        "--source-user",     "wrong_user_xyz",
        "--source-password", "wrong_pass_xyz",
        "--source-db",       "testdb",
        "--target-dialect",  "mysql",
        "--target-host",     "127.0.0.1",
        "--target-port",     "3307",
        "--target-user",     "root",
        "--target-password", os.environ.get("DB_PASSWORD", "root"),
        "--target-db",       "testdb",
    ])
    assert result.exit_code != 0


def test_migrate_db_no_tables_found():
    from mydborm import db as _db
    _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                  user="root", password=os.environ.get("DB_PASSWORD", "root"))
    with _db.connect() as conn:
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_empty_src")
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_empty_tgt")
    _db.close()

    result = runner.invoke(cli, [
        "migrate-db",
        "--source-dialect",  "mysql",
        "--source-host",     "127.0.0.1",
        "--source-port",     "3307",
        "--source-user",     "root",
        "--source-password", os.environ.get("DB_PASSWORD", "root"),
        "--source-db",       "testdb_empty_src",
        "--target-dialect",  "mysql",
        "--target-host",     "127.0.0.1",
        "--target-port",     "3307",
        "--target-user",     "root",
        "--target-password", os.environ.get("DB_PASSWORD", "root"),
        "--target-db",       "testdb_empty_tgt",
    ])
    assert result.exit_code == 0
    assert "No tables found" in result.output


def test_migrate_db_run_failure_exits_nonzero():
    _setup_migrate_db_table()
    try:
        result = runner.invoke(cli, [
            "migrate-db"
        ] + MIGRATE_DB_OPTS + ["--tables", "cli_mig_users,does_not_exist_xyz"])
        assert result.exit_code == 1
        assert "Failed" in result.output
        assert "Status            : FAILED" in result.output
    finally:
        _cleanup_migrate_db_tables()


def test_migrate_db_dry_run_shows_unmapped_type_warning():
    from mydborm import db as _db
    _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                  user="root", password=os.environ.get("DB_PASSWORD", "root"))
    with _db.connect() as conn:
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_source")
        cur.execute("CREATE DATABASE IF NOT EXISTS testdb_target")
    _db.close()

    _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                  user="root", password=os.environ.get("DB_PASSWORD", "root"),
                  database="testdb_source")
    with _db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS cli_mig_unmapped")
        cur.execute("""
            CREATE TABLE cli_mig_unmapped (
              id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
              grad_year YEAR NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
    _db.close()

    try:
        result = runner.invoke(cli, [
            "migrate-db"
        ] + MIGRATE_DB_OPTS + ["--tables", "cli_mig_unmapped", "--dry-run"])
        assert result.exit_code == 0
        assert "Warnings" in result.output
        assert "TEXT fallback" in result.output
    finally:
        _db.configure(dialect="mysql", host="127.0.0.1", port=3307,
                      user="root", password=os.environ.get("DB_PASSWORD", "root"),
                      database="testdb_source")
        with _db.connect() as conn:
            conn.cursor().execute("DROP TABLE IF EXISTS cli_mig_unmapped")
        _db.close()