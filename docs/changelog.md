# Changelog

## [1.0.0] - 2026-06-19
### Added
- MkDocs documentation site
- Coverage 95%+
- Full type hints
- API stability guarantee

## [0.8.0] - 2026-06-19
### Added
- Auto-migration generation — generate(), apply_migration_file()
- GROUP BY + HAVING in QueryBuilder
- Subquery support
- Performance benchmarks

## [0.7.0] - 2026-06-19
### Added
- Coverage 44% → 88%
- Custom validators — EmailValidator, RangeValidator, etc.
- test_dialects, test_migrations, test_cli

## [0.6.0] - 2026-06-19
### Added
- Session — identity map, change tracking, unit of work
- Lazy loading via LazyRelation descriptor
- Eager loading via QueryBuilder.include()

## [0.5.0] - 2026-06-19
### Added
- 24 custom exception types
- Chunked bulk operations with BulkResult + retry
- Savepoints + nested transactions
- bulk_upsert — ON DUPLICATE KEY UPDATE
- JOIN support — inner, left, right
- Model serialization — to_dict, to_json, from_dict
- Schema validation

## [0.4.1] - 2026-06-19
### Fixed
- YugabyteDB dialect — SERIAL, BOOLEAN, JSONB, RETURNING id

## [0.4.0] - 2026-06-19
### Added
- Bulk operations — bulk_create, bulk_update, bulk_delete
- Raw SQL — db.execute, fetchall, fetchone
- Async ORM — AsyncConnectionManager, AsyncBaseModel
- Connection pooling — configure_pool, ping, reconnect

## [0.3.0] - 2026-06-19
### Added
- QueryBuilder with operators, order, limit, offset
- Aggregates — sum, avg, min, max, count
- Relationships — has_many, belongs_to, many_to_many
- GitHub Actions CI

## [0.2.0] - 2026-06-19
### Added
- Core ORM — BaseModel, 11 field types
- Schema migrations
- Rich CLI — version, ping, tables, inspect, migrate

## [0.1.0] - 2026-01-01
### Added
- Initial release