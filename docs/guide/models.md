# Models & CRUD

A **model** is a Python class that represents one database table — one
class per table, one attribute per column. This page covers how to
define one, what the common field options mean, and how to validate
data before it's saved. For the actual create/read/update/delete
calls, see the [Quickstart](quickstart.md#3-crud-create-read-update-delete);
this page focuses on defining the model itself.

## Defining a model

```python
from mydborm import BaseModel, IntField, StrField, BoolField, FloatField

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False, unique=True)
    active   = BoolField(default=True)
    score    = FloatField(nullable=True)
```

Every model inherits from `BaseModel`. `__tablename__` sets the actual
table name in the database — if you skip it, mydborm derives one from
the class name (`User` → `users`).

Each field accepts a few common options:

| Option | What it does |
|---|---|
| `primary_key=True` | Marks this column as the table's unique row identifier. Every model needs exactly one. |
| `nullable=False` | Makes the field required — saving a row without it raises an error instead of silently storing `NULL`. |
| `nullable=True` (default) | The field is optional and can be left empty (`NULL` in the database). |
| `unique=True` | The database rejects two rows with the same value in this column (e.g. no two users sharing an email). |
| `default=...` | The value used automatically when you don't provide one (`active=True` above). |

This is just a description until you call `User.create_table()` —
nothing is sent to the database when you define the class itself.

## Picking field types

Every field describes both a Python type and the database column type
it maps to. Here are a few common ones to get started — the
[Fields guide](fields.md) covers all 29 field types, including
passwords and encrypted columns:

| Field | Python type | MySQL column | YugabyteDB column |
|---|---|---|---|
| `IntField` | `int` | `INT` | `INTEGER` |
| `StrField` | `str` | `VARCHAR(n)` | `VARCHAR(n)` |
| `TextField` | `str` | `TEXT` | `TEXT` |
| `BoolField` | `bool` | `TINYINT(1)` | `BOOLEAN` |
| `FloatField` | `float` | `FLOAT` | `FLOAT` |
| `DecimalField` | `Decimal` | `DECIMAL(p,s)` | `DECIMAL(p,s)` |
| `DateField` | `date` | `DATE` | `DATE` |
| `DateTimeField` | `datetime` | `DATETIME` | `TIMESTAMP` |
| `JSONField` | `dict` | `JSON` | `JSONB` |
| `ForeignKeyField` | `int` | `INT` | `INTEGER` |

You don't need to know the exact database column type to use a field —
mydborm picks the right one for whichever database (`dialect`) you
configured. The column types are listed here mainly so you know what
to expect if you ever look at the table directly.

## Validating data before it's saved

A field option like `nullable=False` checks that a value was provided
at all, but it doesn't check whether the value actually makes sense —
that an email looks like an email, or a number falls in a sane range.
That's what **validators** are for: extra checks that run before a
value reaches the database, so bad data gets rejected in Python with a
clear error instead of failing (or silently succeeding) at the SQL
level.

```python
from mydborm import EmailValidator, RangeValidator, ChoiceValidator

class Profile(BaseModel):
    __tablename__ = "profiles"
    id    = IntField(primary_key=True)
    email = StrField(validators=[EmailValidator()])
    age   = IntField(validators=[RangeValidator(min_val=0, max_val=150)])
    role  = StrField(validators=[ChoiceValidator(choices=["admin", "user"])])
```

Here, trying to `Profile.create(email="not-an-email", age=999, role="superadmin")`
fails before any SQL runs — `EmailValidator` rejects the malformed
email, `RangeValidator` rejects `age=999`, and `ChoiceValidator` rejects
a `role` that isn't `"admin"` or `"user"`.

mydborm ships with validators for email, URL, regex, numeric range,
string length, and choice lists — and you can write your own. See
[Validators](validators.md) for the full list and how to build custom
ones.
