"""Bounded worker pools used before deterministic source aggregation."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait


def bounded_results(function, items, workers, on_wait=None):
    """Yield (item, result) as tasks finish, with at most workers pending tasks."""
    iterator = iter(items)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {}

        def submit_next():
            try:
                item = next(iterator)
            except StopIteration:
                return False
            pending[executor.submit(function, item)] = item
            return True

        for _ in range(workers):
            if not submit_next():
                break
        while pending:
            completed, _ = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
            if on_wait is not None:
                on_wait()
            for future in completed:
                item = pending.pop(future)
                yield item, future.result()
                submit_next()
