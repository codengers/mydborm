# Database Migration

`mydborm.migrate` moves schema and data from one live database to another,
across any combination of MySQL, YugabyteDB, and PostgreSQL. It extracts
the source schema, maps column types to the target dialect, generates
`CREATE TABLE`/`CREATE INDEX` DDL, streams rows over in chunks, and
verifies row counts when it's done.

Supported source → target pairs:

- MySQL → YugabyteDB / PostgreSQL
- YugabyteDB / PostgreSQL → MySQL
- YugabyteDB ↔ PostgreSQL (same type system — no mapping needed)

## Python API

```python
from mydborm import MigrationEngine

engine = MigrationEngine(
    source={"dialect": "mysql", "host": "127.0.0.1", "port": 3306,
            "user": "root", "password": "<password>", "database": "shop"},
    target={"dialect": "yugabyte", "host": "127.0.0.1", "port": 5433,
            "user": "yugabyte", "password": "<password>", "database": "shop"},
)

result = engine.run(
    tables      = None,   # None = every table, or ["users", "orders"]
    chunk_size  = 500,
    overwrite   = False,  # skip tables that already have rows in the target
    on_progress = lambda table, done, total: print(table, done, total),
    verify      = True,   # compare row counts after the copy
)

print(result.summary())
assert result.is_success()
```

`MigrationEngine` opens the source and target connections independently —
both stay open for the duration of the migration and are always closed in a
`finally` block, even on error.

### MigrationResult

```python
result.tables_migrated    # tables successfully copied
result.tables_failed      # tables that raised an error
result.total_rows         # rows counted in the source
result.rows_transferred   # rows actually written to the target
result.duration           # seconds
result.errors             # ["orders: <exception text>", ...]
result.warnings           # ["Skipped 'products' — target already has data", ...]
result.is_success()       # True if tables_failed == 0 and no errors
result.summary()          # human-readable report
```

## Migrating by model class

`MigrationEngine` builds the target schema from whatever is *live* in the
source database. If you already have `BaseModel` subclasses and want the
*model's own field definitions* to be the source of truth for the target
table instead — typed columns, `NOT NULL`, defaults, and all — use
`ObjectMigrator`:

```python
from mydborm import db, ObjectMigrator
from myapp.models import User, Order

source_db = db  # or any configured ConnectionManager
target_db = db.__class__()
target_db.configure(dialect="yugabyte", host="127.0.0.1", port=5433,
                     user="yugabyte", password="<password>", database="shop")

migrator = ObjectMigrator(source_db, target_db, chunk_size=500)

result = migrator.migrate_model(User)
# {"table": "users", "rows_total": 12450, "rows_transferred": 12450, "skipped": False}

results = migrator.migrate_models([User, Order], overwrite=True)
# one model failing (e.g. a missing source table) doesn't stop the rest —
# failed entries come back as {"table": ..., "error": "..."}
```

`ObjectMigrator` doesn't own `source_db`/`target_db` — configure and close
them yourself, the same way you would for `MigrationEngine`. Row transfer
reuses the same chunked, retrying `DataTransfer` used internally by
`MigrationEngine`.

## Dry run

`dry_run()` extracts the schema and generates DDL without opening a write
connection to the target — nothing is created or copied:

```python
report = engine.dry_run(tables=["users", "orders"])

for t in report["tables"]:
    print(t["table"], t["rows"], t["columns"])
    print(t["create_table_sql"])
    print(t["create_index_sql"])

print(report["warnings"])  # unmapped column types that fell back to TEXT
```

## CLI usage

```bash
mydborm migrate-db \
  --source-dialect mysql       --source-host 127.0.0.1 --source-port 3306 \
  --source-user root           --source-password root   --source-db shop \
  --target-dialect yugabyte    --target-host 127.0.0.1 --target-port 5433 \
  --target-user yugabyte       --target-password yugabyte --target-db shop
```

Preview without writing anything:

```bash
mydborm migrate-db ... --dry-run
```

Migrate specific tables only, with a larger chunk size, replacing any
existing rows in the target:

```bash
mydborm migrate-db ... --tables users,orders --chunk-size 2000 --overwrite
```

A run prints a status table as each table finishes, then a final summary:

```
Migrating shop (mysql) → shop (yugabyte)

  ✔ users — 12,450 row(s) transferred
  ✔ orders — 89,231 row(s) transferred

 Table   │ Rows   │ Status
──────────────────────────────
 users   │ 12,450 │ ✔ Done
 orders  │ 89,231 │ ✔ Done
 Total   │ 101,681│ 2/2 done

Status            : SUCCESS
Tables migrated   : 2
Tables failed     : 0
Total rows        : 101681
Rows transferred  : 101681
Duration          : 4.2s
```

## Handling large tables

Rows are streamed from the source cursor in batches of `chunk_size`
(default `500`) and written with `executemany` — the full table is never
loaded into memory. Each batch retries up to 3 times with a 0.5s backoff
on transient failures.

- Raise `chunk_size` (e.g. `2000`–`5000`) for large tables with small rows
  to cut round-trips.
- Lower it for tables with very large rows (big `TEXT`/`BLOB`/`JSON`
  columns) to keep batches within driver/packet limits.

## Existing data in the target

By default, a table that already has rows in the target is **skipped** —
the table and its indexes are still created if missing, but no rows are
copied, and a warning is recorded:

```
Skipped 'products' — target already has data (pass overwrite=True to replace it)
```

Pass `overwrite=True` (or `--overwrite` on the CLI) to delete the existing
rows in the target table before copying.

## Verification

When `verify=True` (the default), every successfully migrated table is
checked after the copy: does it exist in the target, and does its row
count match the source? Mismatches are appended to `result.warnings`:

```
Table 'orders' is missing in the target database
Row count mismatch for 'products': source=1204 target=1198
```

## Type mapping

Unmapped source types fall back to `TEXT` in the target, with a warning
recorded in `result.warnings` (or `report["warnings"]` for a dry run).

**MySQL → YugabyteDB / PostgreSQL**

| Source (MySQL)        | Target            |
|------------------------|-------------------|
| INT, INTEGER           | INTEGER           |
| TINYINT(1)              | BOOLEAN           |
| TINYINT                | SMALLINT          |
| SMALLINT                | SMALLINT          |
| BIGINT                  | BIGINT            |
| BIGINT UNSIGNED         | NUMERIC(20)       |
| FLOAT                   | FLOAT             |
| DOUBLE                  | DOUBLE PRECISION  |
| DECIMAL(p,s)            | DECIMAL(p,s)      |
| VARCHAR(n)              | VARCHAR(n)        |
| CHAR(n)                 | CHAR(n)           |
| TEXT / TINYTEXT / MEDIUMTEXT / LONGTEXT | TEXT |
| BLOB / MEDIUMBLOB / LONGBLOB | BYTEA        |
| BINARY(n), VARBINARY(n) | BYTEA             |
| DATE                    | DATE              |
| DATETIME                | TIMESTAMP         |
| TIMESTAMP               | TIMESTAMPTZ       |
| TIME                    | TIME              |
| JSON                    | JSONB             |
| ENUM(...)               | VARCHAR(255)      |
| SET(...)                | TEXT              |

**YugabyteDB / PostgreSQL → MySQL**

| Source                  | Target (MySQL)    |
|--------------------------|-------------------|
| INTEGER, SERIAL          | INT               |
| BOOLEAN                  | TINYINT(1)        |
| SMALLINT                 | SMALLINT          |
| BIGINT                   | BIGINT            |
| NUMERIC(20)               | BIGINT UNSIGNED   |
| FLOAT                    | FLOAT             |
| DOUBLE PRECISION          | DOUBLE            |
| DECIMAL(p,s) / NUMERIC(p,s) | DECIMAL(p,s)   |
| VARCHAR(n)                | VARCHAR(n)        |
| CHAR(n)                   | CHAR(n)           |
| TEXT                      | TEXT              |
| BYTEA                     | BLOB              |
| DATE                      | DATE              |
| TIMESTAMP                 | DATETIME          |
| TIMESTAMPTZ                | DATETIME          |
| TIME                      | TIME              |
| JSONB / JSON               | JSON              |

```python
from mydborm import TypeMapper

TypeMapper.mysql_to_yugabyte("bigint(20) unsigned")  # -> "NUMERIC(20)"
TypeMapper.yugabyte_to_mysql("numeric(20)")          # -> "BIGINT UNSIGNED"
TypeMapper.map("varchar(100)", "mysql", "postgres")  # -> "VARCHAR(100)"
```
