# Validators

mydborm provides 6 built-in validators that attach directly to field definitions.
Validation runs automatically on every `create()` and `update()` call.

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
    ValidationRule,   # base class for custom validators
)
```

---

## EmailValidator

Validates email address format using RFC-compliant regex.

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

**Pattern used:** `^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`

**None passes:** `email = None` is valid when `nullable=True`.

---

## UrlValidator

Validates URL format — requires `http://` or `https://` prefix.

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

---

## RegexValidator

Validates a value matches a custom regular expression pattern.

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

**Constructor:**

```python
RegexValidator(
    pattern: str,          # regex pattern string
    message: str = None,   # custom error message (optional)
)
```

---

## RangeValidator

Validates a numeric value is within a minimum and maximum range.

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

**Constructor:**

```python
RangeValidator(
    min_val = None,   # minimum value (inclusive)
    max_val = None,   # maximum value (inclusive)
)
```

Both `min_val` and `max_val` are optional — use one or both.

---

## MinLengthValidator

Validates a string meets a minimum character length.

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

**Constructor:**

```python
MinLengthValidator(min_length: int)
```

---

## ChoiceValidator

Validates a value is one of a fixed set of allowed choices.

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

!!! tip "Use ChoiceValidator vs EnumField"
    `ChoiceValidator` validates at the Python level — the DB stores a plain VARCHAR.
    `EnumField` validates AND creates a MySQL ENUM column — stricter at the DB level.
    Use `ChoiceValidator` when you might add/remove choices without a migration.
    Use `EnumField` when you want DB-level enforcement too.

---

## Combining multiple validators

Attach multiple validators to one field — they run in order, stopping at the first failure:

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

---

## Cross-field validation

Use `__validators__` on the model class for rules that span multiple fields:

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

---

## Custom validators

Create your own validator by subclassing `ValidationRule`:

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

---

## Validator reference

| Validator | Constructor | What it checks |
|---|---|---|
| `EmailValidator()` | no args | RFC email format |
| `UrlValidator()` | no args | http/https URL |
| `RegexValidator(pattern, message=None)` | pattern str | custom regex |
| `RangeValidator(min_val=None, max_val=None)` | numeric bounds | min ≤ value ≤ max |
| `MinLengthValidator(min_length)` | int | len(value) ≥ min |
| `ChoiceValidator(choices)` | list | value in choices |
| `ValidationRule` (subclass) | custom | anything |
