"""One-time, non-destructive import of user config from the old data volume.

Run before sourcing settings.env or initializing list defaults. Source files
remain untouched. A persistent marker prevents resurrecting old settings after
the new configuration has been edited or deliberately reset.
"""

import json
import os
from pathlib import Path
import shlex
import shutil
import tempfile

from .runtime_paths import LIST_FILE_SPECS, config_paths, list_paths
from .state_store import state_lock, write_state


MIGRATION_MARKER = ".migration-v1.json"


def install_missing(target, source=None, content=None):
    """Publish a complete file, retaining an existing destination verbatim."""
    if target.exists() or target.is_symlink():
        if not target.is_file():
            raise ValueError(f"configuration path is not a file: {target}")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name + ".", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            if source is not None:
                with source.open("rb") as original:
                    shutil.copyfileobj(original, file)
            else:
                file.write(content)
            file.flush()
            os.fsync(file.fileno())
        if source is not None:
            shutil.copystat(source, temporary)
        temporary.replace(target)
        return True
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def first_existing(paths):
    for path in paths:
        if path.is_file():
            return path
    return None


def copy_directory_missing(source, target, excluded=()):
    if not source.is_dir() or source.resolve() == target.resolve():
        return
    # Snapshot before writing; avoid recursing into a nested custom target.
    files = [path for path in source.rglob("*") if path.is_file() and not path.is_relative_to(target)]
    for path in files:
        relative = path.relative_to(source)
        if relative.parts[0] not in excluded:
            install_missing(target / relative, source=path)


def settings_env_from_json(path):
    # Only used for an existing new JSON config without its shell projection;
    # never combine that JSON with unrelated settings.env from the old volume.
    from .admin.settings import SETTINGS_BY_KEY, validate_setting

    data = json.loads(path.read_text(encoding="utf-8"))
    values = data.get("values", data)
    if not isinstance(values, dict):
        raise ValueError(f"settings values must be an object: {path}")
    normalized = {key: validate_setting(key, value) for key, value in values.items() if key in SETTINGS_BY_KEY}
    return ("".join(f"{key}={shlex.quote(value)}\n" for key, value in sorted(normalized.items()))).encode("utf-8")


def prepare_user_config(environ=None):
    environ = os.environ if environ is None else environ
    paths = config_paths(environ)
    targets = list_paths(environ)
    directory = paths["config_dir"]
    generated = Path(environ.get("GENERATED_DIR", "/etc/bird/generated"))
    old_config = Path(environ.get("LEGACY_CONFIG_DIR", str(generated / "config")))
    old_bird = Path(environ.get("LEGACY_BIRD_DIR", "/etc/bird"))
    defaults = Path(environ.get("DEFAULT_CONFIG_DIR", "/defaults-config"))
    marker = directory / MIGRATION_MARKER
    with state_lock(directory / ".migration"):
        if not marker.exists():
            for key, target in targets.items():
                name = Path(LIST_FILE_SPECS[key][1]).name
                source = first_existing([old_config / name, generated / name, old_bird / name])
                if source is not None:
                    install_missing(target, source=source)

            settings = paths["settings_file"]
            settings_env = paths["settings_env_file"]
            had_settings = settings.exists()
            had_env = settings_env.exists()
            if not had_settings and not had_env:
                # Use one source directory for the pair, preserving its bytes.
                for source_dir in (generated, old_config):
                    if (source_dir / "settings.json").is_file() or (source_dir / "settings.env").is_file():
                        for target, name in ((settings, "settings.json"), (settings_env, "settings.env")):
                            source = source_dir / name
                            if source.is_file():
                                install_missing(target, source=source)
                        break
            elif had_settings and not had_env:
                matching_env = first_existing([
                    source_dir / "settings.env" for source_dir in (generated, old_config)
                    if (source_dir / "settings.json").is_file()
                    and (source_dir / "settings.json").read_bytes() == settings.read_bytes()
                ])
                if matching_env is not None:
                    install_missing(settings_env, source=matching_env)
                else:
                    install_missing(settings_env, content=settings_env_from_json(settings))

            # Preserve additional files in the old user configuration folder,
            # including any custom local source files, without copying settings
            # from a second directory into the selected JSON/env pair.
            copy_directory_missing(old_config, directory, excluded=("settings.json", "settings.env", "list-backups", MIGRATION_MARKER, ".migration.lock"))
            copy_directory_missing(generated / "list-backups", paths["list_backup_dir"])
            copy_directory_missing(old_config / "list-backups", paths["list_backup_dir"])
            write_state(marker, {"version": 1, "legacy_generated_dir": str(generated)})
            print(f"user configuration migration complete: {directory}")

        # Defaults are initialized only after migration, also on later starts
        # when a list has intentionally been removed from the new config.
        for key, target in targets.items():
            # Explicit per-file paths can have custom names.
            default_name = Path(LIST_FILE_SPECS[key][1]).name
            source = defaults / default_name
            if install_missing(target, source=source if source.is_file() else None, content=b""):
                print(f"initialized user config {target.name}")
    return paths


def main():
    prepare_user_config()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
