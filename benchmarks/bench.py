# -*- coding: utf-8 -*-
# =============================================================================
# File        : benchmarks/bench.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-19
# Version     : 0.8.0
# License     : MIT
# Description : Performance benchmarks comparing mydborm vs SQLAlchemy
#               vs Peewee on MySQL 8. Measures insert, select, bulk
#               insert, filter, and update operations.
# =============================================================================

import os
import time
import statistics
from tabulate import tabulate

# ------------------------------------------------------------------ #
#  Config                                                              #
# ------------------------------------------------------------------ #

DB_HOST     = "127.0.0.1"
DB_PORT     = 3307
DB_USER     = "root"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "root")
DB_NAME     = "testdb"
ROWS        = 1000
BULK_ROWS   = 5000
RUNS        = 3

print(f"mydborm benchmark suite")
print(f"MySQL {DB_HOST}:{DB_PORT}/{DB_NAME}")
print(f"Rows: {ROWS} | Bulk rows: {BULK_ROWS} | Runs: {RUNS}")
print("=" * 60)

# ------------------------------------------------------------------ #
#  mydborm setup                                                       #
# ------------------------------------------------------------------ #

from mydborm import db, BaseModel, IntField, StrField, BoolField, FloatField

db.configure(
    dialect  = "mysql",
    host     = DB_HOST,
    port     = DB_PORT,
    user     = DB_USER,
    password = DB_PASSWORD,
    database = DB_NAME,
    charset  = "utf8mb4",
)

class BenchUser(BaseModel):
    __tablename__ = "bench_users"
    id       = IntField(primary_key=True)
    username = StrField(max_length=100, nullable=False)
    email    = StrField(max_length=255, nullable=False)
    active   = BoolField(default=True)
    score    = FloatField(nullable=False)


# ------------------------------------------------------------------ #
#  SQLAlchemy setup                                                    #
# ------------------------------------------------------------------ #

from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float
from sqlalchemy.orm import DeclarativeBase, Session as SASession

SA_URL = (
    f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
sa_engine = create_engine(SA_URL, echo=False)

class SABase(DeclarativeBase):
    pass

class SAUser(SABase):
    __tablename__ = "bench_sa_users"
    id       = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False)
    email    = Column(String(255), nullable=False)
    active   = Column(Boolean, default=True)
    score    = Column(Float, nullable=False)


# ------------------------------------------------------------------ #
#  Peewee setup                                                        #
# ------------------------------------------------------------------ #

from peewee import MySQLDatabase, Model, IntegerField, CharField, BooleanField, FloatField as PWFloat

pw_db = MySQLDatabase(
    DB_NAME,
    host     = DB_HOST,
    port     = DB_PORT,
    user     = DB_USER,
    password = DB_PASSWORD,
)

class PWUser(Model):
    username = CharField(max_length=100)
    email    = CharField(max_length=255)
    active   = BooleanField(default=True)
    score    = PWFloat()

    class Meta:
        database   = pw_db
        table_name = "bench_pw_users"


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

def timeit(fn, runs=RUNS):
    """Run fn() multiple times, return mean seconds."""
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return round(statistics.mean(times), 4)


def setup_tables():
    """Create all benchmark tables."""
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS bench_users")
        cur.execute("DROP TABLE IF EXISTS bench_sa_users")
        cur.execute("DROP TABLE IF EXISTS bench_pw_users")

    BenchUser.create_table()
    SABase.metadata.create_all(sa_engine)
    pw_db.connect(reuse_if_open=True)
    pw_db.create_tables([PWUser], safe=True)


def teardown_tables():
    """Drop all benchmark tables."""
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS bench_users")
        cur.execute("DROP TABLE IF EXISTS bench_sa_users")
        cur.execute("DROP TABLE IF EXISTS bench_pw_users")
    pw_db.close()


def clean_tables():
    with db.connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM bench_users")
        cur.execute("DELETE FROM bench_sa_users")
        cur.execute("DELETE FROM bench_pw_users")


def make_records(n):
    return [
        {"username": f"user{i}", "email": f"user{i}@example.com",
         "active": True, "score": float(i)}
        for i in range(n)
    ]


# ------------------------------------------------------------------ #
#  Benchmarks                                                          #
# ------------------------------------------------------------------ #

setup_tables()
results = []


# ── 1. Single insert ──────────────────────────────────────────────

def mydborm_insert():
    clean_tables()
    for i in range(ROWS):
        BenchUser.create(
            username=f"u{i}", email=f"u{i}@x.com",
            active=True, score=float(i)
        )

def sa_insert():
    clean_tables()
    with SASession(sa_engine) as session:
        for i in range(ROWS):
            session.add(SAUser(
                username=f"u{i}", email=f"u{i}@x.com",
                active=True, score=float(i)
            ))
        session.commit()

def pw_insert():
    clean_tables()
    for i in range(ROWS):
        PWUser.create(
            username=f"u{i}", email=f"u{i}@x.com",
            active=True, score=float(i)
        )

t_my = timeit(mydborm_insert)
t_sa = timeit(sa_insert)
t_pw = timeit(pw_insert)
results.append(["Single insert x" + str(ROWS), t_my, t_sa, t_pw])
print(f"insert x{ROWS}   mydborm={t_my}s  SA={t_sa}s  PW={t_pw}s")


# ── 2. Bulk insert ────────────────────────────────────────────────

def mydborm_bulk():
    clean_tables()
    BenchUser.bulk_create(make_records(BULK_ROWS))

def sa_bulk():
    clean_tables()
    with SASession(sa_engine) as session:
        session.bulk_insert_mappings(SAUser, make_records(BULK_ROWS))
        session.commit()

def pw_bulk():
    clean_tables()
    data = make_records(BULK_ROWS)
    with pw_db.atomic():
        for chunk in [data[i:i+500] for i in range(0, len(data), 500)]:
            PWUser.insert_many(chunk).execute()

t_my = timeit(mydborm_bulk)
t_sa = timeit(sa_bulk)
t_pw = timeit(pw_bulk)
results.append(["Bulk insert x" + str(BULK_ROWS), t_my, t_sa, t_pw])
print(f"bulk x{BULK_ROWS}  mydborm={t_my}s  SA={t_sa}s  PW={t_pw}s")


# ── 3. Select all ─────────────────────────────────────────────────

BenchUser.bulk_create(make_records(ROWS))

def mydborm_select():
    return BenchUser.all()

def sa_select():
    with SASession(sa_engine) as session:
        return session.query(SAUser).all()

def pw_select():
    return list(PWUser.select())

t_my = timeit(mydborm_select)
t_sa = timeit(sa_select)
t_pw = timeit(pw_select)
results.append(["Select all x" + str(ROWS), t_my, t_sa, t_pw])
print(f"select x{ROWS}  mydborm={t_my}s  SA={t_sa}s  PW={t_pw}s")


# ── 4. Filter ─────────────────────────────────────────────────────

def mydborm_filter():
    return BenchUser.filter(active=True)

def sa_filter():
    with SASession(sa_engine) as session:
        return session.query(SAUser).filter_by(active=True).all()

def pw_filter():
    return list(PWUser.select().where(PWUser.active == True))

t_my = timeit(mydborm_filter)
t_sa = timeit(sa_filter)
t_pw = timeit(pw_filter)
results.append(["Filter x" + str(ROWS), t_my, t_sa, t_pw])
print(f"filter x{ROWS}  mydborm={t_my}s  SA={t_sa}s  PW={t_pw}s")


# ── 5. Single get by PK ───────────────────────────────────────────

# Ensure each table has data
records = make_records(ROWS)

clean_tables()
BenchUser.bulk_create(records)
with SASession(sa_engine) as _s:
    _s.bulk_insert_mappings(SAUser, records)
    _s.commit()
with pw_db.atomic():
    for chunk in [records[i:i+500] for i in range(0, len(records), 500)]:
        PWUser.insert_many(chunk).execute()

my_pk = BenchUser.all()[ROWS//2]["id"]
with SASession(sa_engine) as _s:
    sa_pk = _s.query(SAUser).all()[ROWS//2].id
pw_pk = list(PWUser.select())[ROWS//2].id

def mydborm_get():
    return BenchUser.get(id=my_pk)

def sa_get():
    with SASession(sa_engine) as session:
        return session.get(SAUser, sa_pk)

def pw_get():
    return PWUser.get_by_id(pw_pk)


# ── 6. Update ─────────────────────────────────────────────────────

def mydborm_update():
    BenchUser.update({"score": 999.0}, active=True)

def sa_update():
    with SASession(sa_engine) as session:
        session.query(SAUser).filter_by(active=True).update({"score": 999.0})
        session.commit()

def pw_update():
    PWUser.update(score=999.0).where(PWUser.active == True).execute()

t_my = timeit(mydborm_update)
t_sa = timeit(sa_update)
t_pw = timeit(pw_update)
results.append(["Update x" + str(ROWS), t_my, t_sa, t_pw])
print(f"update x{ROWS}  mydborm={t_my}s  SA={t_sa}s  PW={t_pw}s")


# ------------------------------------------------------------------ #
#  Results table                                                       #
# ------------------------------------------------------------------ #

print()
print("=" * 60)
print("RESULTS")
print("=" * 60)
print()

# Add winner column
table_data = []
for op, my, sa, pw in results:
    best  = min(my, sa, pw)
    winner = "mydborm" if my == best else ("SQLAlchemy" if sa == best else "Peewee")
    table_data.append([op, f"{my}s", f"{sa}s", f"{pw}s", winner])

print(tabulate(
    table_data,
    headers=["Operation", "mydborm", "SQLAlchemy", "Peewee", "Winner"],
    tablefmt="rounded_outline"
))

print()

# Summary
my_wins = sum(1 for _, my, sa, pw in results if my == min(my, sa, pw))
print(f"mydborm wins: {my_wins}/{len(results)} operations")

# ------------------------------------------------------------------ #
#  Save results                                                        #
# ------------------------------------------------------------------ #

import datetime
report_path = os.path.join(os.path.dirname(__file__), "results.md")

with open(report_path, "w", encoding="utf-8") as f:
    f.write("# mydborm benchmark results\n\n")
    f.write(f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
    f.write(f"**MySQL:** {DB_HOST}:{DB_PORT}/{DB_NAME}  \n")
    f.write(f"**Rows:** {ROWS} | Bulk rows: {BULK_ROWS} | Runs: {RUNS}  \n\n")
    f.write("| Operation | mydborm | SQLAlchemy | Peewee | Winner |\n")
    f.write("|---|---|---|---|---|\n")
    for op, my, sa, pw in results:
        best   = min(my, sa, pw)
        winner = "mydborm" if my == best else ("SQLAlchemy" if sa == best else "Peewee")
        f.write(f"| {op} | {my}s | {sa}s | {pw}s | {winner} |\n")
    f.write(f"\nmydborm wins: {my_wins}/{len(results)} operations\n")

print(f"\nResults saved to: {report_path}")

 # Close MySQL connection before switching to YugabyteDB
 # Teardown MySQL tables before switching dialect
teardown_tables()
db.close()

# ------------------------------------------------------------------ #
#  YugabyteDB benchmarks                                              #
# ------------------------------------------------------------------ #

import socket

def is_yugabyte_available():
    try:
        s = socket.create_connection(("127.0.0.1", 5433), timeout=2)
        s.close()
        return True
    except OSError:
        return False

if is_yugabyte_available():
    print()
    print("=" * 60)
    print("YugabyteDB benchmarks")
    print("=" * 60)

    from mydborm import db as yb_db

    yb_db.configure(
        dialect  = "yugabyte",
        host     = "127.0.0.1",
        port     = 5433,
        user     = "yugabyte",
        password = os.environ.get("YB_PASSWORD", "yugabyte"),
        database = "yugabyte",
        encoding = "utf-8",
    )

    class YBBenchUser(BaseModel):
        __tablename__ = "yb_bench_users"
        id       = IntField(primary_key=True)
        username = StrField(max_length=100, nullable=False)
        email    = StrField(max_length=255, nullable=False)
        active   = BoolField(default=True)
        score    = FloatField(nullable=False)

    # Setup
    with yb_db.connect() as conn:
        conn.cursor().execute('DROP TABLE IF EXISTS "yb_bench_users"')
    YBBenchUser.create_table()

    yb_results = []

    def yb_clean():
        with yb_db.connect() as conn:
            conn.cursor().execute('DELETE FROM "yb_bench_users"')

    # 1. Single insert
    def yb_insert():
        yb_clean()
        for i in range(ROWS):
            YBBenchUser.create(
                username=f"u{i}", email=f"u{i}@x.com",
                active=True, score=float(i)
            )

    t_yb = timeit(yb_insert)
    yb_results.append(["Single insert x" + str(ROWS), t_yb])
    print(f"insert x{ROWS}   YugabyteDB={t_yb}s")

    # 2. Bulk insert
    def yb_bulk():
        yb_clean()
        YBBenchUser.bulk_create(make_records(BULK_ROWS))

    t_yb = timeit(yb_bulk)
    yb_results.append(["Bulk insert x" + str(BULK_ROWS), t_yb])
    print(f"bulk x{BULK_ROWS}  YugabyteDB={t_yb}s")

    # 3. Select all
    YBBenchUser.bulk_create(make_records(ROWS))

    def yb_select():
        return YBBenchUser.all()

    t_yb = timeit(yb_select)
    yb_results.append(["Select all x" + str(ROWS), t_yb])
    print(f"select x{ROWS}  YugabyteDB={t_yb}s")

    # 4. Filter
    def yb_filter():
        return YBBenchUser.filter(active=True)

    t_yb = timeit(yb_filter)
    yb_results.append(["Filter x" + str(ROWS), t_yb])
    print(f"filter x{ROWS}  YugabyteDB={t_yb}s")

    # 5. Update
    def yb_update():
        YBBenchUser.update({"score": 999.0}, active=True)

    t_yb = timeit(yb_update)
    yb_results.append(["Update x" + str(ROWS), t_yb])
    print(f"update x{ROWS}  YugabyteDB={t_yb}s")

    # Results
    print()
    print("YugabyteDB vs MySQL (mydborm)")
    print()

    mysql_times = {r[0]: r[1] for r in results}
    yb_table    = []
    for op, yb_t in yb_results:
        my_t   = mysql_times.get(op, 0)
        faster = "YugabyteDB" if yb_t < my_t else "MySQL"
        yb_table.append([op, f"{my_t}s", f"{yb_t}s", faster])

    print(tabulate(
        yb_table,
        headers=["Operation", "MySQL", "YugabyteDB", "Faster"],
        tablefmt="rounded_outline"
    ))

    # Save YugabyteDB results to report
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n## YugabyteDB vs MySQL (mydborm)\n\n")
        f.write("| Operation | MySQL | YugabyteDB | Faster |\n")
        f.write("|---|---|---|---|\n")
        for op, yb_t in yb_results:
            my_t   = mysql_times.get(op, 0)
            faster = "YugabyteDB" if yb_t < my_t else "MySQL"
            f.write(f"| {op} | {my_t}s | {yb_t}s | {faster} |\n")

    # Cleanup
    with yb_db.connect() as conn:
        conn.cursor().execute('DROP TABLE IF EXISTS "yb_bench_users"')
    yb_db.close()
    print()
    print("YugabyteDB benchmarks complete.")
else:
    print()
    print("YugabyteDB not available — skipping YB benchmarks.")

# already closed above before YugabyteDB section
pass