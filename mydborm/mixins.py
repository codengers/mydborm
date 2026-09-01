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

        # Custom queries (pagination, ordering, etc.) also exclude
        # deleted rows by default — use query_with_deleted() to opt out.
        Post.query().order_by("title").paginate(page=1, per_page=20)
        Post.query_with_deleted().all()
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
        cls.query            = classmethod(SoftDeleteMixin.query.__func__)
        cls.query_with_deleted = classmethod(SoftDeleteMixin.query_with_deleted.__func__)
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
    def query(cls):
        """
        Return a QueryBuilder pre-filtered to exclude soft-deleted rows.

        Chain whatever else you need — .order_by(), .paginate(), custom
        .where() calls — the soft-delete filter is already applied, so
        deleted rows can't leak into hand-built queries the way they
        would from a bare QueryBuilder(cls).

        Usage:
            Post.query().order_by("title").paginate(page=1, per_page=20)

        Use query_with_deleted() instead if you need to see everything.
        """
        return cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True)

    @classmethod
    def query_with_deleted(cls):
        """Return a QueryBuilder with no soft-delete filter — sees every row."""
        return cls._qb()

    @classmethod
    def all_with_deleted(cls) -> list:
        """Return ALL rows including soft-deleted."""
        return cls.query_with_deleted().all()

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


# ================================================================== #
#  OptimisticLockMixin                                                 #
# ================================================================== #

class OptimisticLockMixin:
    """
    Adds optimistic-locking (version column) support to a BaseModel.
    update() requires the current version in the WHERE kwargs and raises
    OptimisticLockError if zero rows match — the record was modified
    concurrently (version changed) or no longer exists.

    Usage:
        class Account(BaseModel, OptimisticLockMixin):
            __tablename__ = "accounts"
            id      = IntField(primary_key=True)
            balance = FloatField(nullable=False)

        Account.create_table()
        aid = Account.create(balance=100.0)     # version = 0
        row = Account.get(id=aid)

        Account.update({"balance": 150.0}, id=aid, version=row["version"])
        # succeeds, version becomes 1

        Account.update({"balance": 200.0}, id=aid, version=row["version"])
        # raises OptimisticLockError — row["version"] (0) is now stale
    """

    VERSION_FIELD = "version"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from .fields import IntField
        _inject_field(cls, cls.VERSION_FIELD, IntField(nullable=False, default=0))
        cls.create = classmethod(OptimisticLockMixin.create.__func__)
        cls.update = classmethod(OptimisticLockMixin.update.__func__)

    @classmethod
    def create(cls, **kwargs) -> int:
        kwargs.setdefault(cls.VERSION_FIELD, 0)
        from .model import BaseModel
        return BaseModel.create.__func__(cls, **kwargs)

    @classmethod
    def update(cls, data: dict, **where_kwargs) -> int:
        if cls.VERSION_FIELD not in where_kwargs:
            raise ValueError(
                f"{cls.__name__}.update() requires '{cls.VERSION_FIELD}' in "
                "the WHERE kwargs for optimistic locking — fetch the row "
                "first to get its current version."
            )
        expected_version = where_kwargs[cls.VERSION_FIELD]
        data = dict(data)
        data[cls.VERSION_FIELD] = expected_version + 1
        from .model import BaseModel
        rows_affected = BaseModel.update.__func__(cls, data, **where_kwargs)
        if rows_affected == 0:
            from .exceptions import OptimisticLockError
            raise OptimisticLockError(
                f"{cls.__name__} update failed — no row matched id/version "
                f"(expected version={expected_version}); the record may "
                "have been modified concurrently or no longer exists.",
                model=cls.__name__, expected_version=expected_version,
            )
        return rows_affected


# ================================================================== #
#  ViewModel                                                           #
# ================================================================== #

class ViewModel:
    """
    Marks a BaseModel subclass as mapping a read-only database VIEW
    instead of a table. Reads (query/get/all/filter/count/exists) work
    exactly as normal — a view is queried with SELECT like any table.
    Write methods (create/update/delete/bulk_*) raise ViewReadOnlyError.

    Usage:
        class ActiveUser(BaseModel, ViewModel):
            __tablename__  = "active_users"
            __view_query__ = "SELECT * FROM users WHERE active = 1"
            id       = IntField(primary_key=True)
            username = StrField(max_length=100)

        ActiveUser.create_table()   # CREATE VIEW active_users AS SELECT ...
        ActiveUser.all()            # SELECT * FROM active_users
        ActiveUser.create(...)      # raises ViewReadOnlyError

    If the view already exists in the database, __view_query__ can be
    omitted — just point __tablename__ at it and skip create_table().
    """

    _WRITE_METHODS = (
        "create", "update", "delete",
        "bulk_create", "bulk_update", "bulk_upsert", "bulk_delete",
    )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.create_table = classmethod(ViewModel.create_table.__func__)
        cls.drop_table    = classmethod(ViewModel.drop_table.__func__)
        for name in ViewModel._WRITE_METHODS:
            setattr(cls, name, classmethod(ViewModel._blocked.__func__))

    @classmethod
    def create_table(cls, if_not_exists: bool = True):
        view_query = getattr(cls, "__view_query__", None)
        if not view_query:
            raise ValueError(
                f"{cls.__name__} defines no __view_query__ — can't CREATE VIEW "
                "without a SELECT statement. Set __view_query__, or if the view "
                "already exists in the database just skip create_table()."
            )
        from .db import db
        with db.connect() as conn:
            cur = conn.cursor()
            # MySQL's CREATE VIEW has no IF NOT EXISTS clause (unlike CREATE
            # TABLE) and PostgreSQL/YugabyteDB don't support it either — drop
            # first instead, which is safe since a view carries no data and
            # works identically across all four dialects.
            if if_not_exists:
                cur.execute(f"DROP VIEW IF EXISTS {cls._table}")
            cur.execute(f"CREATE VIEW {cls._table} AS {view_query}")
        print(f"[mydborm] View '{cls._table}' ready.")

    @classmethod
    def drop_table(cls, if_exists: bool = True):
        from .db import db
        exists = "IF EXISTS " if if_exists else ""
        with db.connect() as conn:
            conn.cursor().execute(f"DROP VIEW {exists}{cls._table}")
        print(f"[mydborm] View '{cls._table}' dropped.")

    @classmethod
    def _blocked(cls, *args, **kwargs):
        from .exceptions import ViewReadOnlyError
        raise ViewReadOnlyError(
            f"{cls.__name__} maps a read-only view — write operations "
            "are not supported.",
            model=cls.__name__,
        )


# ================================================================== #
#  AsyncViewModel                                                      #
# ================================================================== #

class AsyncViewModel:
    """Async equivalent of ViewModel, for AsyncBaseModel subclasses."""

    _WRITE_METHODS = (
        "create", "update", "delete",
        "bulk_create", "bulk_update", "bulk_upsert", "bulk_delete",
    )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.create_table = classmethod(AsyncViewModel.create_table.__func__)
        cls.drop_table    = classmethod(AsyncViewModel.drop_table.__func__)
        for name in AsyncViewModel._WRITE_METHODS:
            setattr(cls, name, classmethod(AsyncViewModel._blocked.__func__))

    @classmethod
    async def create_table(cls, if_not_exists: bool = True):
        view_query = getattr(cls, "__view_query__", None)
        if not view_query:
            raise ValueError(
                f"{cls.__name__} defines no __view_query__ — can't CREATE VIEW "
                "without a SELECT statement. Set __view_query__, or if the view "
                "already exists in the database just skip create_table()."
            )
        from .async_db import async_db
        if if_not_exists:
            await async_db.execute(f"DROP VIEW IF EXISTS {cls._table}")
        await async_db.execute(f"CREATE VIEW {cls._table} AS {view_query}")
        print(f"[mydborm] View '{cls._table}' ready.")

    @classmethod
    async def drop_table(cls, if_exists: bool = True):
        from .async_db import async_db
        exists = "IF EXISTS " if if_exists else ""
        await async_db.execute(f"DROP VIEW {exists}{cls._table}")
        print(f"[mydborm] View '{cls._table}' dropped.")

    @classmethod
    async def _blocked(cls, *args, **kwargs):
        from .exceptions import ViewReadOnlyError
        raise ViewReadOnlyError(
            f"{cls.__name__} maps a read-only view — write operations "
            "are not supported.",
            model=cls.__name__,
        )


def _get_dialect_cls_async():
    from .async_db import async_db
    from .dialects import get_dialect
    return get_dialect(async_db.dialect)


# ================================================================== #
#  AsyncSoftDeleteMixin                                                #
# ================================================================== #

class AsyncSoftDeleteMixin:
    """
    Async equivalent of SoftDeleteMixin, for AsyncBaseModel subclasses.

    Usage:
        class Post(AsyncBaseModel, AsyncSoftDeleteMixin):
            __tablename__ = "posts"
            id    = IntField(primary_key=True)
            title = StrField(max_length=200, nullable=False)

        await Post.create_table()
        pid = await Post.create(title="Hello")
        await Post.soft_delete(id=pid)
        await Post.all()               # excludes deleted rows
        await Post.all_with_deleted()

    Only supports fresh table creation via create_table() — the injected
    field is already in cls._fields by the time create_table() runs, so
    no override is needed there (unlike sync, which also retrofits the
    column onto an already-existing table via _add_col_to_db).

    is_deleted() is a classmethod taking the row dict, not a bound
    instance method like sync's — AsyncBaseModel CRUD returns plain
    dicts, not an instance wrapper (same reasoning as async relationships).
    """

    SOFT_DELETE_FIELD = "deleted_at"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from .fields import DateTimeField
        _inject_field(cls, cls.SOFT_DELETE_FIELD, DateTimeField(nullable=True))
        cls.all                = classmethod(AsyncSoftDeleteMixin.all.__func__)
        cls.filter              = classmethod(AsyncSoftDeleteMixin.filter.__func__)
        cls.get                 = classmethod(AsyncSoftDeleteMixin.get.__func__)
        cls.query                = classmethod(AsyncSoftDeleteMixin.query.__func__)
        cls.query_with_deleted  = classmethod(AsyncSoftDeleteMixin.query_with_deleted.__func__)
        cls.all_with_deleted    = classmethod(AsyncSoftDeleteMixin.all_with_deleted.__func__)
        cls.only_deleted        = classmethod(AsyncSoftDeleteMixin.only_deleted.__func__)
        cls.soft_delete         = classmethod(AsyncSoftDeleteMixin.soft_delete.__func__)
        cls.restore              = classmethod(AsyncSoftDeleteMixin.restore.__func__)
        cls.purge                = classmethod(AsyncSoftDeleteMixin.purge.__func__)
        cls.purge_all_deleted    = classmethod(AsyncSoftDeleteMixin.purge_all_deleted.__func__)
        cls.count                = classmethod(AsyncSoftDeleteMixin.count.__func__)
        cls.exists                = classmethod(AsyncSoftDeleteMixin.exists.__func__)
        cls.is_deleted            = classmethod(AsyncSoftDeleteMixin.is_deleted.__func__)

    @classmethod
    def _qb(cls):
        from .fields import DateTimeField
        from .async_db import AsyncQueryBuilder
        _inject_field(cls, cls.SOFT_DELETE_FIELD, DateTimeField(nullable=True))
        return AsyncQueryBuilder(cls)

    @classmethod
    async def all(cls) -> list:
        return await cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True).all()

    @classmethod
    async def filter(cls, **kwargs) -> list:
        q = cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True)
        for k, v in kwargs.items():
            q = q.where(k, v)
        return await q.all()

    @classmethod
    async def get(cls, **kwargs):
        q = cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True)
        for k, v in kwargs.items():
            q = q.where(k, v)
        return await q.first()

    @classmethod
    def query(cls):
        """Chainable AsyncQueryBuilder pre-filtered to exclude soft-deleted rows."""
        return cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True)

    @classmethod
    def query_with_deleted(cls):
        return cls._qb()

    @classmethod
    async def all_with_deleted(cls) -> list:
        return await cls.query_with_deleted().all()

    @classmethod
    async def only_deleted(cls) -> list:
        return await cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", False).all()

    @classmethod
    async def soft_delete(cls, **kwargs) -> int:
        from .async_db import AsyncBaseModel
        return await AsyncBaseModel.update.__func__(
            cls, {cls.SOFT_DELETE_FIELD: _now_str()}, **kwargs
        )

    @classmethod
    async def restore(cls, **kwargs) -> int:
        from .async_db import AsyncBaseModel
        return await AsyncBaseModel.update.__func__(
            cls, {cls.SOFT_DELETE_FIELD: None}, **kwargs
        )

    @classmethod
    async def purge(cls, **kwargs) -> int:
        from .async_db import AsyncBaseModel
        return await AsyncBaseModel.delete.__func__(cls, **kwargs)

    @classmethod
    async def purge_all_deleted(cls) -> int:
        deleted = await cls.only_deleted()
        if not deleted:
            return 0
        pk  = next((n for n, f in cls._fields.items() if f.primary_key), "id")
        ids = [r[pk] for r in deleted]
        placeholders = ", ".join(["%s"] * len(ids))
        from .async_db import async_db
        dialect = _get_dialect_cls_async()
        sql = dialect.delete_sql(cls._table, f"{pk} IN ({placeholders})")
        return await async_db.execute(sql, ids)

    @classmethod
    async def count(cls, **kwargs) -> int:
        q = cls._qb().where(f"{cls.SOFT_DELETE_FIELD}__null", True)
        for k, v in kwargs.items():
            q = q.where(k, v)
        return await q.count()

    @classmethod
    async def exists(cls, **kwargs) -> bool:
        return (await cls.count(**kwargs)) > 0

    @classmethod
    def is_deleted(cls, row: dict) -> bool:
        return row.get(cls.SOFT_DELETE_FIELD) is not None


# ================================================================== #
#  AsyncAuditMixin                                                     #
# ================================================================== #

class AsyncAuditMixin:
    """
    Async equivalent of AuditMixin. age()/was_updated() are classmethods
    taking the row dict, not bound instance methods like sync's.
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
        cls.create      = classmethod(AsyncAuditMixin.create.__func__)
        cls.update       = classmethod(AsyncAuditMixin.update.__func__)
        cls.get           = classmethod(AsyncAuditMixin.get.__func__)
        cls.all            = classmethod(AsyncAuditMixin.all.__func__)
        cls.filter          = classmethod(AsyncAuditMixin.filter.__func__)
        cls.age              = classmethod(AsyncAuditMixin.age.__func__)
        cls.was_updated       = classmethod(AsyncAuditMixin.was_updated.__func__)

    @classmethod
    def set_current_user(cls, user_id: Optional[int]):
        """Set current user ID for audit tracking."""
        cls._current_user_id = user_id

    @classmethod
    def _qb(cls):
        from .async_db import AsyncQueryBuilder
        return AsyncQueryBuilder(cls)

    @classmethod
    async def get(cls, **kwargs):
        q = cls._qb()
        for k, v in kwargs.items():
            q = q.where(k, v)
        return await q.first()

    @classmethod
    async def all(cls) -> list:
        return await cls._qb().all()

    @classmethod
    async def filter(cls, **kwargs) -> list:
        q = cls._qb()
        for k, v in kwargs.items():
            q = q.where(k, v)
        return await q.all()

    @classmethod
    async def create(cls, **kwargs) -> int:
        now = _now_str()
        kwargs.setdefault(cls.CREATED_AT_FIELD, now)
        kwargs.setdefault(cls.UPDATED_AT_FIELD, now)
        if cls._current_user_id is not None:
            kwargs.setdefault(cls.CREATED_BY_FIELD, cls._current_user_id)
            kwargs.setdefault(cls.UPDATED_BY_FIELD, cls._current_user_id)
        from .async_db import AsyncBaseModel
        return await AsyncBaseModel.create.__func__(cls, **kwargs)

    @classmethod
    async def update(cls, data: dict, **kwargs) -> int:
        data = dict(data)
        data[cls.UPDATED_AT_FIELD] = _now_str()
        if cls._current_user_id is not None:
            data[cls.UPDATED_BY_FIELD] = cls._current_user_id
        from .async_db import AsyncBaseModel
        return await AsyncBaseModel.update.__func__(cls, data, **kwargs)

    @classmethod
    def age(cls, row: dict) -> Optional[datetime.timedelta]:
        """Return age of a row since creation. row is a dict, as
        returned by get()/all()/filter()."""
        created = row.get(cls.CREATED_AT_FIELD)
        if created is None:
            return None
        if isinstance(created, str):
            created = datetime.datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
        return datetime.datetime.now() - created

    @classmethod
    def was_updated(cls, row: dict) -> bool:
        created = row.get(cls.CREATED_AT_FIELD)
        updated = row.get(cls.UPDATED_AT_FIELD)
        if created is None or updated is None:
            return False
        return str(created) != str(updated)


# ================================================================== #
#  AsyncTimestampMixin                                                 #
# ================================================================== #

class AsyncTimestampMixin:
    """Async equivalent of TimestampMixin — just created_at/updated_at."""

    CREATED_AT_FIELD = "created_at"
    UPDATED_AT_FIELD = "updated_at"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        from .fields import DateTimeField
        _inject_field(cls, cls.CREATED_AT_FIELD, DateTimeField(nullable=True))
        _inject_field(cls, cls.UPDATED_AT_FIELD, DateTimeField(nullable=True))
        cls.create = classmethod(AsyncTimestampMixin.create.__func__)
        cls.update = classmethod(AsyncTimestampMixin.update.__func__)
        cls.get    = classmethod(AsyncTimestampMixin.get.__func__)
        cls.all    = classmethod(AsyncTimestampMixin.all.__func__)

    @classmethod
    def _qb(cls):
        from .async_db import AsyncQueryBuilder
        return AsyncQueryBuilder(cls)

    @classmethod
    async def get(cls, **kwargs):
        q = cls._qb()
        for k, v in kwargs.items():
            q = q.where(k, v)
        return await q.first()

    @classmethod
    async def all(cls) -> list:
        return await cls._qb().all()

    @classmethod
    async def create(cls, **kwargs) -> int:
        now = _now_str()
        kwargs.setdefault(cls.CREATED_AT_FIELD, now)
        kwargs.setdefault(cls.UPDATED_AT_FIELD, now)
        from .async_db import AsyncBaseModel
        return await AsyncBaseModel.create.__func__(cls, **kwargs)

    @classmethod
    async def update(cls, data: dict, **kwargs) -> int:
        data = dict(data)
        data[cls.UPDATED_AT_FIELD] = _now_str()
        from .async_db import AsyncBaseModel
        return await AsyncBaseModel.update.__func__(cls, data, **kwargs)