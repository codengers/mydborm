# Relationships

Real data is rarely just one flat table. An author has books, a book has
one author, and a student is enrolled in many courses while each course has
many students. **Relationships** are how mydborm lets you navigate between
related rows without writing a JOIN by hand every time — you call a method
(or access an attribute) on one model instance and get back the related
row or rows.

There are three shapes of relationship, matching the three common ways
tables refer to each other:

- **has_many** — one row relates to many rows in another table (one author,
  many books)
- **belongs_to** — the reverse: one row points back to a single parent row
  (a book belongs to one author)
- **many_to_many** — rows on both sides can relate to multiple rows on the
  other side, via a separate join table (students and courses)

## has_many

Use `has_many` when the *other* table has a foreign key column pointing
back at this one — for example, a `books` table with an `author_id` column.
Calling `.has_many()` on an author instance fetches every book whose
`author_id` matches that author's primary key:

```python
author = Author.get(id=1)
books  = author.has_many(Book, foreign_key="author_id")
```

`foreign_key` tells mydborm which column on the *related* table (`Book`) to
match against this instance's id. If you don't pass it, mydborm guesses
`<this_model_name>_id` — so for `Author` it would assume `author_id` — but
it's good practice to spell it out so the code stays readable.

## belongs_to

`belongs_to` is the mirror image — use it on the table that *holds* the
foreign key, to fetch the single parent row it points to:

```python
book   = Book.get(id=1)
author = book.belongs_to(Author, foreign_key="author_id")
```

Here `foreign_key` is the column on `Book` itself (the side you're calling
this from) that stores the related author's id. If omitted, mydborm guesses
`<related_model_name>_id`, i.e. `author_id` for a call to
`belongs_to(Author)`.

## many_to_many

Some relationships can't be expressed with a single foreign key on either
side — a student can take many courses, and a course can have many
students. These need a **join table** (sometimes called an "association
table") that just stores pairs of ids, one row per student/course
combination:

```python
student = Student.get(id=1)
courses = student.many_to_many(
    Course,
    join_table = "student_courses",
    source_key = "student_id",
    target_key = "course_id"
)
```

`join_table` is the name of that link table. `source_key` is the column in
the join table that refers back to *this* model (`Student`), and
`target_key` is the column that refers to the model you're fetching
(`Course`). Both default to `<model_name>_id` if you leave them out, but as
with `has_many`/`belongs_to`, naming them explicitly avoids surprises.

## Lazy loading

The relationship calls above (`has_many`, `belongs_to`, `many_to_many`) run
a query immediately, every time you call them. **Lazy loading** is a
slightly different pattern: you declare the relationship once as part of
the model, and the actual database query only happens the first time you
*access* the attribute — not when the object is loaded. After that first
access, the result is cached on the instance, so accessing it again doesn't
re-run the query:

```python
from mydborm.model import LazyRelation

class Author(BaseModel):
    __tablename__ = "authors"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100)
    books = LazyRelation("Book", foreign_key="author_id")

author = Author.get(id=1)
books  = author.books   # query runs here, on first access
books  = author.books   # second access — returns the cached list, no new query
```

This is convenient because `Author.get(id=1)` stays a cheap, single-table
query — you only pay for loading `books` if your code actually asks for it.

## Eager loading

Lazy loading has a downside if you're not careful: if you load a list of
50 authors and then access `.books` on each one inside a loop, that's 50
separate queries — one per author — on top of the original query that
fetched the authors. This is known as the **N+1 query problem**, and it's
one of the most common performance mistakes when working with an ORM.

**Eager loading** solves this by fetching the related rows for *all* the
authors in one extra query, up front, instead of one query per author.
You ask for it with `.include()` on the query builder, naming the relation
you want preloaded:

```python
authors = Author.query().include("books").all()
for a in authors:
    print(a.books)  # already loaded — no extra queries inside the loop
```

`.include()` only works with relations declared as `LazyRelation` on the
model (like `books` above) — it looks up that descriptor, runs one batched
query for every author in the result set, and attaches each author's books
before you ever start the loop. The rule of thumb: if you're going to
access a relationship for every row in a list, eager-load it with
`.include()`; if you only need it occasionally, lazy loading is simpler and
avoids fetching data you might not use.
