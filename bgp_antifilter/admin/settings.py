"""Settings schema, validation and persistence independent of HTTP."""

import ipaddress
import json
import os
import shlex
import time

from .. import dns_resolver
from .storage import json_load, write_text_atomic


SETTINGS_SECTIONS = [
    {
        "id": "update",
        "title": "Обновление",
        "items": [
            {"key": "UPDATE_INTERVAL", "type": "int", "default": "1800", "min": 30, "max": 86400, "unit": "sec"},
            {"key": "CACHE_MAX_AGE", "type": "int", "default": "604800", "min": 60, "max": 2592000, "unit": "sec"},
            {"key": "FETCH_TIMEOUT", "type": "int", "default": "30", "min": 1, "max": 300, "unit": "sec"},
            {"key": "FETCH_ATTEMPTS", "type": "int", "default": "5", "min": 1, "max": 20},
            {"key": "FETCH_RETRY_DELAY", "type": "number", "default": "5", "min": 0, "max": 120, "unit": "sec"},
            {"key": "INCLUDE_GOOGLE_RANGES", "type": "bool", "default": "1", "hidden": True},
            {"key": "REQUIRE_ALL_URL_SOURCES", "type": "bool", "default": "0"},
            {"key": "DNS_RESOLVE_TIMEOUT", "type": "number", "default": "3", "min": 0.1, "max": 30, "unit": "sec"},
            {"key": "DNS_RESOLVERS", "type": "dns_list", "default": "", "allow_empty": True},
        ],
    },
    {
        "id": "security",
        "title": "Безопасность генерации",
        "items": [
            {"key": "MIN_PREFIX_LENGTH", "type": "int", "default": "8", "min": 1, "max": 32},
            {"key": "ALLOW_BROAD_ROUTES", "type": "bool", "default": "0"},
        ],
    },
    {
        "id": "bird",
        "title": "BIRD / BGP",
        "items": [
            {"key": "MY_AS", "type": "asn", "default": "64500", "requires_restart": True},
            {"key": "MT_AS", "type": "asn", "default": "65455", "requires_restart": True},
            {"key": "MT_IP", "type": "ipv4", "default": "192.168.55.1", "requires_restart": True},
            {"key": "BIRD_IP", "type": "ipv4", "default": "192.168.55.5", "requires_restart": True},
            {"key": "ROUTER_ID", "type": "ipv4", "default": "192.168.55.5", "requires_restart": True},
            {"key": "BGP_COMMUNITY", "type": "community", "default": "65432,500", "requires_restart": True},
            {"key": "BGP_PROTOCOL", "type": "string", "default": "mikrotik"},
            {"key": "HEALTHCHECK_REQUIRE_BGP", "type": "bool", "default": "1"},
        ],
    },
]


SETTINGS_BY_KEY = {item["key"]: item for section in SETTINGS_SECTIONS for item in section["items"]}


def validate_setting(key, value):
    spec = SETTINGS_BY_KEY.get(key)
    if not spec:
        raise ValueError(f"unknown setting: {key}")
    raw = str(value).strip()
    if raw == "" and spec.get("allow_empty"):
        return ""
    if raw == "":
        raise ValueError(f"{key} must not be empty")
    setting_type = spec["type"]
    if setting_type == "bool":
        if raw.lower() in {"1", "true", "yes", "on"}:
            return "1"
        if raw.lower() in {"0", "false", "no", "off"}:
            return "0"
        raise ValueError(f"{key} must be 0 or 1")
    if setting_type in {"int", "asn"}:
        try:
            number = int(raw)
        except ValueError as exc:
            raise ValueError(f"{key} must be an integer") from exc
        if setting_type == "asn" and not 1 <= number <= 4294967295:
            raise ValueError(f"{key} must be between 1 and 4294967295")
        if "min" in spec and number < spec["min"]:
            raise ValueError(f"{key} must be at least {spec['min']}")
        if "max" in spec and number > spec["max"]:
            raise ValueError(f"{key} must be at most {spec['max']}")
        return str(number)
    if setting_type == "number":
        try:
            number = float(raw)
        except ValueError as exc:
            raise ValueError(f"{key} must be a number") from exc
        if "min" in spec and number < spec["min"]:
            raise ValueError(f"{key} must be at least {spec['min']}")
        if "max" in spec and number > spec["max"]:
            raise ValueError(f"{key} must be at most {spec['max']}")
        return str(int(number)) if number.is_integer() else str(number)
    if setting_type == "dns_list":
        try:
            values = dns_resolver.parse_nameservers(raw)
        except ValueError as exc:
            raise ValueError(f"{key} must contain IPv4 DNS servers separated by spaces or commas") from exc
        if not values:
            raise ValueError(f"{key} must contain at least one IPv4 address")
        return ",".join(values)
    if setting_type == "ipv4":
        try:
            return str(ipaddress.IPv4Address(raw))
        except ValueError as exc:
            raise ValueError(f"{key} must be a valid IPv4 address") from exc
    if setting_type == "community":
        parts = raw.split(",")
        if len(parts) != 2:
            raise ValueError(f"{key} must use AS,VALUE format")
        numbers = []
        for part in parts:
            try:
                number = int(part.strip())
            except ValueError as exc:
                raise ValueError(f"{key} parts must be integers") from exc
            if not 0 <= number <= 65535:
                raise ValueError(f"{key} parts must be between 0 and 65535")
            numbers.append(number)
        return f"{numbers[0]},{numbers[1]}"
    if setting_type == "string":
        if not raw.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"{key} contains unsupported characters")
        return raw
    raise ValueError(f"{key} has unsupported type")


class SettingsService:
    def __init__(self, config):
        self.config = config

    def settings_overrides(self):
        data = json_load(self.config.settings_file, {})
        if not isinstance(data, dict):
            return {}
        values = data.get("values", data)
        if not isinstance(values, dict):
            return {}
        return {key: str(value) for key, value in values.items() if key in SETTINGS_BY_KEY}

    def effective_settings(self):
        overrides = self.settings_overrides()
        result = {}
        for key, spec in SETTINGS_BY_KEY.items():
            base = os.environ.get(key, spec["default"])
            result[key] = overrides.get(key, str(base))
        return result

    def base_setting_value(self, key):
        spec = SETTINGS_BY_KEY[key]
        return validate_setting(key, os.environ.get(key, spec["default"]))

    def command_environment(self):
        env = os.environ.copy()
        env.update(self.effective_settings())
        return env

    def save_settings(self, values):
        normalized = {}
        for key, value in values.items():
            if key not in SETTINGS_BY_KEY:
                continue
            setting_value = validate_setting(key, value)
            if setting_value != self.base_setting_value(key):
                normalized[key] = setting_value
        payload = {
            "updated_at": int(time.time()),
            "values": normalized,
        }
        write_text_atomic(self.config.settings_file, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        env_lines = [f"{key}={shlex.quote(value)}" for key, value in sorted(normalized.items())]
        write_text_atomic(self.config.settings_env_file, "\n".join(env_lines) + ("\n" if env_lines else ""))
        return normalized

    def settings_payload(self):
        overrides = self.settings_overrides()
        effective = self.effective_settings()
        sections = []
        for section in SETTINGS_SECTIONS:
            section_items = []
            for item in section["items"]:
                if item.get("hidden"):
                    continue
                key = item["key"]
                base_value = self.base_setting_value(key)
                value = validate_setting(key, effective[key])
                section_items.append({
                    **item,
                    "value": value,
                    "env_value": base_value,
                    "overridden": value != base_value,
                })
            sections.append({**section, "items": section_items})
        return {
            "sections": sections,
            "values": effective,
            "overrides": overrides,
            "settings_file": str(self.config.settings_file),
            "settings_env_file": str(self.config.settings_env_file),
        }
