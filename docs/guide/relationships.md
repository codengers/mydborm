# Relationships

## has_many

```python
author = Author.get(id=1)
books  = author.has_many(Book, foreign_key="author_id")
```

## belongs_to

```python
book   = Book.get(id=1)
author = book.belongs_to(Author, foreign_key="author_id")
```

## many_to_many

```python
student = Student.get(id=1)
courses = student.many_to_many(
    Course,
    join_table = "student_courses",
    source_key = "student_id",
    target_key = "course_id"
)
```

## Lazy loading

```python
from mydborm.model import LazyRelation

class Author(BaseModel):
    __tablename__ = "authors"
    id    = IntField(primary_key=True)
    name  = StrField(max_length=100)
    books = LazyRelation("Book", foreign_key="author_id")

author = Author.get(id=1)
books  = author.books   # loaded on first access, cached after
```

## Eager loading

```python
authors = Author.query().include("books").all()
for a in authors:
    print(a.books)  # already loaded, no extra queries
```
