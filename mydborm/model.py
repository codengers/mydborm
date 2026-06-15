# =============================================================================
# File        : model.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Core ORM engine. Provides ModelMeta metaclass for
#               declarative field introspection at class definition time
#               and BaseModel with full CRUD: create_table, drop_table,
#               create, all, get, filter, update, delete, count, exists.
# =============================================================================

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

    def __repr__(self):
        return f"<{self.__class__.__name__} table={self._table!r}>"

