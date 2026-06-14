import tempfile
import unittest
from pathlib import Path

from bgp_antifilter import updater_server


class UpdaterServerTests(unittest.TestCase):
    def test_validate_version_accepts_plain_and_v_prefixed_values(self):
        self.assertEqual(updater_server.validate_version("0.2.6"), "0.2.6")
        self.assertEqual(updater_server.validate_version("v0.2.7"), "0.2.7")

    def test_validate_version_rejects_invalid_format(self):
        with self.assertRaises(ValueError):
            updater_server.validate_version("latest")

    def test_update_env_version_replaces_existing_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("FOO=bar\nBGP_ANTIFILTER_VERSION=0.2.5\n", encoding="utf-8")

            updater_server.update_env_version(path, "0.2.6")

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "FOO=bar\nBGP_ANTIFILTER_VERSION=0.2.6\n",
            )

    def test_update_env_version_appends_missing_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("FOO=bar\n", encoding="utf-8")

            updater_server.update_env_version(path, "0.2.6")

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "FOO=bar\n\nBGP_ANTIFILTER_VERSION=0.2.6\n",
            )


if __name__ == "__main__":
    unittest.main()
