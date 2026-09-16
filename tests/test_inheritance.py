import os
# =============================================================================
# File        : tests/test_inheritance.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : pytest tests for Single Table Inheritance — shared table
#               naming, discriminator column/value, create() auto-fill,
#               read scoping (all/get/filter/count/query), and table
#               reconciliation across create_table() calls.
# =============================================================================

import pytest
from mydborm import db, BaseModel, IntField, StrField, FloatField


# ------------------------------------------------------------------ #
#  Test models                                                        #
# ------------------------------------------------------------------ #

class Person(BaseModel):
    __tablename__ = "sti_people"
    __discriminator_col__ = "type"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)
    type = StrField(max_length=50, nullable=False)


class Employee(Person):
    salary = FloatField(nullable=True)


class Manager(Employee):
    team_size = IntField(nullable=True)


# A plain, non-STI subclass hierarchy stays unaffected.
class Widget(BaseModel):
    __tablename__ = "sti_widgets"
    id   = IntField(primary_key=True)
    name = StrField(max_length=100, nullable=False)


# ------------------------------------------------------------------ #
#  Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.configure(
        dialect="mysql", host="127.0.0.1",
        port=3307, user="root", password=os.environ.get("DB_PASSWORD", "root"), database="testdb"
    )
    Person.create_table()
    Employee.create_table()
    Manager.create_table()
    yield
    Person.drop_table()
    db.close()


@pytest.fixture(autouse=True)
def seed_table():
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM sti_people")
    yield


# ------------------------------------------------------------------ #
#  Table + discriminator metadata                                     #
# ------------------------------------------------------------------ #

def test_subclasses_share_parent_table():
    assert Person._table == "sti_people"
    assert Employee._table == "sti_people"
    assert Manager._table == "sti_people"


def test_discriminator_column_inherited():
    assert Person._discriminator_col == "type"
    assert Employee._discriminator_col == "type"
    assert Manager._discriminator_col == "type"


def test_discriminator_value_defaults_to_class_name():
    assert Person._discriminator_value == "Person"
    assert Employee._discriminator_value == "Employee"
    assert Manager._discriminator_value == "Manager"


def test_only_subclasses_are_read_scoped():
    assert Person._discriminator_scoped is False
    assert Employee._discriminator_scoped is True
    assert Manager._discriminator_scoped is True


def test_non_sti_model_unaffected():
    assert Widget._table == "sti_widgets"
    assert Widget._discriminator_col is None
    assert Widget._discriminator_value is None
    assert Widget._discriminator_scoped is False


# ------------------------------------------------------------------ #
#  create() auto-fills the discriminator                              #
# ------------------------------------------------------------------ #

def test_create_auto_fills_discriminator():
    pid = Person.create(name="Alice")
    row = Person.get(id=pid)
    assert row["type"] == "Person"

    eid = Employee.create(name="Bob", salary=50000)
    erow = Person.get(id=eid)
    assert erow["type"] == "Employee"


def test_create_respects_explicit_discriminator_override():
    eid = Employee.create(name="Zoe", salary=1000, type="Contractor")
    row = Person.get(id=eid)
    assert row["type"] == "Contractor"


# ------------------------------------------------------------------ #
#  Read scoping                                                        #
# ------------------------------------------------------------------ #

def test_base_all_returns_every_subtype():
    Person.create(name="Alice")
    Employee.create(name="Bob", salary=1.0)
    Manager.create(name="Carol", salary=2.0, team_size=3)

    assert len(Person.all()) == 3


def test_subclass_all_returns_only_its_own_type():
    Person.create(name="Alice")
    Employee.create(name="Bob", salary=1.0)
    Manager.create(name="Carol", salary=2.0, team_size=3)

    employees = Employee.all()
    assert len(employees) == 1
    assert employees[0]["name"] == "Bob"

    managers = Manager.all()
    assert len(managers) == 1
    assert managers[0]["name"] == "Carol"


def test_subclass_get_filter_count_are_scoped():
    Person.create(name="Alice")
    Employee.create(name="Bob", salary=1.0)
    Manager.create(name="Carol", salary=2.0, team_size=3)

    assert Employee.get(name="Bob") is not None
    assert Employee.get(name="Carol") is None  # Carol is a Manager, not an Employee
    assert Employee.filter(name="Bob") != []
    assert Employee.count() == 1
    assert Person.count() == 3
    assert Employee.exists(name="Bob") is True
    assert Employee.exists(name="Carol") is False


def test_subclass_query_is_prefiltered():
    Person.create(name="Alice")
    Employee.create(name="Bob", salary=1.0)

    rows = Employee.query().all()
    assert len(rows) == 1
    assert rows[0]["name"] == "Bob"

    # Can still chain additional filters on top of the discriminator scope
    rows2 = Employee.query().where("name", "Bob").all()
    assert len(rows2) == 1


# ------------------------------------------------------------------ #
#  create_table() reconciliation                                      #
# ------------------------------------------------------------------ #

def test_create_table_reconciles_subtype_columns():
    from mydborm.migrations import get_live_schema
    schema = get_live_schema("sti_people")
    assert "salary" in schema
    assert "team_size" in schema


def test_create_table_is_idempotent_across_call_order():
    # Calling create_table() again on any class in the hierarchy must
    # not error and must not drop/alter existing columns.
    Manager.create_table()
    Employee.create_table()
    Person.create_table()
    from mydborm.migrations import get_live_schema
    schema = get_live_schema("sti_people")
    assert {"id", "name", "type", "salary", "team_size"} <= set(schema.keys())
