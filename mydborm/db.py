# =============================================================================
# File        : db.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Cross-platform connection manager. Supports MySQL and
#               YugabyteDB via PostgreSQL wire protocol (psycopg2).
#               Provides thread-safe connection pooling, context manager
#               support, and DATABASE_URL environment variable config.
# =============================================================================

# =============================================================================
# File        : db.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Cross-platform connection manager. Supports MySQL and
#               YugabyteDB via PostgreSQL wire protocol (psycopg2).
#               Provides thread-safe connection pooling, context manager
#               support, and DATABASE_URL environment variable config.
# =============================================================================
"""
db.py — Cross-platform connection manager for mydborm.
Supports MySQL and YugabyteDB (via PostgreSQL wire protocol).
"""

import os
import threading
from contextlib import contextmanager
from urllib.parse import urlparse

# Thread-local storage — one connection per thread
_local = threading.local()

SUPPORTED_DIALECTS = ("mysql", "yugabyte", "postgres")


def _parse_url(url: str) -> dict:
    """
    Parse a DATABASE_URL string into a config dict.

    Examples:
        mysql://root:root@localhost:3306/testdb
        yugabyte://yugabyte:yugabyte@localhost:5433/yugabyte
    """
    p = urlparse(url)
    scheme = p.scheme.lower()

    if "yugabyte" in scheme or "postgres" in scheme:
        dialect = "yugabyte"
    else:
        dialect = "mysql"

    return {
        "dialect":   dialect,
        "host":      p.hostname or "127.0.0.1",
        "port":      p.port or (5433 if dialect == "yugabyte" else 3306),
        "user":      p.username or "root",
        "password":  p.password or "",
        "database":  p.path.lstrip("/"),
    }


class ConnectionManager:
    """
    Central connection manager.

    Usage — direct config:
        db.configure(dialect="mysql", host="localhost",
                     user="root", password="root", database="testdb")

    Usage — from environment variable:
        os.environ["DATABASE_URL"] = "mysql://root:root@localhost:3306/testdb"
        db.from_env()

    Usage — as context manager:
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
    """

    def __init__(self):
        self._config: dict = {}

    # ------------------------------------------------------------------ #
    #  Configuration                                                        #
    # ------------------------------------------------------------------ #

    def configure(self, **kwargs):
        """Set connection config directly as keyword arguments."""
        if "dialect" not in kwargs:
            raise ValueError(
                "dialect is required. "
                f"Choose from: {SUPPORTED_DIALECTS}"
            )
        self._config = kwargs

    def from_env(self, var: str = "DATABASE_URL"):
        """
        Load config from an environment variable.
        Works on Windows, Linux, and macOS.
        """
        url = os.environ.get(var)
        if not url:
            raise EnvironmentError(
                f"Environment variable {var!r} is not set.\n"
                "Set it like:\n"
                "  Windows PowerShell : $env:DATABASE_URL='mysql://...'\n"
                "  Linux / macOS      : export DATABASE_URL='mysql://...'"
            )
        self._config = _parse_url(url)

    # ------------------------------------------------------------------ #
    #  Internal                                                             #
    # ------------------------------------------------------------------ #

    @property
    def dialect(self) -> str:
        return self._config.get("dialect", "mysql")

    def _make_connection(self):
        """Create a raw DB connection based on dialect."""
        cfg = {k: v for k, v in self._config.items() if k != "dialect"}

        if self.dialect == "mysql":
            try:
                import mysql.connector
                return mysql.connector.connect(**cfg)
            except ImportError:
                raise ImportError(
                    "mysql-connector-python is not installed.\n"
                    "Run: pip install mysql-connector-python"
                )

        elif self.dialect in ("yugabyte", "postgres"):
            try:
                import psycopg2
                cfg.setdefault("port", 5433)
                return psycopg2.connect(**cfg)
            except ImportError:
                raise ImportError(
                    "psycopg2 is not installed.\n"
                    "Run: pip install psycopg2-binary"
                )

        else:
            raise ValueError(
                f"Unsupported dialect: {self.dialect!r}. "
                f"Choose from: {SUPPORTED_DIALECTS}"
            )

    # ------------------------------------------------------------------ #
    #  Connection context manager                                           #
    # ------------------------------------------------------------------ #

    @contextmanager
    def connect(self):
        """
        Thread-safe connection with automatic commit / rollback.

        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO ...")
        # auto-committed here
        """
        if not self._config:
            raise RuntimeError(
                "Database not configured.\n"
                "Call db.configure(...) or db.from_env() first."
            )

        # Reuse existing thread-local connection
        if not getattr(_local, "conn", None):
            _local.conn = self._make_connection()

        conn = _local.conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self):
        """Close the current thread's connection."""
        conn = getattr(_local, "conn", None)
        if conn:
            try:
                conn.close()
            finally:
                _local.conn = None

    # ------------------------------------------------------------------ #
    #  Raw SQL                                                           #
    # ------------------------------------------------------------------ #

    def fetchall(self, sql: str, params: list = None) -> list:
        """
        Execute a raw SELECT and return list of dicts.

        Usage:
            rows = db.fetchall(
                "SELECT * FROM users WHERE active = %s", [True]
            )
        """
        if not self._config:
            raise RuntimeError(
                "Database not configured.\n"
                "Call db.configure(...) or db.from_env() first."
            )
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or [])
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def fetchone(self, sql: str, params: list = None) -> dict:
        """
        Execute a raw SELECT and return a single row dict or None.

        Usage:
            row = db.fetchone(
                "SELECT * FROM users WHERE email = %s",
                ["alice@example.com"]
            )
        """
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    def table_exists(self, table: str) -> bool:
        """
        Check if a table exists in the current database.

        Usage:
            if db.table_exists("users"):
                print("Table exists")
        """
        dialect = self.dialect
        if dialect == "mysql":
            rows = self.fetchall(
                "SELECT COUNT(*) as cnt FROM information_schema.tables "
                "WHERE table_schema = DATABASE() "
                "AND table_name = %s;",
                [table]
            )
        else:
            rows = self.fetchall(
                "SELECT COUNT(*) as cnt FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_name = %s;",
                [table]
            )
        return rows[0]["cnt"] > 0

    def list_tables(self) -> list:
        """
        Return list of all table names in the current database.

        Usage:
            tables = db.list_tables()
            print(tables)  # ['users', 'products', ...]
        """
        dialect = self.dialect
        if dialect == "mysql":
            rows = self.fetchall("SHOW TABLES;")
        else:
            rows = self.fetchall(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name;"
            )
        return [list(row.values())[0] for row in rows]

    # ------------------------------------------------------------------ #
    #  Transactions                                                        #
    # ------------------------------------------------------------------ #

    @contextmanager
    def transaction(self):
        """
        Explicit transaction context manager.
        All statements inside the block are committed together.
        Any exception triggers a full rollback.

        Usage:
            with db.transaction() as conn:
                db.execute("INSERT INTO users ...")
                db.execute("INSERT INTO profiles ...")
            # both committed or both rolled back
        """
        if not self._config:
            raise RuntimeError(
                "Database not configured.\n"
                "Call db.configure(...) or db.from_env() first."
            )

        if not getattr(_local, "conn", None):
            _local.conn = self._make_connection()

        conn = _local.conn

        # Disable auto-commit for explicit transaction
        if self.dialect == "mysql":
            conn.autocommit = False
        else:
            conn.autocommit = False

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if self.dialect != "mysql":
                conn.autocommit = True


    def execute(self, sql: str, params: list = None) -> int:
        """
        Execute a raw SQL statement (INSERT, UPDATE, DELETE, DDL).
        Returns number of affected rows.

        Usage:
            db.execute("UPDATE users SET active = %s WHERE id = %s", [False, 1])
        """
        if not self._config:
            raise RuntimeError(
                "Database not configured.\n"
                "Call db.configure(...) or db.from_env() first."
            )
        if getattr(_local, "conn", None):
            cur = _local.conn.cursor()
            cur.execute(sql, params or [])
            return cur.rowcount
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or [])
            return cur.rowcount
    def __repr__(self):
        if not self._config:
            return "<ConnectionManager: not configured>"
        return (
            f"<ConnectionManager: dialect={self.dialect!r} "
            f"host={self._config.get('host')!r} "
            f"database={self._config.get('database')!r}>"
        )


# Global singleton — import and use anywhere
db = ConnectionManager()


