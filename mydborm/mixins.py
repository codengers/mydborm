# -*- coding: utf-8 -*-
# =============================================================================
# File        : mydborm/mixins.py
# Project     : mydborm
# Version     : 1.3.0
# Description : Mixins — SoftDeleteMixin, AuditMixin, TimestampMixin
# =============================================================================

from __future__ import annotations
import datetime
from typing import Optional


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_dialect_cls():
    from .db import db
    from .dialects import get_dialect
    return get_dialect(db.dialect)


def _add_col_to_db(table: str, col: str, col_type: str):
    """Add a column to an existing table if it doesn't exist."""
    from .db import db
    from .migrations import get_live_schema
    schema = get_live_schema(table)
    if schema and col not in schema:
        dialect = _get_dialect_cls()
        sql = dialect.add_column_sql(table, col, col_type)
        with db.connect() as conn:
            conn.cursor().execute(sql)
        print(f"[mydborm] Added '{col}' to '{table}'")


def _inject_field(cls, field_name: str, field_obj):
    """Inject a field into a model class _fields dict."""
    if field_name not in cls._fields:
        field_obj.name = field_name
        cls._fields[field_name] = field_obj


# ================================================================== #
#  SoftDeleteMixin                                                     #
# ================================================================== #

class SoftDeleteMixin:
    """
    Adds soft-delete support to a BaseModel.

    Usage:
        class Post(BaseModel, SoftDeleteMixin):
            __tablename__ = "posts"
            id    = IntField(primary_key=True)
            title = StrField(max_length=200, nullable=False)

        Post.create_table()

        pid = Post.create(title="Hello")
        Post.soft_delete(id=pid)       # sets deleted_at = now()
        Post.all()                     # excludes deleted rows
        Post.all_with_deleted()        # includes deleted rows
        Post.restore(id=pid)           # clears deleted_at
        Post.purge(id=pid)             # permanent delete
    """

    SOFT_DELETE_FIELD = "deleted_at"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from .fields import DateTimeField
        f = DateTimeField(nullable=True)
        _inject_field(cls, cls.SOFT_DELETE_FIELD, f)
        # Inject methods directly onto subclass to override BaseModel MRO
        cls.all              = classmethod(SoftDeleteMixin.all.__func__)
        cls.filter           = classmethod(SoftDeleteMixin.filter.__func__)
        cls.get              = classmethod(SoftDeleteMixin.get.__func__)
        cls.all_with_deleted = classmethod(SoftDeleteMixin.all_with_deleted.__func__)
        cls.only_deleted     = classmethod(SoftDeleteMixin.only_deleted.__func__)
        cls.soft_delete      = classmethod(SoftDeleteMixin.soft_delete.__func__)
        cls.restore          = classmethod(SoftDeleteMixin.restore.__func__)
        cls.purge            = classmethod(SoftDeleteMixin.purge.__func__)
        cls.purge_all_deleted = classmethod(SoftDeleteMixin.purge_all_deleted.__func__)
        cls.count            = classmethod(SoftDeleteMixin.count.__func__)
        cls.exists           = classmethod(SoftDeleteMixin.exists.__func__)

    @classmethod
    def create_table(cls, if_not_exists: bool = True):
        from .fields import DateTimeField
        _inject_field(cls, cls.SOFT_DELETE_FIELD, DateTimeField(nullable=True))
        super().create_table(if_not_exists=if_not_exists)
        _add_col_to_db(cls._table, cls.SOFT_DELETE_FIELD, "DATETIME NULL")

    @classmethod
    def _qb(cls):
        """Return a fresh QueryBuilder with soft-delete field injected."""
        from .fields import DateTimeField
        from .model import QueryBuilder
        _inject_field(cls, cls.SOFT_DELETE_FIELD, DateTimeField(nullable=True))
        return QueryBuilder(cls)

    @classmethod
    def all(cls) -> list:
        """Return all non-deleted rows."""
        return cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True).all()

    @classmethod
    def filter(cls, **kwargs) -> list:
        """Return non-deleted rows matching kwargs."""
        q = cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True)
        for k, v in kwargs.items():
            q = q.where(k, v)
        return q.all()

    @classmethod
    def get(cls, **kwargs):
        """Get a single non-deleted row."""
        q = cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True)
        for k, v in kwargs.items():
            q = q.where(k, v)
        return q.first()

    @classmethod
    def all_with_deleted(cls) -> list:
        """Return ALL rows including soft-deleted."""
        return cls._qb().all()

    @classmethod
    def only_deleted(cls) -> list:
        """Return ONLY soft-deleted rows."""
        return cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", False).all()

    @classmethod
    def soft_delete(cls, **kwargs) -> int:
        """Soft-delete rows — sets deleted_at = now()."""
        from .model import BaseModel
        return BaseModel.update.__func__(
            cls, {cls.SOFT_DELETE_FIELD: _now_str()}, **kwargs
        )

    @classmethod
    def restore(cls, **kwargs) -> int:
        """Restore soft-deleted rows — clears deleted_at."""
        from .model import BaseModel
        return BaseModel.update.__func__(
            cls, {cls.SOFT_DELETE_FIELD: None}, **kwargs
        )

    @classmethod
    def purge(cls, **kwargs) -> int:
        """Permanently delete rows."""
        from .model import BaseModel
        return BaseModel.delete.__func__(cls, **kwargs)

    @classmethod
    def purge_all_deleted(cls) -> int:
        """Permanently delete all soft-deleted rows."""
        deleted = cls.only_deleted()
        if not deleted:
            return 0
        pk  = next((n for n, f in cls._fields.items() if f.primary_key), "id")
        ids = [r[pk] for r in deleted]
        placeholders = ", ".join(["%s"] * len(ids))
        from .db import db
        dialect = _get_dialect_cls()
        sql = dialect.delete_sql(cls._table, f"{pk} IN ({placeholders})")
        with db.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, ids)
            return cur.rowcount

    @classmethod
    def count(cls, **kwargs) -> int:
        """Count non-deleted rows."""
        q = cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True)
        for k, v in kwargs.items():
            q = q.where(k, v)
        return q.count()

    @classmethod
    def exists(cls, **kwargs) -> bool:
        """Check if non-deleted row exists."""
        return cls.count(**kwargs) > 0

    def is_deleted(self) -> bool:
        """Check if this instance is soft-deleted."""
        return self._data.get("deleted_at") is not None


# ================================================================== #
#  AuditMixin                                                          #
# ================================================================== #

class AuditMixin:
    """
    Auto-sets created_at, updated_at, created_by, updated_by.

    Usage:
        class Order(BaseModel, AuditMixin):
            __tablename__ = "orders"
            id    = IntField(primary_key=True)
            total = FloatField(nullable=False)

        Order.create_table()
        oid   = Order.create(total=99.99)
        order = Order.get(id=oid)
        print(order["created_at"])   # auto-set

        AuditMixin.set_current_user(42)
        Order.create(total=50.0)     # created_by = 42
    """

    CREATED_AT_FIELD = "created_at"
    UPDATED_AT_FIELD = "updated_at"
    CREATED_BY_FIELD = "created_by"
    UPDATED_BY_FIELD = "updated_by"
    _current_user_id: Optional[int] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from .fields import DateTimeField, IntField
        _inject_field(cls, cls.CREATED_AT_FIELD, DateTimeField(nullable=True))
        _inject_field(cls, cls.UPDATED_AT_FIELD, DateTimeField(nullable=True))
        _inject_field(cls, cls.CREATED_BY_FIELD, IntField(nullable=True))
        _inject_field(cls, cls.UPDATED_BY_FIELD, IntField(nullable=True))
        cls.create     = classmethod(AuditMixin.create.__func__)
        cls.update     = classmethod(AuditMixin.update.__func__)
        cls.get        = classmethod(AuditMixin.get.__func__)
        cls.all        = classmethod(AuditMixin.all.__func__)
        cls.filter     = classmethod(AuditMixin.filter.__func__)

    @classmethod
    def _inject_audit_fields(cls):
        from .fields import DateTimeField, IntField
        _inject_field(cls, cls.CREATED_AT_FIELD, DateTimeField(nullable=True))
        _inject_field(cls, cls.UPDATED_AT_FIELD, DateTimeField(nullable=True))
        _inject_field(cls, cls.CREATED_BY_FIELD, IntField(nullable=True))
        _inject_field(cls, cls.UPDATED_BY_FIELD, IntField(nullable=True))

    @classmethod
    def set_current_user(cls, user_id: Optional[int]):
        """Set current user ID for audit tracking."""
        cls._current_user_id = user_id

    @classmethod
    def create_table(cls, if_not_exists: bool = True):
        cls._inject_audit_fields()
        super().create_table(if_not_exists=if_not_exists)
        col_types = {
            cls.CREATED_AT_FIELD: "DATETIME NULL",
            cls.UPDATED_AT_FIELD: "DATETIME NULL",
            cls.CREATED_BY_FIELD: "INT NULL",
            cls.UPDATED_BY_FIELD: "INT NULL",
        }
        for col, col_type in col_types.items():
            _add_col_to_db(cls._table, col, col_type)

    @classmethod
    def _qb(cls):
        from .model import QueryBuilder
        cls._inject_audit_fields()
        return QueryBuilder(cls)

    @classmethod
    def get(cls, **kwargs):
        cls._inject_audit_fields()
        q = cls._qb()
        for k, v in kwargs.items():
            q = q.where(k, v)
        return q.first()

    @classmethod
    def all(cls) -> list:
        cls._inject_audit_fields()
        return cls._qb().all()

    @classmethod
    def filter(cls, **kwargs) -> list:
        cls._inject_audit_fields()
        q = cls._qb()
        for k, v in kwargs.items():
            q = q.where(k, v)
        return q.all()

    @classmethod
    def create(cls, **kwargs) -> int:
        cls._inject_audit_fields()
        now = _now_str()
        kwargs.setdefault(cls.CREATED_AT_FIELD, now)
        kwargs.setdefault(cls.UPDATED_AT_FIELD, now)
        if cls._current_user_id is not None:
            kwargs.setdefault(cls.CREATED_BY_FIELD, cls._current_user_id)
            kwargs.setdefault(cls.UPDATED_BY_FIELD, cls._current_user_id)
        from .model import BaseModel
        return BaseModel.create.__func__(cls, **kwargs)

    @classmethod
    def update(cls, data: dict, **kwargs) -> int:
        cls._inject_audit_fields()
        data = dict(data)
        data[cls.UPDATED_AT_FIELD] = _now_str()
        if cls._current_user_id is not None:
            data[cls.UPDATED_BY_FIELD] = cls._current_user_id
        from .model import BaseModel
        return BaseModel.update.__func__(cls, data, **kwargs)

    def age(self) -> Optional[datetime.timedelta]:
        """Return age of this record since creation."""
        created = self._data.get("created_at")
        if created is None:
            return None
        if isinstance(created, str):
            created = datetime.datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
        return datetime.datetime.now() - created

    def was_updated(self) -> bool:
        """Return True if record was updated after creation."""
        created = self._data.get("created_at")
        updated = self._data.get("updated_at")
        if created is None or updated is None:
            return False
        return str(created) != str(updated)


# ================================================================== #
#  TimestampMixin                                                      #
# ================================================================== #

class TimestampMixin:
    """
    Lightweight mixin — just created_at and updated_at.

    Usage:
        class Comment(BaseModel, TimestampMixin):
            __tablename__ = "comments"
            id      = IntField(primary_key=True)
            content = TextField(nullable=False)
    """

    CREATED_AT_FIELD = "created_at"
    UPDATED_AT_FIELD = "updated_at"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from .fields import DateTimeField
        _inject_field(cls, cls.CREATED_AT_FIELD, DateTimeField(nullable=True))
        _inject_field(cls, cls.UPDATED_AT_FIELD, DateTimeField(nullable=True))
        cls.create = classmethod(TimestampMixin.create.__func__)
        cls.update = classmethod(TimestampMixin.update.__func__)
        cls.get    = classmethod(TimestampMixin.get.__func__)
        cls.all    = classmethod(TimestampMixin.all.__func__)

    @classmethod
    def _inject_ts_fields(cls):
        from .fields import DateTimeField
        _inject_field(cls, cls.CREATED_AT_FIELD, DateTimeField(nullable=True))
        _inject_field(cls, cls.UPDATED_AT_FIELD, DateTimeField(nullable=True))

    @classmethod
    def create_table(cls, if_not_exists: bool = True):
        cls._inject_ts_fields()
        super().create_table(if_not_exists=if_not_exists)
        for col in [cls.CREATED_AT_FIELD, cls.UPDATED_AT_FIELD]:
            _add_col_to_db(cls._table, col, "DATETIME NULL")

    @classmethod
    def _qb(cls):
        from .model import QueryBuilder
        cls._inject_ts_fields()
        return QueryBuilder(cls)

    @classmethod
    def get(cls, **kwargs):
        cls._inject_ts_fields()
        q = cls._qb()
        for k, v in kwargs.items():
            q = q.where(k, v)
        return q.first()

    @classmethod
    def all(cls) -> list:
        cls._inject_ts_fields()
        return cls._qb().all()

    @classmethod
    def create(cls, **kwargs) -> int:
        cls._inject_ts_fields()
        now = _now_str()
        kwargs.setdefault(cls.CREATED_AT_FIELD, now)
        kwargs.setdefault(cls.UPDATED_AT_FIELD, now)
        from .model import BaseModel
        return BaseModel.create.__func__(cls, **kwargs)

    @classmethod
    def update(cls, data: dict, **kwargs) -> int:
        cls._inject_ts_fields()
        data = dict(data)
        data[cls.UPDATED_AT_FIELD] = _now_str()
        from .model import BaseModel
        return BaseModel.update.__func__(cls, data, **kwargs)