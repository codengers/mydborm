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