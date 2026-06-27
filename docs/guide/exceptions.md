# Exceptions

When something goes wrong inside mydborm — a bad connection, a row that
doesn't exist, a bulk insert that partially fails — it needs to tell your
code about it somehow. Python's way of doing that is to **raise an
exception**: instead of returning a normal value, the function stops and
hands control to the nearest matching `except` block up the call stack. If
nothing catches it, your program crashes and prints a traceback.

mydborm could just let the raw errors from the MySQL/PostgreSQL driver
bubble straight up to your code. The problem with that is drivers raise
generic, low-level errors — you'd be stuck writing code like
`except Exception as e: if "Duplicate entry" in str(e):` and hoping the
wording of the error message never changes. Instead, mydborm defines its
**own exception types** with names that describe what actually happened —
`RecordNotFoundError`, `ValidationError`, `BulkInsertError`, and so on — so
you can write `except RecordNotFoundError` and know exactly what you're
catching, without parsing strings or guessing.

This page covers every exception type mydborm defines, what triggers it,
and what data it carries so you can write a useful error message instead
of just "something went wrong."

> **A note on accuracy:** a few exception types described in earlier
> versions of this page — `NotConfiguredError`, `ConnectionError`,
> `ConnectionTimeoutError`, `QueryError`, `RecordNotFoundError`,
> `MultipleRecordsError`, `FieldRequiredError`, `FieldTypeError`,
> `FieldLengthError`, `DeadlockError`, `SavepointError`,
> `MigrationError` and its subclasses, and `UnsupportedDialectError` — are
> all defined as classes in `mydborm/exceptions.py` and exported from the
> package, but as of this version **nothing in mydborm's actual code raises
> them yet**. The operations that you'd expect to raise them (an unconfigured
> connection, a bad host, a missing row, a field with the wrong type, a
> migration failure, an unsupported dialect) currently raise plain Python
> built-ins instead (`RuntimeError`, `ValueError`, `TypeError`), or simply
> return `None`. This page documents both: what's wired up today, and what
> the reserved-but-unused types look like, so you know what to actually
> write `except` clauses for right now. Each section below is labeled
> **(active)** or **(reserved, not yet raised)** to make this obvious at a
> glance.

---

## Why mydborm has its own exception types

Imagine you're saving a new `Product` row and forgot to set its required
`name` field. Without a typed exception system, you'd get something like:

```
mysql.connector.errors.IntegrityError: 1048 (23000): Column 'name' cannot be null
```

That tells you *something* failed, but your code would have to parse that
string to figure out *what* — fragile, and it changes between MySQL,
PostgreSQL, and YugabyteDB. mydborm instead defines its own family of
exception classes that describe the failure in terms of your model, not the
database's internals.

## Catching errors: how exception hierarchies work

If you haven't worked with custom exception classes before, here's the
piece that matters: in Python, exception classes can **inherit** from each
other, the same way regular classes do. mydborm uses this on purpose. Every
exception it defines is a subclass of one root class, `MydbormError`:

```text
MydbormError                        (the root — catches everything below)
├── ConnectionError
│   └── ConnectionTimeoutError
├── NotConfiguredError
├── QueryError
├── RecordNotFoundError
├── MultipleRecordsError
├── ValidationError
│   ├── FieldRequiredError
│   ├── FieldTypeError
│   └── FieldLengthError
├── BulkOperationError
│   ├── BulkInsertError
│   ├── BulkUpdateError
│   └── BulkUpsertError
├── TransactionError
│   ├── SavepointError
│   └── DeadlockError
├── RetryExhaustedError
├── MigrationError
│   ├── MigrationAlreadyAppliedError
│   └── MigrationNotFoundError
├── SchemaError
└── UnsupportedDialectError
```

What this buys you: a `try`/`except` block matches an exception if it's
*either* that exact class *or* any subclass of it. So:

- `except FieldRequiredError:` catches only that one specific problem
  (a required field was missing).
- `except ValidationError:` catches `FieldRequiredError` *and*
  `FieldTypeError` *and* `FieldLengthError` *and* any other validation
  problem — because they all inherit from `ValidationError`.
- `except MydbormError:` catches absolutely anything mydborm raises,
  because every single exception class above eventually inherits from it.

This lets you handle errors at whatever level of detail makes sense for
each situation — react specifically to one problem, broadly to a category
of problems, or just catch "any mydborm error" as a fallback. You'll see
this pattern used throughout the examples below.

---

## Import exceptions

All exception types are importable directly from the `mydborm` package:

```python
from mydborm import (
    MydbormError,
    ConnectionError,
    ConnectionTimeoutError,
    NotConfiguredError,
    QueryError,
    RecordNotFoundError,
    MultipleRecordsError,
    ValidationError,
    FieldRequiredError,
    FieldTypeError,
    FieldLengthError,
    BulkOperationError,
    BulkInsertError,
    BulkUpdateError,
    BulkUpsertError,
    TransactionError,
    SavepointError,
    DeadlockError,
    RetryExhaustedError,
    MigrationError,
    MigrationAlreadyAppliedError,
    MigrationNotFoundError,
    SchemaError,
    UnsupportedDialectError,
)
```

---

## Connection-related errors

### Not configured — `RuntimeError` (active) / `NotConfiguredError` (reserved)

If you try to run any database operation before calling `db.configure()`
or `db.from_env()`, mydborm doesn't know which database to talk to. Today
that raises a plain `RuntimeError` with a helpful message — it is **not**
yet `NotConfiguredError`, even though that class exists and is exported:

```python
from mydborm import db, BaseModel, IntField

class User(BaseModel):
    __tablename__ = "users"
    id = IntField(primary_key=True)

# WRONG — configure not called yet
try:
    users = User.all()
except RuntimeError as e:
    print(f"Error: {e}")
    # Fix it:
    db.configure(
        dialect  = "mysql",
        host     = "127.0.0.1",
        port     = 3306,
        user     = "root",
        password = "yourpassword",
        database = "mydb",
    )
    users = User.all()  # now works
```

If a future release switches this to `NotConfiguredError`, catching the
broader `MydbormError` (or both `RuntimeError` and `NotConfiguredError`)
is the safest way to be ready for that without changing your code twice.

### Bad host / unreachable server (reserved — `ConnectionError`, `ConnectionTimeoutError`)

`ConnectionError` and `ConnectionTimeoutError` are defined to represent "the
database server couldn't be reached" and "the connection attempt took too
long," respectively, and they're exported from the package:

```python
from mydborm import ConnectionError, ConnectionTimeoutError
```

As of this version, though, mydborm doesn't catch and re-wrap the driver's
own connection failure — if `host` is wrong or the server is down, the
underlying MySQL/PostgreSQL driver's own exception propagates unchanged
(for example `mysql.connector.errors.InterfaceError`). If you want to
handle "can't connect" generically today, catch `Exception` around your
first `db.connect()` call, or check the driver-specific exception types for
whichever dialect you're using:

```python
from mydborm import db

db.configure(
    dialect  = "mysql",
    host     = "192.168.1.999",   # wrong host
    port     = 3306,
    user     = "root",
    password = "root",
    database = "mydb",
)

try:
    with db.connect() as conn:
        pass
except Exception as e:
    print(f"Cannot connect to database: {e}")

    # Retry with the correct host
    db.configure(dialect="mysql", host="127.0.0.1", port=3306,
                 user="root", password="root", database="mydb")
```

---

## Validation errors

A **validation error** happens when the data you're trying to save doesn't
match the rules you defined on the field — for example a required field
left empty, or a string field given a value that's too long.

### How validation actually fails today — plain `ValueError` / `TypeError` (active)

Each `Field` (in `mydborm/fields.py`) checks its own value when you call
`.create()`, `.update()`, or run a custom validator like `EmailValidator`.
Right now, every one of those checks raises a built-in `ValueError` or
`TypeError` with a descriptive message — not the typed `ValidationError`,
`FieldRequiredError`, `FieldTypeError`, or `FieldLengthError` classes you
might expect from their names (those classes exist and are exported, but
nothing currently raises them):

```python
from mydborm import BaseModel, IntField, StrField, FloatField, BoolField

class Product(BaseModel):
    __tablename__ = "products"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)   # required
    sku   = StrField(max_length=20,  nullable=False)   # required
    price = FloatField(nullable=False)                 # required

# Missing a required field
try:
    Product.create(name="Laptop", sku=None, price=999.99)
except ValueError as e:
    print(f"Validation failed: {e}")
    # Field 'sku' cannot be None.

# Wrong type
class Order(BaseModel):
    __tablename__ = "orders"
    id      = IntField(primary_key=True)
    shipped = BoolField(nullable=False)

try:
    Order.create(shipped="yes")   # BoolField wants True/False, not a string
except TypeError as e:
    print(f"Wrong type: {e}")

# String too long
class Tag(BaseModel):
    __tablename__ = "tags"
    id   = IntField(primary_key=True)
    name = StrField(max_length=20, nullable=False)

try:
    Tag.create(name="this-tag-name-is-way-too-long-for-the-field")
except ValueError as e:
    print(f"Too long: {e}")
```

Since both `ValueError` and `TypeError` are plain Python built-ins (not
mydborm-specific), the safest way to catch "any field validation problem"
today is:

```python
try:
    Product.create(name=None, sku="LAP-001", price=999.99)
except (ValueError, TypeError) as e:
    print(f"Could not save product: {e}")
```

### The reserved typed versions — `ValidationError`, `FieldRequiredError`, `FieldTypeError`, `FieldLengthError`

These classes describe what a future, more specific version of this
validation could look like, and you can already import them:

```python
from mydborm import ValidationError, FieldRequiredError, FieldTypeError, FieldLengthError
```

`ValidationError` carries `field`, `value`, and `reason` attributes, and
`FieldRequiredError`/`FieldTypeError`/`FieldLengthError` all inherit from
it — so `except ValidationError` would catch all three at once, the same
way `except MydbormError` catches everything. They're documented here so
the names and intent are clear, but don't write `except FieldRequiredError`
expecting it to fire today — catch `ValueError`/`TypeError` instead, as
shown above.

---

## Bulk operation exceptions (active)

Unlike the sections above, bulk operations' exceptions are fully wired up
— `BulkInsertError`, `BulkUpdateError`, and `BulkUpsertError` really are
raised by the code in `mydborm/bulk.py`. See
[Bulk Operations](bulk_ops.md) for the full picture of chunking, retries,
and `BulkResult`; this section focuses on the exceptions themselves.

### BulkInsertError

Raised by `chunked_bulk_create(..., raise_on_error=True)` when a chunk
fails partway through a large insert. It carries how many rows succeeded
before the failure, so you don't lose track of partial progress:

```python
from mydborm import BaseModel, IntField, StrField, BulkInsertError
from mydborm.bulk import chunked_bulk_create

class Product(BaseModel):
    __tablename__ = "products"
    id   = IntField(primary_key=True)
    sku  = StrField(max_length=20, nullable=False)
    name = StrField(max_length=100, nullable=False)

# 10,000 products in chunks of 100
records = [{"sku": f"SKU{i:05d}", "name": f"Product {i}"} for i in range(10000)]

try:
    result = chunked_bulk_create(
        Product,
        records,
        chunk_size     = 100,
        retries        = 2,
        raise_on_error = True,   # raise on first chunk failure
    )
except BulkInsertError as e:
    print(f"Bulk insert partially failed:")
    print(f"  Inserted: {e.inserted:,} rows")
    print(f"  Failed:   {e.failed:,} rows")
    print(f"  Errors:   {len(e.errors)} chunks")
    for err in e.errors:
        print(f"    Chunk {err['chunk']}: {err['records']} rows — {err['error']}")
```

**Without `raise_on_error` — you get a result object back instead of an
exception**, even if some rows failed:

```python
# Continues even if some chunks fail
result = chunked_bulk_create(Product, records, chunk_size=100)

print(result.summary())
# Operation : insert
# Total     : 10000
# Inserted  : 9850
# Failed    : 150
# Chunks    : 100
# Retries   : 3
# Success   : 98.5%
# Duration  : 2.4s

if result.has_errors:
    for err in result.errors:
        print(f"Chunk {err['chunk']} failed: {err['error']}")
```

### BulkUpdateError

```python
from mydborm import BulkUpdateError
from mydborm.bulk import chunked_bulk_update

updates = [{"id": i, "price": float(i)} for i in range(1000)]

try:
    result = chunked_bulk_update(
        Product, updates, key="id",
        chunk_size=100, raise_on_error=True
    )
except BulkUpdateError as e:
    # Note: BulkUpdateError reuses the "inserted" attribute name from its
    # parent class to mean "rows successfully updated" — a little
    # confusing, but that's what's on the object today.
    print(f"Updated: {e.inserted}, Failed: {e.failed}")
```

### BulkUpsertError

```python
from mydborm import BulkUpsertError

try:
    Product.bulk_upsert(
        records,
        conflict_key  = "sku",
        update_fields = ["name", "price"],
    )
except BulkUpsertError as e:
    print(f"Upsert failed: inserted={e.inserted}, failed={e.failed}")
    for err in e.errors:
        print(f"  Error: {err['error']}")
```

> Note: `Product.bulk_upsert(...)` (the non-chunked version on the model
> itself) doesn't currently catch its own database errors and re-raise
> them as `BulkUpsertError` — that wrapping only happens inside the
> *chunked* helpers in `mydborm/bulk.py`. A raw database error from
> `bulk_upsert()` called directly will propagate as-is. Keep that in mind
> if you're catching `BulkUpsertError` around a direct `bulk_upsert()`
> call rather than a chunked one.

---

## Transaction-related errors

### RetryExhaustedError (active)

This one is real and raised today. `db.transaction_with_retry(...)`
detects deadlocks by checking the database error message for known
deadlock signatures, retries with increasing delays between attempts, and
if it still hasn't succeeded after all retries are used up, raises
`RetryExhaustedError`:

```python
from mydborm import db, RetryExhaustedError

# Use transaction_with_retry — auto-retries on deadlock
try:
    with db.transaction_with_retry(retries=3, retry_delay=0.5):
        # Transfer money between accounts
        db.execute(
            "UPDATE accounts SET balance = balance - %s WHERE id = %s",
            [100, 1]
        )
        db.execute(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s",
            [100, 2]
        )
        # If another transaction causes a deadlock:
        # → auto-retries with 0.5s, 1s, 2s delays
        # → raises RetryExhaustedError after 3 attempts

except RetryExhaustedError as e:
    print(f"Transfer failed after {e.attempts} attempts")
    print(f"Last error: {e.last_error}")
    # Alert: manual intervention needed
```

```python
from mydborm import RetryExhaustedError

try:
    with db.transaction_with_retry(retries=5):
        db.execute("UPDATE stock SET qty = qty - 1 WHERE product_id = %s", [42])
except RetryExhaustedError as e:
    print(f"Gave up after {e.attempts} attempts")
    print(f"Last error type: {type(e.last_error).__name__}")
    print(f"Last error: {e.last_error}")
```

Two details worth knowing: if the error *isn't* a deadlock (it doesn't
match the known signatures), `transaction_with_retry` doesn't retry at all
— it raises that original error immediately. And when retries *are*
exhausted, `e.last_error` holds the original driver exception, not a
mydborm type — `RetryExhaustedError` is just the wrapper telling you "we
gave up."

### DeadlockError, SavepointError (reserved, not yet raised)

`DeadlockError` and `SavepointError` are defined as subclasses of
`TransactionError` and exported from the package, but nothing in the
current code raises either of them. A deadlock detected outside of
`transaction_with_retry` propagates as the raw driver exception, and
`db.savepoint(...)` does the same if the `SAVEPOINT`/`ROLLBACK TO`
statement fails:

```python
from mydborm import db

try:
    with db.transaction():
        db.execute("INSERT INTO orders (user_id, total) VALUES (%s, %s)", [1, 99.99])

        with db.savepoint("after_order") as sp:
            print(f"Savepoint created: {sp}")
            db.execute("INSERT INTO order_items ...")

except Exception as e:
    print(f"Savepoint or transaction failed: {e}")
```

---

## Schema errors

### SchemaError (active)

This one is real. `User.validate_schema(strict=True)` compares your
model's fields against the live database table and raises `SchemaError`
if they don't match — for example a column you added to the model but
haven't migrated into the database yet:

```python
from mydborm import BaseModel, IntField, StrField, SchemaError

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False)
    phone    = StrField(max_length=20,  nullable=True)   # not yet in DB
    # 'old_field' is in DB but not in model

# Non-strict — returns a dict describing the differences, never raises
result = User.validate_schema()
print(result)
# {
#   'table':         'users',
#   'valid':         False,
#   'missing_in_db': ['phone'],         # in model, not in DB
#   'extra_in_db':   ['old_field'],     # in DB, not in model
#   'matched':       ['id', 'username', 'email']
# }

if not result["valid"]:
    if result["missing_in_db"]:
        print("Run migrations to add:", result["missing_in_db"])
    if result["extra_in_db"]:
        print("Consider removing from model:", result["extra_in_db"])

# Strict — raises on mismatch instead of just reporting it
try:
    User.validate_schema(strict=True)
    print("Schema is valid!")
except SchemaError as e:
    print(f"Schema mismatch in table '{e.table}'")
    print(f"  Missing in DB : {e.missing_columns}")   # ['phone']
    print(f"  Extra in DB   : {e.extra_columns}")     # ['old_field']
    print(f"  Full message  : {str(e)}")
    # Schema mismatch for table 'users' | missing in DB: ['phone'] | extra in DB: ['old_field']
```

---

## Migration errors (reserved, not yet raised)

`MigrationError`, `MigrationAlreadyAppliedError`, and
`MigrationNotFoundError` describe failures you might expect from
`mydborm.migrations.migrate(...)` — a migration that fails to apply, one
that's already been applied, or one that can't be found. All three classes
exist and are exported, but as of this version `migrate()` doesn't raise
any of them — check the return value instead, or handle whatever
exception the underlying SQL execution raises:

```python
from mydborm.migrations import migrate

result = migrate(User, description="add phone column")
print(result)   # inspect the result dict to see what happened
```

If you want code that's ready for these exceptions becoming active in a
future release, it doesn't hurt to wrap calls in a `try`/`except
Exception` today and switch to the specific types later.

---

## UnsupportedDialectError (reserved — actual error is `ValueError`)

If you pass a `dialect` that mydborm doesn't recognize, `db.configure()`
raises a plain `ValueError` today, not `UnsupportedDialectError` (which
exists and is exported, but isn't raised anywhere yet):

```python
from mydborm import db

try:
    db.configure(dialect="oracle", host="localhost", user="sa", password="pw", database="db")
except ValueError as e:
    print(f"Unsupported dialect: {e}")
    # Choose from: ('mysql', 'yugabyte', 'postgres', 'postgresql')
```

---

## Exception attributes reference

These are the attributes available on each exception class, regardless of
whether it's currently raised by mydborm's own code (see the **Active?**
column) — useful if you're catching one, or if you're calling these
classes yourself (e.g. raising one from your own code that wraps mydborm).

| Exception | Attributes | Active? |
|---|---|---|
| `ConnectionError` | `dialect`, `host`, `port`, `message` | No — driver error propagates |
| `ConnectionTimeoutError` | `timeout`, `dialect`, `host`, `port` | No |
| `NotConfiguredError` | `message` | No — `RuntimeError` raised instead |
| `ValidationError` | `field`, `value`, `reason`, `message` | No — `ValueError`/`TypeError` raised instead |
| `FieldRequiredError` | `field` | No |
| `FieldTypeError` | `field`, `value` | No |
| `FieldLengthError` | `field`, `value` | No |
| `QueryError` | `sql`, `params`, `message` | No |
| `RecordNotFoundError` | `model`, `filters` | No — `.get()` returns `None` instead |
| `MultipleRecordsError` | `model`, `count` | No — no `get_one()` exists |
| `BulkOperationError` | `inserted`, `failed`, `errors` | Yes (base class) |
| `BulkInsertError` | `inserted`, `failed`, `errors` | **Yes** |
| `BulkUpdateError` | `inserted`, `failed`, `errors` | **Yes** |
| `BulkUpsertError` | `inserted`, `failed`, `errors` | **Yes** |
| `SavepointError` | `savepoint`, `message` | No |
| `DeadlockError` | `message` | No |
| `RetryExhaustedError` | `attempts`, `last_error` | **Yes** |
| `MigrationError` | `version`, `sql`, `message` | No |
| `SchemaError` | `table`, `missing_columns`, `extra_columns` | **Yes** |
| `UnsupportedDialectError` | `dialect`, `supported` | No — `ValueError` raised instead |

---

## Best practices

### Catch the most specific exception that's actually raised

Given everything above, the practical version of "catch specific
exceptions" for mydborm today mixes a few real mydborm types with the
plain Python built-ins that currently do the job of the others:

```python
# Good — catches exactly what mydborm actually raises today
try:
    uid = User.create(username="alice", email="bad-email")
except (ValueError, TypeError) as e:
    return {"error": f"Invalid data: {e}"}
except RuntimeError as e:
    return {"error": "Database not configured"}
except MydbormError as e:
    return {"error": f"Database error: {e}"}

# Bad — swallows everything, including bugs in your own code
try:
    uid = User.create(username="alice", email="bad-email")
except Exception:
    return {"error": "Something went wrong"}
```

`except MydbormError` is still worth keeping as your last, broadest
mydborm-specific net — it will automatically start catching more cases for
free if a future release upgrades `RuntimeError`/`ValueError` call sites to
the typed exceptions described above, with no changes needed on your end.

### Log errors with context

```python
import logging
from mydborm import MydbormError, BulkInsertError

logger = logging.getLogger(__name__)

def sync_products(records):
    try:
        from mydborm.bulk import chunked_bulk_create
        result = chunked_bulk_create(Product, records, chunk_size=500)
        logger.info(f"Synced {result.inserted} products in {result.duration}s")
        return result
    except BulkInsertError as e:
        logger.error(
            f"Bulk insert failed: inserted={e.inserted}, failed={e.failed}",
            extra={"errors": e.errors}
        )
        raise
    except MydbormError as e:
        logger.error(f"DB error during product sync: {e}", exc_info=True)
        raise
```

### Retry pattern for deadlocks without transaction_with_retry

If you need retry behavior outside of `db.transaction_with_retry(...)`,
you can write your own loop. Since deadlocks aren't currently raised as a
typed `DeadlockError`, match on the driver's own exception type or message
instead:

```python
import time

def with_retry(fn, retries=3, delay=0.5):
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            if "deadlock" in str(e).lower() and attempt < retries:
                time.sleep(delay * (2 ** attempt))
            else:
                raise

result = with_retry(lambda: transfer_funds(from_id=1, to_id=2, amount=100))
```
