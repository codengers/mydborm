# =============================================================================
# File        : examples/transactions_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Transactions demo — db.transaction() for all-or-nothing
#               groups of statements, db.savepoint() for rolling back
#               just part of a transaction, and transaction_with_retry()
#               for automatically retrying on deadlock.
# =============================================================================

from mydborm import db, BaseModel, IntField, StrField, FloatField

db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3307,
    user     = "root",
    password = "root",
    database = "testdb",
)


class TxAccount(BaseModel):
    __tablename__ = "tx_accounts"
    id      = IntField(primary_key=True)
    owner   = StrField(max_length=100, nullable=False)
    balance = FloatField(nullable=False, default=0.0)


def main():
    print("=" * 60)
    print("  mydborm — Transactions demo")
    print("=" * 60)

    TxAccount.create_table()
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM tx_accounts")

    alice = TxAccount.create(owner="Alice", balance=100.0)
    bob   = TxAccount.create(owner="Bob",   balance=50.0)

    # ------------------------------------------------------------------ #
    #  transaction() — group statements so they all succeed together     #
    # ------------------------------------------------------------------ #
    print("\n── A successful transfer ────────────────────────────────")

    # Moving money between two accounts is really two separate UPDATE
    # statements. If the first one ran and the second one failed, you'd
    # have created money out of nowhere. db.transaction() makes sure
    # either both statements commit, or neither does.
    def transfer(from_id, to_id, amount):
        with db.transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE tx_accounts SET balance = balance - %s WHERE id = %s",
                [amount, from_id],
            )
            cur.execute(
                "UPDATE tx_accounts SET balance = balance + %s WHERE id = %s",
                [amount, to_id],
            )
        # both updates committed together here

    transfer(alice, bob, 30.0)
    print(f"  Alice: ${TxAccount.get(id=alice)['balance']}")
    print(f"  Bob:   ${TxAccount.get(id=bob)['balance']}")

    # ------------------------------------------------------------------ #
    #  A failed transaction rolls back everything                        #
    # ------------------------------------------------------------------ #
    print("\n── A failed transfer rolls back completely ─────────────")

    before_alice = TxAccount.get(id=alice)["balance"]
    before_bob   = TxAccount.get(id=bob)["balance"]

    try:
        with db.transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE tx_accounts SET balance = balance - %s WHERE id = %s",
                [1000.0, alice],
            )
            # Simulate a problem partway through — maybe a validation
            # check elsewhere in real code decided this transfer is bad.
            raise RuntimeError("insufficient funds check failed")
            # this second statement never runs:
            cur.execute(
                "UPDATE tx_accounts SET balance = balance + %s WHERE id = %s",
                [1000.0, bob],
            )
    except RuntimeError as e:
        print(f"  Caught: {e}")

    after_alice = TxAccount.get(id=alice)["balance"]
    after_bob   = TxAccount.get(id=bob)["balance"]
    print(f"  Alice's balance unchanged: {before_alice} == {after_alice}")
    print(f"  Bob's balance unchanged:   {before_bob} == {after_bob}")

    # ------------------------------------------------------------------ #
    #  savepoint() — roll back only part of a transaction                #
    # ------------------------------------------------------------------ #
    print("\n── Savepoints — partial rollback ────────────────────────")

    # A savepoint lets you undo just one part of a transaction without
    # losing everything else that already happened in it.
    with db.transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE tx_accounts SET balance = balance + %s WHERE id = %s",
            [10.0, alice],
        )
        try:
            with db.savepoint("bonus_attempt"):
                cur = conn.cursor()
                cur.execute(
                    "UPDATE tx_accounts SET balance = balance + %s WHERE id = %s",
                    [9999.0, bob],
                )
                raise RuntimeError("bonus amount was a mistake — undo just this part")
        except RuntimeError as e:
            print(f"  Caught inside savepoint: {e}")
        # Alice's +10 from before the savepoint is still here;
        # only Bob's +9999 inside the savepoint got undone.

    print(f"  Alice (kept the +10):        ${TxAccount.get(id=alice)['balance']}")
    print(f"  Bob (bonus rolled back):     ${TxAccount.get(id=bob)['balance']}")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM tx_accounts")
        conn.cursor().execute("DROP TABLE tx_accounts")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
