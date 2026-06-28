# =============================================================================
# File        : examples/yugabyte_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : YugabyteDB-specific demo — the exact same model code you'd
#               write for MySQL, just pointed at a different dialect, plus
#               the column types and primary-key tradeoffs that matter
#               once you're running on a distributed database instead of
#               a single MySQL server.
# =============================================================================

from mydborm import db, BaseModel, IntField, StrField, BoolField, JSONField

db.configure(
    dialect  = "yugabyte",
    host     = "127.0.0.1",
    port     = 5433,
    user     = "yugabyte",
    password = "yugabyte",
    database = "yugabyte",
)


class YBEvent(BaseModel):
    __tablename__ = "yb_events"
    id        = IntField(primary_key=True)
    name      = StrField(max_length=100, nullable=False)
    completed = BoolField(default=False)
    # JSONField becomes JSONB on YugabyteDB — indexable, queryable JSON,
    # not just an opaque text blob. Handy for semi-structured event
    # payloads you don't want to flatten into columns up front.
    payload   = JSONField(nullable=True)


def main():
    print("=" * 60)
    print("  mydborm — YugabyteDB demo")
    print("=" * 60)

    YBEvent.create_table()
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM yb_events")

    # ------------------------------------------------------------------ #
    #  Same model code, different dialect                                 #
    # ------------------------------------------------------------------ #
    print("\n── Same code as MySQL — just a different dialect ───────")

    # Nothing about YBEvent itself mentions YugabyteDB. If you swapped
    # db.configure(dialect="mysql", port=3306, ...) at the top of this
    # file and reran it, this exact model and these exact calls would
    # work unchanged against MySQL instead. That portability is the
    # whole point of mydborm's dialect system.
    eid = YBEvent.create(
        name="signup",
        completed=True,
        payload={"user_id": 42, "plan": "pro", "source": "ad_campaign_7"},
    )
    event = YBEvent.get(id=eid)
    print(f"  Created event: {event['name']} (id={eid})")
    print(f"  JSONB payload round-trips as a Python dict: {event['payload']}")

    # ------------------------------------------------------------------ #
    #  What's actually different under the hood                          #
    # ------------------------------------------------------------------ #
    print("\n── What the dialect changes for you automatically ──────")

    print(f"  BoolField column type here:  "
          f"{type(event['completed']).__name__} "
          f"(BOOLEAN in Postgres/YugabyteDB, vs TINYINT(1) in MySQL)")
    print("  Identifiers are double-quoted in the generated SQL here "
          "(MySQL uses backticks) — you never write the quoting yourself.")

    # ------------------------------------------------------------------ #
    #  Primary keys on a distributed database                            #
    # ------------------------------------------------------------------ #
    print("\n── A YugabyteDB-specific tradeoff: SERIAL vs UUID PKs ──")

    # mydborm's default YugabyteDB primary key is SERIAL — a simple
    # auto-incrementing integer, same idea as MySQL's AUTO_INCREMENT.
    # That's fine for small/medium tables and keeps this demo simple.
    # But YugabyteDB scales by splitting a table's rows across multiple
    # nodes ("tablets") by primary key range. A SERIAL key means newly
    # inserted rows all land in the same numeric range — and therefore
    # the same tablet — at any given moment, creating a write hotspot
    # exactly when you're inserting the most. For high-write tables at
    # real scale, a random or hashed key (e.g. a UUID) spreads inserts
    # across tablets evenly instead. This is a YugabyteDB-only concern —
    # it doesn't apply when targeting plain MySQL.
    print("  Fine for this demo: SERIAL (auto-incrementing) primary key.")
    print("  For a high-write table at real scale: prefer a UUID or other")
    print("  evenly-distributed key so inserts spread across tablets")
    print("  instead of hammering whichever one currently holds the")
    print("  highest id range.")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM yb_events")
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE yb_events")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
