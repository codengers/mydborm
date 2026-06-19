## YugabyteDB vs MySQL (mydborm)

| Operation | MySQL | YugabyteDB | Faster |
|---|---|---|---|
| Single insert x1000 | 11.04s | 8.35s | YugabyteDB |
| Bulk insert x5000 | 0.24s | 0.45s | MySQL |
| Select all x1000 | 0.032s | 0.060s | MySQL |
| Filter x1000 | 0.023s | 0.055s | MySQL |
| Update x1000 | 0.011s | 0.219s | MySQL |

### Analysis
- MySQL wins on bulk ops, selects, and updates — expected for a single-node DB
- YugabyteDB wins on single inserts — RETURNING id + YSQL optimizations
- YugabyteDB update (0.219s) is slower due to distributed consensus on write
- For read-heavy workloads: MySQL is 2x faster
- For write-heavy distributed workloads: YugabyteDB scales horizontally

### When to use each
- **MySQL** — single-node, read-heavy, bulk operations
- **YugabyteDB** — distributed, geo-redundant, PostgreSQL compatibility needed