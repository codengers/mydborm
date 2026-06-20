# Changelog

## [1.2.1] - 2026-06-20
### Fixed
- Security extras (`bcrypt`, `cryptography`) now correctly declared in `pyproject.toml`
- `pip install mydborm[security]` now works correctly

## [1.2.0] - 2026-06-20
### Added
- `PasswordField` — one-way bcrypt hashing for user passwords
  - Auto-hashes on `create()` / `update()`
  - `PasswordField.verify(plain, hashed)` → True/False
  - `PasswordField.hash(plain, rounds=12)` → hash string
  - Configurable work factor (rounds)
- `EncryptedField` — two-way AES encryption (Fernet/AES-128-CBC)
  - Auto-encrypts on `create()` / `update()`
  - `EncryptedField.generate_key()` → new Fernet key
  - `EncryptedField.encrypt(plain, key)` → ciphertext
  - `EncryptedField.decrypt(cipher, key)` → plaintext
  - `field.decrypt_value(cipher)` → plaintext
- `pip install mydborm[security]` — optional security dependencies
- 35 new tests — total: 658 tests

## [1.1.0] - 2026-06-20
### Added
- 17 new field types with full MySQL ↔ YugabyteDB dialect mapping:
  - `TinyIntField` — TINYINT → SMALLINT
  - `SmallIntField` — SMALLINT → SMALLINT
  - `BigIntField` — BIGINT → BIGINT
  - `UnsignedBigIntField` — BIGINT UNSIGNED → NUMERIC(20)
  - `DoubleField` — DOUBLE → DOUBLE PRECISION
  - `BitField(n)` — BIT(n) → BIT(n)
  - `CharField(n)` — CHAR(n) → CHAR(n)
  - `TinyTextField` — TINYTEXT → TEXT
  - `MediumTextField` — MEDIUMTEXT → TEXT
  - `LongTextField` — LONGTEXT → TEXT
  - `BinaryField(n)` — BINARY(n) → BYTEA
  - `VarBinaryField(n)` — VARBINARY(n) → BYTEA
  - `BlobField` — BLOB/MEDIUMBLOB/LONGBLOB → BYTEA
  - `TimeField` — TIME → TIME
  - `TimestampField` — TIMESTAMP → TIMESTAMPTZ
  - `EnumField(choices)` — ENUM(...) → VARCHAR(n)
  - `SetField(choices)` — SET(...) → TEXT[]
- 62 new tests — total: 623 tests

## [1.0.1] - 2026-06-19
### Fixed
- CLI version test uses dynamic version check
- Security extra properly declared in pyproject.toml

## [1.0.0] - 2026-06-19 — Stable release
### Added
- MkDocs documentation site at https://codengers.github.io/mydborm/
- Type hints and docstring improvements
- Production/Stable PyPI classifier
- `docs` optional dependencies group
- API stability guarantee

## [0.8.0] - 2026-06-19
### Added
- Auto-migration generation — `generate()`, `apply_migration_file()`, `list_migration_files()`
- `mydborm generate` CLI command
- GROUP BY + HAVING in QueryBuilder — `.group_by()`, `.having()`
- Subquery support — `.subquery(field)` + `__in` subquery
- Performance benchmarks — mydborm vs SQLAlchemy vs Peewee vs YugabyteDB
- 26 new auto-migration tests + 26 GROUP BY tests — total: 561 tests

## [0.7.0] - 2026-06-19
### Added
- Coverage 44% → 88% (+44%)
- `tests/test_dialects.py` — 42 tests, MySQL + YugabyteDB dialect 100% coverage
- `tests/test_migrations.py` — 31 tests, migration engine 90% coverage
- `tests/test_cli.py` — 35 tests, all 6 CLI commands tested
- Custom validators — `EmailValidator`, `UrlValidator`, `RegexValidator`,
  `RangeValidator`, `MinLengthValidator`, `ChoiceValidator`
- `Field.validators` parameter — attach validators to any field
- `Model.__validators__` — cross-field validation rules
- 48 validator tests — total: 509 tests

## [0.6.0] - 2026-06-19
### Added
- `Session` — identity map, change tracking, unit of work
- `ObjectState` — NEW, CLEAN, DIRTY, DELETED, DETACHED
- `TrackedInstance` — wraps ModelInstance with state tracking
- `TrackingDict` — auto-marks dirty fields on assignment
- `session.get()`, `session.add()`, `session.delete()`
- `session.flush()`, `session.commit()`, `session.rollback()`
- `session.is_dirty()`, `session.dirty_fields()`, `session.original_value()`
- Context manager support — auto flush+commit, rollback on exception
- `LazyRelation` descriptor — lazy loading with caching
- `QueryBuilder.include()` — eager loading, N+1 prevention
- `ModelInstance.__getattr__` fix — descriptor-aware attribute access
- 32 session tests + 23 lazy loading tests — total: 353 tests

## [0.5.0] - 2026-06-19
### Added
- 24 custom exception types (`MydbormError` hierarchy)
- Chunked bulk operations — `chunked_bulk_create/update/delete`
- `BulkResult` — detailed result with inserted/failed/chunks/retries/duration
- `_with_retry` — exponential backoff retry helper
- Savepoints — `db.savepoint()`, partial rollback within transactions
- Nested transactions — `db.nested_transaction()`
- Bulk transactions — `db.bulk_transaction()`
- Transaction retry — `db.transaction_with_retry(retries, retry_delay)`
- UTF-8/charset configuration — `db.configure(charset="utf8mb4", encoding="utf-8")`
- `bulk_upsert()` — ON DUPLICATE KEY UPDATE (MySQL) / ON CONFLICT DO UPDATE (YugabyteDB)
- JOIN support — `.join()`, `.inner_join()`, `.left_join()`, `.right_join()`
- Serialization — `to_dict()`, `to_json()`, `to_json_dict()`, `from_dict()`, `from_json()`
- Schema validation — `validate_schema()`, `schema_info()`
- 128 new tests — total: 298 tests

## [0.4.1] - 2026-06-19
### Fixed
- YugabyteDB dialect — SERIAL primary keys (not AUTO_INCREMENT)
- YugabyteDB — native BOOLEAN (not TINYINT(1))
- YugabyteDB — JSONB (not JSON)
- YugabyteDB — double-quote identifiers (not backticks)
- YugabyteDB — RETURNING id on INSERT (for lastrowid)
- `to_sql_def()` accepts `dialect` parameter
- YugabyteDB tests skip gracefully when container not running
- 27 YugabyteDB integration tests — total: 169 tests

## [0.4.0] - 2026-06-19
### Added
- Bulk operations — `bulk_create()`, `bulk_update()`, `bulk_delete()`
- Raw SQL — `db.execute()`, `db.fetchall()`, `db.fetchone()`
- Transaction context manager — `db.transaction()`
- `db.table_exists()`, `db.list_tables()`
- `AsyncConnectionManager` — via aiomysql (MySQL) / aiopg (YugabyteDB)
- `AsyncBaseModel` — full async CRUD: create, get, all, filter, update, delete, count
- Connection pooling — `db.configure_pool()`, `db.pool_status()`, `db.ping()`, `db.reconnect()`
- `mydborm pool` CLI command
- 73 new tests — total: 142 tests

## [0.3.0] - 2026-06-19
### Added
- `QueryBuilder` — `.where()`, operators, `.order_by()`, `.limit()`, `.offset()`
- 8 filter operators — `__gt`, `__lt`, `__gte`, `__lte`, `__ne`, `__like`, `__in`, `__null`
- Aggregates — `.sum()`, `.avg()`, `.min()`, `.max()`, `.count()`
- `ModelInstance` — dict + attribute access + relationship methods
- `has_many()`, `belongs_to()`, `many_to_many()` relationship methods
- GitHub Actions CI — Python 3.9, 3.10, 3.11, 3.12 matrix
- PyPI trusted publishing — auto-publish on git tag
- 48 new tests — total: 69 tests

## [0.2.0] - 2026-06-19
### Added
- `BaseModel` with full CRUD: create, get, all, filter, update, delete, count, exists
- 10 field types: IntField, StrField, TextField, BoolField, FloatField, DecimalField,
  DateField, DateTimeField, JSONField, ForeignKeyField
- Thread-safe `ConnectionManager` with pool support
- MySQL 8+ + YugabyteDB (YSQL) dialect support
- Schema migration engine — `migrate()`, `migration_status()`, `rollback()`
- Rich CLI — version, ping, tables, inspect, migrate
- 21 tests

## [0.1.0] - 2026-01-01
### Added
- Initial release with basic project scaffold
