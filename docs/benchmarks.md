# Benchmarks

## mydborm vs SQLAlchemy vs Peewee (MySQL)

| Operation | mydborm | SQLAlchemy | Peewee | Winner |
|---|---|---|---|---|
| Single insert x1000 | 11.0s | 4.1s | 7.8s | SQLAlchemy |
| Bulk insert x5000 | 0.24s | 0.29s | 0.33s | **mydborm** |
| Select all x1000 | 0.032s | 0.010s | 0.119s | SQLAlchemy |
| Filter x1000 | 0.023s | 0.007s | 0.103s | SQLAlchemy |
| Update x1000 | 0.011s | 0.013s | 0.007s | Peewee |

## mydborm: MySQL vs YugabyteDB

| Operation | MySQL | YugabyteDB | Faster |
|---|---|---|---|
| Single insert x1000 | 11.0s | 8.4s | YugabyteDB |
| Bulk insert x5000 | 0.24s | 0.45s | MySQL |
| Select all x1000 | 0.032s | 0.060s | MySQL |
| Update x1000 | 0.011s | 0.219s | MySQL |

## Key takeaway

Use `bulk_create()` for large datasets — mydborm is the fastest at bulk inserts.
For single-row inserts, wrap in `db.transaction()` for a 3x speedup.