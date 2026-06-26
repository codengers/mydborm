# =============================================================================
# File        : migrate.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Version     : 1.10.0
# License     : MIT
# Description : Database-to-database migration engine. Extracts schema +
#               data from a source database (MySQL, YugabyteDB, or
#               PostgreSQL) and replicates it into a target database of
#               any supported dialect — type mapping, DDL generation,
#               chunked data transfer, and post-migration verification.
# =============================================================================

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .bulk import _with_retry
from .db import ConnectionManager
from .dialects import get_dialect
from .exceptions import UnsupportedDialectError

PG_FAMILY = ("yugabyte", "postgres")


def _normalize_dialect(name: str) -> str:
    name = (name or "").lower()
    return "postgres" if name == "postgresql" else name


def _quote(identifier: str, dialect: str) -> str:
    dialect = _normalize_dialect(dialect)
    if dialect in PG_FAMILY:
        return f'"{identifier}"'
    return f"`{identifier}`"


# ------------------------------------------------------------------ #
#  Type string parsing                                                 #
# ------------------------------------------------------------------ #

_TYPE_RE = re.compile(
    r"^([a-zA-Z][a-zA-Z _]*?)\s*(?:\(([^)]*)\))?\s*(unsigned)?\s*$",
    re.IGNORECASE,
)

_PG_ALIASES = {
    "CHARACTER VARYING":          "VARCHAR",
    "CHARACTER":                  "CHAR",
    "TIMESTAMP WITHOUT TIME ZONE": "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE":   "TIMESTAMPTZ",
    "TIME WITHOUT TIME ZONE":     "TIME",
    "TIME WITH TIME ZONE":        "TIME",
    "REAL":                       "FLOAT",
    "INT4":                       "INTEGER",
    "INT8":                       "BIGINT",
    "INT2":                       "SMALLINT",
    "BOOL":                       "BOOLEAN",
    "SERIAL":                     "INTEGER",
    "BIGSERIAL":                  "BIGINT",
}


def _parse_sql_type(col_type: str):
    """Split a SQL type string into (BASE_NAME, [args], unsigned)."""
    s = (col_type or "").strip()
    m = _TYPE_RE.match(s)
    if not m:
        return s.upper(), [], False
    base = re.sub(r"\s+", " ", m.group(1).strip()).upper()
    args_str = m.group(2)
    args = [a.strip() for a in args_str.split(",")] if args_str else []
    unsigned = bool(m.group(3)) or "UNSIGNED" in s.upper()
    return base, args, unsigned


# ------------------------------------------------------------------ #
#  Stage 2 — TypeMapper                                                #
# ------------------------------------------------------------------ #

class TypeMapper:
    """
    Maps column type strings between MySQL and the PostgreSQL-family
    dialects (YugabyteDB / PostgreSQL).

    Usage:
        TypeMapper.mysql_to_yugabyte("varchar(100)")   # -> "VARCHAR(100)"
        TypeMapper.yugabyte_to_mysql("boolean")         # -> "TINYINT(1)"
        TypeMapper.map("int(11)", "mysql", "yugabyte")  # -> "INTEGER"
    """

    _MYSQL_KNOWN = {
        "INT", "INTEGER", "TINYINT", "SMALLINT", "MEDIUMINT", "BIGINT",
        "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "VARCHAR", "CHAR",
        "TEXT", "TINYTEXT", "MEDIUMTEXT", "LONGTEXT",
        "BLOB", "TINYBLOB", "MEDIUMBLOB", "LONGBLOB",
        "BINARY", "VARBINARY", "DATE", "DATETIME", "TIMESTAMP", "TIME",
        "JSON", "ENUM", "SET", "BIT",
    }

    _PG_KNOWN = {
        "INTEGER", "BOOLEAN", "SMALLINT", "BIGINT", "NUMERIC", "DECIMAL",
        "FLOAT", "DOUBLE PRECISION", "VARCHAR", "CHAR", "TEXT", "BYTEA",
        "DATE", "TIMESTAMP", "TIMESTAMPTZ", "TIME", "JSONB", "JSON",
    }

    # ------------------------------------------------------------------ #

    @staticmethod
    def mysql_to_yugabyte(col_type: str) -> str:
        """Map a MySQL column type string to its YugabyteDB/PostgreSQL equivalent."""
        base, args, unsigned = _parse_sql_type(col_type)

        if base in ("INT", "INTEGER", "MEDIUMINT"):
            return "INTEGER"
        if base == "TINYINT":
            return "BOOLEAN" if args and args[0] == "1" else "SMALLINT"
        if base == "SMALLINT":
            return "SMALLINT"
        if base == "BIGINT":
            return "NUMERIC(20)" if unsigned else "BIGINT"
        if base == "FLOAT":
            return "FLOAT"
        if base == "DOUBLE":
            return "DOUBLE PRECISION"
        if base in ("DECIMAL", "NUMERIC"):
            if len(args) == 2:
                return f"DECIMAL({args[0]},{args[1]})"
            if len(args) == 1:
                return f"DECIMAL({args[0]})"
            return "DECIMAL"
        if base == "VARCHAR":
            return f"VARCHAR({args[0]})" if args else "VARCHAR"
        if base == "CHAR":
            return f"CHAR({args[0]})" if args else "CHAR"
        if base in ("TEXT", "TINYTEXT", "MEDIUMTEXT", "LONGTEXT"):
            return "TEXT"
        if base in ("BLOB", "TINYBLOB", "MEDIUMBLOB", "LONGBLOB",
                    "BINARY", "VARBINARY"):
            return "BYTEA"
        if base == "DATE":
            return "DATE"
        if base == "DATETIME":
            return "TIMESTAMP"
        if base == "TIMESTAMP":
            return "TIMESTAMPTZ"
        if base == "TIME":
            return "TIME"
        if base == "JSON":
            return "JSONB"
        if base == "ENUM":
            return "VARCHAR(255)"
        if base == "SET":
            return "TEXT"
        if base == "BIT":
            return "BOOLEAN" if args and args[0] == "1" else "BYTEA"

        return "TEXT"

    @staticmethod
    def yugabyte_to_mysql(col_type: str) -> str:
        """Map a YugabyteDB/PostgreSQL column type string to its MySQL equivalent."""
        base, args, _ = _parse_sql_type(col_type)
        base = _PG_ALIASES.get(base, base)

        if base in ("INTEGER", "SERIAL"):
            return "INT"
        if base == "BOOLEAN":
            return "TINYINT(1)"
        if base == "SMALLINT":
            return "SMALLINT"
        if base == "BIGINT":
            return "BIGINT"
        if base in ("NUMERIC", "DECIMAL"):
            if len(args) >= 2:
                return f"DECIMAL({args[0]},{args[1]})"
            if len(args) == 1:
                return "BIGINT UNSIGNED" if int(args[0]) >= 20 else f"DECIMAL({args[0]})"
            return "DECIMAL"
        if base == "FLOAT":
            return "FLOAT"
        if base == "DOUBLE PRECISION":
            return "DOUBLE"
        if base == "VARCHAR":
            return f"VARCHAR({args[0]})" if args else "VARCHAR(255)"
        if base == "CHAR":
            return f"CHAR({args[0]})" if args else "CHAR(1)"
        if base == "TEXT":
            return "TEXT"
        if base == "BYTEA":
            return "BLOB"
        if base == "DATE":
            return "DATE"
        if base == "TIMESTAMP":
            return "DATETIME"
        if base == "TIMESTAMPTZ":
            return "DATETIME"
        if base == "TIME":
            return "TIME"
        if base in ("JSONB", "JSON"):
            return "JSON"

        return "TEXT"

    # ------------------------------------------------------------------ #

    @classmethod
    def map(cls, col_type: str, source_dialect: str, target_dialect: str) -> str:
        """
        Map a column type string from one dialect to another.
        Supported pairs: mysql<->yugabyte, mysql<->postgres,
        yugabyte<->postgres (identity — same type system).
        """
        source = _normalize_dialect(source_dialect)
        target = _normalize_dialect(target_dialect)

        if source == target:
            return col_type
        if source == "mysql" and target in PG_FAMILY:
            return cls.mysql_to_yugabyte(col_type)
        if source in PG_FAMILY and target == "mysql":
            return cls.yugabyte_to_mysql(col_type)
        if source in PG_FAMILY and target in PG_FAMILY:
            return col_type

        raise UnsupportedDialectError(
            f"No type mapping available from {source_dialect!r} to {target_dialect!r}",
            dialect=source_dialect,
        )

    @classmethod
    def is_known_type(cls, col_type: str, source_dialect: str) -> bool:
        """True if the source type is recognised (i.e. not falling back to TEXT)."""
        base, _, _ = _parse_sql_type(col_type)
        source = _normalize_dialect(source_dialect)
        if source == "mysql":
            return base in cls._MYSQL_KNOWN
        return _PG_ALIASES.get(base, base) in cls._PG_KNOWN


def _pg_column_type(data_type, char_len, num_precision, num_scale) -> str:
    """Build a canonical type string from PostgreSQL/YugabyteDB column metadata."""
    dt = (data_type or "").lower()
    if dt == "character varying":
        return f"character varying({char_len})" if char_len is not None else "character varying"
    if dt == "character":
        return f"character({char_len})" if char_len is not None else "character"
    if dt in ("numeric", "decimal"):
        if num_precision is None:
            return "numeric"
        if num_scale:
            return f"numeric({num_precision},{num_scale})"
        return f"numeric({num_precision})"
    return dt


# ------------------------------------------------------------------ #
#  Stage 1 — SchemaExtractor                                           #
# ------------------------------------------------------------------ #

class SchemaExtractor:
    """
    Reads live schema metadata — columns, primary keys, indexes, and
    foreign keys — from a configured ConnectionManager.

    Usage:
        extractor = SchemaExtractor(source_db)
        schema = extractor.extract_table("users")
        # {"table": "users", "columns": [...], "primary_key": [...],
        #  "indexes": [...], "foreign_keys": [...]}
    """

    def __init__(self, conn_manager: ConnectionManager):
        self.db = conn_manager

    @property
    def dialect(self) -> str:
        return _normalize_dialect(self.db.dialect)

    def list_tables(self) -> list:
        return self.db.list_tables()

    def extract_table(self, table: str) -> dict:
        if self.dialect == "mysql":
            return self._extract_mysql(table)
        return self._extract_postgres(table)

    def extract_schema(self, tables: Optional[list] = None) -> dict:
        names = tables if tables is not None else self.list_tables()
        return {name: self.extract_table(name) for name in names}

    # ---- MySQL ---- #

    def _extract_mysql(self, table: str) -> dict:
        columns_rows = self.db.fetchall(
            "SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, "
            "COLUMN_KEY "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION;",
            [table],
        )

        columns = []
        primary_key = []
        for row in columns_rows:
            is_pk = row["COLUMN_KEY"] == "PRI"
            if is_pk:
                primary_key.append(row["COLUMN_NAME"])
            columns.append({
                "name":           row["COLUMN_NAME"],
                "type":           row["COLUMN_TYPE"],
                "nullable":       row["IS_NULLABLE"] == "YES",
                "default":        row["COLUMN_DEFAULT"],
                "is_primary_key": is_pk,
            })

        idx_rows = self.db.fetchall(
            "SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE "
            "FROM INFORMATION_SCHEMA.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
            "ORDER BY INDEX_NAME, SEQ_IN_INDEX;",
            [table],
        )
        indexes = {}
        for r in idx_rows:
            name = r["INDEX_NAME"]
            if name == "PRIMARY":
                continue
            idx = indexes.setdefault(
                name, {"name": name, "columns": [], "unique": not bool(r["NON_UNIQUE"])}
            )
            idx["columns"].append(r["COLUMN_NAME"])

        fk_rows = self.db.fetchall(
            "SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
            "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
            "AND REFERENCED_TABLE_NAME IS NOT NULL;",
            [table],
        )
        foreign_keys = [
            {
                "column":     r["COLUMN_NAME"],
                "ref_table":  r["REFERENCED_TABLE_NAME"],
                "ref_column": r["REFERENCED_COLUMN_NAME"],
            }
            for r in fk_rows
        ]

        return {
            "table":        table,
            "columns":      columns,
            "primary_key":  primary_key,
            "indexes":      list(indexes.values()),
            "foreign_keys": foreign_keys,
        }

    # ---- PostgreSQL / YugabyteDB ---- #

    def _extract_postgres(self, table: str) -> dict:
        pk_rows = self.db.fetchall(
            "SELECT kcu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "  AND tc.table_schema = kcu.table_schema "
            "WHERE tc.constraint_type = 'PRIMARY KEY' "
            "AND tc.table_schema = 'public' AND tc.table_name = %s "
            "ORDER BY kcu.ordinal_position;",
            [table],
        )
        primary_key = [r["column_name"] for r in pk_rows]
        pk_set = set(primary_key)

        columns_rows = self.db.fetchall(
            "SELECT column_name, data_type, is_nullable, column_default, "
            "character_maximum_length, numeric_precision, numeric_scale "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position;",
            [table],
        )
        columns = []
        for row in columns_rows:
            col_type = _pg_column_type(
                row["data_type"], row["character_maximum_length"],
                row["numeric_precision"], row["numeric_scale"],
            )
            columns.append({
                "name":           row["column_name"],
                "type":           col_type,
                "nullable":       row["is_nullable"] == "YES",
                "default":        row["column_default"],
                "is_primary_key": row["column_name"] in pk_set,
            })

        idx_rows = self.db.fetchall(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename = %s;",
            [table],
        )
        indexes = []
        for r in idx_rows:
            indexdef = r["indexdef"]
            m = re.search(r"\(([^)]+)\)\s*$", indexdef)
            if not m:
                continue
            cols = [c.strip().strip('"') for c in m.group(1).split(",")]
            if set(cols) == pk_set:
                continue  # primary key index — already covered by PRIMARY KEY
            indexes.append({
                "name":    r["indexname"],
                "columns": cols,
                "unique":  "UNIQUE" in indexdef.upper(),
            })

        fk_rows = self.db.fetchall(
            "SELECT pg_get_constraintdef(c.oid) AS condef "
            "FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE c.contype = 'f' AND t.relname = %s;",
            [table],
        )
        foreign_keys = []
        for r in fk_rows:
            m = re.search(
                r"FOREIGN KEY \(([^)]+)\) REFERENCES (\S+)\(([^)]+)\)",
                r["condef"], re.IGNORECASE,
            )
            if not m:
                continue
            foreign_keys.append({
                "column":     m.group(1).strip().strip('"'),
                "ref_table":  m.group(2).split(".")[-1].strip('"'),
                "ref_column": m.group(3).strip().strip('"'),
            })

        return {
            "table":        table,
            "columns":      columns,
            "primary_key":  primary_key,
            "indexes":      indexes,
            "foreign_keys": foreign_keys,
        }


# ------------------------------------------------------------------ #
#  Stage 3 — DDLGenerator                                              #
# ------------------------------------------------------------------ #

class DDLGenerator:
    """
    Generates CREATE TABLE / CREATE INDEX SQL for a target dialect from
    an extracted table schema (as returned by SchemaExtractor), mapping
    column types via TypeMapper.

    Usage:
        ddl = DDLGenerator("mysql", "yugabyte")
        sql = ddl.generate(schema)
        # {"create_table": "...", "create_indexes": [...]}
        print(ddl.warnings)  # any unmapped-type fallbacks
    """

    def __init__(self, source_dialect: str, target_dialect: str):
        self.source_dialect = _normalize_dialect(source_dialect)
        self.target_dialect = _normalize_dialect(target_dialect)
        self.dialect_cls = get_dialect(self.target_dialect)
        self.warnings = []

    def column_definition(self, column: dict) -> str:
        mapped_type = TypeMapper.map(column["type"], self.source_dialect, self.target_dialect)
        if not TypeMapper.is_known_type(column["type"], self.source_dialect):
            self.warnings.append(
                f"No type mapping for column '{column['name']}' "
                f"({column['type']!r}) — using TEXT fallback"
            )

        parts = [_quote(column["name"], self.target_dialect), mapped_type]
        if not column.get("nullable", True):
            parts.append("NOT NULL")

        default = column.get("default")
        if default is not None and not column.get("is_primary_key"):
            parts.append(f"DEFAULT {self._format_default(default, mapped_type)}")

        return " ".join(parts)

    @staticmethod
    def _format_default(value, mapped_type: str = "") -> str:
        if mapped_type.upper() in ("BOOLEAN", "TINYINT(1)"):
            text = str(value).strip().upper()
            if isinstance(value, bool):
                return "TRUE" if value else "FALSE"
            if text in ("0", "FALSE", "F"):
                return "FALSE" if mapped_type.upper() == "BOOLEAN" else "0"
            if text in ("1", "TRUE", "T"):
                return "TRUE" if mapped_type.upper() == "BOOLEAN" else "1"

        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value)
        if text.upper() in ("CURRENT_TIMESTAMP", "NULL", "TRUE", "FALSE"):
            return text.upper()
        if re.match(r"^-?\d+(\.\d+)?$", text):
            return text
        escaped = text.replace("'", "''")
        return f"'{escaped}'"

    def create_table_sql(self, table_schema: dict, if_not_exists: bool = True) -> str:
        columns = table_schema["columns"]
        col_defs = [self.column_definition(c) for c in columns]

        pk_cols = table_schema.get("primary_key") or [
            c["name"] for c in columns if c.get("is_primary_key")
        ]
        if pk_cols:
            pk_list = ", ".join(_quote(c, self.target_dialect) for c in pk_cols)
            col_defs.append(f"PRIMARY KEY ({pk_list})")

        return self.dialect_cls.create_table_sql(
            table_schema["table"], col_defs, if_not_exists=if_not_exists
        )

    def create_index_sql(self, table: str, index: dict) -> str:
        unique = "UNIQUE " if index.get("unique") else ""
        cols = ", ".join(_quote(c, self.target_dialect) for c in index["columns"])

        # Postgres-family index names are unique per-schema (not per-table)
        # — namespace with the table name to avoid collisions across tables.
        idx_name = index["name"]
        if self.target_dialect in PG_FAMILY and not idx_name.startswith(f"{table}_"):
            idx_name = f"{table}_{idx_name}"[:63]

        if self.target_dialect == "mysql":
            return (
                f"CREATE {unique}INDEX {_quote(idx_name, self.target_dialect)} "
                f"ON {_quote(table, self.target_dialect)} ({cols});"
            )
        return (
            f"CREATE {unique}INDEX IF NOT EXISTS {_quote(idx_name, self.target_dialect)} "
            f"ON {_quote(table, self.target_dialect)} ({cols});"
        )

    def generate(self, table_schema: dict, if_not_exists: bool = True) -> dict:
        """Return {"create_table": sql, "create_indexes": [sql, ...]}."""
        create_table = self.create_table_sql(table_schema, if_not_exists=if_not_exists)

        pk_set = set(table_schema.get("primary_key") or [])
        create_indexes = []
        for idx in table_schema.get("indexes", []):
            if pk_set and set(idx["columns"]) == pk_set:
                continue  # already covered by the PRIMARY KEY clause
            create_indexes.append(self.create_index_sql(table_schema["table"], idx))

        return {"create_table": create_table, "create_indexes": create_indexes}


# ------------------------------------------------------------------ #
#  Stage 4 — DataTransfer                                              #
# ------------------------------------------------------------------ #

class DataTransfer:
    """
    Streams rows from a source table to a target table in fixed-size
    chunks, retrying transient failures and reporting progress.
    Never loads an entire table into memory.

    Usage:
        transfer = DataTransfer(source_db, target_db, chunk_size=500)
        stats = transfer.copy_table("users", columns, on_progress=cb)
        # {"rows_total": 1000, "rows_transferred": 1000}
    """

    def __init__(self, source_db: ConnectionManager, target_db: ConnectionManager,
                 chunk_size: int = 500, retries: int = 3, retry_delay: float = 0.5):
        self.source_db = source_db
        self.target_db = target_db
        self.chunk_size = chunk_size
        self.retries = retries
        self.retry_delay = retry_delay

    def count_rows(self, conn_manager: ConnectionManager, table: str) -> int:
        row = conn_manager.fetchone(
            f"SELECT COUNT(*) AS cnt FROM {_quote(table, conn_manager.dialect)};"
        )
        return row["cnt"] if row else 0

    def target_has_data(self, table: str) -> bool:
        try:
            return self.count_rows(self.target_db, table) > 0
        except Exception:
            return False

    @staticmethod
    def transform_row(row: dict, columns: list, target_dialect: str) -> tuple:
        """Coerce source values for the target dialect (e.g. MySQL
        TINYINT(1) bytes/int -> Python bool for a native BOOLEAN target)."""
        target_dialect = _normalize_dialect(target_dialect)
        values = []
        for col in columns:
            v = row.get(col["name"])
            src_type = (col.get("type") or "").lower()
            is_bool_source = src_type.startswith("tinyint(1)") or src_type == "bit(1)"

            if is_bool_source and target_dialect in PG_FAMILY:
                if isinstance(v, bytes):
                    v = bool(v[0]) if len(v) else False
                elif isinstance(v, int):
                    v = bool(v)

            values.append(v)
        return tuple(values)

    def copy_table(self, table: str, columns: list,
                    on_progress: Optional[Callable] = None) -> dict:
        """Copy every row of `table` from source_db to target_db in chunks."""
        total = self.count_rows(self.source_db, table)
        if total == 0:
            if on_progress:
                on_progress(table, 0, 0)
            return {"rows_total": 0, "rows_transferred": 0}

        col_names      = [c["name"] for c in columns]
        source_dialect = _normalize_dialect(self.source_db.dialect)
        target_dialect = _normalize_dialect(self.target_db.dialect)

        select_cols = ", ".join(_quote(c, source_dialect) for c in col_names)
        select_sql  = f"SELECT {select_cols} FROM {_quote(table, source_dialect)};"

        insert_cols  = ", ".join(_quote(c, target_dialect) for c in col_names)
        placeholders = ", ".join(["%s"] * len(col_names))
        insert_sql   = (
            f"INSERT INTO {_quote(table, target_dialect)} ({insert_cols}) "
            f"VALUES ({placeholders});"
        )

        transferred = 0
        with self.source_db.connect() as src_conn:
            src_cur = src_conn.cursor()
            src_cur.execute(select_sql)

            while True:
                rows = src_cur.fetchmany(self.chunk_size)
                if not rows:
                    break

                batch = [
                    self.transform_row(dict(zip(col_names, r)), columns, target_dialect)
                    for r in rows
                ]

                def do_insert(batch=batch):
                    with self.target_db.connect() as tgt_conn:
                        tgt_cur = tgt_conn.cursor()
                        tgt_cur.executemany(insert_sql, batch)

                _with_retry(do_insert, retries=self.retries, retry_delay=self.retry_delay)

                transferred += len(batch)
                if on_progress:
                    on_progress(table, transferred, total)

        return {"rows_total": total, "rows_transferred": transferred}


# ------------------------------------------------------------------ #
#  Stage 5 — Verifier                                                  #
# ------------------------------------------------------------------ #

class Verifier:
    """
    Post-migration verification: confirms every migrated table exists
    in the target with a matching row count.

    Usage:
        verifier = Verifier(source_db, target_db)
        report = verifier.verify(["users", "orders"])
        # {"results": [...], "warnings": [...]}
    """

    def __init__(self, source_db: ConnectionManager, target_db: ConnectionManager):
        self.source_db = source_db
        self.target_db = target_db

    def _count(self, conn_manager: ConnectionManager, table: str) -> int:
        row = conn_manager.fetchone(
            f"SELECT COUNT(*) AS cnt FROM {_quote(table, conn_manager.dialect)};"
        )
        return row["cnt"] if row else 0

    def verify_table(self, table: str) -> dict:
        source_rows  = self._count(self.source_db, table)
        target_exists = table in self.target_db.list_tables()
        target_rows  = self._count(self.target_db, table) if target_exists else 0
        return {
            "table":        table,
            "source_rows":  source_rows,
            "target_rows":  target_rows,
            "table_exists": target_exists,
            "match":        target_exists and source_rows == target_rows,
        }

    def verify(self, tables: list) -> dict:
        results  = [self.verify_table(t) for t in tables]
        warnings = []
        for r in results:
            if not r["table_exists"]:
                warnings.append(f"Table '{r['table']}' is missing in the target database")
            elif not r["match"]:
                warnings.append(
                    f"Row count mismatch for '{r['table']}': "
                    f"source={r['source_rows']} target={r['target_rows']}"
                )
        return {"results": results, "warnings": warnings}


# ------------------------------------------------------------------ #
#  MigrationResult                                                      #
# ------------------------------------------------------------------ #

@dataclass
class MigrationResult:
    """
    Outcome of a MigrationEngine.run() call.

    Usage:
        result = engine.run()
        print(result.summary())
        if not result.is_success():
            raise RuntimeError(result.summary())
    """
    tables_migrated:  int = 0
    tables_failed:    int = 0
    total_rows:       int = 0
    rows_transferred: int = 0
    duration:         float = 0.0
    errors:           list = field(default_factory=list)
    warnings:         list = field(default_factory=list)

    def is_success(self) -> bool:
        return self.tables_failed == 0 and not self.errors

    def summary(self) -> str:
        lines = [
            f"Status            : {'SUCCESS' if self.is_success() else 'FAILED'}",
            f"Tables migrated   : {self.tables_migrated}",
            f"Tables failed     : {self.tables_failed}",
            f"Total rows        : {self.total_rows}",
            f"Rows transferred  : {self.rows_transferred}",
            f"Duration          : {self.duration}s",
        ]
        if self.warnings:
            lines.append(f"Warnings          : {len(self.warnings)}")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.errors:
            lines.append(f"Errors            : {len(self.errors)}")
            for e in self.errors:
                lines.append(f"  - {e}")
        return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Stage 6 — MigrationEngine                                           #
# ------------------------------------------------------------------ #

class MigrationEngine:
    """
    Orchestrates a full database-to-database migration: schema
    extraction, type mapping, DDL generation, chunked data transfer,
    and post-migration verification.

    Usage:
        engine = MigrationEngine(
            source={"dialect": "mysql", "host": "127.0.0.1", "port": 3306,
                    "user": "root", "password": "root", "database": "shop"},
            target={"dialect": "yugabyte", "host": "127.0.0.1", "port": 5433,
                    "user": "yugabyte", "password": "yugabyte", "database": "shop"},
        )

        report = engine.dry_run()              # preview, no writes
        result = engine.run(chunk_size=500)     # perform the migration
        print(result.summary())
    """

    def __init__(self, source: dict, target: dict):
        self.source_config = dict(source)
        self.target_config = dict(target)

        self.source_db = ConnectionManager()
        self.source_db.configure(**self.source_config)
        self.target_db = ConnectionManager()
        self.target_db.configure(**self.target_config)

    def _close(self):
        try:
            self.source_db.close()
        finally:
            self.target_db.close()

    def dry_run(self, tables: Optional[list] = None) -> dict:
        """Preview the migration — extract schema and generate DDL only, no writes."""
        extractor = SchemaExtractor(self.source_db)
        ddl       = DDLGenerator(self.source_db.dialect, self.target_db.dialect)

        report = {"tables": [], "warnings": []}
        try:
            table_names = tables if tables is not None else extractor.list_tables()
            for name in table_names:
                schema    = extractor.extract_table(name)
                generated = ddl.generate(schema)
                row_count = self.source_db.fetchone(
                    f"SELECT COUNT(*) AS cnt FROM "
                    f"{_quote(name, self.source_db.dialect)};"
                )["cnt"]

                report["tables"].append({
                    "table":            name,
                    "rows":             row_count,
                    "columns":          len(schema["columns"]),
                    "create_table_sql": generated["create_table"],
                    "create_index_sql": generated["create_indexes"],
                })
            report["warnings"] = list(ddl.warnings)
        finally:
            self._close()

        return report

    def run(
        self,
        tables: Optional[list] = None,
        chunk_size: int = 500,
        overwrite: bool = False,
        on_progress: Optional[Callable] = None,
        verify: bool = True,
    ) -> MigrationResult:
        """Run the full migration: DDL + chunked data transfer + verification."""
        start  = time.time()
        result = MigrationResult()

        extractor = SchemaExtractor(self.source_db)
        ddl       = DDLGenerator(self.source_db.dialect, self.target_db.dialect)
        transfer  = DataTransfer(self.source_db, self.target_db, chunk_size=chunk_size)

        migrated_tables = []
        try:
            table_names = tables if tables is not None else extractor.list_tables()

            for name in table_names:
                try:
                    schema    = extractor.extract_table(name)
                    generated = ddl.generate(schema)

                    with self.target_db.connect() as conn:
                        conn.cursor().execute(generated["create_table"])

                    for index_sql in generated["create_indexes"]:
                        try:
                            with self.target_db.connect() as conn:
                                conn.cursor().execute(index_sql)
                        except Exception as e:
                            result.warnings.append(
                                f"Could not create index on '{name}': {e}"
                            )

                    if transfer.target_has_data(name):
                        if not overwrite:
                            result.warnings.append(
                                f"Skipped '{name}' — target already has data "
                                f"(pass overwrite=True to replace it)"
                            )
                            continue
                        with self.target_db.connect() as conn:
                            conn.cursor().execute(
                                f"DELETE FROM {_quote(name, self.target_db.dialect)};"
                            )

                    stats = transfer.copy_table(
                        name, schema["columns"], on_progress=on_progress
                    )
                    result.total_rows       += stats["rows_total"]
                    result.rows_transferred += stats["rows_transferred"]
                    result.tables_migrated  += 1
                    migrated_tables.append(name)

                except Exception as e:
                    result.tables_failed += 1
                    result.errors.append(f"{name}: {e}")

            result.warnings.extend(ddl.warnings)

            if verify and migrated_tables:
                verifier = Verifier(self.source_db, self.target_db)
                vr = verifier.verify(migrated_tables)
                result.warnings.extend(vr["warnings"])

        finally:
            self._close()

        result.duration = round(time.time() - start, 3)
        return result
