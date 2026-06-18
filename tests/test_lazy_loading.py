# -*- coding: utf-8 -*-
# =============================================================================
# File        : tests/test_lazy_loading.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.6.0
# License     : MIT
# Description : pytest tests for lazy loading (LazyRelation descriptor)
#               and eager loading (QueryBuilder.include()) with N+1
#               prevention and caching verification.
# =============================================================================

import os
import pytest
from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField
from mydborm.model import LazyRelation


# ------------------------------------------------------------------ #
#  Models                                                              #
# ------------------------------------------------------------------ #

class Publisher(BaseModel):
    __tablename__ = "ll_publishers"
    id      = IntField(primary_key=True)
    name    = StrField(max_length=100, nullable=False)
    country = StrField(max_length=50,  nullable=True)


class Writer(BaseModel):
    __tablename__ = "ll_writers"
    id           = IntField(primary_key=True)
    name         = StrField(max_length=100, nullable=False)
    active       = BoolField(default=True)
    publisher_id = IntField(nullable=True)
    books        = LazyRelation("Novel", foreign_key="writer_id")
    publisher    = LazyRelation("Publisher",
                                foreign_key="publisher_id",
                                relation_type="belongs_to")


class Novel(BaseModel):
    __tablename__ = "ll_novels"
    id        = IntField(primary_key=True)
    title     = StrField(max_length=200, nullable=False)
    price     = FloatField(nullable=False)
    writer_id = IntField(nullable=False)
    published = BoolField(default=True)


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
    Publisher.create_table()
    Writer.create_table()
    Novel.create_table()
    yield
    Novel.drop_table()
    Writer.drop_table()
    Publisher.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def clean():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM ll_novels")
        cur.execute("DELETE FROM ll_writers")
        cur.execute("DELETE FROM ll_publishers")
    yield


@pytest.fixture()
def seeded():
    p1 = Publisher.create(name="TechPress",   country="USA")
    p2 = Publisher.create(name="DevBooks",    country="UK")

    w1 = Writer.create(name="Alice", active=True,  publisher_id=p1)
    w2 = Writer.create(name="Bob",   active=True,  publisher_id=p2)
    w3 = Writer.create(name="Carol", active=False, publisher_id=None)

    n1 = Novel.create(title="Python ORM",     price=29.99, writer_id=w1)
    n2 = Novel.create(title="DB Design",      price=39.99, writer_id=w1)
    n3 = Novel.create(title="Clean Code",     price=19.99, writer_id=w2)
    n4 = Novel.create(title="Refactoring",    price=24.99, writer_id=w2)
    n5 = Novel.create(title="Design Patterns",price=34.99, writer_id=w2)

    return {
        "p1": p1, "p2": p2,
        "w1": w1, "w2": w2, "w3": w3,
        "n1": n1, "n2": n2, "n3": n3, "n4": n4, "n5": n5,
    }


# ------------------------------------------------------------------ #
#  LazyRelation descriptor                                             #
# ------------------------------------------------------------------ #

def test_lazy_relation_defined_on_class():
    assert hasattr(Writer, "books")
    assert isinstance(Writer.__dict__["books"], LazyRelation)


def test_lazy_relation_has_many_loads_on_access(seeded):
    writer = Writer.get(id=seeded["w1"])
    books  = writer.books
    assert books is not None
    assert len(books) == 2


def test_lazy_relation_correct_records(seeded):
    writer = Writer.get(id=seeded["w1"])
    titles = {b["title"] for b in writer.books}
    assert titles == {"Python ORM", "DB Design"}


def test_lazy_relation_empty_when_no_related(seeded):
    writer = Writer.get(id=seeded["w3"])
    books  = writer.books
    assert books == []


def test_lazy_relation_isolation(seeded):
    w1    = Writer.get(id=seeded["w1"])
    w2    = Writer.get(id=seeded["w2"])
    assert len(w1.books) == 2
    assert len(w2.books) == 3


# ------------------------------------------------------------------ #
#  Lazy caching                                                        #
# ------------------------------------------------------------------ #

def test_lazy_cached_on_second_access(seeded):
    writer    = Writer.get(id=seeded["w1"])
    books1    = writer.books
    cache_key = "_lazy_books"
    assert cache_key in writer._data
    books2    = writer.books
    assert books1 is books2


def test_lazy_cache_key_stored_in_data(seeded):
    writer = Writer.get(id=seeded["w1"])
    _      = writer.books
    assert "_lazy_books" in writer._data


def test_lazy_not_loaded_before_access(seeded):
    writer = Writer.get(id=seeded["w1"])
    assert "_lazy_books" not in writer._data


# ------------------------------------------------------------------ #
#  belongs_to lazy relation                                            #
# ------------------------------------------------------------------ #

def test_lazy_belongs_to_loads_parent(seeded):
    writer    = Writer.get(id=seeded["w1"])
    publisher = writer.publisher
    assert publisher is not None
    assert publisher["name"] == "TechPress"


def test_lazy_belongs_to_none_when_no_fk(seeded):
    writer    = Writer.get(id=seeded["w3"])
    publisher = writer.publisher
    assert publisher is None


def test_lazy_belongs_to_correct_parent(seeded):
    w1 = Writer.get(id=seeded["w1"])
    w2 = Writer.get(id=seeded["w2"])
    assert w1.publisher["name"] == "TechPress"
    assert w2.publisher["name"] == "DevBooks"


# ------------------------------------------------------------------ #
#  Eager loading — include()                                           #
# ------------------------------------------------------------------ #

def test_eager_include_returns_correct_count(seeded):
    writers = Writer.query().include("books").all()
    assert len(writers) == 3


def test_eager_include_preloads_books(seeded):
    writers = Writer.query().include("books").all()
    for w in writers:
        assert "_lazy_books" in w._data


def test_eager_include_correct_book_counts(seeded):
    writers = Writer.query().include("books").all()
    counts  = {w["name"]: len(w.books) for w in writers}
    assert counts["Alice"] == 2
    assert counts["Bob"]   == 3
    assert counts["Carol"] == 0


def test_eager_include_no_extra_queries(seeded):
    """
    Eager loading should fire exactly 2 queries total:
    1. SELECT * FROM ll_writers
    2. SELECT * FROM ll_novels WHERE writer_id IN (...)
    Then accessing .books on each writer fires ZERO extra queries.
    """
    query_count = [0]
    original_writer_fetch = Writer._fetch
    original_novel_fetch  = Novel._fetch

    @classmethod
    def counting_writer_fetch(cls, sql, params=None):
        query_count[0] += 1
        return original_writer_fetch.__func__(cls, sql, params)

    @classmethod
    def counting_novel_fetch(cls, sql, params=None):
        query_count[0] += 1
        return original_novel_fetch.__func__(cls, sql, params)

    Writer._fetch = counting_writer_fetch
    Novel._fetch  = counting_novel_fetch
    try:
        writers = Writer.query().include("books").all()
        # Access .books — should use cache, not fire new queries
        before = query_count[0]
        _ = [w.books for w in writers]
        after = query_count[0]
        # No extra queries after eager load
        assert after == before
        # Total queries should be exactly 2
        assert query_count[0] == 2
    finally:
        Writer._fetch = original_writer_fetch
        Novel._fetch  = original_novel_fetch

def test_eager_include_with_where(seeded):
    writers = (Writer.query()
               .where("active", True)
               .include("books")
               .all())
    assert len(writers) == 2
    for w in writers:
        assert "_lazy_books" in w._data


def test_eager_include_with_limit(seeded):
    writers = Writer.query().include("books").limit(2).all()
    assert len(writers) == 2
    for w in writers:
        assert "_lazy_books" in w._data


def test_eager_no_duplicates(seeded):
    writers = Writer.query().include("books").all()
    ids     = [w["id"] for w in writers]
    assert len(ids) == len(set(ids))


def test_eager_empty_related(seeded):
    writers = Writer.query().include("books").all()
    carol   = next(w for w in writers if w["name"] == "Carol")
    assert carol.books == []


# ------------------------------------------------------------------ #
#  LazyRelation resolution                                             #
# ------------------------------------------------------------------ #

def test_lazy_relation_resolves_model_by_name(seeded):
    descriptor = Writer.__dict__["books"]
    model      = descriptor._resolve_model(Writer)
    assert model.__name__ == "Novel"


def test_lazy_relation_raises_on_unknown_model():
    bad = LazyRelation("NonExistentModel999", foreign_key="writer_id")
    bad.attr_name = "nonexistent"
    from mydborm.model import ModelInstance
    inst = ModelInstance(Writer, {"id": 1, "name": "Test",
                                  "active": True, "publisher_id": None})
    with pytest.raises(ValueError, match="could not find model"):
        bad.__get__(inst, type(inst))


# ------------------------------------------------------------------ #
#  Combined: session + lazy loading                                    #
# ------------------------------------------------------------------ #

def test_lazy_works_with_session(seeded):
    from mydborm import Session
    with Session() as session:
        writer = session.get(Writer, id=seeded["w1"])
        books  = writer.books
        assert len(books) == 2


def test_lazy_works_after_create(seeded):
    new_id = Novel.create(
        title="New Book", price=9.99, writer_id=seeded["w1"]
    )
    writer = Writer.get(id=seeded["w1"])
    assert len(writer.books) == 3