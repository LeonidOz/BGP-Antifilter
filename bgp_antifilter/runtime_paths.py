import os
from pathlib import Path


LIST_FILE_SPECS = {
    "urls": ("LISTS_FILE", "/etc/bird/lists.txt"),
    "asns": ("INCLUDE_ASNS_FILE", "/etc/bird/include-asns.txt"),
    "include-domains": ("INCLUDE_DOMAINS_FILE", "/etc/bird/include-domains.txt"),
    "exclude-domains": ("EXCLUDE_DOMAINS_FILE", "/etc/bird/exclude-domains.txt"),
}

GENERATED_PATH_SPECS = {
    "generated_dir": ("GENERATED_DIR", "/etc/bird/generated"),
    "routes_file": ("ROUTES_FILE", "/etc/bird/generated/routes.conf"),
    "status_file": ("STATUS_FILE", "/etc/bird/generated/status.json"),
    "metrics_file": ("METRICS_FILE", "/etc/bird/generated/metrics.prom"),
    "runtime_file": ("RUNTIME_FILE", "/etc/bird/generated/runtime.json"),
    "update_runtime_file": ("UPDATE_RUNTIME_FILE", "/etc/bird/generated/update-runtime.json"),
    "container_log_file": ("CONTAINER_LOG_FILE", "/etc/bird/generated/container.log"),
    "settings_file": ("SETTINGS_FILE", "/etc/bird/generated/settings.json"),
    "settings_env_file": ("SETTINGS_ENV_FILE", "/etc/bird/generated/settings.env"),
    "cache_dir": ("CACHE_DIR", "/etc/bird/generated/cache"),
}


def env_path(name, default):
    return Path(os.environ.get(name, default))


def env_paths(specs):
    return {
        key: env_path(env_name, default)
        for key, (env_name, default) in specs.items()
    }
