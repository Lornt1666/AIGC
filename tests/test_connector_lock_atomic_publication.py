from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
import time

from src.mission_os.connector_kernel import AppendOnlyEvidenceLedger


def test_incomplete_candidate_publication_never_overlaps_critical_sections(tmp_path: Path) -> None:
    publisher_paused = Event()
    release_publisher = Event()
    second_entered = Event()
    release_second = Event()
    first_entered = Event()
    counter_lock = Lock()
    active = 0
    maximum_active = 0

    def pause_before_owner_publication() -> None:
        publisher_paused.set()
        assert release_publisher.wait(timeout=2.0)

    first = AppendOnlyEvidenceLedger(
        tmp_path / "ledger.jsonl",
        lock_timeout_seconds=2.0,
        stale_lock_seconds=0.05,
        publication_hook=pause_before_owner_publication,
    )
    second = AppendOnlyEvidenceLedger(
        tmp_path / "ledger.jsonl",
        lock_timeout_seconds=2.0,
        stale_lock_seconds=0.05,
    )

    def enter(ledger: AppendOnlyEvidenceLedger, entered: Event, release: Event | None) -> None:
        nonlocal active, maximum_active
        with ledger.transaction():
            with counter_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            entered.set()
            if release is not None:
                assert release.wait(timeout=2.0)
            else:
                time.sleep(0.02)
            with counter_lock:
                active -= 1

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(enter, first, first_entered, None)
        assert publisher_paused.wait(timeout=2.0)

        second_future = pool.submit(enter, second, second_entered, release_second)
        assert second_entered.wait(timeout=2.0)

        # The first contender now publishes its fully formed candidate while the
        # second process owns the canonical lock. Atomic rename must fail closed.
        release_publisher.set()
        time.sleep(0.05)
        assert not first_entered.is_set()

        release_second.set()
        second_future.result(timeout=2.0)
        first_future.result(timeout=2.0)

    assert maximum_active == 1
    assert first_entered.is_set()
    assert not first.lock_path.exists()


def test_unreadable_owner_is_never_assumed_stale(tmp_path: Path) -> None:
    ledger = AppendOnlyEvidenceLedger(
        tmp_path / "ledger.jsonl",
        lock_timeout_seconds=0.05,
        stale_lock_seconds=0.01,
    )
    ledger.lock_path.mkdir(parents=True)
    # No owner record: there is no evidence that an owner is dead.
    time.sleep(0.02)

    try:
        with ledger.transaction():
            raise AssertionError("unowned lock must not be stolen")
    except TimeoutError:
        pass

    assert ledger.lock_path.exists()
