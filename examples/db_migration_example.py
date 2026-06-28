# =============================================================================
# File        : examples/db_migration_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Database-to-database migration demo — MigrationEngine
#               copies schema + data from one live database to another
#               (here, two databases on the same MySQL server, to keep
#               the example runnable without a second server). Also
#               shows ObjectMigrator, which builds the target table from
#               a BaseModel's own field definitions instead of the
#               source database's live schema.
# =============================================================================

from mydborm import db, BaseModel, IntField, StrField, BoolField
from mydborm import MigrationEngine, ObjectMigrator

SOURCE = dict(dialect="mysql", host="127.0.0.1", port=3307,
              user="root", password="root", database="migration_demo_source")
TARGET = dict(dialect="mysql", host="127.0.0.1", port=3307,
              user="root", password="root", database="migration_demo_target")


class DMUser(BaseModel):
    __tablename__ = "dm_users"
    id     = IntField(primary_key=True)
    name   = StrField(max_length=100, nullable=False)
    active = BoolField(default=True)


def main():
    print("=" * 60)
    print("  mydborm — Database migration demo")
    print("=" * 60)

    # Create the two demo databases and seed the source with some rows.
    db.configure(**{k: v for k, v in SOURCE.items() if k != "database"})
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS migration_demo_source")
        cur.execute("CREATE DATABASE IF NOT EXISTS migration_demo_target")
    db.close()

    db.configure(**SOURCE)
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS dm_users")
        cur.execute("""
            CREATE TABLE dm_users (
              id     INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
              name   VARCHAR(100) NOT NULL,
              active TINYINT(1) DEFAULT 1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cur.executemany(
            "INSERT INTO dm_users (name, active) VALUES (%s, %s)",
            [("Alice", 1), ("Bob", 0), ("Carol", 1)],
        )
    db.close()

    # Clear any leftover dm_users table in the target from an earlier run.
    db.configure(**TARGET)
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS dm_users")
    db.close()

    # ------------------------------------------------------------------ #
    #  MigrationEngine — migrate by introspecting the live source schema  #
    # ------------------------------------------------------------------ #
    print("\n── MigrationEngine: dry run ─────────────────────────────")

    engine = MigrationEngine(source=SOURCE, target=TARGET)

    # dry_run() shows you what WOULD happen — generated DDL and row
    # counts — without opening a write connection to the target at all.
    preview = engine.dry_run(tables=["dm_users"])
    for t in preview["tables"]:
        print(f"  Table '{t['table']}': {t['rows']} row(s), "
              f"{t['columns']} column(s)")
        print(f"  Generated DDL: {t['create_table_sql']}")

    print("\n── MigrationEngine: actually run it ─────────────────────")

    engine = MigrationEngine(source=SOURCE, target=TARGET)

    def on_progress(table, done, total):
        print(f"    {table}: {done}/{total} rows copied")

    result = engine.run(tables=["dm_users"], chunk_size=2, on_progress=on_progress)
    print(result.summary())

    # ------------------------------------------------------------------ #
    #  ObjectMigrator — build the target table from a model class         #
    # ------------------------------------------------------------------ #
    print("\n── ObjectMigrator: migrate by model class ──────────────")

    # Reset the target table so ObjectMigrator can create it fresh from
    # DMUser's own field definitions, rather than from the live source
    # schema MigrationEngine just copied above.
    db.configure(**TARGET)
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS dm_users")
    db.close()

    source_db = db.__class__()
    source_db.configure(**SOURCE)
    target_db = db.__class__()
    target_db.configure(**TARGET)

    migrator = ObjectMigrator(source_db, target_db)
    object_result = migrator.migrate_model(DMUser)
    print(f"  {object_result}")
    source_db.close()
    target_db.close()

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    db.configure(**SOURCE)
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS dm_users")
        conn.cursor().execute("DROP DATABASE migration_demo_source")
    db.close()
    db.configure(**TARGET)
    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS dm_users")
        conn.cursor().execute("DROP DATABASE migration_demo_target")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
