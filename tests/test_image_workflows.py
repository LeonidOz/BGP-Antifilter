from pathlib import Path
import unittest


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


class ImageWorkflowTests(unittest.TestCase):
    def test_main_publishes_edge_and_sha_but_not_latest(self):
        workflow = (WORKFLOWS / "docker-publish.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main]", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn(
            "type=raw,value=edge,enable=${{ github.ref == 'refs/heads/main' }}",
            workflow,
        )
        self.assertIn("type=sha,prefix=sha-", workflow)
        self.assertNotIn("value=latest", workflow)
        self.assertNotIn("type=semver", workflow)

    def test_release_keeps_latest_and_version_tags(self):
        workflow = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
        self.assertIn('      - "v*"', workflow)
        self.assertIn("type=raw,value=latest", workflow)
        self.assertIn("type=semver,pattern={{version}}", workflow)
        self.assertNotIn("value=edge", workflow)

    def test_both_publish_workflows_build_both_architectures(self):
        for name in ("docker-publish.yml", "release.yml"):
            with self.subTest(workflow=name):
                workflow = (WORKFLOWS / name).read_text(encoding="utf-8")
                self.assertIn("platforms: linux/amd64,linux/arm64", workflow)
                self.assertIn("uses: docker/setup-qemu-action@", workflow)
                self.assertIn("uses: docker/setup-buildx-action@", workflow)


if __name__ == "__main__":
    unittest.main()
