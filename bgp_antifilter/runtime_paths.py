import os
from pathlib import Path


CONFIG_PATH_SPECS = {
    "config_dir": ("CONFIG_DIR", "/etc/bird/config"),
    "settings_file": ("SETTINGS_FILE", "/etc/bird/config/settings.json"),
    "settings_env_file": ("SETTINGS_ENV_FILE", "/etc/bird/config/settings.env"),
    "list_backup_dir": ("LIST_BACKUP_DIR", "/etc/bird/config/list-backups"),
}

LIST_FILE_SPECS = {
    "urls": ("LISTS_FILE", "/etc/bird/config/lists.txt"),
    "domain-list-urls": ("DOMAIN_LIST_URLS_FILE", "/etc/bird/config/domain-list-urls.txt"),
    "asns": ("INCLUDE_ASNS_FILE", "/etc/bird/config/include-asns.txt"),
    "countries": ("INCLUDE_COUNTRIES_FILE", "/etc/bird/config/include-countries.txt"),
    "include-domains": ("INCLUDE_DOMAINS_FILE", "/etc/bird/config/include-domains.txt"),
    "exclude-domains": ("EXCLUDE_DOMAINS_FILE", "/etc/bird/config/exclude-domains.txt"),
}

GENERATED_PATH_SPECS = {
    "generated_dir": ("GENERATED_DIR", "/etc/bird/generated"),
    "routes_file": ("ROUTES_FILE", "/etc/bird/generated/routes.conf"),
    "status_file": ("STATUS_FILE", "/etc/bird/generated/status.json"),
    "metrics_file": ("METRICS_FILE", "/etc/bird/generated/metrics.prom"),
    "runtime_file": ("RUNTIME_FILE", "/etc/bird/generated/runtime.json"),
    "update_runtime_file": ("UPDATE_RUNTIME_FILE", "/etc/bird/generated/update-runtime.json"),
    "network_status_file": ("NETWORK_STATUS_FILE", "/etc/bird/generated/network-status.json"),
    "container_log_file": ("CONTAINER_LOG_FILE", "/etc/bird/generated/container.log"),
    "cache_dir": ("CACHE_DIR", "/etc/bird/generated/cache"),
}


def env_path(name, default):
    return Path(os.environ.get(name, default))


def env_paths(specs):
    return {
        key: env_path(env_name, default)
        for key, (env_name, default) in specs.items()
    }


def config_paths(environ=None):
    environ = os.environ if environ is None else environ
    directory = Path(environ.get("CONFIG_DIR", CONFIG_PATH_SPECS["config_dir"][1]))
    settings = Path(environ.get("SETTINGS_FILE", str(directory / "settings.json")))
    return {
        "config_dir": directory,
        "settings_file": settings,
        "settings_env_file": Path(environ.get("SETTINGS_ENV_FILE", str(directory / "settings.env"))),
        # Old stack files can still explicitly keep settings in generated/.
        "list_backup_dir": Path(environ.get("LIST_BACKUP_DIR", str(settings.parent / "list-backups"))),
    }


def list_paths(environ=None):
    environ = os.environ if environ is None else environ
    directory = config_paths(environ)["config_dir"]
    return {
        key: Path(environ.get(name, str(directory / Path(default).name)))
        for key, (name, default) in LIST_FILE_SPECS.items()
    }
