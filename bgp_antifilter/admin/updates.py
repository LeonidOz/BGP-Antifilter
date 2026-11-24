"""Release checks, their cache and the application updater adapter."""

import json
import time
import urllib.error
import urllib.request

from .. import __version__, updater_server


REPOSITORY_URL = "https://github.com/LeonidOz/BGP-Antifilter"


LATEST_RELEASE_API_URL = "https://api.github.com/repos/LeonidOz/BGP-Antifilter/releases/latest"


UPDATE_CHECK_TTL_SECONDS = 15 * 60


def parse_semver(value):
    return tuple(map(int, updater_server.validate_version(value).split(".")))


def github_latest_release(timeout=5):
    request = urllib.request.Request(
        LATEST_RELEASE_API_URL,
        headers={
            "User-Agent": f"BGP-Antifilter-Admin/{__version__}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("latest release payload must be an object")
    tag_name = str(payload.get("tag_name") or "").strip()
    version = tag_name[1:] if tag_name.lower().startswith("v") else tag_name
    if not version:
        raise ValueError("latest release payload does not include tag_name")
    parse_semver(version)
    return {
        "tag_name": tag_name or f"v{version}",
        "version": version,
        "html_url": str(payload.get("html_url") or REPOSITORY_URL),
        "published_at": str(payload.get("published_at") or ""),
        "name": str(payload.get("name") or ""),
        "body": str(payload.get("body") or "")[:12000],
    }


def updater_health():
    return updater_server.health_status()


class UpdatesService:
    def __init__(self):
        self.cache = {"checked_at": 0.0, "payload": None}

    def update_status_payload(self, force=False):
        now = time.time()
        cached = self.cache.get("payload")
        checked_at = float(self.cache.get("checked_at") or 0.0)
        if not force and cached is not None and now - checked_at < UPDATE_CHECK_TTL_SECONDS:
            return dict(cached)

        current_version = __version__
        payload = {
            "ok": False,
            "repository_url": REPOSITORY_URL,
            "current_version": current_version,
            "latest_version": current_version,
            "latest_tag": f"v{current_version}",
            "release_url": REPOSITORY_URL,
            "release_name": "",
            "release_notes": "",
            "published_at": "",
            "update_available": False,
            "error": "",
            "checked_at_unix": int(now),
        }
        try:
            latest = github_latest_release()
            update_available = updater_server.is_newer_version(latest["version"], current_version)
            payload.update({
                "ok": True,
                "latest_version": latest["version"],
                "latest_tag": latest["tag_name"],
                "release_url": latest["html_url"],
                "release_name": latest["name"],
                "release_notes": latest.get("body", ""),
                "published_at": latest["published_at"],
                "update_available": update_available,
            })
        except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError) as exc:
            payload["error"] = str(exc)

        self.cache["checked_at"] = now
        self.cache["payload"] = payload
        return dict(payload)

    def status_payload(self, force=False):
        payload = self.update_status_payload(force=force)
        runtime = updater_server.reconcile_runtime(__version__)
        updater_ok, updater_error = updater_health()
        payload.update({
            "runtime": runtime, "updater_ok": updater_ok, "updater_error": updater_error,
            "apply_available": bool(payload.get("ok")) and bool(payload.get("update_available")) and updater_ok and not runtime.get("active", False),
        })
        return payload

    def start_update(self, version):
        target = updater_server.validate_version(version)
        release = self.update_status_payload(force=True)
        if not release["ok"]:
            raise RuntimeError(f"release check failed: {release['error']}")
        if not release["update_available"] or target != release["latest_version"]:
            raise ValueError("requested version is not the latest available release; check updates again")
        return updater_server.start_update(target)
