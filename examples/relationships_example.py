# =============================================================================
# File        : examples/relationships_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Relationships demo — has_many, belongs_to, many_to_many,
#               plus lazy loading (LazyRelation, loaded on first access)
#               vs eager loading (.include(), loaded up front to avoid
#               the N+1 query problem).
# =============================================================================

from mydborm import db, BaseModel, IntField, StrField, FloatField
from mydborm.model import LazyRelation

db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3307,
    user     = "root",
    password = "root",
    database = "testdb",
)


class RelAuthor(BaseModel):
    __tablename__ = "rel_authors"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)
    # LazyRelation only fetches "rel_books" the first time .books is
    # accessed on an instance — and only for that one instance.
    books = LazyRelation("RelBook", foreign_key="author_id")


class RelBook(BaseModel):
    __tablename__ = "rel_books"
    id        = IntField(primary_key=True)
    title     = StrField(max_length=200, nullable=False)
    price     = FloatField(nullable=False)
    author_id = IntField(nullable=False)


class RelStudent(BaseModel):
    __tablename__ = "rel_students"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


class RelCourse(BaseModel):
    __tablename__ = "rel_courses"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


class RelEnrollment(BaseModel):
    # The join table for the many-to-many relationship below.
    __tablename__ = "rel_enrollments"
    student_id = IntField(nullable=False)
    course_id  = IntField(nullable=False)


def main():
    print("=" * 60)
    print("  mydborm — Relationships demo")
    print("=" * 60)

    for model in [RelAuthor, RelBook, RelStudent, RelCourse, RelEnrollment]:
        model.create_table()
    with db.connect() as conn:
        for table in ["rel_enrollments", "rel_books", "rel_authors",
                      "rel_students", "rel_courses"]:
            conn.cursor().execute(f"DELETE FROM {table}")

    # ------------------------------------------------------------------ #
    #  has_many() / belongs_to() — one-to-many, called explicitly         #
    # ------------------------------------------------------------------ #
    print("\n── has_many() / belongs_to() ────────────────────────────")

    alice = RelAuthor.create(name="Alice")
    RelBook.create(title="Python ORM Patterns",   price=29.99, author_id=alice)
    RelBook.create(title="YugabyteDB in Practice", price=39.99, author_id=alice)

    author = RelAuthor.get(id=alice)
    books  = author.has_many(RelBook, foreign_key="author_id")
    print(f"  {author['name']}'s books: {[b['title'] for b in books]}")

    one_book = RelBook.get(id=books[0]["id"])
    parent   = one_book.belongs_to(RelAuthor, foreign_key="author_id")
    print(f"  '{one_book['title']}' belongs to: {parent['name']}")

    # ------------------------------------------------------------------ #
    #  many_to_many() — through a join table                              #
    # ------------------------------------------------------------------ #
    print("\n── many_to_many() ───────────────────────────────────────")

    bob    = RelStudent.create(name="Bob")
    math   = RelCourse.create(name="Math 101")
    physics = RelCourse.create(name="Physics 101")
    RelEnrollment.create(student_id=bob, course_id=math)
    RelEnrollment.create(student_id=bob, course_id=physics)

    student = RelStudent.get(id=bob)
    courses = student.many_to_many(
        RelCourse,
        join_table="rel_enrollments",
        source_key="student_id",
        target_key="course_id",
    )
    print(f"  {student['name']} is enrolled in: {[c['name'] for c in courses]}")

    # ------------------------------------------------------------------ #
    #  Lazy loading — LazyRelation fetches on first attribute access      #
    # ------------------------------------------------------------------ #
    print("\n── Lazy loading ─────────────────────────────────────────")

    carol = RelAuthor.create(name="Carol")
    RelBook.create(title="Distributed SQL Basics", price=24.99, author_id=carol)

    carol_obj = RelAuthor.get(id=carol)
    print("  Accessing .books for the first time runs a query now:")
    print(f"    {[b['title'] for b in carol_obj.books]}")
    print("  Accessing .books again reuses the cached result — no new query.")
    print(f"    {[b['title'] for b in carol_obj.books]}")

    # ------------------------------------------------------------------ #
    #  Eager loading — .include() avoids the N+1 query problem            #
    # ------------------------------------------------------------------ #
    print("\n── Eager loading with .include() ────────────────────────")

    # Without .include(), looping over authors and reading .books would
    # run one extra query PER author (the "N+1 query problem" — 1 query
    # for the authors, then N more for each author's books).
    # .include() instead loads every author's books in a single extra
    # query, then hands out the cached results as you access .books.
    authors = RelAuthor.query().include("books").all()
    print(f"  Loaded {len(authors)} authors with their books pre-fetched:")
    for a in authors:
        print(f"    {a['name']}: {[b['title'] for b in a.books]}")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    with db.connect() as conn:
        for table in ["rel_enrollments", "rel_books", "rel_authors",
                      "rel_students", "rel_courses"]:
            conn.cursor().execute(f"DELETE FROM {table}")
            conn.cursor().execute(f"DROP TABLE {table}")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
