# mydborm

> **Lightweight Python ORM for MySQL and YugabyteDB.**
> Ship database-backed apps and data pipelines in minutes — not hours.

[![PyPI version](https://badge.fury.io/py/mydborm.svg)](https://pypi.org/project/mydborm/)
[![Python](https://img.shields.io/pypi/pyversions/mydborm)](https://pypi.org/project/mydborm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/codengers/mydborm/actions/workflows/ci.yml/badge.svg)](https://github.com/codengers/mydborm/actions)
[![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen)](https://github.com/codengers/mydborm)
[![PyPI Downloads](https://img.shields.io/pypi/dm/mydborm)](https://pypi.org/project/mydborm/)

---

## Why mydborm?

SQLAlchemy is powerful — and complex. Peewee is simple — but not distributed-SQL-aware. **mydborm sits in the middle**: zero-boilerplate Python classes, parameterized queries, bulk operations, and first-class [YugabyteDB](https://www.yugabyte.com/) support — all in a 47 KB package with no heavy dependencies.

| | mydborm | SQLAlchemy | Peewee |
|---|---|---|---|
| Install size | **47 KB** | 3 MB | 800 KB |
| MySQL support | ✅ | ✅ | ✅ |
| YugabyteDB (Distributed SQL) | ✅ Native | ⚠️ Workaround | ❌ |
| PostgreSQL | ✅ | ✅ | ✅ |
| Async built-in | ✅ | needs ext | ❌ |
| Password hashing | ✅ bcrypt | ❌ | ❌ |
| AES field encryption | ✅ Fernet | ❌ | ❌ |
| Soft delete mixin | ✅ | ❌ | ❌ |
| CLI included | ✅ | ❌ | ❌ |
| Learning curve | **Low** | High | Medium |

---

## Key Features

- **Lightweight & fast** — 47 KB, two runtime dependencies, sub-millisecond query overhead.
- **Native Distributed SQL** — purpose-built dialect for YugabyteDB (YSQL). Run the exact same model code against a single-node MySQL dev database and a distributed YugabyteDB production cluster.
- **Intuitive syntax** — one Python class = one table. No metaclass magic to learn, no session factories, no engine strings.
- **29 field types** — covers everything from `TinyIntField` to `EncryptedField` (AES-128) and `PasswordField` (bcrypt).
- **Bulk operations** — chunked `bulk_create / bulk_update / bulk_delete` with retry, exponential backoff, and progress callbacks. Built for data pipelines.
- **Rich QueryBuilder** — `where()`, `or_where()`, `select()`, `distinct()`, `update()`, `delete()`, `paginate()`, `group_by()`, `having()`, joins, subqueries.
- **Mixins** — `SoftDeleteMixin`, `AuditMixin`, `TimestampMixin` drop into any model in one line.
- **Lifecycle hooks** — `before_create`, `after_create`, `before_update`, `after_update`, `before_delete`, `after_delete` with zero registration ceremony.
- **Async support** — `AsyncBaseModel` via `aiomysql` and `aiopg` for FastAPI and async microservices.
- **Security-first fields** — `PasswordField` auto-hashes on write; `EncryptedField` auto-encrypts. Plain text never stored.
- **Schema migrations** — auto-generate versioned SQL diff files. Run `mydborm generate --model myapp.models.User` from the CLI.

---

## Installation

```bash
# Core — MySQL + YugabyteDB + PostgreSQL
pip install mydborm

# Add CLI tools
pip install mydborm[cli]

# Add async support (FastAPI / asyncio)
pip install mydborm[async]

# Add security fields (bcrypt + AES)
pip install mydborm[security]

# Everything
pip install mydborm[cli,async,security]
```

**Runtime requirements:** Python 3.9+ · `mysql-connector-python` · `psycopg2-binary`

---

## Quick Start

### Scenario A — MySQL

Standard relational database. Works with any MySQL 8+ instance, including RDS and Cloud SQL.

```python
# ── quickstart_mysql.py ────────────────────────────────────────────────────
from mydborm import (
    db,
    BaseModel,
    IntField,
    StrField,
    BoolField,
    FloatField,
    EmailValidator,
)

# 1. Configure once — thread-safe, connection-pooled
db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3306,
    user     = "root",
    password = "yourpassword",
    database = "shop",
    charset  = "utf8mb4",
)

# 2. Declare your model — one class, one table
class Product(BaseModel):
    __tablename__ = "products"
    id       = IntField(primary_key=True)
    name     = StrField(max_length=120, nullable=False)
    sku      = StrField(max_length=20,  nullable=False, unique=True)
    price    = FloatField(nullable=False)
    in_stock = BoolField(default=True)

# 3. Create the table (safe to call repeatedly — IF NOT EXISTS)
Product.create_table()

# 4. Insert a record — returns the new primary key (int)
pid = Product.create(
    name     = "Wireless Keyboard",
    sku      = "KB-WL-001",
    price    = 49.99,
    in_stock = True,
)
print(f"Created product #{pid}")   # Created product #1

# 5. Read it back
product = Product.get(id=pid)
print(product["name"])   # Wireless Keyboard

# 6. Query with filters
budget_items = (
    Product.query()
           .where("price__lte", 50.0)
           .where("in_stock", True)
           .order_by("price")
           .all()
)
print(f"Found {len(budget_items)} items under $50")

# 7. Update
Product.update({"price": 44.99}, id=pid)

# 8. Delete
Product.delete(id=pid)
```

---

### Scenario B — YugabyteDB (Distributed SQL)

Switch `dialect` and `port`. **Everything else is identical.** The same model, same CRUD calls, same query builder — now running against a horizontally scalable, fault-tolerant distributed cluster.

```python
# ── quickstart_yugabyte.py ─────────────────────────────────────────────────
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField

# The ONLY change from MySQL: dialect + port
db.configure(
    dialect  = "yugabyte",       # ← changed
    host     = "127.0.0.1",
    port     = 5433,             # ← changed (YugabyteDB YSQL default)
    user     = "yugabyte",
    password = "yugabyte",
    database = "yugabyte",
)

# Same model — no changes needed
class Product(BaseModel):
    __tablename__ = "products"
    id       = IntField(primary_key=True)
    name     = StrField(max_length=120, nullable=False)
    sku      = StrField(max_length=20,  nullable=False, unique=True)
    price    = FloatField(nullable=False)
    in_stock = BoolField(default=True)

Product.create_table()

# mydborm handles the dialect differences internally:
#   MySQL      → AUTO_INCREMENT, backtick identifiers, TINYINT(1) for bool
#   YugabyteDB → SERIAL, double-quote identifiers, native BOOLEAN, JSONB, RETURNING id

pid = Product.create(
    name     = "Wireless Keyboard",
    sku      = "KB-WL-001",
    price    = 49.99,
    in_stock = True,
)

product = Product.get(id=pid)
print(product["name"])   # Wireless Keyboard — same API, distributed backend
```

**YugabyteDB dialect differences handled automatically by mydborm:**

| Feature | MySQL | YugabyteDB |
|---|---|---|
| Primary key | `AUTO_INCREMENT` | `SERIAL` |
| Identifiers | `` `backticks` `` | `"double-quotes"` |
| Boolean | `TINYINT(1)` | `BOOLEAN` |
| JSON | `JSON` | `JSONB` (indexable) |
| Timestamps | `DATETIME` | `TIMESTAMPTZ` |
| Insert return | `lastrowid` | `RETURNING id` |

---

## CRUD Reference

All examples use the `Product` model from the Quick Start above.

### Create

```python
# Single insert — returns new primary key (int)
pid = Product.create(name="Mouse", sku="MS-001", price=29.99, in_stock=True)

# Bulk insert — one SQL statement, returns row count
records = [
    {"name": f"Item {i}", "sku": f"SKU-{i:04d}", "price": float(i), "in_stock": True}
    for i in range(1, 1001)
]
count = Product.bulk_create(records)
print(f"Inserted {count} products")   # Inserted 1000 products

# Chunked bulk — for very large datasets with retry + progress
from mydborm.bulk import chunked_bulk_create

result = chunked_bulk_create(
    Product,
    records,
    chunk_size  = 500,
    retries     = 3,
    on_progress = lambda done, total: print(f"{done}/{total}"),
)
print(result.summary())
```

### Read

```python
# By primary key — returns ModelInstance or None
product = Product.get(id=1)

# Equality filter shorthand
in_stock = Product.filter(in_stock=True)

# Full query builder
results = (
    Product.query()
           .where("price__gte", 10.0)        # price >= 10
           .where("price__lte", 100.0)       # price <= 100
           .where("name__like", "%board%")   # LIKE
           .where("in_stock", True)
           .order_by("price", desc=False)
           .limit(20)
           .offset(0)
           .all()
)

# Aggregates
total    = Product.count(in_stock=True)
cheapest = Product.query().min("price")
avg      = Product.query().where("in_stock", True).avg("price")

# Check existence
exists = Product.exists(sku="KB-WL-001")   # True / False
```

**WHERE operators:**

| Syntax | SQL equivalent | Example |
|---|---|---|
| `"field", value` | `= %s` | `.where("in_stock", True)` |
| `"field__gt"` | `> %s` | `.where("price__gt", 50.0)` |
| `"field__lt"` | `< %s` | `.where("price__lt", 100.0)` |
| `"field__gte"` | `>= %s` | `.where("price__gte", 10.0)` |
| `"field__lte"` | `<= %s` | `.where("price__lte", 99.99)` |
| `"field__ne"` | `!= %s` | `.where("status__ne", "deleted")` |
| `"field__like"` | `LIKE %s` | `.where("name__like", "%board%")` |
| `"field__in"` | `IN (...)` | `.where("id__in", [1, 2, 3])` |
| `"field__null"` | `IS NULL / IS NOT NULL` | `.where("deleted_at__null", True)` |

### Update

```python
# Update by any field — returns rows affected (int)
rows = Product.update({"price": 39.99}, id=1)

# Update multiple rows
rows = Product.update({"in_stock": False}, price=0.0)

# Bulk update
updates = [{"id": i, "price": float(i) * 0.9} for i in range(1, 1001)]
Product.bulk_update(updates, key="id")
```

### Delete

```python
# Delete by any field — returns rows deleted (int)
deleted = Product.delete(id=1)

# Bulk delete by IDs
ids = [p["id"] for p in Product.filter(in_stock=False)]
Product.bulk_delete(ids)

# Soft delete (keeps row, sets deleted_at timestamp)
from mydborm.mixins import SoftDeleteMixin

class Post(BaseModel, SoftDeleteMixin):
    __tablename__ = "posts"
    id    = IntField(primary_key=True)
    title = StrField(max_length=200, nullable=False)

Post.soft_delete(id=1)            # sets deleted_at — row hidden from .all()
Post.restore(id=1)                # clears deleted_at — row visible again
Post.purge(id=1)                  # permanent delete
```

---

## QueryBuilder Reference

`QueryBuilder` is returned by `Model.query()` and provides a fully chainable, composable query API. Every method returns `self` so they can be combined in any order before calling a terminal method.

### Filtering — `where()` and `or_where()`

```python
# AND conditions — all where() calls are joined with AND
Product.query().where("in_stock", True).where("price__lte", 50.0).all()
# → WHERE in_stock = 1 AND price <= 50.0

# OR conditions — or_where() calls are grouped and ANDed with the WHERE block
Order.query().or_where("status", "pending").or_where("status", "retry").all()
# → WHERE (status = 'pending' OR status = 'retry')

# AND + OR combined
Order.query()
     .where("user_id", 5)
     .or_where("status", "pending")
     .or_where("status", "retry")
     .all()
# → WHERE user_id = 5 AND (status = 'pending' OR status = 'retry')

# or_where() supports all the same operators as where()
Item.query().or_where("price__lt", 1.0).or_where("price__gt", 99.0).all()
Item.query().or_where("name__in", ["Apple", "Banana"]).all()
Item.query().or_where("deleted_at__null", True).all()
```

### Column projection — `select()`

```python
# Fetch only specific columns — avoids loading large TEXT/BLOB columns
rows = User.query().select("id", "username").where("active", True).all()

# Works with ordering, limit, and paginate
page = (Product.query()
               .select("id", "name", "price")
               .where("in_stock", True)
               .order_by("price")
               .paginate(page=1, per_page=20))

# count() is always COUNT(*) regardless of select()
total = User.query().select("username").count()  # counts all rows
```

### Deduplication — `distinct()`

```python
# SELECT DISTINCT — remove duplicate rows
User.query().select("country").distinct().all()
# → SELECT DISTINCT country FROM users

# Combine with filters and ordering
User.query().select("role").distinct().where("active", True).order_by("role").all()

# distinct() does not affect count() — use group_by for distinct counts
Item.query().select("status").distinct().count()  # still COUNT(*) of all rows
```

### Bulk update — `update()`

```python
# Update all matching rows — returns affected row count
count = Order.query().where("status", "pending").update(status="processing")

# OR conditions work too
Item.query().or_where("name", "Cherry").or_where("name", "Elderberry").update(stock=0)

# No WHERE → updates every row in the table
Product.query().update(featured=False)
```

### Bulk delete — `delete()`

```python
# Delete all matching rows — returns deleted row count
count = Order.query().where("status__ne", "shipped").delete()

# Combine with OR
Item.query().or_where("stock", 0).or_where("in_stock", False).delete()
```

### Pagination — `paginate()`

```python
page = (Product.query()
               .where("in_stock", True)
               .order_by("price")
               .paginate(page=2, per_page=20))
# Returns:
# {
#   "data"    : [<ModelInstance>, ...],   # rows for this page
#   "total"   : 57,                        # total matching rows
#   "pages"   : 3,                         # total pages
#   "page"    : 2,                         # current page (clamped to 1 if < 1)
#   "per_page": 20,                        # rows per page
# }
```

### Aggregates

```python
Product.query().count()                            # total rows
Product.query().where("in_stock", True).count()   # filtered count
Product.query().sum("price")
Product.query().avg("price")
Product.query().min("price")
Product.query().max("price")
```

### Group by + having

```python
# Revenue per region
rows = (Order.query()
             .select("region")
             .group_by("region")
             .having("SUM(total) > %s", 10000)
             .all())

# Count orders per user
rows = Order.query().group_by("user_id").having("COUNT(*) > 2").all()
```

### Joins

```python
rows = (User.query()
            .inner_join("orders", "users.id = orders.user_id")
            .where("orders.shipped", True)
            .order_by("users.username")
            .all())

rows = (User.query()
            .left_join("orders", "users.id = orders.user_id")
            .all())
```

### Subqueries

```python
active_ids = User.query().where("active", True).subquery("id")
orders = Order.query().where("user_id__in", active_ids).all()
```

### Terminal methods summary

| Method | Returns | Description |
|---|---|---|
| `.all()` | `list[ModelInstance]` | All matching rows |
| `.first()` | `ModelInstance \| None` | First matching row |
| `.count()` | `int` | `COUNT(*)` of matching rows |
| `.exists()` | `bool` | True if any row matches |
| `.update(**kwargs)` | `int` | Rows updated |
| `.delete()` | `int` | Rows deleted |
| `.paginate(page, per_page)` | `dict` | Paginated result with metadata |

---

## Advanced Usage — Data Science & Pipelines

mydborm is well-suited for data extraction scripts and ingestion pipelines where you need to query a table, transform rows, and feed them into downstream tools (pandas, Polars, Kafka producers, etc.).

### Query → pandas DataFrame

```python
import pandas as pd
from mydborm import db, BaseModel, IntField, StrField, FloatField, DateTimeField

db.configure(dialect="mysql", host="127.0.0.1", port=3306,
             user="root", password="root", database="analytics")

class SalesEvent(BaseModel):
    __tablename__ = "sales_events"
    id         = IntField(primary_key=True)
    product_id = IntField(nullable=False)
    region     = StrField(max_length=50, nullable=False)
    revenue    = FloatField(nullable=False)
    created_at = DateTimeField(nullable=True)

# Pull last 30 days of high-value events
rows = (
    SalesEvent.query()
              .where("revenue__gte", 1000.0)
              .where("region__in", ["NA", "EU", "APAC"])
              .order_by("created_at", desc=True)
              .limit(10_000)
              .all()
)

# Convert to list of dicts — one line
records = [row.to_dict() for row in rows]

# Load into pandas
df = pd.DataFrame(records)
print(df.head())
print(df.groupby("region")["revenue"].sum())
```

### Bulk ingestion pipeline

```python
from mydborm.bulk import chunked_bulk_create
import csv

def ingest_csv(filepath: str, model_class, chunk_size: int = 500):
    """Load a CSV file into a mydborm model table — with retry and progress."""
    with open(filepath, newline="", encoding="utf-8") as f:
        reader  = csv.DictReader(f)
        records = list(reader)

    result = chunked_bulk_create(
        model_class,
        records,
        chunk_size  = chunk_size,
        retries     = 3,
        retry_delay = 0.5,
        on_progress = lambda done, total:
            print(f"\rIngesting... {done:,}/{total:,}", end=""),
    )
    print(f"\nDone. {result.inserted:,} rows inserted, {result.failed} failed.")
    if result.has_errors:
        for err in result.errors:
            print(f"  Chunk {err['chunk']}: {err['error']}")
    return result

ingest_csv("sales_2024.csv", SalesEvent, chunk_size=500)
```

### FastAPI microservice — async mode

```python
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from mydborm.async_db import async_db, AsyncBaseModel
from mydborm import IntField, StrField, FloatField, BoolField

class Product(AsyncBaseModel):
    __tablename__ = "products"
    id       = IntField(primary_key=True)
    name     = StrField(max_length=120, nullable=False)
    price    = FloatField(nullable=False)
    in_stock = BoolField(default=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await async_db.configure(
        dialect="mysql", host="127.0.0.1", port=3306,
        user="root", password="root", database="shop"
    )
    await Product.create_table()
    yield
    await async_db.close()

app = FastAPI(lifespan=lifespan)

@app.get("/products/{product_id}")
async def get_product(product_id: int):
    product = await Product.get(id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Not found")
    return product.to_dict()

@app.get("/products")
async def list_products(in_stock: bool = True):
    products = await Product.filter(in_stock=in_stock)
    return [p.to_dict() for p in products]

@app.post("/products")
async def create_product(name: str, price: float):
    pid = await Product.create(name=name, price=price, in_stock=True)
    return {"id": pid}
```

### YugabyteDB — distributed ingestion at scale

```python
# Switch dialect to target a YugabyteDB cluster.
# The chunked_bulk_create call is identical — mydborm handles
# ON CONFLICT DO UPDATE and RETURNING id automatically.

db.configure(
    dialect  = "yugabyte",
    host     = "yb-node-1.prod.internal",  # any node in the cluster
    port     = 5433,
    user     = "app_user",
    password = "securepassword",
    database = "analytics",
)

result = chunked_bulk_create(SalesEvent, records, chunk_size=1000)
print(result.summary())
# Operation : insert
# Total     : 500000
# Inserted  : 500000
# Failed    : 0
# Chunks    : 500
# Duration  : 42.3s
```

---

## Security Fields

```python
import os
from mydborm import db, BaseModel, IntField, StrField
from mydborm import PasswordField, EncryptedField

# pip install mydborm[security]

KEY = os.environ["ENCRYPTION_KEY"]   # generate with EncryptedField.generate_key()

class User(BaseModel):
    __tablename__ = "users"
    id         = IntField(primary_key=True)
    username   = StrField(max_length=50,  nullable=False)
    password   = PasswordField(nullable=False)              # bcrypt, auto-hashed
    api_secret = EncryptedField(secret_key=KEY)             # AES-128, auto-encrypted

User.create_table()

uid  = User.create(username="alice", password="hunter2", api_secret="my-api-secret-value")
user = User.get(id=uid)

# Password: verify only — never decryptable
ok = PasswordField.verify("hunter2", user["password"])   # True

# Encrypted field: decrypt when needed
plain = EncryptedField.decrypt(user["api_secret"], secret_key=KEY)   # my-api-secret-value
```

---

## CLI

```bash
pip install mydborm[cli]

# Test connection
mydborm ping --dialect mysql --port 3306 --user root --password root --database shop

# List tables with row counts
mydborm tables --dialect yugabyte --port 5433 --user yugabyte --password yugabyte --database analytics

# Inspect schema
mydborm inspect --dialect mysql --port 3306 --user root --password root --database shop

# Auto-generate migration file from model diff
mydborm generate \
  --dialect mysql --port 3306 --user root --password root --database shop \
  --model myapp.models.Product \
  --output migrations/ \
  --apply
```

---

## All Field Types

| Field | MySQL | YugabyteDB / PostgreSQL | Notes |
|---|---|---|---|
| `IntField` | `INT` | `INTEGER` | |
| `StrField(n)` | `VARCHAR(n)` | `VARCHAR(n)` | |
| `TextField` | `TEXT` | `TEXT` | |
| `BoolField` | `TINYINT(1)` | `BOOLEAN` | |
| `FloatField` | `FLOAT` | `FLOAT` | |
| `DecimalField(p,s)` | `DECIMAL(p,s)` | `DECIMAL(p,s)` | |
| `DateField` | `DATE` | `DATE` | |
| `DateTimeField` | `DATETIME` | `TIMESTAMP` | |
| `JSONField` | `JSON` | `JSONB` | indexable on YugabyteDB |
| `ForeignKeyField` | `INT` | `INTEGER` | |
| `TinyIntField` | `TINYINT` | `SMALLINT` | |
| `SmallIntField` | `SMALLINT` | `SMALLINT` | |
| `BigIntField` | `BIGINT` | `BIGINT` | |
| `UnsignedBigIntField` | `BIGINT UNSIGNED` | `NUMERIC(20)` | |
| `DoubleField` | `DOUBLE` | `DOUBLE PRECISION` | |
| `BitField(n)` | `BIT(n)` | `BIT(n)` | |
| `CharField(n)` | `CHAR(n)` | `CHAR(n)` | fixed-length |
| `TinyTextField` | `TINYTEXT` | `TEXT` | |
| `MediumTextField` | `MEDIUMTEXT` | `TEXT` | |
| `LongTextField` | `LONGTEXT` | `TEXT` | |
| `BinaryField(n)` | `BINARY(n)` | `BYTEA` | |
| `VarBinaryField(n)` | `VARBINARY(n)` | `BYTEA` | |
| `BlobField` | `BLOB` | `BYTEA` | |
| `TimeField` | `TIME` | `TIME` | |
| `TimestampField` | `TIMESTAMP` | `TIMESTAMPTZ` | |
| `EnumField(choices)` | `ENUM(...)` | `VARCHAR(n)` | |
| `SetField(choices)` | `SET(...)` | `TEXT[]` | |
| `PasswordField` | `VARCHAR(255)` | `VARCHAR(255)` | bcrypt, auto-hashed |
| `EncryptedField` | `TEXT` | `TEXT` | AES-128-CBC, auto-encrypted |

---

## Links

| Resource | URL |
|---|---|
| PyPI | https://pypi.org/project/mydborm/ |
| Documentation | https://codengers.github.io/mydborm/ |
| GitHub | https://github.com/codengers/mydborm |
| Issue tracker | https://github.com/codengers/mydborm/issues |
| Changelog | https://github.com/codengers/mydborm/blob/main/CHANGELOG.md |

---

## License & Contributing

**License:** MIT — free for commercial and personal use.

**Contributing:**
1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Add tests — every PR must include tests
4. Run: `pytest tests/ -q` — must be all green
5. Open a PR to the `develop` branch

Bug reports and feature requests are welcome via [GitHub Issues](https://github.com/codengers/mydborm/issues).

---

*Built by [Atikrant Upadhye](https://github.com/codengers) · MIT License*
