# mydborm

[![PyPI version](https://badge.fury.io/py/mydborm.svg)](https://pypi.org/project/mydborm/)
[![Python](https://img.shields.io/pypi/pyversions/mydborm)](https://pypi.org/project/mydborm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**mydborm** is a lightweight, developer-friendly ORM for **MySQL 8+** and **YugabyteDB (YSQL)**.  
Zero bloat. Declarative models. Full CRUD. Schema migrations. CLI included.

---

## Features

- Declarative model definitions with field validation
- Full CRUD — `create`, `get`, `all`, `filter`, `update`, `delete`, `count`, `exists`
- Schema migration engine with history tracking
- Dual database support — MySQL and YugabyteDB
- Thread-safe connection manager with context manager support
- `DATABASE_URL` environment variable support
- Rich CLI — `ping`, `inspect`, `tables`, `migrate`
- Zero mandatory dependencies beyond database drivers
- Python 3.8+ compatible, platform independent

---

## Installation

```bash
pip install mydborm
```

With CLI support:

```bash
pip install mydborm[cli]
```

---

## Quickstart

### 1. Configure connection

```python
from mydborm import db

# Direct config
db.configure(
    dialect  = "mysql",       # or "yugabyte"
    host     = "127.0.0.1",
    port     = 3306,
    user     = "root",
    password = "yourpassword",
    database = "mydb",
)

# Or via environment variable
# export DATABASE_URL="mysql://root:password@localhost:3306/mydb"
db.from_env()
```

---

### 2. Define models

```python
from mydborm import BaseModel, IntField, StrField, BoolField, FloatField

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False, unique=True)
    active   = BoolField(default=True)

class Product(BaseModel):
    __tablename__ = "products"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=100, nullable=False)
    price  = FloatField(nullable=False)
    active = BoolField(default=True)
```

---

### 3. Run migrations

```python
from mydborm.migrations import migrate, migration_status

migrate(User,    description="Create users table")
migrate(Product, description="Create products table")

for m in migration_status():
    print(m["description"], "→", "Applied" if not m["rolled_back"] else "Rolled back")
```

---

### 4. CRUD operations

```python
# Create
uid = User.create(username="alice", email="alice@example.com", active=True)

# Read
user  = User.get(id=uid)
users = User.all()
devs  = User.filter(active=True)

# Update
User.update({"active": False}, id=uid)

# Delete
User.delete(id=uid)

# Aggregate
count  = User.count()
exists = User.exists(email="alice@example.com")
```

---

## Field types

| Field           | SQL Type (MySQL)   | SQL Type (YugabyteDB) |
|-----------------|--------------------|-----------------------|
| `IntField`      | `INT`              | `INTEGER`             |
| `StrField`      | `VARCHAR(n)`       | `VARCHAR(n)`          |
| `TextField`     | `TEXT`             | `TEXT`                |
| `BoolField`     | `TINYINT(1)`       | `BOOLEAN`             |
| `FloatField`    | `FLOAT`            | `FLOAT`               |
| `DecimalField`  | `DECIMAL(p,s)`     | `DECIMAL(p,s)`        |
| `DateField`     | `DATE`             | `DATE`                |
| `DateTimeField` | `DATETIME`         | `TIMESTAMP`           |
| `JSONField`     | `JSON`             | `JSONB`               |
| `ForeignKeyField`| `INT`             | `INTEGER`             |

---

## CLI commands

```bash
# Show version
mydborm version

# Test connectivity
mydborm ping --dialect mysql --host 127.0.0.1 --port 3306 --password root

# List all tables
mydborm tables --dialect mysql --port 3306 --password root

# Inspect schema
mydborm inspect --dialect mysql --port 3306 --password root

# Run migration for a model
mydborm migrate --dialect mysql --port 3306 --password root \
  --model myapp.models.User

# Show migration history
mydborm migrate --status --dialect mysql --port 3306 --password root

# Rollback last migration
mydborm migrate --rollback --dialect mysql --port 3306 --password root \
  --model myapp.models.User
```

---

## YugabyteDB support

```python
db.configure(
    dialect  = "yugabyte",
    host     = "127.0.0.1",
    port     = 5433,
    user     = "yugabyte",
    password = "yugabyte",
    database = "yugabyte",
)
```

mydborm automatically uses YSQL-compatible SQL:
- Double-quoted identifiers
- `SERIAL` primary keys
- Native `BOOLEAN`
- `JSONB` instead of `JSON`
- `RETURNING id` on INSERT

---

## Docker quickstart

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: mydb
    ports:
      - "3306:3306"

  yugabyte:
    image: yugabytedb/yugabyte:latest
    command: bash -c "bin/yugabyted start --daemon=false"
    ports:
      - "5433:5433"
```

```bash
docker compose up -d
```

---

## Project structure

```
mydborm/
├── mydborm/
│   ├── __init__.py       # Public API
│   ├── db.py             # Connection manager
│   ├── fields.py         # Field types
│   ├── model.py          # BaseModel + CRUD
│   ├── migrations.py     # Schema migration engine
│   ├── cli.py            # CLI commands
│   └── dialects/
│       ├── mysql.py      # MySQL SQL generation
│       └── yugabyte.py   # YugabyteDB SQL generation
├── tests/                # pytest test suite
├── examples/             # Usage examples
└── pyproject.toml
```

---

## Running tests

```bash
pip install mydborm[dev]
pytest
```

---

## Author

**Atikrant Upadhye**  
[PyPI](https://pypi.org/project/mydborm/) · [GitHub](https://github.com/codengers/mydborm)

---

## License

MIT License — see [LICENSE](LICENSE) for details.