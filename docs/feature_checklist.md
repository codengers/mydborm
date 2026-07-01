# mydborm — ORM Feature Checklist

A feature-by-feature audit of mydborm (current `main`, v1.10.1) against a
general "what a mature ORM might support" checklist. Verified against the
actual source in `mydborm/` — not assumed from docs or the class names
alone. `[x]` = supported, `[~]` = partial (see note), `[ ]` = not
supported.

> Generated as a reference for evaluating mydborm as a dependency in
> another project. Not part of the published docs site.

---

## Object Relational Mapping
- [x] Map database tables to classes — `BaseModel` + `ModelMeta`, `__tablename__`
- [x] Map rows to objects — `ModelInstance`
- [x] Map columns to object attributes — `Field` descriptors, dict-like *and* attribute access

## Model Definition
- [x] Define database schema using programming classes
- [x] Define fields/columns — 29 field types (`mydborm/fields.py`)
- [x] Define constraints — `nullable`, `unique`, `primary_key`, `max_length`, etc.
- [~] Define metadata — `__tablename__`, `__pk__`, `__indexes__` exist; no single unified metadata object (e.g. SQLAlchemy's `MetaData`)

## Automatic SQL Generation
- [x] Generate SELECT queries
- [x] Generate INSERT queries
- [x] Generate UPDATE queries
- [x] Generate DELETE queries

## CRUD Operations
- [x] Create records — `.create()`
- [x] Retrieve records — `.get()`, `.all()`, `.filter()`
- [x] Update records — `.update()`
- [x] Delete records — `.delete()`

## Query Builder
- [x] Filter queries — `.where()`, operator suffixes (`__gt`, `__in`, `__like`, ...)
- [x] Sorting — `.order_by()`
- [x] Grouping — `.group_by()`, `.having()`
- [x] Aggregations — `.count()`, `.sum()`, `.avg()`, `.min()`, `.max()`
- [x] Joins — `.join()`, `.inner_join()`, `.left_join()`, `.right_join()`
- [x] Subqueries — `.subquery()`
- [x] Raw SQL execution support — `.where_raw()`/`.or_where_raw()`, `db.execute()`, `db.fetchall()`

## Database Connection Management
- [x] Open connections — `db.connect()`
- [x] Close connections — `db.close()`
- [~] Connection pooling — real for async (`aiomysql`/`aiopg` pools); the sync `configure_pool()` only stores config numbers, it does not hold multiple live connections
- [x] Connection reuse — one connection per thread, reused across calls
- [ ] Connection timeout handling — no enforced connect/read timeout wiring

## Transaction Management
- [x] Begin transaction — `db.transaction()`
- [x] Commit transaction
- [x] Rollback transaction
- [x] Nested transactions — `db.nested_transaction()`
- [x] Savepoints — `db.savepoint()`

## Relationship Management
- [~] One-to-One — no dedicated type; achievable via `belongs_to` + a `unique` FK column, but it's on you to enforce uniqueness
- [x] One-to-Many — `has_many`
- [x] Many-to-One — `belongs_to`
- [x] Many-to-Many — `many_to_many` (via an explicit join table)
- [x] Foreign key mapping — `ForeignKeyField` now generates a real `FOREIGN KEY (...) REFERENCES ...` table constraint in `create_table()` (resolves `to=` against the defined model, single-column PK target, MySQL + YugabyteDB/PostgreSQL dialect quoting). Previously `to_sql_def()` had a broken signature that crashed `create_table()` for *any* model with a `ForeignKeyField` — fixed alongside the constraint generation. See `tests/test_foreign_keys.py`.

## Lazy Loading
- [x] Load related data only when required — `LazyRelation` descriptor, cached after first access

## Eager Loading
- [x] Preload related data — `.include()`
- [x] Reduce multiple database calls — batches all related rows in one extra query, not one per parent row

## Identity Mapping
- [x] Maintain unique object instance per database row — `Session`'s identity map
- [x] Avoid duplicate objects

## Change Tracking
- [x] Detect modified objects — `Session` + `TrackedInstance`
- [x] Track dirty fields
- [x] Auto-generate update statements — on `session.flush()`

## Unit of Work Pattern
- [x] Track object lifecycle — `ObjectState` (NEW/CLEAN/DIRTY/DELETED)
- [x] Batch database changes
- [x] Commit changes together

## Schema Management
- [x] Create tables
- [~] Modify tables — add/drop columns via `migrate()`; no column type change or rename
- [x] Drop tables
- [x] Schema synchronization — `diff_schema()` compares model to live table

## Database Migration
- [x] Version schema changes — `generate()` writes numbered `.sql` files, tracked in a `_mydborm_migrations` table
- [x] Upgrade database — `migrate()` / `apply_migration_file()`
- [~] Rollback database changes — `rollback()` exists, but it **drops the table and all its data** rather than a column-level undo
- [x] *(beyond the checklist)* database-**to**-database migration — `mydborm.migrate.MigrationEngine`/`ObjectMigrator` copy schema + data between two live databases (e.g. MySQL → YugabyteDB)

## Data Validation
- [x] Field validation
- [x] Type validation — raises `FieldTypeError` (also a `TypeError`)
- [x] Constraint validation — required (`FieldRequiredError`) and length (`FieldLengthError`)
- [x] Custom validators — subclass `ValidationRule`

## Data Type Mapping
- [x] Convert language types to database types — every field maps to the right MySQL/YugabyteDB/PostgreSQL column type automatically

## Database Independence
- [~] Support multiple databases — **MySQL, YugabyteDB, PostgreSQL only.** No Oracle, SQL Server, or SQLite.

## SQL Dialect Handling
- [x] Handle database-specific SQL differences — `mydborm/dialects/` (identifier quoting, `AUTO_INCREMENT` vs `SERIAL`, `JSON` vs `JSONB`, etc.)

## Relationship Cascading
- [ ] Cascade insert / update / delete — `delete()` is a plain `DELETE FROM ... WHERE ...`; deleting a parent does **not** delete its children at the application level. `ForeignKeyField` now generates a real `FOREIGN KEY` constraint (see Foreign key mapping above), but without `ON DELETE`/`ON UPDATE` actions — by default the database rejects deleting a referenced parent row rather than cascading.

## Caching Support
- [ ] Query caching
- [ ] Object caching (beyond the per-instance lazy-relation cache, which isn't a general object cache)
- [ ] Second-level caching

## Performance Optimization
- [x] Batch inserts — `bulk_create()`, `chunked_bulk_create()`
- [x] Bulk updates — `bulk_update()`, `chunked_bulk_update()`
- [ ] Query optimization (no planner/optimizer — you write the query, that's what runs)
- [~] Prepared statements — every query is parameterized (`%s` placeholders), but mydborm doesn't explicitly prepare-and-cache statement plans server-side

## Pagination
- [x] Limit records — `.limit()`
- [x] Offset records — `.offset()`
- [x] Page-based fetching — `.paginate(page, per_page)`

## Sorting
- [x] Ascending order
- [x] Descending order
- [x] Multi-column sorting — chained `.order_by()` calls stack: `.order_by("region").order_by("revenue", desc=True)`

## Filtering
- [x] WHERE conditions
- [x] Dynamic filters
- [x] Complex conditions — chained `.where()`/`.or_where()`, plus `.where_raw()` for anything the operator syntax can't express

## Aggregation Functions
- [x] COUNT
- [x] SUM
- [x] AVG
- [x] MIN
- [x] MAX

## Join Operations
- [x] INNER JOIN
- [x] LEFT JOIN
- [x] RIGHT JOIN
- [~] (FULL) OUTER JOIN — `join_type="FULL"` is accepted by `.join()`, but MySQL itself doesn't support `FULL OUTER JOIN`, so this only works on the PostgreSQL-family dialects

## Index Management
- [x] Define indexes — `index=True` on any field
- [x] Unique indexes — `unique=True` on any field
- [x] Composite indexes — `__indexes__` class attribute

## Constraint Management
- [x] Primary keys
- [x] Foreign keys — see Relationship Management above; navigation and a real `FOREIGN KEY` DB constraint
- [x] Unique constraints
- [ ] Check constraints — mentioned in one field's docstring as a YugabyteDB option, never actually generated

## Inheritance Mapping
- [~] Single table inheritance — a subclass inherits its parent's field definitions (plain Python class inheritance applied to the field dict), but there's no discriminator column and no polymorphic query that returns a mix of subclass types from one table
- [ ] Joined table inheritance
- [ ] Concrete table inheritance

## Lifecycle Hooks / Events
- [x] Before insert/update/delete — `before_create`/`before_update`/`before_delete`, detected via `hasattr` at runtime, no registration needed
- [x] After insert/update/delete — `after_create`/`after_update`/`after_delete`

## Audit Tracking
- [x] Created timestamp / Updated timestamp — `TimestampMixin`
- [x] Created by / Modified by — `AuditMixin`

## Soft Delete Support
- [x] `SoftDeleteMixin` — `delete()` sets a flag instead of removing the row

## Optimistic Locking
- [ ] Version tracking / conflict prevention — not implemented

## Pessimistic Locking
- [ ] Row locking / `SELECT ... FOR UPDATE` — not implemented

## Concurrency Handling
- [~] `db.transaction_with_retry()` exists to retry on a detected deadlock, **but it's broken for the realistic case**: when the deadlock-shaped error comes from your own statements inside its `with` block, retrying would require yielding twice from the same `@contextmanager` generator, which Python's `contextlib` forbids — you get `RuntimeError: generator didn't stop after throw()` instead of a clean retry. (Found and documented this session; a manual retry loop around plain `db.transaction()` works correctly as a workaround — see `docs/guide/exceptions.md`.)

## Stored Procedure Support
- [ ] Not implemented

## Database Views Mapping
- [ ] Not implemented

## Composite Key Support
- [x] `__pk__ = ("col1", "col2")`

## Automatic Timestamp Handling
- [x] `created_at` / `updated_at` — via `TimestampMixin` or a `DateTimeField`/`TimestampField` with a default

## Serialization Support
- [x] Object → dict — `.to_dict()`
- [x] Object → JSON — `.to_json()`
- [ ] Object → XML — not implemented

## Deserialization
- [x] Dict → object — `.from_dict()`
- [x] JSON → object — `.from_json()`

## Data Encryption Support
- [x] Encrypt before saving / decrypt after fetching — `EncryptedField` (AES/Fernet)

## Multi Database Support
- [x] Connect multiple databases — each `ConnectionManager()` instance holds its own independent connection (fixed this session — instances used to silently share one connection slot); used today by the cross-database `MigrationEngine`
- [ ] Database routing — no automatic "send this query to that database" layer; you manage which `ConnectionManager` you call yourself

## Read/Write Splitting
- [ ] Not implemented

## Sharding Support
- [ ] Not implemented

## Multi-Tenancy Support
- [ ] Not implemented

## Automatic Retry Handling
- [x] Bulk operations — `chunked_bulk_*` functions retry a failed chunk with exponential backoff
- [~] Transaction-level retry — see Concurrency Handling above; exists but doesn't work for the common case

## Logging
- [ ] Query logging — no `logging` module usage anywhere in the package, only scattered `print()` statements (e.g. `"[mydborm] Table ready."`)
- [ ] Error logging
- [ ] Performance logging

## Debugging Support
- [~] Show generated SQL — `QueryBuilder.__repr__()` shows the built SQL + params, but there's no dedicated debug/echo mode you can flip on
- [ ] Explain query plans — not implemented

## Security Features
- [x] SQL injection protection / parameterized queries — `%s` placeholders for every value, throughout
- [x] Safe escaping — identifiers are backtick-quoted (MySQL) or double-quote-quoted (YugabyteDB/PostgreSQL) per dialect

## Custom Query Execution
- [x] Execute raw SQL — `db.execute()`, `db.fetchall()`, `db.fetchone()`
- [x] Native database queries — same methods, no abstraction forced on you

## Repository Pattern Support
- [ ] No explicit `Repository` base class — `BaseModel` itself is the closest thing to a per-model data-access point, but there's no separate repository layer

## Session Management
- [x] `Session` — identity map, change tracking, manual or context-manager (`with Session():`) usage

## Proxy Objects
- [x] Lazy object references — `LazyRelation` is a true descriptor-based proxy: nothing is fetched until first attribute access, then cached on the instance

## Bulk Operations
- [x] Bulk insert — `bulk_create()`, `chunked_bulk_create()`
- [x] Bulk update — `bulk_update()`, `chunked_bulk_update()`
- [x] Bulk delete — `bulk_delete()`, `chunked_bulk_delete()`
- [x] *(beyond the checklist)* Bulk upsert — `bulk_upsert()`

## Data Seeding
- [ ] No dedicated seed/fixture-loading helper — use `bulk_create()` yourself

## Testing Support
- [ ] No SQLite or in-memory dialect (only MySQL/YugabyteDB/PostgreSQL)
- [ ] No mocking helpers shipped in the library itself
- [~] Test transactions — you can wrap test data in `db.transaction()` and roll it back yourself; nothing automated

## Asynchronous Database Operations
- [x] Async queries — `AsyncBaseModel`, full async CRUD
- [ ] Async transactions — no `async def transaction()`/`savepoint()` equivalent exists
- [x] Non-blocking database calls — real `aiomysql`/`aiopg` connection pools

## Monitoring Integration
- [ ] No metrics hooks (Prometheus, StatsD, or otherwise)

---

## Summary

| | Count |
|---|---|
| Fully supported (`[x]`) | 106 |
| Partial / has caveats (`[~]`) | 13 |
| Not supported (`[ ]`) | 29 |

**What mydborm is genuinely strong at:** declarative models, CRUD, the
query builder (including subqueries and all five aggregates), bulk
operations with retry, sessions/change-tracking, async support, security
fields, lifecycle hooks, mixins (soft delete/audit/timestamps), real
`FOREIGN KEY` constraint generation, and — unusually for a "lightweight"
ORM — a real database-to-database migration engine.

**Where it's thin, if you're evaluating it for production use:** no
cascading deletes (`ON DELETE`/`ON UPDATE` actions aren't generated for
foreign keys), no caching layer, no locking (optimistic or pessimistic),
no stored procedures or views, no sharding/multi-tenancy/read-write-
splitting, minimal logging, and the deadlock-retry feature doesn't
actually work for the case most people would reach for it. None of these
are silent landmines, though — most either fail clearly
(`NotImplementedError`-shaped absence) or are now documented in
`docs/guide/exceptions.md`.
