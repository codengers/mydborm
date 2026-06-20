# Bulk Operations

mydborm provides high-performance bulk operations for inserting, updating,
deleting, and upserting large datasets — with chunking, retry logic,
progress callbacks, and detailed result objects.

---

## Basic bulk operations

### bulk_create()

Insert many records in a single SQL statement:

```python
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField

class Product(BaseModel):
    __tablename__ = "products"
    id       = IntField(primary_key=True)
    name     = StrField(max_length=100, nullable=False)
    sku      = StrField(max_length=20,  nullable=False)
    price    = FloatField(nullable=False)
    active   = BoolField(default=True)

# Insert 1000 products in one SQL call — much faster than looping create()
records = [
    {"name": f"Product {i}", "sku": f"P{i:05d}", "price": float(i), "active": True}
    for i in range(1000)
]
count = Product.bulk_create(records)
print(f"Inserted {count} products")   # 1000
```

### bulk_update()

Update many records at once:

```python
# Get current products
products = Product.filter(active=True)

# Apply 10% discount to all active products
updates = [
    {"id": p["id"], "price": round(p["price"] * 0.9, 2)}
    for p in products
]
count = Product.bulk_update(updates, key="id")
print(f"Updated {count} products")

# Update by custom key field
Product.bulk_update(
    [{"sku": "P00001", "price": 9.99},
     {"sku": "P00002", "price": 19.99}],
    key="sku"
)
```

### bulk_delete()

Delete many records by ID:

```python
# Delete all inactive products
inactive = Product.filter(active=False)
ids      = [p["id"] for p in inactive]
deleted  = Product.bulk_delete(ids)
print(f"Deleted {deleted} products")

# Delete by custom key
Product.bulk_delete(["P00001", "P00002"], key="sku")
```

### bulk_upsert()

Insert new records or update existing ones based on a unique field:

```python
# Sync product catalog — inserts new, updates existing
catalog = [
    {"sku": "LAPTOP-001", "name": "MacBook Pro",  "price": 1999.99, "active": True},
    {"sku": "PHONE-001",  "name": "iPhone 15",    "price": 999.99,  "active": True},
    {"sku": "TABLET-001", "name": "iPad Pro",      "price": 799.99,  "active": True},
]

count = Product.bulk_upsert(
    catalog,
    conflict_key  = "sku",                    # detect conflicts on this field
    update_fields = ["name", "price"],        # update these on conflict
)
print(f"Processed {count} products")

# With create_index=True (default) — auto-creates UNIQUE index on conflict_key
# MySQL: ON DUPLICATE KEY UPDATE
# YugabyteDB: ON CONFLICT (sku) DO UPDATE SET
```

---

## Chunked bulk operations

For very large datasets — splits into chunks with retry logic:

```python
from mydborm.bulk import chunked_bulk_create, chunked_bulk_update, chunked_bulk_delete
```

### chunked_bulk_create()

```python
from mydborm.bulk import chunked_bulk_create

records = [
    {"name": f"Item {i}", "sku": f"I{i:06d}", "price": float(i % 100), "active": True}
    for i in range(100_000)
]

result = chunked_bulk_create(
    Product,
    records,
    chunk_size  = 500,    # rows per INSERT statement
    retries     = 3,      # retry each chunk up to 3 times on failure
    retry_delay = 0.5,    # 0.5s → 1s → 2s exponential backoff
)

print(result.summary())
# Operation : insert
# Total     : 100000
# Inserted  : 100000
# Failed    : 0
# Chunks    : 200
# Retries   : 0
# Success   : 100.0%
# Duration  : 24.3s
```

### Progress callback

```python
def show_progress(done, total):
    pct = done / total * 100
    bar = "=" * int(pct / 2) + " " * (50 - int(pct / 2))
    print(f"\r[{bar}] {done:,}/{total:,} ({pct:.1f}%)", end="", flush=True)

result = chunked_bulk_create(
    Product,
    records,
    chunk_size  = 500,
    on_progress = show_progress,
)
print()   # newline after progress bar
print(f"Done in {result.duration}s!")
```

### chunked_bulk_update()

```python
from mydborm.bulk import chunked_bulk_update

# Update 50,000 product prices
products = Product.all()
updates  = [{"id": p["id"], "price": p["price"] * 1.1} for p in products]

result = chunked_bulk_update(
    Product,
    updates,
    key        = "id",
    chunk_size = 500,
    retries    = 2,
)
print(f"Updated {result.updated} products in {result.duration}s")
```

### chunked_bulk_delete()

```python
from mydborm.bulk import chunked_bulk_delete

# Delete 100,000 old records
old_ids = [p["id"] for p in Product.filter(active=False)]

result = chunked_bulk_delete(
    Product,
    old_ids,
    chunk_size = 1000,
    retries    = 2,
)
print(f"Deleted {result.deleted} records in {result.duration}s")
```

---

## BulkResult

All chunked operations return a `BulkResult` object:

```python
from mydborm.bulk import BulkResult

result = chunked_bulk_create(Product, records, chunk_size=500)

# Counts
print(result.total)        # total records attempted
print(result.inserted)     # successfully inserted
print(result.updated)      # successfully updated
print(result.deleted)      # successfully deleted
print(result.failed)       # failed records

# Stats
print(result.chunks)       # number of chunks processed
print(result.retries)      # total retry attempts made
print(result.duration)     # total time in seconds
print(result.success_rate) # e.g. 99.5 (percentage)
print(result.has_errors)   # True if any chunk failed

# Error details
for err in result.errors:
    print(f"Chunk {err['chunk']}: {err['records']} records — {err['error']}")

# Full summary string
print(result.summary())
```

---

## Retry logic

Each chunk is retried independently with **exponential backoff**:

```python
result = chunked_bulk_create(
    Product,
    records,
    chunk_size  = 500,
    retries     = 3,      # up to 3 retries per chunk
    retry_delay = 0.5,    # delays: 0.5s, 1.0s, 2.0s
)
# If chunk 5 fails:
# → wait 0.5s, retry
# → wait 1.0s, retry
# → wait 2.0s, retry
# → record as failed, continue with chunk 6
```

### raise_on_error

Stop immediately when any chunk fails:

```python
from mydborm import BulkInsertError
from mydborm.bulk import chunked_bulk_create

try:
    result = chunked_bulk_create(
        Product,
        records,
        chunk_size     = 500,
        raise_on_error = True,   # stop on first failure
    )
except BulkInsertError as e:
    print(f"Stopped at chunk failure:")
    print(f"  Inserted: {e.inserted}")
    print(f"  Failed  : {e.failed}")
    for err in e.errors:
        print(f"  Error: {err['error']}")
```

---

## Performance tips

### Choose the right chunk_size

```python
# Small records (a few fields) → larger chunks
result = chunked_bulk_create(User, records, chunk_size=1000)

# Large records (many fields, TEXT columns) → smaller chunks
result = chunked_bulk_create(Article, records, chunk_size=100)

# Very large records (BLOBs, encrypted fields) → tiny chunks
result = chunked_bulk_create(Document, records, chunk_size=10)
```

### Benchmark guide

| Records | chunk_size | Expected time |
|---|---|---|
| 1,000 | 500 | ~0.3s |
| 10,000 | 500 | ~2s |
| 100,000 | 500 | ~20s |
| 1,000,000 | 1000 | ~3-4 min |

### Compare bulk vs loop

```python
import time

# Slow — N separate INSERT statements
t0 = time.time()
for r in records[:1000]:
    Product.create(**r)
print(f"Loop: {time.time()-t0:.2f}s")   # ~10s

# Fast — 1 INSERT statement
t0 = time.time()
Product.bulk_create(records[:1000])
print(f"Bulk: {time.time()-t0:.2f}s")   # ~0.3s
```
