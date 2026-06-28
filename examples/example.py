# =============================================================================
# File        : examples/example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Real-world usage demo of mydborm. Shows connection setup,
#               model definition, migrations, and full CRUD operations
#               against MySQL. Switch dialect to 'yugabyte' for YugabyteDB.
# =============================================================================

from mydborm import (
    db, BaseModel,
    IntField, StrField, BoolField, FloatField
)
from mydborm.migrations import migrate, migration_status

# ------------------------------------------------------------------ #
#  1. Configure connection                                             #
# ------------------------------------------------------------------ #

db.configure(
    dialect  = "mysql",       # or "yugabyte"
    host     = "127.0.0.1",
    port     = 3307,          # 3306 for local MySQL, 5433 for YugabyteDB
    user     = "root",
    password = "root",
    database = "testdb",
)

print("=" * 60)
print("  mydborm — Real-world usage demo")
print("=" * 60)

# ------------------------------------------------------------------ #
#  2. Define models                                                    #
# ------------------------------------------------------------------ #

class Author(BaseModel):
    __tablename__ = "authors"
    id       = IntField(primary_key=True)
    name     = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False, unique=True)
    active   = BoolField(default=True)


class Book(BaseModel):
    __tablename__ = "books"
    id         = IntField(primary_key=True)
    title      = StrField(max_length=200, nullable=False)
    price      = FloatField(nullable=False)
    author_id  = IntField(nullable=False)
    published  = BoolField(default=False)


# ------------------------------------------------------------------ #
#  3. Run migrations                                                   #
# ------------------------------------------------------------------ #

print("\n── Migrations ──────────────────────────────────────────")
for model in [Author, Book]:
    result = migrate(model, description=f"Create {model._table} table")
    print(f"  {result['message']}")
    # migrate() skips re-creating a table once its migration is marked
    # applied, even if the table itself was dropped some other way
    # since then. create_table() is a no-op CREATE TABLE IF NOT EXISTS,
    # so this keeps the demo runnable no matter how many times — or in
    # what order — it's been run before.
    model.create_table()

print("\n── Migration status ────────────────────────────────────")
for m in migration_status():
    status = "✔ Applied" if not m["rolled_back"] else "✘ Rolled back"
    print(f"  [{m['id']}] {m['description']:<35} {status}")

# ------------------------------------------------------------------ #
#  4. CRUD — Authors                                                   #
# ------------------------------------------------------------------ #

print("\n── Authors CRUD ────────────────────────────────────────")

# Clean slate
with db.connect() as conn:
    conn.cursor().execute("DELETE FROM books")
    conn.cursor().execute("DELETE FROM authors")

# Create
a1 = Author.create(name="Alice Dev",   email="alice@example.com", active=True)
a2 = Author.create(name="Bob Coder",   email="bob@example.com",   active=True)
a3 = Author.create(name="Carol Arch",  email="carol@example.com", active=False)
print(f"  Created 3 authors: ids {a1}, {a2}, {a3}")

# Read all
authors = Author.all()
print(f"  All authors ({len(authors)}):")
for a in authors:
    print(f"    → {a['name']:<15} active={bool(a['active'])}")

# Filter
active = Author.filter(active=True)
print(f"  Active authors: {len(active)}")

# Get single
author = Author.get(id=a1)
print(f"  Get id={a1}: {author['name']}")

# Update
Author.update({"active": False}, id=a2)
print(f"  Updated id={a2} active → False")

# Count + exists
print(f"  Total authors : {Author.count()}")
print(f"  Alice exists  : {Author.exists(email='alice@example.com')}")
print(f"  Ghost exists  : {Author.exists(email='ghost@example.com')}")

# ------------------------------------------------------------------ #
#  5. CRUD — Books                                                     #
# ------------------------------------------------------------------ #

print("\n── Books CRUD ──────────────────────────────────────────")

b1 = Book.create(title="Python ORM Patterns", price=29.99,
                 author_id=a1, published=True)
b2 = Book.create(title="YugabyteDB in Practice", price=39.99,
                 author_id=a1, published=True)
b3 = Book.create(title="Database Internals", price=49.99,
                 author_id=a2, published=False)
print(f"  Created 3 books: ids {b1}, {b2}, {b3}")

books = Book.all()
print(f"  All books ({len(books)}):")
for b in books:
    print(f"    → {b['title']:<30} ${b['price']}")

published = Book.filter(published=True)
print(f"  Published books : {len(published)}")

Book.update({"published": True, "price": 44.99}, id=b3)
updated = Book.get(id=b3)
print(f"  Updated book    : {updated['title']} → ${updated['price']}")

Book.delete(id=b3)
print(f"  Deleted book id={b3}")
print(f"  Books remaining : {Book.count()}")

# ------------------------------------------------------------------ #
#  6. Cleanup                                                          #
# ------------------------------------------------------------------ #

print("\n── Cleanup ─────────────────────────────────────────────")
with db.connect() as conn:
    conn.cursor().execute("DELETE FROM books")
    conn.cursor().execute("DELETE FROM authors")
print("  All demo data removed.")

db.close()
print("\n✔ Demo complete.\n")