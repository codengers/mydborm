# =============================================================================
# File        : model.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Core ORM engine. Provides ModelMeta metaclass for
#               declarative field introspection at class definition time,
#               and BaseModel with full CRUD operations: create_table,
#               drop_table, create, all, get, filter, update, delete,
#               count, and exists.
# =============================================================================
"""
model.py — BaseModel with metaclass for mydborm.
Provides declarative model definition + CRUD operations.
"""

from .fields import Field
from .db import db

# ------------------------------------------------------------------ #
#  QueryBuilder                                                        #
# ------------------------------------------------------------------ #

class QueryBuilder:
    """
    Fluent chainable query builder for mydborm models.

    Usage:
        results = (User.query()
                       .where("active", True)
                       .where("price__gt", 20)
                       .order_by("name")
                       .limit(10)
                       .offset(0)
                       .all())

    Supported operators (append to field name with __):
        __gt    →  >
        __lt    →  
        __gte   →  >=
        __lte   →  <=
        __ne    →  !=
        __like  →  LIKE
        __in    →  IN (...)
        __null  →  IS NULL / IS NOT NULL
    """

    OPERATORS = {
        "__gt":   ">",
        "__lt":   "<",
        "__gte":  ">=",
        "__lte":  "<=",
        "__ne":   "!=",
        "__like": "LIKE",
        "__in":   "IN",
        "__null": "IS",
    }

    def __init__(self, model_class):
        self._model     = model_class
        self._wheres    = []    # list of (clause, value)
        self._order     = None
        self._order_dir = "ASC"
        self._limit     = None
        self._offset    = None

    # ── Filters ──────────────────────────────────────────────────── #

    def where(self, field_op: str, value=None) -> "QueryBuilder":
        """
        Add a WHERE condition.

        Simple equality:
            .where("active", True)

        With operator:
            .where("price__gt", 20)
            .where("name__like", "%alice%")
            .where("score__in", [1, 2, 3])
            .where("deleted_at__null", True)   # IS NULL
            .where("deleted_at__null", False)  # IS NOT NULL
        """
        # Detect operator suffix
        op     = "="
        col    = field_op
        for suffix, operator in self.OPERATORS.items():
            if field_op.endswith(suffix):
                col = field_op[: -len(suffix)]
                op  = operator
                break

        if op == "IN":
            if not hasattr(value, "__iter__") or isinstance(value, str):
                raise ValueError(
                    f".where('{field_op}', value): "
                    f"__in requires a list or tuple."
                )
            placeholders = ", ".join(["%s"] * len(value))
            clause = f"{col} IN ({placeholders})"
            self._wheres.append((clause, list(value)))

        elif op == "IS":
            null_str = "NULL" if value else "NOT NULL"
            clause   = f"{col} IS {null_str}"
            self._wheres.append((clause, []))

        else:
            clause = f"{col} {op} %s"
            self._wheres.append((clause, [value]))

        return self

    # ── Ordering ─────────────────────────────────────────────────── #

    def order_by(self, field: str, desc: bool = False) -> "QueryBuilder":
        """
        .order_by("name")           → ORDER BY name ASC
        .order_by("price", desc=True) → ORDER BY price DESC
        """
        self._order     = field
        self._order_dir = "DESC" if desc else "ASC"
        return self

    # ── Pagination ───────────────────────────────────────────────── #

    def limit(self, n: int) -> "QueryBuilder":
        """Limit number of rows returned."""
        self._limit = n
        return self

    def offset(self, n: int) -> "QueryBuilder":
        """Skip first n rows."""
        self._offset = n
        return self

    # ── SQL builder ──────────────────────────────────────────────── #

    def _build_sql(self, select: str = "*") -> tuple:
        """Build SQL string and flat params list."""
        table  = self._model._table
        sql    = f"SELECT {select} FROM {table}"
        params = []

        if self._wheres:
            clauses = [w[0] for w in self._wheres]
            sql    += " WHERE " + " AND ".join(clauses)
            for _, vals in self._wheres:
                params.extend(vals)

        if self._order:
            sql += f" ORDER BY {self._order} {self._order_dir}"

        if self._limit is not None and self._offset is not None:
            sql += f" LIMIT {self._limit} OFFSET {self._offset}"
        elif self._limit is not None:
            sql += f" LIMIT {self._limit}"
        elif self._offset is not None:
            sql += f" LIMIT 18446744073709551615 OFFSET {self._offset}"

        return sql, params

    # ── Execution ────────────────────────────────────────────────── #

    def all(self) -> list:
        """Execute and return all matching rows as list of dicts."""
        sql, params = self._build_sql()
        return self._model._fetch(sql + ";", params)

    def first(self) -> dict | None:
        """Return first matching row or None."""
        original_limit = self._limit
        self._limit    = 1
        sql, params    = self._build_sql()
        self._limit    = original_limit
        rows = self._model._fetch(sql + ";", params)
        return rows[0] if rows else None

    def count(self) -> int:
        """Return count of matching rows."""
        sql, params = self._build_sql(select="COUNT(*)")
        rows = self._model._fetch(sql + ";", params)
        return list(rows[0].values())[0]

    def exists(self) -> bool:
        """Return True if any row matches."""
        return self.count() > 0

    def sum(self, field: str) -> float:
        """Return SUM of a field."""
        sql, params = self._build_sql(select=f"SUM({field})")
        rows = self._model._fetch(sql + ";", params)
        result = list(rows[0].values())[0]
        return float(result) if result is not None else 0.0

    def avg(self, field: str) -> float:
        """Return AVG of a field."""
        sql, params = self._build_sql(select=f"AVG({field})")
        rows = self._model._fetch(sql + ";", params)
        result = list(rows[0].values())[0]
        return float(result) if result is not None else 0.0

    def min(self, field: str):
        """Return MIN of a field."""
        sql, params = self._build_sql(select=f"MIN({field})")
        rows = self._model._fetch(sql + ";", params)
        return list(rows[0].values())[0]

    def max(self, field: str):
        """Return MAX of a field."""
        sql, params = self._build_sql(select=f"MAX({field})")
        rows = self._model._fetch(sql + ";", params)
        return list(rows[0].values())[0]

    def delete(self) -> int:
        """Delete all matching rows. Returns affected row count."""
        table  = self._model._table
        params = []
        sql    = f"DELETE FROM {table}"

        if self._wheres:
            clauses = [w[0] for w in self._wheres]
            sql    += " WHERE " + " AND ".join(clauses)
            for _, vals in self._wheres:
                params.extend(vals)

        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql + ";", params)
            return cur.rowcount

    def __repr__(self):
        sql, params = self._build_sql()
        return f"<QueryBuilder sql={sql!r} params={params!r}>"

# ------------------------------------------------------------------ #
#  Metaclass — introspects fields at class definition time            #
# ------------------------------------------------------------------ #

class ModelMeta(type):
    """
    Runs once when a model class is defined.
    Collects all Field instances declared on the class
    and stores them in cls._fields dict.
    """
    def __new__(mcs, name, bases, namespace):
        fields = {}

        # Inherit fields from parent models
        for base in bases:
            if hasattr(base, "_fields"):
                fields.update(base._fields)

        # Collect fields declared on this class
        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, Field):
                attr_value.name = attr_name   # inject field name
                fields[attr_name] = attr_value

        namespace["_fields"] = fields
        namespace["_table"]  = namespace.get(
            "__tablename__",
            name.lower() + "s"   # default: ClassName → classnames
        )
        return super().__new__(mcs, name, bases, namespace)


# ------------------------------------------------------------------ #
#  BaseModel                                                           #
# ------------------------------------------------------------------ #

class BaseModel(metaclass=ModelMeta):
    """
    Inherit from this to define a database model.

    Example:
        class User(BaseModel):
            __tablename__ = "users"
            id       = IntField(primary_key=True)
            username = StrField(max_length=100, nullable=False)
            email    = StrField(max_length=255, nullable=False, unique=True)
            active   = BoolField(default=True)

        # Create table
        User.create_table()

        # Insert
        User.create(username="alice", email="alice@example.com")

        # Query
        users = User.all()
        user  = User.get(id=1)
        devs  = User.filter(active=True)

        # Update
        User.update({"active": False}, id=1)

        # Delete
        User.delete(id=1)
    """

    # ------------------------------------------------------------------ #
    #  Schema                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create_table(cls, if_not_exists: bool = True) -> None:
        """Create the database table for this model."""
        exist_clause = "IF NOT EXISTS" if if_not_exists else ""
        col_defs = []

        for fname, field in cls._fields.items():
            col_defs.append(f"  {fname} {field.to_sql_def()}")

        sql = (
            f"CREATE TABLE {exist_clause} {cls._table} "
            f"(\n{',\n'.join(col_defs)}\n);"
        )
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql)
        print(f"[mydborm] Table '{cls._table}' ready.")

    @classmethod
    def drop_table(cls, if_exists: bool = True) -> None:
        """Drop the database table for this model."""
        exist_clause = "IF EXISTS" if if_exists else ""
        sql = f"DROP TABLE {exist_clause} {cls._table};"
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql)
        print(f"[mydborm] Table '{cls._table}' dropped.")

    # ------------------------------------------------------------------ #
    #  Create                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(cls, **kwargs) -> int:
        """
        Insert a new row. Returns the new row's primary key.

        User.create(username="alice", email="alice@example.com")
        """
        # Validate all provided values
        validated = {}
        for fname, field in cls._fields.items():
            if field.primary_key:
                continue   # auto-increment, skip
            value = kwargs.get(fname, field.default)
            validated[fname] = field.validate(value)

        columns = ", ".join(validated.keys())
        placeholders = ", ".join(["%s"] * len(validated))
        sql = (
            f"INSERT INTO {cls._table} ({columns}) "
            f"VALUES ({placeholders});"
        )
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, list(validated.values()))
            return cur.lastrowid

    # ------------------------------------------------------------------ #
    #  Read                                                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _fetch(cls, sql: str, params: list = None) -> list:
        """Internal: run a SELECT and return list of dicts."""
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or [])
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    @classmethod
    def all(cls) -> list:
        """Return all rows as list of dicts."""
        return cls._fetch(f"SELECT * FROM {cls._table};")

    @classmethod
    def get(cls, **kwargs) -> dict | None:
        """
        Return a single row matching kwargs or None.

        User.get(id=1)
        """
        where, values = cls._build_where(kwargs)
        sql = f"SELECT * FROM {cls._table} WHERE {where} LIMIT 1;"
        rows = cls._fetch(sql, values)
        return rows[0] if rows else None

    @classmethod
    def filter(cls, **kwargs) -> list:
        """
        Return all rows matching kwargs.

        User.filter(active=True)
        """
        where, values = cls._build_where(kwargs)
        sql = f"SELECT * FROM {cls._table} WHERE {where};"
        return cls._fetch(sql, values)

    # ------------------------------------------------------------------ #
    #  Update                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def update(cls, data: dict, **where_kwargs) -> int:
        """
        Update rows matching where_kwargs with data.
        Returns number of affected rows.

        User.update({"active": False}, id=1)
        """
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        where, where_vals = cls._build_where(where_kwargs)
        sql = (
            f"UPDATE {cls._table} "
            f"SET {set_clause} "
            f"WHERE {where};"
        )
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, list(data.values()) + where_vals)
            return cur.rowcount

    # ------------------------------------------------------------------ #
    #  Delete                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def delete(cls, **kwargs) -> int:
        """
        Delete rows matching kwargs.
        Returns number of deleted rows.

        User.delete(id=1)
        """
        where, values = cls._build_where(kwargs)
        sql = f"DELETE FROM {cls._table} WHERE {where};"
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, values)
            return cur.rowcount

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @classmethod
    def _build_where(cls, kwargs: dict) -> tuple:
        """Build a WHERE clause from keyword arguments."""
        if not kwargs:
            raise ValueError("At least one filter condition is required.")
        clauses = [f"{k} = %s" for k in kwargs.keys()]
        return " AND ".join(clauses), list(kwargs.values())

    @classmethod
    def count(cls, **kwargs) -> int:
        """Count rows, optionally filtered."""
        if kwargs:
            where, values = cls._build_where(kwargs)
            sql = f"SELECT COUNT(*) FROM {cls._table} WHERE {where};"
            rows = cls._fetch(sql, values)
        else:
            sql = f"SELECT COUNT(*) FROM {cls._table};"
            rows = cls._fetch(sql)
        return list(rows[0].values())[0]

    @classmethod
    def exists(cls, **kwargs) -> bool:
        """Return True if any row matches kwargs."""
        return cls.count(**kwargs) > 0

    @classmethod
    def query(cls) -> "QueryBuilder":
        """
        Return a QueryBuilder for this model.

        Usage:
            User.query().where("active", True).order_by("name").all()
        """
        return QueryBuilder(cls)

    def __repr__(self):
        return f"<{self.__class__.__name__} table={self._table!r}>"

