# mydborm examples

Each file below is a self-contained, runnable script — no test framework
needed, just `python examples/<file>.py`. Every example connects to the
local MySQL instance from this repo's `docker-compose.yml` (see the
[Installation guide](../docs/guide/installation.md) if you don't have
it running yet), creates its own demo tables, prints what it's doing,
and cleans up after itself, so they're safe to run repeatedly and in
any order.

| File | Covers |
|---|---|
| [`example.py`](example.py) | The basics end-to-end: connect, define models, run migrations, full CRUD |
| [`query_builder_example.py`](query_builder_example.py) | Chained `.where()`/`.or_where()`, operator suffixes (`__gt`, `__in`, ...), joins, `group_by`/`having`, subqueries, pagination, bulk update/delete |
| [`relationships_example.py`](relationships_example.py) | `has_many`, `belongs_to`, `many_to_many`, lazy loading vs eager loading with `.include()` |
| [`transactions_example.py`](transactions_example.py) | `db.transaction()` for all-or-nothing groups of statements, `db.savepoint()` for partial rollback |
| [`bulk_operations_example.py`](bulk_operations_example.py) | `chunked_bulk_create/update/delete` with a progress callback, `bulk_upsert()` |
| [`validators_example.py`](validators_example.py) | Every built-in validator (email, URL, regex, range, length, choice) plus writing a custom one |
| [`security_example.py`](security_example.py) | `PasswordField` (one-way bcrypt hashing) vs `EncryptedField` (two-way AES encryption) — requires `pip install mydborm[security]` |
| [`session_example.py`](session_example.py) | The identity map (same row → same Python object) and automatic change tracking |
| [`async_example.py`](async_example.py) | `AsyncBaseModel` for FastAPI and other asyncio frameworks — requires `pip install mydborm[async]` |
| [`db_migration_example.py`](db_migration_example.py) | Moving schema + data between two databases with `MigrationEngine`, and building a target table from a model class with `ObjectMigrator` |

For the full write-up behind any of these, see the matching page in the
[Guide](../docs/guide/).
