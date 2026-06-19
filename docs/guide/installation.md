# Installation

## Requirements

- Python 3.9+
- MySQL 8+ or YugabyteDB 2.x+

## Install

```bash
# Core ORM
pip install mydborm

# With CLI support
pip install mydborm[cli]

# With async support
pip install mydborm[async]

# All extras
pip install mydborm[dev,cli,async]
```

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
    ports:
      - "5433:5433"
```

```bash
docker compose up -d
```

## Configure

```python
from mydborm import db

# MySQL
db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3306,
    user     = "root",
    password = "yourpassword",
    database = "mydb",
    charset  = "utf8mb4",
)

# YugabyteDB
db.configure(
    dialect  = "yugabyte",
    host     = "127.0.0.1",
    port     = 5433,
    user     = "yugabyte",
    password = "yugabyte",
    database = "yugabyte",
)

# Via environment variable
import os
os.environ["DATABASE_URL"] = "mysql://root:password@localhost:3306/mydb"
db.from_env()
```