"""Filesystem configuration passed explicitly to admin services."""

from dataclasses import dataclass
import os
from pathlib import Path

from ..runtime_paths import GENERATED_PATH_SPECS, config_paths, list_paths


@dataclass
class AdminConfig:
    static_root: Path
    generated_dir: Path
    config_dir: Path
    list_backup_dir: Path
    routes_file: Path
    last_good_routes_file: Path
    status_file: Path
    metrics_file: Path
    runtime_file: Path
    update_runtime_file: Path
    container_log_file: Path
    settings_file: Path
    settings_env_file: Path
    update_lock_dir: Path
    reload_result_file: Path
    list_files: dict[str, Path]

    @classmethod
    def from_env(cls, environ=None):
        environ = os.environ if environ is None else environ
        paths = {key: Path(environ.get(name, default)) for key, (name, default) in GENERATED_PATH_SPECS.items()}
        configuration = config_paths(environ)
        return cls(
            static_root=Path(environ.get("ADMIN_STATIC_DIR", "/admin-ui")),
            generated_dir=paths["generated_dir"], routes_file=paths["routes_file"],
            config_dir=configuration["config_dir"], list_backup_dir=configuration["list_backup_dir"],
            last_good_routes_file=Path(environ.get("LAST_GOOD_ROUTES_FILE", "/etc/bird/generated/routes.last-good.conf")),
            status_file=paths["status_file"], metrics_file=paths["metrics_file"],
            runtime_file=paths["runtime_file"], update_runtime_file=paths["update_runtime_file"],
            container_log_file=paths["container_log_file"], settings_file=configuration["settings_file"],
            settings_env_file=configuration["settings_env_file"],
            update_lock_dir=Path(environ.get("UPDATE_LOCK_DIR", "/etc/bird/generated/update.lock")),
            reload_result_file=paths["generated_dir"] / "reload-result.json",
            list_files=list_paths(environ),
        )
