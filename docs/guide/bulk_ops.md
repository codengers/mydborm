# Bulk Operations

If you've ever needed to insert, update, or delete thousands of rows at
once — importing a CSV of products, recalculating prices for every item in
a catalog, purging old records — you've probably noticed that calling
`.create()` once per row gets slow fast. This page covers mydborm's
**bulk operations**: ways to insert, update, delete, and upsert (insert-or-update)
many rows at once, built specifically to handle large datasets without
choking your database connection or losing track of partial failures.

## Why not just loop over `.create()`?

Every time you call `Product.create(...)`, mydborm sends one SQL
statement to the database and waits for a response before your code moves
on — that round trip (your app to the database server and back) has a
fixed cost, even for a tiny row. If you insert 10,000 rows in a Python
`for` loop, you pay that round-trip cost 10,000 times.

`bulk_create()` instead builds a **single** `INSERT` statement covering
many rows and sends it once. One round trip instead of thousands. The
difference is dramatic — see [Compare bulk vs loop](#compare-bulk-vs-loop)
near the end of this page for real numbers.

---

## Basic bulk operations

These four methods live directly on your model class. They're the
right tool when your dataset comfortably fits in memory and you don't need
retry logic — for anything large enough that a single failure shouldn't
lose your whole batch, skip ahead to
[Chunked bulk operations](#chunked-bulk-operations).

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

`records` is just a plain list of dicts — one dict per row, with the same
keys you'd pass to `.create()`. `bulk_create()` validates every record the
same way `.create()` does (checking required fields, types, lengths) and
then sends them all as one `INSERT` statement. It returns the number of
rows actually inserted.

### bulk_update()

Update many records at once — each dict in the list needs to include
whichever field you're using to identify the row (by default, `id`):

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

Unlike `bulk_create()`, `bulk_update()` doesn't combine everything into one
statement — under the hood it runs one `UPDATE` per record (each row can be
changing different fields, so they can't always be merged into a single
query). It still returns the total number of rows affected.

### bulk_delete()

Delete many records by their key value — pass a plain list of IDs (or
whatever field you're matching on):

```python
# Delete all inactive products
inactive = Product.filter(active=False)
ids      = [p["id"] for p in inactive]
deleted  = Product.bulk_delete(ids)
print(f"Deleted {deleted} products")

# Delete by custom key
Product.bulk_delete(["P00001", "P00002"], key="sku")
```

This one *does* run as a single `DELETE ... WHERE key IN (...)` statement,
so it's just as efficient as `bulk_create()`.

### bulk_upsert()

"Upsert" means **insert** a row if it doesn't exist yet, or **update** it
if it does — useful when you're syncing data from somewhere else and don't
know ahead of time which rows are new:

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
```

`conflict_key` is the field mydborm uses to decide "is this a new row or an
existing one?" — usually a column with a `UNIQUE` constraint, like a SKU
or email address. `update_fields` lists which columns get overwritten when
a conflict is found; any column you don't list stays untouched on existing
rows.

By default (`create_index=True`), if `conflict_key` isn't already a
primary key, mydborm automatically creates a `UNIQUE` index on it the
first time you call `bulk_upsert()` — without a unique index, the database
has no way to detect a "conflict" in the first place. The actual SQL
mydborm generates depends on which database you're using:

```python
# With create_index=True (default) — auto-creates UNIQUE index on conflict_key
# MySQL: ON DUPLICATE KEY UPDATE
# YugabyteDB / PostgreSQL: ON CONFLICT (sku) DO UPDATE SET
```

---

## Chunked bulk operations

The methods above are great until your dataset gets big enough that
sending it all as one giant SQL statement becomes a problem — a single
`INSERT` with 100,000 rows can hit query-size limits, tie up the database
connection for a long time, and if it fails partway through (a dropped
network connection, a database restart), you lose the *entire* batch with
no way to know which rows made it in.

The **chunked** versions in `mydborm.bulk` solve this by splitting your
data into smaller batches ("chunks") and sending each one as its own
statement, one after another. If one chunk fails, the others aren't
affected — you find out exactly which chunk failed and how many rows
succeeded before it.

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

`chunk_size` controls how many rows go into each individual `INSERT`
statement — with 100,000 records and `chunk_size=500`, that's 200 separate
statements sent one after another, instead of either 100,000 individual
`.create()` calls or one enormous 100,000-row statement. It's a middle
ground: each chunk is still fast to send, but you get far fewer round
trips than inserting row-by-row. See
[Choose the right chunk_size](#choose-the-right-chunk_size) below for
guidance on picking a number.

`retries` and `retry_delay` control what happens when a chunk fails — see
[Retry logic](#retry-logic) below for the full explanation.

### Progress callback

For a long-running import, it's useful to show *something* moving on
screen rather than staring at a frozen terminal for 30 seconds. Pass a
function to `on_progress` and mydborm calls it after every chunk finishes,
with how many rows are done so far and the total:

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

Same chunking and retry behavior as `chunked_bulk_create()`, but for
updates — each record in the list must include the `key` field so mydborm
knows which row to update:

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

If you pass `raise_on_error=True` and a chunk fails, `chunked_bulk_delete()`
raises `BulkDeleteError`:

```python
from mydborm import BulkDeleteError
from mydborm.bulk import chunked_bulk_delete

try:
    chunked_bulk_delete(Product, old_ids, chunk_size=1000, raise_on_error=True)
except BulkDeleteError as e:
    print(f"Bulk delete partially failed: failed={e.failed}")
```

---

## BulkResult

All three chunked functions above (and the non-chunked methods, via their
return values) describe what happened using a `BulkResult` object — a
single object that bundles up every statistic about the run instead of
making you track counters yourself:

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

A `chunked_bulk_create()` call only ever populates `.inserted` (the
`.updated`/`.deleted` counts stay `0`), and likewise `chunked_bulk_update()`
only populates `.updated`, and `chunked_bulk_delete()` only populates
`.deleted` — they all share the same `BulkResult` class, so unrelated
counters are simply left at zero rather than removed.

---

## Retry logic

Picture this: you kick off a bulk import of 50,000 rows split into 100
chunks, and chunk 37 fails because of a one-second network blip — nothing
actually wrong with your data. Without retries, that one hiccup would mark
500 rows as permanently failed, even though trying again half a second
later would have worked fine.

That's what the `retries` option buys you: each chunk is retried
independently, and if a retry succeeds, mydborm just moves on to the next
chunk as if nothing happened. The delay between retries grows each time —
this is called **exponential backoff**, and the idea is simple: if the
first retry fails too, the problem is more likely to be a real outage
than a one-off blip, so waiting a bit longer before trying again gives the
database more time to recover instead of hammering it repeatedly:

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

`retry_delay` is the *starting* delay in seconds — mydborm doubles it on
each subsequent attempt (`retry_delay * 2^attempt`), so `retry_delay=0.5`
with `retries=3` waits 0.5s, then 1.0s, then 2.0s before giving up on that
chunk. Only after all retries for a chunk are exhausted does it get
counted as failed; mydborm then moves on and keeps processing the
remaining chunks rather than stopping the whole operation.

### raise_on_error

By default, a failed chunk (after retries are exhausted) is just recorded
in `result.errors` and the operation keeps going — you check
`result.has_errors` afterward to see if anything went wrong. If you'd
rather stop immediately the moment any chunk fails — for example because a
failure usually means something is fundamentally broken (bad credentials,
a table that doesn't exist) rather than a transient blip — pass
`raise_on_error=True`:

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

Even when it raises, the exception still tells you how many rows made it
in *before* the failing chunk (`e.inserted`) — so you're not left
guessing whether it's safe to just re-run the whole import from scratch.

---

## Performance tips

### Choose the right chunk_size

There's no single "correct" chunk size — it's a trade-off between fewer
round trips (bigger chunks) and keeping each individual statement small
enough to send quickly and retry cheaply if it fails (smaller chunks). As
a starting point, scale it down as your rows get bigger or heavier:

```python
# Small records (a few fields) → larger chunks
result = chunked_bulk_create(User, records, chunk_size=1000)

# Large records (many fields, TEXT columns) → smaller chunks
result = chunked_bulk_create(Article, records, chunk_size=100)

# Very large records (BLOBs, encrypted fields) → tiny chunks
result = chunked_bulk_create(Document, records, chunk_size=10)
```

### Benchmark guide

Rough numbers to set expectations — actual timing depends on your
database, network, row size, and indexes:

| Records | chunk_size | Expected time |
|---|---|---|
| 1,000 | 500 | ~0.3s |
| 10,000 | 500 | ~2s |
| 100,000 | 500 | ~20s |
| 1,000,000 | 1000 | ~3-4 min |

### Compare bulk vs loop

This is the difference that motivates everything on this page — the same
1,000 rows, inserted two different ways:

```python
import time

# Slow — N separate INSERT statements (one round trip per row)
t0 = time.time()
for r in records[:1000]:
    Product.create(**r)
print(f"Loop: {time.time()-t0:.2f}s")   # ~10s

# Fast — 1 INSERT statement (one round trip total)
t0 = time.time()
Product.bulk_create(records[:1000])
print(f"Bulk: {time.time()-t0:.2f}s")   # ~0.3s
```

Same data, same database — roughly 30x faster just by batching the rows
into one statement instead of looping. That gap only grows as your row
count goes up, which is exactly why bulk operations (and their chunked
versions, for when "one giant statement" itself becomes the bottleneck)
exist.
