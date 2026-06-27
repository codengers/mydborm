# Transactions

Sometimes a single piece of work needs more than one SQL statement to
finish — for example, creating a user *and* creating their profile row.
If the first statement succeeds but the second one fails (a network blip,
a constraint violation, the process crashing), you're left with a user and
no profile: a half-finished, inconsistent state in your database.

A **transaction** groups multiple statements into one all-or-nothing unit.
Either every statement inside it succeeds and gets saved together, or — if
anything raises an exception — *all* of them are undone, as if none of it
ever happened. This guarantee (commonly summarized as "atomicity") is the
main reason to reach for a transaction: whenever a single logical
operation needs to touch more than one table, or run more than one
statement, wrap it in one.

## Basic transaction

Use `db.transaction()` as a context manager. Everything you run inside the
`with` block is part of the same transaction:

```python
with db.transaction():
    db.execute("INSERT INTO users (username) VALUES (%s)", ["alice"])
    db.execute("INSERT INTO profiles (user_id) VALUES (%s)", [1])
```

If both `INSERT` statements succeed, they're committed together when the
`with` block exits. If the second one raises an exception, mydborm
automatically rolls back the first one too — you never end up with a user
row and no matching profile.

## Savepoints

A plain transaction is all-or-nothing for everything inside it. But
sometimes you want to attempt something risky in the *middle* of a
transaction, and if just that part fails, undo only that part — without
throwing away everything that happened before it. That's what a
**savepoint** is for: think of it as a checkpoint you can roll back to
without rolling back the whole transaction.

```python
with db.transaction():
    User.create(username="alice")
    try:
        with db.savepoint("after_alice"):
            User.create(username="bob")
            raise Exception("bob failed")
    except Exception:
        pass  # only bob rolled back — alice is still queued to be committed
```

Here, creating "bob" fails inside the savepoint, so only bob's `INSERT` is
undone. "Alice" was created before the savepoint started, so she's
unaffected and is still committed when the outer transaction finishes. The
name you pass to `db.savepoint(...)` is just a label — if you don't supply
one, mydborm generates one for you.

## Bulk transaction

`db.bulk_transaction()` works the same way as `db.transaction()` — it
wraps multiple statements so they all commit together or all roll back
together. It exists as a clearly-named option for the common case of
inserting many rows across related tables in one logical batch:

```python
with db.bulk_transaction():
    db.execute("INSERT INTO orders ...")
    db.execute("INSERT INTO order_items ...")
```

## Nested transactions

If you have code that wraps its own work in `db.transaction()`, but that
code might sometimes be called from *inside* another transaction that's
already open, `db.nested_transaction()` handles both cases for you
automatically: it starts a real transaction if there isn't one open yet, or
falls back to a savepoint if there already is one. Either way, a failure
inside it only undoes the nested part:

```python
with db.transaction():
    User.create(username="outer")
    with db.nested_transaction():
        User.create(username="inner")
```

This is mainly useful when writing reusable functions that need to be safe
to call both on their own and as part of a larger transaction someone else
started.

## Retry on deadlock

A **deadlock** happens when two transactions are each waiting on a lock
the other one holds, and the database has to pick one to fail so the other
can proceed. This is a normal, expected occurrence under concurrent load —
not a bug in your code — and the usual fix is simply to retry the whole
transaction. `db.transaction_with_retry()` does this automatically: if the
transaction fails because of a deadlock (or a lock wait timeout), it
retries up to `retries` times, waiting a little longer between each
attempt. Any other kind of error is raised immediately, without retrying:

```python
with db.transaction_with_retry(retries=3):
    db.execute("UPDATE accounts SET balance = balance - 100 ...")
    db.execute("UPDATE accounts SET balance = balance + 100 ...")
```

This example — moving money from one account to another — is a classic
case for both a transaction (you never want only one side of the transfer
to happen) and retry-on-deadlock (two transfers touching the same accounts
at the same time are likely to collide).
