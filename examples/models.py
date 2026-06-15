from mydborm import BaseModel, IntField, StrField, BoolField, FloatField

class Product(BaseModel):
    __tablename__ = "products"
    id       = IntField(primary_key=True)
    name     = StrField(max_length=100, nullable=False)
    price    = FloatField(nullable=False)
    active   = BoolField(default=True)
