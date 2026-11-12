"""User list persistence, backups and confirmed route exports."""

import shutil
import time

from ..export_address_list import export_rsc, read_snapshot, validate_list_name
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
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        backup = backup_dir / f"{path.name}.{stamp}.bak"
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

    def address_list(self, name):
        validate_list_name(name)
        try:
            return export_rsc(read_snapshot(self.config.last_good_routes_file, self.config.update_lock_dir), name)
        except (OSError, ValueError) as exc:
            raise SnapshotUnavailable(f"confirmed route snapshot unavailable: {exc}") from exc
