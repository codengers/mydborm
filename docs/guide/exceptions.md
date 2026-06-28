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

> **A note on accuracy:** `NotConfiguredError`, `UnsupportedDialectError`,
> `SavepointError`, `FieldRequiredError`, `FieldTypeError`, and
> `FieldLengthError` are now actually raised at their real call sites
> (they were defined but unused in earlier versions of mydborm). Each of
> these also still inherits from whatever plain Python built-in
> (`RuntimeError`, `ValueError`, `TypeError`) it raised before being wired
> up, so existing `except RuntimeError`/`except ValueError`/`except
> TypeError` code keeps working unchanged — you only need to catch the
> specific type if you want more precise handling than the built-in gives
> you.
>
> A few others — `ConnectionError`, `ConnectionTimeoutError`, `QueryError`,
> `RecordNotFoundError`, `MultipleRecordsError`, `DeadlockError`,
> `MigrationError` and its subclasses — are still defined and exported but
> **not yet raised anywhere**. Most of these would require an actual new
> feature first (e.g. `RecordNotFoundError` needs a `strict=` option on
> `get()` that doesn't exist yet; `MultipleRecordsError` needs a `get_one()`
> method that doesn't exist yet), not just a renamed exception, so they're
> left as future work rather than wired up as a drop-in fix. Each section
> below is labeled **(active)** or **(reserved, not yet raised)** to make
> this obvious at a glance.

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

### Not configured — `NotConfiguredError` (active)

If you try to run any database operation before calling `db.configure()`
or `db.from_env()`, mydborm doesn't know which database to talk to, and
raises `NotConfiguredError`:

```python
from mydborm import db, BaseModel, IntField
from mydborm import NotConfiguredError

class User(BaseModel):
    __tablename__ = "users"
    id = IntField(primary_key=True)

# WRONG — configure not called yet
try:
    users = User.all()
except NotConfiguredError as e:
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

`NotConfiguredError` also inherits from `RuntimeError` (what it raised
before this was wired up), so existing `except RuntimeError:` code keeps
working — you only need to catch `NotConfiguredError` specifically if you
want to distinguish "not configured" from other runtime errors.

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

### How validation fails — `FieldRequiredError`, `FieldTypeError`, `FieldLengthError` (active)

Each `Field` (in `mydborm/fields.py`) checks its own value when you call
`.create()` or `.update()`. A missing required field raises
`FieldRequiredError`, a value of the wrong type raises `FieldTypeError`,
and a string that's too long raises `FieldLengthError` — all three inherit
from `ValidationError`, which carries `field`, `value`, and `reason`
attributes:

```python
from mydborm import BaseModel, IntField, StrField, FloatField, BoolField
from mydborm import FieldRequiredError, FieldTypeError, FieldLengthError

class Product(BaseModel):
    __tablename__ = "products"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)   # required
    sku   = StrField(max_length=20,  nullable=False)   # required
    price = FloatField(nullable=False)                 # required

# Missing a required field
try:
    Product.create(name="Laptop", sku=None, price=999.99)
except FieldRequiredError as e:
    print(f"Validation failed: {e}")
    # Field 'sku' cannot be None. (field='sku')

# Wrong type
class Order(BaseModel):
    __tablename__ = "orders"
    id      = IntField(primary_key=True)
    shipped = BoolField(nullable=False)

try:
    Order.create(shipped="yes")   # BoolField wants True/False, not a string
except FieldTypeError as e:
    print(f"Wrong type: {e}")

# String too long
class Tag(BaseModel):
    __tablename__ = "tags"
    id   = IntField(primary_key=True)
    name = StrField(max_length=20, nullable=False)

try:
    Tag.create(name="this-tag-name-is-way-too-long-for-the-field")
except FieldLengthError as e:
    print(f"Too long: {e}")
```

`FieldRequiredError` also inherits from `ValueError`, `FieldTypeError`
also inherits from `TypeError`, and `FieldLengthError` also inherits from
`ValueError` — these are exactly the built-ins each one raised before
being wired up, so existing code written as:

```python
try:
    Product.create(name=None, sku="LAP-001", price=999.99)
except (ValueError, TypeError) as e:
    print(f"Could not save product: {e}")
```

keeps working unchanged. Catch the specific `FieldRequiredError` /
`FieldTypeError` / `FieldLengthError` (or the shared parent
`ValidationError`, which catches all three at once) when you want to
handle each case differently instead of lumping them all into "some kind
of bad value."

A handful of other validation-shaped checks — a custom `RangeValidator`/
`ChoiceValidator` failing, an `EnumField`/`SetField` value not in its
allowed choices, a numeric field outside its column's range (e.g.
`TinyIntField` outside -128..127) — still raise a plain `ValueError`, since
none of `FieldRequiredError`/`FieldTypeError`/`FieldLengthError` accurately
describes "value out of range" or "not one of the allowed choices."

---

## Bulk operation exceptions (active)

Unlike the sections above, bulk operations' exceptions are fully wired up
— `BulkInsertError`, `BulkUpdateError`, `BulkUpsertError`, and
`BulkDeleteError` really are raised by the code in `mydborm/bulk.py`. See
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

### BulkDeleteError

```python
from mydborm.bulk import chunked_bulk_delete
from mydborm import BulkDeleteError

ids_to_delete = [101, 102, 103, 999999]  # 999999 doesn't exist

try:
    chunked_bulk_delete(Product, ids_to_delete, chunk_size=2, raise_on_error=True)
except BulkDeleteError as e:
    print(f"Bulk delete partially failed: failed={e.failed}")
```

---

## Transaction-related errors

### RetryExhaustedError — real bug, only partially fixed

`db.transaction_with_retry(...)` is meant to detect deadlocks by checking
the database error message for known deadlock signatures, retry with
increasing delays between attempts, and raise `RetryExhaustedError` if it
still hasn't succeeded after all retries are used up. Until recently,
`RetryExhaustedError` wasn't even imported into `db.py` — reaching that
line would have crashed with `NameError: name 'RetryExhaustedError' is not
defined` instead of raising the intended exception. That import is fixed.

There's a deeper problem underneath, though: `transaction_with_retry` is
implemented as a single `@contextmanager` generator that tries to retry by
looping back to a second `yield` inside the same generator. Python's
`contextlib` only allows a generator-based context manager to yield once —
when the deadlock-shaped exception comes from **your own code inside the
`with` block** (the realistic case — a deadlock on one of your own
`UPDATE`/`INSERT` statements), retrying means throwing that exception back
into the generator and having it try to yield again, which `contextlib`
rejects with its own `RuntimeError: generator didn't stop after throw()`.
You will see *that* error, not a clean retry and not `RetryExhaustedError`:

```python
from mydborm import db

try:
    with db.transaction_with_retry(retries=3, retry_delay=0.5):
        db.execute(
            "UPDATE accounts SET balance = balance - %s WHERE id = %s",
            [100, 1]
        )
        db.execute(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s",
            [100, 2]
        )
except Exception as e:
    # On a real deadlock here, expect RuntimeError("generator didn't
    # stop after throw()") from contextlib, not RetryExhaustedError —
    # the retry loop can't yield a second time from the same generator.
    print(f"Transfer failed: {type(e).__name__}: {e}")
```

`RetryExhaustedError` (and the retry itself) does work correctly for a
failure that happens while *establishing* the transaction — before
anything in the `with` block has run — since that doesn't require the
generator to yield twice. That's a narrower case than "one of my
statements deadlocked," which is what most people reaching for this
method actually want to handle. Fixing the common case requires
rewriting `transaction_with_retry` so it can genuinely re-run the whole
`with` block on each attempt (for example, as a small wrapper function
you call with your transaction body as an argument, rather than a
`with`-statement context manager) — that's a bigger change than a
one-line fix, and hasn't been done yet.

If you need working deadlock retry today, wrap your own retry loop
around `db.transaction()` instead:

```python
from mydborm import db
import time

def transfer_with_retry(retries=3, retry_delay=0.5):
    for attempt in range(retries + 1):
        try:
            with db.transaction():
                db.execute(
                    "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                    [100, 1]
                )
                db.execute(
                    "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                    [100, 2]
                )
            return
        except Exception as e:
            if "deadlock" not in str(e).lower() or attempt == retries:
                raise
            time.sleep(retry_delay * (2 ** attempt))
```

Two details worth knowing about `transaction_with_retry` even given the
limitation above: if the error *isn't* a deadlock (it doesn't match the
known signatures), it doesn't retry at all — it raises that original
error immediately, same as a plain `db.transaction()` would. And on the
one path where `RetryExhaustedError` genuinely is reachable (the
transaction-establishment case described above), `e.last_error` holds the
original driver exception, not a mydborm type — `RetryExhaustedError` is
just the wrapper telling you "we gave up."

### SavepointError — calling `db.savepoint()` outside a transaction (active)

`db.savepoint(...)` only makes sense inside an open `db.transaction()` —
calling it on its own raises `SavepointError`:

```python
from mydborm import db, SavepointError

try:
    with db.savepoint("oops"):   # no surrounding db.transaction()
        pass
except SavepointError as e:
    print(f"Can't do that: {e}")
```

`SavepointError` also inherits from `RuntimeError` (what it raised before
being wired up), so `except RuntimeError:` still works too.

That's the one case mydborm checks for itself, though. If the
`SAVEPOINT`/`ROLLBACK TO` statement itself fails at the database level
(say, the savepoint name collides, or the connection drops mid-savepoint),
that raw driver exception still propagates unchanged — it is **not**
wrapped in `SavepointError`:

```python
try:
    with db.transaction():
        db.execute("INSERT INTO orders (user_id, total) VALUES (%s, %s)", [1, 99.99])

        with db.savepoint("after_order") as sp:
            print(f"Savepoint created: {sp}")
            db.execute("INSERT INTO order_items ...")

except Exception as e:
    print(f"Savepoint or transaction failed: {e}")
```

### DeadlockError (reserved, not yet raised)

`DeadlockError` is defined as a subclass of `TransactionError` and
exported from the package, but nothing in the current code raises it. A
deadlock detected outside of `transaction_with_retry()` (see above)
propagates as the raw driver exception instead.

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

## UnsupportedDialectError (active)

Calling `db.configure()` without a `dialect` at all raises
`UnsupportedDialectError` immediately:

```python
from mydborm import db, UnsupportedDialectError

try:
    db.configure(host="localhost", user="sa", password="pw", database="db")
except UnsupportedDialectError as e:
    print(f"Missing dialect: {e}")
```

`configure()` only checks that a `dialect` was *provided*, though — it
doesn't check whether the value is one it actually understands. That
check happens later, the first time you actually connect, so an
unrecognized dialect value raises `UnsupportedDialectError` on
`db.connect()` (or any operation that connects under the hood), not on
`configure()` itself:

```python
db.configure(dialect="oracle", host="localhost", user="sa", password="pw", database="db")

try:
    with db.connect() as conn:   # the dialect value is checked here
        pass
except UnsupportedDialectError as e:
    print(f"Unsupported dialect: {e}")
    print(f"You passed: {e.dialect!r}")
```

`get_dialect()` (used internally for SQL generation, e.g. by the
[database migration](db_migration.md) tools) raises the same exception
for an unrecognized name. `UnsupportedDialectError` also inherits from
`ValueError` (what it raised before being wired up), so
`except ValueError:` still works everywhere above.

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
| `NotConfiguredError` | `message` | **Yes** (also a `RuntimeError`) |
| `ValidationError` | `field`, `value`, `reason`, `message` | Yes (base class) |
| `FieldRequiredError` | `field` | **Yes** (also a `ValueError`) |
| `FieldTypeError` | `field`, `value` | **Yes** (also a `TypeError`) |
| `FieldLengthError` | `field`, `value` | **Yes** (also a `ValueError`) |
| `QueryError` | `sql`, `params`, `message` | No |
| `RecordNotFoundError` | `model`, `filters` | No — `.get()` returns `None` instead |
| `MultipleRecordsError` | `model`, `count` | No — no `get_one()` exists |
| `BulkOperationError` | `inserted`, `failed`, `errors` | Yes (base class) |
| `BulkInsertError` | `inserted`, `failed`, `errors` | **Yes** |
| `BulkUpdateError` | `inserted`, `failed`, `errors` | **Yes** |
| `BulkUpsertError` | `inserted`, `failed`, `errors` | **Yes** |
| `BulkDeleteError` | `inserted`, `failed`, `errors` | **Yes** |
| `SavepointError` | `savepoint`, `message` | **Yes**, for the "outside a transaction" case (also a `RuntimeError`) |
| `DeadlockError` | `message` | No |
| `RetryExhaustedError` | `attempts`, `last_error` | Partially — only for failures while starting the transaction, not for a deadlock on your own statements (see above) |
| `MigrationError` | `version`, `sql`, `message` | No |
| `SchemaError` | `table`, `missing_columns`, `extra_columns` | **Yes** |
| `UnsupportedDialectError` | `dialect`, `supported` | **Yes** (also a `ValueError`) |

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
