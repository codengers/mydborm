# =============================================================================
# File        : tests/test_relationships.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.3.0
# License     : MIT
# Description : pytest tests for model relationships — has_many,
#               belongs_to, many_to_many, and ModelInstance behaviour.
# =============================================================================

import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm.model import ModelInstance


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class Author(BaseModel):
    __tablename__ = "authors"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


class Book(BaseModel):
    __tablename__ = "books"
    id        = IntField(primary_key=True)
    title     = StrField(max_length=200, nullable=False)
    author_id = IntField(nullable=False)
    price     = FloatField(nullable=False)


class Student(BaseModel):
    __tablename__ = "students"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


class Course(BaseModel):
    __tablename__ = "courses"
    id    = IntField(primary_key=True)
    title = StrField(max_length=200, nullable=False)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password="root", database="testdb"
    )

    # Drop in reverse dependency order
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS student_courses")

    for model in [Book, Author, Course, Student]:
        model.drop_table()
        model.create_table()

    # Create join table for many_to_many
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_courses (
                student_id INT NOT NULL,
                course_id  INT NOT NULL,
                PRIMARY KEY (student_id, course_id)
            ) ENGINE=InnoDB;
        """)
    yield

    with db.connect() as conn:
        conn.cursor().execute("DROP TABLE IF EXISTS student_courses")
    for model in [Book, Author, Course, Student]:
        model.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean_tables():
    """Wipe all tables before each test."""
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM student_courses")
        cur.execute("DELETE FROM books")
        cur.execute("DELETE FROM authors")
        cur.execute("DELETE FROM students")
        cur.execute("DELETE FROM courses")
    yield


# ------------------------------------------------------------------ #
#  ModelInstance behaviour                                             #
# ------------------------------------------------------------------ #

def test_get_returns_model_instance():
    aid = Author.create(name="Alice")
    a   = Author.get(id=aid)
    assert isinstance(a, ModelInstance)


def test_filter_returns_model_instances():
    Author.create(name="Alice")
    Author.create(name="Bob")
    rows = Author.all()
    assert all(isinstance(r, ModelInstance) for r in rows)


def test_dict_access():
    aid = Author.create(name="Alice")
    a   = Author.get(id=aid)
    assert a["name"] == "Alice"


def test_attribute_access():
    aid = Author.create(name="Alice")
    a   = Author.get(id=aid)
    assert a.name == "Alice"


def test_contains():
    aid = Author.create(name="Alice")
    a   = Author.get(id=aid)
    assert "name" in a
    assert "ghost" not in a


def test_keys_values_items():
    aid = Author.create(name="Alice")
    a   = Author.get(id=aid)
    assert "name" in a.keys()
    assert "Alice" in a.values()
    assert ("name", "Alice") in a.items()


def test_repr():
    aid = Author.create(name="Alice")
    a   = Author.get(id=aid)
    assert "Author" in repr(a)
    assert "Alice" in repr(a)


def test_invalid_attribute_raises():
    aid = Author.create(name="Alice")
    a   = Author.get(id=aid)
    with pytest.raises(AttributeError):
        _ = a.nonexistent_field


# ------------------------------------------------------------------ #
#  has_many                                                            #
# ------------------------------------------------------------------ #

def test_has_many_returns_related():
    aid = Author.create(name="Alice")
    Book.create(title="Book One", author_id=aid, price=9.99)
    Book.create(title="Book Two", author_id=aid, price=14.99)

    author = Author.get(id=aid)
    books  = author.has_many(Book, foreign_key="author_id")

    assert len(books) == 2
    titles = {b["title"] for b in books}
    assert titles == {"Book One", "Book Two"}


def test_has_many_empty():
    aid    = Author.create(name="Bob")
    author = Author.get(id=aid)
    books  = author.has_many(Book, foreign_key="author_id")
    assert books == []


def test_has_many_default_fk():
    aid = Author.create(name="Carol")
    Book.create(title="Carol's Book", author_id=aid, price=5.00)
    author = Author.get(id=aid)
    books  = author.has_many(Book)
    assert len(books) == 1
    assert books[0]["title"] == "Carol's Book"


def test_has_many_isolation():
    aid1 = Author.create(name="Author1")
    aid2 = Author.create(name="Author2")
    Book.create(title="A1 Book", author_id=aid1, price=1.00)
    Book.create(title="A2 Book", author_id=aid2, price=2.00)

    a1    = Author.get(id=aid1)
    books = a1.has_many(Book, foreign_key="author_id")
    assert len(books) == 1
    assert books[0]["title"] == "A1 Book"


# ------------------------------------------------------------------ #
#  belongs_to                                                          #
# ------------------------------------------------------------------ #

def test_belongs_to_returns_parent():
    aid = Author.create(name="Alice")
    bid = Book.create(title="My Book", author_id=aid, price=9.99)

    book   = Book.get(id=bid)
    author = book.belongs_to(Author, foreign_key="author_id")

    assert author is not None
    assert author["name"] == "Alice"


def test_belongs_to_default_fk():
    aid  = Author.create(name="Dave")
    bid  = Book.create(title="Dave's Book", author_id=aid, price=3.00)
    book = Book.get(id=bid)

    author = book.belongs_to(Author)
    assert author["name"] == "Dave"


def test_belongs_to_none_when_no_fk():
    """belongs_to returns None when FK value is missing."""
    bid  = Book.create(title="Orphan", author_id=0, price=1.00)
    book = Book.get(id=bid)
    result = book.belongs_to(Author, foreign_key="ghost_id")
    assert result is None


# ------------------------------------------------------------------ #
#  many_to_many                                                        #
# ------------------------------------------------------------------ #

def test_many_to_many_returns_related():
    sid = Student.create(name="Alice")
    c1  = Course.create(title="Python")
    c2  = Course.create(title="Databases")

    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO student_courses (student_id, course_id) VALUES (%s,%s)",
            [sid, c1]
        )
        cur.execute(
            "INSERT INTO student_courses (student_id, course_id) VALUES (%s,%s)",
            [sid, c2]
        )

    student = Student.get(id=sid)
    courses = student.many_to_many(
        Course,
        join_table="student_courses",
        source_key="student_id",
        target_key="course_id"
    )

    assert len(courses) == 2
    titles = {c["title"] for c in courses}
    assert titles == {"Python", "Databases"}


def test_many_to_many_empty():
    sid     = Student.create(name="Bob")
    student = Student.get(id=sid)
    courses = student.many_to_many(
        Course,
        join_table="student_courses",
        source_key="student_id",
        target_key="course_id"
    )
    assert courses == []


def test_many_to_many_isolation():
    s1  = Student.create(name="S1")
    s2  = Student.create(name="S2")
    c1  = Course.create(title="Math")
    c2  = Course.create(title="Science")

    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO student_courses VALUES (%s,%s)", [s1, c1]
        )
        cur.execute(
            "INSERT INTO student_courses VALUES (%s,%s)", [s2, c2]
        )

    student1 = Student.get(id=s1)
    courses  = student1.many_to_many(
        Course,
        join_table="student_courses",
        source_key="student_id",
        target_key="course_id"
    )
    assert len(courses) == 1
    assert courses[0]["title"] == "Math"


# ------------------------------------------------------------------ #
#  Query builder + relationships combined                              #
# ------------------------------------------------------------------ #

def test_query_then_relationship():
    aid1 = Author.create(name="Active Author")
    aid2 = Author.create(name="Another Author")
    Book.create(title="B1", author_id=aid1, price=5.00)
    Book.create(title="B2", author_id=aid1, price=10.00)
    Book.create(title="B3", author_id=aid2, price=3.00)

    authors = Author.query().where("name__like", "Active%").all()
    assert len(authors) == 1

    books = authors[0].has_many(Book, foreign_key="author_id")
    assert len(books) == 2