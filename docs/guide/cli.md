# CLI

## Commands

```bash
# Show version
mydborm version

# Test connectivity
mydborm ping --dialect mysql --host 127.0.0.1 --port 3306 --password root

# List tables
mydborm tables --dialect mysql --database mydb --password root

# Inspect schema
mydborm inspect --dialect mysql --database mydb --password root

# Migration status
mydborm migrate --dialect mysql --database mydb --password root --status

# Apply migration
mydborm migrate --dialect mysql --database mydb --password root \
                --model myapp.models.User

# Generate migration file
mydborm generate --dialect mysql --database mydb --password root \
                 --model myapp.models.User --output migrations/

# Connection pool status
mydborm pool --dialect mysql --database mydb --password root
```
