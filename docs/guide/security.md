# Security

Some columns shouldn't be stored as plain, readable text — passwords,
API keys, tokens, social security numbers. If your database is ever
leaked, copied, or just looked at by someone who shouldn't have access,
plain-text sensitive data is the difference between "no big deal" and
"every user needs to change their password right now."

mydborm gives you two field types for this, and picking the right one
matters more than it might seem at first:

- **`PasswordField`** — scrambles the value in a way that **cannot be
  undone**. You can check whether a guess is correct, but you (or
  anyone, including someone who steals your database) can never
  recover the original password from what's stored. This is called
  **one-way hashing**.
- **`EncryptedField`** — scrambles the value in a way that **can be
  undone**, but only by someone who has the secret key. This is called
  **two-way encryption**.

That distinction — "can never get it back" vs. "can get it back if you
have the key" — is the most important thing to understand on this
page, so it's worth repeating: use `PasswordField` for things you only
ever need to *check* (does this password match?), and use
`EncryptedField` for things you need to *read back later* (what is this
user's API key, so I can call a third-party service with it?).

---

## Installation

Both field types need extra libraries that aren't installed with
mydborm by default, since not every project needs them:

```bash
pip install mydborm[security]
```

This installs two packages:

- **bcrypt** — the library that does the one-way hashing for
  `PasswordField`.
- **cryptography** — the library that does the two-way encryption for
  `EncryptedField`.

---

## PasswordField — for things you only ever verify

Use `PasswordField` for **user login passwords** (or anything else
where all you ever need to know is "does this match what I have on
file?" — PINs, recovery codes, etc).

### Why not just store the password as text?

If you store a password as plain text and your database is ever
exposed, every user's actual password is exposed too — and since
people reuse passwords across sites, that's bad even for accounts
outside your app. The standard fix is to never store the actual
password at all. Instead, you run it through a one-way function (a
**hash**) that scrambles it into something unrecognizable, and you
store *that* instead. "One-way" means there's no function that takes
the scrambled output and produces the original password back — the
scrambling is designed to be effectively irreversible, even for you,
even with the database in hand.

`PasswordField` does this scrambling using an algorithm called
**bcrypt**, which is specifically designed for passwords (it's
deliberately slow, which makes it expensive for an attacker to guess
millions of passwords per second if they ever get a copy of your
database).

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

A `PasswordField` is declared just like any other field — there's
nothing extra to configure to get the basic behavior.

**SQL generated:**

```sql
-- MySQL
password VARCHAR(255) NOT NULL

-- YugabyteDB
password VARCHAR(255) NOT NULL
```

The column is just a `VARCHAR(255)` under the hood — to the database,
it looks like any other text column. The "hashing" part is something
mydborm does in Python before the value ever reaches the database; the
database itself has no idea it's storing a password.

### Create a user

The password is **automatically hashed** the moment you call
`create()` — you never have to call a hashing function yourself, and
the plain text never gets written to the database:

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

That long string starting with `$2b$12$...` is the bcrypt hash. It's
not meant to be read by a human — it's the scrambled result, plus a bit
of bookkeeping bcrypt needs (explained below) to be able to check a
password against it later.

### Verify a password (login)

Since you can't "unscramble" a hash back into the original password,
checking a login attempt works differently than you might expect:
instead of decrypting the stored value and comparing it to what the
user typed, you hash what the user typed using the *same* method and
compare the two hashes. `PasswordField.verify()` does exactly that for
you:

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

`PasswordField.verify(plain_password, hashed_password)` returns `True`
or `False` — it never reveals or reconstructs the original password,
it just tells you whether the one typed in matches the one that was
originally hashed.

### Change password

The same auto-hashing happens on `update()`, so changing a password
looks just like setting one for the first time — you still verify the
*old* password first to make sure the request is legitimate:

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

### Hash a password manually

Most of the time `create()` and `update()` handle hashing for you
automatically. But if you ever need the hash itself — for a script, a
test, or a one-off migration — you can call the hashing function
directly without going through a model at all:

```python
# Hash without storing
hashed = PasswordField.hash("mysecret", rounds=12)
print(hashed)   # $2b$12$...

# Verify later
ok = PasswordField.verify("mysecret", hashed)
print(ok)   # True
```

### Configure work factor (rounds)

Bcrypt has a "work factor" called **rounds** that controls how many
times the scrambling step repeats internally. More rounds means the
hash takes longer to compute — which sounds like a downside, but it's
actually the whole point: it also makes it proportionally slower for
an attacker trying to guess passwords by brute force. The default is
12 rounds, which is a good balance of "fast enough for a real login
form" and "slow enough to discourage guessing."

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

Use a low value like `rounds=4` only in your test suite, where you're
hashing passwords over and over and don't want the test run to slow
down — never in production.

### How bcrypt works

A couple of things that often confuse people new to password hashing:

- Each hash includes a **random salt** — a random chunk of data mixed
  in before scrambling, so the *same* password hashed twice produces
  two *different*-looking hashes. This stops an attacker from spotting
  "these two users have the same password" just by comparing the
  stored hashes.
- The salt and the rounds value are both saved as part of the stored
  hash string itself — that's why you don't need a separate column for
  them; the one `VARCHAR(255)` has everything `verify()` needs.
- There is no "unhash" function. The only thing you can ever do with a
  stored hash is check whether a candidate password produces a
  matching hash — you can never work backwards to the original
  password.

---

## EncryptedField — for things you need to read back later

Use `EncryptedField` for data where, unlike a password, you genuinely
need the original value back at some point — API keys you'll send to a
third-party service, OAuth tokens, social security numbers, credit card
numbers, or any other personal data your app needs to display or reuse
later.

This uses **encryption** rather than hashing. The difference: encryption
is two-way by design. Anyone holding the correct **secret key** (a
piece of data that acts like a password for the encryption itself) can
turn the scrambled value back into the original. That's exactly what
you want for an API key — you need to get the real key back out so you
can actually use it to call an API — but it's the opposite of what you
want for a login password, where letting anyone reverse it would defeat
the purpose.

Because encryption is reversible, the entire security of the system
comes down to one thing: keeping the secret key safe.

!!! warning "Keep your key safe"
    If you lose your encryption key, **all encrypted data is
    unrecoverable** — there is no backdoor or recovery option, by
    design. And if someone else gets a copy of your key (and your
    database), they can decrypt everything just as easily as you can.
    Store keys in environment variables or a secrets manager — never
    written directly in your source code.

### Generate a key

Before you can encrypt anything, you need a secret key. mydborm gives
you a helper to generate a properly random one — don't try to make one
up yourself (e.g. typing a memorable phrase), since that's much easier
for an attacker to guess than a truly random key:

```python
from mydborm import EncryptedField

# Generate once — store securely
key = EncryptedField.generate_key()
print(key)
# dBF_6PJ5hRkzGjQ8N9TmY2w4sIoXcVeA3nKuLbEZWp0=

# Store in .env file:
# ENCRYPTION_KEY=dBF_6PJ5hRkzGjQ8N9TmY2w4sIoXcVeA3nKuLbEZWp0=
```

Generate this key once for your application and keep using the same
one — if you generate a new key later without migrating your existing
encrypted data first, you'll permanently lose access to anything
encrypted with the old key. (See [Rotate encryption keys
periodically](#rotate-encryption-keys-periodically) below for how to
switch keys safely.)

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

Each `EncryptedField` needs the secret key passed in as `secret_key=`
— that's how mydborm knows what to encrypt and decrypt with for that
particular field. Reading the key from an environment variable (as
shown above with `os.environ["ENCRYPTION_KEY"]`) rather than typing it
directly into your source file means the key never ends up committed
to version control by accident.

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

Like `PasswordField`, the database column itself is just plain text
(`TEXT` this time, since encrypted values are longer than a bcrypt
hash) — the encryption and decryption happen entirely in Python,
outside the database.

### Store credentials

Values are **automatically encrypted** the moment you call `create()`
— you pass in the real value, and mydborm encrypts it before it's ever
written to the database:

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

The scrambled text you see (starting with `gAAAAA...`) is called
**ciphertext** — the encrypted form of your original value, sometimes
called the **plaintext**. Unlike a password hash, ciphertext isn't a
dead end: anyone with the right key can turn it back into the original
value, which is the whole point of choosing encryption here instead of
hashing.

### Decrypt values

Because encryption is reversible, mydborm gives you three equivalent
ways to get the original value back, depending on what's most
convenient in your code:

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

In every case, you need to supply the same `secret_key` that was used
to encrypt the value in the first place — decrypting with the wrong key
will fail rather than silently produce garbage.

### Full workflow example

Here's a more complete, realistic example — storing OAuth tokens after
a user connects a third-party account, then retrieving and decrypting
the access token later to actually call that provider's API:

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

### How the encryption works

`EncryptedField` uses a scheme called **Fernet**, which bundles
together a few standard cryptography building blocks so you don't have
to assemble them yourself:

- The underlying scrambling algorithm is **AES** (a widely used,
  well-trusted encryption standard) — this is the part that actually
  transforms your plaintext into ciphertext and back.
- Like bcrypt, each encryption uses fresh random data mixed in (an
  **IV**, short for "initialization vector") — so encrypting the exact
  same value twice produces two different-looking ciphertexts.
- Fernet also attaches an **authentication tag** (using something
  called HMAC) to every ciphertext. This means that if someone tampers
  with the stored ciphertext — even changing a single character —
  decrypting it raises an error instead of silently returning corrupted
  or wrong data.
- The final ciphertext is encoded as base64 (safe, plain ASCII text),
  so it stores cleanly in a normal `TEXT` column without any special
  handling.

---

## Security best practices

### Use environment variables for keys

Whether it's your database password or your encryption key, the rule
is the same: secrets belong in environment variables (or a dedicated
secrets manager for production systems), never typed directly into a
`.py` file that gets committed to git.

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

It's easy to accidentally leak a secret through a `print()` or a log
line you added for debugging and forgot to remove. Logs are often kept
around for a long time and read by more people than your database is —
so anything written to a log should already be safe to show to anyone
who can read your logs.

```python
# BAD
print(f"User logged in with password: {plain_password}")
logger.info(f"API key: {decrypted_key}")

# GOOD
print(f"User {user_id} logged in successfully")
logger.info(f"API key for service {service} retrieved (length={len(decrypted_key)})")
```

### Rotate encryption keys periodically

"Rotating" a key means switching to a new one — good practice to limit
how much damage a leaked key can do, since an old key that's no longer
in use can't decrypt anything new. Because `EncryptedField` is
reversible, you can do this safely: decrypt everything with the old
key, then re-encrypt it with the new one, without losing any data
(something that's simply not possible with one-way `PasswordField`
hashes).

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

The core question to ask yourself: **will I ever need to see the
original value again?** If no, hash it with `PasswordField`. If yes,
encrypt it with `EncryptedField`.

| Use case | Field | Why |
|---|---|---|
| User login passwords | `PasswordField` | One-way — even you can't read it back |
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
