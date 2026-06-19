# Quickstart

## 1. Define a model

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

## 2. Create table

```python
Product.create_table()
```

## 3. CRUD

```python
# Create
pid = Product.create(name="Widget", price=9.99, active=True)

# Read
product  = Product.get(id=pid)
products = Product.all()
active   = Product.filter(active=True)

# Update
Product.update({"price": 12.99}, id=pid)

# Delete
Product.delete(id=pid)
```

## 4. Query builder

```python
results = (Product.query()
                  .where("active", True)
                  .where("price__lt", 20.0)
                  .order_by("name")
                  .limit(10)
                  .all())
```

## 5. Migrations

```python
from mydborm.migrations import migrate, generate

# Apply migration
migrate(Product, description="create products table")

# Generate SQL file
generate(Product, output_dir="migrations/")
```