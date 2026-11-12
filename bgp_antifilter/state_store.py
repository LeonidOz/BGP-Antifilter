"""Atomic JSON state transactions shared by the container's processes.

The sidecar lock stays in place: unlinking it could let two writers lock
different inodes. The OS releases the lock when a process exits or crashes.
Readers need no lock because writers publish complete files with os.replace.
"""

from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import tempfile
import time

if os.name == "nt":
    import msvcrt
else:
    import fcntl


def read_state(path):
    deadline = time.monotonic() + 1
    try:
        while True:
            try:
                value = json.loads(Path(path).read_text(encoding="utf-8"))
                break
            except PermissionError:
                if os.name != "nt" or time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


@contextmanager
def state_lock(path, timeout=10):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a+b") as lock:
        if os.name == "nt":
            # Windows byte-range locks need a byte to lock.
            if lock.seek(0, os.SEEK_END) == 0:
                lock.write(b"\0")
                lock.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out locking state file: {path}") from exc
                time.sleep(0.01)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _publish(path, value):
    # Unique files prevent collisions even with abandoned temporary files.
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=path.name + ".", suffix=".tmp", delete=False,
        ) as file:
            temp_path = Path(file.name)
            file.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode & 0o777)
        else:
            os.chmod(temp_path, 0o644)
        deadline = time.monotonic() + 1
        while True:
            try:
                temp_path.replace(path)
                break
            except PermissionError:
                # Windows readers can briefly prevent replacing an open file.
                # Retry the atomic publish; never fall back to truncating it.
                if os.name != "nt" or time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def mutate_state(path, transform):
    """Read, transform and publish under one lock; None means no write."""
    path = Path(path)
    with state_lock(path):
        current = read_state(path)
        updated = transform(current)
        if updated is None:
            return current
        _publish(path, updated)
        return updated


def patch_state(path, **updates):
    return mutate_state(path, lambda current: {**current, **updates})


def write_state(path, value):
    return mutate_state(path, lambda current: value)
