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

import json
from typing import Optional
from .fields import Field, JSONField
from .db import db

# ------------------------------------------------------------------ #
#  LazyRelation descriptor                                             #
# ------------------------------------------------------------------ #

class LazyRelation:
    """
    Descriptor that loads related objects on first access.
    Cached on the instance after first load.

    Usage on model class:
        class Author(BaseModel):
            __tablename__ = "authors"
            id   = IntField(primary_key=True)
            name = StrField(max_length=100)
            books = LazyRelation("Book", foreign_key="author_id")

        author = Author.get(id=1)
        books  = author.books   # loaded on first access
        books  = author.books   # cached, no second query
    """

    def __init__(self, related_model_name: str,
                 foreign_key: str = None,
                 relation_type: str = "has_many"):
        self.related_model_name = related_model_name
        self.foreign_key        = foreign_key
        self.relation_type      = relation_type
        self.attr_name          = None

    def __set_name__(self, owner, name):
        self.attr_name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self

        # Check cache first
        cache_key = f"_lazy_{self.attr_name}"
        cached    = obj._data.get(cache_key)
        if cached is not None:
            return cached

        # Resolve related model class
        related_model = self._resolve_model(obj._model_class)

        # Load based on relation type
        if self.relation_type == "has_many":
            fk   = self.foreign_key or \
                   f"{obj._model_class.__name__.lower()}_id"
            pk   = obj._get_pk_value()
            rows = related_model.query().where(fk, pk).all()

        elif self.relation_type == "belongs_to":
            fk     = self.foreign_key or \
                     f"{related_model.__name__.lower()}_id"
            fk_val = obj._data.get(fk)
            rows   = related_model.get(id=fk_val) if fk_val else None

        else:
            rows = []

        # Cache on instance — bypass TrackingDict field check
        dict.__setitem__(obj._data, cache_key, rows)
        return rows

    def _resolve_model(self, owner_class):
        """
        Resolve related model class by name.
        Searches all BaseModel subclasses.
        """
        def find_subclass(cls, name):
            for sub in cls.__subclasses__():
                if sub.__name__ == name:
                    return sub
                found = find_subclass(sub, name)
                if found:
                    return found
            return None

        model = find_subclass(BaseModel, self.related_model_name)
        if model is None:
            raise ValueError(
                "LazyRelation: could not find model "
                + repr(self.related_model_name)
                + ". Make sure it is defined before accessing "
                + repr(self.attr_name) + "."
            )
        return model

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
        self._wheres    = []
        self._order     = None
        self._order_dir = "ASC"
        self._limit     = None
        self._offset    = None
        self._joins     = []
        self._includes  = []
        self._group_by  = []
        self._having    = []
        self._columns   = []
        self._or_wheres = []
        self._distinct  = False

    # ── Column projection ─────────────────────────────────────────── #

    def distinct(self) -> "QueryBuilder":
        """Add DISTINCT to the SELECT clause.

        Example:
            User.query().select("country").distinct().all()
            # → SELECT DISTINCT country FROM users

            User.query().distinct().count()
            # → SELECT COUNT(DISTINCT *) — note: use select() to specify the field
        """
        self._distinct = True
        return self

    def select(self, *columns: str) -> "QueryBuilder":
        """Restrict SELECT to specific columns.

        Example:
            User.query().select("id", "name").where("active", True).all()
            # → SELECT id, name FROM users WHERE active = 1
        """
        self._columns = list(columns)
        return self

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
            if isinstance(value, str) and value.startswith("(SELECT"):
                self._wheres.append((f"{col} IN {value}", []))
            elif not hasattr(value, "__iter__") or isinstance(value, str):
                raise ValueError(
                    f".where('{field_op}', value): "
                    f"__in requires a list or tuple."
                )
            else:
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

    def where_raw(self, sql: str, *params) -> "QueryBuilder":
        """
        Add a raw SQL AND condition — escape hatch for expressions that don't
        fit the built-in operator syntax.

        Args:
            sql    : raw SQL fragment, use %s for parameter placeholders
            params : positional values for each %s placeholder

        Usage:
            # Date functions
            Order.query().where_raw("YEAR(created_at) = %s", 2024).all()

            # JSON extraction (MySQL 5.7+)
            User.query().where_raw("JSON_EXTRACT(meta, '$.role') = %s", "admin").all()

            # Full-text search
            Post.query().where_raw("MATCH(body) AGAINST(%s IN BOOLEAN MODE)", "+python").all()

            # No parameters
            Product.query().where_raw("price > cost * 1.2").all()

            # Mix with standard where()
            Order.query()
                 .where("user_id", 5)
                 .where_raw("DATEDIFF(NOW(), created_at) < %s", 30)
                 .all()
        """
        self._wheres.append((sql, list(params)))
        return self

    def or_where_raw(self, sql: str, *params) -> "QueryBuilder":
        """
        Add a raw SQL OR condition.

        Same as where_raw() but placed in the OR group:
            WHERE <and_conditions> AND (<or1> OR <or2> OR ...)

        Usage:
            Order.query()
                 .where("user_id", 5)
                 .or_where_raw("YEAR(created_at) = %s", 2024)
                 .or_where_raw("status = 'legacy'")
                 .all()
        """
        self._or_wheres.append((sql, list(params)))
        return self

    def or_where(self, field_op: str, value=None) -> "QueryBuilder":
        """
        Add an OR condition.

        OR conditions are grouped together and ANDed with any WHERE conditions:
            WHERE <and_conditions> AND (<or1> OR <or2> OR ...)

        Supports the same operators as .where():
            .or_where("status", "pending")
            .or_where("status__in", ["retry", "queued"])
            .or_where("deleted_at__null", True)

        Example:
            Order.query()
                 .where("user_id", 5)
                 .or_where("status", "pending")
                 .or_where("status", "retry")
                 .all()
            # → SELECT * FROM orders
            #   WHERE user_id = 5 AND (status = 'pending' OR status = 'retry')
        """
        op  = "="
        col = field_op
        for suffix, operator in self.OPERATORS.items():
            if field_op.endswith(suffix):
                col = field_op[: -len(suffix)]
                op  = operator
                break

        if op == "IN":
            if isinstance(value, str) and value.startswith("(SELECT"):
                self._or_wheres.append((f"{col} IN {value}", []))
            elif not hasattr(value, "__iter__") or isinstance(value, str):
                raise ValueError(
                    f".or_where('{field_op}', value): "
                    f"__in requires a list or tuple."
                )
            else:
                placeholders = ", ".join(["%s"] * len(value))
                self._or_wheres.append(
                    (f"{col} IN ({placeholders})", list(value))
                )
        elif op == "IS":
            null_str = "NULL" if value else "NOT NULL"
            self._or_wheres.append((f"{col} IS {null_str}", []))
        else:
            self._or_wheres.append((f"{col} {op} %s", [value]))

        return self

    # ── Joins ────────────────────────────────────────────────────── #

    def join(self, table: str, on: str,
             join_type: str = "INNER") -> "QueryBuilder":
        """
        Add a JOIN clause.

        Args:
            table     : table name to join
            on        : join condition e.g. "users.id = orders.user_id"
            join_type : INNER, LEFT, RIGHT (default INNER)

        Usage:
            User.query()
                .join("orders", "users.id = orders.user_id")
                .where("orders.shipped", True)
                .all()
        """
        join_type = join_type.upper()
        if join_type not in ("INNER", "LEFT", "RIGHT", "FULL"):
            raise ValueError(
                "join_type must be INNER, LEFT, RIGHT or FULL. "
                "Got: " + repr(join_type)
            )
        self._joins.append(
            join_type + " JOIN " + table + " ON " + on
        )
        return self

    def inner_join(self, table: str, on: str) -> "QueryBuilder":
        """Shortcut for INNER JOIN."""
        return self.join(table, on, join_type="INNER")

    def left_join(self, table: str, on: str) -> "QueryBuilder":
        """Shortcut for LEFT JOIN."""
        return self.join(table, on, join_type="LEFT")

    def right_join(self, table: str, on: str) -> "QueryBuilder":
        """Shortcut for RIGHT JOIN."""
        return self.join(table, on, join_type="RIGHT")
    
    def include(self, *relation_names: str) -> "QueryBuilder":
        """
        Eager load related objects — prevents N+1 queries.
        Loads all related records in a single batch query per relation.

        Args:
            relation_names : names of LazyRelation attributes to preload

        Usage:
            authors = Author.query().include("books").all()
            for a in authors:
                print(a.books)  # no extra queries

            # Multiple relations
            authors = Author.query().include("books", "profile").all()
        """
        self._includes.extend(relation_names)
        return self

    def group_by(self, *fields: str) -> "QueryBuilder":
        """
        Add GROUP BY clause.

        Args:
            fields : one or more field names to group by

        Usage:
            Order.query()
                 .group_by("user_id")
                 .count()

            Order.query()
                 .group_by("user_id", "status")
                 .all()
        """
        self._group_by.extend(fields)
        return self

    def having(self, condition: str,
               *params) -> "QueryBuilder":
        """
        Add HAVING clause — filter on aggregated values.
        Must be used with group_by().

        Args:
            condition : SQL condition string e.g. "COUNT(*) > 5"
            params    : optional parameter values for %s placeholders

        Usage:
            Order.query()
                 .group_by("user_id")
                 .having("COUNT(*) > 2")
                 .all()

            Order.query()
                 .group_by("status")
                 .having("SUM(total) > %s", 1000)
                 .all()
        """
        self._having.append(condition)
        if params:
            self._wheres.append(("", list(params)))
        return self

    def subquery(self, field: str = "*") -> str:
        """
        Return this query as a subquery string.

        Args:
            field : field to select in subquery (default "*")

        Usage:
            active_ids = (User.query()
                              .where("active", True)
                              .subquery("id"))

            Order.query()
                 .where("user_id__in", active_ids)
                 .all()
        """
        sql, params = self._build_sql(select=field)
        # Inline params into SQL for subquery use
        for param in params:
            if isinstance(param, str):
                sql = sql.replace("%s", f"'{param}'", 1)
            elif isinstance(param, bool):
                sql = sql.replace("%s", "1" if param else "0", 1)
            elif param is None:
                sql = sql.replace("%s", "NULL", 1)
            else:
                sql = sql.replace("%s", str(param), 1)
        return "(" + sql.rstrip(";") + ")"

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
        table           = self._model._table
        # Remember whether caller passed the default wildcard (not an aggregate)
        caller_default  = (select == "*")

        # Column projection takes priority (only when not overridden internally)
        if self._columns and caller_default:
            select = ", ".join(self._columns)
        elif self._group_by and caller_default:
            select = ", ".join(self._group_by)

        # DISTINCT only applies on normal SELECT, not on COUNT(*)/aggregates
        keyword = "SELECT DISTINCT" if (self._distinct and caller_default) else "SELECT"
        sql    = keyword + " " + select + " FROM " + table
        params = []

        # JOINs
        for join_clause in self._joins:
            sql += " " + join_clause

        # WHERE — AND conditions + OR group
        and_clauses = [w[0] for w in self._wheres if w[0]]
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

        # GROUP BY
        if self._group_by:
            sql += " GROUP BY " + ", ".join(self._group_by)

        # HAVING
        if self._having:
            sql += " HAVING " + " AND ".join(self._having)

        # ORDER BY
        if self._order:
            sql += " ORDER BY " + self._order + " " + self._order_dir

        # LIMIT / OFFSET
        if self._limit is not None and self._offset is not None:
            sql += " LIMIT " + str(self._limit) + " OFFSET " + str(self._offset)
        elif self._limit is not None:
            sql += " LIMIT " + str(self._limit)
        elif self._offset is not None:
            sql += " LIMIT 18446744073709551615 OFFSET " + str(self._offset)

        return sql, params

    # ── Execution ────────────────────────────────────────────────── #

    def all(self) -> list:
        """Execute and return all matching rows as list of dicts."""
        sql, params = self._build_sql()
        rows        = self._model._fetch(sql + ";", params)

        if not rows or not self._includes:
            return rows

        # Deduplicate rows by primary key before eager loading
        pk_field = next(
            (f for f, field in self._model._fields.items()
             if field.primary_key), "id"
        )
        seen = {}
        deduped = []
        for row in rows:
            pk_val = row._data.get(pk_field)
            if pk_val not in seen:
                seen[pk_val] = row
                deduped.append(row)
        rows = deduped

        # Eager load each included relation
        for relation_name in self._includes:
            descriptor = None
            for cls in type.mro(self._model):
                if relation_name in cls.__dict__:
                    descriptor = cls.__dict__[relation_name]
                    break

            if not isinstance(descriptor, LazyRelation):
                continue

            related_model = descriptor._resolve_model(self._model)
            fk            = descriptor.foreign_key or \
                            f"{self._model.__name__.lower()}_id"

            # Collect all PKs from loaded rows
            pk_values = [r._data.get(pk_field) for r in rows
                         if r._data.get(pk_field)]

            if not pk_values:
                continue

            # Single batch query for all related records
            related_rows = related_model.query().where(
                fk + "__in", pk_values
            ).all()

            # Group by FK value
            grouped = {}
            for rrow in related_rows:
                fk_val = rrow._data.get(fk)
                if fk_val not in grouped:
                    grouped[fk_val] = []
                grouped[fk_val].append(rrow)

            # Attach to each parent row
            cache_key = f"_lazy_{relation_name}"
            for row in rows:
                pk_val = row._data.get(pk_field)
                dict.__setitem__(
                    row._data,
                    cache_key,
                    grouped.get(pk_val, [])
                )

        return rows

    def first(self) -> Optional[dict]:
        """Return first matching row or None."""
        original_limit = self._limit
        self._limit    = 1
        sql, params    = self._build_sql()
        self._limit    = original_limit
        rows = self._model._fetch(sql + ";", params)
        return rows[0] if rows else None

    def count(self) -> int:
        """Return count of matching rows or groups."""
        if self._group_by:
            # Count number of groups using subquery
            inner_sql, params = self._build_sql(
                select=", ".join(self._group_by)
            )
            sql  = "SELECT COUNT(*) FROM (" + inner_sql + ") AS _grp"
            rows = self._model._fetch(sql + ";", params)
        else:
            sql, params = self._build_sql(select="COUNT(*)")
            rows = self._model._fetch(sql + ";", params)
        if rows:
            val = list(rows[0]._data.values())[0]
            return int(val)
        return 0

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

    def update(self, **kwargs) -> int:
        """Bulk-update matching rows. Returns affected row count.

        Example:
            User.query().where("active", False).update(role="guest")
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

        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql + ";", params)
            return cur.rowcount

    def delete(self) -> int:
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

        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql + ";", params)
            return cur.rowcount

    def paginate(self, page: int = 1, per_page: int = 20) -> dict:
        """Return a paginated result dict.

        Args:
            page     : 1-based page number (default 1)
            per_page : rows per page (default 20)

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
        total  = self.count()
        pages  = max(1, -(-total // per_page))   # ceiling division
        offset = (page - 1) * per_page
        data   = self.limit(per_page).offset(offset).all()
        return {
            "data"    : data,
            "total"   : total,
            "pages"   : pages,
            "page"    : page,
            "per_page": per_page,
        }

    def __repr__(self):
        sql, params = self._build_sql()
        return f"<QueryBuilder sql={sql!r} params={params!r}>"

# ------------------------------------------------------------------ #
#  ModelInstance — row data + relationship methods                     #
# ------------------------------------------------------------------ #

class ModelInstance:
    """
    Wraps a row dict and gives it relationship methods.
    Returned by BaseModel.get(), first(), and filter() rows.

    Behaves like a dict:
        user["name"]       ← works
        user.get("name")   ← works
        dict(user)         ← works
    Also supports attribute access:
        user.name          ← works
    """

    def __init__(self, model_class, data: dict):
        object.__setattr__(self, "_model_class", model_class)
        object.__setattr__(self, "_data", data)

    # ── Dict-like access ─────────────────────────────────────────── #

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def get(self, key, default=None):
        return self._data.get(key, default)

    # ── Attribute access ─────────────────────────────────────────── #

    def __getattr__(self, key):
        data       = object.__getattribute__(self, "_data")
        model_cls  = object.__getattribute__(self, "_model_class")

        # Check for LazyRelation descriptor on model class first
        for cls in type.mro(model_cls):
            if key in cls.__dict__:
                descriptor = cls.__dict__[key]
                if hasattr(descriptor, "__get__"):
                    return descriptor.__get__(self, type(self))

        # Fall back to _data dict
        if key in data:
            return data[key]

        raise AttributeError(
            f"'{model_cls.__name__}' has no attribute '{key}'"
        )

    def __setattr__(self, key, value):
        self._data[key] = value

    # ── Relationships (delegated to model class) ──────────────────── #

    def has_many(self, related_model, foreign_key: str = None) -> list:
        fk  = foreign_key or f"{self._model_class.__name__.lower()}_id"
        pk  = self._get_pk_value()
        return related_model.query().where(fk, pk).all()

    def belongs_to(self, related_model, foreign_key: str = None):
        fk     = foreign_key or f"{related_model.__name__.lower()}_id"
        fk_val = self._data.get(fk)
        if fk_val is None:
            return None
        return related_model.get(id=fk_val)

    def many_to_many(
        self,
        related_model,
        join_table: str,
        source_key: str = None,
        target_key: str = None,
    ) -> list:
        src_key = source_key or f"{self._model_class.__name__.lower()}_id"
        tgt_key = target_key or f"{related_model.__name__.lower()}_id"
        pk      = self._get_pk_value()
        tbl     = related_model._table
        sql = (
            f"SELECT {tbl}.* FROM {tbl} "
            f"INNER JOIN {join_table} "
            f"ON {tbl}.id = {join_table}.{tgt_key} "
            f"WHERE {join_table}.{src_key} = %s;"
        )
        return related_model._fetch(sql, [pk])

    def to_dict(self, exclude: list = None) -> dict:
        """Convert ModelInstance to a plain Python dict."""
        exclude = exclude or []
        return {k: v for k, v in self._data.items() if k not in exclude}

    def to_json(self, exclude: list = None, indent: int = None) -> str:
        """Convert ModelInstance to a JSON string."""
        import json
        from datetime import date, datetime

        def serializer(obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            raise TypeError(
                "Object of type " + type(obj).__name__ +
                " is not JSON serializable"
            )

        return json.dumps(
            self.to_dict(exclude=exclude),
            default=serializer,
            indent=indent,
            ensure_ascii=False,
        )

    def to_json_dict(self, exclude: list = None) -> dict:
        """Convert to a JSON-safe dict (dates as ISO strings)."""
        import json
        return json.loads(self.to_json(exclude=exclude))

    def _get_pk_value(self):
        comp_pk = getattr(self._model_class, "_composite_pk", None)
        if comp_pk:
            return {f: self._data.get(f) for f in comp_pk}
        for fname, field in self._model_class._fields.items():
            if field.primary_key:
                return self._data.get(fname)
        raise ValueError(
            f"No primary key on {self._model_class.__name__}."
        )

    def __repr__(self):
        return (
            f"<{self._model_class.__name__} "
            f"{self._data}>"
        )

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
            name.lower() + "s"
        )
        # Composite PK support — __pk__ = ("col1", "col2")
        namespace["_composite_pk"] = namespace.get("__pk__", None)
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
        exist_clause = "IF NOT EXISTS " if if_not_exists else ""
        col_defs    = []
        dialect     = db.dialect
        has_comp_pk = bool(getattr(cls, "_composite_pk", None))

        for fname, field in cls._fields.items():
            if has_comp_pk and field.primary_key:
                # Skip inline PRIMARY KEY — will add as table constraint
                sql_def = field.to_sql_def(dialect)
                sql_def = (sql_def
                           .replace(" PRIMARY KEY AUTO_INCREMENT", " NOT NULL AUTO_INCREMENT")
                           .replace(" PRIMARY KEY", " NOT NULL")
                           .replace(" SERIAL PRIMARY KEY", " SERIAL")
                           .replace("SERIAL", "INTEGER NOT NULL"))
                col_defs.append("  " + fname + " " + sql_def)
            else:
                col_defs.append("  " + fname + " " + field.to_sql_def(dialect))

        # Add composite PK constraint
        if has_comp_pk:
            pk_cols = getattr(cls, "_composite_pk")
            if dialect in ("yugabyte", "postgres"):
                pk_clause = "PRIMARY KEY (" + ", ".join(f'"{c}"' for c in pk_cols) + ")"
            else:
                pk_clause = "PRIMARY KEY (" + ", ".join(f"`{c}`" for c in pk_cols) + ")"
            col_defs.append("  " + pk_clause)

        col_separator = ",\n"
        if db.dialect in ("yugabyte", "postgres"):
            sql = (
                'CREATE TABLE ' + exist_clause + '"' + cls._table + '"' +
                " (\n" + col_separator.join(col_defs) + "\n);"
            )
        else:
            sql = (
                "CREATE TABLE " + exist_clause + cls._table +
                " (\n" + col_separator.join(col_defs) + "\n);"
            )
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql)
            # Create single-field indexes from field definitions
            for fname, field in cls._fields.items():
                if getattr(field, "index", False) and not field.primary_key \
                        and not getattr(field, "unique", False):
                    unique    = ""
                    idx_name  = f"idx_{cls._table}_{fname}".replace("idx_idx_", "idx_")
                    if db.dialect in ("yugabyte", "postgres"):
                        idx_sql = (
                            f'CREATE {unique}INDEX IF NOT EXISTS "{idx_name}" '
                            f'ON "{cls._table}" ("{fname}")'
                        )
                    else:
                        idx_sql = (
                            f"CREATE {unique}INDEX `{idx_name}` "
                            f"ON `{cls._table}` (`{fname}`)"
                        )
                    try:
                        cur.execute(idx_sql)
                    except Exception:
                        pass  # index may already exist

            # Create composite indexes from __indexes__
            for idx in getattr(cls, "__indexes__", []):
                fields    = idx.get("fields", [])
                unique    = "UNIQUE " if idx.get("unique", False) else ""
                idx_name  = idx.get("name") or f"idx_{cls._table}_{'_'.join(fields)}"
                if not fields:
                    continue
                if db.dialect in ("yugabyte", "postgres"):
                    cols    = ", ".join(f'"{f}"' for f in fields)
                    idx_sql = (
                        f'CREATE {unique}INDEX IF NOT EXISTS "{idx_name}" '
                        f'ON "{cls._table}" ({cols})'
                    )
                else:
                    cols    = ", ".join(f"`{f}`" for f in fields)
                    idx_sql = (
                        f"CREATE {unique}INDEX `{idx_name}` "
                        f"ON `{cls._table}` ({cols})"
                    )
                try:
                    cur.execute(idx_sql)
                except Exception:
                    pass

        print(f"[mydborm] Table '{cls._table}' ready.")

    @classmethod
    def drop_table(cls, if_exists: bool = True) -> None:
        """Drop the database table for this model."""
        exist_clause = "IF EXISTS" if if_exists else ""
        if db.dialect in ("yugabyte", "postgres"):
            sql = 'DROP TABLE ' + exist_clause + ' "' + cls._table + '";'
        else:
            sql = "DROP TABLE " + exist_clause + " " + cls._table + ";"
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql)
        print(f"[mydborm] Table '{cls._table}' dropped.")

    @classmethod
    def create_index(
        cls,
        fields: list,
        name: str = None,
        unique: bool = False,
    ) -> str:
        """
        Create an index on one or more columns.

        Args:
            fields : list of field names to index
            name   : optional index name (auto-generated if not provided)
            unique : if True creates a UNIQUE index

        Returns:
            Index name created.

        Usage:
            Product.create_index(["category"])
            Product.create_index(["category", "price"], name="idx_cat_price")
            Product.create_index(["email"], unique=True)
        """
        if not fields:
            raise ValueError("create_index requires at least one field.")
        unique_kw = "UNIQUE " if unique else ""
        idx_name  = name or f"idx_{cls._table}_{'_'.join(fields)}"
        if db.dialect in ("yugabyte", "postgres"):
            cols = ", ".join(f'"{f}"' for f in fields)
            sql  = (
                f'CREATE {unique_kw}INDEX IF NOT EXISTS "{idx_name}" '
                f'ON "{cls._table}" ({cols})'
            )
        else:
            cols = ", ".join(f"`{f}`" for f in fields)
            sql  = (
                f"CREATE {unique_kw}INDEX `{idx_name}` "
                f"ON `{cls._table}` ({cols})"
            )
        with db.connect() as conn:
            conn.cursor().execute(sql)
        print(f"[mydborm] Index '{idx_name}' created on '{cls._table}'")
        return idx_name

    @classmethod
    def drop_index(cls, name: str) -> None:
        """
        Drop an index by name.

        Args:
            name: index name to drop

        Usage:
            Product.drop_index("idx_products_category")
        """
        if db.dialect in ("yugabyte", "postgres"):
            sql = f'DROP INDEX IF EXISTS "{name}"'
        else:
            sql = f"DROP INDEX `{name}` ON `{cls._table}`"
        with db.connect() as conn:
            conn.cursor().execute(sql)
        print(f"[mydborm] Index '{name}' dropped")

    @classmethod
    def list_indexes(cls) -> list:
        """
        List all indexes on this model's table.

        Returns:
            List of dicts with index info.

        Usage:
            indexes = Product.list_indexes()
            for idx in indexes:
                print(idx["name"], idx["columns"], idx["unique"])
        """
        with db.connect() as conn:
            cur = conn.cursor()
            if db.dialect in ("yugabyte", "postgres"):
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = %s
                """, [cls._table])
                rows = cur.fetchall()
                return [
                    {"name": r[0], "definition": r[1],
                     "unique": "UNIQUE" in (r[1] or "").upper()}
                    for r in rows
                ]
            else:
                cur.execute(f"SHOW INDEX FROM `{cls._table}`")
                rows    = cur.fetchall()
                indexes = {}
                for row in rows:
                    name   = row[2]
                    col    = row[4]
                    unique = row[1] == 0
                    if name not in indexes:
                        indexes[name] = {
                            "name"    : name,
                            "columns" : [],
                            "unique"  : unique,
                            "primary" : name == "PRIMARY",
                        }
                    indexes[name]["columns"].append(col)
                return list(indexes.values())

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
        validated   = {}
        comp_pk     = getattr(cls, "_composite_pk", None)
        for fname, field in cls._fields.items():
            if field.primary_key and not comp_pk:
                continue   # skip auto-increment PK
            if comp_pk and fname in comp_pk:
                # composite PK fields are required — include them
                value = kwargs.get(fname)
                if value is None:
                    raise ValueError(
                        f"Composite PK field '{fname}' is required."
                    )
                validated[fname] = value
                continue
            value = kwargs.get(fname, field.default)
            validated[fname] = field.validate(value)

        # Run model-level validators if defined
        if hasattr(cls, "__validators__"):
            for validator_fn in cls.__validators__:
                validator_fn(validated)

        # ── Lifecycle hook: before_create ──────────────────────────────
        if hasattr(cls, "before_create") and callable(
                getattr(cls, "before_create")):
            result = cls.before_create(validated)
            if result is not None:
                validated = result

        columns      = ", ".join(validated.keys())
        placeholders = ", ".join(["%s"] * len(validated))
        sql = (
            f"INSERT INTO {cls._table} ({columns}) "
            f"VALUES ({placeholders});"
        )
        comp_pk = getattr(cls, "_composite_pk", None)
        with db.connect() as conn:
            cur = conn.cursor()
            if db.dialect in ("yugabyte", "postgres") and not comp_pk:
                sql = sql.rstrip(";") + " RETURNING id;"
                cur.execute(sql, list(validated.values()))
                row    = cur.fetchone()
                new_id = row[0] if row else None
            else:
                cur.execute(sql, list(validated.values()))
                if comp_pk:
                    # Return dict of composite PK values
                    new_id = {f: validated[f] for f in comp_pk if f in validated}
                else:
                    new_id = cur.lastrowid

        # ── Lifecycle hook: after_create ───────────────────────────────
        if hasattr(cls, "after_create") and callable(
                getattr(cls, "after_create")):
            cls.after_create(new_id, validated)

        return new_id

    # ------------------------------------------------------------------ #
    #  Read                                                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _fetch(cls, sql: str, params: list = None) -> list:
        """Internal: run a SELECT and return list of ModelInstance."""
        json_fields = [
            fname for fname, field in cls._fields.items()
            if isinstance(field, JSONField)
        ]
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or [])
            columns = [desc[0] for desc in cur.description]
            results = []
            for row in cur.fetchall():
                data = dict(zip(columns, row))
                # JSONField stores JSON as text — parse it back into a
                # dict/list here. psycopg2 already auto-parses JSONB
                # columns on its own, so only strings need decoding.
                for fname in json_fields:
                    value = data.get(fname)
                    if isinstance(value, str):
                        try:
                            data[fname] = json.loads(value)
                        except ValueError:
                            pass
                results.append(ModelInstance(cls, data))
            return results

    @classmethod
    def all(cls) -> list:
        """Return all rows as list of dicts."""
        return cls._fetch(f"SELECT * FROM {cls._table};")

    @classmethod
    def get(cls, **kwargs) -> Optional[dict]:
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
        # ── Lifecycle hook: before_update ──────────────────────────────
        if hasattr(cls, "before_update") and callable(
                getattr(cls, "before_update")):
            result = cls.before_update(data, where_kwargs)
            if result is not None:
                data = result

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
            rows_affected = cur.rowcount

        # ── Lifecycle hook: after_update ───────────────────────────────
        if hasattr(cls, "after_update") and callable(
                getattr(cls, "after_update")):
            cls.after_update(rows_affected, data, where_kwargs)

        return rows_affected

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
        # ── Lifecycle hook: before_delete ──────────────────────────────
        if hasattr(cls, "before_delete") and callable(
                getattr(cls, "before_delete")):
            cls.before_delete(kwargs)

        where, values = cls._build_where(kwargs)
        sql = f"DELETE FROM {cls._table} WHERE {where};"
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, values)
            rows_deleted = cur.rowcount

        # ── Lifecycle hook: after_delete ───────────────────────────────
        if hasattr(cls, "after_delete") and callable(
                getattr(cls, "after_delete")):
            cls.after_delete(rows_deleted, kwargs)

        return rows_deleted

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
    def from_dict(cls, data: dict) -> "ModelInstance":
        """
        Create a ModelInstance from a plain dict WITHOUT saving to DB.

        Usage:
            user = User.from_dict({"id": 1, "username": "alice"})
            print(user.username)
        """
        return ModelInstance(cls, dict(data))

    @classmethod
    def from_json(cls, json_str: str) -> "ModelInstance":
        """
        Create a ModelInstance from a JSON string WITHOUT saving to DB.

        Usage:
            user = User.from_json('{"id": 1, "username": "alice"}')
        """
        import json
        return cls.from_dict(json.loads(json_str))
    
    @classmethod
    def validate_schema(cls, strict: bool = False) -> dict:
        """
        Compare model field definitions against the live DB schema.

        Args:
            strict (bool): if True raises SchemaError on mismatch

        Returns:
            {
                "table"         : "users",
                "valid"         : True | False,
                "missing_in_db" : ["phone"],
                "extra_in_db"   : ["old_col"],
                "matched"       : ["id", "username", ...]
            }

        Usage:
            result = User.validate_schema()
            User.validate_schema(strict=True)
        """
        from .exceptions import SchemaError
        from .migrations import get_live_schema

        live          = get_live_schema(cls._table)
        model_cols    = set(cls._fields.keys())
        live_cols     = set(live.keys())
        missing_in_db = list(model_cols - live_cols)
        extra_in_db   = list(live_cols  - model_cols)
        matched       = list(model_cols & live_cols)
        valid         = not missing_in_db and not extra_in_db

        result = {
            "table":          cls._table,
            "valid":          valid,
            "missing_in_db":  missing_in_db,
            "extra_in_db":    extra_in_db,
            "matched":        matched,
        }

        if strict and not valid:
            raise SchemaError(
                "Schema mismatch for table '" + cls._table + "'",
                table           = cls._table,
                missing_columns = missing_in_db,
                extra_columns   = extra_in_db,
            )

        return result

    @classmethod
    def schema_info(cls) -> dict:
        """
        Return model schema information — fields, types, constraints.

        Usage:
            info = User.schema_info()
            for field, details in info["fields"].items():
                print(field, details)
        """
        fields_info = {}
        for fname, field in cls._fields.items():
            fields_info[fname] = {
                "type":        field.__class__.__name__,
                "sql_type":    field.sql_type,
                "primary_key": field.primary_key,
                "nullable":    field.nullable,
                "unique":      field.unique,
                "default":     field.default,
            }

        return {
            "table":    cls._table,
            "dialect":  db.dialect if db._config else "not configured",
            "fields":   fields_info,
            "pk_field": next(
                (f for f, field in cls._fields.items()
                 if field.primary_key), None
            ),
        }

    @classmethod
    def query(cls) -> "QueryBuilder":
        """
        Return a QueryBuilder for this model.

        Usage:
            User.query().where("active", True).order_by("name").all()
        """
        return QueryBuilder(cls)

    # ------------------------------------------------------------------ #
    #  Relationships                                                     #
    # ------------------------------------------------------------------ #

    def has_many(self, related_model, foreign_key: str = None) -> list:
        """
        Return all related records where foreign_key = self.pk.

        Usage:
            author = Author.get(id=1)
            books  = author.has_many(Book, foreign_key="author_id")

        If foreign_key is omitted, defaults to:
            <this_classname_lower>_id   e.g. "author_id"
        """
        fk  = foreign_key or f"{self.__class__.__name__.lower()}_id"
        pk  = self._get_pk_value()
        return related_model.query().where(fk, pk).all()

    def belongs_to(self, related_model, foreign_key: str = None) -> Optional[dict]:
        """
        Return the parent record this instance belongs to.

        Usage:
            book   = Book.get(id=1)
            author = book.belongs_to(Author, foreign_key="author_id")

        If foreign_key is omitted, defaults to:
            <related_classname_lower>_id   e.g. "author_id"
        """
        fk      = foreign_key or f"{related_model.__name__.lower()}_id"
        fk_val  = self._data.get(fk)
        if fk_val is None:
            return None
        return related_model.get(id=fk_val)

    def many_to_many(
        self,
        related_model,
        join_table: str,
        source_key: str = None,
        target_key: str = None,
    ) -> list:
        """
        Return all related records via a join table.

        Usage:
            student = Student.get(id=1)
            courses = student.many_to_many(
                Course,
                join_table="student_courses",
                source_key="student_id",
                target_key="course_id"
            )

        If source_key / target_key are omitted they default to:
            <this_classname_lower>_id   and
            <related_classname_lower>_id
        """
        src_key  = source_key or f"{self.__class__.__name__.lower()}_id"
        tgt_key  = target_key or f"{related_model.__name__.lower()}_id"
        pk       = self._get_pk_value()
        tbl      = related_model._table

        sql = (
            f"SELECT {tbl}.* FROM {tbl} "
            f"INNER JOIN {join_table} "
            f"ON {tbl}.id = {join_table}.{tgt_key} "
            f"WHERE {join_table}.{src_key} = %s;"
        )
        return related_model._fetch(sql, [pk])

    # ------------------------------------------------------------------ #
    #  Instance helpers                                                    #
    # ------------------------------------------------------------------ #

    def _get_pk_value(self):
        """Return the primary key value for this instance."""
        comp_pk = getattr(self.__class__, "_composite_pk", None)
        if comp_pk:
            return {f: self._data.get(f) for f in comp_pk}
        for fname, field in self._fields.items():
            if field.primary_key:
                return self._data.get(fname)
        raise ValueError(
            f"No primary key defined on {self.__class__.__name__}."
        )

    # ------------------------------------------------------------------ #
    #  Bulk operations                                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def bulk_create(cls, records: list) -> int:
        """
        Insert multiple rows in a single query.
        Returns number of inserted rows.

        Usage:
            User.bulk_create([
                {"username": "alice", "email": "alice@example.com"},
                {"username": "bob",   "email": "bob@example.com"},
            ])
        """
        if not records:
            return 0

        # Validate all records and collect columns from first record
        first = {
            k: v for k, v in records[0].items()
            if k in cls._fields and not cls._fields[k].primary_key
        }
        columns = list(first.keys())

        # Validate each record
        validated_rows = []
        for record in records:
            row = {}
            for col in columns:
                field = cls._fields.get(col)
                if field:
                    row[col] = field.validate(record.get(col, field.default))
                else:
                    row[col] = record.get(col)
            validated_rows.append(row)

        col_str      = ", ".join(columns)
        placeholders = "(" + ", ".join(["%s"] * len(columns)) + ")"
        all_placeholders = ", ".join([placeholders] * len(validated_rows))
        sql = (
            "INSERT INTO " + cls._table +
            " (" + col_str + ") VALUES " + all_placeholders + ";"
        )

        # Flatten all values into a single list
        flat_values = []
        for row in validated_rows:
            flat_values.extend(row.values())

        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, flat_values)
            return cur.rowcount

    @classmethod
    def bulk_update(cls, records: list, key: str = "id") -> int:
        """
        Update multiple rows. Each record must contain the key field.
        Returns total number of affected rows.

        Usage:
            User.bulk_update([
                {"id": 1, "active": False},
                {"id": 2, "active": False},
            ])
        """
        if not records:
            return 0

        total = 0
        with db.connect() as conn:
            cur = conn.cursor()
            for record in records:
                key_val = record.get(key)
                if key_val is None:
                    raise ValueError(
                        "bulk_update: every record must include "
                        "the key field '" + key + "'."
                    )
                data = {k: v for k, v in record.items() if k != key}
                if not data:
                    continue
                set_clause = ", ".join(k + " = %s" for k in data.keys())
                sql = (
                    "UPDATE " + cls._table +
                    " SET " + set_clause +
                    " WHERE " + key + " = %s;"
                )
                cur.execute(sql, list(data.values()) + [key_val])
                total += cur.rowcount
        return total

    @classmethod
    def bulk_upsert(
        cls,
        records: list,
        conflict_key: str = "id",
        update_fields: list = None,
        create_index: bool = True,
    ) -> int:
        """
        Insert records or update on conflict — dialect aware.

        MySQL → INSERT ... ON DUPLICATE KEY UPDATE
        YugabyteDB → INSERT ... ON CONFLICT DO UPDATE

        Args:
            records (list): list of dicts to insert/update
            conflict_key (str): unique field that determines conflict
            update_fields (list): fields to update on conflict
            create_index (bool): auto-create UNIQUE index on conflict_keys

        Returns:
            number of affected rows
        """
        if not records:
            return 0

        dialect = db.dialect

        # Auto-create UNIQUE index on conflict_key if not primary key
        field = cls._fields.get(conflict_key)
        if create_index and field and not field.primary_key:
            idx_name = "uq_" + cls._table + "_" + conflict_key
            try:
                with db.connect() as conn:
                    cur = conn.cursor()
                    if dialect == "mysql":
                        cur.execute(
                            "SELECT COUNT(*) FROM information_schema.statistics "
                            "WHERE table_schema = DATABASE() "
                            "AND table_name = %s "
                            "AND index_name = %s",
                            [cls._table, idx_name]
                        )
                        if cur.fetchone()[0] == 0:
                            cur.execute(
                                "ALTER TABLE `" + cls._table +
                                "` ADD UNIQUE INDEX `" + idx_name +
                                "` (`" + conflict_key + "`)"
                            )
                    else:
                        cur.execute(
                            "SELECT COUNT(*) FROM pg_indexes "
                            "WHERE tablename = %s AND indexname = %s",
                            [cls._table, idx_name]
                        )
                        if cur.fetchone()[0] == 0:
                            cur.execute(
                                'CREATE UNIQUE INDEX "' + idx_name +
                                '" ON "' + cls._table +
                                '" ("' + conflict_key + '")'
                            )
            except Exception:
                pass  # index may already exist

        # Collect columns
        first   = {
            k: v for k, v in records[0].items()
            if k in cls._fields and not cls._fields[k].primary_key
        }
        columns = list(first.keys())

        if update_fields is None:
            update_fields = [c for c in columns if c != conflict_key]

        if not update_fields:
            return cls.bulk_create(records)

        # Validate
        validated_rows = []
        for record in records:
            row = {}
            for col in columns:
                field = cls._fields.get(col)
                if field:
                    row[col] = field.validate(
                        record.get(col, field.default)
                    )
                else:
                    row[col] = record.get(col)
            validated_rows.append(row)

        col_str      = ", ".join(columns)
        placeholders = "(" + ", ".join(["%s"] * len(columns)) + ")"
        all_ph       = ", ".join([placeholders] * len(validated_rows))

        flat_values = []
        for row in validated_rows:
            flat_values.extend(row.values())

        if dialect == "mysql":
            update_clause = ", ".join(
                "`" + f + "` = VALUES(`" + f + "`)"
                for f in update_fields
            )
            sql = (
                "INSERT INTO `" + cls._table + "` "
                "(" + col_str + ") VALUES " + all_ph +
                " ON DUPLICATE KEY UPDATE " + update_clause + ";"
            )
        else:
            update_clause = ", ".join(
                '"' + f + '" = EXCLUDED."' + f + '"'
                for f in update_fields
            )
            sql = (
                'INSERT INTO "' + cls._table + '" '
                "(" + col_str + ") VALUES " + all_ph +
                ' ON CONFLICT ("' + conflict_key + '") '
                "DO UPDATE SET " + update_clause + ";"
            )

        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, flat_values)
            return cur.rowcount

    @classmethod
    def bulk_delete(cls, ids: list, key: str = "id") -> int:
        """
        Delete multiple rows by a list of key values.
        Returns number of deleted rows.

        Usage:
            User.bulk_delete([1, 2, 3])
            User.bulk_delete(["alice", "bob"], key="username")
        """
        if not ids:
            return 0

        placeholders = ", ".join(["%s"] * len(ids))
        sql = (
            "DELETE FROM " + cls._table +
            " WHERE " + key + " IN (" + placeholders + ");"
        )
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, ids)
            return cur.rowcount

    def __repr__(self):
        return f"<{self.__class__.__name__} table={self._table!r}>"



