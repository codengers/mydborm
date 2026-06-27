# Validators

When you save a row, you want to catch bad data *before* it ever reaches
the database — a malformed email, a rating of 11 out of 5, a status that
isn't one of the ones your app understands. That's what a **validator**
is for: a small rule attached to a field that checks the value and
raises a Python error if it doesn't pass.

This is different from a database constraint. A validator runs **in
Python, on your machine, before any SQL is sent** — not as a rule
stored inside the database itself (the kind of rule database people
call a "CHECK constraint"). That means:

- The error happens immediately, with a clear Python message, instead
  of a cryptic database error after a network round trip.
- The check works the same way no matter which database you're using
  (MySQL, PostgreSQL, or YugabyteDB).
- You can write your own validators in plain Python — no SQL required.

mydborm runs validators automatically every time you call `create()` or
`update()`. You don't have to call anything yourself — just attach a
validator to a field when you define your model, and mydborm checks it
on every save from then on. There are 6 built-in validators, and you
can write custom ones too.

---

## Import validators

```python
from mydborm import (
    EmailValidator,
    UrlValidator,
    RegexValidator,
    RangeValidator,
    MinLengthValidator,
    ChoiceValidator,
    ValidationRule,   # base class for writing your own custom validators
)
```

Each one is attached to a field through that field's `validators=[...]`
argument — you can attach one or several to the same field, as you'll
see further down.

---

## EmailValidator

Checks that a string looks like a valid email address (using a regular
expression — a pattern-matching rule — under the hood, so you don't have
to write the pattern yourself).

```python
from mydborm import BaseModel, IntField, StrField, EmailValidator

class Contact(BaseModel):
    __tablename__ = "contacts"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100, nullable=False)
    email = StrField(max_length=255, nullable=False,
                     validators=[EmailValidator()])

# Valid emails
Contact.create(name="Alice", email="alice@example.com")          # OK
Contact.create(name="Bob",   email="bob.smith+tag@domain.co.uk") # OK
Contact.create(name="Carol", email="carol@sub.domain.org")       # OK

# Invalid emails
try:
    Contact.create(name="Dave", email="notanemail")
except ValueError as e:
    print(e)
    # Field 'email' must be a valid email address. Got: 'notanemail'

try:
    Contact.create(name="Eve", email="missing@domain")
except ValueError as e:
    print(e)
    # Field 'email' must be a valid email address. Got: 'missing@domain'

try:
    Contact.create(name="Frank", email="@nodomain.com")
except ValueError as e:
    print(e)
    # Field 'email' must be a valid email address. Got: '@nodomain.com'
```

Each `try`/`except` block above shows the same pattern you'll use
everywhere in this guide: call `create()` or `update()`, and if a
validator fails, mydborm raises a `ValueError` with a message you can
catch and show to the user (or log).

**Pattern used:** `^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`
— that's the regular expression mydborm checks the value against. You
don't need to understand regex syntax to use the validator; it's only
shown here for anyone curious or debugging an edge case.

**None passes:** if the field is `nullable=True`, setting `email = None`
skips the validator entirely — there's nothing to check.

---

## UrlValidator

Checks that a string is a URL starting with `http://` or `https://`.
Anything else — a bare domain, a different protocol, random text — is
rejected.

```python
from mydborm import UrlValidator

class Website(BaseModel):
    __tablename__ = "websites"
    id  = IntField(primary_key=True)
    url = StrField(max_length=500, nullable=False,
                   validators=[UrlValidator()])

# Valid URLs
Website.create(url="https://example.com")                  # OK
Website.create(url="http://example.com/path?query=1")      # OK
Website.create(url="https://sub.domain.org/page#anchor")   # OK

# Invalid URLs
try:
    Website.create(url="example.com")         # missing https://
except ValueError as e:
    print(e)   # Field 'url' must be a valid URL. Got: 'example.com'

try:
    Website.create(url="ftp://example.com")   # only http/https allowed
except ValueError as e:
    print(e)   # Field 'url' must be a valid URL. Got: 'ftp://example.com'

try:
    Website.create(url="not a url at all")
except ValueError as e:
    print(e)   # Field 'url' must be a valid URL. Got: 'not a url at all'
```

Note that `example.com` without a protocol fails — mydborm doesn't try
to guess what you meant, it just checks for `http://` or `https://` at
the start.

---

## RegexValidator

The three validators above are really just convenient shortcuts for
common patterns. `RegexValidator` is the general-purpose version: give
it any regular expression (a text pattern describing what a valid value
looks like) and it checks values against that pattern. Reach for this
when you need a format the built-in validators don't cover — product
SKUs, hex color codes, phone numbers, anything with a predictable shape.

```python
from mydborm import RegexValidator

class Product(BaseModel):
    __tablename__ = "products"
    id        = IntField(primary_key=True)
    sku       = StrField(max_length=20, nullable=False, validators=[
                    RegexValidator(
                        r'^[A-Z]{2,4}-\d{4}$',
                        message="SKU must be 2-4 uppercase letters, dash, 4 digits. E.g. PROD-0001"
                    )
                ])
    hex_color = StrField(max_length=7, nullable=True, validators=[
                    RegexValidator(r'^#[0-9A-Fa-f]{6}$')
                ])
    phone     = StrField(max_length=20, nullable=True, validators=[
                    RegexValidator(
                        r'^\+?[\d\s\-\(\)]{7,20}$',
                        message="Invalid phone number format"
                    )
                ])

# Valid
Product.create(sku="PROD-0001", hex_color="#FF5733")   # OK
Product.create(sku="AB-1234",   hex_color="#000000")   # OK
Product.create(sku="WXYZ-9999", hex_color=None)        # OK — nullable

# Invalid
try:
    Product.create(sku="prod-0001")   # lowercase not allowed
except ValueError as e:
    print(e)
    # SKU must be 2-4 uppercase letters, dash, 4 digits. E.g. PROD-0001

try:
    Product.create(sku="PROD-0001", hex_color="red")   # not hex format
except ValueError as e:
    print(e)
    # Field 'hex_color' does not match pattern '^#[0-9A-Fa-f]{6}$'. Got: 'red'
```

Passing your own `message=` (like the `sku` field does above) replaces
mydborm's default error text with something more useful to whoever
reads it. If you skip `message`, you get a generic message that
includes the raw pattern — fine for debugging, less fine for showing to
an end user.

**Constructor:**

```python
RegexValidator(
    pattern: str,          # the regex pattern to match against
    message: str = None,   # custom error message (optional)
)
```

---

## RangeValidator

Checks that a number falls between a minimum and a maximum (both
inclusive — meaning the boundary values themselves are allowed). Use it
for ratings, percentages, prices, ages, or any number that only makes
sense within certain bounds.

```python
from mydborm import RangeValidator, IntField, FloatField

class Survey(BaseModel):
    __tablename__ = "surveys"
    id       = IntField(primary_key=True)
    rating   = IntField(nullable=False,
                        validators=[RangeValidator(min_val=1, max_val=5)])
    price    = FloatField(nullable=False,
                          validators=[RangeValidator(min_val=0.01, max_val=99999.99)])
    discount = IntField(nullable=True,
                        validators=[RangeValidator(min_val=0, max_val=100)])
    age      = IntField(nullable=False,
                        validators=[RangeValidator(min_val=13)])   # min only
    score    = FloatField(nullable=True,
                          validators=[RangeValidator(max_val=100.0)])  # max only

# Valid
Survey.create(rating=5, price=29.99, discount=10, age=25)   # OK
Survey.create(rating=1, price=0.01, age=18)                  # OK — min boundary

# Invalid
try:
    Survey.create(rating=6, price=10.0, age=20)   # rating > 5
except ValueError as e:
    print(e)
    # Field 'rating' must be <= 5. Got: 6

try:
    Survey.create(rating=3, price=-1.0, age=20)   # negative price
except ValueError as e:
    print(e)
    # Field 'price' must be >= 0.01. Got: -1.0

try:
    Survey.create(rating=3, price=10.0, age=10)   # underage
except ValueError as e:
    print(e)
    # Field 'age' must be >= 13. Got: 10
```

Notice `age` only sets `min_val` and `score` only sets `max_val` — you
don't have to specify both ends. Leave either one out (it defaults to
`None`) if you only care about one side of the range.

**Constructor:**

```python
RangeValidator(
    min_val = None,   # minimum allowed value (inclusive)
    max_val = None,   # maximum allowed value (inclusive)
)
```

---

## MinLengthValidator

Checks that a string is at least a certain number of characters long.
Handy for usernames, passwords, or any text field where "too short" is
a meaningful error (rather than letting an empty or one-character value
silently slip through).

```python
from mydborm import MinLengthValidator

class UserAccount(BaseModel):
    __tablename__ = "user_accounts"
    id         = IntField(primary_key=True)
    username   = StrField(max_length=30,  nullable=False,
                          validators=[MinLengthValidator(3)])
    password   = StrField(max_length=255, nullable=False,
                          validators=[MinLengthValidator(8)])
    bio        = StrField(max_length=500, nullable=True,
                          validators=[MinLengthValidator(10)])
    company    = StrField(max_length=100, nullable=True,
                          validators=[MinLengthValidator(2)])

# Valid
UserAccount.create(username="alice", password="strongpass123")   # OK
UserAccount.create(username="bob",   password="p@ssw0rd!")       # OK

# Invalid
try:
    UserAccount.create(username="ab", password="validpass")   # too short
except ValueError as e:
    print(e)
    # Field 'username' must be at least 3 characters. Got: 2

try:
    UserAccount.create(username="carol", password="short")   # < 8 chars
except ValueError as e:
    print(e)
    # Field 'password' must be at least 8 characters. Got: 5
```

!!! note "Don't store real passwords as plain `StrField`s"
    The example above uses a plain `StrField` for `password` just to
    demonstrate `MinLengthValidator`. In a real app, use `PasswordField`
    instead — it automatically hashes the password so you never store
    it as readable text. See [Security](security.md) for details.

**Constructor:**

```python
MinLengthValidator(min_length: int)
```

---

## ChoiceValidator

Checks that a value is one of a fixed list of allowed options — useful
for things like order status, priority level, or any field where only
a specific, known set of values makes sense.

```python
from mydborm import ChoiceValidator

STATUSES   = ["pending", "processing", "shipped", "delivered", "cancelled", "refunded"]
PRIORITIES = ["low", "medium", "high", "critical"]
SIZES      = ["XS", "S", "M", "L", "XL", "XXL"]
REGIONS    = ["NA", "EU", "APAC", "LATAM", "MEA"]

class Order(BaseModel):
    __tablename__ = "orders"
    id       = IntField(primary_key=True)
    status   = StrField(max_length=20, nullable=False, default="pending",
                        validators=[ChoiceValidator(STATUSES)])
    priority = StrField(max_length=10, nullable=False, default="medium",
                        validators=[ChoiceValidator(PRIORITIES)])
    region   = StrField(max_length=10, nullable=True,
                        validators=[ChoiceValidator(REGIONS)])

# Valid
Order.create(status="pending",  priority="high")           # OK
Order.create(status="shipped",  priority="low", region="EU")  # OK

# Invalid
try:
    Order.create(status="unknown", priority="medium")
except ValueError as e:
    print(e)
    # Field 'status' must be one of ['pending', 'processing', 'shipped',
    #   'delivered', 'cancelled', 'refunded']. Got: 'unknown'

try:
    Order.create(status="pending", priority="CRITICAL")   # case sensitive!
except ValueError as e:
    print(e)
    # Field 'priority' must be one of ['low', 'medium', 'high', 'critical']. Got: 'CRITICAL'
```

The comparison is exact and case-sensitive — `"CRITICAL"` does not match
`"critical"` in the list. If you want to accept either case, convert the
value yourself before saving (e.g. `priority.lower()`).

!!! tip "ChoiceValidator vs EnumField — which one should I use?"
    Both restrict a field to a fixed set of values, but they enforce it
    in different places:

    - `ChoiceValidator` checks the value in **Python**, before the SQL
      is sent. The database column itself is a plain `VARCHAR` with no
      restriction of its own.
    - `EnumField` is a different kind of field entirely — it checks the
      value in Python *and* creates a MySQL `ENUM` column, so the
      database itself also refuses invalid values, even if some other
      tool writes to the table directly.

    Use `ChoiceValidator` if your list of allowed values might change
    without you wanting to run a database migration. Use `EnumField` if
    you want the database to enforce the rule too.

---

## Combining multiple validators

A field can have more than one validator. They run in the order you
list them, and stop at the very first one that fails — so put your
fastest or most "obvious" check first if it matters to you.

```python
from mydborm import MinLengthValidator, RegexValidator, ChoiceValidator

class BlogPost(BaseModel):
    __tablename__ = "blog_posts"
    id   = IntField(primary_key=True)
    slug = StrField(max_length=100, nullable=False, validators=[
        MinLengthValidator(3),
        RegexValidator(
            r'^[a-z0-9\-]+$',
            message="Slug may only contain lowercase letters, numbers, and hyphens"
        ),
    ])
    status = StrField(max_length=20, nullable=False, validators=[
        ChoiceValidator(["draft", "review", "published", "archived"]),
    ])

# Valid
BlogPost.create(slug="my-first-post", status="draft")   # OK

# Fails MinLengthValidator first
try:
    BlogPost.create(slug="ab", status="draft")
except ValueError as e:
    print(e)   # Field 'slug' must be at least 3 characters. Got: 2

# Passes MinLength, fails Regex
try:
    BlogPost.create(slug="My Post Title", status="draft")
except ValueError as e:
    print(e)   # Slug may only contain lowercase letters, numbers, and hyphens
```

In the second example, `"My Post Title"` is 13 characters long, so it
sails past `MinLengthValidator(3)` — but it has spaces and uppercase
letters, so it fails the regex check that runs next.

---

## Cross-field validation

Everything above checks **one field** in isolation. Sometimes a rule
depends on more than one field at once — for example, "the discount
percentage can't exceed 100, but only if a minimum order amount is also
set." For that, use `__validators__` on the model class itself instead
of on an individual field:

```python
class Discount(BaseModel):
    __tablename__ = "discounts"
    id          = IntField(primary_key=True)
    code        = StrField(max_length=20,  nullable=False)
    min_order   = FloatField(nullable=True)
    max_uses    = IntField(nullable=True)
    percentage  = FloatField(nullable=False,
                             validators=[RangeValidator(min_val=0.01, max_val=100.0)])
    expires_at  = StrField(max_length=20, nullable=True)

    __validators__ = [
        # min_order must be positive if set
        lambda data: (_ for _ in ()).throw(
            ValueError("min_order must be a positive number")
        ) if data.get("min_order") is not None and data["min_order"] <= 0 else None,

        # max_uses must be positive if set
        lambda data: (_ for _ in ()).throw(
            ValueError("max_uses must be at least 1")
        ) if data.get("max_uses") is not None and data["max_uses"] < 1 else None,
    ]

# Valid
Discount.create(code="SAVE10", percentage=10.0, min_order=50.0, max_uses=100)

# Fails cross-field validator
try:
    Discount.create(code="BAD", percentage=10.0, min_order=-5.0)
except ValueError as e:
    print(e)   # min_order must be a positive number
```

Each entry in `__validators__` is a function that receives the full
dictionary of values being saved (`data`) and can raise a `ValueError`
if something about the *combination* of fields is wrong. The
`lambda data: (_ for _ in ()).throw(...)` lines look unusual — that's
just a one-line trick for raising an exception inside a `lambda`, since
Python's `lambda` syntax doesn't allow a plain `raise` statement. If
you find that pattern hard to read, you can write the same check as a
normal function instead:

```python
def check_min_order(data):
    if data.get("min_order") is not None and data["min_order"] <= 0:
        raise ValueError("min_order must be a positive number")

class Discount(BaseModel):
    ...
    __validators__ = [check_min_order]
```

Both versions behave identically — use whichever reads more clearly to
you.

---

## Custom validators

If none of the built-in validators fit what you need, write your own by
subclassing `ValidationRule` and implementing a `validate()` method. It
receives the value being saved and the name of the field, and should
raise a `ValueError` if the value is invalid (returning normally — i.e.
not raising anything — means the value passed).

```python
from mydborm.fields import ValidationRule

class UKPostcodeValidator(ValidationRule):
    """Validates UK postcode format e.g. SW1A 1AA"""
    import re as _re
    PATTERN = _re.compile(
        r'^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$',
        _re.IGNORECASE
    )

    def validate(self, value, field_name: str):
        if value is not None and not self.PATTERN.match(str(value)):
            raise ValueError(
                f"Field '{field_name}' must be a valid UK postcode. "
                f"Examples: SW1A 1AA, EC1A 1BB. Got: {value!r}"
            )


class CreditCardValidator(ValidationRule):
    """Luhn algorithm check for credit card numbers"""
    def validate(self, value, field_name: str):
        if value is None:
            return
        digits = str(value).replace(" ", "").replace("-", "")
        if not digits.isdigit() or len(digits) < 13:
            raise ValueError(f"Field '{field_name}' is not a valid card number.")
        total = 0
        for i, d in enumerate(reversed(digits)):
            n = int(d)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        if total % 10 != 0:
            raise ValueError(f"Field '{field_name}' failed Luhn check.")


class Address(BaseModel):
    __tablename__ = "addresses"
    id       = IntField(primary_key=True)
    postcode = StrField(max_length=10, nullable=False,
                        validators=[UKPostcodeValidator()])

Address.create(postcode="SW1A 1AA")   # OK
Address.create(postcode="EC1A1BB")    # OK — space optional

try:
    Address.create(postcode="12345")  # US zip — not valid UK
except ValueError as e:
    print(e)
```

The `CreditCardValidator` example above shows that a custom validator
isn't limited to a regex check — it's plain Python, so it can run any
logic you want (here, the Luhn algorithm, a simple checksum formula
used to catch typos in card numbers) before deciding whether to raise
an error.

---

## Validator reference

| Validator | Constructor | What it checks |
|---|---|---|
| `EmailValidator()` | no args | Looks like a valid email address |
| `UrlValidator()` | no args | Starts with `http://` or `https://` |
| `RegexValidator(pattern, message=None)` | pattern str | Matches a custom regex pattern |
| `RangeValidator(min_val=None, max_val=None)` | numeric bounds | `min_val <= value <= max_val` |
| `MinLengthValidator(min_length)` | int | `len(value) >= min_length` |
| `ChoiceValidator(choices)` | list | Value is in the `choices` list |
| `ValidationRule` (subclass) | custom | Anything you write yourself |

All validators skip their check when the value is `None` — so a
`nullable=True` field with no value provided always passes, regardless
of which validators are attached.
