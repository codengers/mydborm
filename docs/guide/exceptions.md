# Exceptions

mydborm provides 24 typed exceptions. Catch exactly what you need — no more parsing error strings or catching generic `Exception`.

---

## Full exception hierarchy
---

## Import exceptions

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

## Connection exceptions

### NotConfiguredError

Raised when you call any DB operation before `db.configure()`.

```python
from mydborm import db, BaseModel, IntField, NotConfiguredError

class User(BaseModel):
    __tablename__ = "users"
    id = IntField(primary_key=True)

# WRONG — configure not called
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

### ConnectionError

Raised when the database server cannot be reached.

```python
from mydborm import db, ConnectionError

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
except ConnectionError as e:
    print(f"Cannot connect to database")
    print(f"  Dialect: {e.dialect}")   # mysql
    print(f"  Host:    {e.host}")      # 192.168.1.999
    print(f"  Port:    {e.port}")      # 3306
    print(f"  Error:   {e.message}")

    # Retry with correct host
    db.configure(dialect="mysql", host="127.0.0.1", port=3306,
                 user="root", password="root", database="mydb")
```

### ConnectionTimeoutError

Raised when the connection attempt times out.

```python
from mydborm import ConnectionTimeoutError

try:
    with db.connect() as conn:
        pass
except ConnectionTimeoutError as e:
    print(f"Connection timed out after {e.timeout}s")
    print("Check if the database server is running")
    print(f"Host: {e.host}:{e.port}")
```

---

## Validation exceptions

### FieldRequiredError

Raised when a `nullable=False` field receives `None`.

```python
from mydborm import BaseModel, IntField, StrField, FieldRequiredError

class Product(BaseModel):
    __tablename__ = "products"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)   # required
    sku   = StrField(max_length=20,  nullable=False)   # required
    price = FloatField(nullable=False)                 # required

try:
    Product.create(name="Laptop", sku=None, price=999.99)
except FieldRequiredError as e:
    print(f"Missing required field: '{e.field}'")
    # Missing required field: 'sku'

try:
    Product.create(name=None, sku="LAP-001", price=999.99)
except FieldRequiredError as e:
    print(f"Field '{e.field}' is required — got None")
    # Field 'name' is required — got None
```

### FieldTypeError

Raised when a field receives the wrong Python type.

```python
from mydborm import BaseModel, IntField, BoolField, FieldTypeError

class Order(BaseModel):
    __tablename__ = "orders"
    id       = IntField(primary_key=True)
    shipped  = BoolField(nullable=False)

# BoolField requires True or False — not strings or integers
try:
    Order.create(shipped="yes")
except FieldTypeError as e:
    print(f"Wrong type for '{e.field}'")
    print(f"  Got:      {type(e.value).__name__} = {e.value!r}")
    print(f"  Expected: bool")
    # Wrong type for 'shipped'
    #   Got:      str = 'yes'
    #   Expected: bool

try:
    Order.create(shipped=1)   # use True not 1
except FieldTypeError as e:
    print(f"Use True/False not 1/0 for BoolField")
```

### FieldLengthError

Raised when a string exceeds `max_length`.

```python
from mydborm import BaseModel, IntField, StrField, FieldLengthError

class Tag(BaseModel):
    __tablename__ = "tags"
    id   = IntField(primary_key=True)
    name = StrField(max_length=20, nullable=False)

try:
    Tag.create(name="this-tag-name-is-way-too-long-for-the-field")
except FieldLengthError as e:
    print(f"Field '{e.field}' too long:")
    print(f"  Max:    20 characters")
    print(f"  Got:    {len(str(e.value))} characters")
    print(f"  Value:  {e.value!r}")
```

### ValidationError (base)

Catch all validation errors at once:

```python
from mydborm import ValidationError

try:
    Product.create(
        name  = None,        # FieldRequiredError
        sku   = "A" * 100,  # FieldLengthError
        price = -5.0,       # custom RangeValidator
    )
except ValidationError as e:
    print(f"Validation failed on field '{e.field}': {e.message}")
```

---

## Bulk operation exceptions

### BulkInsertError

Raised by `chunked_bulk_create(..., raise_on_error=True)` when a chunk fails. Contains partial success info.

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

**Without raise_on_error — get a result object:**

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

---

## Transaction exceptions

### DeadlockError

Raised when the database detects a deadlock between concurrent transactions.

```python
from mydborm import db, DeadlockError, RetryExhaustedError

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

except DeadlockError as e:
    # Only raised if NOT using transaction_with_retry
    print("Deadlock detected — retry the transaction")
```

### RetryExhaustedError

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

### SavepointError

```python
from mydborm import db, SavepointError

try:
    with db.transaction():
        db.execute("INSERT INTO orders (user_id, total) VALUES (%s, %s)", [1, 99.99])

        with db.savepoint("after_order") as sp:
            print(f"Savepoint created: {sp}")
            db.execute("INSERT INTO order_items ...")

except SavepointError as e:
    print(f"Savepoint '{e.savepoint}' failed: {e.message}")
```

---

## Schema exceptions

### SchemaError

Raised by `validate_schema(strict=True)` when model definition doesn't match the live database.

```python
from mydborm import BaseModel, IntField, StrField, SchemaError

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False)
    phone    = StrField(max_length=20,  nullable=True)   # not yet in DB
    # 'old_field' is in DB but not in model

# Non-strict — returns dict, never raises
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

# Strict — raises on mismatch
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

## Migration exceptions

### MigrationError

```python
from mydborm import MigrationError
from mydborm.migrations import migrate

try:
    result = migrate(User, description="add phone column")
except MigrationError as e:
    print(f"Migration failed!")
    print(f"  Version: {e.version}")
    print(f"  SQL:     {e.sql}")
    print(f"  Error:   {e.message}")
```

### MigrationAlreadyAppliedError

```python
from mydborm import MigrationAlreadyAppliedError
from mydborm.migrations import migrate

try:
    migrate(User, description="create users")
    migrate(User, description="create users")  # second call
except MigrationAlreadyAppliedError as e:
    print(f"Migration {e.version} was already applied — skipping")
    print("This is usually safe to ignore")
```

---

## UnsupportedDialectError

```python
from mydborm import db, UnsupportedDialectError

try:
    db.configure(dialect="oracle", host="localhost", user="sa", password="pw", database="db")
except UnsupportedDialectError as e:
    print(f"Dialect '{e.dialect}' is not supported")
    print(f"Supported dialects: {e.supported}")
    # Supported dialects: ['mysql', 'yugabyte', 'postgres']
```

---

## Exception attributes reference

| Exception | Attributes |
|---|---|
| `ConnectionError` | `dialect`, `host`, `port`, `message` |
| `ConnectionTimeoutError` | `timeout`, `dialect`, `host`, `port` |
| `ValidationError` | `field`, `value`, `reason`, `message` |
| `FieldRequiredError` | `field` |
| `FieldTypeError` | `field`, `value` |
| `FieldLengthError` | `field`, `value` |
| `QueryError` | `sql`, `params`, `message` |
| `RecordNotFoundError` | `model`, `filters` |
| `MultipleRecordsError` | `model`, `count` |
| `BulkOperationError` | `inserted`, `failed`, `errors` |
| `SavepointError` | `savepoint`, `message` |
| `DeadlockError` | `message` |
| `RetryExhaustedError` | `attempts`, `last_error` |
| `MigrationError` | `version`, `sql`, `message` |
| `SchemaError` | `table`, `missing_columns`, `extra_columns` |
| `UnsupportedDialectError` | `dialect`, `supported` |

---

## Best practices

### Catch the most specific exception

```python
# Good — catches exactly what you handle
try:
    uid = User.create(username="alice", email="bad-email")
except FieldRequiredError as e:
    return {"error": f"Field '{e.field}' is required"}
except ValidationError as e:
    return {"error": f"Invalid value for '{e.field}': {e.message}"}
except ConnectionError as e:
    return {"error": "Database unavailable — please try again"}
except MydbormError as e:
    return {"error": f"Database error: {e}"}

# Bad — swallows everything
try:
    uid = User.create(username="alice", email="bad-email")
except Exception:
    return {"error": "Something went wrong"}
```

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

### Retry pattern without transaction_with_retry

```python
import time
from mydborm import DeadlockError

def with_retry(fn, retries=3, delay=0.5):
    for attempt in range(retries + 1):
        try:
            return fn()
        except DeadlockError:
            if attempt < retries:
                time.sleep(delay * (2 ** attempt))
            else:
                raise

result = with_retry(lambda: transfer_funds(from_id=1, to_id=2, amount=100))
```
