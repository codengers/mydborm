# Query builder

`.filter()` and `.get()` are fine for simple lookups, but as soon as you need
to combine several conditions, sort the results, page through them, or pull
in data from another table, you need something more flexible. That's what
the **query builder** is for.

You start one by calling `.query()` on a model, then chain methods onto it
to build up the query piece by piece. Nothing is sent to the database until
you call a method that actually runs it — like `.all()`, `.first()`, or
`.count()`. Up until that point you're just describing what you want:

```python
User.query().where("active", True).all()
```

Because every chain method (`.where()`, `.order_by()`, `.limit()`, ...)
returns the query builder itself, you can keep tacking more conditions onto
the end of the line, in whatever order makes sense to you.

## Filtering with `.where()`

The most common method you'll use is `.where()`. In its simplest form it
checks a column for equality:

```python
User.query().where("active", True).all()
```

This translates to `WHERE active = 1`. To do anything other than a plain
equality check — greater than, contains a substring, "is one of these
values" — append a double-underscore suffix to the field name. mydborm reads
that suffix and turns it into the matching SQL operator:

```python
User.query().where("age__gt", 18).all()
User.query().where("email__like", "%@example.com").all()
User.query().where("id__in", [1, 2, 3]).all()
```

Each call to `.where()` adds one more condition, and multiple conditions are
combined with `AND` — so `.where("active", True).where("age__gt", 18)` means
"active AND older than 18". The full set of suffixes you can use:

| Operator | SQL |
|---|---|
| `field` | `= value` |
| `field__gt` | `> value` |
| `field__lt` | `< value` |
| `field__gte` | `>= value` |
| `field__lte` | `<= value` |
| `field__ne` | `!= value` |
| `field__like` | `LIKE value` |
| `field__in` | `IN (...)` |
| `field__null` | `IS NULL` (pass `True`) or `IS NOT NULL` (pass `False`) |

### OR conditions

Everything passed to `.where()` is ANDed together. If you need "this AND
(that OR the other)", use `.or_where()` instead — it supports the same
operator suffixes as `.where()`, but groups its conditions together with
`OR` and then ANDs that whole group onto the rest of the query:

```python
Order.query()
     .where("user_id", 5)
     .or_where("status", "pending")
     .or_where("status", "retry")
     .all()
# WHERE user_id = 5 AND (status = 'pending' OR status = 'retry')
```

### Raw SQL conditions

The operator suffixes above cover most everyday filtering, but sometimes you
need a SQL expression that doesn't map to a simple `column op value` — date
functions, full-text search, JSON field extraction. `.where_raw()` is an
escape hatch for exactly that: you write the SQL fragment yourself, using
`%s` as a placeholder anywhere you need to insert a value safely (never
paste user input directly into the string):

```python
Order.query().where_raw("YEAR(created_at) = %s", 2024).all()
Post.query().where_raw("MATCH(body) AGAINST(%s IN BOOLEAN MODE)", "+python").all()

# Mixed with a normal where()
Order.query() \
     .where("user_id", 5) \
     .where_raw("DATEDIFF(NOW(), created_at) < %s", 30) \
     .all()
```

`.or_where_raw()` is the same idea, but joined with `OR` instead of `AND`,
just like `.or_where()`.

## Choosing which columns come back

By default a query returns every column. If you only need a couple of
fields, `.select()` narrows the `SELECT` clause — useful for trimming down
how much data comes back over the wire:

```python
User.query().select("id", "name").where("active", True).all()
# SELECT id, name FROM users WHERE active = 1
```

`.distinct()` adds `DISTINCT`, so you only get unique rows back (handy when
combined with `.select()` to find, say, every distinct country your users
are in):

```python
User.query().select("country").distinct().all()
```

## Sorting, limit, and offset

`.order_by()` sorts the results; pass `desc=True` to sort descending instead
of the default ascending. `.limit()` caps how many rows come back, and
`.offset()` skips a number of rows before collecting them — the two
together are how you implement "page 3 of results":

```python
User.query().order_by("username").all()
User.query().order_by("score", desc=True).limit(10).offset(20).all()
```

If you're paging through results often, see `.paginate()` below — it
wraps limit/offset into a single call that also tells you how many pages
there are in total.

## Aggregates

When you want a single number back instead of a list of rows — a count, a
total, an average — use one of the aggregate methods. These run the query
and return a plain Python value, not a list:

```python
User.query().count()
User.query().where("active", True).sum("score")
User.query().avg("score")
User.query().min("score")
User.query().max("score")
```

`.exists()` is a shortcut for "does at least one row match?" — it's cheaper
than fetching rows yourself just to check if the list is empty:

```python
User.query().where("email", "a@example.com").exists()  # True / False
```

`.first()` runs the query with an implicit `LIMIT 1` and returns either the
single matching row or `None`, which is handy when you expect at most one
result but don't want to write `.limit(1).all()[0]` and handle the empty-list
case yourself.

## JOINs

A JOIN lets you pull in columns from a related table in the same query,
instead of querying it separately and stitching the results together in
Python. `.inner_join()` only returns rows that have a match in both tables;
`.left_join()` keeps every row from the left-hand table even if there's no
matching row on the right (missing columns come back as `NULL`):

```python
User.query().inner_join("orders", "users.id = orders.user_id").all()
User.query().left_join("orders", "users.id = orders.user_id").all()
```

`.right_join()` is also available for the mirror-image case. The second
argument to each is the join condition — the SQL that says how the two
tables relate.

## GROUP BY + HAVING

`.group_by()` collapses rows that share the same value in a column into a
single group — typically so you can run an aggregate (like `COUNT`) per
group instead of over the whole table. `.having()` then filters *those
groups* (as opposed to `.where()`, which filters individual rows before
grouping happens):

```python
Order.query().group_by("user_id").having("COUNT(*) > 5").all()
```

That example reads as: "group orders by user, then only keep the users who
have more than 5 orders."

## Subqueries

A subquery is a query nested inside another query — useful when the list of
values you want to filter by isn't something you already have in Python,
but is itself the result of a database lookup. `.subquery()` turns a query
builder chain into a SQL fragment you can drop into another `.where()` call
instead of running it and collecting the results yourself:

```python
active_ids = User.query().where("active", True).subquery("id")
Order.query().where("user_id__in", active_ids).all()
```

This runs as a single SQL statement — "orders belonging to any currently
active user" — rather than first fetching all active user IDs into Python
and then querying orders with that list.

## Bulk update and delete

`.update()` and `.delete()` run directly against whatever rows the rest of
the chain matches, without you having to load them into Python first:

```python
User.query().where("active", False).update(role="guest")
User.query().where("status", "cancelled").delete()
```

Both return the number of rows affected.

## Pagination helper

If you're building something like a paginated table or API endpoint,
`.paginate()` saves you from manually juggling `.limit()`/`.offset()` and a
separate `.count()` call — it returns the page of data plus the metadata you
need to render "page 2 of 7":

```python
result = User.query().where("active", True).paginate(page=2, per_page=20)
# {"data": [...], "total": 137, "page": 2, "per_page": 20, "pages": 7}
```
