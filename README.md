# mydborm

[![PyPI version](https://badge.fury.io/py/mydborm.svg)](https://pypi.org/project/mydborm/)
[![Python](https://img.shields.io/pypi/pyversions/mydborm)](https://pypi.org/project/mydborm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/codengers/mydborm/actions/workflows/ci.yml/badge.svg)](https://github.com/codengers/mydborm/actions)

**mydborm** is a production-grade lightweight ORM for **MySQL 8+**, **PostgreSQL**, and **YugabyteDB (YSQL)**.
Zero bloat. Declarative models. Full CRUD. Bulk ops. Async. Migrations. CLI included.

---

## Features

| Feature | Status |
|---|---|
| Declarative models with 11+ field types | ✅ |
| Full CRUD — create, get, all, filter, update, delete | ✅ |
| QueryBuilder — where, select, update, delete, order, limit, offset, paginate | ✅ |
| JOIN support — inner, left, right | ✅ |
| Aggregates — sum, avg, min, max, count, group_by, having | ✅ |
| Relationships — has_many, belongs_to, many_to_many | ✅ |
| Composite primary keys — `__pk__` | ✅ |
| Index management — create, drop, list, `__indexes__` | ✅ |
| Lifecycle hooks — before/after create, update, delete | ✅ |
| Bulk operations — create, update, delete, upsert | ✅ |
| Chunked bulk with retry + progress callback | ✅ |
| Raw SQL — execute, fetchall, fetchone | ✅ |
| Transactions — commit, rollback, savepoints | ✅ |
| Nested transactions + bulk_transaction | ✅ |
| Transaction retry on deadlock | ✅ |
| Async support — aiomysql + aiopg | ✅ |
| Connection pooling + ping + reconnect | ✅ |
| Schema migrations with history tracking | ✅ |
| MySQL + PostgreSQL + YugabyteDB dialect support | ✅ |
| UTF-8 / unicode support | ✅ |
| Custom exception hierarchy | ✅ |
| Rich CLI — version, ping, tables, inspect, migrate, pool | ✅ |
| CI — Python 3.9, 3.10, 3.11, 3.12 | ✅ |
| Mixins — SoftDeleteMixin, AuditMixin, TimestampMixin | ✅ |
| Session / Unit of Work — identity map, change tracking, flush | ✅ |
| Field validators — Email, URL, Regex, Range, MinLength, Choice | ✅ |
| PasswordField (bcrypt) + EncryptedField (Fernet) | ✅ |
| 950+ tests, 96% coverage | ✅ |

---

## Installation

```bash
pip install mydborm
pip install mydborm[cli]      # CLI support
pip install mydborm[async]    # Async support
```

---

## Quickstart

### 1. Configure connection

```python
from mydborm import db

# Direct config
db.configure(
    dialect  = "mysql",       # or "yugabyte" or "postgres"
    host     = "127.0.0.1",
    port     = 3306,
    user     = "root",
    password = "yourpassword",
    database = "mydb",
    charset  = "utf8mb4",     # UTF-8 support
    encoding = "utf-8",
)

# Or via environment variable
# export DATABASE_URL="mysql://root:password@localhost:3306/mydb"
db.from_env()
```

---

### 2. Define models

```python
from mydborm import BaseModel, IntField, StrField, BoolField, FloatField

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False, unique=True)
    active   = BoolField(default=True)

class Order(BaseModel):
    __tablename__ = "orders"
    id         = IntField(primary_key=True)
    user_id    = IntField(nullable=False)
    total      = FloatField(nullable=False)
    shipped    = BoolField(default=False)
```

---

### 3. Migrations

```python
from mydborm.migrations import migrate, migration_status

migrate(User,  description="Create users table")
migrate(Order, description="Create orders table")

for m in migration_status():
    print(m["description"], "→", "Applied")
```

---

### 4. CRUD operations

```python
# Create
uid = User.create(username="alice", email="alice@example.com")

# Read
user  = User.get(id=uid)
users = User.all()
devs  = User.filter(active=True)

# Update
User.update({"active": False}, id=uid)

# Delete
User.delete(id=uid)

# Aggregates
count = User.count()
exists = User.exists(email="alice@example.com")
```

---

### 5. Query builder

`QueryBuilder` provides a fully chainable, composable query API. All methods return `self` (except terminal methods), so they can be combined in any order.

#### Filtering

```python
# Simple equality
User.query().where("active", True).all()

# Comparison operators
User.query().where("id__gt", 5).all()          # id > 5
User.query().where("price__lte", 100).all()    # price <= 100
User.query().where("score__ne", 0).all()       # score != 0

# Pattern match
User.query().where("email__like", "%@gmail.com").all()

# IN list
User.query().where("id__in", [1, 2, 3]).all()

# NULL check
User.query().where("deleted_at__null", True).all()   # IS NULL
User.query().where("deleted_at__null", False).all()  # IS NOT NULL

# Chain multiple filters (AND)
results = (User.query()
               .where("active", True)
               .where("username__like", "ali%")
               .where("id__gt", 10)
               .all())
```

#### Operator reference

| Suffix | SQL | Example |
|---|---|---|
| *(none)* | `=` | `.where("active", True)` |
| `__gt` | `>` | `.where("age__gt", 18)` |
| `__lt` | `<` | `.where("price__lt", 50)` |
| `__gte` | `>=` | `.where("score__gte", 90)` |
| `__lte` | `<=` | `.where("stock__lte", 5)` |
| `__ne` | `!=` | `.where("status__ne", "banned")` |
| `__like` | `LIKE` | `.where("name__like", "A%")` |
| `__in` | `IN (…)` | `.where("id__in", [1,2,3])` |
| `__null` | `IS NULL` / `IS NOT NULL` | `.where("deleted_at__null", True)` |

#### Column projection — `select()`

Restrict which columns are fetched — useful for large tables or when you only need a subset of fields.

```python
# Fetch only id and username — avoids loading large columns
rows = User.query().select("id", "username").all()

# Combine with filters and ordering
rows = (User.query()
            .select("id", "email", "active")
            .where("active", True)
            .order_by("email")
            .limit(50)
            .all())

# Works with paginate() too
page = User.query().select("id", "username").paginate(page=1, per_page=20)

# count() is always correct regardless of select()
total = User.query().select("username").where("active", True).count()  # → N
```

#### Bulk update — `update()`

Update all rows matching the current WHERE filters in a single query.

```python
# Deactivate all suspended users
User.query().where("status", "suspended").update(active=False)

# Update multiple columns at once
Product.query().where("category", "clearance").update(discount=0.5, featured=False)

# No WHERE → updates every row
Item.query().update(stock=0)

# Returns the number of affected rows
count = Order.query().where("shipped", False).update(status="pending")
print(f"{count} orders updated")

# Chain with operators
Order.query().where("total__lt", 10).update(flagged=True)
```

#### Ordering, limit, offset

```python
# Ascending (default)
User.query().order_by("username").all()

# Descending
Order.query().order_by("total", desc=True).limit(10).all()

# Skip + take
User.query().offset(20).limit(10).all()
```

#### Terminal methods

```python
User.query().where("active", True).all()        # list of rows
User.query().where("email", "a@b.com").first()  # first row or None
User.query().where("active", True).count()      # int
User.query().where("email", "a@b.com").exists() # bool
User.query().where("active", False).delete()    # affected row count
User.query().where("active", False).update(role="guest")  # affected row count
```

#### Aggregates

```python
total  = User.query().where("active", True).count()
avg    = Order.query().avg("total")
top5   = Order.query().order_by("total", desc=True).limit(5).all()
revenue = Order.query().where("shipped", True).sum("total")
min_p  = Product.query().min("price")
max_p  = Product.query().max("price")
```

#### Group by + having

```python
# Count orders per user
rows = (Order.query()
             .group_by("user_id")
             .having("COUNT(*) > 2")
             .all())

# Total revenue per status
rows = (Order.query()
             .select("status")
             .group_by("status")
             .having("SUM(total) > %s", 1000)
             .all())
```

#### Pagination

```python
page = (User.query()
            .where("active", True)
            .order_by("id")
            .paginate(page=2, per_page=20))
# Returns:
# {
#   "data"    : [<ModelInstance>, ...],
#   "total"   : 57,       # total matching rows
#   "pages"   : 3,        # total pages
#   "page"    : 2,        # current page
#   "per_page": 20,       # rows per page
# }

# page < 1 is clamped to 1
page = User.query().paginate(page=0)  # treated as page=1
```

#### Subqueries

```python
# Use one query's result inside another
active_ids = User.query().where("active", True).subquery("id")
orders = Order.query().where("user_id__in", active_ids).all()
```

---

### 6. JOIN support

```python
# INNER JOIN
rows = (User.query()
            .inner_join("orders", "users.id = orders.user_id")
            .where("orders.shipped", True)
            .order_by("users.username")
            .all())

# LEFT JOIN — include users with no orders
rows = (User.query()
            .left_join("orders", "users.id = orders.user_id")
            .all())

# Multiple JOINs
rows = (Product.query()
               .inner_join("categories",
                           "products.category_id = categories.id")
               .inner_join("orders",
                           "products.id = orders.product_id")
               .where("categories.name", "Electronics")
               .all())
```

---

### 7. Bulk operations

```python
# Bulk create
User.bulk_create([
    {"username": "alice", "email": "alice@example.com"},
    {"username": "bob",   "email": "bob@example.com"},
])

# Bulk update
User.bulk_update([
    {"id": 1, "active": False},
    {"id": 2, "active": False},
])

# Bulk delete
User.bulk_delete([1, 2, 3])

# Bulk upsert — insert or update on conflict
User.bulk_upsert(
    [{"email": "alice@example.com", "username": "alice_v2"}],
    conflict_key  = "email",
    update_fields = ["username"]
)
```

---

### 8. Chunked bulk with retry

```python
from mydborm.bulk import chunked_bulk_create

def on_progress(done, total):
    print(f"Progress: {done}/{total}")

result = chunked_bulk_create(
    User, records,
    chunk_size  = 500,
    retries     = 3,
    retry_delay = 0.5,
    on_progress = on_progress,
)
print(result.summary())
# Operation : insert
# Total     : 10000
# Inserted  : 10000
# Chunks    : 20
# Success   : 100.0%
# Duration  : 2.4s
```

---

### 9. Transactions + savepoints

```python
# Basic transaction
with db.transaction():
    db.execute("INSERT INTO users ...")
    db.execute("INSERT INTO profiles ...")

# Savepoint — partial rollback
with db.transaction():
    User.create(username="alice")
    try:
        with db.savepoint("after_alice"):
            User.create(username="bob")
            raise Exception("bob failed")
    except Exception:
        pass  # only bob rolled back, alice kept

# Bulk transaction — atomic multi-model
with db.bulk_transaction():
    db.execute("INSERT INTO orders ...")
    db.execute("INSERT INTO order_items ...")

# Nested transaction
with db.transaction():
    User.create(username="outer")
    with db.nested_transaction():
        User.create(username="inner")

# Retry on deadlock
with db.transaction_with_retry(retries=3):
    db.execute("UPDATE accounts SET balance = balance - 100 ...")
    db.execute("UPDATE accounts SET balance = balance + 100 ...")
```

---

### 10. Relationships

```python
# has_many
author = Author.get(id=1)
books  = author.has_many(Book, foreign_key="author_id")

# belongs_to
book   = Book.get(id=1)
author = book.belongs_to(Author, foreign_key="author_id")

# many_to_many
student = Student.get(id=1)
courses = student.many_to_many(
    Course,
    join_table = "student_courses",
    source_key = "student_id",
    target_key = "course_id"
)
```

---

### 11. Async support

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
        port     = 3307,
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

---

### 12. Raw SQL

```python
# Execute
db.execute("UPDATE users SET active = %s WHERE id = %s", [False, 1])

# Fetch all
rows = db.fetchall("SELECT * FROM users WHERE active = %s", [True])

# Fetch one
row = db.fetchone("SELECT * FROM users WHERE email = %s",
                  ["alice@example.com"])

# Utilities
tables = db.list_tables()
exists = db.table_exists("users")
```

---

### 13. Connection pooling

```python
db.configure_pool(pool_size=10, max_overflow=20)
print(db.pool_status())
db.ping()       # True / False
db.reconnect()  # force reconnect
```

---

### 14. Error handling

```python
from mydborm import (
    MydbormError, BulkInsertError, ValidationError,
    TransactionError, SchemaError, RetryExhaustedError
)

try:
    User.bulk_create(records)
except BulkInsertError as e:
    print(f"Inserted: {e.inserted}, Failed: {e.failed}")
    for err in e.errors:
        print(f"  Chunk {err['chunk']}: {err['error']}")

try:
    with db.transaction_with_retry(retries=3):
        db.execute("UPDATE accounts ...")
except RetryExhaustedError as e:
    print(f"Failed after {e.attempts} attempts: {e.last_error}")
```

---

### 15. Composite primary keys

```python
class OrderItem(BaseModel):
    __tablename__ = "order_items"
    __pk__        = ("order_id", "product_id")   # composite PK
    order_id   = IntField(nullable=False)
    product_id = IntField(nullable=False)
    qty        = IntField(nullable=False)

OrderItem.create_table()
OrderItem.create(order_id=1, product_id=42, qty=3)
row = OrderItem.get(order_id=1, product_id=42)
```

---

### 16. Index management

```python
class Article(BaseModel):
    __tablename__ = "articles"
    __indexes__   = [
        {"name": "idx_slug",   "columns": ["slug"],        "unique": True},
        {"name": "idx_status", "columns": ["status", "published_at"]},
    ]
    id           = IntField(primary_key=True)
    slug         = StrField(max_length=200, nullable=False)
    status       = StrField(max_length=20)
    published_at = DateTimeField()

Article.create_table()          # indexes created automatically

# Manual index management
Article.create_index("idx_author", ["author_id"])
Article.drop_index("idx_author")
print(Article.list_indexes())   # [{"name": ..., "columns": [...], "unique": ...}]
```

---

### 17. Lifecycle hooks

```python
class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False)

    @classmethod
    def before_create(cls, data: dict) -> dict:
        data["username"] = data["username"].strip().lower()
        return data

    @classmethod
    def after_create(cls, record_id, data: dict):
        print(f"User {record_id} created: {data['username']}")

    @classmethod
    def before_update(cls, data: dict, **filters) -> dict:
        return data

    @classmethod
    def after_delete(cls, deleted_count: int, **filters):
        print(f"Deleted {deleted_count} user(s)")

uid = User.create(username="  Alice  ", email="alice@example.com")
# → User 1 created: alice
User.delete(id=uid)
# → Deleted 1 user(s)
```

---

### 18. Mixins

Drop-in mixins that add common columns and behaviour to any model.

#### TimestampMixin — automatic created_at / updated_at

```python
from mydborm import BaseModel, IntField, StrField
from mydborm.mixins import TimestampMixin

class Post(TimestampMixin, BaseModel):
    __tablename__ = "posts"
    id      = IntField(primary_key=True)
    title   = StrField(max_length=200)

Post.create_table()
post = Post.create(title="Hello World")
# post["created_at"] and post["updated_at"] set automatically
```

#### SoftDeleteMixin — logical deletion via deleted_at

```python
from mydborm.mixins import SoftDeleteMixin

class User(SoftDeleteMixin, BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100)

User.create_table()
user = User.create(username="alice")

User.soft_delete(id=user["id"])      # sets deleted_at, row stays in DB
User.restore(id=user["id"])          # clears deleted_at
active = User.active().all()         # WHERE deleted_at IS NULL
deleted = User.deleted().all()       # WHERE deleted_at IS NOT NULL
User.hard_delete(id=user["id"])      # permanent DELETE
```

#### AuditMixin — track who created / updated each row

```python
from mydborm.mixins import AuditMixin

class Document(AuditMixin, BaseModel):
    __tablename__ = "documents"
    id      = IntField(primary_key=True)
    title   = StrField(max_length=200)

Document.create_table()
doc = Document.create(title="Spec", created_by="alice", updated_by="alice")
Document.update({"updated_by": "bob"}, id=doc["id"])
```

---

### 19. Session / Unit of Work

`Session` implements an identity map and change tracker — load rows once, mutate them freely, then flush all changes in a single pass.

```python
from mydborm import Session

# Basic usage — explicit flush
s = Session()
user = s.get(User, id=1)          # loads from DB, registers in identity map
user["username"] = "alice_v2"     # tracked as dirty
s.is_dirty(user)                  # → True
s.dirty_fields(user)              # → ["username"]
s.original_value(user, "username")# → "alice"
s.flush()                         # UPDATE written to DB, marked clean

# Add new records
s.add(User, username="dave", email="dave@example.com")
s.flush()                         # INSERT for all pending new records

# Delete
s.delete(user)
s.flush()                         # DELETE executed

# Rollback — discard all in-memory changes (no DB writes)
user["username"] = "wrong_name"
s.rollback()                      # reverts to "alice_v2"

# Context manager — auto-flush on __exit__, rollback on exception
with Session() as s:
    user = s.get(User, id=1)
    user["username"] = "context_user"
# flush() called automatically on clean exit

# Query within a session
with Session() as s:
    active_users = s.all(User)
    inactive     = s.filter(User, active=False)

# Helpers
s.expunge(user)      # remove one object from the session
s.expunge_all()      # remove all tracked objects
s.close()            # alias for expunge_all
s.stats()            # {"tracked": 3, "new": 1, "dirty": 2, "deleted": 0}
```

---

### 20. Field validators

Attach reusable validation rules to any field.

```python
from mydborm.fields import (
    StrField, IntField,
    ValidationRule, EmailValidator, UrlValidator,
    RegexValidator, RangeValidator, MinLengthValidator, ChoiceValidator,
)

class Profile(BaseModel):
    __tablename__ = "profiles"
    id       = IntField(primary_key=True)
    email    = StrField(max_length=255, validators=[EmailValidator()])
    website  = StrField(max_length=500, validators=[UrlValidator()])
    username = StrField(max_length=50,  validators=[
                    MinLengthValidator(3),
                    RegexValidator(r"^[a-z0-9_]+$", "lowercase alphanumeric only"),
               ])
    age      = IntField(validators=[RangeValidator(18, 120)])
    role     = StrField(max_length=20, validators=[
                    ChoiceValidator(["admin", "editor", "viewer"]),
               ])
```

#### PasswordField — bcrypt hashing

```python
from mydborm.fields import PasswordField

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    password = PasswordField(rounds=12)

uid  = User.create(username="alice", password="secret123")
# stored as bcrypt hash

user = User.get(id=uid)
PasswordField().verify("secret123", user["password"])   # → True
PasswordField().needs_rehash(user["password"])           # → False
hashed = PasswordField.hash("newpassword")
```

#### EncryptedField — Fernet symmetric encryption

```python
from mydborm.fields import EncryptedField

key = EncryptedField.generate_key()  # generate once, store securely

class Secret(BaseModel):
    __tablename__ = "secrets"
    id   = IntField(primary_key=True)
    data = EncryptedField(secret_key=key)

Secret.create(data="top secret value")  # stored encrypted
row = Secret.get(id=1)
plain = Secret._fields["data"].decrypt_value(row["data"])  # → "top secret value"
```

---

## Field types

### Core fields

| Field | MySQL | PostgreSQL / YugabyteDB |
|---|---|---|
| `IntField` | `INT` | `INTEGER` |
| `StrField(max_length)` | `VARCHAR(n)` | `VARCHAR(n)` |
| `TextField` | `TEXT` | `TEXT` |
| `BoolField` | `TINYINT(1)` | `BOOLEAN` |
| `FloatField` | `FLOAT` | `FLOAT` |
| `DecimalField(precision, scale)` | `DECIMAL(p,s)` | `DECIMAL(p,s)` |
| `DateField` | `DATE` | `DATE` |
| `DateTimeField` | `DATETIME` | `TIMESTAMP` |
| `JSONField` | `JSON` | `JSONB` |
| `ForeignKeyField(to)` | `INT` | `INTEGER` |

### Extended fields

| Field | MySQL | Notes |
|---|---|---|
| `TinyIntField` | `TINYINT` | −128 to 127 |
| `SmallIntField` | `SMALLINT` | −32768 to 32767 |
| `BigIntField` | `BIGINT` | 64-bit integer |
| `UnsignedBigIntField` | `BIGINT UNSIGNED` | 0 to 2⁶⁴−1 |
| `DoubleField` | `DOUBLE` | 64-bit float |
| `BitField` | `BIT(n)` | bit mask |
| `CharField(max_length)` | `CHAR(n)` | fixed-length string |
| `TinyTextField` | `TINYTEXT` | up to 255 bytes |
| `MediumTextField` | `MEDIUMTEXT` | up to 16 MB |
| `LongTextField` | `LONGTEXT` | up to 4 GB |
| `BinaryField(length)` | `BINARY(n)` | fixed binary; `BYTEA` on PG |
| `VarBinaryField(max_length)` | `VARBINARY(n)` | variable binary; `BYTEA` on PG |
| `BlobField` | `BLOB` | binary large object |
| `TimeField` | `TIME` | HH:MM:SS |
| `TimestampField` | `TIMESTAMP` | Unix timestamp |
| `EnumField(choices)` | `ENUM(...)` | restricted string set |
| `SetField(choices)` | `SET(...)` | multi-value set |
| `PasswordField` | `VARCHAR(255)` | bcrypt hash |
| `EncryptedField` | `TEXT` | Fernet-encrypted |

---

## CLI commands

```bash
mydborm version
mydborm ping     --dialect mysql --port 3306 --password root
mydborm tables   --dialect mysql --port 3306 --password root
mydborm inspect  --dialect mysql --port 3306 --password root
mydborm migrate  --dialect mysql --port 3306 --password root --status
mydborm migrate  --dialect mysql --port 3306 --password root \
                 --model myapp.models.User
mydborm pool     --dialect mysql --port 3306 --password root
```

---

## Docker quickstart

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: mydb
    ports:
      - "3306:3306"

  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: mydb
    ports:
      - "5432:5432"

  yugabyte:
    image: yugabytedb/yugabyte:latest
    command: bash -c "bin/yugabyted start --daemon=false"
    ports:
      - "5433:5433"
```

```bash
docker compose up -d
```

---

## Dialect support

### MySQL

```python
db.configure(dialect="mysql", host="127.0.0.1", port=3306,
             user="root", password="root", database="mydb")
```

### PostgreSQL

```python
db.configure(dialect="postgres", host="127.0.0.1", port=5432,
             user="postgres", password="postgres", database="mydb")
```

PostgreSQL-specific behaviour:
- `SERIAL` / `BIGSERIAL` primary keys
- Native `BOOLEAN`
- `JSONB` storage for `JSONField`
- Double-quoted identifiers
- `RETURNING id` on INSERT
- `ON CONFLICT DO UPDATE` for upsert

### YugabyteDB

```python
db.configure(dialect="yugabyte", host="127.0.0.1", port=5433,
             user="yugabyte", password="yugabyte", database="yugabyte")
```

YugabyteDB uses YSQL (PostgreSQL-compatible) and behaves identically to the PostgreSQL dialect with full distributed SQL support.

---

## Running tests

```bash
pip install mydborm[dev]
pytest
```

---

## Project structure

```
mydborm/
├── mydborm/
│   ├── __init__.py       # Public API surface
│   ├── db.py             # Connection manager, pooling, transactions
│   ├── fields.py         # 30+ field types with validators + dialect SQL
│   ├── model.py          # BaseModel + QueryBuilder + relationships
│   ├── bulk.py           # Chunked bulk ops + BulkResult + retry
│   ├── session.py        # Session — identity map + unit of work
│   ├── async_db.py       # Async ORM via aiomysql/aiopg
│   ├── migrations.py     # Schema migration engine
│   ├── mixins.py         # SoftDeleteMixin, AuditMixin, TimestampMixin
│   ├── exceptions.py     # 24 custom exception types
│   ├── cli.py            # Rich CLI commands
│   └── dialects/
│       ├── mysql.py      # MySQL SQL generation
│       ├── postgres.py   # PostgreSQL SQL generation
│       └── yugabyte.py   # YugabyteDB SQL generation
├── tests/                # 950+ tests, 96% coverage
└── pyproject.toml
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## Author

**Atikrant Upadhye**
[PyPI](https://pypi.org/project/mydborm/) · [GitHub](https://github.com/codengers/mydborm)

---

## License

MIT License — see [LICENSE](LICENSE) for details.