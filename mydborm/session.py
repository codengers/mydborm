# -*- coding: utf-8 -*-
# =============================================================================
# File        : session.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.6.0
# License     : MIT
# Description : Session — implements Identity Map, Unit of Work, and
#               Change Tracking patterns. A Session is an in-memory
#               unit of work that tracks object lifecycle, detects dirty
#               fields, and coordinates atomic flushes to the database.
# =============================================================================

import copy
from typing import Optional, Type
from .db import db
from .exceptions import MydbormError


# ------------------------------------------------------------------ #
#  Tracked object states                                               #
# ------------------------------------------------------------------ #

class ObjectState:
    NEW      = "new"       # created, not yet in DB
    CLEAN    = "clean"     # loaded from DB, no changes
    DIRTY    = "dirty"     # loaded from DB, modified
    DELETED  = "deleted"   # marked for deletion
    DETACHED = "detached"  # removed from session


# ------------------------------------------------------------------ #
#  TrackedInstance                                                     #
# ------------------------------------------------------------------ #

class TrackedInstance:
    """
    Wraps a ModelInstance and tracks its state and dirty fields.

    Attributes:
        instance  : the ModelInstance being tracked
        state     : ObjectState constant
        original  : snapshot of data when first loaded/created
        dirty     : set of field names that changed
    """

    def __init__(self, instance, state: str = ObjectState.CLEAN):
        self.instance = instance
        self.state    = state
        self.original = copy.deepcopy(dict(instance._data))
        self.dirty    = set()

    def mark_dirty(self, field: str):
        """Mark a field as modified."""
        self.state = ObjectState.DIRTY
        self.dirty.add(field)

    def mark_clean(self):
        """Reset after successful flush."""
        self.original = copy.deepcopy(dict(self.instance._data))
        self.dirty    = set()
        self.state    = ObjectState.CLEAN

    def dirty_data(self) -> dict:
        """Return only the changed fields and their new values."""
        return {
            k: self.instance._data[k]
            for k in self.dirty
            if k in self.instance._data
        }

    def __repr__(self):
        return (
            f"<TrackedInstance "
            f"model={self.instance._model_class.__name__} "
            f"state={self.state} "
            f"dirty={self.dirty}>"
        )


# ------------------------------------------------------------------ #
#  Session                                                             #
# ------------------------------------------------------------------ #

class Session:
    """
    Unit of Work + Identity Map session.

    Tracks object lifecycle, detects dirty fields, and coordinates
    atomic flushes to the database. Use as context manager for
    automatic commit/rollback.

    Usage:
        # As context manager
        with Session() as session:
            user = session.get(User, id=1)
            user.username = "updated"
            # auto-committed on exit

        # Manual
        session = Session()
        session.configure(dialect="mysql", ...)
        user = session.get(User, id=1)
        user.username = "updated"
        session.flush()
        session.commit()
        session.close()
    """

    def __init__(self):
        # Identity map: (table, pk_value) → TrackedInstance
        self._identity_map: dict = {}
        # Pending new objects: list of TrackedInstance
        self._new:     list = []
        # Pending deletions: list of TrackedInstance
        self._deleted: list = []

    # ------------------------------------------------------------------ #
    #  Context manager                                                     #
    # ------------------------------------------------------------------ #

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            try:
                self.flush()
                self.commit()
            except Exception:
                self.rollback()
                raise
        else:
            self.rollback()
        self.close()
        return False

    # ------------------------------------------------------------------ #
    #  Identity map                                                        #
    # ------------------------------------------------------------------ #

    def _identity_key(self, model_class, pk_value) -> tuple:
        return (model_class._table, pk_value)

    def _get_pk_value(self, instance) -> Optional[int]:
        """Get primary key value from a ModelInstance."""
        for fname, field in instance._model_class._fields.items():
            if field.primary_key:
                return instance._data.get(fname)
        return None

    def _register(self, instance,
                   state: str = ObjectState.CLEAN) -> TrackedInstance:
        """Register a ModelInstance in the identity map."""
        pk  = self._get_pk_value(instance)
        key = self._identity_key(instance._model_class, pk)

        if key in self._identity_map:
            return self._identity_map[key]

        tracked = TrackedInstance(instance, state)
        if pk is not None:
            self._identity_map[key] = tracked

        # Patch instance to enable change tracking
        self._patch_instance(instance, tracked)
        return tracked

    def _patch_instance(self, instance, tracked: TrackedInstance):
        """
        Replace instance._data with a TrackingDict that
        auto-marks dirty fields on any key assignment.
        """
        original_data = instance._data

        class TrackingDict(dict):
            def __setitem__(td_self, key, value):
                super().__setitem__(key, value)
                if key in instance._model_class._fields:
                    tracked.mark_dirty(key)

        tracking = TrackingDict(original_data)
        object.__setattr__(instance, "_data", tracking)

    # ------------------------------------------------------------------ #
    #  Get — with identity map                                            #
    # ------------------------------------------------------------------ #

    def get(self, model_class, **kwargs):
        """
        Get a record — returns cached instance if already loaded.

        Usage:
            user = session.get(User, id=1)
            same = session.get(User, id=1)
            assert user is same  # identical object
        """
        # Check identity map first
        pk_field = next(
            (f for f, field in model_class._fields.items()
             if field.primary_key), None
        )
        if pk_field and pk_field in kwargs:
            key = self._identity_key(model_class, kwargs[pk_field])
            if key in self._identity_map:
                return self._identity_map[key].instance

        # Load from DB
        instance = model_class.get(**kwargs)
        if instance is None:
            return None

        tracked = self._register(instance, ObjectState.CLEAN)
        return tracked.instance

    def all(self, model_class) -> list:
        """
        Load all records, registering each in the identity map.

        Usage:
            users = session.all(User)
        """
        instances = model_class.all()
        result    = []
        for inst in instances:
            tracked = self._register(inst, ObjectState.CLEAN)
            result.append(tracked.instance)
        return result

    def filter(self, model_class, **kwargs) -> list:
        """
        Filter records, registering each in the identity map.

        Usage:
            active_users = session.filter(User, active=True)
        """
        instances = model_class.filter(**kwargs)
        result    = []
        for inst in instances:
            tracked = self._register(inst, ObjectState.CLEAN)
            result.append(tracked.instance)
        return result

    # ------------------------------------------------------------------ #
    #  Add — queue for insert                                             #
    # ------------------------------------------------------------------ #

    def add(self, model_class, **kwargs):
        """
        Queue a new object for insertion on next flush.

        Usage:
            session.add(User, username="alice", email="a@x.com")
            session.add(Order, user_id=1, total=99.99)
            session.flush()  # both inserted atomically
        """
        from .model import ModelInstance
        instance = ModelInstance(model_class, kwargs)
        tracked  = TrackedInstance(instance, ObjectState.NEW)
        self._new.append(tracked)
        return instance

    # ------------------------------------------------------------------ #
    #  Delete — queue for deletion                                        #
    # ------------------------------------------------------------------ #

    def delete(self, instance):
        """
        Mark an instance for deletion on next flush.

        Usage:
            user = session.get(User, id=1)
            session.delete(user)
            session.flush()
        """
        pk  = self._get_pk_value(instance)
        key = self._identity_key(instance._model_class, pk)

        if key in self._identity_map:
            tracked       = self._identity_map[key]
            tracked.state = ObjectState.DELETED
            self._deleted.append(tracked)
        else:
            tracked = TrackedInstance(instance, ObjectState.DELETED)
            self._deleted.append(tracked)

    # ------------------------------------------------------------------ #
    #  Flush — write pending changes to DB                                #
    # ------------------------------------------------------------------ #

    def flush(self):
        """
        Write all pending changes to the database without committing.

        Order: INSERTs → UPDATEs → DELETEs
        """
        # INSERT new objects
        for tracked in self._new:
            inst        = tracked.instance
            model_class = inst._model_class
            data        = {
                k: v for k, v in inst._data.items()
                if k in model_class._fields
                and not model_class._fields[k].primary_key
            }
            pk = model_class.create(**data)

            # Update instance with new PK
            pk_field = next(
                (f for f, field in model_class._fields.items()
                 if field.primary_key), None
            )
            if pk_field:
                inst._data[pk_field] = pk

            tracked.mark_clean()
            key = self._identity_key(model_class, pk)
            self._identity_map[key] = tracked

        self._new.clear()

        # UPDATE dirty objects
        for key, tracked in list(self._identity_map.items()):
            if tracked.state == ObjectState.DIRTY:
                inst        = tracked.instance
                model_class = inst._model_class
                dirty       = tracked.dirty_data()
                pk_field    = next(
                    (f for f, field in model_class._fields.items()
                     if field.primary_key), None
                )
                if dirty and pk_field:
                    pk_val = inst._data.get(pk_field)
                    model_class.update(dirty, **{pk_field: pk_val})
                    tracked.mark_clean()

        # DELETE marked objects
        for tracked in self._deleted:
            inst        = tracked.instance
            model_class = inst._model_class
            pk_field    = next(
                (f for f, field in model_class._fields.items()
                 if field.primary_key), None
            )
            if pk_field:
                pk_val = inst._data.get(pk_field)
                model_class.delete(**{pk_field: pk_val})
                key = self._identity_key(model_class, pk_val)
                self._identity_map.pop(key, None)
                tracked.state = ObjectState.DETACHED

        self._deleted.clear()

    # ------------------------------------------------------------------ #
    #  Commit / Rollback                                                   #
    # ------------------------------------------------------------------ #

    def commit(self):
        """Commit the current database transaction."""
        conn = getattr(db._local if hasattr(db, '_local') else None,
                       "conn", None)
        try:
            import threading
            local = db.__dict__.get('_ConnectionManager__local') or \
                    getattr(db, '_local', threading.local())
            conn = getattr(local, "conn", None)
            if conn:
                conn.commit()
        except Exception:
            pass

    def rollback(self):
        """
        Rollback pending changes — clear queued inserts/deletes
        and reset dirty tracking.
        """
        self._new.clear()
        self._deleted.clear()
        for tracked in self._identity_map.values():
            if tracked.state == ObjectState.DIRTY:
                # Update TrackingDict contents in-place
                # not replace the reference
                for k, v in tracked.original.items():
                    dict.__setitem__(tracked.instance._data, k, v)
                tracked.state = ObjectState.CLEAN
                tracked.dirty = set()

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def expunge(self, instance):
        """Remove an instance from the session without deleting it."""
        pk  = self._get_pk_value(instance)
        key = self._identity_key(instance._model_class, pk)
        self._identity_map.pop(key, None)

    def expunge_all(self):
        """Remove all instances from the session."""
        self._identity_map.clear()
        self._new.clear()
        self._deleted.clear()

    def close(self):
        """Close the session and release all tracked objects."""
        self.expunge_all()

    def is_dirty(self, instance) -> bool:
        """Check if an instance has unsaved changes."""
        pk  = self._get_pk_value(instance)
        key = self._identity_key(instance._model_class, pk)
        if key in self._identity_map:
            return self._identity_map[key].state == ObjectState.DIRTY
        return False

    def dirty_fields(self, instance) -> list:
        """Return list of modified field names for an instance."""
        pk  = self._get_pk_value(instance)
        key = self._identity_key(instance._model_class, pk)
        if key in self._identity_map:
            return list(self._identity_map[key].dirty)
        return []

    def original_value(self, instance, field: str):
        """Return the original DB value of a field before modification."""
        pk  = self._get_pk_value(instance)
        key = self._identity_key(instance._model_class, pk)
        if key in self._identity_map:
            return self._identity_map[key].original.get(field)
        return None

    def stats(self) -> dict:
        """Return session statistics."""
        states = {}
        for tracked in self._identity_map.values():
            states[tracked.state] = states.get(tracked.state, 0) + 1
        return {
            "tracked":  len(self._identity_map),
            "new":      len(self._new),
            "deleted":  len(self._deleted),
            "clean":    states.get(ObjectState.CLEAN,  0),
            "dirty":    states.get(ObjectState.DIRTY,  0),
        }

    def __repr__(self):
        s = self.stats()
        return (
            f"<Session tracked={s['tracked']} "
            f"new={s['new']} "
            f"dirty={s['dirty']} "
            f"deleted={s['deleted']}>"
        )