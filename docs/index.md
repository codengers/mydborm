# mydborm

[![PyPI version](https://badge.fury.io/py/mydborm.svg)](https://pypi.org/project/mydborm/)
[![Python](https://img.shields.io/pypi/pyversions/mydborm)](https://pypi.org/project/mydborm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/codengers/mydborm/actions/workflows/ci.yml/badge.svg)](https://github.com/codengers/mydborm/actions)
[![Coverage](https://img.shields.io/badge/coverage-88%25-brightgreen)](https://github.com/codengers/mydborm)

**mydborm** is a production-grade lightweight Python ORM for **MySQL 8+** and **YugabyteDB (YSQL)**.

Zero bloat. Declarative models. Full CRUD. 29 field types. Bulk ops. Async. Migrations. Security. CLI.

---

## Install

```bash
pip install mydborm                      # core ORM
pip install mydborm[cli]                 # + CLI commands
pip install mydborm[async]               # + async support
pip install mydborm[security]            # + bcrypt + AES encryption
pip install mydborm[dev,cli,async,security]  # everything
```

---

## 60-second quickstart

```python
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm import PasswordField, EmailValidator, RangeValidator

db.configure(
    dialect  = "mysql",       # or "yugabyte"
    host     = "127.0.0.1",
    port     = 3306,
    user     = "root",
    password = "yourpassword",
    database = "mydb",
    charset  = "utf8mb4",
)

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50,  nullable=False, unique=True)
    email    = StrField(max_length=255, nullable=False,
                        validators=[EmailValidator()])
    age      = IntField(nullable=True,
                        validators=[RangeValidator(min_val=13, max_val=120)])
    password = PasswordField(nullable=False)
    active   = BoolField(default=True)

User.create_table()

# Create — password auto-hashed, email validated
uid = User.create(
    username = "alice",
    email    = "alice@example.com",
    age      = 28,
    password = "mysecretpass",
)

# Login verification
user = User.get(id=uid)
if PasswordField.verify("mysecretpass", user["password"]):
    print("Login successful!")

# Query
active_users = (User.query()
                    .where("active", True)
                    .order_by("username")
                    .limit(10)
                    .all())
```

---

## Features

| Feature | Status | Since |
|---|---|---|
| Declarative models | ✅ | v0.2 |
| 29 field types (10 core + 17 extended + 2 security) | ✅ | v1.2 |
| Full CRUD — create, get, all, filter, update, delete | ✅ | v0.2 |
| QueryBuilder — where, join, group_by, having, subquery | ✅ | v0.3/v0.8 |
| Relationships — has_many, belongs_to, many_to_many | ✅ | v0.3 |
| Lazy + eager loading | ✅ | v0.6 |
| Session — identity map, change tracking, unit of work | ✅ | v0.6 |
| Bulk operations with chunking + retry + BulkResult | ✅ | v0.4/v0.5 |
| Transactions + savepoints + nested transactions | ✅ | v0.5 |
| Schema migrations + auto-generation | ✅ | v0.2/v0.8 |
| Custom validators — email, url, regex, range, length, choice | ✅ | v0.7 |
| PasswordField — bcrypt one-way hashing | ✅ | v1.2 |
| EncryptedField — AES two-way encryption | ✅ | v1.2 |
| Async support — aiomysql + aiopg | ✅ | v0.4 |
| Connection pooling + ping + reconnect | ✅ | v0.4 |
| MySQL 8+ + YugabyteDB (YSQL) dialect support | ✅ | v0.4 |
| UTF-8 / unicode support | ✅ | v0.5 |
| Rich CLI — 7 commands | ✅ | v0.2 |
| 658 tests — 88% coverage | ✅ | v1.2 |
| Python 3.9, 3.10, 3.11, 3.12 | ✅ | v0.3 |

---

## Field types

### Core fields (v0.2+)

| Field | MySQL | YugabyteDB |
|---|---|---|
| `IntField` | `INT` | `INTEGER` |
| `StrField(max_length)` | `VARCHAR(n)` | `VARCHAR(n)` |
| `TextField` | `TEXT` | `TEXT` |
| `BoolField` | `TINYINT(1)` | `BOOLEAN` |
| `FloatField` | `FLOAT` | `FLOAT` |
| `DecimalField(p,s)` | `DECIMAL(p,s)` | `DECIMAL(p,s)` |
| `DateField` | `DATE` | `DATE` |
| `DateTimeField` | `DATETIME` | `TIMESTAMP` |
| `JSONField` | `JSON` | `JSONB` |
| `ForeignKeyField` | `INT` | `INTEGER` |

### Extended fields (v1.1+)

| Field | MySQL | YugabyteDB |
|---|---|---|
| `TinyIntField` | `TINYINT` | `SMALLINT` |
| `SmallIntField` | `SMALLINT` | `SMALLINT` |
| `BigIntField` | `BIGINT` | `BIGINT` |
| `UnsignedBigIntField` | `BIGINT UNSIGNED` | `NUMERIC(20)` |
| `DoubleField` | `DOUBLE` | `DOUBLE PRECISION` |
| `BitField(n)` | `BIT(n)` | `BIT(n)` |
| `CharField(n)` | `CHAR(n)` | `CHAR(n)` |
| `TinyTextField` | `TINYTEXT` | `TEXT` |
| `MediumTextField` | `MEDIUMTEXT` | `TEXT` |
| `LongTextField` | `LONGTEXT` | `TEXT` |
| `BinaryField(n)` | `BINARY(n)` | `BYTEA` |
| `VarBinaryField(n)` | `VARBINARY(n)` | `BYTEA` |
| `BlobField` | `BLOB` | `BYTEA` |
| `TimeField` | `TIME` | `TIME` |
| `TimestampField` | `TIMESTAMP` | `TIMESTAMPTZ` |
| `EnumField(choices)` | `ENUM(...)` | `VARCHAR(n)` |
| `SetField(choices)` | `SET(...)` | `TEXT[]` |

### Security fields (v1.2+)

| Field | Storage | Algorithm |
|---|---|---|
| `PasswordField` | `VARCHAR(255)` | bcrypt |
| `EncryptedField` | `TEXT` | AES-128-CBC (Fernet) |

---

## Why mydborm?

| | mydborm | SQLAlchemy | Peewee |
|---|---|---|---|
| Install size | **47 KB** | 3 MB | 800 KB |
| MySQL + YugabyteDB | **✅** | ✅ | ✅ |
| Async built-in | **✅** | needs ext | ❌ |
| CLI included | **✅** | ❌ | ❌ |
| Password hashing | **✅** | ❌ | ❌ |
| AES encryption | **✅** | ❌ | ❌ |
| Bulk insert speed | **Fastest** | Medium | Medium |
| Session pattern | **✅** | ✅ | ❌ |
