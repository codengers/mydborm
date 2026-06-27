# Migrations

> This page is about keeping **one** database's schema in sync with your
> Python model definitions as they change over time. If you're instead
> trying to copy data and tables *between two different databases* (say,
> moving from MySQL to YugabyteDB), that's a separate feature — see
> [Database Migration](db_migration.md).

When you add a field to a model, rename one, or change a type, your model
class and your actual database table drift out of sync — the table doesn't
automatically grow a new column just because you added one to the Python
class. mydborm's **migrations** module compares your model's field
definitions against what the live database table actually looks like, and
generates the `CREATE TABLE` or `ALTER TABLE` statements needed to bring
the table in line with the model.

## Apply a migration

`migrate()` does the comparison and applies whatever changes are needed —
creating the table if it doesn't exist yet, or adding/dropping columns if
it does — in one step:

```python
from mydborm.migrations import migrate, migration_status, rollback

migrate(User, description="create users table")
```

`description` is just a human-readable label stored alongside the
migration record — it doesn't affect what SQL gets run. Behind the scenes,
mydborm records every migration it applies in a tracking table
(`_mydborm_migrations`) along with a checksum of the SQL, so running
`migrate(User, ...)` again later won't reapply a migration that's already
been applied.

## Check status

Since every applied migration is recorded, you can list them — useful for
checking what's already been run against a given database, especially
when several developers or environments might apply migrations
independently:

```python
for m in migration_status():
    print(m["version"], m["description"], m["applied_at"])
```

Each entry also includes whether it's since been rolled back.

## Rollback

`rollback()` undoes a migration for a model — but be aware of what "undo"
actually means here: it **drops the table entirely**, deleting all of its
data, and then marks the migration as rolled back in the tracking table.
There's no automatic way to get the data back afterward, so only use this
in development, or when you're certain the table's contents are
disposable:

```python
rollback(User)
```

If you need to preserve data while changing a table's structure, write
and review a migration file manually (see below) instead of relying on
`rollback()`.

## Auto-generate SQL files

Applying a migration immediately with `migrate()` is convenient, but
sometimes you'd rather see the SQL first — to review it, tweak it, or commit
it to version control so your team has a record of every schema change.
`generate()` writes the migration SQL to a numbered file instead of running
it right away:

```python
from mydborm.migrations import generate, apply_migration_file

result = generate(User, output_dir="migrations/")
print(result["file"])  # migrations/0001_user.sql

apply_migration_file("migrations/0001_user.sql")
```

`generate()` figures out the next version number automatically by counting
the `.sql` files already in `output_dir`, so files end up named
`0001_*.sql`, `0002_*.sql`, and so on. Once you're happy with a generated
file (or after editing it), `apply_migration_file()` runs the SQL statements
it contains against the database. You can also pass `apply=True` to
`generate()` to skip the separate step and apply it immediately after
writing the file.

## CLI

All of the above is also available from the terminal, without writing any
Python — see [CLI](cli.md) for the full list of commands and options:

```bash
mydborm migrate --dialect mysql --status
mydborm generate --model myapp.models.User --output migrations/
mydborm generate --model myapp.models.User --apply
```
