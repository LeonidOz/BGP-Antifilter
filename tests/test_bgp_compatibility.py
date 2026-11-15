import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from bgp_antifilter.bgp_config import peer_environment
from bgp_antifilter.container_runtime import render_bird_config
from tests.admin_support import admin_application

ROOT = Path(__file__).resolve().parents[1]


class BgpCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.app = admin_application(self.root)

    def test_legacy_environment_and_custom_templates_keep_working(self):
        env = {"MT_IP": "192.0.2.10", "MT_AS": "64510", "BGP_PROTOCOL": "mikrotik"}
        with mock.patch.dict(os.environ, env, clear=True):
            settings = self.app.settings.effective_settings()
            self.assertEqual(settings["PEER_IP"], env["MT_IP"])
            self.assertEqual(settings["PEER_AS"], env["MT_AS"])
            command = self.app.settings.command_environment()
            self.assertEqual(command["MT_IP"], command["PEER_IP"])
            template = self.root / "template"
            output = self.root / "output"
            template.write_text("$PEER_IP $MT_IP $PEER_AS $MT_AS $BGP_PROTOCOL", encoding="utf-8")
            render_bird_config(template, output)
            self.assertEqual(output.read_text(), "192.0.2.10 192.0.2.10 64510 64510 mikrotik")

    def test_canonical_env_wins_but_legacy_persisted_settings_override_environment(self):
        env = {"PEER_IP": "192.0.2.20", "MT_IP": "192.0.2.10", "PEER_AS": "64520", "MT_AS": "64510"}
        self.assertEqual(peer_environment(env)["MT_IP"], "192.0.2.20")
        self.app.config.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.app.config.settings_file.write_text(json.dumps({"values": {"MT_IP": "192.0.2.30", "MT_AS": "64530"}}))
        with mock.patch.dict(os.environ, env, clear=True):
            settings = self.app.settings.effective_settings()
            self.assertEqual(settings["PEER_IP"], "192.0.2.30")
            self.assertEqual(settings["PEER_AS"], "64530")
            self.app.settings.save_settings({"MT_IP": "192.0.2.40", "MT_AS": "64540"})
            saved = json.loads(self.app.config.settings_file.read_text())["values"]
            self.assertEqual(saved, {"PEER_IP": "192.0.2.40", "PEER_AS": "64540"})
            self.assertNotIn("MT_", self.app.config.settings_env_file.read_text())
            self.assertEqual(self.app.settings.command_environment()["MT_AS"], "64540")

    def test_old_configuration_backups_are_imported_under_canonical_names(self):
        backup = self.app.backups.export()
        backup["settings"]["MT_IP"] = backup["settings"].pop("PEER_IP")
        backup["settings"]["MT_AS"] = backup["settings"].pop("PEER_AS")
        backup["settings"]["MT_IP"] = "192.0.2.55"
        backup["settings"]["BGP_PROTOCOL"] = "mikrotik"
        preview = self.app.backups.preview(backup)
        self.app.backups.restore(preview["id"])
        self.assertEqual(self.app.settings.effective_settings()["PEER_IP"], "192.0.2.55")
        self.assertEqual(self.app.settings.effective_settings()["BGP_PROTOCOL"], "mikrotik")
        self.assertNotIn("MT_IP", self.app.backups.export()["settings"])

    def test_partial_legacy_updates_preserve_unrelated_overrides(self):
        self.app.settings.save_settings({"MT_IP": "192.0.2.30", "FETCH_TIMEOUT": "11"})
        self.app.settings.update_settings({"MT_AS": "64530"})
        effective = self.app.settings.effective_settings()
        self.assertEqual(effective["PEER_IP"], "192.0.2.30")
        self.assertEqual(effective["PEER_AS"], "64530")
        self.assertEqual(effective["FETCH_TIMEOUT"], "11")

    def test_inherited_runtime_override_is_not_mistaken_for_compose_base(self):
        self.app.config.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.app.config.settings_file.write_text(json.dumps({"values": {"MT_IP": "192.0.2.30"}}))
        with mock.patch.dict(os.environ, {"PEER_IP": "192.0.2.30", "BGP_BASE_PEER_IP": "192.0.2.20"}, clear=True):
            self.app.settings.update_settings({"FETCH_TIMEOUT": "11"})
            self.assertEqual(self.app.settings.settings_overrides()["PEER_IP"], "192.0.2.30")
            self.assertEqual(self.app.settings.base_setting_value("PEER_IP"), "192.0.2.20")
            self.app.settings.save_settings({})
            self.assertEqual(self.app.settings.effective_settings()["PEER_IP"], "192.0.2.20")

    def test_conflicting_or_invalid_aliases_are_rejected_before_writing(self):
        with self.assertRaisesRegex(ValueError, "must match"):
            self.app.settings.save_settings({"PEER_IP": "192.0.2.1", "MT_IP": "192.0.2.2"})
        backup = self.app.backups.export()
        for value, message in [("bad", "MT_IP must be a valid"), ("192.0.2.99", "must match")]:
            candidate = copy.deepcopy(backup)
            candidate["settings"]["MT_IP"] = value
            with self.assertRaisesRegex(ValueError, message):
                self.app.backups.preview(candidate)
        self.assertFalse(self.app.config.settings_file.exists())

    @unittest.skipUnless(shutil.which("sh"), "Requires POSIX shell")
    def test_legacy_shell_overrides_win_and_removed_overrides_restore_base(self):
        saved = self.root / "settings.env"
        saved.write_text("MT_IP=192.0.2.30\nMT_AS=64530\n")
        script = '''. "$LIB"
load_settings_env
printf '%s %s %s %s\n' "$PEER_IP" "$PEER_AS" "$MT_IP" "$MT_AS"
: > "$SETTINGS_ENV_FILE"
sh -c '. "$LIB"; load_settings_env; printf "%s %s\n" "$PEER_IP" "$PEER_AS"'
load_settings_env
printf '%s %s\n' "$PEER_IP" "$PEER_AS"
'''
        result = subprocess.run(["sh", "-c", script], env={**os.environ, "LIB": str(ROOT / "deploy/lib.sh"),
                                "SETTINGS_ENV_FILE": str(saved), "PEER_IP": "192.0.2.20", "PEER_AS": "64520"},
                                text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout.splitlines(), ["192.0.2.30 64530 192.0.2.30 64530", "192.0.2.20 64520", "192.0.2.20 64520"])
