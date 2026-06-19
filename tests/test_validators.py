# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_validators.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.7.0
# License     : MIT
# Description : pytest tests for built-in validators — EmailValidator,
#               UrlValidator, RegexValidator, RangeValidator,
#               MinLengthValidator, ChoiceValidator, and model-level
#               cross-field validation via __validators__.
# =============================================================================

import os
import pytest
from mydborm import (
    db, BaseModel, IntField, StrField, BoolField, FloatField,
    EmailValidator, UrlValidator, RegexValidator,
    RangeValidator, MinLengthValidator, ChoiceValidator,
    ValidationRule,
)


# ------------------------------------------------------------------ #
#  Test models                                                         #
# ------------------------------------------------------------------ #

class Profile(BaseModel):
    __tablename__ = "val_profiles"
    id      = IntField(primary_key=True)
    email   = StrField(max_length=255, nullable=False,
                       validators=[EmailValidator()])
    website = StrField(max_length=255, nullable=True,
                       validators=[UrlValidator()])
    age     = IntField(nullable=False,
                       validators=[RangeValidator(min_val=0, max_val=150)])
    code    = StrField(max_length=10, nullable=True,
                       validators=[RegexValidator(r'^[A-Z]{3}$')])
    role    = StrField(max_length=20, nullable=False,
                       validators=[ChoiceValidator(["admin", "user", "guest"])])
    name    = StrField(max_length=100, nullable=False,
                       validators=[MinLengthValidator(2)])
    score   = FloatField(nullable=True,
                         validators=[RangeValidator(min_val=0.0, max_val=10.0)])


class CrossFieldModel(BaseModel):
    __tablename__ = "val_cross"
    id       = IntField(primary_key=True)
    role     = StrField(max_length=20,  nullable=False)
    website  = StrField(max_length=255, nullable=True)
    discount = IntField(nullable=True)
    price    = FloatField(nullable=False)

    __validators__ = [
        lambda data: (_ for _ in ()).throw(
            ValueError("admin role requires a website")
        ) if data.get("role") == "admin" and not data.get("website") else None,

        lambda data: (_ for _ in ()).throw(
            ValueError("discount cannot exceed price")
        ) if (data.get("discount") or 0) > (data.get("price") or 0) else None,
    ]


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
    )
    Profile.create_table()
    CrossFieldModel.create_table()
    yield
    CrossFieldModel.drop_table()
    Profile.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM val_profiles")
        cur.execute("DELETE FROM val_cross")
    yield


# ------------------------------------------------------------------ #
#  ValidationRule base                                                 #
# ------------------------------------------------------------------ #

def test_validation_rule_base_raises():
    class BadRule(ValidationRule):
        pass
    with pytest.raises(NotImplementedError):
        BadRule().validate("x", "field")


def test_validators_exported_from_package():
    import mydborm
    assert hasattr(mydborm, "EmailValidator")
    assert hasattr(mydborm, "UrlValidator")
    assert hasattr(mydborm, "RegexValidator")
    assert hasattr(mydborm, "RangeValidator")
    assert hasattr(mydborm, "MinLengthValidator")
    assert hasattr(mydborm, "ChoiceValidator")


# ------------------------------------------------------------------ #
#  EmailValidator                                                      #
# ------------------------------------------------------------------ #

def test_email_valid():
    v = EmailValidator()
    v.validate("alice@example.com", "email")


def test_email_valid_subdomains():
    v = EmailValidator()
    v.validate("user@mail.example.co.uk", "email")


def test_email_invalid_no_at():
    v = EmailValidator()
    with pytest.raises(ValueError, match="valid email"):
        v.validate("notanemail", "email")


def test_email_invalid_no_domain():
    v = EmailValidator()
    with pytest.raises(ValueError, match="valid email"):
        v.validate("user@", "email")


def test_email_none_passes():
    v = EmailValidator()
    v.validate(None, "email")


def test_email_on_model_valid():
    uid = Profile.create(
        email="alice@example.com", age=25,
        role="user", name="Alice"
    )
    assert uid > 0


def test_email_on_model_invalid():
    with pytest.raises(ValueError, match="valid email"):
        Profile.create(
            email="bad-email", age=25,
            role="user", name="Alice"
        )


# ------------------------------------------------------------------ #
#  UrlValidator                                                        #
# ------------------------------------------------------------------ #

def test_url_valid_http():
    v = UrlValidator()
    v.validate("http://example.com", "website")


def test_url_valid_https():
    v = UrlValidator()
    v.validate("https://example.com/path?q=1", "website")


def test_url_invalid_no_scheme():
    v = UrlValidator()
    with pytest.raises(ValueError, match="valid URL"):
        v.validate("example.com", "website")


def test_url_invalid_ftp():
    v = UrlValidator()
    with pytest.raises(ValueError, match="valid URL"):
        v.validate("ftp://example.com", "website")


def test_url_none_passes():
    v = UrlValidator()
    v.validate(None, "website")


# ------------------------------------------------------------------ #
#  RegexValidator                                                      #
# ------------------------------------------------------------------ #

def test_regex_valid():
    v = RegexValidator(r'^[A-Z]{3}$')
    v.validate("ABC", "code")


def test_regex_invalid():
    v = RegexValidator(r'^[A-Z]{3}$')
    with pytest.raises(ValueError, match="pattern"):
        v.validate("abc", "code")


def test_regex_custom_message():
    v = RegexValidator(r'^\d+$', message="must be digits only")
    with pytest.raises(ValueError, match="must be digits only"):
        v.validate("abc", "code")


def test_regex_none_passes():
    v = RegexValidator(r'^\d+$')
    v.validate(None, "code")


def test_regex_on_model_valid():
    uid = Profile.create(
        email="b@x.com", age=20,
        code="XYZ", role="user", name="Bob"
    )
    assert uid > 0


def test_regex_on_model_invalid():
    with pytest.raises(ValueError, match="pattern"):
        Profile.create(
            email="c@x.com", age=20,
            code="xyz", role="user", name="Carol"
        )


# ------------------------------------------------------------------ #
#  RangeValidator                                                      #
# ------------------------------------------------------------------ #

def test_range_valid_within():
    v = RangeValidator(min_val=0, max_val=100)
    v.validate(50, "age")


def test_range_valid_at_min():
    v = RangeValidator(min_val=0, max_val=100)
    v.validate(0, "age")


def test_range_valid_at_max():
    v = RangeValidator(min_val=0, max_val=100)
    v.validate(100, "age")


def test_range_invalid_below_min():
    v = RangeValidator(min_val=0, max_val=100)
    with pytest.raises(ValueError, match=">="):
        v.validate(-1, "age")


def test_range_invalid_above_max():
    v = RangeValidator(min_val=0, max_val=100)
    with pytest.raises(ValueError, match="<="):
        v.validate(101, "age")


def test_range_min_only():
    v = RangeValidator(min_val=18)
    v.validate(18, "age")
    with pytest.raises(ValueError):
        v.validate(17, "age")


def test_range_max_only():
    v = RangeValidator(max_val=100)
    v.validate(100, "age")
    with pytest.raises(ValueError):
        v.validate(101, "age")


def test_range_none_passes():
    v = RangeValidator(min_val=0, max_val=100)
    v.validate(None, "age")


def test_range_float_values():
    v = RangeValidator(min_val=0.0, max_val=10.0)
    v.validate(5.5, "score")
    with pytest.raises(ValueError):
        v.validate(10.1, "score")


def test_range_on_model_valid():
    uid = Profile.create(
        email="d@x.com", age=25,
        role="user", name="Dave"
    )
    assert uid > 0


def test_range_on_model_invalid():
    with pytest.raises(ValueError, match="<="):
        Profile.create(
            email="e@x.com", age=200,
            role="user", name="Eve"
        )


# ------------------------------------------------------------------ #
#  MinLengthValidator                                                  #
# ------------------------------------------------------------------ #

def test_min_length_valid():
    v = MinLengthValidator(3)
    v.validate("abc", "name")


def test_min_length_invalid():
    v = MinLengthValidator(3)
    with pytest.raises(ValueError, match="at least 3"):
        v.validate("ab", "name")


def test_min_length_exact():
    v = MinLengthValidator(3)
    v.validate("abc", "name")


def test_min_length_none_passes():
    v = MinLengthValidator(3)
    v.validate(None, "name")


def test_min_length_on_model_invalid():
    with pytest.raises(ValueError, match="at least"):
        Profile.create(
            email="f@x.com", age=25,
            role="user", name="F"
        )


# ------------------------------------------------------------------ #
#  ChoiceValidator                                                     #
# ------------------------------------------------------------------ #

def test_choice_valid():
    v = ChoiceValidator(["a", "b", "c"])
    v.validate("a", "role")


def test_choice_invalid():
    v = ChoiceValidator(["a", "b", "c"])
    with pytest.raises(ValueError, match="one of"):
        v.validate("d", "role")


def test_choice_none_passes():
    v = ChoiceValidator(["a", "b"])
    v.validate(None, "role")


def test_choice_on_model_valid():
    uid = Profile.create(
        email="g@x.com", age=25,
        role="admin", name="Grace"
    )
    assert uid > 0


def test_choice_on_model_invalid():
    with pytest.raises(ValueError, match="one of"):
        Profile.create(
            email="h@x.com", age=25,
            role="superuser", name="Heidi"
        )


# ------------------------------------------------------------------ #
#  Multiple validators on one field                                    #
# ------------------------------------------------------------------ #

def test_multiple_validators_all_pass():
    f = StrField(
        max_length=50,
        validators=[MinLengthValidator(3), RegexValidator(r'^[a-z]+$')]
    )
    f.name = "slug"
    f.validate("hello")


def test_multiple_validators_first_fails():
    f = StrField(
        max_length=50,
        validators=[MinLengthValidator(5), RegexValidator(r'^[a-z]+$')]
    )
    f.name = "slug"
    with pytest.raises(ValueError, match="at least 5"):
        f.validate("hi")


def test_multiple_validators_second_fails():
    f = StrField(
        max_length=50,
        validators=[MinLengthValidator(2), RegexValidator(r'^[a-z]+$')]
    )
    f.name = "slug"
    with pytest.raises(ValueError, match="pattern"):
        f.validate("HELLO")


# ------------------------------------------------------------------ #
#  Model-level cross-field validators                                  #
# ------------------------------------------------------------------ #

def test_cross_field_valid():
    uid = CrossFieldModel.create(
        role="admin", website="https://admin.example.com",
        price=100.0, discount=10
    )
    assert uid > 0


def test_cross_field_admin_requires_website():
    with pytest.raises(ValueError, match="requires a website"):
        CrossFieldModel.create(
            role="admin", website=None,
            price=100.0
        )


def test_cross_field_discount_exceeds_price():
    with pytest.raises(ValueError, match="cannot exceed"):
        CrossFieldModel.create(
            role="user", price=50.0, discount=100
        )


def test_cross_field_non_admin_no_website():
    uid = CrossFieldModel.create(
        role="user", price=50.0
    )
    assert uid > 0