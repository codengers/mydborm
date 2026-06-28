# =============================================================================
# File        : examples/data_engineering_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : A data-engineering-flavored demo — ingesting raw,
#               messy records (extract/transform/load), loading them
#               idempotently so re-running the same batch never creates
#               duplicates, and running a downstream aggregation query.
#               Targets YugabyteDB: a common reason data engineers reach
#               for it over plain MySQL is that it shards a table's rows
#               across multiple nodes, so write/read throughput scales
#               horizontally as you add nodes — useful once a pipeline
#               outgrows what a single MySQL server can take.
# =============================================================================

from mydborm import db, BaseModel, IntField, StrField, FloatField, JSONField

db.configure(
    dialect  = "yugabyte",
    host     = "127.0.0.1",
    port     = 5433,
    user     = "yugabyte",
    password = "yugabyte",
    database = "yugabyte",
)

# A long-running pipeline process — not a short script — is exactly the
# case connection pooling is for: instead of opening a fresh connection
# for every batch, a pool keeps a handful open and reuses them.
db.configure_pool(pool_size=5, max_overflow=10)


class RawOrderEvent(BaseModel):
    __tablename__ = "de_order_events"
    id          = IntField(primary_key=True)
    # The natural/business key from the source system — what makes a
    # row "the same record" across pipeline re-runs, as opposed to our
    # own auto-incrementing id, which is meaningless to the source.
    order_id    = StrField(max_length=50, nullable=False, unique=True)
    customer    = StrField(max_length=100, nullable=False)
    amount      = FloatField(nullable=False)
    # Keep the original raw payload around as well as the columns we
    # actually query on. Common warehouse pattern: if the source schema
    # adds a field later, it's already sitting in here, even though
    # nothing was querying it yet when the row was first loaded.
    raw_payload = JSONField(nullable=True)


def extract_batch():
    """
    Stand-in for "pull the next batch from an API / message queue / CSV
    drop." Deliberately messy, the way real upstream data usually is:
    a duplicate order_id (the same event delivered twice) and a stray
    whitespace in a customer name.
    """
    return [
        {"order_id": "ORD-1001", "customer": "Alice",  "amount": 49.99,
         "source": "web", "promo_code": None},
        {"order_id": "ORD-1002", "customer": "Bob",    "amount": 19.50,
         "source": "mobile", "promo_code": "SAVE10"},
        {"order_id": "ORD-1003", "customer": " Carol", "amount": 99.00,
         "source": "web", "promo_code": None},
        {"order_id": "ORD-1002", "customer": "Bob",    "amount": 19.50,
         "source": "mobile", "promo_code": "SAVE10"},  # duplicate delivery
    ]


def transform(raw_records):
    """Clean up what the extract step handed us, keep the original
    payload alongside the cleaned columns."""
    cleaned = []
    seen_order_ids = set()
    for r in raw_records:
        if r["order_id"] in seen_order_ids:
            continue  # drop the duplicate delivery
        seen_order_ids.add(r["order_id"])
        cleaned.append({
            "order_id":    r["order_id"],
            "customer":    r["customer"].strip(),
            "amount":      r["amount"],
            "raw_payload": r,
        })
    return cleaned


def load_batch(records):
    """
    Load with bulk_upsert(), keyed on the business key (order_id), not
    our own auto-incrementing id. That's what makes this idempotent:
    running the exact same batch through the pipeline twice updates the
    existing rows in place instead of inserting duplicates.
    """
    return RawOrderEvent.bulk_upsert(
        records,
        conflict_key   = "order_id",
        update_fields  = ["customer", "amount", "raw_payload"],
    )


def main():
    print("=" * 60)
    print("  mydborm — Data engineering (ETL) demo")
    print("=" * 60)

    RawOrderEvent.create_table()
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM de_order_events")

    # ------------------------------------------------------------------ #
    #  First pipeline run                                                 #
    # ------------------------------------------------------------------ #
    print("\n── Extract → transform → load (first run) ──────────────")

    raw = extract_batch()
    print(f"  Extracted {len(raw)} raw record(s) (includes 1 duplicate)")

    cleaned = transform(raw)
    print(f"  After transform/dedupe: {len(cleaned)} record(s)")

    load_batch(cleaned)
    print(f"  Rows in table after load: {RawOrderEvent.count()}")

    # ------------------------------------------------------------------ #
    #  Re-running the same batch must NOT create duplicates               #
    # ------------------------------------------------------------------ #
    print("\n── Re-running the exact same batch ──────────────────────")

    # This is the property that matters most in a real pipeline: if a
    # job retries after a partial failure, or the same file gets picked
    # up twice, you must not end up with duplicate rows.
    load_batch(transform(extract_batch()))
    print(f"  Rows in table after re-run: {RawOrderEvent.count()} "
          f"(unchanged — same order_ids, so upsert updated, not inserted)")

    # ------------------------------------------------------------------ #
    #  A typical downstream reporting query                               #
    # ------------------------------------------------------------------ #
    print("\n── Downstream aggregation ───────────────────────────────")

    by_customer = (RawOrderEvent.query()
                                 .select("customer", "SUM(amount) as total")
                                 .group_by("customer")
                                 .having("SUM(amount) > %s", 20)
                                 .all())
    print("  Customers with over $20 in orders:")
    for row in by_customer:
        print(f"    {row['customer']}: ${row['total']}")

    # The raw payload is still there if you ever need a field that
    # wasn't promoted to its own column.
    sample = RawOrderEvent.query().where("order_id", "ORD-1002").first()
    print(f"\n  Raw payload for {sample['order_id']}: {sample['raw_payload']}")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM de_order_events")
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE de_order_events")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
