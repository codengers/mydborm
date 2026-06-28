# =============================================================================
# File        : bulk.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.5.0
# License     : MIT
# Description : Production-grade bulk operations with chunking, retry
#               logic, progress callbacks, and detailed BulkResult.
#               Supports MySQL and YugabyteDB.
# =============================================================================

import time
import math
from typing import Callable, Optional
from .exceptions import BulkInsertError, BulkUpdateError, BulkUpsertError, BulkDeleteError


# ------------------------------------------------------------------ #
#  BulkResult                                                          #
# ------------------------------------------------------------------ #

class BulkResult:
    """
    Detailed result object returned by all bulk operations.

    Attributes:
        operation  : "insert", "update", "upsert", "delete"
        total      : total records attempted
        inserted   : records successfully inserted
        updated    : records successfully updated
        deleted    : records successfully deleted
        failed     : records that failed
        chunks     : number of chunks processed
        retries    : total retry attempts made
        errors     : list of error dicts {chunk, records, error}
        duration   : total time in seconds

    Usage:
        result = User.bulk_create(records, chunk_size=500)
        print(result.inserted)    # 850
        print(result.failed)      # 2
        print(result.success_rate) # 99.76
        print(result)
    """

    def __init__(self, operation: str, total: int):
        self.operation = operation
        self.total     = total
        self.inserted  = 0
        self.updated   = 0
        self.deleted   = 0
        self.failed    = 0
        self.chunks    = 0
        self.retries   = 0
        self.errors    = []
        self._start    = time.time()
        self.duration  = 0.0

    def finish(self):
        """Call when operation is complete."""
        self.duration = round(time.time() - self._start, 3)

    @property
    def success_rate(self) -> float:
        """Percentage of records processed successfully."""
        if self.total == 0:
            return 100.0
        succeeded = self.inserted + self.updated + self.deleted
        return round((succeeded / self.total) * 100, 2)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def add_error(self, chunk_num: int, records: list,
                  error: Exception):
        self.errors.append({
            "chunk":   chunk_num,
            "records": len(records),
            "error":   str(error),
        })
        self.failed += len(records)

    def __repr__(self):
        return (
            f"<BulkResult op={self.operation!r} "
            f"total={self.total} "
            f"inserted={self.inserted} "
            f"failed={self.failed} "
            f"duration={self.duration}s>"
        )

    def summary(self) -> str:
        """Human readable summary."""
        lines = [
            f"Operation : {self.operation}",
            f"Total     : {self.total}",
            f"Inserted  : {self.inserted}",
            f"Updated   : {self.updated}",
            f"Failed    : {self.failed}",
            f"Chunks    : {self.chunks}",
            f"Retries   : {self.retries}",
            f"Success   : {self.success_rate}%",
            f"Duration  : {self.duration}s",
        ]
        if self.errors:
            lines.append(f"Errors    : {len(self.errors)}")
            for e in self.errors:
                lines.append(
                    f"  chunk {e['chunk']}: "
                    f"{e['records']} records — {e['error']}"
                )
        return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Retry helper                                                        #
# ------------------------------------------------------------------ #

def _with_retry(fn, retries: int = 0, retry_delay: float = 0.5,
                result: BulkResult = None):
    """
    Execute fn() with exponential backoff retry.

    Args:
        fn          : callable to execute
        retries     : max number of retry attempts
        retry_delay : base delay in seconds (doubles each attempt)
        result      : BulkResult to track retry count
    """
    last_error = None
    attempts   = retries + 1

    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_error = e
            if attempt < retries:
                if result:
                    result.retries += 1
                delay = retry_delay * (2 ** attempt)
                time.sleep(delay)
            else:
                raise last_error


# ------------------------------------------------------------------ #
#  Chunk helper                                                        #
# ------------------------------------------------------------------ #

def _chunks(lst: list, size: int):
    """Split a list into chunks of given size."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


# ------------------------------------------------------------------ #
#  Chunked bulk_create                                                 #
# ------------------------------------------------------------------ #

def chunked_bulk_create(
    model_class,
    records: list,
    chunk_size: int = 500,
    retries: int = 0,
    retry_delay: float = 0.5,
    on_progress: Optional[Callable] = None,
    raise_on_error: bool = False,
) -> BulkResult:
    """
    Insert records in chunks with retry support.

    Args:
        model_class    : the BaseModel subclass
        records        : list of dicts to insert
        chunk_size     : rows per INSERT statement (default 500)
        retries        : retry attempts per chunk (default 0)
        retry_delay    : base retry delay in seconds
        on_progress    : callback(done, total) called after each chunk
        raise_on_error : raise BulkInsertError on first chunk failure

    Returns:
        BulkResult with full stats

    Usage:
        result = chunked_bulk_create(User, records, chunk_size=500,
                                     retries=3, retry_delay=0.5)
        print(result.summary())
    """
    if not records:
        r = BulkResult("insert", 0)
        r.finish()
        return r

    result     = BulkResult("insert", len(records))
    all_chunks = list(_chunks(records, chunk_size))
    done       = 0

    for i, chunk in enumerate(all_chunks):
        result.chunks += 1
        try:
            def do_insert(c=chunk):
                return model_class.bulk_create(c)

            rows = _with_retry(do_insert, retries=retries,
                               retry_delay=retry_delay, result=result)
            result.inserted += rows
            done            += len(chunk)

            if on_progress:
                on_progress(done, result.total)

        except Exception as e:
            result.add_error(i + 1, chunk, e)
            done += len(chunk)

            if on_progress:
                on_progress(done, result.total)

            if raise_on_error:
                result.finish()
                raise BulkInsertError(
                    f"Chunk {i+1} failed: {e}",
                    inserted = result.inserted,
                    failed   = result.failed,
                    errors   = result.errors,
                )

    result.finish()
    return result


# ------------------------------------------------------------------ #
#  Chunked bulk_update                                                 #
# ------------------------------------------------------------------ #

def chunked_bulk_update(
    model_class,
    records: list,
    key: str = "id",
    chunk_size: int = 500,
    retries: int = 0,
    retry_delay: float = 0.5,
    on_progress: Optional[Callable] = None,
    raise_on_error: bool = False,
) -> BulkResult:
    """
    Update records in chunks with retry support.

    Args:
        model_class    : the BaseModel subclass
        records        : list of dicts — each must include the key field
        key            : field used to identify rows (default "id")
        chunk_size     : rows per batch (default 500)
        retries        : retry attempts per chunk
        retry_delay    : base retry delay in seconds
        on_progress    : callback(done, total)
        raise_on_error : raise BulkUpdateError on first chunk failure

    Returns:
        BulkResult with full stats
    """
    if not records:
        r = BulkResult("update", 0)
        r.finish()
        return r

    result     = BulkResult("update", len(records))
    all_chunks = list(_chunks(records, chunk_size))
    done       = 0

    for i, chunk in enumerate(all_chunks):
        result.chunks += 1
        try:
            def do_update(c=chunk):
                return model_class.bulk_update(c, key=key)

            rows = _with_retry(do_update, retries=retries,
                               retry_delay=retry_delay, result=result)
            result.updated += rows
            done           += len(chunk)

            if on_progress:
                on_progress(done, result.total)

        except Exception as e:
            result.add_error(i + 1, chunk, e)
            done += len(chunk)

            if on_progress:
                on_progress(done, result.total)

            if raise_on_error:
                result.finish()
                raise BulkUpdateError(
                    f"Chunk {i+1} failed: {e}",
                    inserted = result.updated,
                    failed   = result.failed,
                    errors   = result.errors,
                )

    result.finish()
    return result


# ------------------------------------------------------------------ #
#  Chunked bulk_delete                                                 #
# ------------------------------------------------------------------ #

def chunked_bulk_delete(
    model_class,
    ids: list,
    key: str = "id",
    chunk_size: int = 500,
    retries: int = 0,
    retry_delay: float = 0.5,
    on_progress: Optional[Callable] = None,
    raise_on_error: bool = False,
) -> BulkResult:
    """
    Delete records in chunks with retry support.

    Args:
        model_class    : the BaseModel subclass
        ids            : list of key values to delete
        key            : field to match against (default "id")
        chunk_size     : ids per DELETE statement
        retries        : retry attempts per chunk
        retry_delay    : base retry delay in seconds
        on_progress    : callback(done, total)
        raise_on_error : raise BulkOperationError on failure

    Returns:
        BulkResult with full stats
    """
    if not ids:
        r = BulkResult("delete", 0)
        r.finish()
        return r

    result     = BulkResult("delete", len(ids))
    all_chunks = list(_chunks(ids, chunk_size))
    done       = 0

    for i, chunk in enumerate(all_chunks):
        result.chunks += 1
        try:
            def do_delete(c=chunk):
                return model_class.bulk_delete(c, key=key)

            rows = _with_retry(do_delete, retries=retries,
                               retry_delay=retry_delay, result=result)
            result.deleted += rows
            done           += len(chunk)

            if on_progress:
                on_progress(done, result.total)

        except Exception as e:
            result.add_error(i + 1, chunk, e)
            done += len(chunk)

            if on_progress:
                on_progress(done, result.total)

            if raise_on_error:
                result.finish()
                raise BulkDeleteError(
                    f"Chunk {i+1} failed: {e}",
                    inserted = 0,
                    failed   = result.failed,
                    errors   = result.errors,
                )

    result.finish()
    return result