# CLI

Everything covered elsewhere in these docs is Python code you write inside
your application. The `mydborm` **command-line tool** is different — it's
a set of commands you run directly from your terminal, useful for checking
things or running one-off tasks (does my connection work? what tables exist?
let me apply this migration) without writing a throwaway Python script
every time.

It's an optional extra, so install it with:

```bash
pip install mydborm[cli]
```

That gives you a `mydborm` command with eight subcommands, covered below.
Every command that talks to a database accepts the same family of
connection options — `--dialect`, `--host`, `--port`, `--user`,
`--password`, `--database` — so you can point any of them at MySQL,
YugabyteDB, or PostgreSQL. Run `mydborm <command> --help` at any time to
see a command's full option list and defaults.

## version

Prints the installed mydborm version, the author, and which databases it
supports. No database connection needed — useful for sanity-checking what's
installed, especially when reporting a bug or checking you're on the
version you think you are:

```bash
mydborm version
```

## ping

Tests whether your connection settings actually work — it tries to connect
with the credentials you give it and, if successful, prints back the
server version, database name, and connected user. This is the first
command to reach for when something isn't working: it tells you whether
the problem is your connection details or something further down in your
application code.

```bash
mydborm ping --dialect mysql --host 127.0.0.1 --port 3306 --password root
```

If the connection fails, it prints the error and exits with a non-zero
status code (handy if you're scripting a health check around it).

## tables

Lists every table that exists in the connected database — a quick way to
confirm you're pointed at the database you think you are, or to see what's
already there before you start adding models:

```bash
mydborm tables --dialect mysql --database mydb --password root
```

## inspect

Goes one level deeper than `tables` — for every table in the database, it
prints the full column list: name, type, whether it's nullable, key
information, and default value. Useful when you want to see the database's
own idea of a table's structure, for example to compare it against what
your model class defines:

```bash
mydborm inspect --dialect mysql --database mydb --password root
```

## migrate

Applies or inspects [migrations](migrations.md) — the process of keeping a
database table's structure in sync with a Python model. Used without
`--model`, add `--status` to see a history of migrations already applied:

```bash
mydborm migrate --dialect mysql --database mydb --password root --status
```

Pass `--model` with the dotted Python import path to a model class to
compare that model against the live table and apply whatever's needed
(creating the table, or adding/dropping columns):

```bash
mydborm migrate --dialect mysql --database mydb --password root \
                --model myapp.models.User
```

Add `--rollback` alongside `--model` to undo a migration — keep in mind
this **drops the table and all of its data**, so only do this when you're
sure the data is disposable (see [Migrations](migrations.md#rollback) for
details).

## generate

Like `migrate --model`, but instead of applying changes immediately, it
writes the SQL to a numbered file in a `migrations/` directory — so you (or
a teammate) can review the SQL before it touches a real database, and so
the change is tracked in version control:

```bash
mydborm generate --dialect mysql --database mydb --password root \
                 --model myapp.models.User --output migrations/
```

Add `--apply` to also run the generated SQL immediately, instead of just
writing the file:

```bash
mydborm generate --dialect mysql --database mydb --password root \
                 --model myapp.models.User --apply
```

Add `--list` instead of `--model` to see migration files that already
exist in the output directory.

## pool

Shows the status of mydborm's [connection pool](installation.md) for the
given database — how many connections are configured, and whether the
database is currently reachable. Useful for confirming pool settings took
effect, or as a deeper-than-`ping` health check:

```bash
mydborm pool --dialect mysql --database mydb --password root
```

You can also pass `--size` and `--overflow` to see what status looks like
under a particular pool configuration.

## migrate-db

This is the odd one out — instead of keeping one database's schema in sync
with a model, `migrate-db` copies tables and data **from one database to
another**, including across different database engines (for example, MySQL
to YugabyteDB). It's a separate feature from everything else on this page;
see [Database Migration](db_migration.md) for the full explanation. The
short version: you give it source and target connection details, and it
copies the data over in batches.

```bash
mydborm migrate-db --source-dialect mysql --source-password root --source-db shop \
                    --target-dialect yugabyte --target-password yugabyte --target-db shop
```

Add `--dry-run` to preview what would be migrated (table names, row counts)
without writing anything to the target database — useful for sanity-checking
before running the real thing:

```bash
mydborm migrate-db --source-dialect mysql --source-password root --source-db shop \
                    --target-dialect yugabyte --target-password yugabyte --target-db shop \
                    --tables users,orders --dry-run
```

`--tables` restricts the migration to specific, comma-separated tables
instead of copying every table in the source database.
