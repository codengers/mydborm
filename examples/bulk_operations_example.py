# =============================================================================
# File        : examples/bulk_operations_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Bulk operations demo — chunked_bulk_create/update/delete
#               for inserting/updating/deleting many rows in safe
#               batches with retry and progress callbacks, plus
#               bulk_upsert() for "insert or update" in one call.
# =============================================================================

from mydborm import (
    db, BaseModel, IntField, StrField, FloatField,
    chunked_bulk_create, chunked_bulk_update, chunked_bulk_delete,
)

db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3307,
    user     = "root",
    password = "root",
    database = "testdb",
)


class BulkProduct(BaseModel):
    __tablename__ = "bulk_products"
    id    = IntField(primary_key=True)
    sku   = StrField(max_length=50, nullable=False, unique=True)
    name  = StrField(max_length=100, nullable=False)
    price = FloatField(nullable=False)


def main():
    print("=" * 60)
    print("  mydborm — Bulk operations demo")
    print("=" * 60)

    BulkProduct.create_table()
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM bulk_products")

    # ------------------------------------------------------------------ #
    #  Why bulk instead of a loop?                                        #
    # ------------------------------------------------------------------ #
    # Calling Product.create(...) 1,000 times in a Python for-loop sends
    # 1,000 separate INSERT statements — one network round-trip each.
    # chunked_bulk_create() instead batches them into a handful of
    # multi-row INSERT statements ("chunks"), which is dramatically
    # faster for anything beyond a few dozen rows.

    print("\n── chunked_bulk_create() with a progress callback ──────")

    records = [
        {"sku": f"SKU-{i:04d}", "name": f"Product {i}", "price": 9.99 + i}
        for i in range(1, 251)
    ]

    def on_progress(done, total):
        if done == total or done % 100 == 0:
            print(f"    ...{done}/{total} rows inserted")

    # chunk_size=100 means each INSERT statement carries 100 rows, so
    # 250 records take 3 round-trips instead of 250. retries=2 means
    # if a chunk fails for a transient reason, it's retried up to twice
    # with a short backoff before giving up on that chunk.
    result = chunked_bulk_create(
        BulkProduct, records,
        chunk_size=100, retries=2, retry_delay=0.2,
        on_progress=on_progress,
    )
    print(result.summary())

    # ------------------------------------------------------------------ #
    #  chunked_bulk_update() — update many rows by primary key            #
    # ------------------------------------------------------------------ #
    print("\n── chunked_bulk_update() ────────────────────────────────")

    all_products = BulkProduct.all()
    updates = [
        {"id": p["id"], "price": round(p["price"] * 1.10, 2)}
        for p in all_products
    ]
    update_result = chunked_bulk_update(
        BulkProduct, updates, key="id", chunk_size=100,
    )
    print(update_result.summary())

    sample = BulkProduct.get(id=all_products[0]["id"])
    print(f"  Example: {sample['name']} now costs ${sample['price']}")

    # ------------------------------------------------------------------ #
    #  bulk_upsert() — insert new rows, update existing ones, in one call  #
    # ------------------------------------------------------------------ #
    print("\n── bulk_upsert() ────────────────────────────────────────")

    upsert_rows = [
        # SKU-0001 already exists — this updates its price instead of
        # failing on the duplicate "sku" value.
        {"sku": "SKU-0001", "name": "Product 1", "price": 5.00},
        # SKU-9999 is new — this inserts it.
        {"sku": "SKU-9999", "name": "Brand New Product", "price": 19.99},
    ]
    affected = BulkProduct.bulk_upsert(
        upsert_rows, conflict_key="sku", update_fields=["name", "price"],
    )
    print(f"  Upsert affected {affected} row(s)")
    print(f"  SKU-0001 price is now: "
          f"${BulkProduct.query().where('sku', 'SKU-0001').first()['price']}")

    # ------------------------------------------------------------------ #
    #  chunked_bulk_delete() — delete many rows by id                     #
    # ------------------------------------------------------------------ #
    print("\n── chunked_bulk_delete() ────────────────────────────────")

    ids_to_delete = [p["id"] for p in BulkProduct.all()[:50]]
    delete_result = chunked_bulk_delete(
        BulkProduct, ids_to_delete, key="id", chunk_size=20,
    )
    print(delete_result.summary())
    print(f"  Remaining products: {BulkProduct.count()}")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM bulk_products")
        conn.cursor().execute("DROP TABLE bulk_products")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
