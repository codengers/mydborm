# Quickstart

This walks through the core workflow you'll use in almost every
mydborm project: define a model, create its table, then create, read,
update, and delete (CRUD) rows. If you haven't installed mydborm or
connected to a database yet, do that first in
[Installation](installation.md).

## 1. Define a model

A **model** is a Python class that represents one database table. Each
class attribute is a `Field`, and each `Field` becomes one column:

```python
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField

db.configure(dialect="mysql", host="127.0.0.1", port=3306,
             user="root", password="root", database="mydb")

class Product(BaseModel):
    __tablename__ = "products"
    id       = IntField(primary_key=True)
    name     = StrField(max_length=100, nullable=False)
    price    = FloatField(nullable=False)
    active   = BoolField(default=True)
```

A couple of things to notice:

- `__tablename__` is the actual table name in the database. If you
  leave it out, mydborm guesses one from the class name.
- `IntField(primary_key=True)` marks `id` as the table's primary key —
  the unique identifier mydborm uses to look up a specific row.
- `nullable=False` means "this column is required" — trying to save a
  `Product` without a `name` or `price` raises an error before any SQL
  is even sent to the database.
- `default=True` means `active` is automatically `True` if you don't
  specify it.

This class definition doesn't touch the database yet — it's just a
description. The next step actually creates the table.

## 2. Create the table

```python
Product.create_table()
```

This sends a `CREATE TABLE` statement built from your field
definitions. You only need to run it once (or again later if you add
new fields — see [Migrations](migrations.md) for handling schema
changes over time).

## 3. CRUD: create, read, update, delete

With the table in place, you can work with `Product` rows as Python
objects instead of writing SQL:

```python
# Create — returns the new row's id
pid = Product.create(name="Widget", price=9.99, active=True)

# Read
product  = Product.get(id=pid)       # a single row, by primary key
products = Product.all()             # every row in the table
active   = Product.filter(active=True)  # rows matching a simple condition

# Update — takes the new values, then which row(s) to apply them to
Product.update({"price": 12.99}, id=pid)

# Delete
Product.delete(id=pid)
```

`Product.get(id=pid)` raises an error if no row matches, while
`Product.filter(...)` returns an empty list instead of raising — keep
that difference in mind when deciding which one to use.

## 4. Filtering and ordering with the query builder

`.filter()` is fine for simple lookups, but real queries usually need
more — combining conditions, sorting, paging. That's what the
**query builder** is for: it lets you build up a query piece by piece,
then run it with `.all()`:

```python
results = (Product.query()
                  .where("active", True)
                  .where("price__lt", 20.0)   # price less than 20
                  .order_by("name")
                  .limit(10)
                  .all())
```

Each `.where(...)` call adds another condition (they're combined with
`AND`). See [Query Builder](query_builder.md) for the full set of
available operators, joins, and aggregates.

## 5. Keeping the database schema in sync

As your model changes over time — adding a column, renaming one — your
database table needs to change too. mydborm can compare your model
against the live table and generate the SQL for you:

```python
from mydborm.migrations import migrate, generate

# Compare Product's fields against the database and apply any
# differences (e.g. add a missing column) right away
migrate(Product, description="create products table")

# Or write the SQL to a file instead of applying it immediately,
# so you can review it first or commit it to version control
generate(Product, output_dir="migrations/")
```

See [Migrations](migrations.md) for the full workflow, including
rollbacks and tracking which migrations have already been applied.

## Where to go next

- [Models & CRUD](models.md) — more on defining models and the full
  CRUD API
- [Fields](fields.md) — every available field type, including
  passwords and encrypted columns
- [Query Builder](query_builder.md) — joins, grouping, subqueries
- [Relationships](relationships.md) — linking models together
  (`has_many`, `belongs_to`, `many_to_many`)
