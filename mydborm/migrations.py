# =============================================================================
# File        : migrations.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Schema migration engine. Compares live database schema
#               against model definitions and generates ALTER TABLE
#               statements. Tracks applied migrations in _mydborm_migrations
#               table. Supports migrate up, rollback, and status inspect.
# =============================================================================

import hashlib
import json
from datetime import datetime
from typing import Optional

from .db import db
from .fields import Field


# ------------------------------------------------------------------ #
#  Migration tracking table                                            #
# ------------------------------------------------------------------ #

MIGRATIONS_TABLE = "_mydborm_migrations"

CREATE_MIGRATIONS_TABLE_MYSQL = f"""
CREATE TABLE IF NOT EXISTS `{MIGRATIONS_TABLE}` (
  id          INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  version     VARCHAR(64)  NOT NULL UNIQUE,
  description VARCHAR(255) NOT NULL,
  checksum    VARCHAR(64)  NOT NULL,
  applied_at  DATETIME     NOT NULL,
  rolled_back TINYINT(1)   DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

CREATE_MIGRATIONS_TABLE_YSQL = f"""
CREATE TABLE IF NOT EXISTS "{MIGRATIONS_TABLE}" (
  id          SERIAL PRIMARY KEY,
  version     VARCHAR(64)  NOT NULL UNIQUE,
  description VARCHAR(255) NOT NULL,
  checksum    VARCHAR(64)  NOT NULL,
  applied_at  TIMESTAMP    NOT NULL,
  rolled_back BOOLEAN      DEFAULT FALSE
);
"""


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def _checksum(sql: str) -> str:
    """SHA-256 checksum of a SQL string for integrity tracking."""
    return hashlib.sha256(sql.encode()).hexdigest()[:16]


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _get_dialect() -> str:
    return db.dialect


def _ensure_migrations_table():
    """Create the migrations tracking table if it doesn't exist."""
    dialect = _get_dialect()
    sql = (
        CREATE_MIGRATIONS_TABLE_MYSQL
        if dialect == "mysql"
        else CREATE_MIGRATIONS_TABLE_YSQL
    )
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute(sql)


# ------------------------------------------------------------------ #
#  Live schema inspection                                              #
# ------------------------------------------------------------------ #

def get_live_schema(table: str) -> dict:
    """
    Return the live column definitions for a table as a dict.

    Returns:
        {
          "column_name": {
              "type": "varchar(100)",
              "nullable": "YES",
              "key": "PRI",
              "default": None
          }, ...
        }
    Returns {} if table does not exist.
    """
    dialect = _get_dialect()
    schema = {}

    with db.connect() as conn:
        cur = conn.cursor()

        if dialect == "mysql":
            try:
                cur.execute(f"DESCRIBE `{table}`;")
                for row in cur.fetchall():
                    schema[row[0]] = {
                        "type":     row[1],
                        "nullable": row[2],
                        "key":      row[3],
                        "default":  row[4],
                    }
            except Exception:
                return {}

        else:
            cur.execute(f"""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = '{table}'
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """)
            rows = cur.fetchall()
            if not rows:
                return {}
            for row in rows:
                schema[row[0]] = {
                    "type":     row[1],
                    "nullable": row[2],
                    "default":  row[3],
                }

    return schema


def table_exists(table: str) -> bool:
    """Check if a table exists in the live database."""
    dialect = _get_dialect()
    with db.connect() as conn:
        cur = conn.cursor()
        if dialect == "mysql":
            cur.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name = '{table}';
            """)
        else:
            cur.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = '{table}';
            """)
        return cur.fetchone()[0] > 0


# ------------------------------------------------------------------ #
#  Schema differ                                                       #
# ------------------------------------------------------------------ #

def diff_schema(model_class) -> dict:
    """
    Compare model field definitions against the live DB schema.

    Returns a diff dict:
    {
        "table"      : "users",
        "new_table"  : True | False,
        "add_columns": {"col": "VARCHAR(100) NOT NULL", ...},
        "drop_columns": ["old_col", ...],
        "unchanged"  : ["id", "username", ...]
    }
    """
    table  = model_class._table
    fields = model_class._fields
    live   = get_live_schema(table)

    diff = {
        "table":       table,
        "new_table":   not table_exists(table),
        "add_columns": {},
        "drop_columns": [],
        "unchanged":   [],
    }

    if diff["new_table"]:
        # All columns are new
        for fname, field in fields.items():
            diff["add_columns"][fname] = field.to_sql_def()
        return diff

    live_cols  = set(live.keys())
    model_cols = set(fields.keys())

    # Columns in model but not in DB → add
    for col in model_cols - live_cols:
        diff["add_columns"][col] = fields[col].to_sql_def()

    # Columns in DB but not in model → drop
    diff["drop_columns"] = list(live_cols - model_cols)

    # Columns in both → unchanged
    diff["unchanged"] = list(live_cols & model_cols)

    return diff


# ------------------------------------------------------------------ #
#  SQL generators                                                      #
# ------------------------------------------------------------------ #

def generate_migration_sql(model_class) -> list[str]:
    """
    Generate a list of SQL statements to migrate a model.

    If table is new  → CREATE TABLE
    If table exists  → ALTER TABLE ADD/DROP COLUMN
    """
    diff    = diff_schema(model_class)
    table   = diff["table"]
    dialect = _get_dialect()
    sqls    = []

    if diff["new_table"]:
        col_defs = []
        for fname, field in model_class._fields.items():
            col_defs.append(f"  {fname} {field.to_sql_def()}")
        col_block = ",\n".join(col_defs)

        if dialect == "mysql":
            sqls.append(
                f"CREATE TABLE IF NOT EXISTS `{table}` (\n"
                f"{col_block}\n"
                f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
            )
        else:
            sqls.append(
                f'CREATE TABLE IF NOT EXISTS "{table}" (\n'
                f"{col_block}\n);"
            )
        return sqls

    # ADD columns
    for col, definition in diff["add_columns"].items():
        if dialect == "mysql":
            sqls.append(
                f"ALTER TABLE `{table}` ADD COLUMN `{col}` {definition};"
            )
        else:
            sqls.append(
                f'ALTER TABLE "{table}" ADD COLUMN "{col}" {definition};'
            )

    # DROP columns
    for col in diff["drop_columns"]:
        if dialect == "mysql":
            sqls.append(
                f"ALTER TABLE `{table}` DROP COLUMN `{col}`;"
            )
        else:
            sqls.append(
                f'ALTER TABLE "{table}" DROP COLUMN "{col}";'
            )

    return sqls


# ------------------------------------------------------------------ #
#  Apply migrations                                                    #
# ------------------------------------------------------------------ #

def migrate(model_class, description: str = "") -> dict:
    """
    Apply migrations for a model class.

    Returns a result dict:
    {
        "table"    : "users",
        "sqls"     : [...],
        "applied"  : True | False,
        "message"  : "...",
    }
    """
    _ensure_migrations_table()

    table   = model_class._table
    sqls    = generate_migration_sql(model_class)
    version = _checksum("".join(sqls) + table)

    if not sqls:
        return {
            "table":   table,
            "sqls":    [],
            "applied": False,
            "message": f"Table '{table}' is already up to date.",
        }

    # Check if already applied
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id FROM `{MIGRATIONS_TABLE}` "
            f"WHERE version = %s AND rolled_back = 0;",
            [version]
        )
        if cur.fetchone():
            return {
                "table":   table,
                "sqls":    sqls,
                "applied": False,
                "message": f"Migration for '{table}' already applied.",
            }

    # Apply each SQL statement
    with db.connect() as conn:
        cur = conn.cursor()
        for sql in sqls:
            cur.execute(sql)

        # Record migration
        cur.execute(
            f"INSERT INTO `{MIGRATIONS_TABLE}` "
            f"(version, description, checksum, applied_at) "
            f"VALUES (%s, %s, %s, %s);",
            [
                version,
                description or f"Auto-migration for {table}",
                _checksum("".join(sqls)),
                _now(),
            ]
        )

    return {
        "table":   table,
        "sqls":    sqls,
        "applied": True,
        "message": f"Migration applied for '{table}': "
                   f"{len(sqls)} statement(s).",
    }


# ------------------------------------------------------------------ #
#  Status                                                              #
# ------------------------------------------------------------------ #

def migration_status() -> list[dict]:
    """
    Return all applied migrations from the tracking table.

    Returns list of dicts with keys:
        id, version, description, checksum, applied_at, rolled_back
    """
    _ensure_migrations_table()

    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, version, description, checksum, "
            f"applied_at, rolled_back "
            f"FROM `{MIGRATIONS_TABLE}` "
            f"ORDER BY id ASC;"
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ------------------------------------------------------------------ #
#  Rollback                                                            #
# ------------------------------------------------------------------ #

def rollback(model_class) -> dict:
    """
    Roll back the last migration for a model by dropping its table.
    Marks the migration as rolled_back in the tracking table.

    Use with caution — this drops the table and all its data.
    """
    _ensure_migrations_table()

    table   = model_class._table
    dialect = _get_dialect()

    if not table_exists(table):
        return {
            "table":    table,
            "applied":  False,
            "message":  f"Table '{table}' does not exist.",
        }

    with db.connect() as conn:
        cur = conn.cursor()

        # Drop the table
        if dialect == "mysql":
            cur.execute(f"DROP TABLE IF EXISTS `{table}`;")
        else:
            cur.execute(f'DROP TABLE IF EXISTS "{table}";')

        # Mark as rolled back
        cur.execute(
            f"UPDATE `{MIGRATIONS_TABLE}` SET rolled_back = 1 "
            f"WHERE version IN ("
            f"  SELECT version FROM ("
            f"    SELECT version FROM `{MIGRATIONS_TABLE}` "
            f"    WHERE description LIKE %s "
            f"    AND rolled_back = 0 "
            f"    ORDER BY id DESC LIMIT 1"
            f"  ) AS sub"
            f");",
            [f"%{table}%"]
        )

    return {
        "table":   table,
        "applied": True,
        "message": f"Rolled back '{table}' — table dropped.",
    }

# ------------------------------------------------------------------ #
#  Auto-migration file generation                                      #
# ------------------------------------------------------------------ #

import os as _os
import datetime as _datetime


def generate(
    model_class,
    output_dir: str = "migrations",
    description: str = "",
    apply: bool = False,
) -> dict:
    """
    Generate a versioned SQL migration file from model diff.

    Compares model definition against live DB schema and writes
    a numbered SQL file to output_dir.

    Args:
        model_class : BaseModel subclass to generate migration for
        output_dir  : directory to write migration files (default "migrations")
        description : optional description for the migration
        apply       : if True, also apply the migration immediately

    Returns:
        {
            "file"       : path to generated file (or None if up to date),
            "version"    : migration version string,
            "sqls"       : list of SQL statements,
            "applied"    : True if migration was applied,
            "message"    : status message,
        }

    Usage:
        from mydborm.migrations import generate

        result = generate(User, output_dir="migrations/")
        print(result["file"])
        # migrations/0001_create_users.sql
    """
    sqls = generate_migration_sql(model_class)

    if not sqls:
        return {
            "file"    : None,
            "version" : "",
            "sqls"    : [],
            "applied" : False,
            "message" : f"Table '{model_class._table}' is up to date — no migration needed.",
        }

    # Ensure output directory exists
    _os.makedirs(output_dir, exist_ok=True)

    # Determine next version number
    existing = sorted([
        f for f in _os.listdir(output_dir)
        if f.endswith(".sql")
    ])
    next_num = len(existing) + 1
    version  = f"{next_num:04d}"

    # Build filename
    table_name  = model_class._table
    desc_slug   = description.lower().replace(" ", "_") if description else table_name
    filename    = f"{version}_{desc_slug}.sql"
    filepath    = _os.path.join(output_dir, filename)

    # Build file content
    timestamp = _datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines     = [
        f"-- mydborm auto-generated migration",
        f"-- version    : {version}",
        f"-- table      : {table_name}",
        f"-- generated  : {timestamp}",
        f"-- description: {description or table_name}",
        "",
    ]
    for sql in sqls:
        lines.append(sql)
        lines.append("")

    content = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[mydborm] Migration file created: {filepath}")

    # Optionally apply
    applied = False
    if apply:
        apply_result = apply_migration_file(filepath)
        applied      = apply_result["applied"]

    return {
        "file"    : filepath,
        "version" : version,
        "sqls"    : sqls,
        "applied" : applied,
        "message" : f"Migration file created: {filepath}",
    }


def apply_migration_file(filepath: str) -> dict:
    """
    Apply a SQL migration file to the database.

    Args:
        filepath : path to .sql migration file

    Returns:
        {
            "file"     : filepath,
            "applied"  : True if successful,
            "sqls"     : list of SQL statements applied,
            "message"  : status message,
        }

    Usage:
        result = apply_migration_file("migrations/0001_create_users.sql")
    """
    from .db import db

    if not _os.path.exists(filepath):
        return {
            "file"    : filepath,
            "applied" : False,
            "sqls"    : [],
            "message" : f"File not found: {filepath}",
        }

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract SQL statements (skip comment lines)
    # Extract SQL statements — join multi-line statements, skip comments
    sqls     = []
    current  = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("--"):
            continue
        current.append(line)
        if line.endswith(";"):
            sqls.append(" ".join(current))
            current = []
    if current:
        sqls.append(" ".join(current))

    applied_sqls = []
    with db.connect() as conn:
        cur = conn.cursor()
        for sql in sqls:
            if sql:
                cur.execute(sql)
                applied_sqls.append(sql)

    print(f"[mydborm] Applied migration: {filepath}")

    return {
        "file"    : filepath,
        "applied" : True,
        "sqls"    : applied_sqls,
        "message" : f"Applied {len(applied_sqls)} statement(s) from {filepath}",
    }


def list_migration_files(output_dir: str = "migrations") -> list:
    """
    List all migration files in the output directory.

    Args:
        output_dir : directory containing .sql files

    Returns:
        list of dicts with file, version, name

    Usage:
        files = list_migration_files("migrations/")
        for f in files:
            print(f["version"], f["name"])
    """
    if not _os.path.exists(output_dir):
        return []

    files = []
    for fname in sorted(_os.listdir(output_dir)):
        if fname.endswith(".sql"):
            parts   = fname.split("_", 1)
            version = parts[0] if len(parts) > 1 else ""
            name    = parts[1].replace(".sql", "") if len(parts) > 1 else fname
            files.append({
                "file"    : _os.path.join(output_dir, fname),
                "version" : version,
                "name"    : name,
                "filename": fname,
            })

    return files


