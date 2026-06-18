# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_serialization.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.5.0
# License     : MIT
# Description : pytest tests for model serialization — to_dict, to_json,
#               to_json_dict, from_dict, from_json, schema_info,
#               and validate_schema.
# =============================================================================

import os
import json
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm.exceptions import SchemaError
from mydborm.model import ModelInstance


# ------------------------------------------------------------------ #
#  Test models                                                         #
# ------------------------------------------------------------------ #

class SerUser(BaseModel):
    __tablename__ = "ser_test_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False)
    active   = BoolField(default=True)
    score    = FloatField(nullable=True)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect  = "mysql",
        host     = "127.0.0.1",
        port     = 3307,
        user     = "root",
        password = os.environ.get("DB_PASSWORD", "root"),
        database = "testdb",
        charset  = "utf8mb4",
        encoding = "utf-8",
    )
    SerUser.create_table()
    yield
    SerUser.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM ser_test_users")
    yield


@pytest.fixture()
def alice():
    uid = SerUser.create(
        username="alice", email="alice@example.com",
        active=True, score=9.5
    )
    return SerUser.get(id=uid)


# ------------------------------------------------------------------ #
#  to_dict                                                             #
# ------------------------------------------------------------------ #

def test_to_dict_returns_dict(alice):
    d = alice.to_dict()
    assert isinstance(d, dict)


def test_to_dict_contains_all_fields(alice):
    d = alice.to_dict()
    assert "id"       in d
    assert "username" in d
    assert "email"    in d
    assert "active"   in d
    assert "score"    in d


def test_to_dict_values_correct(alice):
    d = alice.to_dict()
    assert d["username"] == "alice"
    assert d["email"]    == "alice@example.com"


def test_to_dict_exclude_single(alice):
    d = alice.to_dict(exclude=["active"])
    assert "active"   not in d
    assert "username" in d


def test_to_dict_exclude_multiple(alice):
    d = alice.to_dict(exclude=["active", "score"])
    assert "active" not in d
    assert "score"  not in d
    assert "id"     in d


def test_to_dict_exclude_empty(alice):
    d = alice.to_dict(exclude=[])
    assert len(d) == 5


def test_to_dict_does_not_modify_original(alice):
    d = alice.to_dict(exclude=["active"])
    assert alice["active"] is not None


# ------------------------------------------------------------------ #
#  to_json                                                             #
# ------------------------------------------------------------------ #

def test_to_json_returns_string(alice):
    j = alice.to_json()
    assert isinstance(j, str)


def test_to_json_valid_json(alice):
    j    = alice.to_json()
    data = json.loads(j)
    assert isinstance(data, dict)


def test_to_json_contains_fields(alice):
    j    = alice.to_json()
    data = json.loads(j)
    assert "username" in data
    assert "email"    in data


def test_to_json_exclude(alice):
    j    = alice.to_json(exclude=["active", "score"])
    data = json.loads(j)
    assert "active" not in data
    assert "score"  not in data


def test_to_json_indent(alice):
    j = alice.to_json(indent=2)
    assert "\n" in j


def test_to_json_unicode():
    uid = SerUser.create(
        username="Atikrant Upadhye",
        email="atikrant@example.com",
        active=True, score=10.0
    )
    user = SerUser.get(id=uid)
    j    = user.to_json()
    data = json.loads(j)
    assert data["username"] == "Atikrant Upadhye"


# ------------------------------------------------------------------ #
#  to_json_dict                                                        #
# ------------------------------------------------------------------ #

def test_to_json_dict_returns_dict(alice):
    d = alice.to_json_dict()
    assert isinstance(d, dict)


def test_to_json_dict_exclude(alice):
    d = alice.to_json_dict(exclude=["score"])
    assert "score" not in d


# ------------------------------------------------------------------ #
#  from_dict                                                           #
# ------------------------------------------------------------------ #

def test_from_dict_returns_model_instance():
    u = SerUser.from_dict({"id": 1, "username": "bob",
                           "email": "bob@x.com",
                           "active": True, "score": 5.0})
    assert isinstance(u, ModelInstance)


def test_from_dict_attribute_access():
    u = SerUser.from_dict({"id": 1, "username": "bob",
                           "email": "bob@x.com"})
    assert u.username == "bob"
    assert u["email"] == "bob@x.com"


def test_from_dict_not_saved_to_db():
    u = SerUser.from_dict({"id": 9999, "username": "ghost",
                           "email": "ghost@x.com"})
    assert SerUser.get(id=9999) is None


def test_from_dict_partial_fields():
    u = SerUser.from_dict({"username": "partial"})
    assert u.username == "partial"
    assert u.get("email") is None


def test_from_dict_roundtrip(alice):
    d  = alice.to_dict()
    u2 = SerUser.from_dict(d)
    assert u2["username"] == alice["username"]
    assert u2["email"]    == alice["email"]


# ------------------------------------------------------------------ #
#  from_json                                                           #
# ------------------------------------------------------------------ #

def test_from_json_returns_model_instance():
    u = SerUser.from_json(
        '{"id": 1, "username": "carol", "email": "carol@x.com"}'
    )
    assert isinstance(u, ModelInstance)


def test_from_json_attribute_access():
    u = SerUser.from_json(
        '{"id": 1, "username": "carol", "email": "carol@x.com"}'
    )
    assert u.username == "carol"


def test_from_json_roundtrip(alice):
    j  = alice.to_json()
    u2 = SerUser.from_json(j)
    assert u2["username"] == alice["username"]


# ------------------------------------------------------------------ #
#  schema_info                                                         #
# ------------------------------------------------------------------ #

def test_schema_info_returns_dict():
    info = SerUser.schema_info()
    assert isinstance(info, dict)


def test_schema_info_table():
    info = SerUser.schema_info()
    assert info["table"] == "ser_test_users"


def test_schema_info_pk_field():
    info = SerUser.schema_info()
    assert info["pk_field"] == "id"


def test_schema_info_fields():
    info = SerUser.schema_info()
    assert "id"       in info["fields"]
    assert "username" in info["fields"]
    assert "active"   in info["fields"]


def test_schema_info_field_details():
    info = SerUser.schema_info()
    assert info["fields"]["id"]["primary_key"]     is True
    assert info["fields"]["username"]["nullable"]  is False
    assert info["fields"]["active"]["type"]        == "BoolField"


def test_schema_info_dialect():
    info = SerUser.schema_info()
    assert info["dialect"] == "mysql"


# ------------------------------------------------------------------ #
#  validate_schema                                                     #
# ------------------------------------------------------------------ #

def test_validate_schema_valid():
    result = SerUser.validate_schema()
    assert result["valid"]          is True
    assert result["missing_in_db"]  == []
    assert result["extra_in_db"]    == []
    assert len(result["matched"])   == 5


def test_validate_schema_table():
    result = SerUser.validate_schema()
    assert result["table"] == "ser_test_users"


def test_validate_schema_matched_fields():
    result = SerUser.validate_schema()
    assert set(result["matched"]) == {"id", "username",
                                       "email", "active", "score"}


def test_validate_schema_strict_passes():
    SerUser.validate_schema(strict=True)


def test_validate_schema_strict_raises_on_mismatch():
    class BadModel(BaseModel):
        __tablename__ = "ser_test_users"
        id            = IntField(primary_key=True)
        username      = StrField(max_length=100, nullable=False)
        ghost_column  = StrField(max_length=50, nullable=True)

    result = BadModel.validate_schema()
    assert result["valid"]             is False
    assert "ghost_column" in result["missing_in_db"]

    with pytest.raises(SchemaError) as exc:
        BadModel.validate_schema(strict=True)
    assert "ghost_column" in exc.value.missing_columns


def test_validate_schema_extra_in_db():
    class PartialModel(BaseModel):
        __tablename__ = "ser_test_users"
        id            = IntField(primary_key=True)
        username      = StrField(max_length=100, nullable=False)

    result = PartialModel.validate_schema()
    assert "email"  in result["extra_in_db"]
    assert "active" in result["extra_in_db"]
    assert "score"  in result["extra_in_db"]