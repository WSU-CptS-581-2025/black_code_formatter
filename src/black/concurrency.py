"""
Formatting many files at once via multiprocessing. Contains entrypoint and utilities.

NOTE: this module is only imported if we need to format several files at once.
"""

import asyncio
import logging
import os
import signal
import sys
import traceback
from collections.abc import Iterable
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import Manager
from pathlib import Path
from typing import Any, Optional

from mypy_extensions import mypyc_attr

from black import WriteBack, format_file_in_place
from black.cache import Cache
from black.mode import Mode
from black.output import err
from black.report import Changed, Report


def maybe_install_uvloop() -> None:
    """If our environment has uvloop installed we use it.

    This is called only from command-line entry points to avoid
    interfering with the parent process if Black is used as a library.
    """
    try:
        import uvloop

        uvloop.install()
    except ImportError:
        pass


def cancel(tasks: Iterable["asyncio.Future[Any]"]) -> None:
    """asyncio signal handler that cancels all `tasks` and reports to stderr."""
    err("Aborted!")
    for task in tasks:
        task.cancel()


def shutdown(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel all pending tasks on `loop`, wait for them, and close the loop."""
    try:
        # This part is borrowed from asyncio/runners.py in Python 3.7b2.
        to_cancel = [task for task in asyncio.all_tasks(loop) if not task.done()]
        if not to_cancel:
            return

        for task in to_cancel:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*to_cancel, return_exceptions=True))
    finally:
        # `concurrent.futures.Future` objects cannot be cancelled once they
        # are already running. There might be some when the `shutdown()` happened.
        # Silence their logger's spew about the event loop being closed.
        cf_logger = logging.getLogger("concurrent.futures")
        cf_logger.setLevel(logging.CRITICAL)
        loop.close()


# diff-shades depends on being to monkeypatch this function to operate. I know it's
# not ideal, but this shouldn't cause any issues ... hopefully. ~ichard26
@mypyc_attr(patchable=True)
def reformat_many(
    sources: set[Path],
    fast: bool,
    write_back: WriteBack,
    mode: Mode,
    report: Report,
    workers: Optional[int],
) -> None:
    """Reformat multiple files using a ProcessPoolExecutor."""
    maybe_install_uvloop()

    executor: Executor
    if workers is None:
        workers = int(os.environ.get("BLACK_NUM_WORKERS", 0))
        workers = workers or os.cpu_count() or 1
    if sys.platform == "win32":
        # Work around https://bugs.python.org/issue26903
        workers = min(workers, 60)
    try:
        executor = ProcessPoolExecutor(max_workers=workers)
    except (ImportError, NotImplementedError, OSError):
        # we arrive here if the underlying system does not support multi-processing
        # like in AWS Lambda or Termux, in which case we gracefully fallback to
        # a ThreadPoolExecutor with just a single worker (more workers would not do us
        # any good due to the Global Interpreter Lock)
        executor = ThreadPoolExecutor(max_workers=1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            schedule_formatting(
                sources=sources,
                fast=fast,
                write_back=write_back,
                mode=mode,
                report=report,
                loop=loop,
                executor=executor,
            )
        )
    finally:
        try:
            shutdown(loop)
        finally:
            asyncio.set_event_loop(None)
        if executor is not None:
            executor.shutdown()


async def schedule_formatting(
    sources: set[Path],
    fast: bool,
    write_back: WriteBack,
    mode: Mode,
    report: "Report",
    loop: asyncio.AbstractEventLoop,
    executor: "Executor",
) -> None:
    """Run formatting of `sources` in parallel using the provided `executor`.

    (Use ProcessPoolExecutors for actual parallelism.)

    `write_back`, `fast`, and `mode` options are passed to
    :func:`format_file_in_place`.
    """
    sources, sources_to_cache = _prepare_sources(sources, write_back, mode, report)
    if not sources:
        return

    lock = _get_lock_if_needed(write_back)
    tasks = _create_formatting_tasks(sources, fast, mode, write_back, lock, loop, executor)

    pending = tasks.keys()
    _setup_signal_handlers(loop, pending)
    
    await _process_tasks(pending, tasks, report, write_back, sources_to_cache)
    
    if sources_to_cache:
        Cache.read(mode).write(sources_to_cache)


def _prepare_sources(
    sources: set[Path], write_back: WriteBack, mode: Mode, report: "Report"
) -> tuple[set[Path], list[Path]]:
    """Filter sources using cache and report cached files."""
    cache = Cache.read(mode)
    sources_to_cache = []
    
    if write_back not in (WriteBack.DIFF, WriteBack.COLOR_DIFF):
        sources, cached = cache.filtered_cached(sources)
        for src in sorted(cached):
            report.done(src, Changed.CACHED)
            
    return sources, sources_to_cache


def _get_lock_if_needed(write_back: WriteBack) -> Optional[Any]:
    """Create a lock for diff output to prevent interleaved output."""
    if write_back in (WriteBack.DIFF, WriteBack.COLOR_DIFF):
        # For diff output, we need locks to ensure we don't interleave output
        # from different processes.
        manager = Manager()
        return manager.Lock()
    return None


def _create_formatting_tasks(
    sources: set[Path],
    fast: bool,
    mode: Mode,
    write_back: WriteBack,
    lock: Optional[Any],
    loop: asyncio.AbstractEventLoop,
    executor: "Executor",
) -> dict[asyncio.Future, Path]:
    """Create async tasks for formatting each source file."""
    return {
        asyncio.ensure_future(
            loop.run_in_executor(
                executor, format_file_in_place, src, fast, mode, write_back, lock
            )
        ): src
        for src in sorted(sources)
    }


def _setup_signal_handlers(
    loop: asyncio.AbstractEventLoop, pending: set[asyncio.Future]
) -> None:
    """Set up signal handlers for graceful cancellation."""
    try:
        loop.add_signal_handler(signal.SIGINT, cancel, pending)
        loop.add_signal_handler(signal.SIGTERM, cancel, pending)
    except NotImplementedError:
        # There are no good alternatives for these on Windows.
        pass


async def _process_tasks(
    pending: set[asyncio.Future],
    tasks: dict[asyncio.Future, Path],
    report: "Report",
    write_back: WriteBack,
    sources_to_cache: list[Path],
) -> None:
    """Process completed tasks and update reporting/caching."""
    cancelled = []
    
    while pending:
        done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            src = tasks.pop(task)
            if task.cancelled():
                cancelled.append(task)
            elif exc := task.exception():
                _handle_task_exception(src, exc, report)
            else:
                _handle_task_success(src, task.result(), write_back, sources_to_cache, report)
    
    if cancelled:
        await asyncio.gather(*cancelled, return_exceptions=True)


def _handle_task_exception(src: Path, exc: Exception, report: "Report") -> None:
    """Handle exception from a formatting task."""
    if report.verbose:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    report.failed(src, str(exc))


def _handle_task_success(
    src: Path,
    was_changed: bool,
    write_back: WriteBack,
    sources_to_cache: list[Path],
    report: "Report",
) -> None:
    """Handle successful completion of a formatting task."""
    changed = Changed.YES if was_changed else Changed.NO
    # If the file was written back or was successfully checked as
    # well-formatted, store this information in the cache.
    if write_back is WriteBack.YES or (
        write_back is WriteBack.CHECK and changed is Changed.NO
    ):
        sources_to_cache.append(src)
    report.done(src, changed)
