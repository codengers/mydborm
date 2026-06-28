# mydborm — Claude Code Project File

> This file gives Claude Code full context about the mydborm project so it can
> autonomously read, edit, test, and commit code without asking repeated questions.

---

## Project identity

- **Name**: mydborm
- **Type**: Python ORM library (PyPI package)
- **PyPI**: https://pypi.org/project/mydborm/
- **GitHub**: https://github.com/codengers/mydborm
- **Docs**: https://codengers.github.io/mydborm/
- **Author**: Atikrant Upadhye — GitHub: codengers
- **License**: MIT
- **Current version**: 1.10.1
- **Python**: 3.9, 3.10, 3.11, 3.12
- **OS**: Windows 11, VSCode

---

## Response style

- Keep responses concise — lead with the result, not a narration of every step taken.
- When running tests, builds, or other commands with long output, summarize rather
  than pasting the full log: report pass/fail counts and only the relevant failure
  lines, not the entire output.
- Don't repeat information already visible in a tool result back to the user unless
  it changes what they need to do next.

---

## What this project is

mydborm is a **lightweight, production-grade Python ORM** for MySQL 8+,
YugabyteDB (YSQL), and PostgreSQL. It provides:

- Declarative model definitions with 29 field types
- Full CRUD with QueryBuilder (WHERE, JOIN, GROUP BY, subqueries)
- Relationships: has_many, belongs_to, many_to_many
- Lazy + eager loading, identity map, change tracking (Session)
- Schema migrations + auto-generation
- Bulk operations with chunking + retry + progress callbacks
- 6 custom validators (email, URL, regex, range, length, choice)
- PasswordField (bcrypt) + EncryptedField (AES) security fields
- SoftDeleteMixin, AuditMixin, TimestampMixin
- Lifecycle hooks (before/after create/update/delete)
- Index management (auto + composite + runtime)
- Composite primary keys
- PostgreSQL dialect (in addition to MySQL + YugabyteDB)
- Async support (aiomysql + aiopg)
- Connection pooling
- Database-to-database migration engine (MigrationEngine, ObjectMigrator, TypeMapper)
- Rich CLI (8 commands)
- 1094 tests, 96% coverage

---

## Repository structure

```
mydborm/
├── mydborm/                   # Source package
│   ├── __init__.py            # All public exports
│   ├── db.py                  # ConnectionManager, pooling, transactions
│   ├── fields.py              # 29 field types + validators
│   ├── model.py               # ModelMeta, BaseModel, QueryBuilder, ModelInstance
│   ├── bulk.py                # BulkResult, chunked_bulk_*
│   ├── async_db.py            # AsyncConnectionManager, AsyncBaseModel
│   ├── migrations.py          # migrate(), generate(), apply_migration_file() — single-DB schema migrations
│   ├── migrate.py             # MigrationEngine, ObjectMigrator, TypeMapper — database-to-database migration
│   ├── exceptions.py          # 24 custom exception types
│   ├── session.py             # Session, ObjectState, TrackedInstance
│   ├── mixins.py              # SoftDeleteMixin, AuditMixin, TimestampMixin
│   ├── cli.py                 # Typer CLI
│   └── dialects/
│       ├── __init__.py        # get_dialect() registry
│       ├── mysql.py           # MySQLDialect
│       ├── yugabyte.py        # YugabyteDialect
│       └── postgres.py        # PostgreSQLDialect
├── tests/                     # 1094 tests, 96% coverage
├── docs/                      # MkDocs documentation
├── benchmarks/                # Performance benchmarks
├── examples/                  # Runnable usage examples (one script per topic)
├── .github/workflows/         # CI/CD (ci.yml)
├── docker-compose.yml         # MySQL + YugabyteDB + PostgreSQL
├── pyproject.toml             # Package config + dependencies
└── mkdocs.yml                 # Documentation config
```

---

## Environment setup

### Virtual environment

```powershell
# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Install all dependencies
pip install -e ".[dev,cli,async,security]"
```

### Database setup

| Database | Port | User | Password | Database |
|---|---|---|---|---|
| MySQL (Docker) | 3307 | root | root | testdb |
| YugabyteDB (Docker) | 5433 | yugabyte | yugabyte | yugabyte |
| PostgreSQL | 5432 | postgres | postgres | postgres |

> Note: Local MySQL occupies port 3306, so Docker MySQL uses 3307.

Environment variables:
- `DB_PASSWORD` — MySQL password (default: `root`)
- `YB_PASSWORD` — YugabyteDB password (default: `yugabyte`)

Start databases:
```powershell
docker compose up -d
```

### Verify setup

```powershell
pytest tests/ -q
# Expected: 1094 passed, 4 skipped (skips are PostgreSQL-port-unavailable guards)
```

---

## Running tests

```powershell
# Full suite
pytest tests/

# With coverage
pytest tests/ --cov=mydborm --cov-report=term-missing

# Specific file
pytest tests/test_model.py -v

# Specific test
pytest tests/test_model.py::test_create_returns_id -v

# Fast — skip slow async tests
pytest tests/ -k "not async" -q
```

### Test files map

| File | Tests for |
|---|---|
| `test_connection.py` | db.configure, from_env, pool, transactions |
| `test_pool.py` | Connection pool sizing, status, ping |
| `test_fields.py` | Core 10 field types + validation |
| `test_model.py` | BaseModel, CRUD, ModelInstance |
| `test_query_builder.py` | WHERE, JOIN, GROUP BY, subquery, aggregates |
| `test_group_by.py` | group_by/having aggregation paths |
| `test_raw_sql.py` | where_raw(), or_where_raw() |
| `test_relationships.py` | has_many, belongs_to, many_to_many |
| `test_lazy_loading.py` | LazyRelation, eager loading via .include() |
| `test_bulk.py` | bulk_create, bulk_update, bulk_delete, upsert |
| `test_chunked_bulk.py` | BulkResult, chunked ops, retry, progress |
| `test_upsert_joins.py` | bulk_upsert(), join-based queries |
| `test_transactions.py` | transaction, savepoints, nested, retry |
| `test_session.py` | Session, identity map, change tracking |
| `test_validators.py` | All 6 validators + custom validators |
| `test_extended_fields.py` | 17 extended field types |
| `test_password_field.py` | PasswordField + EncryptedField |
| `test_mixins.py` | SoftDeleteMixin, AuditMixin, TimestampMixin |
| `test_lifecycle_hooks.py` | before/after create/update/delete |
| `test_index_management.py` | Auto indexes, composite indexes, MySQL + YugabyteDB |
| `test_composite_keys.py` | __pk__, composite PK CRUD, MySQL + YugabyteDB |
| `test_postgresql.py` | PostgreSQL dialect (skipped if port 5432 unavailable) |
| `test_yugabyte.py` | YugabyteDB live tests (skipped if port 5433 unavailable) |
| `test_dialects.py` | MySQL + YugabyteDB + PostgreSQL SQL generation |
| `test_migrations.py` | migrate(), migration_status(), rollback() — single-DB schema migrations |
| `test_auto_migrations.py` | generate(), apply_migration_file() |
| `test_db_migration.py` | MigrationEngine, ObjectMigrator, TypeMapper — database-to-database migration |
| `test_cli.py` | All 8 CLI commands |
| `test_async.py` | AsyncBaseModel, AsyncConnectionManager |
| `test_serialization.py` | to_dict, to_json, from_dict |
| `test_exceptions.py` | All 24 exception types |

---

## Git workflow

```
main         ← branch protected — all work (features, fixes, releases) PRs into here
feature/*    ← new features
fix/*        ← bug fixes
chore/*      ← version bumps, maintenance
docs/*       ← documentation-only changes
```

> Note: a `develop` branch exists in the repo's history but is not part of the
> active workflow — it's dozens of commits behind `main` with nothing unique on
> it. Branch from `main`, not `develop`.

### Create a feature branch

```powershell
git checkout main
git pull origin main
git checkout -b feature/my-feature
git push -u origin feature/my-feature
```

### Commit convention

```
feat: short description         # new feature
fix: short description          # bug fix
test: short description         # tests only
refactor: short description     # no behavior change
docs: short description         # documentation
bump: version X.Y.Z -> A.B.C   # version bump
chore: short description        # maintenance
```

### Release process

Confirm CI is green at each gate below before moving to the next step —
especially before pushing the tag, since that triggers an automatic PyPI
publish and PyPI does not allow re-uploading or deleting a published version.

```powershell
# 1. Bump version in pyproject.toml and mydborm/__init__.py, on its own branch
git checkout main
git pull origin main
git checkout -b chore/bump-vX.Y.Z
git add pyproject.toml mydborm/__init__.py
git commit -m "bump: version 1.10.0 -> 1.10.1"
git push -u origin chore/bump-vX.Y.Z

# 2. Open a PR into main and wait for CI to pass
gh pr create --fill
gh pr checks <pr-number>          # confirm all required checks are green

# 3. Merge, then tag from main — only once CI on main itself is also green
gh pr merge <pr-number> --squash --delete-branch
git checkout main
git pull origin main
git tag v1.10.1
git push origin v1.10.1
# Pushing the tag triggers the "Publish to PyPI" GitHub Action automatically.
```

---

## Key design decisions

### Field system

Every field inherits from `Field` base class. Field types implement:
- `validate(value)` — coerce and validate, raise TypeError/ValueError
- `to_sql_def(dialect)` — return SQL column definition string

```python
class IntField(Field):
    sql_type = "INT"

    def validate(self, value):
        value = super().validate(value)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                raise TypeError(f"Field '{self.name}' expects int, got {type(value).__name__}.")
        return value
```

### Dialect system

All SQL generation is dialect-aware via static method classes:

```python
get_dialect("mysql")      → MySQLDialect      # backtick identifiers, AUTO_INCREMENT
get_dialect("yugabyte")   → YugabyteDialect   # double-quote identifiers, SERIAL, JSONB
get_dialect("postgres")   → PostgreSQLDialect # same as YugabyteDialect, port 5432
```

### Mixin injection (MRO workaround)

Mixins use `__init_subclass__` to inject methods directly onto the subclass,
bypassing Python's MRO which would prefer `BaseModel.all()` over `SoftDeleteMixin.all()`:

```python
class SoftDeleteMixin:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Inject methods directly onto subclass
        cls.all    = classmethod(SoftDeleteMixin.all.__func__)
        cls.filter = classmethod(SoftDeleteMixin.filter.__func__)
        # ...
```

### Lifecycle hooks

No registration needed — hooks are detected via `hasattr` at runtime:

```python
# In BaseModel.create()
if hasattr(cls, "before_create") and callable(getattr(cls, "before_create")):
    result = cls.before_create(validated)
    if result is not None:
        validated = result
```

### Composite PK

Declared via `__pk__ = ("col1", "col2")` tuple. `ModelMeta` stores it as
`_composite_pk`. The `create()` method returns a dict of PK values instead of int.

---

## Coverage targets

Current: **96%** (1094 tests). Target of 95%+ already met — when adding new
code, check `--cov-report=term-missing` for the specific lines your change
introduces rather than chasing a fixed gap list (the exact missing lines
shift release to release).

Run coverage check:
```powershell
pytest tests/ --cov=mydborm --cov-report=term-missing -q 2>$null | Select-String "TOTAL"
```

---

## Common tasks for Claude Code

### Add a new field type

1. Open `mydborm/fields.py`
2. Add class inheriting from `Field`
3. Implement `validate()` and set `sql_type`
4. Add dialect overrides if MySQL ≠ YugabyteDB
5. Export from `mydborm/__init__.py`
6. Add tests to `tests/test_extended_fields.py`

### Add a new CLI command

1. Open `mydborm/cli.py`
2. Add `@cli.command()` function (the Typer instance in `cli.py` is named `cli`, not `app`)
3. Add tests to `tests/test_cli.py` using `CliRunner`

### Add a new dialect

1. Create `mydborm/dialects/newdialect.py`
2. Subclass `YugabyteDialect` or `MySQLDialect`
3. Register in `mydborm/dialects/__init__.py`
4. Add connection handling in `mydborm/db.py`

### Fix a coverage gap

1. Run: `pytest tests/ --cov=mydborm --cov-report=term-missing -q`
2. Identify missing lines in output
3. Read the source lines: `Get-Content mydborm\file.py | Select-Object -Skip N -First M`
4. Write a targeted test that exercises that code path
5. Verify: `pytest tests/test_file.py --cov=mydborm/file.py --cov-report=term-missing`

### Bump version and release

See [Release process](#release-process) above for the full command sequence.
Summary: bump `version` in `pyproject.toml` and `__version__` in
`mydborm/__init__.py` on a `chore/bump-vX.Y.Z` branch off `main`, PR into
`main`, confirm CI is green, merge, then tag and push the tag from `main` —
the tag push triggers PyPI publish automatically, no manual approval step.

---

## pyproject.toml summary

```toml
[project]
name    = "mydborm"
version = "1.10.1"
requires-python = ">=3.8"

dependencies = [
    "mysql-connector-python>=8.0",
    "psycopg2-binary>=2.9",
]

[project.optional-dependencies]
cli      = ["typer>=0.9", "rich>=13.0"]
ui       = ["streamlit>=1.30"]
async    = ["aiomysql>=0.3", "aiopg>=1.4"]
security = ["bcrypt>=4.0", "cryptography>=41.0"]
dev      = ["pytest>=7", "pytest-cov", "pytest-asyncio>=0.23", "ruff", ...]
```

---

## DO NOT

- Push directly to `main` — branch protection enforced
- Use PowerShell for multi-line Python strings (quote mangling) — use `.py` files
- Double-quote identifiers with MySQL (use backticks)
- Use backtick identifiers with YugabyteDB/PostgreSQL (use double-quotes)
- Hardcode encryption keys or passwords
- Use `dict | None` syntax — use `Optional[dict]` for Python 3.9 compat
- Skip tests when adding features — every feature needs tests

---

## Quick commands reference

```powershell
# Test
pytest tests/ -q
pytest tests/ --cov=mydborm --cov-report=term-missing -q

# Lint
ruff check mydborm/

# Build docs
mkdocs serve
mkdocs gh-deploy --force

# Build package
python -m build

# Check PyPI versions
pip index versions mydborm

# Install local editable
pip install -e ".[dev,cli,async,security]"
```
