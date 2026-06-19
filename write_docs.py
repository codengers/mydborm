# -*- coding: utf-8 -*-
import os

BASE = r"C:\Users\atikr\OneDrive\Python_work\mydborm"

files = {}

files["docs/guide/fields.md"] = r'''# Fields

Fields define the columns in your database table. Each field maps a Python type to a SQL column, with full dialect support for MySQL and YugabyteDB.

---

## All field types at a glance

| Field | Python type | MySQL | YugabyteDB |
|---|---|---|---|
| `IntField` | `int` | `INT` | `INTEGER` |
| `StrField(max_length=n)` | `str` | `VARCHAR(n)` | `VARCHAR(n)` |
| `TextField` | `str` | `TEXT` | `TEXT` |
| `BoolField` | `bool` | `TINYINT(1)` | `BOOLEAN` |
| `FloatField` | `float` | `FLOAT` | `FLOAT` |
| `DecimalField(p,s)` | `Decimal` | `DECIMAL(p,s)` | `DECIMAL(p,s)` |
| `DateField` | `date` | `DATE` | `DATE` |
| `DateTimeField` | `datetime` | `DATETIME` | `TIMESTAMP` |
| `JSONField` | `dict/list` | `JSON` | `JSONB` |
| `ForeignKeyField(to)` | `int` | `INT` | `INTEGER` |

---

## Field options

Every field accepts these common options:

| Option | Type | Default | Description |
|---|---|---|---|
| `primary_key` | bool | False | Auto-increment PK |
| `nullable` | bool | True | Allow NULL |
| `default` | any | None | Default value |
| `unique` | bool | False | UNIQUE constraint |
| `index` | bool | False | Create index |
| `validators` | list | [] | Custom validators |

---

## IntField

Maps to `INT` (MySQL) / `INTEGER` (YugabyteDB). Use for IDs, counts, ages, quantities.

```python
from mydborm import BaseModel, IntField

class Product(BaseModel):
    __tablename__ = "products"
    id       = IntField(primary_key=True)   # AUTO_INCREMENT / SERIAL
    quantity = IntField(nullable=False)
    views    = IntField(default=0)
    rating   = IntField(nullable=True)
```

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

**Validation examples:**

```python
from mydborm import IntField

f = IntField(nullable=False)
f.name = "quantity"

f.validate(42)        # OK  → 42
f.validate("10")      # OK  → coerced to 10
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

Maps to `VARCHAR(n)`. Use for names, emails, codes — any text with a known max length.

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

**Validation examples:**

```python
f = StrField(max_length=10, nullable=False)
f.name = "username"

f.validate("alice")         # OK  → "alice"
f.validate("a" * 11)       # ERROR → exceeds max_length=10
f.validate(None)            # ERROR → cannot be None
f.validate(123)             # OK  → coerced to "123"
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

Maps to `TEXT`. No size limit — use for long content like descriptions, blog posts, notes.

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
    `TextField` has no `max_length` parameter. For searchable short strings use `StrField`. For long content use `TextField`.

---

## BoolField

Maps to `TINYINT(1)` (MySQL) / `BOOLEAN` (YugabyteDB). Always use `True`/`False` — not `1`/`0`.

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

**Validation examples:**

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
    MySQL stores booleans as `TINYINT(1)` and returns `1`/`0`.
    YugabyteDB returns native `True`/`False`.
    mydborm normalises this — always use `True`/`False` in your code.

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

Maps to `FLOAT`. Good for prices, scores, ratings. For money use `DecimalField`.

```python
from mydborm import FloatField

class Product(BaseModel):
    __tablename__ = "products"
    id     = IntField(primary_key=True)
    price  = FloatField(nullable=False)
    weight = FloatField(nullable=True)   # kg
    rating = FloatField(nullable=True, default=0.0)  # 0.0–5.0
```

**Validation examples:**

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

Maps to `DECIMAL(precision, scale)`. Use for money and anything where floating point errors matter.

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
    `FloatField` can have rounding errors: `0.1 + 0.2 = 0.30000000000000004`.
    `DecimalField` is exact: `0.1 + 0.2 = 0.3`.

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

Maps to `DATE`. Stores year, month, day — no time component.

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

**Real-world example:**

```python
from datetime import date

eid = Employee.create(
    name     = "Alice Smith",
    hired_on = date(2024, 1, 15),
    birthday = date(1990, 6, 20),
)

emp = Employee.get(id=eid)
print(emp["hired_on"])   # 2024-01-15
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

Maps to `DATETIME` (MySQL) / `TIMESTAMP` (YugabyteDB). Full date + time.

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

---

## JSONField

Maps to `JSON` (MySQL) / `JSONB` (YugabyteDB). Store structured data — settings, metadata, tags.

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

**Real-world examples:**

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
theme = profile["settings"]["theme"]           # "dark"
email = profile["settings"]["notifications"]["email"]  # True
first_tag = profile["tags"][0]                 # "premium"

# Update a nested value
settings = profile["settings"]
settings["theme"] = "light"
UserProfile.update({"settings": settings}, id=uid)
```

!!! tip "YugabyteDB JSONB advantage"
    YugabyteDB stores JSON as `JSONB` (binary) which is faster to query and
    supports GIN indexes for searching inside JSON fields.

---

## ForeignKeyField

Maps to `INT` — a reference to another table's primary key.

```python
from mydborm import ForeignKeyField

class Author(BaseModel):
    __tablename__ = "authors"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)

class Book(BaseModel):
    __tablename__ = "books"
    id          = IntField(primary_key=True)
    title       = StrField(max_length=200, nullable=False)
    author_id   = ForeignKeyField(to="Author", nullable=False)
    category_id = ForeignKeyField(to="Category", nullable=True)  # optional FK
    price       = FloatField(nullable=False)
```

**SQL generated:**

```sql
-- MySQL / YugabyteDB
author_id   INT NOT NULL,
category_id INT
```

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

## Custom validators

Attach validation rules to any field using the `validators` parameter.

### Built-in validators

```python
from mydborm import (
    EmailValidator,     # valid email format
    UrlValidator,       # valid http/https URL
    RegexValidator,     # custom regex pattern
    RangeValidator,     # numeric min/max
    MinLengthValidator, # minimum string length
    ChoiceValidator,    # allowed values list
)
```

### EmailValidator

```python
from mydborm import StrField, EmailValidator

class Contact(BaseModel):
    __tablename__ = "contacts"
    id    = IntField(primary_key=True)
    email = StrField(max_length=255, nullable=False,
                     validators=[EmailValidator()])

# Valid
Contact.create(email="alice@example.com")        # OK
Contact.create(email="user.name+tag@domain.co.uk")  # OK

# Invalid
try:
    Contact.create(email="not-an-email")
except ValueError as e:
    print(e)
    # Field 'email' must be a valid email address. Got: 'not-an-email'

try:
    Contact.create(email="missing@domain")
except ValueError as e:
    print(e)
    # Field 'email' must be a valid email address. Got: 'missing@domain'
```

### UrlValidator

```python
from mydborm import StrField, UrlValidator

class Website(BaseModel):
    __tablename__ = "websites"
    id  = IntField(primary_key=True)
    url = StrField(max_length=500, nullable=False,
                   validators=[UrlValidator()])

Website.create(url="https://example.com")         # OK
Website.create(url="http://example.com/path?q=1") # OK

try:
    Website.create(url="example.com")   # missing http://
except ValueError as e:
    print(e)  # Field 'url' must be a valid URL. Got: 'example.com'

try:
    Website.create(url="ftp://example.com")   # only http/https
except ValueError as e:
    print(e)  # Field 'url' must be a valid URL. Got: 'ftp://example.com'
```

### RangeValidator

```python
from mydborm import IntField, FloatField, RangeValidator

class Product(BaseModel):
    __tablename__ = "products"
    id       = IntField(primary_key=True)
    price    = FloatField(nullable=False,
                          validators=[RangeValidator(min_val=0.01, max_val=99999.99)])
    discount = IntField(nullable=True,
                        validators=[RangeValidator(min_val=0, max_val=100)])
    rating   = FloatField(nullable=True,
                          validators=[RangeValidator(min_val=1.0, max_val=5.0)])

Product.create(price=29.99, discount=10, rating=4.5)  # OK

try:
    Product.create(price=-5.00)   # negative price
except ValueError as e:
    print(e)  # Field 'price' must be >= 0.01. Got: -5.0

try:
    Product.create(price=10.0, discount=150)  # discount > 100
except ValueError as e:
    print(e)  # Field 'discount' must be <= 100. Got: 150
```

### RegexValidator

```python
from mydborm import StrField, RegexValidator

class Product(BaseModel):
    __tablename__ = "products"
    id  = IntField(primary_key=True)
    sku = StrField(max_length=20, nullable=False,
                   validators=[RegexValidator(
                       r'^[A-Z]{2,4}-\d{4}$',
                       message="SKU format: 2-4 uppercase letters, dash, 4 digits (e.g. PROD-0001)"
                   )])
    hex_color = StrField(max_length=7, nullable=True,
                         validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$')])

Product.create(sku="PROD-0001", hex_color="#FF5733")  # OK
Product.create(sku="AB-1234",   hex_color="#000000")  # OK

try:
    Product.create(sku="prod-0001")   # lowercase not allowed
except ValueError as e:
    print(e)  # SKU format: 2-4 uppercase letters, dash, 4 digits (e.g. PROD-0001)
```

### MinLengthValidator

```python
from mydborm import StrField, MinLengthValidator

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50, nullable=False,
                        validators=[MinLengthValidator(3)])
    password = StrField(max_length=255, nullable=False,
                        validators=[MinLengthValidator(8)])

User.create(username="alice", password="securepass123")  # OK

try:
    User.create(username="ab", password="securepass123")
except ValueError as e:
    print(e)  # Field 'username' must be at least 3 characters. Got: 2
```

### ChoiceValidator

```python
from mydborm import StrField, ChoiceValidator

STATUSES  = ["pending", "processing", "shipped", "delivered", "cancelled"]
SIZES     = ["XS", "S", "M", "L", "XL", "XXL"]
PRIORITIES = ["low", "medium", "high", "critical"]

class Order(BaseModel):
    __tablename__ = "orders"
    id       = IntField(primary_key=True)
    status   = StrField(max_length=20, nullable=False,
                        validators=[ChoiceValidator(STATUSES)])
    priority = StrField(max_length=10, nullable=False, default="medium",
                        validators=[ChoiceValidator(PRIORITIES)])

Order.create(status="pending", priority="high")  # OK

try:
    Order.create(status="unknown")
except ValueError as e:
    print(e)
    # Field 'status' must be one of ['pending', 'processing', 'shipped',
    #   'delivered', 'cancelled']. Got: 'unknown'
```

### Combining validators

```python
from mydborm import StrField, MinLengthValidator, RegexValidator, ChoiceValidator

class UserAccount(BaseModel):
    __tablename__ = "user_accounts"
    id       = IntField(primary_key=True)
    username = StrField(max_length=30, nullable=False, validators=[
        MinLengthValidator(3),
        RegexValidator(r'^[a-zA-Z0-9_]+$',
                       message="Username may only contain letters, numbers and underscore"),
    ])
    role = StrField(max_length=20, nullable=False, validators=[
        ChoiceValidator(["admin", "editor", "viewer", "guest"]),
    ])

# All validators run in order — first failure stops
try:
    UserAccount.create(username="ab", role="admin")  # too short
except ValueError as e:
    print(e)  # Field 'username' must be at least 3 characters

try:
    UserAccount.create(username="alice smith", role="admin")  # space not allowed
except ValueError as e:
    print(e)  # Username may only contain letters, numbers and underscore
```

### Cross-field validation with __validators__

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
'''

files["docs/guide/exceptions.md"] = r'''# Exceptions

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
'''

for path, content in files.items():
    full_path = os.path.join(BASE, path.replace("/", os.sep))
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    lines = content.count("\n")
    print(f"Written: {path} ({lines} lines)")

print("\nDone! Run: mkdocs serve")