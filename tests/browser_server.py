"""Isolated real admin HTTP server for browser tests; BIRD/Docker are simulated.

All lists, snapshots, imports and reload transactions use real application code.
Only host services and release discovery are fixtures. Binds to loopback only.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bgp_antifilter import __version__
from bgp_antifilter.admin.server import AdminHandler, AdminHTTPServer
from bgp_antifilter.route_transaction import RouteManager
from bgp_antifilter.state_store import read_state, write_state
from tests.admin_support import admin_application


def main():
    with tempfile.TemporaryDirectory(prefix="bgp-browser-") as temporary:
        root = Path(temporary)
        os.environ.update(ADMIN_PASSWORD="browser-test", INCLUDE_GOOGLE_RANGES="0", FETCH_ATTEMPTS="1", FETCH_RETRY_DELAY="0", PYTHONPATH=str(ROOT))
        app = admin_application(root)
        app.config.static_root = ROOT / "admin-ui"
        source = root / "source.txt"
        original_run = app.actions.run_command

        def command(args, timeout=120):
            if args[0] == "birdc":
                return {"ok": True, "returncode": 0, "stdout": "BIRD 3.4.0 ready.\nLast reboot on 2026-11-15 00:00:00\nmikrotik BGP master up Established\n", "stderr": "", "duration_seconds": 0}
            if args[0] == "/check-ip.py":
                return original_run([sys.executable, "-m", "bgp_antifilter.check_ip", *args[1:]], timeout)
            return original_run(args, timeout)

        def manager():
            value = RouteManager(app.config, app.settings.command_environment())
            value.configure = lambda: None
            return value

        def reset():
            app.auth.sessions.clear()
            app.auth.login_attempts.clear()
            source.write_text("192.0.2.0/24\n", encoding="utf-8")
            for path in app.config.list_files.values():
                path.write_text("", encoding="utf-8")
            app.config.list_files["urls"].write_text("Example | " + source.as_uri() + "\n", encoding="utf-8")
            app.config.settings_file.unlink(missing_ok=True)
            app.config.settings_env_file.unlink(missing_ok=True)
            manager().apply()

        def reload(preview_id=None):
            started = int(time.time())
            write_state(app.config.reload_result_file, {"active": True, "started_at_unix": started})
            time.sleep(0.3)
            try:
                manager().apply(preview_id)
                result = {"ok": True, "returncode": 0, "stdout": "BIRD accepted updated routes", "stderr": ""}
            except Exception as exc:
                result = {"ok": False, "returncode": 1, "stdout": "", "stderr": str(exc)}
            write_state(app.config.reload_result_file, {**result, "active": False, "started_at_unix": started, "finished_at_unix": int(time.time()), "duration_seconds": 1})

        app.actions.run_command = command
        app.actions.apply_reload = reload
        app.diagnostics.login_network_payload = lambda: {"labels": ["192.0.2.1"]}
        app.diagnostics.network_summary = lambda: {"hostname": "browser-test", "local_ipv4": ["192.0.2.1"], "bird": {}, "dns": {}, "custom_dns": {}, "admin": {"port": "18761"}, "external": {"ok": False, "error": "offline fixture"}}
        major, minor, patch = __version__.split(".")
        next_version = f"{major}.{minor}.{int(patch) + 1}"
        app.updates.status_payload = lambda force=False: {"ok": True, "current_version": __version__, "latest_version": next_version, "latest_tag": "v" + next_version, "update_available": True, "apply_available": False, "updater_ok": False, "updater_error": "Browser fixture", "runtime": {}}

        class Handler(AdminHandler):
            def route_manager(self):
                return manager()

            def do_POST(self):
                if self.path == "/__test/reset":
                    reset()
                    self.send_json({"ok": True})
                elif self.path == "/__test/source":
                    source.write_text(self.read_json()["content"], encoding="utf-8")
                    self.send_json({"ok": True})
                elif self.path == "/__test/expire":
                    app.auth.sessions.clear()
                    self.send_json({"ok": True})
                elif self.path == "/__test/stop":
                    self.send_json({"ok": True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                else:
                    super().do_POST()

        reset()
        server = AdminHTTPServer(("127.0.0.1", 18761), app)
        # Use the test-only handler without changing the production server class.
        server.RequestHandlerClass = Handler
        print("Browser fixture ready", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
