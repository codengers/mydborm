# =============================================================================
# File        : examples/session_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Session demo — the identity map (asking for the same row
#               twice gives back the same Python object) and automatic
#               change tracking (editing an attribute queues an UPDATE,
#               flushed and committed together on exit).
# =============================================================================

from mydborm import db, BaseModel, IntField, StrField, FloatField, Session

db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3307,
    user     = "root",
    password = "root",
    database = "testdb",
)


class SessUser(BaseModel):
    __tablename__ = "sess_users"
    id      = IntField(primary_key=True)
    name    = StrField(max_length=100, nullable=False)
    credits = FloatField(nullable=False, default=0.0)


def main():
    print("=" * 60)
    print("  mydborm — Session demo")
    print("=" * 60)

    SessUser.create_table()
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM sess_users")

    alice_id = SessUser.create(name="Alice", credits=10.0)
    SessUser.create(name="Bob", credits=5.0)

    # ------------------------------------------------------------------ #
    #  The identity map — same row, same Python object                   #
    # ------------------------------------------------------------------ #
    print("\n── Identity map ─────────────────────────────────────────")

    # Without a Session, every BaseModel.get() call builds a brand new
    # object, even for the same row — fine most of the time, but it
    # means two parts of your code editing "the same" user are actually
    # editing two unrelated copies. A Session instead remembers what
    # it's already loaded and hands back the exact same object.
    with Session() as session:
        user_a = session.get(SessUser, id=alice_id)
        user_b = session.get(SessUser, id=alice_id)
        print(f"  Same underlying row, same object: {user_a is user_b}")

        # Compare to calling BaseModel.get() directly, with no session:
        plain_a = SessUser.get(id=alice_id)
        plain_b = SessUser.get(id=alice_id)
        print(f"  Without a session, two separate objects: "
              f"{plain_a is not plain_b}")

    # ------------------------------------------------------------------ #
    #  Automatic change tracking — edit an attribute, it gets saved       #
    # ------------------------------------------------------------------ #
    print("\n── Change tracking ──────────────────────────────────────")

    with Session() as session:
        user = session.get(SessUser, id=alice_id)
        user.credits = 25.0   # just a normal attribute assignment
        # No explicit "save" call needed — leaving the `with` block
        # flushes every change made inside it and commits them together.

    refreshed = SessUser.get(id=alice_id)
    print(f"  Alice's credits after the session closed: {refreshed['credits']}")

    # ------------------------------------------------------------------ #
    #  Manual control — add(), flush(), commit() yourself                 #
    # ------------------------------------------------------------------ #
    print("\n── Manual add() / flush() / commit() ───────────────────")

    session = Session()
    new_user = session.add(SessUser, name="Carol", credits=0.0)
    print(f"  Queued, not in the database yet: {SessUser.count()} row(s) so far")
    session.flush()
    session.commit()
    session.close()
    print(f"  After flush()+commit(): {SessUser.count()} row(s) total")
    print(f"  New user's id was assigned during flush: {new_user['id']}")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM sess_users")
        conn.cursor().execute("DROP TABLE sess_users")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
