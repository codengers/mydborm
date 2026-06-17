# =============================================================================
# File        : async_db.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.4.0
# License     : MIT
# Description : Async connection manager and AsyncBaseModel for mydborm.
#               Supports MySQL via aiomysql and YugabyteDB via aiopg.
#               Provides async CRUD, query builder, and raw SQL.
#               Usage: await AsyncUser.all()
# =============================================================================

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from .fields import Field


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

    # ------------------------------------------------------------------ #
    #  Configuration                                                       #
    # ------------------------------------------------------------------ #

    async def configure(self, **kwargs):
        """Configure and initialise the connection pool."""
        if "dialect" not in kwargs:
            raise ValueError("dialect is required: 'mysql' or 'yugabyte'")
        self._config = kwargs
        await self._create_pool()

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
        else:
            raise ValueError(
                "Unsupported dialect: " + repr(dialect) +
                ". Choose 'mysql' or 'yugabyte'."
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
            raise RuntimeError(
                "Async DB not configured.\n"
                "Call: await async_db.configure(...) first."
            )
        async with self._pool.acquire() as conn:
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
            col_defs.append("  " + fname + " " + field.to_sql_def())
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