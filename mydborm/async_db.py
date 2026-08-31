# =============================================================================
# File        : async_db.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.4.0
# License     : MIT
# Description : Async connection manager and AsyncBaseModel for mydborm.
#               Supports MySQL via aiomysql, YugabyteDB via aiopg, and
#               SQLite via aiosqlite. Provides async CRUD, query builder,
#               and raw SQL. Usage: await AsyncUser.all()
# =============================================================================

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from .fields import Field
from .exceptions import NotConfiguredError, UnsupportedDialectError
from .model import QueryBuilderBase, _validate_identifier

_SQL_LOGGER = logging.getLogger("mydborm.sql")

# Same cap as the sync side (db.py) — bounds memory for long-running
# processes that leave echo=True on.
_MAX_TRACKED_QUERIES = 1000


# ------------------------------------------------------------------ #
#  SQLite async adapters (aiosqlite has no built-in connection pool,   #
#  and — like sync sqlite3 — needs "?" placeholders, not "%s")         #
# ------------------------------------------------------------------ #

class _AsyncSQLiteCursorAdapter:
    """Wraps an aiosqlite.Cursor, translating "%s" placeholders to "?"."""
    def __init__(self, raw):
        self._raw = raw

    async def execute(self, sql, params=None):
        return await self._raw.execute(sql.replace("%s", "?"), params or [])

    async def executemany(self, sql, seq_of_params):
        return await self._raw.executemany(sql.replace("%s", "?"), seq_of_params)

    def __getattr__(self, name):
        return getattr(self._raw, name)


class _AsyncSQLiteCursorCM:
    """
    Returned by _AsyncSQLiteConnectionAdapter.cursor(). mydborm only ever
    uses `async with conn.cursor() as cur:` (never a bare `await
    conn.cursor()`), so this only needs to support that one pattern —
    unlike aiomysql/aiopg's cursor(), which is also directly awaitable.
    """
    def __init__(self, raw_conn):
        self._raw_conn = raw_conn
        self._cur = None

    async def __aenter__(self):
        self._cur = await self._raw_conn.cursor()
        return _AsyncSQLiteCursorAdapter(self._cur)

    async def __aexit__(self, exc_type, exc, tb):
        await self._cur.close()


class _AsyncSQLiteConnectionAdapter:
    """Wraps an aiosqlite.Connection so the "%s" placeholder translation
    is transparent to the rest of async_db.py."""
    def __init__(self, raw):
        self._raw = raw

    def cursor(self):
        return _AsyncSQLiteCursorCM(self._raw)

    def __getattr__(self, name):
        return getattr(self._raw, name)


class _AsyncSQLitePool:
    """
    Minimal stand-in for aiomysql/aiopg's connection pool. SQLite has no
    real concept of a multi-connection pool for a single file — this
    keeps one aiosqlite connection alive and serializes access to it
    with a lock, so concurrent coroutines don't interleave statements
    within another coroutine's connect()-block.
    """
    def __init__(self, path: str):
        self._path   = path
        self._conn   = None
        self._lock   = asyncio.Lock()
        self._closed_conn = None

    async def _ensure_conn(self):
        if self._conn is None:
            import aiosqlite
            self._conn = await aiosqlite.connect(self._path)
            await self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    @asynccontextmanager
    async def acquire(self):
        async with self._lock:
            conn = await self._ensure_conn()
            yield _AsyncSQLiteConnectionAdapter(conn)

    def close(self):
        """Sync, matching aiomysql/aiopg pool.close() — marks for closing."""
        self._closed_conn = self._conn
        self._conn = None

    async def wait_closed(self):
        if self._closed_conn is not None:
            await self._closed_conn.close()
            self._closed_conn = None


# ------------------------------------------------------------------ #
#  Query logging adapters (mirrors db.py's sync versions)              #
# ------------------------------------------------------------------ #

class _AsyncQueryLogCursor:
    """Wraps any async cursor to time and log each execute()/executemany()."""
    def __init__(self, raw, manager):
        self._raw = raw
        self._manager = manager

    def _record(self, sql, params, duration_ms):
        _SQL_LOGGER.debug("%s | params=%r | %.2fms", sql, params, duration_ms)
        queries = self._manager.queries
        queries.append({"sql": sql, "params": params, "duration_ms": duration_ms})
        del queries[:-_MAX_TRACKED_QUERIES]

    async def execute(self, sql, params=None):
        start = time.perf_counter()
        try:
            return await self._raw.execute(sql, params or [])
        finally:
            self._record(sql, params, (time.perf_counter() - start) * 1000)

    async def executemany(self, sql, seq_of_params):
        start = time.perf_counter()
        try:
            return await self._raw.executemany(sql, seq_of_params)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            rows = len(seq_of_params) if hasattr(seq_of_params, "__len__") else "?"
            self._record(sql, f"<{rows} rows>", duration_ms)

    def __getattr__(self, name):
        return getattr(self._raw, name)


class _AsyncQueryLogCursorCM:
    """
    Returned by _AsyncQueryLogConnection.cursor(). Every underlying async
    connection (aiomysql, aiopg, or the sqlite adapter above) supports
    `async with raw_conn.cursor() as cur:` — this drives that same
    protocol manually so it can wrap whatever cursor comes out the other
    end in a _AsyncQueryLogCursor.
    """
    def __init__(self, raw_conn, manager):
        self._raw_conn = raw_conn
        self._manager = manager
        self._cm = None

    async def __aenter__(self):
        self._cm = self._raw_conn.cursor()
        real_cur = await self._cm.__aenter__()
        return _AsyncQueryLogCursor(real_cur, self._manager)

    async def __aexit__(self, exc_type, exc, tb):
        return await self._cm.__aexit__(exc_type, exc, tb)


class _AsyncQueryLogConnection:
    """Wraps a connection so every cursor it hands out is a _AsyncQueryLogCursor."""
    def __init__(self, raw, manager):
        self._raw = raw
        self._manager = manager

    def cursor(self):
        return _AsyncQueryLogCursorCM(self._raw, self._manager)

    def __getattr__(self, name):
        return getattr(self._raw, name)


# ------------------------------------------------------------------ #
#  Async Connection Manager                                            #
# ------------------------------------------------------------------ #

class AsyncConnectionManager:
    """
    Async connection manager for mydborm.

    Usage:
        await async_db.configure(
            dialect="mysql", host="127.0.0.1",
            port=3307, user="root", password="root", database="testdb"
        )

        async with async_db.connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                row = await cur.fetchone()
    """

    def __init__(self):
        self._config  = {}
        self._pool    = None
        self._log_queries = False
        self.queries: list = []

    # ------------------------------------------------------------------ #
    #  Configuration                                                       #
    # ------------------------------------------------------------------ #

    async def configure(self, **kwargs):
        """
        Configure and initialise the connection pool.

        Keyword Args include everything db.configure() accepts, plus:
            echo (bool): log every executed SQL statement (with params and
                duration) via the "mydborm.sql" logger, and record it in
                .queries — default False
        """
        if "dialect" not in kwargs:
            raise UnsupportedDialectError(
                "dialect is required: 'mysql', 'yugabyte', or 'sqlite'"
            )
        self._log_queries = kwargs.pop("echo", False)
        self._config = kwargs
        await self._create_pool()

    def clear_queries(self):
        """Empty the .queries log (has no effect on whether echo is on)."""
        self.queries.clear()

    async def _create_pool(self):
        """Create the underlying async connection pool."""
        cfg     = {k: v for k, v in self._config.items() if k != "dialect"}
        dialect = self._config.get("dialect", "mysql")

        if dialect == "mysql":
            try:
                import aiomysql
                self._pool = await aiomysql.create_pool(
                    host     = cfg.get("host", "127.0.0.1"),
                    port     = cfg.get("port", 3307),
                    user     = cfg.get("user", "root"),
                    password = cfg.get("password", ""),
                    db       = cfg.get("database", ""),
                    minsize  = cfg.get("minsize", 1),
                    maxsize  = cfg.get("maxsize", 10),
                    autocommit = False,
                )
            except ImportError:
                raise ImportError(
                    "aiomysql is not installed.\n"
                    "Run: pip install mydborm[async]"
                )

        elif dialect in ("yugabyte", "postgres"):
            try:
                import aiopg
                dsn = (
                    "host={host} port={port} user={user} "
                    "password={password} dbname={database}"
                ).format(
                    host     = cfg.get("host", "127.0.0.1"),
                    port     = cfg.get("port", 5433),
                    user     = cfg.get("user", ""),
                    password = cfg.get("password", ""),
                    database = cfg.get("database", ""),
                )
                self._pool = await aiopg.create_pool(dsn)
            except ImportError:
                raise ImportError(
                    "aiopg is not installed.\n"
                    "Run: pip install mydborm[async]"
                )

        elif dialect == "sqlite":
            try:
                import aiosqlite  # noqa: F401 — imported here to fail fast if missing
            except ImportError:
                raise ImportError(
                    "aiosqlite is not installed.\n"
                    "Run: pip install mydborm[async]"
                )
            path = cfg.get("database") or ":memory:"
            self._pool = _AsyncSQLitePool(path)
            await self._pool._ensure_conn()

        else:
            raise UnsupportedDialectError(
                "Unsupported dialect: " + repr(dialect) +
                ". Choose 'mysql', 'yugabyte', or 'sqlite'.",
                dialect=dialect,
            )

    @property
    def dialect(self) -> str:
        return self._config.get("dialect", "mysql")

    # ------------------------------------------------------------------ #
    #  Connection                                                          #
    # ------------------------------------------------------------------ #

    @asynccontextmanager
    async def connect(self):
        """
        Async context manager — acquires a connection from the pool.

        async with async_db.connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        """
        if self._pool is None:
            raise NotConfiguredError(
                "Async DB not configured.\n"
                "Call: await async_db.configure(...) first."
            )
        async with self._pool.acquire() as conn:
            if self._log_queries:
                conn = _AsyncQueryLogConnection(conn, self)
            try:
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

    # ------------------------------------------------------------------ #
    #  Raw SQL                                                             #
    # ------------------------------------------------------------------ #

    async def execute(self, sql: str, params: list = None) -> int:
        """Execute a raw SQL statement. Returns affected row count."""
        async with self.connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params or [])
                return cur.rowcount

    async def fetchall(self, sql: str, params: list = None) -> list:
        """Execute a SELECT and return list of dicts."""
        async with self.connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params or [])
                columns = [desc[0] for desc in cur.description]
                rows    = await cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]

    async def fetchone(self, sql: str,
                       params: list = None) -> Optional[dict]:
        """Execute a SELECT and return a single dict or None."""
        rows = await self.fetchall(sql, params)
        return rows[0] if rows else None

    # ------------------------------------------------------------------ #
    #  Pool management                                                     #
    # ------------------------------------------------------------------ #

    async def close(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    def __repr__(self):
        if not self._config:
            return "<AsyncConnectionManager: not configured>"
        return (
            "<AsyncConnectionManager: dialect="
            + repr(self.dialect)
            + " host=" + repr(self._config.get("host"))
            + " database=" + repr(self._config.get("database"))
            + ">"
        )


# Global singleton
async_db = AsyncConnectionManager()


# ------------------------------------------------------------------ #
#  AsyncQueryBuilder                                                    #
# ------------------------------------------------------------------ #

class AsyncQueryBuilder(QueryBuilderBase):
    """Async QueryBuilder — see QueryBuilderBase (model.py) for the
    chainable filter/ordering/join API shared with the sync QueryBuilder.
    This class adds the terminal methods that actually execute against
    the database.

    .include() is inherited and accepted, but eager loading isn't wired
    up yet — async relationship declarations don't exist yet either, so
    calling .all() with any .include() active raises NotImplementedError
    rather than silently doing nothing.
    """

    @property
    def _dialect(self) -> str:
        return async_db.dialect

    # ── Execution ────────────────────────────────────────────────── #

    async def all(self) -> list:
        """Execute and return all matching rows as list of dicts."""
        if self._includes:
            raise NotImplementedError(
                "Eager loading via .include() is not yet supported for "
                "async models."
            )
        sql, params = self._build_sql()
        return await self._model._fetch(sql + ";", params)

    async def first(self) -> Optional[dict]:
        """Return first matching row or None."""
        original_limit = self._limit
        self._limit    = 1
        sql, params    = self._build_sql()
        self._limit    = original_limit
        rows = await self._model._fetch(sql + ";", params)
        return rows[0] if rows else None

    async def count(self) -> int:
        """Return count of matching rows or groups."""
        if self._group_by:
            # Count number of groups using subquery
            inner_sql, params = self._build_sql(
                select=", ".join(self._group_by)
            )
            sql  = "SELECT COUNT(*) FROM (" + inner_sql + ") AS _grp"
            rows = await self._model._fetch(sql + ";", params)
        else:
            sql, params = self._build_sql(select="COUNT(*)")
            rows = await self._model._fetch(sql + ";", params)
        if rows:
            val = list(rows[0].values())[0]
            return int(val)
        return 0

    async def exists(self) -> bool:
        """Return True if any row matches."""
        return (await self.count()) > 0

    async def sum(self, field: str) -> float:
        """Return SUM of a field."""
        _validate_identifier(field)
        sql, params = self._build_sql(select=f"SUM({field})")
        rows = await self._model._fetch(sql + ";", params)
        result = list(rows[0].values())[0]
        return float(result) if result is not None else 0.0

    async def avg(self, field: str) -> float:
        """Return AVG of a field."""
        _validate_identifier(field)
        sql, params = self._build_sql(select=f"AVG({field})")
        rows = await self._model._fetch(sql + ";", params)
        result = list(rows[0].values())[0]
        return float(result) if result is not None else 0.0

    async def min(self, field: str):
        """Return MIN of a field."""
        _validate_identifier(field)
        sql, params = self._build_sql(select=f"MIN({field})")
        rows = await self._model._fetch(sql + ";", params)
        return list(rows[0].values())[0]

    async def max(self, field: str):
        """Return MAX of a field."""
        _validate_identifier(field)
        sql, params = self._build_sql(select=f"MAX({field})")
        rows = await self._model._fetch(sql + ";", params)
        return list(rows[0].values())[0]

    async def update(self, **kwargs) -> int:
        """Bulk-update matching rows. Returns affected row count.

        Example:
            await User.query().where("active", False).update(role="guest")
        """
        if not kwargs:
            return 0
        table   = self._model._table
        set_sql = ", ".join(f"{col} = %s" for col in kwargs)
        params  = list(kwargs.values())
        sql     = f"UPDATE {table} SET {set_sql}"

        and_clauses = [w[0] for w in self._wheres]
        or_clauses  = [w[0] for w in self._or_wheres]
        conditions  = []
        if and_clauses:
            conditions.append(" AND ".join(and_clauses))
        if or_clauses:
            conditions.append("(" + " OR ".join(or_clauses) + ")")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        for _, vals in self._wheres:
            params.extend(vals)
        for _, vals in self._or_wheres:
            params.extend(vals)

        async with async_db.connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql + ";", params)
                return cur.rowcount

    async def delete(self) -> int:
        """Delete all matching rows. Returns affected row count."""
        table  = self._model._table
        params = []
        sql    = f"DELETE FROM {table}"

        and_clauses = [w[0] for w in self._wheres]
        or_clauses  = [w[0] for w in self._or_wheres]
        conditions  = []
        if and_clauses:
            conditions.append(" AND ".join(and_clauses))
        if or_clauses:
            conditions.append("(" + " OR ".join(or_clauses) + ")")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        for _, vals in self._wheres:
            params.extend(vals)
        for _, vals in self._or_wheres:
            params.extend(vals)

        async with async_db.connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql + ";", params)
                return cur.rowcount

    async def paginate(self, page: int = 1, per_page: int = 20) -> dict:
        """Return a paginated result dict.

        Returns:
            {
                "data"    : list of rows,
                "total"   : total matching rows,
                "pages"   : total number of pages,
                "page"    : current page,
                "per_page": rows per page,
            }
        """
        if page < 1:
            page = 1
        total  = await self.count()
        pages  = max(1, -(-total // per_page))   # ceiling division
        offset = (page - 1) * per_page
        data   = await self.limit(per_page).offset(offset).all()
        return {
            "data":     data,
            "total":    total,
            "pages":    pages,
            "page":     page,
            "per_page": per_page,
        }

    def __repr__(self):
        sql, params = self._build_sql()
        return f"<AsyncQueryBuilder sql={sql!r} params={params!r}>"


# ------------------------------------------------------------------ #
#  AsyncModelMeta                                                      #
# ------------------------------------------------------------------ #

class AsyncModelMeta(type):
    """Metaclass for AsyncBaseModel — same field introspection as sync."""
    def __new__(mcs, name, bases, namespace):
        fields = {}
        for base in bases:
            if hasattr(base, "_fields"):
                fields.update(base._fields)
        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, Field):
                attr_value.name = attr_name
                fields[attr_name] = attr_value
        namespace["_fields"] = fields
        namespace["_table"]  = namespace.get(
            "__tablename__",
            name.lower() + "s"
        )
        return super().__new__(mcs, name, bases, namespace)


# ------------------------------------------------------------------ #
#  AsyncBaseModel                                                      #
# ------------------------------------------------------------------ #

class AsyncBaseModel(metaclass=AsyncModelMeta):
    """
    Async ORM base model.

    Usage:
        class User(AsyncBaseModel):
            __tablename__ = "users"
            id       = IntField(primary_key=True)
            username = StrField(max_length=100, nullable=False)

        await User.create_table()
        uid  = await User.create(username="alice")
        user = await User.get(id=uid)
        all  = await User.all()
    """

    # ------------------------------------------------------------------ #
    #  Schema                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    async def create_table(cls, if_not_exists: bool = True) -> None:
        """Create the database table for this model."""
        exist = "IF NOT EXISTS " if if_not_exists else ""
        col_defs      = []
        col_separator = ",\n"
        for fname, field in cls._fields.items():
            col_defs.append("  " + fname + " " + field.to_sql_def(async_db.dialect))
        sql = (
            "CREATE TABLE " + exist + cls._table +
            " (\n" + col_separator.join(col_defs) + "\n);"
        )
        await async_db.execute(sql)
        print("[mydborm] Async table '" + cls._table + "' ready.")

    @classmethod
    async def drop_table(cls, if_exists: bool = True) -> None:
        """Drop the database table."""
        exist = "IF EXISTS " if if_exists else ""
        await async_db.execute(
            "DROP TABLE " + exist + cls._table + ";"
        )
        print("[mydborm] Async table '" + cls._table + "' dropped.")

    # ------------------------------------------------------------------ #
    #  Create                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    async def create(cls, **kwargs) -> int:
        """Insert a new row. Returns the new primary key."""
        validated = {}
        for fname, field in cls._fields.items():
            if field.primary_key:
                continue
            value = kwargs.get(fname, field.default)
            validated[fname] = field.validate(value)

        columns      = ", ".join(validated.keys())
        placeholders = ", ".join(["%s"] * len(validated))
        sql = (
            "INSERT INTO " + cls._table +
            " (" + columns + ") VALUES (" + placeholders + ");"
        )
        async with async_db.connect() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, list(validated.values()))
                return cur.lastrowid

    # ------------------------------------------------------------------ #
    #  Read                                                                #
    # ------------------------------------------------------------------ #

    @classmethod
    async def _fetch(cls, sql: str, params: list = None) -> list:
        """Internal: run SELECT and return list of dicts."""
        return await async_db.fetchall(sql, params)

    @classmethod
    async def all(cls) -> list:
        """Return all rows."""
        return await cls._fetch("SELECT * FROM " + cls._table + ";")

    @classmethod
    async def get(cls, **kwargs) -> Optional[dict]:
        """Return a single matching row or None."""
        where, values = cls._build_where(kwargs)
        sql = (
            "SELECT * FROM " + cls._table +
            " WHERE " + where + " LIMIT 1;"
        )
        rows = await cls._fetch(sql, values)
        return rows[0] if rows else None

    @classmethod
    async def filter(cls, **kwargs) -> list:
        """Return all rows matching kwargs."""
        where, values = cls._build_where(kwargs)
        sql = (
            "SELECT * FROM " + cls._table +
            " WHERE " + where + ";"
        )
        return await cls._fetch(sql, values)

    @classmethod
    async def count(cls, **kwargs) -> int:
        """Count rows, optionally filtered."""
        if kwargs:
            where, values = cls._build_where(kwargs)
            sql  = (
                "SELECT COUNT(*) FROM " + cls._table +
                " WHERE " + where + ";"
            )
            rows = await cls._fetch(sql, values)
        else:
            rows = await cls._fetch(
                "SELECT COUNT(*) FROM " + cls._table + ";"
            )
        return list(rows[0].values())[0]

    # ------------------------------------------------------------------ #
    #  Update                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    async def update(cls, data: dict, **where_kwargs) -> int:
        """Update rows matching where_kwargs with data."""
        set_clause    = ", ".join(k + " = %s" for k in data.keys())
        where, wvals  = cls._build_where(where_kwargs)
        sql = (
            "UPDATE " + cls._table +
            " SET " + set_clause +
            " WHERE " + where + ";"
        )
        return await async_db.execute(sql, list(data.values()) + wvals)

    # ------------------------------------------------------------------ #
    #  Delete                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    async def delete(cls, **kwargs) -> int:
        """Delete rows matching kwargs."""
        where, values = cls._build_where(kwargs)
        sql = (
            "DELETE FROM " + cls._table +
            " WHERE " + where + ";"
        )
        return await async_db.execute(sql, values)

    @classmethod
    def query(cls) -> "AsyncQueryBuilder":
        """Start a chainable query.

        Usage:
            await (User.query()
                       .where("active", True)
                       .where("price__gt", 20)
                       .order_by("name")
                       .limit(10)
                       .all())
        """
        return AsyncQueryBuilder(cls)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_where(cls, kwargs: dict) -> tuple:
        if not kwargs:
            raise ValueError("At least one filter condition is required.")
        clauses = [k + " = %s" for k in kwargs.keys()]
        return " AND ".join(clauses), list(kwargs.values())

    def __repr__(self):
        return "<Async" + self.__class__.__name__ + " table=" + repr(self._table) + ">"