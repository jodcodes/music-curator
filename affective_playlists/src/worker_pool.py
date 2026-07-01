"""
Shared bounded worker pool for all parallel flows.

Usage:
    pool = WorkerPool(max_workers=4)
    results = pool.map(fn, items)

ponytail: ThreadPoolExecutor per call, not a persistent daemon pool.
Ceiling: no work-stealing or priority queues; upgrade to ray/celery if needed.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable, List, Optional, Tuple, TypeVar

from src.logger import setup_logger

logger = setup_logger(__name__)

T = TypeVar("T")
R = TypeVar("R")

# Global cap so no single flow can monopolize the machine.
_GLOBAL_MAX_WORKERS = int(os.getenv("AFFECTIVE_MAX_WORKERS", "8"))
_DEFAULT_WORKERS = min(4, max(2, (os.cpu_count() or 2)))


def resolve_workers(requested: Optional[int], item_count: int) -> int:
    """Return an appropriate worker count given a request and item count."""
    if item_count <= 1:
        return 1
    cap = min(_GLOBAL_MAX_WORKERS, item_count)
    if requested is not None and requested > 0:
        return min(requested, cap)
    return min(_DEFAULT_WORKERS, cap)


def map_parallel(
    fn: Callable[[T], R],
    items: Iterable[T],
    workers: Optional[int] = None,
    label: str = "items",
) -> List[Tuple[T, R | Exception]]:
    """
    Run fn over items in a bounded thread pool.

    Returns list of (item, result_or_exception) pairs in completion order.
    Never raises — callers decide how to handle per-item errors.
    """
    item_list = list(items)
    if not item_list:
        return []

    n = resolve_workers(workers, len(item_list))
    if n <= 1:
        results = []
        for item in item_list:
            try:
                results.append((item, fn(item)))
            except Exception as exc:
                logger.warning("Worker error on %s item: %s", label, exc)
                results.append((item, exc))
        return results

    logger.debug("Processing %d %s with %d workers", len(item_list), label, n)
    results: List[Tuple[T, R | Exception]] = []
    with ThreadPoolExecutor(max_workers=n) as pool:
        future_to_item = {pool.submit(fn, item): item for item in item_list}
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                results.append((item, future.result()))
            except Exception as exc:
                logger.warning("Worker error on %s item: %s", label, exc)
                results.append((item, exc))
    return results


# Self-check — runs if invoked directly.
if __name__ == "__main__":
    import time

    def slow_double(x: int) -> int:
        time.sleep(0.01)
        return x * 2

    out = map_parallel(slow_double, range(10), workers=4, label="ints")
    assert len(out) == 10, "expected 10 results"
    errors = [r for _, r in out if isinstance(r, Exception)]
    assert not errors, f"unexpected errors: {errors}"

    out_err = map_parallel(lambda x: 1 / x, [1, 0, 2], workers=2, label="divs")
    assert len(out_err) == 3
    assert isinstance(out_err[1][1], Exception) or any(
        isinstance(r, Exception) for _, r in out_err
    )

    print("worker_pool: all checks passed")
