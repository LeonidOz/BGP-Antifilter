"""Command execution and reload lifecycle independent of HTTP handlers."""

import json
import subprocess
import threading
import time

from .. import runtime_state
from ..state_store import read_state, write_state
from .storage import append_text


def parse_command_status(stdout):
    decoder = json.JSONDecoder()
    parsed = None
    text = stdout or ""
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "sources" in value and "routes" in value:
            parsed = value
    return parsed


class ActionsService:
    def __init__(self, config, settings):
        self.config = config
        self.settings = settings
        self.reload_lock = threading.Lock()
        self.reload_thread = None

    def write_reload_result(self, payload):
        write_state(self.config.reload_result_file, payload)

    def read_reload_result(self):
        return read_state(self.config.reload_result_file)

    def run_command(self, command, timeout=120):
        started = time.time()
        try:
            completed = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
                env=self.settings.command_environment(),
            )
            return {
                "ok": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "duration_seconds": round(time.time() - started, 3),
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "returncode": None,
                "stdout": exc.stdout or "",
                "stderr": f"command timed out after {timeout} seconds",
                "duration_seconds": round(time.time() - started, 3),
            }
        except OSError as exc:
            return {
                "ok": False,
                "returncode": None,
                "stdout": "",
                "stderr": str(exc),
                "duration_seconds": round(time.time() - started, 3),
            }

    def reload_runtime_active(self):
        runtime = self.reconcile_runtime_state(read_state(self.config.runtime_file))
        return bool(runtime.get("generation_active"))

    def reload_thread_active(self):
        return self.reload_thread is not None and self.reload_thread.is_alive()

    def reload_lock_active(self):
        return self.config.update_lock_dir.exists()

    def reconcile_runtime_state(self, runtime):
        return runtime_state.reconcile_generation(
            self.config.runtime_file, runtime, lambda: self.reload_thread_active() or self.reload_lock_active(),
        )

    def apply_reload(self):
        started_at = int(time.time())
        result = self.run_command(["/reload-routes.sh"], timeout=600)
        finished_at = int(time.time())
        payload = {
            "active": False,
            "started_at_unix": started_at,
            "finished_at_unix": finished_at,
            **result,
        }
        try:
            self.write_reload_result(payload)
        except OSError:
            pass
        try:
            lines = [
                f"[manual-reload] started={started_at} finished={finished_at} ok={result.get('ok')} returncode={result.get('returncode')}\n",
            ]
            if result.get("stdout"):
                lines.append("[manual-reload][stdout]\n")
                lines.append(result["stdout"])
                if not result["stdout"].endswith("\n"):
                    lines.append("\n")
            if result.get("stderr"):
                lines.append("[manual-reload][stderr]\n")
                lines.append(result["stderr"])
                if not result["stderr"].endswith("\n"):
                    lines.append("\n")
            append_text(self.config.container_log_file, "".join(lines))
        except OSError:
            pass

    def start_reload(self):
        with self.reload_lock:
            if self.reload_runtime_active() or (self.reload_thread is not None and self.reload_thread.is_alive()):
                raise RuntimeError("reload already running")
            try:
                self.write_reload_result({
                    "active": True,
                    "accepted": True,
                    "ok": None,
                    "returncode": None,
                    "stdout": "",
                    "stderr": "",
                    "duration_seconds": 0,
                    "started_at_unix": int(time.time()),
                    "finished_at_unix": None,
                })
            except OSError:
                pass
            self.reload_thread = threading.Thread(target=self.apply_reload, daemon=True)
            self.reload_thread.start()
        return {
            "ok": True,
            "accepted": True,
            "message": "reload started",
        }

    def visible_runtime_state(self, runtime):
        state = self.reconcile_runtime_state(runtime)
        if state.get("generation_active") or not self.reload_thread_active():
            return state
        state.update({
            "generation_active": True,
            "generation_kind": state.get("generation_kind") or "manual",
            "generation_message": state.get("generation_message") or "Starting manual route update",
            "generation_stage": state.get("generation_stage") or "bootstrap",
            "generation_stage_message": state.get("generation_stage_message") or "Waiting for route generator to publish progress",
        })
        return state

    def run_route_check(self, mode):
        result = self.run_command(["/update-routes.py", mode], timeout=300)
        parsed_status = parse_command_status(result.get("stdout", ""))
        if parsed_status is not None:
            result["status"] = parsed_status
        return result

    def check_target(self, target, diagnostics):
        addresses, error = diagnostics.resolve_ipv4_targets(target)
        if error:
            raise ValueError(error)
        results = []
        ok = True
        for address in addresses:
            result = self.run_command(["/check-ip.py", address, "--json"], timeout=30)
            parsed = None
            if result["stdout"]:
                try:
                    parsed = json.loads(result["stdout"])
                except json.JSONDecodeError:
                    pass
            result["result"] = parsed
            results.append(result)
            ok = ok and result["ok"]
        return {
            "ok": ok, "target": target, "addresses": addresses,
            "result": results[0]["result"] if len(results) == 1 else None,
            "results": results,
        }
