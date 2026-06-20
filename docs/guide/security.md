# Security

mydborm provides two security-focused field types:

- **PasswordField** — one-way bcrypt hashing for user passwords
- **EncryptedField** — two-way AES encryption for sensitive data

---

## Installation

```bash
pip install mydborm[security]
```

This installs `bcrypt` and `cryptography` as extra dependencies.

---

## PasswordField — bcrypt hashing

Use `PasswordField` for **user passwords**. Passwords are hashed using bcrypt
and **cannot be decrypted** — you can only verify them.

### Define the field

```python
from mydborm import db, BaseModel, IntField, StrField, BoolField
from mydborm import PasswordField

class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50,  nullable=False, unique=True)
    email    = StrField(max_length=255, nullable=False, unique=True)
    password = PasswordField(nullable=False)
    active   = BoolField(default=True)

User.create_table()
```

**SQL generated:**

```sql
-- MySQL
password VARCHAR(255) NOT NULL

-- YugabyteDB
password VARCHAR(255) NOT NULL
```

### Create a user

The password is **automatically hashed** on `create()` — you never store plain text:

```python
uid = User.create(
    username = "alice",
    email    = "alice@example.com",
    password = "mysecretpassword",    # plain text in
)

user = User.get(id=uid)
print(user["password"])
# $2b$12$K9L7bPzQx5uF3Yw8RtJm8...   ← bcrypt hash stored
print(user["password"] == "mysecretpassword")   # False — never plain text
```

### Verify a password (login)

```python
def login(username, plain_password):
    user = User.query().where("username", username).first()
    if not user:
        return False, "User not found"

    if PasswordField.verify(plain_password, user["password"]):
        return True, "Login successful"
    else:
        return False, "Wrong password"

ok, msg = login("alice", "mysecretpassword")
print(ok, msg)   # True  Login successful

ok, msg = login("alice", "wrongpassword")
print(ok, msg)   # False Wrong password
```

### Change password

```python
def change_password(user_id, old_password, new_password):
    user = User.get(id=user_id)
    if not user:
        raise ValueError("User not found")

    if not PasswordField.verify(old_password, user["password"]):
        raise ValueError("Current password is incorrect")

    # Update — new password is auto-hashed
    User.update({"password": new_password}, id=user_id)
    return True

change_password(uid, "mysecretpassword", "newstrongerpassword!")
```

### Hash password manually

```python
# Hash without storing
hashed = PasswordField.hash("mysecret", rounds=12)
print(hashed)   # $2b$12$...

# Verify later
ok = PasswordField.verify("mysecret", hashed)
print(ok)   # True
```

### Configure work factor (rounds)

Higher rounds = slower hashing = more secure. Default is 12.

```python
class User(BaseModel):
    __tablename__ = "users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50, nullable=False)
    # rounds=12 is production default
    # rounds=4 for tests (much faster)
    password = PasswordField(rounds=12, nullable=False)
```

| Rounds | Hash time | Use case |
|---|---|---|
| 4 | ~1ms | Tests only |
| 10 | ~100ms | Low-security apps |
| 12 | ~400ms | **Recommended** |
| 14 | ~1.5s | High-security |

### How bcrypt works
- Each hash includes a **random salt** — same password hashes differently each time
- The **rounds** parameter controls how many iterations are run
- Stored hash includes the rounds and salt — no extra columns needed
- **Cannot be reversed** — only verification is possible

---

## EncryptedField — AES encryption

Use `EncryptedField` for **data you need to retrieve** — API keys, tokens,
SSNs, credit card numbers, personal data.

!!! warning "Keep your key safe"
    If you lose your encryption key, **all encrypted data is unrecoverable**.
    Store keys in environment variables or a secrets manager — never in code.

### Generate a key

```python
from mydborm import EncryptedField

# Generate once — store securely
key = EncryptedField.generate_key()
print(key)
# dBF_6PJ5hRkzGjQ8N9TmY2w4sIoXcVeA3nKuLbEZWp0=

# Store in .env file:
# ENCRYPTION_KEY=dBF_6PJ5hRkzGjQ8N9TmY2w4sIoXcVeA3nKuLbEZWp0=
```

### Define the model

```python
import os
from mydborm import db, BaseModel, IntField, StrField
from mydborm import EncryptedField

KEY = os.environ["ENCRYPTION_KEY"]   # never hardcode!

class APICredential(BaseModel):
    __tablename__ = "api_credentials"
    id         = IntField(primary_key=True)
    service    = StrField(max_length=50, nullable=False)
    api_key    = EncryptedField(secret_key=KEY, nullable=False)
    api_secret = EncryptedField(secret_key=KEY, nullable=True)
    webhook    = EncryptedField(secret_key=KEY, nullable=True)

APICredential.create_table()
```

**SQL generated:**

```sql
-- MySQL
api_key    TEXT NOT NULL
api_secret TEXT
webhook    TEXT

-- YugabyteDB
api_key    TEXT NOT NULL
api_secret TEXT
webhook    TEXT
```

### Store credentials

Values are **automatically encrypted** on `create()`:

```python
cid = APICredential.create(
    service    = "stripe",
    api_key    = "sk_live_51abc123xyz",          # plain text in
    api_secret = "whsec_webhook_secret_456",
    webhook    = "https://api.myapp.com/webhook",
)

cred = APICredential.get(id=cid)
print(cred["api_key"])
# gAAAAABqNiQh8G-CriEJg6VvaewyJH...   ← ciphertext stored

print(cred["api_key"] == "sk_live_51abc123xyz")   # False — encrypted in DB
```

### Decrypt values

```python
# Method 1 — static method
plain = EncryptedField.decrypt(cred["api_key"], secret_key=KEY)
print(plain)   # sk_live_51abc123xyz

# Method 2 — field instance
field = APICredential._fields["api_key"]
plain = field.decrypt_value(cred["api_key"])
print(plain)   # sk_live_51abc123xyz

# Method 3 — encrypt/decrypt directly
cipher = EncryptedField.encrypt("my_secret_value", secret_key=KEY)
plain  = EncryptedField.decrypt(cipher, secret_key=KEY)
```

### Full workflow example

```python
import os
from mydborm import db, BaseModel, IntField, StrField, EncryptedField

KEY = os.environ.get("ENCRYPTION_KEY") or EncryptedField.generate_key()

class OAuthToken(BaseModel):
    __tablename__ = "oauth_tokens"
    id            = IntField(primary_key=True)
    user_id       = IntField(nullable=False)
    provider      = StrField(max_length=20, nullable=False)
    access_token  = EncryptedField(secret_key=KEY, nullable=False)
    refresh_token = EncryptedField(secret_key=KEY, nullable=True)
    expires_in    = IntField(nullable=True)

OAuthToken.create_table()

# Store after OAuth flow
def save_oauth_token(user_id, provider, access, refresh, expires):
    # Delete existing token for this user+provider
    existing = OAuthToken.filter(user_id=user_id, provider=provider)
    for t in existing:
        OAuthToken.delete(id=t["id"])

    # Store new token (auto-encrypted)
    return OAuthToken.create(
        user_id       = user_id,
        provider      = provider,
        access_token  = access,
        refresh_token = refresh,
        expires_in    = expires,
    )

# Retrieve and decrypt for API calls
def get_access_token(user_id, provider):
    token = OAuthToken.query().where("user_id", user_id).where("provider", provider).first()
    if not token:
        return None
    return EncryptedField.decrypt(token["access_token"], secret_key=KEY)

# Usage
save_oauth_token(1, "google", "ya29.abc...", "1//def...", 3600)
access = get_access_token(1, "google")
print(access)   # ya29.abc...
```

### How Fernet encryption works
- Uses **Fernet** — a safe, authenticated encryption scheme
- Each encryption uses a **random IV** — same value encrypts differently each time
- Includes **HMAC authentication** — tampered ciphertext raises an error
- Ciphertext is base64 — safe to store in TEXT columns

---

## Security best practices

### Use environment variables for keys

```python
# .env file (never commit this!)
# ENCRYPTION_KEY=your-key-here
# DB_PASSWORD=your-db-password

import os
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ["ENCRYPTION_KEY"]
```

### Never log plain passwords or decrypted values

```python
# BAD
print(f"User logged in with password: {plain_password}")
logger.info(f"API key: {decrypted_key}")

# GOOD
print(f"User {user_id} logged in successfully")
logger.info(f"API key for service {service} retrieved (length={len(decrypted_key)})")
```

### Rotate encryption keys periodically

```python
def rotate_encryption_key(old_key, new_key):
    """Re-encrypt all credentials with a new key."""
    creds = APICredential.all()
    for cred in creds:
        # Decrypt with old key
        plain_key    = EncryptedField.decrypt(cred["api_key"],    secret_key=old_key)
        plain_secret = EncryptedField.decrypt(cred["api_secret"], secret_key=old_key) if cred["api_secret"] else None

        # Re-encrypt with new key
        new_key_enc    = EncryptedField.encrypt(plain_key,    secret_key=new_key)
        new_secret_enc = EncryptedField.encrypt(plain_secret, secret_key=new_key) if plain_secret else None

        APICredential.update({
            "api_key":    new_key_enc,
            "api_secret": new_secret_enc,
        }, id=cred["id"])

    print(f"Re-encrypted {len(creds)} credentials")
```

### PasswordField vs EncryptedField — choosing the right one

| Use case | Field | Why |
|---|---|---|
| User login passwords | `PasswordField` | One-way — even you can't read it |
| API keys / tokens | `EncryptedField` | Need to retrieve and use them |
| OAuth access tokens | `EncryptedField` | Need to send to external APIs |
| Credit card numbers | `EncryptedField` | Need to display last 4 digits |
| SSN / passport | `EncryptedField` | Need to verify identity |
| Admin PINs | `PasswordField` | Only need to verify |
| Webhook secrets | `EncryptedField` | Need to sign payloads |
| Recovery codes | `PasswordField` | One-time verify, never show again |

---

## Field reference

### PasswordField

| Property | Value |
|---|---|
| MySQL type | `VARCHAR(255)` |
| YugabyteDB type | `VARCHAR(255)` |
| Algorithm | bcrypt |
| Default rounds | 12 |
| Reversible | No — verify only |

**Methods:**

```python
PasswordField.verify(plain, hashed)    # → bool
PasswordField.hash(plain, rounds=12)   # → hash string
field.needs_rehash(hashed)             # → bool
```

### EncryptedField

| Property | Value |
|---|---|
| MySQL type | `TEXT` |
| YugabyteDB type | `TEXT` |
| Algorithm | Fernet (AES-128-CBC + HMAC-SHA256) |
| Key size | 32 bytes (base64-encoded) |
| Reversible | Yes — decrypt with same key |

**Methods:**

```python
EncryptedField.generate_key()                    # → new key string
EncryptedField.encrypt(plain, secret_key=key)    # → ciphertext
EncryptedField.decrypt(cipher, secret_key=key)   # → plain text
field.decrypt_value(cipher)                      # → plain text
```
