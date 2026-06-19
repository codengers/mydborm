# Query builder

## Filtering

```python
User.query().where("active", True).all()
User.query().where("age__gt", 18).all()
User.query().where("email__like", "%@example.com").all()
User.query().where("id__in", [1, 2, 3]).all()
```

## Operators

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
| `field__null` | `IS NULL` |

## Sorting, limit, offset

```python
User.query().order_by("username").all()
User.query().order_by("score", desc=True).limit(10).offset(20).all()
```

## Aggregates

```python
User.query().count()
User.query().where("active", True).sum("score")
User.query().avg("score")
User.query().min("score")
User.query().max("score")
```

## JOINs

```python
User.query().inner_join("orders", "users.id = orders.user_id").all()
User.query().left_join("orders", "users.id = orders.user_id").all()
```

## GROUP BY + HAVING

```python
Order.query().group_by("user_id").having("COUNT(*) > 5").all()
```

## Subqueries

```python
active_ids = User.query().where("active", True).subquery("id")
Order.query().where("user_id__in", active_ids).all()
```
