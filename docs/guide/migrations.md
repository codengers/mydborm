# Migrations

## Apply migration

```python
from mydborm.migrations import migrate, migration_status, rollback

migrate(User, description="create users table")
```

## Check status

```python
for m in migration_status():
    print(m["version"], m["description"], m["applied_at"])
```

## Rollback

```python
rollback(User)
```

## Auto-generate SQL files

```python
from mydborm.migrations import generate, apply_migration_file

result = generate(User, output_dir="migrations/")
print(result["file"])  # migrations/0001_user.sql

apply_migration_file("migrations/0001_user.sql")
```

## CLI

```bash
mydborm migrate --dialect mysql --status
mydborm generate --model myapp.models.User --output migrations/
mydborm generate --model myapp.models.User --apply
```
