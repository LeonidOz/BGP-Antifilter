"""User list persistence, backups and confirmed route exports."""

import shutil
import time
import uuid
import difflib
import hashlib

from ..export_address_list import export_rsc, read_snapshot, validate_list_name
from ..state_store import state_lock
from .storage import text_load, write_text_atomic


class UnknownListError(LookupError):
    pass


class SnapshotUnavailable(OSError):
    pass


class ListWriteError(OSError):
    pass


class ListService:
    def __init__(self, config):
        self.config = config

    def backup_file(self, path):
        if not path.exists():
            return None
        backup_dir = self.config.list_backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = f"{time.time_ns():020d}"
        backup = backup_dir / f"{path.name}.{stamp}-{uuid.uuid4().hex}.bak"
        shutil.copy2(path, backup)
        return str(backup)

    def list_path(self, name):
        path = self.config.list_files.get(name)
        if not path:
            raise UnknownListError("unknown list")
        return path

    def index(self):
        return {
            name: {"path": str(path), "bytes": path.stat().st_size if path.exists() else 0}
            for name, path in self.config.list_files.items()
        }

    def read(self, name):
        path = self.list_path(name)
        return {"name": name, "path": str(path), "content": text_load(path)}

    def save(self, name, content):
        with state_lock(self.config.config_dir / ".configuration"):
            return self._save(name, content)

    def _save(self, name, content):
        path = self.list_path(name)
        if not isinstance(content, str):
            raise ValueError("content must be a string")
        if "\x00" in content:
            raise ValueError("content contains NUL byte")
        backup = self.backup_file(path)
        if content and not content.endswith("\n"):
            content += "\n"
        try:
            write_text_atomic(path, content)
        except OSError as exc:
            raise ListWriteError(str(exc)) from exc
        return {"ok": True, "backup": backup, "bytes": len(content.encode("utf-8"))}

    def history(self, name):
        path = self.list_path(name)
        def created(backup):
            stamp = backup.name[len(path.name) + 1:].split("-", 1)[0]
            return int(stamp) if len(stamp) == 20 and stamp.isdigit() else backup.stat().st_mtime_ns
        return [{"id": backup.name, "bytes": backup.stat().st_size, "modified_at_unix": created(backup) // 1_000_000_000}
                for backup in sorted(self.config.list_backup_dir.glob(path.name + ".*.bak"), key=created, reverse=True)
                if backup.is_file() and not backup.is_symlink()]

    def history_version(self, name, identifier):
        self.list_path(name)
        if identifier not in {entry["id"] for entry in self.history(name)}:
            raise ValueError("unknown backup")
        path = self.config.list_backup_dir / identifier
        content = path.read_text(encoding="utf-8")
        current = self.read(name)["content"]
        return {"id": identifier, "content": content, "current_sha256": hashlib.sha256(current.encode()).hexdigest(),
                "diff": "".join(difflib.unified_diff(current.splitlines(True), content.splitlines(True), fromfile="current", tofile="backup"))}

    def restore(self, name, identifier, current_sha256):
        with state_lock(self.config.config_dir / ".configuration"):
            version = self.history_version(name, identifier)
            if current_sha256 != version["current_sha256"]:
                raise ValueError("list changed since preview; review the backup again")
            return self._save(name, version["content"])

    def address_list(self, name):
        validate_list_name(name)
        try:
            return export_rsc(read_snapshot(self.config.last_good_routes_file, self.config.update_lock_dir), name)
        except (OSError, ValueError) as exc:
            raise SnapshotUnavailable(f"confirmed route snapshot unavailable: {exc}") from exc
