# mydborm benchmark results

**Date:** 2026-06-19 08:31:02  
**MySQL:** 127.0.0.1:3307/testdb  
**Rows:** 1000 | Bulk rows: 5000 | Runs: 3  

| Operation | mydborm | SQLAlchemy | Peewee | Winner |
|---|---|---|---|---|
| Single insert x1000 | 11.0355s | 4.0917s | 7.832s | SQLAlchemy |
| Bulk insert x5000 | 0.2425s | 0.3104s | 0.4065s | mydborm |
| Select all x1000 | 0.0322s | 0.01s | 0.119s | SQLAlchemy |
| Filter x1000 | 0.0228s | 0.0074s | 0.1029s | SQLAlchemy |
| Update x1000 | 0.0107s | 0.0134s | 0.0072s | Peewee |

mydborm wins: 1/5 operations

## YugabyteDB vs MySQL (mydborm)

| Operation | MySQL | YugabyteDB | Faster |
|---|---|---|---|
| Single insert x1000 | 11.0355s | 8.3537s | YugabyteDB |
| Bulk insert x5000 | 0.2425s | 0.4482s | MySQL |
| Select all x1000 | 0.0322s | 0.0602s | MySQL |
| Filter x1000 | 0.0228s | 0.0554s | MySQL |
| Update x1000 | 0.0107s | 0.2185s | MySQL |
