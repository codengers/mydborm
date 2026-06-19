# Session

## Identity map

```python
from mydborm import Session

session = Session()
u1 = session.get(User, id=1)
u2 = session.get(User, id=1)
assert u1 is u2  # same object
```

## Change tracking

```python
u1["username"] = "updated"
session.is_dirty(u1)        # True
session.dirty_fields(u1)    # ["username"]
session.original_value(u1, "username")  # "alice"
session.flush()             # writes to DB
```

## Unit of work

```python
session.add(User, username="new_user", email="x@x.com")
session.flush()  # INSERT
```

## Context manager

```python
with Session() as session:
    u = session.get(User, id=1)
    u["username"] = "updated"
    # auto-committed on exit, rolled back on exception
```

## Rollback

```python
u["username"] = "will_be_discarded"
session.rollback()
print(u["username"])  # original value restored
```
