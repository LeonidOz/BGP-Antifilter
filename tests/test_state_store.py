import errno
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from bgp_antifilter.state_store import mutate_state, patch_state, read_state, state_lock, write_state


def increment_state(path, start, count):
    start.wait(10)
    for _ in range(count):
        def increment(current):
            # Expose lost updates if read/modify/write is not one transaction.
            time.sleep(0.001)
            return {**current, "count": current.get("count", 0) + 1}
        mutate_state(path, increment)


def exit_with_lock(path, ready):
    with state_lock(path):
        ready.set()
        os._exit(0)


class StateStoreTests(unittest.TestCase):
    def test_process_writers_do_not_lose_updates_or_publish_partial_json(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            write_state(path, {"count": 0, "preserved": "yes"})
            start = context.Event()
            workers = [context.Process(target=increment_state, args=(path, start, 15)) for _ in range(4)]
            try:
                for worker in workers:
                    worker.start()
                start.set()
                deadline = time.monotonic() + 20
                while any(worker.is_alive() for worker in workers) and time.monotonic() < deadline:
                    # Windows may deny opening a file during os.replace. A
                    # successful raw read must always contain complete JSON.
                    try:
                        content = path.read_text(encoding="utf-8")
                    except PermissionError:
                        if os.name != "nt":
                            raise
                    else:
                        self.assertEqual(json.loads(content)["preserved"], "yes")
                    time.sleep(0.005)
                for worker in workers:
                    worker.join(timeout=1)
                    self.assertEqual(worker.exitcode, 0)
                self.assertEqual(read_state(path), {"count": 60, "preserved": "yes"})
            finally:
                for worker in workers:
                    if worker.is_alive():
                        worker.terminate()
                        worker.join(timeout=5)

    def test_process_exit_releases_lock_without_removing_sidecar(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            ready = context.Event()
            worker = context.Process(target=exit_with_lock, args=(path, ready))
            worker.start()
            try:
                self.assertTrue(ready.wait(10))
                worker.join(timeout=5)
                self.assertEqual(worker.exitcode, 0)
                patch_state(path, recovered=True)
                self.assertTrue(read_state(path)["recovered"])
                self.assertTrue(path.with_name("runtime.json.lock").exists())
            finally:
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=5)

    def test_failed_publish_preserves_previous_json_and_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            write_state(path, {"before": True})
            with mock.patch.object(Path, "replace", side_effect=OSError(errno.EIO, "failed publish")):
                with self.assertRaises(OSError):
                    patch_state(path, after=True)
            self.assertEqual(read_state(path), {"before": True})
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])
            patch_state(path, recovered=True)
            self.assertEqual(read_state(path), {"before": True, "recovered": True})

    def test_transform_failure_does_not_write_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            write_state(path, {"before": True})
            with self.assertRaises(ValueError):
                mutate_state(path, mock.Mock(side_effect=ValueError("bad transition")))
            patch_state(path, after=True)
            self.assertEqual(read_state(path), {"before": True, "after": True})

    def test_missing_corrupt_and_non_object_state_can_be_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            self.assertEqual(read_state(path), {})
            for content in ("{broken", "[]", "null"):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    patch_state(path, active=False)
                    self.assertEqual(read_state(path), {"active": False})

    def test_lock_timeout_does_not_modify_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runtime.json"
            write_state(path, {"before": True})
            with state_lock(path):
                with self.assertRaises(TimeoutError):
                    with state_lock(path, timeout=0):
                        self.fail("acquired an already held lock")
            self.assertEqual(read_state(path), {"before": True})


if __name__ == "__main__":
    unittest.main()
