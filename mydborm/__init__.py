s# =============================================================================
# File        : __init__.py
# Project     : mydborm � Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Package entry point. Exposes the public API surface:
#               db connection manager, BaseModel, and all field types.
#               Install: pip install mydborm
#               Usage  : from mydborm import db, BaseModel, IntField
# =============================================================================
"""
mydborm — Lightweight ORM for MySQL and YugabyteDB.
"""

from .db import db
from .model import BaseModel
from .fields import (
    Field,
    IntField,
    StrField,
    TextField,
    BoolField,
    FloatField,
    DecimalField,
    DateField,
    DateTimeField,
    JSONField,
    ForeignKeyField,
)

__version__ = "0.3.0"
__author__  = "Codengers"
__license__ = "MIT"

__all__ = [
    "db",
    "BaseModel",
    "Field",
    "IntField",
    "StrField",
    "TextField",
    "BoolField",
    "FloatField",
    "DecimalField",
    "DateField",
    "DateTimeField",
    "JSONField",
    "ForeignKeyField",
]

