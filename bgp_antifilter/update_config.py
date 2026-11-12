"""Environment options shared by source collection and the update CLI."""

import os

DEFAULT_CACHE_MAX_AGE = 7 * 24 * 60 * 60
DEFAULT_MIN_PREFIX_LENGTH = 8


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name, str(default))
    try:
        number = int(value)
    except ValueError:
        raise SystemExit(f"{name} must be an integer")

    if number <= 0:
        raise SystemExit(f"{name} must be greater than zero")

    return number


def env_float(name, default):
    value = os.environ.get(name, str(default))
    try:
        number = float(value)
    except ValueError:
        raise SystemExit(f"{name} must be a number")
    if number <= 0:
        raise SystemExit(f"{name} must be greater than zero")
    return number
