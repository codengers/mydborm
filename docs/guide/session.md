# Session

Everything you've seen so far — `User.create(...)`, `User.get(...)`,
`.where(...)` — talks to the database immediately, one call at a time. For
a lot of code that's exactly what you want. But once you're juggling
several objects at once and need to change a handful of them together, then
save everything in one go, doing it call-by-call gets tedious and slow (one
round trip to the database per change). `Session` is mydborm's answer to
that: it tracks a group of objects in memory, remembers what you've changed,
and writes everything to the database together when you're ready.

A `Session` gives you three related features, covered below: an **identity
map** (so you don't end up with duplicate copies of the same row), **change
tracking** (so it knows exactly what to save), and a **unit of work** (so
you can batch several changes into one trip to the database).

## Identity map

Normally, if you call `User.get(id=1)` twice, you get back two separate
Python objects that happen to hold the same data — editing one doesn't
affect the other, and mydborm has no way of knowing they represent the
same row. A `Session` fixes this with an **identity map**: a lookup table,
keyed by table name and primary key, that makes sure asking for the same
row twice gives you back the *same* Python object both times, not two
independent copies.

```python
from mydborm import Session

session = Session()
u1 = session.get(User, id=1)
u2 = session.get(User, id=1)
assert u1 is u2  # same object — the session returned the cached one instead of querying again
```

The second `session.get(User, id=1)` doesn't even touch the database — the
session already has that row tracked from the first call, so it just hands
back the same instance.

## Change tracking

Once an object is tracked by a session, the session keeps an eye on it.
Every time you change a field, the session quietly notes which field
changed and what its original value was — this is called **change
tracking**, and it's what lets the session figure out exactly what needs to
be saved, without you having to track it yourself or resend every field on
every save:

```python
u1["username"] = "updated"
session.is_dirty(u1)        # True — something on u1 has changed since it was loaded
session.dirty_fields(u1)    # ["username"] — exactly which field(s) changed
session.original_value(u1, "username")  # "alice" — the value before your edit
```

"Dirty" just means "modified but not yet saved" — it's standard terminology
you'll see in most ORMs. Nothing is sent to the database yet at this point;
you're only editing the in-memory object. `session.flush()` is what
actually writes the pending changes out:

```python
session.flush()  # writes the change to the database
```

## Unit of work

Tracking changes to existing rows is half the story — a session can also
queue up brand new rows to be inserted, and write several pending changes
out together in a single `flush()` call. This grouping of "everything that
needs to happen, done together" is called a **unit of work**, and it's
useful because it turns what would be several separate database round
trips into one:

```python
session.add(User, username="new_user", email="x@x.com")
session.flush()  # INSERT happens here
```

If you `session.add(...)` several new objects and modify a few existing
ones before calling `flush()`, all of those inserts and updates go out
together when you finally call it.

## Context manager

Most of the time you don't want to call `flush()` and handle errors
yourself — you just want "do this block of work, and either save all of it
or none of it." Using `Session` as a context manager (`with Session() as
session:`) does exactly that: changes are flushed and committed
automatically when the block exits normally, or rolled back automatically
if an exception happens partway through:

```python
with Session() as session:
    u = session.get(User, id=1)
    u["username"] = "updated"
    # auto-committed on exit, rolled back on exception
```

This is the recommended way to use `Session` for most code, since it
removes the risk of forgetting to call `flush()` or leaving a half-finished
change in memory.

## Rollback

If you want to discard changes you've made to a tracked object *without*
saving them — and without waiting for an exception to trigger it — call
`session.rollback()` directly. It restores every dirty object back to the
values it had when the session first loaded it:

```python
u["username"] = "will_be_discarded"
session.rollback()
print(u["username"])  # original value restored — "will_be_discarded" never reached the database
```
