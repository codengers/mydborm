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
import pytest
from typer.testing import CliRunner
from mydborm.cli import cli

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