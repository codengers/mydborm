# Transactions

## Basic transaction

```python
with db.transaction():
    db.execute("INSERT INTO users (username) VALUES (%s)", ["alice"])
    db.execute("INSERT INTO profiles (user_id) VALUES (%s)", [1])
```

## Savepoints

```python
with db.transaction():
    User.create(username="alice")
    try:
        with db.savepoint("after_alice"):
            User.create(username="bob")
            raise Exception("bob failed")
    except Exception:
        pass  # only bob rolled back
```

## Bulk transaction

```python
with db.bulk_transaction():
    db.execute("INSERT INTO orders ...")
    db.execute("INSERT INTO order_items ...")
```

## Nested transactions

```python
with db.transaction():
    User.create(username="outer")
    with db.nested_transaction():
        User.create(username="inner")
```

## Retry on deadlock

```python
with db.transaction_with_retry(retries=3):
    db.execute("UPDATE accounts SET balance = balance - 100 ...")
    db.execute("UPDATE accounts SET balance = balance + 100 ...")
```
