"""Portable, validated configuration backups with review before restoration."""

import difflib
import hashlib
import json
import time
import uuid

from ..route_transaction import operation_lock
from ..state_store import read_state, state_lock, write_state
from .settings import SETTINGS_BY_KEY, validate_setting
from ..bgp_config import ALIASES, canonical_settings
from .storage import text_load, write_text_atomic


class BackupService:
    def __init__(self, config, settings, lists):
        self.config, self.settings, self.lists = config, settings, lists
        self.directory = config.generated_dir / "config-imports"

    def export(self):
        with state_lock(self.config.config_dir / ".configuration"):
            return self._export()

    def _export(self):
        return {"schema": 1, "created_at_unix": int(time.time()),
                "lists": {name: text_load(path) for name, path in self.config.list_files.items()},
                "settings": self.settings.effective_settings()}

    def fingerprint(self):
        return hashlib.sha256(json.dumps({"lists": {name: text_load(path) for name, path in self.config.list_files.items()},
                                         "settings": self.settings.effective_settings()}, sort_keys=True).encode()).hexdigest()

    def validate(self, data):
        if not isinstance(data, dict) or data.get("schema") != 1:
            raise ValueError("unsupported configuration backup")
        lists, settings = data.get("lists"), data.get("settings")
        if not isinstance(lists, dict) or set(lists) != set(self.config.list_files):
            raise ValueError("backup must contain all supported lists and no unknown lists")
        for name, content in lists.items():
            if not isinstance(content, str) or "\x00" in content or len(content.encode()) > 1_000_000:
                raise ValueError(f"invalid list content: {name}")
        if not isinstance(settings, dict) or set(settings) - (set(SETTINGS_BY_KEY) | set(ALIASES)):
            raise ValueError("backup must contain all supported settings and no unknown settings")
        normalized = canonical_settings({key: validate_setting(key, value) for key, value in settings.items()}, reject_conflicts=True)
        # Backups from releases before parallel collection lack these options.
        for key, spec in SETTINGS_BY_KEY.items():
            if spec.get("legacy_backup_default"):
                normalized.setdefault(key, spec["default"])
        if set(normalized) != set(SETTINGS_BY_KEY):
            raise ValueError("backup must contain all supported settings and no unknown settings")
        return {"schema": 1, "lists": lists, "settings": normalized}

    def preview(self, data):
        normalized = self.validate(data)
        with state_lock(self.config.config_dir / ".configuration"):
            current = self._export()
            diffs = {name: "".join(difflib.unified_diff(current["lists"][name].splitlines(True), content.splitlines(True),
                                                     fromfile="current/" + name, tofile="backup/" + name))
                     for name, content in normalized["lists"].items() if current["lists"][name] != content}
            settings = {key: {"before": current["settings"][key], "after": value}
                        for key, value in normalized["settings"].items() if value != current["settings"][key]}
            identifier = uuid.uuid4().hex
            self.directory.mkdir(parents=True, exist_ok=True)
            for path in self.directory.glob("*.json"):
                if path.stat().st_mtime < time.time() - 86400:
                    path.unlink(missing_ok=True)
            write_state(self.directory / (identifier + ".json"),
                        {"created_at_unix": int(time.time()), "backup": normalized, "fingerprint": self.fingerprint()})
            return {"id": identifier, "lists": diffs, "settings": settings}

    def restore(self, identifier):
        if not isinstance(identifier, str) or len(identifier) != 32 or any(char not in "0123456789abcdef" for char in identifier):
            raise ValueError("invalid import id")
        with operation_lock(self.config), state_lock(self.config.config_dir / ".configuration"):
            path = self.directory / (identifier + ".json")
            preview = read_state(path)
            if not preview or time.time() - preview["created_at_unix"] > 3600:
                raise ValueError("import preview expired")
            if preview["fingerprint"] != self.fingerprint():
                raise ValueError("configuration changed since import preview")
            data = self.validate(preview["backup"])
            saved = {file: file.read_bytes() if file.exists() else None for file in
                     (*self.config.list_files.values(), self.config.settings_file, self.config.settings_env_file)}
            backup_path = self.config.config_dir / "config-backups" / (uuid.uuid4().hex + ".json")
            write_state(backup_path, self._export())
            try:
                for name, content in data["lists"].items():
                    self.lists._save(name, content)
                self.settings._save_settings(data["settings"])
            except Exception:
                for file, content in saved.items():
                    if content is None:
                        file.unlink(missing_ok=True)
                    else:
                        write_text_atomic(file, content.decode("utf-8"))
                raise
            path.unlink(missing_ok=True)
            return {"ok": True, "backup": str(backup_path), "requires_restart": True}
