import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bgp_antifilter import config_migration
from bgp_antifilter.admin.config import AdminConfig
from bgp_antifilter.runtime_paths import GENERATED_PATH_SPECS, LIST_FILE_SPECS, config_paths, list_paths


class ConfigMigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.generated = self.root / "generated"
        self.legacy = self.generated / "config"
        self.config = self.root / "config"
        self.defaults = self.root / "defaults"
        self.old_bird = self.root / "bird"
        for directory in (self.legacy, self.defaults, self.old_bird):
            directory.mkdir(parents=True, exist_ok=True)
        self.environment = {
            "GENERATED_DIR": str(self.generated), "CONFIG_DIR": str(self.config),
            "DEFAULT_CONFIG_DIR": str(self.defaults), "LEGACY_BIRD_DIR": str(self.old_bird),
        }
        for _variable, default in LIST_FILE_SPECS.values():
            (self.defaults / Path(default).name).write_text("# default\n", encoding="utf-8")

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return config_migration.prepare_user_config(self.environment)

    def test_import_preserves_empty_lists_settings_backups_and_generated_snapshot(self):
        for _variable, default in LIST_FILE_SPECS.values():
            (self.legacy / Path(default).name).write_bytes(b"")
        (self.legacy / "include-domains.txt").write_bytes("пример.рф\r\n".encode("utf-8"))
        settings = b'{"values":{"FETCH_TIMEOUT":"12","INCLUDE_GOOGLE_RANGES":"0"}}\n'
        projection = b"# kept byte-for-byte\nFETCH_TIMEOUT=12\nINCLUDE_GOOGLE_RANGES=0\n"
        (self.generated / "settings.json").write_bytes(settings)
        (self.generated / "settings.env").write_bytes(projection)
        backups = self.generated / "list-backups"
        backups.mkdir()
        (backups / "lists.txt.old.bak").write_bytes(b"old source\n")
        (self.generated / "routes.last-good.conf").write_bytes(b"confirmed routes\n")
        (self.generated / "cache").mkdir()
        (self.generated / "cache/source.cache").write_bytes(b"cached routes\n")
        original = {path: path.read_bytes() for path in self.generated.rglob("*") if path.is_file()}

        self.prepare()

        self.assertEqual((self.config / "lists.txt").read_bytes(), b"")
        self.assertEqual((self.config / "include-domains.txt").read_bytes(), "пример.рф\r\n".encode("utf-8"))
        self.assertEqual((self.config / "settings.json").read_bytes(), settings)
        self.assertEqual((self.config / "settings.env").read_bytes(), projection)
        self.assertEqual((self.config / "list-backups/lists.txt.old.bak").read_bytes(), b"old source\n")
        self.assertEqual(original, {path: path.read_bytes() for path in original})
        self.assertEqual(json.loads((self.config / config_migration.MIGRATION_MARKER).read_text())["version"], 1)
        self.assertFalse((self.config / "routes.last-good.conf").exists())
        self.assertFalse((self.config / "cache").exists())

    def test_new_config_wins_and_settings_pair_is_not_mixed_with_old_env(self):
        self.config.mkdir()
        (self.config / "lists.txt").write_bytes(b"")
        (self.legacy / "lists.txt").write_bytes(b"old list\n")
        (self.config / "settings.json").write_text('{"values":{"FETCH_TIMEOUT":"45"}}', encoding="utf-8")
        (self.generated / "settings.json").write_text('{"values":{"FETCH_TIMEOUT":"12"}}', encoding="utf-8")
        (self.generated / "settings.env").write_text("FETCH_TIMEOUT=12\n", encoding="utf-8")
        self.prepare()
        self.assertEqual((self.config / "lists.txt").read_bytes(), b"")
        self.assertEqual((self.config / "settings.env").read_text(encoding="utf-8"), "FETCH_TIMEOUT=45\n")

    def test_existing_new_settings_env_is_preserved_without_importing_old_json(self):
        self.config.mkdir()
        (self.config / "settings.env").write_text("FETCH_TIMEOUT=45\n", encoding="utf-8")
        (self.generated / "settings.json").write_text('{"values":{"FETCH_TIMEOUT":"12"}}', encoding="utf-8")
        self.prepare()
        self.assertFalse((self.config / "settings.json").exists())
        self.assertEqual((self.config / "settings.env").read_text(), "FETCH_TIMEOUT=45\n")

    def test_restarts_do_not_resurrect_old_settings_or_deleted_lists(self):
        (self.legacy / "lists.txt").write_text("old source\n", encoding="utf-8")
        (self.generated / "settings.json").write_text('{"values":{"FETCH_TIMEOUT":"12"}}', encoding="utf-8")
        self.prepare()
        (self.config / "lists.txt").unlink()
        (self.config / "settings.json").unlink()
        (self.legacy / "lists.txt").write_text("changed old source\n", encoding="utf-8")
        self.prepare()
        self.assertEqual((self.config / "lists.txt").read_text(), "# default\n")
        self.assertFalse((self.config / "settings.json").exists())

    def test_interrupted_copy_can_resume_without_overwriting_completed_targets(self):
        (self.legacy / "lists.txt").write_text("old source\n", encoding="utf-8")
        (self.generated / "settings.json").write_text('{"values":{"FETCH_TIMEOUT":"12"}}', encoding="utf-8")
        (self.generated / "settings.env").write_text("# preserve comments too\nFETCH_TIMEOUT=12\n", encoding="utf-8")
        install = config_migration.install_missing

        def fail_projection(target, **kwargs):
            if target == self.config / "settings.env":
                raise OSError("interrupted")
            return install(target, **kwargs)

        with mock.patch.object(config_migration, "install_missing", side_effect=fail_projection):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertFalse((self.config / config_migration.MIGRATION_MARKER).exists())
        (self.config / "lists.txt").write_text("edited new source\n", encoding="utf-8")
        self.prepare()
        self.assertEqual((self.config / "lists.txt").read_text(), "edited new source\n")
        self.assertEqual((self.config / "settings.env").read_bytes(), (self.generated / "settings.env").read_bytes())

    def test_older_bird_paths_and_custom_target_names_are_supported(self):
        (self.old_bird / "lists.txt").write_text("old mount\n", encoding="utf-8")
        (self.old_bird / "include-asns.txt").write_text("AS64500\n", encoding="utf-8")
        target = self.root / "custom" / "renamed-list.txt"
        self.environment["LISTS_FILE"] = str(target)
        self.prepare()
        self.assertEqual(target.read_text(), "old mount\n")
        self.assertEqual((self.config / "include-asns.txt").read_text(), "AS64500\n")

    def test_extra_config_files_and_existing_backup_conflicts_are_preserved(self):
        (self.legacy / "custom").mkdir()
        (self.legacy / "custom/source.txt").write_text("custom data\n", encoding="utf-8")
        (self.generated / "list-backups").mkdir()
        (self.generated / "list-backups/old.bak").write_text("old\n", encoding="utf-8")
        (self.config / "list-backups").mkdir(parents=True)
        (self.config / "list-backups/old.bak").write_text("new\n", encoding="utf-8")
        self.prepare()
        self.assertEqual((self.config / "custom/source.txt").read_text(), "custom data\n")
        self.assertEqual((self.config / "list-backups/old.bak").read_text(), "new\n")

    def test_defaults_are_used_only_for_missing_lists(self):
        (self.legacy / "lists.txt").write_text("user source\n", encoding="utf-8")
        (self.legacy / "include-domains.txt").write_bytes(b"")
        self.prepare()
        self.assertEqual((self.config / "lists.txt").read_text(), "user source\n")
        self.assertEqual((self.config / "include-domains.txt").read_bytes(), b"")
        self.assertEqual((self.config / "include-countries.txt").read_text(), "# default\n")

    def test_failed_atomic_publish_leaves_no_partial_target_or_marker(self):
        (self.legacy / "lists.txt").write_bytes(b"original\n")
        with mock.patch.object(Path, "replace", side_effect=OSError("publish failed")):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertFalse((self.config / "lists.txt").exists())
        self.assertEqual(list(self.config.glob("*.tmp")), [])
        self.assertFalse((self.config / config_migration.MIGRATION_MARKER).exists())
        self.assertEqual((self.legacy / "lists.txt").read_bytes(), b"original\n")

    def test_config_path_defaults_and_explicit_legacy_paths_stay_consistent(self):
        self.assertNotIn("settings_file", GENERATED_PATH_SPECS)
        paths = config_paths(self.environment)
        self.assertEqual(paths["settings_file"], self.config / "settings.json")
        self.assertEqual(list_paths(self.environment)["urls"], self.config / "lists.txt")
        legacy_env = {**self.environment, "LISTS_FILE": str(self.legacy / "lists.txt"),
                      "SETTINGS_FILE": str(self.generated / "settings.json"), "SETTINGS_ENV_FILE": str(self.generated / "settings.env")}
        config = AdminConfig.from_env(legacy_env)
        self.assertEqual(config.list_files["urls"], self.legacy / "lists.txt")
        self.assertEqual(config.settings_file, self.generated / "settings.json")
        self.assertEqual(config.list_backup_dir, self.generated / "list-backups")


if __name__ == "__main__":
    unittest.main()
