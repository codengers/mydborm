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

import hashlib
import logging
import os
import re
import threading
import time
from contextlib import contextmanager
from urllib.parse import urlparse

from .exceptions import (
    NotConfiguredError, UnsupportedDialectError, SavepointError, RetryExhaustedError,
)

SUPPORTED_DIALECTS = ("mysql", "yugabyte", "postgres", "postgresql", "sqlite")

# Local copy of model.py's identifier pattern — can't import it directly
# (model.py imports `db` from this module, so the reverse import would be
# circular). Used to validate procedure names before interpolating them
# into CALL statements, which can't be parameterized like values can.
_PROC_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def _parse_url(url: str) -> dict:
    """
    Parse a DATABASE_URL string into a config dict.

    Examples:
        mysql://root:root@localhost:3306/testdb
        yugabyte://yugabyte:yugabyte@localhost:5433/yugabyte
        sqlite:///path/to/app.db
        sqlite:///:memory:
    """
    p = urlparse(url)
    scheme = p.scheme.lower()

    if "sqlite" in scheme:
        # sqlite has no host/port/user/password — the URL path is the
        # database file path (or ":memory:")
        return {
            "dialect":  "sqlite",
            "database": p.path.lstrip("/") or ":memory:",
        }

    if "yugabyte" in scheme:
        dialect = "yugabyte"
    elif "postgresql" in scheme or "postgres" in scheme:
        dialect = "postgres"
    else:
        dialect = "mysql"

    return {
        "dialect":   dialect,
        "host":      p.hostname or "127.0.0.1",
        "port":      p.port or (5433 if dialect == "yugabyte" else
                                5432 if dialect == "postgres" else 3306),
        "user":      p.username or "root",
        "password":  p.password or "",
        "database":  p.path.lstrip("/"),
    }


class _SQLiteCursorAdapter:
    """
    Wraps a stdlib sqlite3.Cursor, translating mydborm's "%s" placeholders
    (shared with mysql-connector/psycopg2 paramstyle) to sqlite3's "?"
    (qmark) paramstyle. Every other attribute (description, rowcount,
    lastrowid, fetchall, fetchone, close) passes through untouched.
    """
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=None):
        return self._raw.execute(sql.replace("%s", "?"), params or [])

    def executemany(self, sql, seq_of_params):
        return self._raw.executemany(sql.replace("%s", "?"), seq_of_params)

    def __getattr__(self, name):
        return getattr(self._raw, name)


class _SQLiteConnectionAdapter:
    """
    Wraps a stdlib sqlite3.Connection so the rest of mydborm — written
    against mysql-connector/psycopg2 style connections — can use it
    unmodified. Handles two divergences from those drivers:

    1. Placeholder style ("%s" vs "?") — via _SQLiteCursorAdapter.
    2. No settable `.autocommit` attribute pre-3.12 — mapped onto
       sqlite3's `isolation_level` (None = autocommit, "" = manual
       transaction), matching the semantics the rest of db.py expects.
    """
    def __init__(self, raw):
        self._raw = raw

    def cursor(self):
        return _SQLiteCursorAdapter(self._raw.cursor())

    @property
    def autocommit(self):
        return self._raw.isolation_level is None

    @autocommit.setter
    def autocommit(self, value):
        self._raw.isolation_level = None if value else ""

    def __getattr__(self, name):
        return getattr(self._raw, name)


_SQL_LOGGER = logging.getLogger("mydborm.sql")

# Cap on ConnectionManager.queries — bounds memory for long-running
# processes that leave echo=True on, matching Django's connection.queries
# in spirit but without unbounded growth.
_MAX_TRACKED_QUERIES = 1000


class _QueryLogCursor:
    """
    Wraps any cursor (mysql-connector, psycopg2, or the sqlite adapter
    above) to time and log each execute()/executemany() call. Sits
    *outside* the sqlite %s->? translation layer, so the SQL text logged
    here is always the original "%s"-style string, consistent across
    every dialect.
    """
    def __init__(self, raw, manager):
        self._raw = raw
        self._manager = manager

    def _record(self, sql, params, duration_ms):
        _SQL_LOGGER.debug("%s | params=%r | %.2fms", sql, params, duration_ms)
        queries = self._manager.queries
        queries.append({"sql": sql, "params": params, "duration_ms": duration_ms})
        del queries[:-_MAX_TRACKED_QUERIES]

    def execute(self, sql, params=None):
        start = time.perf_counter()
        try:
            return self._raw.execute(sql, params or [])
        finally:
            self._record(sql, params, (time.perf_counter() - start) * 1000)

    def executemany(self, sql, seq_of_params):
        start = time.perf_counter()
        try:
            return self._raw.executemany(sql, seq_of_params)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            rows = len(seq_of_params) if hasattr(seq_of_params, "__len__") else "?"
            self._record(sql, f"<{rows} rows>", duration_ms)

    def __getattr__(self, name):
        return getattr(self._raw, name)


class _QueryLogConnection:
    """Wraps a connection so every cursor it hands out is a _QueryLogCursor."""
    def __init__(self, raw, manager):
        self._raw = raw
        self._manager = manager

    def cursor(self):
        return _QueryLogCursor(self._raw.cursor(), self._manager)

    def __getattr__(self, name):
        return getattr(self._raw, name)


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
        self._log_queries: bool = False
        self.queries: list = []
        # Per-instance thread-local connection storage — lets multiple
        # ConnectionManager instances (e.g. migration source + target)
        # hold independent connections within the same thread.
        self._local = threading.local()
        # Connection pooling — see configure_pool(). _pool_config is only
        # set once configure_pool() is called; _pg_pool is the lazily
        # created psycopg2 pool for the postgres/yugabyte dialects.
        self._pool_config = None
        self._pg_pool = None
        self._mysql_pool_name_cache = None

    # ------------------------------------------------------------------ #
    #  Configuration                                                        #
    # ------------------------------------------------------------------ #

    def configure(self, **kwargs):
        """
        Set connection config directly as keyword arguments.

        Keyword Args:
            dialect (str): "mysql" or "yugabyte"
            host (str): database host
            port (int): database port
            user (str): database user
            password (str): database password
            database (str): database name
            charset (str): character set (default utf8mb4 for MySQL)
            encoding (str): python encoding (default utf-8)
            echo (bool): log every executed SQL statement (with params and
                duration) via the "mydborm.sql" logger, and record it in
                .queries — default False
        """
        if "dialect" not in kwargs:
            raise UnsupportedDialectError(
                "dialect is required. "
                f"Choose from: {SUPPORTED_DIALECTS}"
            )
        # A new config may point at a different database entirely — tear
        # down any pool bound to the old one so it can't keep serving
        # connections to the wrong target, and require pooling to be
        # explicitly re-enabled via configure_pool() for the new config.
        self._teardown_pools()
        self._pool_config = None
        # Store Python encoding separately — not passed to driver
        self._encoding    = kwargs.pop("encoding", "utf-8")
        self._log_queries = kwargs.pop("echo", False)
        self._config      = kwargs

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

    def _mysql_pool_name(self) -> str:
        """Deterministic pool name for this instance + current config —
        must change if host/port/database/pool_size change. mysql-connector
        keeps pools in a process-global registry keyed by this name and
        raises PoolError("Size can not be changed for active pools") if a
        connect() targets an existing name with a different pool_size, so
        pool_size has to be part of the key, not just the connection
        target."""
        if not self._mysql_pool_name_cache:
            key = (
                f"{id(self)}:{self._config.get('host')}:"
                f"{self._config.get('port')}:{self._config.get('database')}:"
                f"{self._pool_config.get('pool_size')}"
            )
            self._mysql_pool_name_cache = "mydborm_" + hashlib.md5(key.encode()).hexdigest()[:16]
        return self._mysql_pool_name_cache

    def _get_pg_pool(self, cfg: dict):
        """Lazily create the psycopg2 pool for postgres-family dialects."""
        if self._pg_pool is None:
            from psycopg2.pool import ThreadedConnectionPool
            max_conn = self._pool_config["pool_size"] + self._pool_config.get("max_overflow", 0)
            self._pg_pool = ThreadedConnectionPool(1, max_conn, **cfg)
        return self._pg_pool

    def _teardown_pools(self):
        """Tear down any driver-level pool bound to the current config."""
        if self._pg_pool is not None:
            try:
                self._pg_pool.closeall()
            except Exception:
                pass
            self._pg_pool = None
        self._mysql_pool_name_cache = None

    def _make_connection(self):
        """Create a raw DB connection based on dialect."""
        cfg = {k: v for k, v in self._config.items() if k != "dialect"}

        if self.dialect == "mysql":
            try:
                import mysql.connector
                cfg.setdefault("charset", "utf8mb4")
                cfg.setdefault("collation", "utf8mb4_unicode_ci")
                cfg.setdefault("use_unicode", True)
                if self._pool_config:
                    # mysql-connector maintains this pool internally, keyed
                    # by pool_name — a PooledMySQLConnection's .close()
                    # already returns it to the pool, no other code needs
                    # to know pooling is active. Hard-capped at pool_size;
                    # max_overflow/pool_timeout aren't supported by this
                    # driver's pool (it raises PoolError immediately on
                    # exhaustion rather than waiting).
                    cfg["pool_name"] = self._mysql_pool_name()
                    cfg["pool_size"] = self._pool_config["pool_size"]
                return mysql.connector.connect(**cfg)
            except ImportError:
                raise ImportError(
                    "mysql-connector-python is not installed.\n"
                    "Run: pip install mysql-connector-python"
                )

        elif self.dialect in ("yugabyte", "postgres", "postgresql"):
            try:
                import psycopg2
                cfg.setdefault("port", 5433)
                cfg.setdefault("client_encoding", "utf8")
                if self._pool_config:
                    # psycopg2's pool has no drop-in connect() equivalent —
                    # getconn()/putconn() are explicit, see close(). Same
                    # exhaustion behavior as MySQL: raises immediately
                    # rather than waiting on max_overflow/pool_timeout.
                    conn = self._get_pg_pool(cfg).getconn()
                else:
                    conn = psycopg2.connect(**cfg)
                conn.set_client_encoding("UTF8")
                return conn
            except ImportError:
                raise ImportError(
                    "psycopg2 is not installed.\n"
                    "Run: pip install psycopg2-binary"
                )

        elif self.dialect == "sqlite":
            import sqlite3
            path = cfg.get("database") or ":memory:"
            raw  = sqlite3.connect(path, isolation_level=None)
            raw.execute("PRAGMA foreign_keys = ON")
            return _SQLiteConnectionAdapter(raw)

        else:
            raise UnsupportedDialectError(
                f"Unsupported dialect: {self.dialect!r}. "
                f"Choose from: {SUPPORTED_DIALECTS}",
                dialect=self.dialect,
            )

    # ------------------------------------------------------------------ #
    #  Connection reuse / recycling                                        #
    # ------------------------------------------------------------------ #

    def _recycle_if_stale(self):
        """Discard the thread's cached connection if it's older than
        pool_recycle — the standard defense against servers dropping
        idle connections (e.g. MySQL's wait_timeout), active by default
        (3600s) even without configure_pool(). A cheap timestamp check,
        not a network round-trip, since connect()/execute() are called on
        nearly every ORM operation."""
        recycle = (self._pool_config or {}).get("pool_recycle", 3600)
        if not recycle:
            return
        conn = getattr(self._local, "conn", None)
        if conn is not None and time.time() - getattr(self._local, "created_at", 0) > recycle:
            self.close()

    def _get_or_create_connection(self):
        self._recycle_if_stale()
        if not getattr(self._local, "conn", None):
            self._local.conn = self._make_connection()
            self._local.created_at = time.time()
        return self._local.conn

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
            raise NotConfiguredError(
                "Database not configured.\n"
                "Call db.configure(...) or db.from_env() first."
            )

        conn = self._get_or_create_connection()
        if self._log_queries:
            conn = _QueryLogConnection(conn, self)
        # Inside an active transaction()/bulk_transaction() on this thread's
        # connection, don't commit/rollback here — that would prematurely
        # end (and release any locks held by) the outer transaction. This
        # is what makes for_update() actually hold across multiple reads
        # inside a `with db.transaction():` block.
        nested = getattr(self._local, "in_transaction", False)
        try:
            yield conn
            if not nested:
                conn.commit()
        except Exception:
            if not nested:
                conn.rollback()
            raise

    def clear_queries(self):
        """Empty the .queries log (has no effect on whether echo is on)."""
        self.queries.clear()

    def close(self):
        """Close the current thread's connection."""
        conn = getattr(self._local, "conn", None)
        if conn:
            try:
                if self.dialect in ("yugabyte", "postgres", "postgresql") and self._pg_pool is not None:
                    self._pg_pool.putconn(conn)
                else:
                    # Already pool-aware for MySQL when pooling is active —
                    # PooledMySQLConnection.close() returns it to the pool
                    # instead of closing the socket.
                    conn.close()
            finally:
                self._local.conn = None

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
            raise NotConfiguredError(
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

    def call_procedure(self, name: str, params: list = None) -> list:
        """
        Execute a stored procedure and return its result rows as a list
        of dicts (empty list if it returns no result set). If the
        procedure produces multiple result sets, all rows from all of
        them are concatenated.

        Not supported on SQLite (no stored procedure support).

        Usage:
            rows = db.call_procedure("get_active_users", [42])
        """
        if self.dialect == "sqlite":
            raise UnsupportedDialectError(
                "Stored procedures are not supported on SQLite.",
                dialect=self.dialect,
            )
        if not _PROC_NAME_RE.match(name or ""):
            raise ValueError(f"Invalid procedure name: {name!r}")
        params = params or []
        with self.connect() as conn:
            cur = conn.cursor()
            if self.dialect == "mysql":
                # mysql-connector requires callproc() + draining
                # stored_results() for CALL — plain execute("CALL ...")
                # leaves trailing result-set state on the connection that
                # silently corrupts whatever query runs next (verified:
                # the next SELECT's cursor.description comes back None).
                cur.callproc(name, params)
                rows = []
                for result in cur.stored_results():
                    columns = [d[0] for d in result.description]
                    rows.extend(dict(zip(columns, row)) for row in result.fetchall())
                return rows
            else:
                # Postgres-family: plain CALL via execute() is clean —
                # verified no leftover state affecting subsequent queries.
                placeholders = ", ".join(["%s"] * len(params))
                cur.execute(f"CALL {name}({placeholders})", params)
                if cur.description:
                    columns = [d[0] for d in cur.description]
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
                return []

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
        elif dialect == "sqlite":
            rows = self.fetchall(
                "SELECT COUNT(*) as cnt FROM sqlite_master "
                "WHERE type = 'table' AND name = %s;",
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
        elif dialect == "sqlite":
            rows = self.fetchall(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' ORDER BY name;"
            )
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
            raise NotConfiguredError(
                "Database not configured.\n"
                "Call db.configure(...) or db.from_env() first."
            )

        conn = self._get_or_create_connection()

        # Disable auto-commit for explicit transaction
        if self.dialect == "mysql":
            conn.autocommit = False
        else:
            conn.autocommit = False

        # Only the outermost transaction()/bulk_transaction() call commits
        # or rolls back — a nested call (or a connect()-based read/write,
        # e.g. via QueryBuilder, happening inside this block) must not
        # end the transaction early.
        already_in_txn = getattr(self._local, "in_transaction", False)
        self._local.in_transaction = True
        try:
            yield conn
            if not already_in_txn:
                conn.commit()
        except Exception:
            if not already_in_txn:
                conn.rollback()
            raise
        finally:
            self._local.in_transaction = already_in_txn
            if not already_in_txn and self.dialect != "mysql":
                conn.autocommit = True


    def execute(self, sql: str, params: list = None) -> int:
        """
        Execute a raw SQL statement (INSERT, UPDATE, DELETE, DDL).
        Returns number of affected rows.

        Usage:
            db.execute("UPDATE users SET active = %s WHERE id = %s", [False, 1])
        """
        if not self._config:
            raise NotConfiguredError(
                "Database not configured.\n"
                "Call db.configure(...) or db.from_env() first."
            )
        self._recycle_if_stale()
        if getattr(self._local, "conn", None):
            conn = self._local.conn
            if self._log_queries:
                conn = _QueryLogConnection(conn, self)
            cur = conn.cursor()
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

        Wires a real driver-level pool for MySQL (mysql-connector's
        pool_name/pool_size) and postgres-family dialects
        (psycopg2.pool.ThreadedConnectionPool). Not yet enforced for
        either driver: pool_timeout (both raise immediately rather than
        waiting when the pool is exhausted) and max_overflow for MySQL
        (mysql-connector's pool has a hard pool_size cap only). No effect
        for SQLite (serverless, pooling doesn't apply).

        Args:
            pool_size: number of persistent connections (default 5)
            max_overflow: extra connections allowed above pool_size
                (postgres-family only — see limitation above)
            pool_timeout: seconds to wait for a connection (default 30) —
                not yet enforced, see limitation above
            pool_recycle: seconds before recycling a connection (default
                3600) — enforced by mydborm itself, not the driver, so it
                applies uniformly to every dialect

        Usage:
            db.configure(dialect="mysql", ...)
            db.configure_pool(pool_size=10, max_overflow=20)
        """
        self._teardown_pools()
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
        conn = getattr(self._local, "conn", None)
        return {
            "dialect":      self.dialect,
            "host":         self._config.get("host"),
            "database":     self._config.get("database"),
            "pool_config":  self._pool_config or {},
            "pooling_active": bool(self._pool_config) and self.dialect in
                               ("mysql", "yugabyte", "postgres", "postgresql"),
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
            name (str): savepoint name (auto-generated if not provided)

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

        if not getattr(self._local, "conn", None):
            raise SavepointError(
                "savepoint() must be used inside a transaction()."
            )

        conn = self._local.conn
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
        if getattr(self._local, "conn", None):
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
        conn = self._get_or_create_connection()
        if self.dialect == "mysql":
            conn.autocommit = False

        already_in_txn = getattr(self._local, "in_transaction", False)
        self._local.in_transaction = True
        try:
            yield conn
            if not already_in_txn:
                conn.commit()
        except Exception:
            if not already_in_txn:
                conn.rollback()
            raise
        finally:
            self._local.in_transaction = already_in_txn
            if not already_in_txn and self.dialect == "mysql":
                conn.autocommit = False

    # ------------------------------------------------------------------ #
    #  Transaction with retry                                              #
    # ------------------------------------------------------------------ #

    def transaction_with_retry(self, fn, retries: int = 3,
                                retry_delay: float = 0.5):
        """
        Run fn(conn) inside a transaction, retrying the whole transaction
        with exponential backoff on deadlocks and on transient connection
        loss (e.g. "MySQL server has gone away"). Other exceptions are
        raised immediately without retry.

        fn is called again from scratch on each retry, so it must be safe
        to re-run (no side effects outside the transaction).

        Usage:
            def transfer(conn):
                db.execute(
                    "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                    [100, 1],
                )
                db.execute(
                    "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                    [100, 2],
                )

            db.transaction_with_retry(transfer, retries=3, retry_delay=0.5)
        """
        import time

        last_error  = None
        max_attempts = retries + 1

        for attempt in range(max_attempts):
            self.close()  # fresh connection each attempt
            try:
                with self.transaction() as conn:
                    return fn(conn)  # committed successfully

            except Exception as e:
                last_error  = e
                err_str     = str(e).lower()
                is_retryable = (
                    # Deadlocks / lock contention
                    "deadlock"          in err_str or
                    "lock wait timeout" in err_str or
                    "1213"              in err_str or
                    "1205"              in err_str or
                    # Transient connection loss — self.close() above
                    # already gets a fresh connection each attempt, which
                    # is exactly the recovery these need.
                    "gone away"                             in err_str or
                    "lost connection"                       in err_str or
                    "server closed the connection unexpectedly" in err_str or
                    "connection already closed"             in err_str or
                    "broken pipe"                            in err_str or
                    "2006"                                   in err_str or
                    "2013"                                   in err_str
                )
                if not is_retryable:
                    raise
                if attempt < retries:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                raise RetryExhaustedError(
                    f"Transaction failed after {retries + 1} attempts",
                    attempts   = retries + 1,
                    last_error = last_error,
                ) from e

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


