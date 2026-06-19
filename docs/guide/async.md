# Async support

## Configure

```python
import asyncio
from mydborm.async_db import async_db, AsyncBaseModel
from mydborm.fields import IntField, StrField

class AsyncUser(AsyncBaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)

async def main():
    await async_db.configure(
        dialect  = "mysql",
        host     = "127.0.0.1",
        port     = 3306,
        user     = "root",
        password = "root",
        database = "mydb",
    )
    await AsyncUser.create_table()
    uid  = await AsyncUser.create(username="alice")
    user = await AsyncUser.get(id=uid)
    all  = await AsyncUser.all()
    await async_db.close()

asyncio.run(main())
```

## YugabyteDB async

```python
await async_db.configure(
    dialect  = "yugabyte",
    host     = "127.0.0.1",
    port     = 5433,
    user     = "yugabyte",
    password = "yugabyte",
    database = "yugabyte",
)
```
