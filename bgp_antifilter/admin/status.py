"""Public and authenticated status projections."""

import time

from .. import __version__
from ..state_store import read_state
from .storage import json_load, tail_text, text_load


def short_duration(value):
    try:
        seconds = max(0, int(float(value)))
    except (TypeError, ValueError):
        return None
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes}m" if remainder == 0 else f"{minutes}m{remainder}s"
    if seconds < 86400:
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        return f"{hours}h" if minutes == 0 else f"{hours}h{minutes}m"
    days, remainder = divmod(seconds, 86400)
    hours = remainder // 3600
    return f"{days}d" if hours == 0 else f"{days}d{hours}h"


def parse_metrics(text):
    values = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or " " not in line:
            continue
        key, value = line.rsplit(" ", 1)
        try:
            values[key] = float(value)
        except ValueError:
            continue
    return values


class StatusService:
    def __init__(self, config, settings, actions):
        self.config = config
        self.settings = settings
        self.actions = actions
        self.started_at = int(time.time())

    def routes(self):
        return text_load(self.config.routes_file)

    def metrics(self):
        return text_load(self.config.metrics_file)

    def logs(self):
        return tail_text(self.config.container_log_file)

    def public_status_payload(self, now=None):
        now_unix = int(time.time() if now is None else now)
        status = json_load(self.config.status_file, {})
        routes = status.get("routes") if isinstance(status, dict) else {}
        updated_at_unix = status.get("updated_at_unix") if isinstance(status, dict) else None
        duration_seconds = status.get("duration_seconds") if isinstance(status, dict) else None
        route_count = routes.get("final") if isinstance(routes, dict) else None
        return {
            "routes": route_count if isinstance(route_count, int) else route_count if isinstance(route_count, float) else 0,
            "last_generation_ago": short_duration(now_unix - updated_at_unix) if isinstance(updated_at_unix, (int, float)) else None,
            "generation_time": short_duration(duration_seconds),
            "uptime": short_duration(now_unix - self.started_at),
        }

    def route_count_from_file(self):
        if not self.config.routes_file.exists():
            return 0
        return sum(1 for line in self.config.routes_file.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())

    def status_payload(self):
        status = json_load(self.config.status_file, {})
        runtime = self.actions.visible_runtime_state(read_state(self.config.runtime_file))
        reload_result = self.actions.read_reload_result()
        metrics = parse_metrics(text_load(self.config.metrics_file))
        bird = self.actions.run_command(["birdc", "show", "status"], timeout=5)
        bgp_protocol = self.settings.effective_settings().get("BGP_PROTOCOL", "mikrotik")
        bgp = self.actions.run_command(["birdc", "show", "protocols", bgp_protocol], timeout=5)
        return {
            "version": __version__, "status": status, "runtime": runtime, "metrics": metrics,
            "routes_file_count": self.route_count_from_file(), "bird": bird, "bgp": bgp,
            "reload_result": reload_result,
        }
