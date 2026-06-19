# Models

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

## Field types

| Field | MySQL | YugabyteDB | Python type |
|---|---|---|---|
| IntField | INT | INTEGER | int |
| StrField | VARCHAR(n) | VARCHAR(n) | str |
| TextField | TEXT | TEXT | str |
| BoolField | TINYINT(1) | BOOLEAN | bool |
| FloatField | FLOAT | FLOAT | float |
| DecimalField | DECIMAL(p,s) | DECIMAL(p,s) | Decimal |
| DateField | DATE | DATE | date |
| DateTimeField | DATETIME | TIMESTAMP | datetime |
| JSONField | JSON | JSONB | dict |
| ForeignKeyField | INT | INTEGER | int |

## Validators

```python
from mydborm import EmailValidator, RangeValidator, ChoiceValidator

class Profile(BaseModel):
    __tablename__ = "profiles"
    id    = IntField(primary_key=True)
    email = StrField(validators=[EmailValidator()])
    age   = IntField(validators=[RangeValidator(0, 150)])
    role  = StrField(validators=[ChoiceValidator(["admin", "user"])])
```
