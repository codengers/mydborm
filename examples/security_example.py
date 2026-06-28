# =============================================================================
# File        : examples/security_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Security fields demo — PasswordField (one-way bcrypt
#               hash, for login passwords you only ever need to *check*,
#               never read back) vs EncryptedField (two-way AES/Fernet
#               encryption, for secrets you need to retrieve later,
#               like API keys). Requires: pip install mydborm[security]
# =============================================================================

from mydborm import db, BaseModel, IntField, StrField, PasswordField
from mydborm.fields import EncryptedField

db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3307,
    user     = "root",
    password = "root",
    database = "testdb",
)

# In a real app, generate this once and store it in an environment
# variable or a secrets manager — never hardcode it, and never commit
# it to source control. Anyone with this key can decrypt every
# EncryptedField value, so treat it like a password.
ENCRYPTION_KEY = EncryptedField.generate_key()


class SecUser(BaseModel):
    __tablename__ = "sec_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50, nullable=False)
    # PasswordField hashes the value automatically when you create/update
    # a row — you never see or store the plain password anywhere.
    password = PasswordField(nullable=False)


class SecCredential(BaseModel):
    __tablename__ = "sec_credentials"
    id      = IntField(primary_key=True)
    service = StrField(max_length=50, nullable=False)
    # EncryptedField is reversible — useful here because the app needs
    # the real API key back later to actually call that service.
    api_key = EncryptedField(secret_key=ENCRYPTION_KEY, nullable=False)


def main():
    print("=" * 60)
    print("  mydborm — Security fields demo")
    print("=" * 60)

    SecUser.create_table()
    SecCredential.create_table()
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM sec_users")
        conn.cursor().execute("DELETE FROM sec_credentials")

    # ------------------------------------------------------------------ #
    #  PasswordField — one-way hash, can never get the original back     #
    # ------------------------------------------------------------------ #
    print("\n── PasswordField (one-way, bcrypt) ──────────────────────")

    uid = SecUser.create(username="alice", password="correct-horse-battery")
    stored = SecUser.get(id=uid)
    print(f"  What's actually stored in the database: {stored['password'][:20]}...")
    print("  Not the plain password — there's no way to reverse a bcrypt")
    print("  hash back into the original text, even for mydborm itself.")

    # The only thing you can do with a hash is check a guess against it.
    print(f"\n  Correct password check:  "
          f"{PasswordField.verify('correct-horse-battery', stored['password'])}")
    print(f"  Wrong password check:    "
          f"{PasswordField.verify('wrong-guess', stored['password'])}")

    # ------------------------------------------------------------------ #
    #  EncryptedField — two-way, you CAN get the original value back     #
    # ------------------------------------------------------------------ #
    print("\n── EncryptedField (two-way, AES/Fernet) ─────────────────")

    cid = SecCredential.create(service="stripe", api_key="sk_live_abc123xyz")
    cred = SecCredential.get(id=cid)
    print(f"  What's actually stored in the database: {cred['api_key'][:25]}...")
    print("  This is ciphertext, not the real key — but unlike a password")
    print("  hash, it CAN be decrypted, because the app needs to use the")
    print("  real key later to actually call the Stripe API.")

    plain_key = EncryptedField.decrypt(cred["api_key"], secret_key=ENCRYPTION_KEY)
    print(f"\n  Decrypted with the right key: {plain_key}")

    try:
        wrong_key = EncryptedField.generate_key()
        EncryptedField.decrypt(cred["api_key"], secret_key=wrong_key)
    except Exception as e:
        print(f"  Decrypting with the WRONG key fails: {type(e).__name__}")

    # ------------------------------------------------------------------ #
    #  Which one do I use?                                                #
    # ------------------------------------------------------------------ #
    print("\n── Quick decision rule ──────────────────────────────────")
    print("  Will you ever need the real value back? "
          "No  → PasswordField (login passwords)")
    print("  Will you ever need the real value back? "
          "Yes → EncryptedField (API keys, tokens, PII)")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM sec_users")
        conn.cursor().execute("DELETE FROM sec_credentials")
        conn.cursor().execute("DROP TABLE sec_users")
        conn.cursor().execute("DROP TABLE sec_credentials")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
