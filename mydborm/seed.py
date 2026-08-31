# =============================================================================
# File        : seed.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : Data seeding — populate a model's table from a list of
#               records or a JSON fixture file. Sync and async variants.
# =============================================================================

import json


def _load_records_from_file(filepath: str) -> list:
    """Load a JSON fixture file — must contain a top-level list of objects."""
    with open(filepath, "r", encoding="utf-8") as f:
        records = json.load(f)
    if not isinstance(records, list):
        raise ValueError(
            f"Seed file {filepath!r} must contain a JSON list of records."
        )
    return records


def seed(model_class, records: list, if_empty: bool = True) -> int:
    """
    Bulk-insert records into model_class's table.

    Args:
        records  : list of dicts, one per row
        if_empty : if True (default), skip seeding when the table
                   already has rows — safe to call on every app
                   startup/test setup without duplicating data

    Returns:
        Number of rows inserted (0 if skipped or records is empty).

    Usage:
        from mydborm.seed import seed
        seed(User, [
            {"username": "alice", "email": "alice@example.com"},
            {"username": "bob",   "email": "bob@example.com"},
        ])
    """
    if if_empty and model_class.count() > 0:
        return 0
    return model_class.bulk_create(records)


def seed_from_file(model_class, filepath: str, if_empty: bool = True) -> int:
    """
    Load records from a JSON fixture file (a top-level list of objects)
    and seed model_class's table. See seed() for if_empty behavior.

    Usage:
        from mydborm.seed import seed_from_file
        seed_from_file(User, "fixtures/users.json")
    """
    return seed(model_class, _load_records_from_file(filepath), if_empty=if_empty)


async def seed_async(model_class, records: list, if_empty: bool = True) -> int:
    """Async equivalent of seed() — model_class must be an AsyncBaseModel."""
    if if_empty and (await model_class.count()) > 0:
        return 0
    return await model_class.bulk_create(records)


async def seed_from_file_async(model_class, filepath: str, if_empty: bool = True) -> int:
    """Async equivalent of seed_from_file()."""
    return await seed_async(model_class, _load_records_from_file(filepath), if_empty=if_empty)
