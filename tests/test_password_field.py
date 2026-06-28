# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_password_field.py
# Project     : mydborm
# Author      : Atikrant Upadhye
# Created     : 2026-06-19
# Version     : 1.2.0
# License     : MIT
# Description : Tests for PasswordField (bcrypt) and EncryptedField (AES)
# =============================================================================

import os
import pytest

# Skip entire module if security deps not installed
pytest.importorskip("bcrypt",        reason="pip install bcrypt")
pytest.importorskip("cryptography",  reason="pip install cryptography")

from mydborm import (
    db, BaseModel, IntField, StrField,
    PasswordField, EncryptedField,
)

# ------------------------------------------------------------------ #
#  Test key                                                            #
# ------------------------------------------------------------------ #

TEST_KEY = EncryptedField.generate_key()


# ------------------------------------------------------------------ #
#  Test models                                                         #
# ------------------------------------------------------------------ #

class SecureUser(BaseModel):
    __tablename__ = "test_secure_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50, nullable=False)
    password = PasswordField(nullable=False)
    pin      = PasswordField(rounds=4, nullable=True)  # fast rounds for tests


class SecureData(BaseModel):
    __tablename__ = "test_secure_data"
    id         = IntField(primary_key=True)
    service    = StrField(max_length=50, nullable=False)
    api_key    = EncryptedField(secret_key=TEST_KEY, nullable=False)
    api_secret = EncryptedField(secret_key=TEST_KEY, nullable=True)
    notes      = EncryptedField(secret_key=TEST_KEY, nullable=True)


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
    SecureUser.create_table()
    SecureData.create_table()
    yield
    SecureData.drop_table()
    SecureUser.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM test_secure_users")
        cur.execute("DELETE FROM test_secure_data")
    yield


# ------------------------------------------------------------------ #
#  PasswordField — SQL generation                                      #
# ------------------------------------------------------------------ #

def test_password_field_mysql_sql():
    f = PasswordField()
    f.name = "password"
    assert f.to_sql_def("mysql") == "VARCHAR(255)"


def test_password_field_yugabyte_sql():
    f = PasswordField()
    f.name = "password"
    assert f.to_sql_def("yugabyte") == "VARCHAR(255)"


def test_password_field_exported():
    import mydborm
    assert hasattr(mydborm, "PasswordField")


# ------------------------------------------------------------------ #
#  PasswordField — hashing                                             #
# ------------------------------------------------------------------ #

def test_password_hashed_on_create():
    uid  = SecureUser.create(username="alice", password="mysecret")
    user = SecureUser.get(id=uid)
    assert user["password"] != "mysecret"
    assert user["password"].startswith("$2b$")


def test_password_hash_is_bcrypt():
    uid  = SecureUser.create(username="bob", password="bobpass123")
    user = SecureUser.get(id=uid)
    assert user["password"].startswith("$2b$12$")


def test_password_different_hash_each_time():
    h1 = PasswordField.hash("same_password")
    h2 = PasswordField.hash("same_password")
    assert h1 != h2   # bcrypt uses random salt


def test_password_verify_correct():
    uid  = SecureUser.create(username="carol", password="correctpass")
    user = SecureUser.get(id=uid)
    assert PasswordField.verify("correctpass", user["password"]) is True


def test_password_verify_wrong():
    uid  = SecureUser.create(username="dave", password="mypassword")
    user = SecureUser.get(id=uid)
    assert PasswordField.verify("wrongpassword", user["password"]) is False


def test_password_verify_empty_string():
    uid  = SecureUser.create(username="eve", password="somepass")
    user = SecureUser.get(id=uid)
    assert PasswordField.verify("", user["password"]) is False


def test_password_verify_case_sensitive():
    uid  = SecureUser.create(username="frank", password="MyPassword")
    user = SecureUser.get(id=uid)
    assert PasswordField.verify("MyPassword",  user["password"]) is True
    assert PasswordField.verify("mypassword",  user["password"]) is False
    assert PasswordField.verify("MYPASSWORD",  user["password"]) is False


def test_password_no_double_hash():
    # If value already starts with $2b$ it should not be hashed again
    h1   = PasswordField.hash("testpass", rounds=4)
    uid  = SecureUser.create(username="grace", password=h1)
    user = SecureUser.get(id=uid)
    # Should still verify correctly
    assert PasswordField.verify("testpass", user["password"]) is True


def test_password_static_hash():
    hashed = PasswordField.hash("mypassword", rounds=4)
    assert hashed.startswith("$2b$")
    assert PasswordField.verify("mypassword", hashed) is True


def test_password_custom_rounds():
    uid  = SecureUser.create(username="heidi", password="mainpass", pin="1234")
    user = SecureUser.get(id=uid)
    # rounds=4 in pin field
    assert user["pin"].startswith("$2b$04$")


def test_needs_rehash_false_when_rounds_match():
    field = PasswordField(rounds=12)
    field.name = "password"
    hashed = field.validate("mysecret")
    assert field.needs_rehash(hashed) is False


def test_needs_rehash_true_when_rounds_differ():
    old_hash = PasswordField.hash("mysecret", rounds=10)
    field = PasswordField(rounds=12)
    field.name = "password"
    assert field.needs_rehash(old_hash) is True


def test_needs_rehash_accepts_bytes():
    field = PasswordField(rounds=12)
    field.name = "password"
    hashed = field.validate("mysecret")
    assert field.needs_rehash(hashed.encode("utf-8")) is False


def test_needs_rehash_true_for_malformed_hash():
    field = PasswordField(rounds=12)
    field.name = "password"
    assert field.needs_rehash("not-a-bcrypt-hash") is True


def test_password_none_nullable():
    uid  = SecureUser.create(username="ivan", password="pass", pin=None)
    user = SecureUser.get(id=uid)
    assert user["pin"] is None


def test_password_unicode():
    uid  = SecureUser.create(username="judy", password="p@ssw0rd!#€£")
    user = SecureUser.get(id=uid)
    assert PasswordField.verify("p@ssw0rd!#€£", user["password"]) is True


# ------------------------------------------------------------------ #
#  EncryptedField — SQL generation                                     #
# ------------------------------------------------------------------ #

def test_encrypted_field_mysql_sql():
    f = EncryptedField(secret_key=TEST_KEY)
    f.name = "api_key"
    assert f.to_sql_def("mysql") == "TEXT"


def test_encrypted_field_yugabyte_sql():
    f = EncryptedField(secret_key=TEST_KEY)
    f.name = "api_key"
    assert f.to_sql_def("yugabyte") == "TEXT"


def test_encrypted_field_exported():
    import mydborm
    assert hasattr(mydborm, "EncryptedField")


# ------------------------------------------------------------------ #
#  EncryptedField — key generation                                     #
# ------------------------------------------------------------------ #

def test_generate_key_returns_string():
    key = EncryptedField.generate_key()
    assert isinstance(key, str)


def test_generate_key_unique():
    k1 = EncryptedField.generate_key()
    k2 = EncryptedField.generate_key()
    assert k1 != k2


def test_generate_key_valid_fernet():
    from cryptography.fernet import Fernet
    key = EncryptedField.generate_key()
    f   = Fernet(key.encode())
    assert f is not None


# ------------------------------------------------------------------ #
#  EncryptedField — encrypt/decrypt                                    #
# ------------------------------------------------------------------ #

def test_encrypted_on_create():
    cid  = SecureData.create(service="stripe", api_key="sk_live_123")
    cred = SecureData.get(id=cid)
    assert cred["api_key"] != "sk_live_123"
    assert cred["api_key"].startswith("gAAAAA")


def test_decrypt_static_method():
    cid    = SecureData.create(service="github", api_key="ghp_secret_token")
    cred   = SecureData.get(id=cid)
    plain  = EncryptedField.decrypt(cred["api_key"], secret_key=TEST_KEY)
    assert plain == "ghp_secret_token"


def test_decrypt_field_instance():
    cid   = SecureData.create(service="aws", api_key="AKIAIOSFODNN7EXAMPLE")
    cred  = SecureData.get(id=cid)
    field = SecureData._fields["api_key"]
    plain = field.decrypt_value(cred["api_key"])
    assert plain == "AKIAIOSFODNN7EXAMPLE"


def test_encrypt_decrypt_roundtrip():
    original = "super_secret_api_key_12345"
    encrypted = EncryptedField.encrypt(original, secret_key=TEST_KEY)
    decrypted = EncryptedField.decrypt(encrypted, secret_key=TEST_KEY)
    assert decrypted == original


def test_different_encryption_each_time():
    e1 = EncryptedField.encrypt("same_value", secret_key=TEST_KEY)
    e2 = EncryptedField.encrypt("same_value", secret_key=TEST_KEY)
    assert e1 != e2   # Fernet uses random IV


def test_encrypted_nullable_none():
    cid  = SecureData.create(service="test", api_key="key", api_secret=None)
    cred = SecureData.get(id=cid)
    assert cred["api_secret"] is None


def test_encrypted_unicode_value():
    cid  = SecureData.create(service="intl", api_key="密钥_secret_🔑")
    cred = SecureData.get(id=cid)
    plain = EncryptedField.decrypt(cred["api_key"], secret_key=TEST_KEY)
    assert plain == "密钥_secret_🔑"


def test_encrypted_long_value():
    long_val = "x" * 5000
    cid      = SecureData.create(service="big", api_key=long_val)
    cred     = SecureData.get(id=cid)
    plain    = EncryptedField.decrypt(cred["api_key"], secret_key=TEST_KEY)
    assert plain == long_val


def test_encrypted_multiple_fields():
    cid  = SecureData.create(
        service    = "stripe",
        api_key    = "pk_live_abc",
        api_secret = "sk_live_xyz",
        notes      = "Primary Stripe account",
    )
    cred = SecureData.get(id=cid)
    assert EncryptedField.decrypt(cred["api_key"],    TEST_KEY) == "pk_live_abc"
    assert EncryptedField.decrypt(cred["api_secret"], TEST_KEY) == "sk_live_xyz"
    assert EncryptedField.decrypt(cred["notes"],      TEST_KEY) == "Primary Stripe account"


def test_wrong_key_raises():
    cid      = SecureData.create(service="test", api_key="secret")
    cred     = SecureData.get(id=cid)
    wrong_key = EncryptedField.generate_key()
    with pytest.raises(Exception):
        EncryptedField.decrypt(cred["api_key"], secret_key=wrong_key)


def test_no_key_raises():
    with pytest.raises(ValueError, match="secret_key"):
        EncryptedField(secret_key=None)


def test_encrypted_no_double_encrypt():
    # Already encrypted values should not be re-encrypted
    encrypted = EncryptedField.encrypt("myvalue", secret_key=TEST_KEY)
    cid  = SecureData.create(service="test", api_key=encrypted)
    cred = SecureData.get(id=cid)
    plain = EncryptedField.decrypt(cred["api_key"], secret_key=TEST_KEY)
    assert plain == "myvalue"


# ------------------------------------------------------------------ #
#  Combined usage pattern                                              #
# ------------------------------------------------------------------ #

def test_full_secure_user_workflow():
    # Register
    uid = SecureUser.create(username="testuser", password="P@ssw0rd!")
    user = SecureUser.get(id=uid)

    # Login check
    assert PasswordField.verify("P@ssw0rd!", user["password"]) is True
    assert PasswordField.verify("wrong",      user["password"]) is False

    # Password is never stored in plain text
    assert "P@ssw0rd!" not in user["password"]


def test_full_api_credential_workflow():
    key = EncryptedField.generate_key()

    class TempCred(BaseModel):
        __tablename__ = "test_secure_data"
        id      = IntField(primary_key=True)
        service = StrField(max_length=50, nullable=False)
        api_key = EncryptedField(secret_key=key, nullable=False)
        api_secret = EncryptedField(secret_key=key, nullable=True)
        notes   = EncryptedField(secret_key=key, nullable=True)

    # Store credentials
    cid = TempCred.create(
        service    = "paypal",
        api_key    = "client_id_abc123",
        api_secret = "client_secret_xyz789",
    )

    # Retrieve and decrypt
    cred       = TempCred.get(id=cid)
    client_id  = EncryptedField.decrypt(cred["api_key"],    secret_key=key)
    client_sec = EncryptedField.decrypt(cred["api_secret"], secret_key=key)

    assert client_id  == "client_id_abc123"
    assert client_sec == "client_secret_xyz789"

    # Plain values never in DB
    assert cred["api_key"] != "client_id_abc123"