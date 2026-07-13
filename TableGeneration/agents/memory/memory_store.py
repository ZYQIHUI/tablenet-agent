import json
import os
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import RLock


class JsonMemoryStore:
    """Small atomic JSON store for reproducible local generation runs."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = RLock()

    def read(self):
        with self._lock:
            if not self.path.exists():
                return self._empty()
            try:
                with open(self.path, "r", encoding="utf-8") as file_object:
                    value = json.load(file_object)
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"failed to read memory store {self.path}: {exc}") from exc
            if not isinstance(value, dict):
                raise RuntimeError(f"memory store root must be an object: {self.path}")
            return self._normalize(value)

    def update(self, updater):
        with self._lock:
            with self._process_lock():
                data = self.read()
                updated = updater(deepcopy(data))
                if updated is None:
                    updated = data
                normalized = self._normalize(updated)
                self._atomic_write(normalized)
                return deepcopy(normalized)

    @contextmanager
    def _process_lock(self):
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+b") as lock_file:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _atomic_write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file_object:
                json.dump(data, file_object, ensure_ascii=False, indent=2, sort_keys=True)
                file_object.flush()
                os.fsync(file_object.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _normalize(self, value):
        data = self._empty()
        data.update(value)
        if not isinstance(data["inner"], dict):
            data["inner"] = self._empty()["inner"]
        if not isinstance(data["outer"], dict):
            data["outer"] = {}
        inner = self._empty()["inner"]
        inner.update(data["inner"])
        for key in inner:
            if not isinstance(inner[key], list):
                inner[key] = []
        data["inner"] = inner
        return data

    def _empty(self):
        return {
            "inner": {
                "topics": [],
                "schema_signatures": [],
                "header_patterns": [],
                "rejected_candidates": [],
                "failure_reasons": [],
            },
            "outer": {},
        }
