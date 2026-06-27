# mydborm

[![PyPI version](https://badge.fury.io/py/mydborm.svg)](https://pypi.org/project/mydborm/)
[![Python](https://img.shields.io/pypi/pyversions/mydborm)](https://pypi.org/project/mydborm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/codengers/mydborm/actions/workflows/ci.yml/badge.svg)](https://github.com/codengers/mydborm/actions)
[![Coverage](https://img.shields.io/badge/coverage-96%25-brightgreen)](https://github.com/codengers/mydborm)
[![PyPI Downloads](https://img.shields.io/pypi/dm/mydborm)](https://pypi.org/project/mydborm/)

**mydborm is a Python library that lets you work with a database using
plain Python objects instead of writing raw SQL.**

That kind of library is called an **ORM** — "Object-Relational Mapper."
Instead of writing:

```sql
INSERT INTO users (username, email) VALUES ('alice', 'alice@example.com');
```

you write:

```python
User.create(username="alice", email="alice@example.com")
```

Same result, but it reads like normal Python, gets type-checked and
validated before it ever touches the database, and doesn't require you
to hand-write SQL strings throughout your codebase.

mydborm works with **MySQL 8+**, **PostgreSQL**, and **YugabyteDB**
(a distributed database that speaks the PostgreSQL protocol). You write
your model once, and the same code runs against any of the three —
handy if you develop against MySQL locally but deploy to YugabyteDB in
production, or vice versa.

If you're brand new to mydborm, the [Quickstart](guide/quickstart.md)
walks through defining a model and running your first queries in a few
minutes. This page is a tour of what's available.

---

## Install

```bash
pip install mydborm                          # core ORM — works right away
pip install mydborm[cli]                     # + the `mydborm` command-line tool
pip install mydborm[async]                   # + async/await support (for FastAPI etc.)
pip install mydborm[security]                # + password hashing & field encryption
pip install mydborm[dev,cli,async,security]  # everything, useful for contributing
```

If you only need the basics, `pip install mydborm` is enough — the
extras (`cli`, `async`, `security`) pull in additional dependencies
only used by those specific features, so you don't have to install
things you won't use.

---

## A first look

This is the entire lifecycle of a simple `User` model — connect,
define, create the table, and use it:

```python
from mydborm import db, BaseModel, IntField, StrField, BoolField
from mydborm import PasswordField, EmailValidator, RangeValidator

# 1. Tell mydborm which database to talk to.
#    "dialect" just means which database engine — "mysql", "postgres", or "yugabyte".
db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3306,
    user     = "root",
    password = "yourpassword",
    database = "mydb",
    charset  = "utf8mb4",
)

# 2. Describe your table as a Python class.
#    Each Field below is one column — it also validates values for you.
class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50,  nullable=False, unique=True)
    email    = StrField(max_length=255, nullable=False,
                        validators=[EmailValidator()])
    age      = IntField(nullable=True,
                        validators=[RangeValidator(min_val=13, max_val=120)])
    password = PasswordField(nullable=False)   # stored as a bcrypt hash, never plain text
    active   = BoolField(default=True)

# 3. Create the actual table in the database (run this once).
User.create_table()

# 4. Use it like a normal Python object.
uid = User.create(
    username = "alice",
    email    = "alice@example.com",
    age      = 28,
    password = "mysecretpass",   # hashed automatically before it's stored
)

user = User.get(id=uid)
if PasswordField.verify("mysecretpass", user["password"]):
    print("Login successful!")

# 5. Query with method chaining instead of writing SQL.
active_users = (User.query()
                    .where("active", True)
                    .order_by("username")
                    .limit(10)
                    .all())
```

A few things worth calling out for anyone new to this:

- `db.configure(...)` only needs to run once, usually when your app starts.
- Each `Field` (`IntField`, `StrField`, `BoolField`, ...) describes one
  database column **and** validates Python values before they're saved —
  if you try to save `age=200`, the `RangeValidator` above raises an
  error instead of silently writing bad data.
- `User.create_table()` only needs to run once per database (or each
  time your schema changes) — it's not something you call on every
  request.
- Everything after that — `.create()`, `.get()`, `.query()...` — is
  what you'll actually use day-to-day.

Continue with the [Quickstart](guide/quickstart.md) for a slower,
step-by-step walkthrough, or jump straight to the topic you need in
the **Guide** section in the sidebar.

---

## What's included

| Feature | What it gives you |
|---|---|
| Declarative models | Define a table as a Python class instead of SQL DDL |
| 29 field types | Typed columns — from `IntField` to `PasswordField` (bcrypt) and `EncryptedField` (AES) — see [Fields](guide/fields.md) |
| Full CRUD | `.create()`, `.get()`, `.all()`, `.filter()`, `.update()`, `.delete()` |
| QueryBuilder | Chainable `.where()`, `.order_by()`, `.limit()`, joins, `group_by`, subqueries — see [Query Builder](guide/query_builder.md) |
| Relationships | `has_many`, `belongs_to`, `many_to_many`, with lazy or eager loading — see [Relationships](guide/relationships.md) |
| Sessions | Track changes to several objects and save them together — see [Session](guide/session.md) |
| Bulk operations | Insert/update/delete thousands of rows in safe chunks, with automatic retry — see [Bulk Operations](guide/bulk_ops.md) |
| Transactions | Group statements so they all succeed or all roll back together — see [Transactions](guide/transactions.md) |
| Schema migrations | Detect model changes and generate the SQL to apply them — see [Migrations](guide/migrations.md) |
| Database-to-database migration | Move schema + data between MySQL, YugabyteDB, and PostgreSQL — see [Database Migration](guide/db_migration.md) |
| Validators | Built-in email/URL/range/length/choice checks, or write your own — see [Validators](guide/validators.md) |
| Security fields | Password hashing (bcrypt) and two-way field encryption (AES) — see [Security](guide/security.md) |
| Async support | `AsyncBaseModel` for use with FastAPI and other async frameworks — see [Async](guide/async.md) |
| CLI | A `mydborm` command-line tool for connecting, inspecting, and migrating without writing a script — see [CLI](guide/cli.md) |
| Custom exceptions | Specific, catchable error types instead of generic exceptions — see [Exceptions](guide/exceptions.md) |

mydborm currently has **1,000+ tests** with **96% coverage**, and is
tested against **Python 3.9, 3.10, 3.11, and 3.12**.

---

## Why mydborm instead of a bigger ORM?

If you've heard of SQLAlchemy or Peewee, here's the short version of
how mydborm compares. None of these are "better" in every way — it's a
tradeoff between flexibility and simplicity.

| | mydborm | SQLAlchemy | Peewee |
|---|---|---|---|
| Install size | **47 KB** | 3 MB | 800 KB |
| MySQL + PostgreSQL + YugabyteDB | **✅** | ✅ | ✅ |
| Async built-in | **✅** | needs an extra package | ❌ |
| Command-line tool included | **✅** | ❌ | ❌ |
| Password hashing built in | **✅** | ❌ | ❌ |
| Field-level encryption built in | **✅** | ❌ | ❌ |

mydborm trades some of SQLAlchemy's flexibility (it doesn't support
every database SQLAlchemy does, and it's less configurable under the
hood) for a much smaller footprint and things you'd otherwise have to
bolt on yourself — async support, a CLI, password hashing, and
distributed-SQL (YugabyteDB) support, all included from the start.

Pick mydborm if you want to be productive in MySQL, PostgreSQL, or
YugabyteDB quickly without learning a large framework. Pick SQLAlchemy
if you need to support many different databases or want fine-grained
control over query generation.
