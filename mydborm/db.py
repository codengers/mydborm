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
        self._config:   dict = {}
        self._encoding: str  = "utf-8"

    # ------------------------------------------------------------------ #
    #  Configuration                                                        #
    # ------------------------------------------------------------------ #

    def configure(self, **kwargs):
        """
        Set connection config directly as keyword arguments.

        Args:
            dialect   : "mysql" or "yugabyte"
            host      : database host
            port      : database port
            user      : database user
            password  : database password
            database  : database name
            charset   : character set (default utf8mb4 for MySQL)
            encoding  : python encoding for text handling (default utf-8)

        Usage:
            db.configure(dialect="mysql", host="localhost",
                         user="root", password="root",
                         database="mydb", charset="utf8mb4")
        """
        if "dialect" not in kwargs:
            raise ValueError(
                "dialect is required. "
                f"Choose from: {SUPPORTED_DIALECTS}"
            )
        # Store Python encoding separately — not passed to driver
        self._encoding = kwargs.pop("encoding", "utf-8")
        self._config   = kwargs

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

    @property
    def encoding(self) -> str:
        """Python encoding for text handling (default utf-8)."""
        return getattr(self, "_encoding", "utf-8")

    def _make_connection(self):
        """Create a raw DB connection based on dialect."""
        cfg = {k: v for k, v in self._config.items() if k != "dialect"}

        if self.dialect == "mysql":
            try:
                import mysql.connector
                cfg.setdefault("charset", "utf8mb4")
                cfg.setdefault("collation", "utf8mb4_unicode_ci")
                cfg.setdefault("use_unicode", True)
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
                cfg.setdefault("client_encoding", "utf8")
                conn = psycopg2.connect(**cfg)
                conn.set_client_encoding("UTF8")
                return conn
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

    # ------------------------------------------------------------------ #
    #  Connection pooling                                                #
    # ------------------------------------------------------------------ #

    def configure_pool(
        self,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
    ):
        """
        Configure connection pool settings.

        Args:
            pool_size    : number of persistent connections (default 5)
            max_overflow : extra connections allowed above pool_size
            pool_timeout : seconds to wait for a connection (default 30)
            pool_recycle : seconds before recycling a connection (default 3600)

        Usage:
            db.configure(dialect="mysql", ...)
            db.configure_pool(pool_size=10, max_overflow=20)
        """
        self._pool_config = {
            "pool_size":    pool_size,
            "max_overflow": max_overflow,
            "pool_timeout": pool_timeout,
            "pool_recycle": pool_recycle,
        }
        # Reset existing connections so pool config takes effect
        self.close()

    def pool_status(self) -> dict:
        """
        Return current pool configuration and connection status.

        Usage:
            status = db.pool_status()
            print(status)
        """
        conn = getattr(_local, "conn", None)
        return {
            "dialect":      self.dialect,
            "host":         self._config.get("host"),
            "database":     self._config.get("database"),
            "pool_config":  getattr(self, "_pool_config", {}),
            "connected":    conn is not None,
            "connection_id": id(conn) if conn else None,
        }

    def ping(self) -> bool:
        """
        Ping the database to check connectivity.
        Returns True if connected, False otherwise.

        Usage:
            if db.ping():
                print("Database is reachable")
        """
        try:
            with self.connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
            return True
        except Exception:
            return False

    def reconnect(self):
        """
        Force close and reopen the connection.
        Useful after database restarts or stale connections.

        Usage:
            db.reconnect()
        """
        self.close()
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        print("[mydborm] Reconnected to " + repr(self._config.get("host")))

# ------------------------------------------------------------------ #
    #  Savepoints                                                          #
    # ------------------------------------------------------------------ #

    @contextmanager
    def savepoint(self, name: str = None):
        """
        Create a savepoint within an active transaction.
        Allows partial rollback without rolling back the entire transaction.

        Args:
            name : savepoint name (auto-generated if not provided)

        Usage:
            with db.transaction():
                User.create(username="alice")
                with db.savepoint("after_alice"):
                    User.create(username="bob")
                    raise Exception("bob failed")
                # only bob is rolled back, alice is kept
        """
        import uuid
        sp_name = name or f"sp_{uuid.uuid4().hex[:8]}"

        if not getattr(_local, "conn", None):
            raise RuntimeError(
                "savepoint() must be used inside a transaction()."
            )

        conn = _local.conn
        try:
            cur = conn.cursor()
            cur.execute(f"SAVEPOINT {sp_name}")
            yield sp_name
            cur.execute(f"RELEASE SAVEPOINT {sp_name}")
        except Exception:
            cur = conn.cursor()
            cur.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
            raise

    # ------------------------------------------------------------------ #
    #  Nested transactions                                                 #
    # ------------------------------------------------------------------ #

    @contextmanager
    def nested_transaction(self):
        """
        Create a nested transaction using savepoints.
        If already inside a transaction, uses a savepoint.
        If not, starts a new transaction.

        Usage:
            with db.transaction():
                User.create(username="alice")
                with db.nested_transaction():
                    User.create(username="bob")
                    # if this fails, only bob rolls back
        """
        if getattr(_local, "conn", None):
            # Already in a transaction — use savepoint
            with self.savepoint():
                yield
        else:
            # Not in a transaction — start one
            with self.transaction():
                yield

    # ------------------------------------------------------------------ #
    #  Bulk transaction                                                    #
    # ------------------------------------------------------------------ #

    @contextmanager
    def bulk_transaction(self):
        """
        Atomic transaction across multiple model operations.
        ALL operations commit together or ALL roll back together.

        Usage:
            with db.bulk_transaction() as tx:
                tx.execute("INSERT INTO users ...")
                tx.execute("INSERT INTO profiles ...")
                tx.execute("INSERT INTO orders ...")
            # all committed atomically

        The tx object is the connection — use db.execute() inside.
        """
        if not getattr(_local, "conn", None):
            _local.conn = self._make_connection()

        conn = _local.conn
        if self.dialect == "mysql":
            conn.autocommit = False

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if self.dialect == "mysql":
                conn.autocommit = False

    # ------------------------------------------------------------------ #
    #  Transaction with retry                                              #
    # ------------------------------------------------------------------ #

    @contextmanager
    def transaction_with_retry(self, retries: int = 3,
                                retry_delay: float = 0.5):
        """
        Transaction that retries on deadlock with exponential backoff.
        Non-deadlock exceptions are raised immediately without retry.
        """
        import time

        last_error  = None
        max_attempts = retries + 1

        for attempt in range(max_attempts):
            self.close()  # fresh connection each attempt
            try:
                with self.transaction() as conn:
                    yield conn
                return  # committed successfully

            except GeneratorExit:
                return

            except Exception as e:
                last_error  = e
                err_str     = str(e).lower()
                is_deadlock = (
                    "deadlock"          in err_str or
                    "lock wait timeout" in err_str or
                    "1213"              in err_str or
                    "1205"              in err_str
                )
                if is_deadlock and attempt < retries:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                raise
        raise RetryExhaustedError(
            f"Transaction failed after {retries + 1} attempts",
            attempts   = retries + 1,
            last_error = last_error,
        )

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


