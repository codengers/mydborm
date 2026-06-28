# =============================================================================
# File        : examples/validators_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Validators demo — every built-in validator (email, URL,
#               regex, range, minimum length, choice) catching bad data
#               in Python before it reaches SQL, plus a custom validator.
# =============================================================================

from mydborm import (
    db, BaseModel, IntField, StrField,
    EmailValidator, UrlValidator, RegexValidator,
    RangeValidator, MinLengthValidator, ChoiceValidator, ValidationRule,
)

db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3307,
    user     = "root",
    password = "root",
    database = "testdb",
)


# ------------------------------------------------------------------ #
#  A custom validator — subclass ValidationRule, implement validate() #
# ------------------------------------------------------------------ #

class NoSpacesValidator(ValidationRule):
    """Rejects any value containing a space — handy for slugs/usernames."""

    def validate(self, value, field_name: str):
        if value is not None and " " in str(value):
            raise ValueError(
                f"Field '{field_name}' cannot contain spaces. Got: {value!r}"
            )


class VUser(BaseModel):
    __tablename__ = "v_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=50, nullable=False,
                        validators=[MinLengthValidator(3), NoSpacesValidator()])
    email    = StrField(max_length=255, nullable=False,
                        validators=[EmailValidator()])
    website  = StrField(max_length=255, nullable=True,
                        validators=[UrlValidator()])
    referral = StrField(max_length=10, nullable=True,
                        validators=[RegexValidator(r'^[A-Z]{3}\d{3}$',
                                                    message="Referral code must look like ABC123")])
    age      = IntField(nullable=True,
                        validators=[RangeValidator(min_val=13, max_val=120)])
    role     = StrField(max_length=20, nullable=False, default="user",
                        validators=[ChoiceValidator(choices=["user", "admin", "moderator"])])


def try_create(label, **kwargs):
    """Attempt to create a row and report whether validation caught a problem."""
    try:
        uid = VUser.create(**kwargs)
        print(f"  ✔ {label}: created (id={uid})")
        return uid
    except (ValueError, TypeError) as e:
        print(f"  ✘ {label}: rejected — {e}")
        return None


def main():
    print("=" * 60)
    print("  mydborm — Validators demo")
    print("=" * 60)

    VUser.create_table()
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM v_users")

    print("\n── Valid data passes every validator ────────────────────")
    try_create(
        "well-formed user",
        username="alice", email="alice@example.com",
        website="https://alice.dev", referral="ABC123",
        age=28, role="admin",
    )

    print("\n── Each validator catches its own kind of bad data ─────")
    try_create("username too short (MinLengthValidator)",
               username="al", email="a@example.com")
    try_create("username with a space (custom NoSpacesValidator)",
               username="al ice", email="a@example.com")
    try_create("malformed email (EmailValidator)",
               username="bob", email="not-an-email")
    try_create("malformed URL (UrlValidator)",
               username="carol", email="carol@example.com", website="not-a-url")
    try_create("malformed referral code (RegexValidator)",
               username="dave", email="dave@example.com", referral="not-it")
    try_create("age out of range (RangeValidator)",
               username="erin", email="erin@example.com", age=200)
    try_create("role not in the allowed list (ChoiceValidator)",
               username="frank", email="frank@example.com", role="superadmin")

    print(f"\n  Rows that actually made it into the table: {VUser.count()}")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM v_users")
        conn.cursor().execute("DROP TABLE v_users")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
