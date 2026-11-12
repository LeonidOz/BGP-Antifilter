"""Isolated filesystem configuration for admin service and HTTP tests."""

from bgp_antifilter.admin import AdminApplication, AdminConfig
from bgp_antifilter.runtime_paths import GENERATED_PATH_SPECS, LIST_FILE_SPECS


def admin_application(root):
    environment = {name: str(root / key) for key, (name, _default) in GENERATED_PATH_SPECS.items()}
    environment["GENERATED_DIR"] = str(root)
    environment["CONFIG_DIR"] = str(root / "config")
    environment["ADMIN_STATIC_DIR"] = str(root / "static")
    environment["LAST_GOOD_ROUTES_FILE"] = str(root / "routes.last-good.conf")
    environment["UPDATE_LOCK_DIR"] = str(root / "update.lock")
    environment.update({name: str(root / f"{key}.txt") for key, (name, _default) in LIST_FILE_SPECS.items()})
    return AdminApplication(AdminConfig.from_env(environment))
