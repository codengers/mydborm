# -*- coding: utf-8 -*-
import os
import pytest
from typer.testing import CliRunner
from mydborm.cli import cli

runner = CliRunner()
DB_OPTS = ["--dialect","mysql","--host","127.0.0.1","--port","3307","--user","root","--password",os.environ.get("DB_PASSWORD","root"),"--database","testdb"]

def test_version_exits_zero():
    assert runner.invoke(cli, ["version"]).exit_code == 0

def test_version_shows_mydborm():
    assert "mydborm" in runner.invoke(cli, ["version"]).output.lower()

def test_version_shows_version_number():
    out = runner.invoke(cli, ["version"]).output
    assert "0.6.0" in out or "0.7.0" in out

def test_version_shows_license():
    assert "MIT" in runner.invoke(cli, ["version"]).output

def test_version_shows_supported_dbs():
    out = runner.invoke(cli, ["version"]).output.lower()
    assert "mysql" in out
    assert "yugabyte" in out

def test_ping_success():
    assert runner.invoke(cli, ["ping"] + DB_OPTS).exit_code == 0

def test_ping_shows_connected():
    assert "connected" in runner.invoke(cli, ["ping"] + DB_OPTS).output.lower()

def test_ping_shows_dialect():
    assert "mysql" in runner.invoke(cli, ["ping"] + DB_OPTS).output.lower()

def test_ping_shows_database():
    assert "testdb" in runner.invoke(cli, ["ping"] + DB_OPTS).output

def test_ping_bad_port_fails():
    result = runner.invoke(cli, ["ping","--dialect","mysql","--host","127.0.0.1","--port","9999","--user","root","--password","root","--database","testdb"])
    assert result.exit_code != 0

def test_tables_exits_zero():
    assert runner.invoke(cli, ["tables"] + DB_OPTS).exit_code == 0

def test_tables_shows_table():
    assert "table" in runner.invoke(cli, ["tables"] + DB_OPTS).output.lower()

def test_tables_bad_port_fails():
    result = runner.invoke(cli, ["tables","--dialect","mysql","--host","127.0.0.1","--port","9999","--user","root","--password","root","--database","testdb"])
    assert result.exit_code != 0

def test_inspect_exits_zero():
    assert runner.invoke(cli, ["inspect"] + DB_OPTS).exit_code == 0

def test_inspect_shows_database():
    assert "testdb" in runner.invoke(cli, ["inspect"] + DB_OPTS).output

def test_inspect_bad_port_fails():
    result = runner.invoke(cli, ["inspect","--dialect","mysql","--host","127.0.0.1","--port","9999","--user","root","--password","root","--database","testdb"])
    assert result.exit_code != 0

def test_migrate_status_exits_zero():
    assert runner.invoke(cli, ["migrate"] + DB_OPTS + ["--status"]).exit_code == 0

def test_migrate_no_model_shows_tip():
    out = runner.invoke(cli, ["migrate"] + DB_OPTS).output.lower()
    assert "tip" in out or "model" in out or "status" in out

def test_migrate_invalid_model_fails():
    result = runner.invoke(cli, ["migrate"] + DB_OPTS + ["--model","nonexistent.module.Model"])
    assert result.exit_code != 0

def test_pool_exits_zero():
    assert runner.invoke(cli, ["pool"] + DB_OPTS).exit_code == 0

def test_pool_shows_dialect():
    assert "mysql" in runner.invoke(cli, ["pool"] + DB_OPTS).output.lower()

def test_pool_shows_database():
    assert "testdb" in runner.invoke(cli, ["pool"] + DB_OPTS).output

def test_pool_shows_status():
    out = runner.invoke(cli, ["pool"] + DB_OPTS).output.lower()
    assert "alive" in out or "status" in out

def test_pool_custom_size():
    assert "10" in runner.invoke(cli, ["pool"] + DB_OPTS + ["--size","10"]).output

def test_help_exits_zero():
    assert runner.invoke(cli, ["--help"]).exit_code == 0

def test_help_shows_all_commands():
    out = runner.invoke(cli, ["--help"]).output
    for cmd in ["version","ping","tables","inspect","migrate","pool"]:
        assert cmd in out
