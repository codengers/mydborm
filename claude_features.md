# mydborm — ORM Feature Checklist

Cross-referenced against the codebase as of the post-v1.12.0 `main` (4 unreleased rounds: safety fixes, CI/lint hygiene, connection reliability, async parity). ✅ = implemented, ⚠️ = partial, ❌ = not implemented.

## Object Relational Mapping
- ✅ Map database tables to classes (`model.py` — `ModelMeta`, `BaseModel`)
- ✅ Map rows to objects (`ModelInstance`)
- ✅ Map columns to object attributes (`fields.py`)

## Model Definition
- ✅ Define schema using classes
- ✅ Define fields/columns (29 field types)
- ✅ Define constraints (PK, FK, unique, composite PK)
- ✅ Define metadata (`ModelMeta`)

## Automatic SQL Generation
- ✅ SELECT / INSERT / UPDATE / DELETE generation

## CRUD Operations
- ✅ Create / Retrieve / Update / Delete

## Query Builder
- ✅ Filter (`.where()`, `.or_where()`)
- ✅ Sorting (`.order_by()`, multi-column)
- ✅ Grouping (`.group_by()`, `.having()`)
- ✅ Aggregations (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`)
- ✅ Joins (`.inner_join()`, `.left_join()`, `.right_join()`)
- ✅ Subqueries (`.subquery()`)
- ✅ Raw SQL execution (`.where_raw()`, `.or_where_raw()`)

## Database Connection Management
- ✅ Open/close connections (`db.py` — `ConnectionManager`)
- ✅ Connection pooling — real driver-level pools (mysql-connector `pool_name`/`pool_size`, psycopg2 `ThreadedConnectionPool`), not just stored config; `pool_timeout`/MySQL `max_overflow` still not enforced (both drivers raise on exhaustion rather than waiting)
- ✅ Connection reuse
- ✅ Connection timeout handling
- ✅ Stale-connection recycling (`pool_recycle`, on by default) + broadened deadlock/connection-loss retry in `transaction_with_retry()`

## Transaction Management
- ✅ Begin/commit/rollback
- ✅ Nested transactions
- ✅ Savepoints

## Relationship Management
- ✅ One-to-Many / Many-to-One (`has_many`, `belongs_to`)
- ✅ Many-to-Many
- ⚠️ One-to-One (achievable via `belongs_to` + unique constraint, no dedicated API)
- ✅ Foreign key mapping (real FK constraint generation, v1.11.0)

## Lazy Loading
- ✅ `LazyRelation`

## Eager Loading
- ✅ `.include()`

## Identity Mapping
- ✅ `session.py` — `Session` identity map

## Change Tracking
- ✅ `TrackedInstance`, dirty-field tracking

## Unit of Work Pattern
- ✅ `Session` batches/commits changes together

## Schema Management
- ✅ Create/modify/drop tables
- ✅ Schema sync (`migrations.py` — `generate()`)

## Database Migration
- ✅ Version schema changes (`migrate()`, `migration_status()`)
- ✅ Upgrade
- ✅ Rollback (`rollback()`)

## Data Validation
- ✅ Field/type/constraint validation
- ✅ Custom validators (6 built-in: email, URL, regex, range, length, choice)

## Data Type Mapping
- ✅ Python ↔ SQL type mapping (`fields.py` `to_sql_def()`)

## Database Independence
- ✅ MySQL
- ✅ PostgreSQL
- ✅ YugabyteDB (YSQL)
- ✅ SQLite (v1.12.0 — dialect, sync/async CRUD, auto-migrations, cross-DB migration engine)
- ❌ Oracle
- ❌ SQL Server

## SQL Dialect Handling
- ✅ `dialects/` — per-database dialect classes

## Relationship Cascading
- ✅ Cascade insert (via FK + `on_delete`/`on_update`, v1.10.1)
- ✅ Cascade delete/update actions on `ForeignKeyField`

## Caching Support
- ✅ Query caching — `.cache(ttl=...)` on `QueryBuilder`/`AsyncQueryBuilder`, in-memory, table-level invalidation on any write (ORM or `clear_cache()`); ignored when combined with `.for_update()`
- ❌ Object caching
- ❌ Second-level caching

## Performance Optimization
- ✅ Batch inserts / bulk updates (`bulk.py`)
- ⚠️ Query optimization (no query planner/hints)
- ✅ Prepared statements (parameterized `%s` placeholders throughout)

## Pagination
- ✅ Limit / offset / `.paginate()`

## Sorting
- ✅ Ascending/descending, multi-column

## Filtering
- ✅ WHERE conditions, dynamic filters, complex conditions

## Aggregation Functions
- ✅ COUNT, SUM, AVG, MIN, MAX

## Join Operations
- ✅ INNER, LEFT, RIGHT
- ❌ Explicit FULL OUTER JOIN (not all target dialects support it natively)

## Index Management
- ✅ Auto indexes, unique indexes, composite indexes, runtime index creation

## Constraint Management
- ✅ Primary keys, foreign keys, unique constraints
- ❌ CHECK constraints

## Inheritance Mapping
- ❌ Single table inheritance
- ❌ Joined table inheritance
- ❌ Concrete table inheritance

## Lifecycle Hooks / Events
- ✅ before/after create/update/delete (`hasattr`-detected, no registration needed)

## Audit Tracking
- ✅ `AuditMixin` — created/updated timestamps, created/modified by

## Soft Delete Support
- ✅ `SoftDeleteMixin` (v1.11.1 fix: `.query()` now excludes soft-deleted rows by default)

## Optimistic Locking
- ✅ `OptimisticLockMixin` — version column, `update()` requires current version, raises `OptimisticLockError` on conflict

## Pessimistic Locking
- ✅ `.for_update()` on `QueryBuilder`/`AsyncQueryBuilder` — `SELECT ... FOR UPDATE`; not supported on SQLite (raises). Fixed a real bug found while building this: `db.transaction()` nesting now correctly holds locks across multiple reads instead of releasing them early

## Concurrency Handling
- ⚠️ Handled at the transaction/retry level, no explicit conflict-resolution API

## Stored Procedure Support
- ✅ `db.call_procedure()` / `async_db.call_procedure()` — execute a stored procedure, results as list of dicts. Not supported on SQLite

## Database Views Mapping
- ✅ `ViewModel`/`AsyncViewModel` mixins — map a view read-only; optional `__view_query__` lets `create_table()` issue `CREATE VIEW`

## Composite Key Support
- ✅ `__pk__ = (...)` tuple, full CRUD support

## Automatic Timestamp Handling
- ✅ `TimestampMixin` (`created_at`, `updated_at`)

## Serialization Support
- ✅ Object → JSON / dict (`to_dict()`, `to_json()`)
- ❌ Object → XML

## Deserialization
- ✅ JSON/dict → object (`from_dict()`)

## Data Encryption Support
- ✅ `EncryptedField` (AES, encrypt on save / decrypt on fetch)
- ✅ `PasswordField` (bcrypt)

## Multi Database Support
- ⚠️ Multiple `db.configure()` targets possible, but no built-in router
- ❌ Database routing

## Read/Write Splitting
- ❌ Not implemented

## Sharding Support
- ❌ Not implemented

## Multi-Tenancy Support
- ❌ Not implemented

## Automatic Retry Handling
- ✅ Retry on bulk ops (`bulk.py` — exponential backoff)
- ✅ Retry on transactions, sync and async (`transaction_with_retry()` — deadlocks and transient connection loss)

## Logging
- ✅ Query/SQL logging — `echo=True` + `db.queries` (SQL, params, duration; capped ring buffer), v1.12.0
- ❌ No dedicated error/performance logging module beyond query logging

## Debugging Support
- ✅ `db.queries` exposes executed SQL + params + duration_ms for inspection
- ❌ No EXPLAIN helper exposed on QueryBuilder

## Security Features
- ✅ Parameterized queries throughout (SQL injection protection)
- ✅ Safe identifier escaping per dialect

## Custom Query Execution
- ✅ Raw SQL via `.where_raw()` / `.or_where_raw()`
- ⚠️ No fully free-form raw query execution + result mapping API

## Repository Pattern Support
- ❌ Not a distinct layer (BaseModel doubles as data-access layer)

## Session Management
- ✅ `session.py` — `Session`, `ObjectState`, `TrackedInstance`

## Proxy Objects
- ✅ `LazyRelation` (lazy relationship references)
- ⚠️ No general lazy-attribute proxy beyond relationships

## Bulk Operations
- ✅ Bulk insert / update / delete / upsert (`bulk.py`, `test_upsert_joins.py`)

## Data Seeding
- ✅ `seed.py` — `seed()`/`seed_from_file()` (sync), `seed_async()`/`seed_from_file_async()` (async); CLI `mydborm seed --model ... --file ...`

## Testing Support
- ✅ SQLite dialect, including `:memory:` — zero-setup CRUD/query-builder testing with no external service (v1.12.0)
- ❌ No mocking helpers shipped in the library itself

## Asynchronous Database Operations
- ✅ `async_db.py` — `AsyncConnectionManager`, `AsyncBaseModel` (aiomysql, aiopg, aiosqlite)
- ✅ `AsyncQueryBuilder` — full chainable API (where/joins/group_by/order_by/limit/aggregates/paginate), sharing sync's SQL-building code via `QueryBuilderBase`
- ✅ Async transactions — `transaction()`/`savepoint()`/`nested_transaction()`/`bulk_transaction()`/`transaction_with_retry()`
- ✅ Async lifecycle hooks — before/after create/update/delete (hooks may be sync or async)
- ✅ Async bulk operations — `bulk_create`/`bulk_update`/`bulk_upsert`/`bulk_delete`
- ✅ Async relationships — `has_many`/`belongs_to`/`many_to_many` (explicit classmethods taking the row dict — async CRUD returns plain dicts, no instance wrapper)
- ✅ Async mixins — `AsyncSoftDeleteMixin`/`AsyncAuditMixin`/`AsyncTimestampMixin`
- ❌ No `LazyRelation` equivalent for async (a descriptor's `__get__` can't be `async def`) and `.include()` eager loading raises `NotImplementedError` — both documented as intentional API differences, not gaps

## Monitoring Integration
- ❌ No query metrics / slow-query tracking / performance monitoring hooks

---

## Summary of clear gaps

Biggest unimplemented areas, roughly in order of likely value for a "lightweight ORM":

1. ~~SQLite dialect~~ — done (dialect, sync/async CRUD, auto-migrations, cross-DB migration engine)
2. ~~Query/SQL logging~~ — done (`echo=True`, `db.queries`)
3. ~~Real connection pooling~~ — done (driver-level pools, stale-connection recycling, broadened retry)
4. ~~Async feature parity~~ — done (query builder, transactions, hooks, bulk ops, relationships, mixins)
5. ~~Locking~~ — done (`OptimisticLockMixin`, `.for_update()`)
6. ~~Data seeding utility~~ — done (`seed.py`, CLI `mydborm seed`)
7. ~~Stored procedures + database views mapping~~ — done (`call_procedure()`, `ViewModel`/`AsyncViewModel`)
8. ~~Query caching~~ — done (`.cache()`, table-level invalidation, `clear_cache()`)
9. **Inheritance mapping** (single/joined/concrete table)
10. **Read/write splitting, sharding, multi-tenancy** — larger architectural additions
