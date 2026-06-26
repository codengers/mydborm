# Changelog

## [1.8.0] - 2026-06-26

### Added
- `QueryBuilder.or_where()` — OR conditions grouped and ANDed with WHERE filters; supports all 9 operators
- `QueryBuilder.distinct()` — `SELECT DISTINCT` support; unaffected by `count()` and aggregates

---

## [1.7.0] - 2026-06-26

### Added
- `QueryBuilder.update(**kwargs)` — bulk-update matching rows, returns affected row count
- `QueryBuilder.select(*columns)` — column projection, restricts `SELECT *` to specific columns
- Comprehensive README overhaul — sections 18–20 (Mixins, Session, Validators), full operator table, extended field types, 30+ field reference

---

## [1.6.0] - 2026-06-25

### Added
- `QueryBuilder.paginate(page, per_page)` — returns `{data, total, pages, page, per_page}`
- Page clamping: `page < 1` is treated as `page=1`
- 7 new tests in `test_query_builder.py`

---

## [1.5.0] - 2026-06-25

### Improved
- Test coverage raised from 95% → 96% (909 tests passing)
- `bulk.py` 80% → 100%, `session.py` 93% → 98%, `db.py` 85% → 94%
- YugabyteDB provisioned in GitHub Actions CI (no longer skipped)
- GitHub Actions upgraded to Node.js 24 (checkout@v5, setup-python@v6, upload-artifact@v5)
- Coverage report now uploads as `coverage.xml` artifact

---

## [1.4.0] - 2026-06-25

### Added
- PostgreSQL dialect — `get_dialect('postgres')`, `PostgreSQLDialect`, port 5432
- Composite primary keys — `__pk__ = ("col1", "col2")` for MySQL + YugabyteDB
- Index management — `create_index`, `drop_index`, `list_indexes`, `__indexes__`
- Lifecycle hooks — `before_create`, `after_create`, `before_update`, `after_update`, `before_delete`, `after_delete`

### Improved
- Test coverage raised from 88% → 95% (930 tests passing)
- YugabyteDB CLI tests gracefully skipped in CI when service is unavailable

---

## [0.5.0] - 2026-06-15 (in development)

### Added
- Custom exception hierarchy — 24 exception types (exceptions.py)
- Chunked bulk operations with BulkResult + retry logic (bulk.py)
- Savepoints — partial rollback within transactions
- Nested transactions using savepoints
- bulk_transaction() — atomic multi-model operations
- transaction_with_retry() — auto-retry on deadlock
- UTF-8 / charset configuration in db.configure()
- bulk_upsert() — INSERT ON DUPLICATE KEY UPDATE (MySQL)
                   INSERT ON CONFLICT DO UPDATE (YugabyteDB)
- JOIN support in QueryBuilder — inner_join, left_join, right_join
- 263 tests passing

## [0.4.1] - 2026-06-15

### Fixed
- YugabyteDB dialect — SERIAL PK, BOOLEAN, JSONB, double-quote identifiers
- RETURNING id on INSERT for YugabyteDB
- to_sql_def() accepts dialect parameter
- YugabyteDB tests skip gracefully when not available

## [0.4.0] - 2026-06-15

### Added
- bulk_create, bulk_update, bulk_delete
- db.execute, db.fetchall, db.fetchone
- db.transaction context manager
- db.table_exists, db.list_tables
- AsyncConnectionManager via aiomysql + aiopg
- AsyncBaseModel with full async CRUD
- configure_pool, pool_status, ping, reconnect
- mydborm pool CLI command
- 142 tests passing

## [0.3.0] - 2026-06-15

### Added
- QueryBuilder with .where(), operators, .order_by(), .limit(), .offset()
- 8 operators — __gt, __lt, __gte, __lte, __ne, __like, __in, __null
- Aggregates — .sum(), .avg(), .min(), .max(), .count()
- ModelInstance — dict + attribute access
- has_many, belongs_to, many_to_many relationships
- GitHub Actions CI — Python 3.9/3.10/3.11/3.12
- PyPI trusted publishing
- 69 tests passing

## [0.2.0] - 2026-06-15

### Added
- BaseModel with full CRUD
- 11 field types with validation
- Thread-safe ConnectionManager
- MySQL + YugabyteDB dialect support
- Schema migration engine with history tracking
- Rich CLI — version, ping, tables, inspect, migrate
- 21 tests passing

## [0.1.0] - 2026-01-01

### Added
- Initial release with basic project scaffold