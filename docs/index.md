# mydborm

[![PyPI version](https://badge.fury.io/py/mydborm.svg)](https://pypi.org/project/mydborm/)
[![Python](https://img.shields.io/pypi/pyversions/mydborm)](https://pypi.org/project/mydborm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/codengers/mydborm/actions/workflows/ci.yml/badge.svg)](https://github.com/codengers/mydborm/actions)

**mydborm** is a production-grade lightweight Python ORM for **MySQL 8+** and **YugabyteDB (YSQL)**.

Zero bloat. Declarative models. Full CRUD. Bulk ops. Async. Migrations. CLI included.

## Install

```bash
pip install mydborm
pip install mydborm[cli]    # CLI support
pip install mydborm[async]  # Async support
```

## Quickstart

```python
from mydborm import db, BaseModel, IntField, StrField, BoolField

db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3306,
    user     = "root",
    password = "yourpassword",
    database = "mydb",
)

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    active   = BoolField(default=True)

User.create_table()

uid  = User.create(username="alice", active=True)
user = User.get(id=uid)
print(user.username)  # alice

users = User.query().where("active", True).order_by("username").all()
```

## Features

| Feature | Status |
|---|---|
| Declarative models with 11 field types | ✅ |
| Full CRUD — create, get, all, filter, update, delete | ✅ |
| QueryBuilder — where, join, group_by, having, subquery | ✅ |
| Relationships — has_many, belongs_to, many_to_many | ✅ |
| Lazy + eager loading | ✅ |
| Session — identity map, change tracking, unit of work | ✅ |
| Bulk operations with chunking + retry | ✅ |
| Transactions + savepoints | ✅ |
| Schema migrations + auto-generation | ✅ |
| Custom validators | ✅ |
| Async support — aiomysql + aiopg | ✅ |
| Connection pooling | ✅ |
| MySQL + YugabyteDB dialect support | ✅ |
| UTF-8 / unicode support | ✅ |
| Rich CLI — 7 commands | ✅ |
| 561 tests — 88% coverage | ✅ |