# Async support

Everything covered elsewhere in these docs — `BaseModel`, `db.configure()`,
the query builder — is **synchronous**: when you call `User.get(id=1)`, your
program stops and waits until the database responds before moving on to the
next line. For a script or a small CLI tool, that's completely fine.

It becomes a problem inside a web server handling many requests at once
(like a [FastAPI](https://fastapi.tiangolo.com/) app). A synchronous
database call blocks the *entire* process while it waits — so one slow
query can stall every other request the server is trying to handle at the
same time, even ones that have nothing to do with that query. mydborm's
**async support** — `AsyncBaseModel` and `async_db` — lets the server hand
off to other work while waiting on the database, instead of sitting idle.
This assumes you're already familiar with Python's `async`/`await` syntax;
if not, the short version is that `await` marks a point where your code can
pause and let other tasks run until the thing being awaited is ready.

Installing the `async` extra (`pip install mydborm[async]`) pulls in
`aiomysql`, `aiopg`, and `aiosqlite` — the underlying async database drivers
mydborm uses for MySQL, YugabyteDB/PostgreSQL, and SQLite respectively.

## Configure

The async API mirrors the synchronous one closely, with two differences:
every database-touching call needs `await` in front of it, and configuration
happens through `async_db` instead of `db`. Define your model by subclassing
`AsyncBaseModel` instead of `BaseModel` — field definitions work exactly the
same way:

```python
import asyncio
from mydborm.async_db import async_db, AsyncBaseModel
from mydborm.fields import IntField, StrField

class AsyncUser(AsyncBaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)

async def main():
    await async_db.configure(
        dialect  = "mysql",
        host     = "127.0.0.1",
        port     = 3306,
        user     = "root",
        password = "root",
        database = "mydb",
    )
    await AsyncUser.create_table()
    uid  = await AsyncUser.create(username="alice")
    user = await AsyncUser.get(id=uid)
    all  = await AsyncUser.all()
    await async_db.close()

asyncio.run(main())
```

A few things to notice if you're coming from the sync API:

- `async_db.configure(...)` must itself be awaited — it opens a connection
  pool in the background, which is itself an async operation.
- `create_table()`, `create()`, `get()`, `all()`, `filter()`, `update()`,
  and `delete()` all exist on `AsyncBaseModel` with the same names and
  arguments as `BaseModel` — just `await` each call.
- Call `await async_db.close()` when you're done (for example, when your
  application shuts down) to close the pool's connections cleanly.

In a real FastAPI app, you'd typically call `async_db.configure(...)` once
during application startup, and then `await` model calls inside your
endpoint functions — that's what lets FastAPI keep serving other requests
while one endpoint is waiting on a slow query.

## YugabyteDB async

Async support works the same way against YugabyteDB (or PostgreSQL) — just
change the `dialect`, `port`, and credentials to match:

```python
await async_db.configure(
    dialect  = "yugabyte",
    host     = "127.0.0.1",
    port     = 5433,
    user     = "yugabyte",
    password = "yugabyte",
    database = "yugabyte",
)
```

Everything else — `AsyncUser.create()`, `.get()`, `.all()`, and so on —
works identically regardless of which dialect you configured.

## SQLite async

SQLite works the same way too — only `database` is needed, since there's no
host/port/user/password:

```python
await async_db.configure(dialect="sqlite", database="app.db")
# or in-memory:
await async_db.configure(dialect="sqlite", database=":memory:")
```

One difference under the hood: `aiomysql`/`aiopg` give you a real
multi-connection pool, but `aiosqlite` doesn't — mydborm keeps a single
SQLite connection open and serializes access to it with a lock. This is
rarely a practical limitation since SQLite only supports one writer at a
time regardless of driver.
