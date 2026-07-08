# Query logging

Sometimes you need to see exactly what SQL mydborm is sending to the
database — debugging a slow request, verifying a query builder chain
produced the `WHERE` clause you expected, or auditing what a migration
run actually did. mydborm can log every statement it executes, with its
parameters and how long it took, without you having to add print
statements around your own code.

## Turning it on

Pass `echo=True` to `db.configure()` (or `async_db.configure()` for the
async API):

```python
from mydborm import db

db.configure(
    dialect="mysql", host="127.0.0.1", port=3306,
    user="root", password="root", database="mydb",
    echo=True,
)
```

With `echo=True`, every statement mydborm runs is logged through Python's
standard `logging` module, under the logger name `"mydborm.sql"`, at
`DEBUG` level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

Product.create(name="Widget", price=9.99)
# DEBUG:mydborm.sql:INSERT INTO `products` (name, price) VALUES (%s, %s) | params=['Widget', 9.99] | 1.23ms
```

Since it's just a standard Python logger, you can control it the same way
you'd control any other logging in your application — attach your own
handler, write to a file, filter by level, or turn it off entirely by not
configuring the logger (the default is `echo=False`, so nothing is logged
unless you opt in).

`echo=False` (the default) has effectively no overhead — no wrapping, no
extra objects — so it's safe to leave off in production and turn on only
when you need it.

## `db.queries`

Alongside the logger, mydborm also keeps an in-memory list of executed
queries on the `ConnectionManager` itself — handy in tests or a REPL
where reaching for the `logging` module feels like overkill:

```python
db.configure(dialect="sqlite", database=":memory:", echo=True)
Product.create(name="Widget", price=9.99)

db.queries
# [{"sql": "INSERT INTO ...", "params": ["Widget", 9.99], "duration_ms": 1.23}]

db.clear_queries()   # reset the list, e.g. between test assertions
```

`db.queries` is only populated while `echo=True` — with logging off it
stays empty, so there's no memory cost by default. It's capped at the
last 1000 entries so a long-running process with `echo=True` left on
doesn't grow unbounded.

For `executemany()` calls (bulk operations), the params field records a
row count instead of every row's values — e.g. `"<500 rows>"` — to avoid
flooding the log with a bulk insert's entire payload.

## Async

The async API works identically:

```python
await async_db.configure(dialect="mysql", host="127.0.0.1", ..., echo=True)
await AsyncProduct.create(name="Widget", price=9.99)

async_db.queries
async_db.clear_queries()
```

## What gets logged

`echo=True` covers everything that goes through `db.connect()` or
`db.execute()` — every `BaseModel`/`AsyncBaseModel` CRUD call, the query
builder, bulk operations, `migrate()`/`generate()`, and the
[`MigrationEngine`](db_migration.md) (pass `echo=True` in the `source`/
`target` config dicts to log a migration run). Explicit
`db.transaction()`/`db.savepoint()`/`db.bulk_transaction()` blocks are not
currently covered.
