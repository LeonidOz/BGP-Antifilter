import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.admin_support import admin_application


class BackupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = admin_application(Path(temporary.name))
        for path in self.app.config.list_files.values():
            path.write_text("old\n", encoding="utf-8")

    def test_fast_saves_keep_distinct_backups_and_restore_preserves_current(self):
        self.app.lists.save("urls", "second\n")
        self.app.lists.save("urls", "third\n")
        versions = self.app.lists.history("urls")
        self.assertEqual(len(versions), 2)
        version = self.app.lists.history_version("urls", versions[1]["id"])
        self.assertIn("-third", version["diff"])
        self.assertIn("+old", version["diff"])
        self.app.lists.restore("urls", version["id"], version["current_sha256"])
        self.assertEqual(self.app.lists.read("urls")["content"], "old\n")
        self.assertEqual(len(self.app.lists.history("urls")), 3)

    def test_history_rejects_path_traversal_and_stale_restore(self):
        self.app.lists.save("urls", "new\n")
        version = self.app.lists.history_version("urls", self.app.lists.history("urls")[0]["id"])
        self.app.lists.save("urls", "newer\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.app.lists.restore("urls", version["id"], version["current_sha256"])
        with self.assertRaisesRegex(ValueError, "unknown backup"):
            self.app.lists.history_version("urls", "../settings.json")

    def test_configuration_import_validates_and_restores_after_review(self):
        exported = self.app.backups.export()
        changed = copy.deepcopy(exported)
        changed["lists"]["urls"] = "restored\n"
        changed["settings"]["FETCH_TIMEOUT"] = "45"
        preview = self.app.backups.preview(changed)
        self.assertEqual(self.app.lists.read("urls")["content"], "old\n")
        self.assertIn("+restored", preview["lists"]["urls"])
        result = self.app.backups.restore(preview["id"])
        self.assertTrue(Path(result["backup"]).exists())
        self.assertEqual(self.app.lists.read("urls")["content"], "restored\n")
        self.assertEqual(self.app.settings.effective_settings()["FETCH_TIMEOUT"], "45")
        self.assertIn("FETCH_TIMEOUT=45", self.app.config.settings_env_file.read_text())

    def test_bad_import_never_changes_configuration(self):
        original = self.app.backups.export()
        for mutate in (lambda data: data["settings"].update(MT_IP="bad"),
                       lambda data: data["settings"].update(DNS_RESOLVE_TIMEOUT="nan"),
                       lambda data: data["lists"].update({"../secret": "bad"}),
                       lambda data: data["lists"].update(urls="bad\x00")):
            data = copy.deepcopy(original)
            mutate(data)
            with self.assertRaises(ValueError):
                self.app.backups.preview(data)
            self.assertEqual(self.app.lists.read("urls")["content"], "old\n")

    def test_stale_import_and_partial_write_are_rejected_or_rolled_back(self):
        backup = self.app.backups.export()
        backup["lists"]["urls"] = "replacement\n"
        preview = self.app.backups.preview(backup)
        self.app.lists.save("urls", "edited\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.app.backups.restore(preview["id"])
        preview = self.app.backups.preview(backup)
        with mock.patch.object(self.app.settings, "_save_settings", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.app.backups.restore(preview["id"])
        self.assertEqual(self.app.lists.read("urls")["content"], "edited\n")
        self.assertFalse(self.app.config.update_lock_dir.exists())
