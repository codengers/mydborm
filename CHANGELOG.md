# Changelog

All notable changes to mydborm are documented here.

## [0.2.0] - 2026-06-15

### Added
- BaseModel with full CRUD: create, get, all, filter, update, delete, count, exists
- 11 field types: IntField, StrField, TextField, BoolField, FloatField,
  DecimalField, DateField, DateTimeField, JSONField, ForeignKeyField
- Thread-safe ConnectionManager with context manager and DATABASE_URL support
- MySQL 8+ dialect with InnoDB, utf8mb4, AUTO_INCREMENT, TINYINT(1)
- YugabyteDB (YSQL) dialect with SERIAL, BOOLEAN, JSONB, RETURNING id
- Schema migration engine with history tracking in _mydborm_migrations
- Rich CLI: version, ping, tables, inspect, migrate
- 21 pytest tests, 84% code coverage
- Professional file headers with author attribution
- docker-compose.yml for MySQL + YugabyteDB local development

## [0.1.0] - 2026-01-01

### Added
- Initial release with basic project scaffold
