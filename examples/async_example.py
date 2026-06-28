# =============================================================================
# File        : examples/async_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Async demo — AsyncBaseModel for use with FastAPI and
#               other asyncio-based frameworks. The point of the async
#               version isn't speed per query, it's that a slow database
#               call doesn't block your whole server from handling other
#               requests while it waits. Requires: pip install mydborm[async]
# =============================================================================

import asyncio
import time

from mydborm.async_db import async_db, AsyncBaseModel
from mydborm.fields import IntField, StrField, FloatField


class AsyncProduct(AsyncBaseModel):
    __tablename__ = "async_products"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)
    price = FloatField(nullable=False)


async def main():
    print("=" * 60)
    print("  mydborm — Async demo")
    print("=" * 60)

    await async_db.configure(
        dialect  = "mysql",
        host     = "127.0.0.1",
        port     = 3307,
        user     = "root",
        password = "root",
        database = "testdb",
    )

    await AsyncProduct.create_table()
    await async_db.execute("DELETE FROM async_products")

    # ------------------------------------------------------------------ #
    #  Basic async CRUD — same shape as the sync API, with await added    #
    # ------------------------------------------------------------------ #
    print("\n── Async CRUD ───────────────────────────────────────────")

    pid = await AsyncProduct.create(name="Widget", price=9.99)
    product = await AsyncProduct.get(id=pid)
    print(f"  Created and fetched: {product['name']} (${product['price']})")

    await AsyncProduct.update({"price": 12.99}, id=pid)
    updated = await AsyncProduct.get(id=pid)
    print(f"  Updated price: ${updated['price']}")

    # ------------------------------------------------------------------ #
    #  Why bother with async? Run several queries concurrently            #
    # ------------------------------------------------------------------ #
    print("\n── Running queries concurrently ─────────────────────────")

    # In a sync web app, three database calls in a row mean each request
    # waits for the one before it to finish. Here, asyncio.gather() lets
    # the database driver send all three queries without each one
    # blocking the others while it waits on the network — useful when a
    # single request needs several independent pieces of data.
    names = ["Gadget", "Gizmo", "Doohickey"]
    start = time.perf_counter()
    new_ids = await asyncio.gather(*[
        AsyncProduct.create(name=name, price=19.99) for name in names
    ])
    elapsed = time.perf_counter() - start
    print(f"  Created {len(new_ids)} products concurrently in {elapsed:.3f}s")

    all_products = await AsyncProduct.all()
    print(f"  Total products now: {len(all_products)}")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    await async_db.execute("DELETE FROM async_products")
    await AsyncProduct.drop_table()
    await async_db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    asyncio.run(main())
