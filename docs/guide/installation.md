# Installation

This page covers what you need before using mydborm, how to install
it, and how to point it at a real database. If you just want to see
the library in action first, skip to the [Quickstart](quickstart.md)
and come back here when you need the details.

## What you need

- **Python 3.9 or newer.** Check with `python --version`.
- **A database to connect to** — MySQL 8+, PostgreSQL, or YugabyteDB
  2.x+. mydborm doesn't include a database server; it talks to one
  you already have running (locally, in Docker, or in the cloud).

If you don't have a database running yet, see
[Docker quickstart](#docker-quickstart) below — it's the fastest way
to get one running locally for trying things out.

## Install the package

```bash
pip install mydborm
```

This installs the core ORM — models, fields, the query builder,
relationships, transactions, and migrations. That's enough for most
projects.

A few features live in optional "extras" so that projects which don't
need them aren't forced to install extra dependencies:

```bash
pip install mydborm[cli]       # adds the `mydborm` command-line tool
pip install mydborm[async]     # adds async/await support (aiomysql, aiopg)
pip install mydborm[security]  # adds password hashing (bcrypt) and field encryption
```

You can combine them, e.g. `pip install mydborm[cli,async]`. If
you're contributing to mydborm itself rather than just using it, install
everything plus the test tooling:

```bash
pip install mydborm[dev,cli,async,security]
```

## Docker quickstart

If you don't already have MySQL or YugabyteDB running, this
`docker-compose.yml` starts both so you can try mydborm against either
one:

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: mydb
    ports:
      - "3306:3306"

  yugabyte:
    image: yugabytedb/yugabyte:latest
    ports:
      - "5433:5433"
```

```bash
docker compose up -d
```

Give it a few seconds to finish starting up, then it's ready for the
`db.configure(...)` calls below.

## Tell mydborm which database to use

Before you can create models or run queries, mydborm needs to know
*which* database to connect to and how. That's what `db.configure()`
is for — call it once, usually when your application starts:

```python
from mydborm import db

# MySQL
db.configure(
    dialect  = "mysql",       # which database engine — "mysql", "postgres", or "yugabyte"
    host     = "127.0.0.1",
    port     = 3306,
    user     = "root",
    password = "yourpassword",
    database = "mydb",
    charset  = "utf8mb4",
)
```

```python
# YugabyteDB — same idea, different dialect and port
db.configure(
    dialect  = "yugabyte",
    host     = "127.0.0.1",
    port     = 5433,
    user     = "yugabyte",
    password = "yugabyte",
    database = "yugabyte",
)
```

`dialect` is the one option that matters most: it tells mydborm which
SQL syntax and column types to generate. Everything else
(`host`/`port`/`user`/`password`/`database`) is the same kind of
connection info you'd hand to any database client.

### Configuring from an environment variable

If you'd rather keep connection details out of your code (recommended
for anything beyond local experiments), set a `DATABASE_URL`
environment variable and call `db.from_env()` instead:

```python
import os
from mydborm import db

os.environ["DATABASE_URL"] = "mysql://root:password@localhost:3306/mydb"
db.from_env()
```

`db.from_env()` reads `DATABASE_URL`, figures out the dialect from the
URL scheme (`mysql://`, `postgres://`, `yugabyte://`), and configures
the connection exactly as if you'd called `db.configure(...)`
yourself.

## Next step

Once you've installed mydborm and pointed it at a database, head to the
[Quickstart](quickstart.md) to define your first model and run some
queries.
