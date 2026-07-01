# Fields

When you define a model in mydborm, every class attribute you write is a
**field** — a small object that describes one column in the database
table. A field does three jobs at once:

1. It tells mydborm what SQL column to create (`INT`, `VARCHAR(50)`,
   `TEXT`, and so on) when you call `create_table()`.
2. It checks values before they're saved — so a typo like passing the
   string `"abc"` to a number field fails immediately in Python,
   instead of confusing the database later.
3. It can apply extra rules (uniqueness, defaults, required-ness) without
   you writing any SQL yourself.

```python
from mydborm import BaseModel, IntField, StrField

class Product(BaseModel):
    __tablename__ = "products"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)
```

Here, `id` and `name` are fields. `IntField` and `StrField` are two of
the many field *types* mydborm provides — each one matches a kind of
data you'd store (whole numbers, short text, true/false, dates, and so
on).

## Picking the right field type

The simplest rule of thumb: pick the field type that matches the
*shape* of your data, not the database column name you'd normally type
by hand.

- Storing a whole number (an age, a quantity, an ID)? Use `IntField`
  (or one of its bigger/smaller variants — see [Integer
  variants](#integer-variants)).
- Storing short text with a known maximum length (a username, an
  email)? Use `StrField`.
- Storing a number with decimal places? Use `FloatField` for things
  like scores or measurements where tiny rounding differences don't
  matter, or `DecimalField` for money, where they do.
- Storing true/false? Use `BoolField`.
- Storing a date, a time, or both? Use `DateField`, `TimeField`, or
  `DateTimeField`.

Every field type below follows the same pattern: you import it, use it
as a class attribute on your model, and pass it some options that
control how strict or flexible that column is.

---

## Options every field accepts

Regardless of which field type you pick, you can pass these keyword
arguments to any of them:

| Option | Type | Default | What it does |
|---|---|---|---|
| `primary_key` | bool | `False` | Marks this column as the table's unique identifier. mydborm auto-generates the value for you (an auto-incrementing number), so you never set it yourself when creating a row. |
| `nullable` | bool | `True` | Whether this column is allowed to be empty (`None` in Python, `NULL` in SQL). Set `nullable=False` to make a field required. |
| `default` | any | `None` | The value to use automatically if you don't supply one when creating a row. |
| `unique` | bool | `False` | If `True`, the database rejects any row that would duplicate an existing value in this column (handy for things like usernames or emails). |
| `index` | bool | `False` | If `True`, mydborm creates a database index on this column, which speeds up searches and filters on it at the cost of slightly slower writes. |
| `validators` | list | `[]` | A list of extra validation rules to run before saving — see [Custom validators](#custom-validators) below. |

A quick note on terminology: throughout this page you'll see "MySQL"
and "YugabyteDB" column types side by side. mydborm supports both
databases (plus PostgreSQL, which uses the same types as YugabyteDB),
and it automatically translates each field into the right SQL syntax
for whichever one you've connected to with `db.configure()`. You don't
need to remember the SQL names yourself — they're shown here mostly so
you know what's actually being created under the hood.

---

## All field types at a glance

| Field | Python type | MySQL | YugabyteDB / PostgreSQL |
|---|---|---|---|
| `IntField` | `int` | `INT` | `INTEGER` |
| `StrField(max_length=n)` | `str` | `VARCHAR(n)` | `VARCHAR(n)` |
| `TextField` | `str` | `TEXT` | `TEXT` |
| `BoolField` | `bool` | `TINYINT(1)` | `BOOLEAN` |
| `FloatField` | `float` | `FLOAT` | `FLOAT` |
| `DecimalField(precision, scale)` | `Decimal` | `DECIMAL(p,s)` | `DECIMAL(p,s)` |
| `DateField` | `date` | `DATE` | `DATE` |
| `DateTimeField` | `datetime` | `DATETIME` | `DATETIME` |
| `JSONField` | `dict`/`list` | `JSON` | `JSONB` |
| `ForeignKeyField(to=...)` | `int` | `INT` | `INTEGER` |
| `TinyIntField` | `int` | `TINYINT` | `SMALLINT` |
| `SmallIntField` | `int` | `SMALLINT` | `SMALLINT` |
| `BigIntField` | `int` | `BIGINT` | `BIGINT` |
| `UnsignedBigIntField` | `int` | `BIGINT UNSIGNED` | `NUMERIC(20)` |
| `DoubleField` | `float` | `DOUBLE` | `DOUBLE PRECISION` |
| `BitField(length=n)` | `int`/`str` | `BIT(n)` | `BIT(n)` |
| `CharField(length=n)` | `str` | `CHAR(n)` | `CHAR(n)` |
| `TinyTextField` | `str` | `TINYTEXT` | `TEXT` |
| `MediumTextField` | `str` | `MEDIUMTEXT` | `TEXT` |
| `LongTextField` | `str` | `LONGTEXT` | `TEXT` |
| `BinaryField(length=n)` | `bytes` | `BINARY(n)` | `BYTEA` |
| `VarBinaryField(max_length=n)` | `bytes` | `VARBINARY(n)` | `BYTEA` |
| `BlobField` | `bytes` | `BLOB`/`MEDIUMBLOB`/`LONGBLOB` | `BYTEA` |
| `TimeField` | `time` | `TIME` | `TIME` |
| `TimestampField` | `datetime` | `TIMESTAMP` | `TIMESTAMPTZ` |
| `EnumField(choices=[...])` | `str` | `ENUM(...)` | `VARCHAR(n)` |
| `SetField(choices=[...])` | `str`/`list` | `SET(...)` | `TEXT[]` |
| `PasswordField` | `str` | `VARCHAR(255)` | `VARCHAR(255)` |
| `EncryptedField` | `str` | `TEXT` | `TEXT` |

The most common fields you'll reach for in everyday models — `IntField`,
`StrField`, `TextField`, `BoolField`, `FloatField`, `DecimalField`,
`DateField`, `DateTimeField`, `JSONField`, and `ForeignKeyField` — are
covered in detail first. The rest are variants for more specific
situations (bigger numbers, fixed-size codes, binary data, and so on)
and are grouped together near the end of this page.

---

## IntField

`IntField` stores a whole number and becomes `INT` in MySQL or
`INTEGER` in YugabyteDB/PostgreSQL. Reach for it first whenever you
need IDs, counts, ages, or quantities — it's the field type you'll use
most often.

```python
from mydborm import BaseModel, IntField

class Product(BaseModel):
    __tablename__ = "products"
    id       = IntField(primary_key=True)   # AUTO_INCREMENT / SERIAL
    quantity = IntField(nullable=False)
    views    = IntField(default=0)
    rating   = IntField(nullable=True)
```

When `primary_key=True`, mydborm makes the column auto-increment — the
database assigns the next number for you, so you never set `id`
yourself when creating a row.

**SQL generated:**

```sql
-- MySQL
id       INT PRIMARY KEY AUTO_INCREMENT,
quantity INT NOT NULL,
views    INT DEFAULT 0,
rating   INT

-- YugabyteDB
id       SERIAL PRIMARY KEY,
quantity INTEGER NOT NULL,
views    INTEGER DEFAULT 0,
rating   INTEGER
```

If you pass a value that doesn't make sense for an integer column,
`IntField` raises an error before any SQL is sent — that's the
"validation" mentioned earlier in action:

```python
from mydborm import IntField

f = IntField(nullable=False)
f.name = "quantity"

f.validate(42)        # OK  → 42
f.validate(None)      # ERROR → ValueError: Field 'quantity' cannot be None
f.validate("abc")     # ERROR → TypeError: wrong type
```

**Real-world example:**

```python
class InventoryItem(BaseModel):
    __tablename__ = "inventory"
    id          = IntField(primary_key=True)
    product_id  = IntField(nullable=False)
    warehouse_id = IntField(nullable=False)
    quantity    = IntField(nullable=False, default=0)
    reorder_at  = IntField(nullable=True)   # reorder when qty drops below this

item_id = InventoryItem.create(
    product_id   = 1,
    warehouse_id = 5,
    quantity     = 100,
    reorder_at   = 10,
)
```

---

## StrField

`StrField` stores text up to a fixed maximum length and becomes
`VARCHAR(n)` in SQL — `n` being whatever number you pass as
`max_length`. Use it for anything that's text but has a sensible upper
bound: names, emails, short codes, usernames. If `max_length` isn't
given, it defaults to `255`.

```python
from mydborm import StrField

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50,  nullable=False, unique=True)
    email    = StrField(max_length=255, nullable=False, unique=True)
    nickname = StrField(max_length=50,  nullable=True, default="anonymous")
    locale   = StrField(max_length=5,   nullable=True, default="en")
```

**SQL generated:**

```sql
username VARCHAR(50)  NOT NULL UNIQUE,
email    VARCHAR(255) NOT NULL UNIQUE,
nickname VARCHAR(50)  DEFAULT 'anonymous',
locale   VARCHAR(5)   DEFAULT 'en'
```

`max_length` isn't just decoration — mydborm enforces it in Python too,
so you find out about an over-long value right away instead of waiting
for the database to complain:

```python
f = StrField(max_length=10, nullable=False)
f.name = "username"

f.validate("alice")        # OK  → "alice"
f.validate("a" * 11)       # ERROR → exceeds max_length=10
f.validate(None)           # ERROR → cannot be None
f.validate(123)            # ERROR → TypeError: expects str, got int
```

**Real-world example — product catalog:**

```python
class Product(BaseModel):
    __tablename__ = "products"
    id          = IntField(primary_key=True)
    sku         = StrField(max_length=20,  nullable=False, unique=True, index=True)
    name        = StrField(max_length=100, nullable=False)
    brand       = StrField(max_length=50,  nullable=True)
    color       = StrField(max_length=30,  nullable=True)
    size        = StrField(max_length=10,  nullable=True)
    category    = StrField(max_length=50,  nullable=True, index=True)

# Query by indexed fields is fast
laptops = Product.query().where("category", "Electronics").where("brand", "Apple").all()
```

---

## TextField

`TextField` stores text with no length limit, becoming a `TEXT` column
in both MySQL and YugabyteDB. Use it for anything that could run long
— article bodies, descriptions, freeform notes — where picking a
`max_length` for `StrField` wouldn't make sense.

```python
from mydborm import TextField

class Article(BaseModel):
    __tablename__ = "articles"
    id      = IntField(primary_key=True)
    title   = StrField(max_length=200, nullable=False)
    body    = TextField(nullable=False)        # unlimited
    summary = StrField(max_length=500, nullable=True)  # short excerpt
    notes   = TextField(nullable=True)         # internal notes

aid = Article.create(
    title   = "Getting started with mydborm",
    body    = "This is a very long article... " * 1000,
    summary = "A quick intro to mydborm",
)
```

!!! note
    `TextField` doesn't take a `max_length` argument — that's the
    whole point of it. If you need a short, searchable string with a
    known limit, use `StrField` instead; if the content could be
    arbitrarily long, use `TextField`.

---

## BoolField

`BoolField` stores a true/false value. It becomes `TINYINT(1)` in
MySQL (where the database itself only understands `1`/`0`) or native
`BOOLEAN` in YugabyteDB/PostgreSQL — but in your Python code you should
always write `True`/`False`, never `1`/`0`. mydborm handles translating
between the two automatically.

```python
from mydborm import BoolField

class User(BaseModel):
    __tablename__ = "users"
    id         = IntField(primary_key=True)
    active     = BoolField(default=True)
    verified   = BoolField(default=False)
    is_admin   = BoolField(nullable=False, default=False)
    newsletter = BoolField(nullable=True)
```

**SQL generated:**

```sql
-- MySQL
active     TINYINT(1) DEFAULT 1,
verified   TINYINT(1) DEFAULT 0,
is_admin   TINYINT(1) NOT NULL DEFAULT 0

-- YugabyteDB
active     BOOLEAN DEFAULT TRUE,
verified   BOOLEAN DEFAULT FALSE,
is_admin   BOOLEAN NOT NULL DEFAULT FALSE
```

Passing anything other than an actual Python `bool` is rejected — even
numbers, even though MySQL itself stores booleans as numbers under the
hood:

```python
f = BoolField(nullable=False)
f.name = "active"

f.validate(True)    # OK  → True
f.validate(False)   # OK  → False
f.validate(None)    # ERROR → cannot be None
f.validate("yes")   # ERROR → TypeError: expects bool, got str
f.validate(1)       # ERROR → TypeError: expects bool, got int
```

!!! warning "Dialect difference"
    MySQL stores booleans as `TINYINT(1)` and would normally hand you
    back `1`/`0` if you queried it directly. YugabyteDB returns native
    `True`/`False`. mydborm smooths this difference over for you — as
    long as you stick to `True`/`False` in your own code, you don't
    need to worry about which database you're using.

**Real-world example — feature flags:**

```python
class FeatureFlag(BaseModel):
    __tablename__ = "feature_flags"
    id          = IntField(primary_key=True)
    name        = StrField(max_length=50, nullable=False, unique=True)
    enabled     = BoolField(default=False)
    beta_only   = BoolField(default=True)
    description = StrField(max_length=255, nullable=True)

# Toggle a feature
FeatureFlag.update({"enabled": True}, name="dark_mode")

# Get all enabled features
enabled = FeatureFlag.filter(enabled=True)
```

---

## FloatField

`FloatField` stores a number with a decimal point and becomes a
`FLOAT` column. It's a good fit for things like measurements, scores,
or ratings, where tiny rounding differences don't matter. For money or
anything where exact precision matters, use [`DecimalField`](#decimalfield)
instead — see why in the next section.

```python
from mydborm import FloatField

class Product(BaseModel):
    __tablename__ = "products"
    id     = IntField(primary_key=True)
    price  = FloatField(nullable=False)
    weight = FloatField(nullable=True)   # kg
    rating = FloatField(nullable=True, default=0.0)  # 0.0–5.0
```

Whole numbers passed in are automatically converted to floats for you:

```python
f = FloatField(nullable=False)
f.name = "price"

f.validate(9.99)    # OK  → 9.99
f.validate(10)      # OK  → 10.0 (coerced from int)
f.validate("bad")   # ERROR → TypeError
f.validate(None)    # ERROR → cannot be None
```

**Real-world example — analytics:**

```python
class PageView(BaseModel):
    __tablename__ = "page_views"
    id          = IntField(primary_key=True)
    url         = StrField(max_length=500, nullable=False)
    load_time   = FloatField(nullable=True)   # seconds
    scroll_pct  = FloatField(nullable=True)   # 0.0–100.0
    bounce      = BoolField(default=False)

# Average load time per URL
rows = db.fetchall(
    "SELECT url, AVG(load_time) AS avg_ms FROM page_views GROUP BY url ORDER BY avg_ms DESC LIMIT 10"
)
```

---

## DecimalField

`DecimalField` stores a fixed-precision number and becomes
`DECIMAL(precision, scale)` in SQL. `precision` is the total number of
digits allowed, and `scale` is how many of those digits come after the
decimal point. If you don't pass either, they default to `precision=10,
scale=2` — good enough for most prices.

```python
from mydborm import DecimalField

class Order(BaseModel):
    __tablename__ = "orders"
    id          = IntField(primary_key=True)
    subtotal    = DecimalField(precision=10, scale=2, nullable=False)  # 99999999.99
    tax         = DecimalField(precision=10, scale=2, nullable=False)
    discount    = DecimalField(precision=10, scale=2, default=0.00)
    total       = DecimalField(precision=10, scale=2, nullable=False)
    currency    = StrField(max_length=3, default="USD")
```

!!! tip "Always use DecimalField for money"
    Computers store regular floating-point numbers (`FloatField`) in a
    way that can introduce tiny rounding errors — for example,
    `0.1 + 0.2` comes out to `0.30000000000000004`, not `0.3`. That's
    harmless for things like ratings, but unacceptable for money.
    `DecimalField` uses Python's `Decimal` type instead, which is
    exact: `0.1 + 0.2 = 0.3`, every time.

**Real-world example:**

```python
from decimal import Decimal

oid = Order.create(
    subtotal = Decimal("99.99"),
    tax      = Decimal("8.00"),
    discount = Decimal("10.00"),
    total    = Decimal("97.99"),
    currency = "USD",
)
order = Order.get(id=oid)
print(order["total"])   # Decimal('97.99') — exact!
```

---

## DateField

`DateField` stores a calendar date — year, month, day — with no time
of day attached, and becomes a `DATE` column. Use it for things like
birthdays or hire dates, where the time of day is irrelevant or
unknown.

```python
from mydborm import DateField

class Employee(BaseModel):
    __tablename__ = "employees"
    id         = IntField(primary_key=True)
    name       = StrField(max_length=100, nullable=False)
    hired_on   = DateField(nullable=False)
    left_on    = DateField(nullable=True)
    birthday   = DateField(nullable=True)
```

You can pass a Python `date` object (recommended) or a date string —
both are accepted:

```python
from datetime import date

eid = Employee.create(
    name     = "Alice Smith",
    hired_on = date(2024, 1, 15),
    birthday = date(1990, 6, 20),
)

emp = Employee.get(id=eid)
print(emp["hired_on"])        # 2024-01-15
print(type(emp["hired_on"]))  # <class 'datetime.date'>

# Query employees hired this year
import datetime
year_start = date(datetime.date.today().year, 1, 1)
new_hires = Employee.query().where("hired_on__gte", year_start).all()
print(f"New hires this year: {len(new_hires)}")

# Find employees with birthdays this month
this_month = date.today().month
# Use raw SQL for complex date functions
rows = db.fetchall(
    "SELECT * FROM employees WHERE MONTH(birthday) = %s",
    [this_month]
)
```

---

## DateTimeField

`DateTimeField` stores both a date *and* a time of day, becoming
`DATETIME` in MySQL or `TIMESTAMP` in YugabyteDB/PostgreSQL. Use it
whenever you need to know not just *that* something happened, but
*when* — log entries, "created at" timestamps, scheduled events.

```python
from mydborm import DateTimeField

class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    id         = IntField(primary_key=True)
    user_id    = IntField(nullable=False)
    action     = StrField(max_length=50, nullable=False)
    table_name = StrField(max_length=50, nullable=False)
    record_id  = IntField(nullable=True)
    created_at = DateTimeField(nullable=True)
```

**Real-world example:**

```python
from datetime import datetime, timedelta

# Log an action
log_id = AuditLog.create(
    user_id    = 1,
    action     = "UPDATE",
    table_name = "products",
    record_id  = 42,
    created_at = datetime.now(),
)

# Find recent activity — last 24 hours
cutoff = datetime.now() - timedelta(hours=24)
recent = (AuditLog.query()
                  .where("created_at__gte", cutoff)
                  .order_by("created_at", desc=True)
                  .all())
print(f"Actions in last 24h: {len(recent)}")

# Serialise datetime to JSON
log = AuditLog.get(id=log_id)
j = log.to_json()   # datetime auto-converted to ISO string
print(j)
# {"id": 1, "created_at": "2024-06-19T10:30:00", ...}
```

If you need a timestamp that's aware of time zones (rather than just a
plain date and time), see [`TimestampField`](#timefield-and-timestampfield)
further down.

---

## JSONField

`JSONField` stores structured data — nested dictionaries, lists,
whatever shape you need — directly in a column, becoming `JSON` in
MySQL or `JSONB` (a faster, indexable binary form of JSON) in
YugabyteDB. It's useful for things you don't want to model as separate
columns: per-user settings, flexible metadata, tags.

```python
from mydborm import JSONField

class UserProfile(BaseModel):
    __tablename__ = "user_profiles"
    id          = IntField(primary_key=True)
    user_id     = IntField(nullable=False, unique=True)
    settings    = JSONField(nullable=False)
    preferences = JSONField(nullable=True)
    tags        = JSONField(nullable=True)
    metadata    = JSONField(nullable=True)
```

You can store dictionaries or lists, and read/write nested values just
like any other Python data structure:

```python
# Store nested config
uid = UserProfile.create(
    user_id  = 1,
    settings = {
        "theme": "dark",
        "language": "en",
        "notifications": {
            "email": True,
            "push": False,
            "frequency": "daily"
        }
    },
    tags     = ["premium", "beta-tester", "verified"],
    metadata = {
        "signup_source": "google",
        "referral_code": "FRIEND50",
        "last_login":    "2024-06-19T10:00:00"
    }
)

profile = UserProfile.get(id=uid)

# Access nested values
theme = profile["settings"]["theme"]                   # "dark"
email = profile["settings"]["notifications"]["email"]  # True
first_tag = profile["tags"][0]                          # "premium"

# Update a nested value
settings = profile["settings"]
settings["theme"] = "light"
UserProfile.update({"settings": settings}, id=uid)
```

!!! tip "YugabyteDB JSONB advantage"
    YugabyteDB stores JSON as `JSONB` (a binary representation rather
    than plain text), which is faster to query and lets you build
    indexes that search *inside* the JSON itself.

---

## ForeignKeyField

`ForeignKeyField` is how you link one table to another. It's an `INT`
column that holds the primary key value of a row in a different
table, and `create_table()` backs it with a real database-level
`FOREIGN KEY ... REFERENCES ...` constraint — the database itself
rejects inserts/updates that point at a row that doesn't exist. Pass
the related model's class name as a string to `to=`.

```python
from mydborm import ForeignKeyField

class Author(BaseModel):
    __tablename__ = "authors"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)

class Book(BaseModel):
    __tablename__ = "books"
    id        = IntField(primary_key=True)
    title     = StrField(max_length=200, nullable=False)
    author_id = ForeignKeyField(to="Author", nullable=False)
    price     = FloatField(nullable=False)

Author.create_table()
Book.create_table()
```

**SQL generated (`Book.create_table()`):**

```sql
-- MySQL
CREATE TABLE books (
  id        INT NOT NULL AUTO_INCREMENT,
  title     VARCHAR(200) NOT NULL,
  author_id INT NOT NULL,
  price     FLOAT NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY (author_id) REFERENCES authors (id)
);
```

```python
Book.create(title="Orphan", author_id=999)
# -> raises a database IntegrityError / ForeignKeyViolation —
#    there's no author with id 999
```

!!! note "Requirements"
    - The referenced model (`to=`) must already be defined (imported)
      before you call `create_table()` — it's resolved by class name
      against every `BaseModel` subclass. A self-reference (e.g.
      `parent_id = ForeignKeyField(to="Category")` on `Category`
      itself) is fine.
    - The referenced model must have a **single-column** primary key.
      Referencing a model with a composite `__pk__` raises `ValueError`
      at `create_table()` time.
    - Create the referenced table first (or, for a self-reference,
      it's created automatically since the constraint targets the same
      `CREATE TABLE` statement).
    - `on_delete`/`on_update` cascade actions (e.g. `ON DELETE CASCADE`)
      aren't generated — only the bare constraint.

If you find yourself writing a lot of `ForeignKeyField` columns and
then joining across them by hand, take a look at
[Relationships](relationships.md) — it builds `has_many`/`belongs_to`
helpers on top of exactly this field type, so you don't have to write
the joins yourself.

**Real-world example — full e-commerce schema:**

```python
class Category(BaseModel):
    __tablename__ = "categories"
    id        = IntField(primary_key=True)
    name      = StrField(max_length=50, nullable=False)
    parent_id = ForeignKeyField(to="Category", nullable=True)  # self-referential

class Supplier(BaseModel):
    __tablename__ = "suppliers"
    id      = IntField(primary_key=True)
    name    = StrField(max_length=100, nullable=False)
    country = StrField(max_length=50, nullable=True)

class Product(BaseModel):
    __tablename__ = "products"
    id          = IntField(primary_key=True)
    name        = StrField(max_length=100, nullable=False)
    sku         = StrField(max_length=20, nullable=False, unique=True)
    category_id = ForeignKeyField(to="Category", nullable=True)
    supplier_id = ForeignKeyField(to="Supplier", nullable=True)
    price       = FloatField(nullable=False)

# Create all tables
Category.create_table()
Supplier.create_table()
Product.create_table()

# Seed
cat_id  = Category.create(name="Electronics")
sup_id  = Supplier.create(name="TechCorp", country="USA")
prod_id = Product.create(
    name        = "Laptop Pro",
    sku         = "LAPTOP-001",
    category_id = cat_id,
    supplier_id = sup_id,
    price       = 999.99,
)

# JOIN query
results = (Product.query()
                  .inner_join("categories", "products.category_id = categories.id")
                  .inner_join("suppliers",  "products.supplier_id = suppliers.id")
                  .where("categories.name", "Electronics")
                  .all())
```

---

## Extended field types

The fields above cover most day-to-day needs, but mydborm also ships a
larger set of more specialized field types, for when you need more
control over exactly how something is stored — a smaller integer to
save space, a fixed-width code, raw binary data, and so on. You don't
need to know all of these up front; skim the headings and come back
when you hit a specific need.

### Integer variants

`IntField` is a good default, but if you know your numbers will always
be small (saving a little storage) or might be very large (avoiding
overflow errors), these variants give you more control:

- **`TinyIntField`** — a 1-byte integer. MySQL stores it as a true
  `TINYINT` (-128 to 127); YugabyteDB maps it up to `SMALLINT` since it
  has no native tiny integer type. Good for small bounded values like
  a 1-5 star rating or a small priority level.
- **`SmallIntField`** — a 2-byte integer (-32768 to 32767) in both
  MySQL and YugabyteDB. Useful for things like a year or a sort order
  where you know the value will always be modest.
- **`BigIntField`** — an 8-byte integer, for when a regular `IntField`
  isn't big enough — file sizes in bytes, view counters, or IDs in a
  system large enough to exceed a few billion rows.
- **`UnsignedBigIntField`** — an 8-byte integer that can never be
  negative, doubling the usable positive range compared to a signed
  `BigIntField`. MySQL stores it as `BIGINT UNSIGNED`; YugabyteDB maps
  it to `NUMERIC(20)` to avoid overflow, since it has no unsigned
  integer type. Useful for checksums or token IDs that are always
  non-negative.

```python
from mydborm import TinyIntField, SmallIntField, BigIntField, UnsignedBigIntField

class FileUpload(BaseModel):
    __tablename__ = "file_uploads"
    id         = IntField(primary_key=True)
    priority   = TinyIntField(default=0)          # small bounded value
    sort_order = SmallIntField(default=0)
    file_size  = BigIntField(nullable=True)        # bytes — can get large
    checksum   = UnsignedBigIntField(nullable=True) # always non-negative
```

### Floating-point variants

- **`DoubleField`** — a higher-precision floating point number than
  `FloatField` (`DOUBLE` in MySQL, `DOUBLE PRECISION` in YugabyteDB).
  Use it when you need more decimal digits of accuracy than
  `FloatField` gives you — for example latitude/longitude coordinates,
  where small precision losses can shift a location noticeably.

```python
from mydborm import DoubleField

class Location(BaseModel):
    __tablename__ = "locations"
    id        = IntField(primary_key=True)
    latitude  = DoubleField(nullable=True)
    longitude = DoubleField(nullable=True)
```

### Fixed-width text and bits

- **`CharField(length=n)`** — a fixed-width, space-padded string of
  exactly `n` characters (`CHAR(n)`). Use this instead of `StrField`
  when every value really is the same length, like a 2-letter country
  code or a 3-letter currency code — it's slightly more efficient than
  a variable-length column for that case.
- **`BitField(length=n)`** — stores a fixed number of bits (1 to 64),
  for compact flag/permission storage.

```python
from mydborm import CharField, BitField

class Address(BaseModel):
    __tablename__ = "addresses"
    id           = IntField(primary_key=True)
    country_code = CharField(length=2, nullable=False)   # "US", "GB"
    currency     = CharField(length=3, nullable=True)    # "USD", "EUR"
    flags        = BitField(length=8, nullable=True)     # 8-bit flag set
```

### Text variants

If `TextField` doesn't give you enough granularity, MySQL distinguishes
between a few sizes of unlimited text. YugabyteDB doesn't have separate
types for these, so mydborm maps all of them to a plain `TEXT` column
there:

- **`TinyTextField`** — up to 255 bytes. Good for short captions or
  notes where you still want "no fixed length" semantics.
- **`MediumTextField`** — up to 16 MB. Good for long-form content like
  full articles.
- **`LongTextField`** — up to 4 GB. Good for very large content like
  whole documents or large log dumps.

```python
from mydborm import TinyTextField, MediumTextField, LongTextField

class Article(BaseModel):
    __tablename__ = "articles"
    id           = IntField(primary_key=True)
    tagline      = TinyTextField(nullable=True)
    article_body = MediumTextField(nullable=False)
    raw_html     = LongTextField(nullable=True)
```

### Binary data

These fields store raw bytes rather than text — use them for hashes,
encoded keys, or small files. MySQL has separate fixed- and
variable-length binary types; YugabyteDB stores all of them as
`BYTEA`.

- **`BinaryField(length=n)`** — fixed-length binary data, e.g. exactly
  32 bytes for a SHA-256 hash.
- **`VarBinaryField(max_length=n)`** — variable-length binary data up
  to a maximum size, e.g. a digital signature.
- **`BlobField(blob_type=...)`** — for genuinely large binary content
  like images, audio, or file attachments. `blob_type` can be
  `"TINYBLOB"`, `"BLOB"` (the default), `"MEDIUMBLOB"`, or
  `"LONGBLOB"`, matching MySQL's size tiers; YugabyteDB stores all of
  them as `BYTEA` regardless of which tier you pick.

```python
from mydborm import BinaryField, VarBinaryField, BlobField

class Document(BaseModel):
    __tablename__ = "documents"
    id         = IntField(primary_key=True)
    hash_value = BinaryField(length=32, nullable=True)     # SHA-256
    signature  = VarBinaryField(max_length=256, nullable=True)
    attachment = BlobField(blob_type="LONGBLOB", nullable=True)
```

### TimeField and TimestampField

- **`TimeField`** — stores a time of day with no date attached (e.g.
  `"09:00:00"`), for things like opening hours.
- **`TimestampField`** — like `DateTimeField`, but timezone-aware:
  MySQL stores it as `TIMESTAMP`, and YugabyteDB stores it as
  `TIMESTAMPTZ`. Use `TimestampField` for columns like `created_at` or
  `expires_at` where you need to know *which* timezone a moment
  happened in; use plain `DateTimeField` when timezone doesn't matter
  for your use case.

```python
from mydborm import TimeField, TimestampField

class Store(BaseModel):
    __tablename__ = "stores"
    id         = IntField(primary_key=True)
    opens_at   = TimeField(nullable=True)
    closes_at  = TimeField(nullable=True)
    created_at = TimestampField(nullable=True)
    expires_at = TimestampField(nullable=True)
```

### EnumField and SetField

These two fields restrict a column to a fixed list of allowed values —
the difference is whether a row can hold *one* value from the list or
*several at once*:

- **`EnumField(choices=[...])`** — exactly one value out of a fixed
  list, e.g. an order's status. MySQL uses its native `ENUM(...)`
  type; YugabyteDB doesn't have a direct equivalent, so mydborm stores
  it as a `VARCHAR` sized to fit the longest choice, and still
  validates that only allowed values are saved.
- **`SetField(choices=[...])`** — zero or more values from a fixed
  list, stored together in one column, e.g. a list of tags. MySQL uses
  its native comma-separated `SET(...)` type; YugabyteDB stores it as
  a native array (`TEXT[]`). You can pass either a list/tuple/set of
  strings, or a single comma-separated string — both are accepted.

```python
from mydborm import EnumField, SetField

class Order(BaseModel):
    __tablename__ = "orders"
    id     = IntField(primary_key=True)
    status = EnumField(choices=["pending", "processing", "shipped", "delivered"])
    tags   = SetField(choices=["gift", "fragile", "rush", "international"])

oid = Order.create(status="pending", tags=["gift", "rush"])

try:
    Order.create(status="lost-in-space")
except ValueError as e:
    print(e)  # Field 'status' must be one of [...]. Got: 'lost-in-space'
```

---

## Password and encrypted fields

For sensitive data, mydborm provides two purpose-built field types
instead of expecting you to roll your own hashing or encryption:

- **`PasswordField`** — automatically hashes whatever string you assign
  to it using bcrypt before it's saved. The hash is one-way: there's no
  way to recover the original password from it, which is exactly what
  you want for login credentials. You check a password later with
  `PasswordField.verify(plain, hashed)`.
- **`EncryptedField`** — automatically encrypts the value using AES
  (via the `cryptography` library's Fernet scheme) before saving, and
  can decrypt it back when you need the original value. Use this for
  things you need to retrieve later in their original form, like API
  keys or tokens — unlike `PasswordField`, this is two-way.

Both require the optional `security` extra:

```bash
pip install mydborm[security]
```

```python
from mydborm import BaseModel, IntField, StrField, PasswordField

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50, nullable=False)
    password = PasswordField(nullable=False)

# Password is hashed automatically — you never see or store the raw value
uid = User.create(username="alice", password="mysecretpass")

user = User.get(id=uid)
print(PasswordField.verify("mysecretpass", user["password"]))  # True
print(PasswordField.verify("wrongpass", user["password"]))     # False
```

The full walkthrough — including `EncryptedField`, key generation, and
security best practices — lives on its own page: see
[Security](security.md).

---

## Custom validators

The `nullable`, `unique`, and `max_length` options cover the basics,
but sometimes you need a more specific rule — "must look like an
email address," "must be between 1 and 5," "must be one of these
exact strings." That's what the `validators` option is for: pass a
list of validator objects to any field, and mydborm runs them every
time you `create()` or `update()` a row, before anything is sent to
the database.

```python
from mydborm import StrField, EmailValidator

class Contact(BaseModel):
    __tablename__ = "contacts"
    id    = IntField(primary_key=True)
    email = StrField(max_length=255, nullable=False,
                     validators=[EmailValidator()])

Contact.create(email="alice@example.com")        # OK

try:
    Contact.create(email="not-an-email")
except ValueError as e:
    print(e)
    # Field 'email' must be a valid email address. Got: 'not-an-email'
```

mydborm ships six built-in validators covering the most common cases —
email format, URL format, regex patterns, numeric ranges, minimum
string length, and fixed choice lists — and you can attach more than
one to the same field, or write your own. The full reference, with
examples for each one, lives on its own page: see
[Validators](validators.md).

You can also validate *across* multiple fields at once (for example,
"if country is US, state is required") using a model's `__validators__`
list:

```python
class ShippingAddress(BaseModel):
    __tablename__ = "shipping_addresses"
    id          = IntField(primary_key=True)
    country     = StrField(max_length=2,  nullable=False)
    postal_code = StrField(max_length=10, nullable=False)
    state       = StrField(max_length=50, nullable=True)

    __validators__ = [
        # US addresses require state
        lambda data: (_ for _ in ()).throw(
            ValueError("State is required for US addresses")
        ) if data.get("country") == "US" and not data.get("state") else None,

        # US zip codes: 5 digits or 5+4
        lambda data: (_ for _ in ()).throw(
            ValueError("Invalid US zip code format")
        ) if (data.get("country") == "US" and
              not __import__("re").match(r"^\d{5}(-\d{4})?$",
                                         data.get("postal_code", ""))) else None,
    ]

# OK
ShippingAddress.create(country="US", postal_code="10001", state="NY")
ShippingAddress.create(country="GB", postal_code="SW1A 1AA")

# Fails — US needs state
try:
    ShippingAddress.create(country="US", postal_code="10001")
except ValueError as e:
    print(e)  # State is required for US addresses
```

## Where to go next

- [Models & CRUD](models.md) — using fields together in a model, and
  the full create/read/update/delete API
- [Validators](validators.md) — the complete validator reference
- [Security](security.md) — `PasswordField` and `EncryptedField` in
  depth, including key management
- [Migrations](migrations.md) — changing field definitions on a table
  that already has data in it
