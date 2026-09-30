"""Benchmark speedcopy against shutil.copyfile on a mounted share path."""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import statistics
import threading
import time
import uuid
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from tqdm import tqdm

import speedcopy

MB_BYTES = 1024 * 1024
CHUNK_MB = 4
DEFAULT_SIZES_MB = (8, 64, 256)
DEFAULT_REPEATS = 3
DEFAULT_COPIES_PER_WORKER = 3


@dataclass
class CaseResult:
    """Store benchmark data for one file-size case."""

    size_mb: int
    baseline_seconds: float
    speedcopy_seconds: float
    baseline_mb_s: float
    speedcopy_mb_s: float
    speedup: float


@dataclass
class RunConfig:
    """Store run configuration reused by each benchmarked method."""

    repeats: int
    workers: int
    copies_per_worker: int
    show_copy_progress: bool = False


class CopyProgressTracker:
    """Track bytes copied across workers while copies are in flight."""

    def __init__(self) -> None:
        """Initialize an empty tracker with no in-flight copies."""
        self._lock = threading.Lock()
        self._completed = 0
        self._in_flight: Dict[int, Path] = {}

    def start(self, worker_id: int, dst: Path) -> None:
        """Record the destination a worker started writing to."""
        with self._lock:
            self._in_flight[worker_id] = dst

    def finish(self, worker_id: int, size_bytes: int) -> None:
        """Record that a worker finished copying `size_bytes`."""
        with self._lock:
            self._in_flight.pop(worker_id, None)
            self._completed += size_bytes

    def snapshot(self) -> int:
        """Return total bytes copied so far, including in-flight files.

        Returns:
            Completed bytes plus current size of files still being written.

        """
        with self._lock:
            total = self._completed
            in_flight = list(self._in_flight.values())
        for dst in in_flight:
            with contextlib.suppress(OSError):
                total += dst.stat().st_size
        return total


@dataclass
class CopyTask:
    """Bundle the parameters needed to run and time one benchmark pass."""

    copy_fn: Callable[[str, str], str]
    src: str
    run_dir: Path
    workers: int
    copies_per_worker: int
    size_bytes: int = 0
    show_progress: bool = False


@dataclass
class BenchContext:
    """Store per-case parameters shared by both benchmarked methods."""

    src: str
    bench_dir: Path
    config: RunConfig
    size_bytes: int


def parse_sizes(value: str) -> Tuple[int, ...]:
    """Parse comma-separated file sizes in MB into a validated tuple.

    Returns:
        Tuple of positive integer file sizes in MB.

    Raises:
        argparse.ArgumentTypeError: Sizes are missing or non-positive.

    """
    parsed: List[int] = []
    for raw in value.split(","):
        item = raw.strip()
        if not item:
            continue
        parsed.append(int(item))

    if not parsed:
        msg = "Provide at least one file size via --sizes-mb."
        raise argparse.ArgumentTypeError(msg)

    if any(size <= 0 for size in parsed):
        msg = "All file sizes must be positive integers."
        raise argparse.ArgumentTypeError(msg)

    return tuple(parsed)


def parse_args() -> argparse.Namespace:
    """Create CLI parser and return parsed arguments.

    Returns:
        Parsed benchmark CLI arguments.

    """
    parser = argparse.ArgumentParser(
        description=(
            "Compare shutil.copyfile and speedcopy.copyfile "
            "on a mounted share."
        ),
    )
    parser.add_argument(
        "share_path",
        help="Mounted share path used for source and destination files.",
    )
    parser.add_argument(
        "--sizes-mb",
        type=parse_sizes,
        default=DEFAULT_SIZES_MB,
        help=(
            "Comma-separated source file sizes in MB "
            f"(default: {','.join(str(size) for size in DEFAULT_SIZES_MB)})."
        ),
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=DEFAULT_REPEATS,
        help=(
            "How many timed runs to execute per method "
            f"(default: {DEFAULT_REPEATS})."
        ),
    )
    parser.add_argument(
        "--copies-per-worker",
        type=int,
        default=DEFAULT_COPIES_PER_WORKER,
        help=(
            "Copies each worker performs in one timed run "
            f"(default: {DEFAULT_COPIES_PER_WORKER})."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Set >1 to run copies concurrently in multiple threads.",
    )
    parser.add_argument(
        "--copy-progress",
        action="store_true",
        help=(
            "Show a bytes-copied progress bar per run (polls destination "
            "file sizes, adds minor overhead)."
        ),
    )
    args = parser.parse_args()

    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.copies_per_worker < 1:
        parser.error("--copies-per-worker must be at least 1")
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    return args


def generate_file(filepath: Path, size_mb: int) -> None:
    """Create a file with random contents and a target size in MB."""
    chunk_bytes = CHUNK_MB * MB_BYTES
    full_chunks, remainder = divmod(size_mb * MB_BYTES, chunk_bytes)
    with (
        filepath.open("wb") as stream,
        tqdm(
            total=size_mb * MB_BYTES,
            unit="B",
            unit_scale=True,
            desc="generating source",
            leave=False,
        ) as bar,
    ):
        for _ in range(full_chunks):
            stream.write(os.urandom(chunk_bytes))
            bar.update(chunk_bytes)
        if remainder:
            stream.write(os.urandom(remainder))
            bar.update(remainder)


def copy_worker(
    worker_id: int,
    task: CopyTask,
    tracker: Optional[CopyProgressTracker] = None,
) -> None:
    """Run copy operations for one worker and remove each destination file."""
    for index in range(task.copies_per_worker):
        dst = task.run_dir / f"w{worker_id:02d}_copy{index:03d}.bin"
        if tracker is not None:
            tracker.start(worker_id, dst)
        task.copy_fn(task.src, str(dst))
        if tracker is not None:
            tracker.finish(worker_id, task.size_bytes)
        dst.unlink()


def run_once(task: CopyTask) -> float:
    """Run one timed benchmark pass and return elapsed seconds.

    Returns:
        Elapsed wall-clock time in seconds.

    """
    if not task.show_progress:
        started = time.perf_counter()
        if task.workers == 1:
            copy_worker(0, task)
            return time.perf_counter() - started

        with ThreadPoolExecutor(max_workers=task.workers) as executor:
            futures = [
                executor.submit(copy_worker, worker, task)
                for worker in range(task.workers)
            ]
            for future in futures:
                future.result()
        return time.perf_counter() - started

    tracker = CopyProgressTracker()
    total_bytes = task.size_bytes * task.workers * task.copies_per_worker
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=task.workers) as executor:
        futures = [
            executor.submit(copy_worker, worker, task, tracker)
            for worker in range(task.workers)
        ]
        with tqdm(
            total=total_bytes,
            unit="B",
            unit_scale=True,
            desc="bytes",
            leave=False,
        ) as bar:
            pending = set(futures)
            while pending:
                _, pending = wait(
                    pending, timeout=0.05, return_when=FIRST_EXCEPTION
                )
                bar.n = min(tracker.snapshot(), total_bytes)
                bar.refresh()
            bar.n = total_bytes
            bar.refresh()
        for future in futures:
            future.result()

    return time.perf_counter() - started


def time_method(
    method_name: str,
    copy_fn: Callable[[str, str], str],
    context: BenchContext,
) -> float:
    """Time one copy method and return the median run time.

    Returns:
        Median elapsed wall-clock seconds for the method.

    """
    timings: List[float] = []
    progress = tqdm(
        range(context.config.repeats),
        desc=method_name,
        unit="run",
        leave=False,
    )
    for repeat_index in progress:
        run_dir = context.bench_dir / f"{method_name}_run{repeat_index:02d}"
        run_dir.mkdir()
        task = CopyTask(
            copy_fn=copy_fn,
            src=context.src,
            run_dir=run_dir,
            workers=context.config.workers,
            copies_per_worker=context.config.copies_per_worker,
            size_bytes=context.size_bytes,
            show_progress=context.config.show_copy_progress,
        )
        elapsed = run_once(task)
        timings.append(elapsed)
        run_dir.rmdir()
    return statistics.median(timings)


def benchmark_case(
    size_mb: int,
    bench_dir: Path,
    config: RunConfig,
) -> CaseResult:
    """Benchmark one source file size and return timing/speedup metrics.

    Returns:
        One completed case result with timings, throughput, and speedup.

    """
    src = bench_dir / f"src_{size_mb}mb.bin"
    generate_file(src, size_mb)

    context = BenchContext(
        src=str(src),
        bench_dir=bench_dir,
        config=config,
        size_bytes=size_mb * MB_BYTES,
    )
    baseline_seconds = time_method("shutil", shutil.copyfile, context)
    speedcopy_seconds = time_method(
        "speedcopy",
        speedcopy.copyfile,
        context,
    )

    src.unlink()

    total_mb = float(size_mb * config.workers * config.copies_per_worker)
    baseline_mb_s = total_mb / baseline_seconds
    speedcopy_mb_s = total_mb / speedcopy_seconds
    return CaseResult(
        size_mb=size_mb,
        baseline_seconds=baseline_seconds,
        speedcopy_seconds=speedcopy_seconds,
        baseline_mb_s=baseline_mb_s,
        speedcopy_mb_s=speedcopy_mb_s,
        speedup=baseline_seconds / speedcopy_seconds,
    )


def print_results(results: Sequence[CaseResult], workers: int) -> None:
    """Print concise benchmark output and an aggregate summary."""
    mode = "multithreaded" if workers > 1 else "single-threaded"
    print(f"mode={mode}, workers={workers}")
    print(
        "size(MB) | shutil(s) speedcopy(s) | shutil(MB/s) speedcopy(MB/s) "
        "| gain"
    )

    total_shutil = 0.0
    total_speedcopy = 0.0
    for result in results:
        total_shutil += result.baseline_seconds
        total_speedcopy += result.speedcopy_seconds
        print(
            f"{result.size_mb:>8} | "
            f"{result.baseline_seconds:>8.3f} "
            f"{result.speedcopy_seconds:>11.3f} | "
            f"{result.baseline_mb_s:>11.1f} {result.speedcopy_mb_s:>14.1f} | "
            f"{result.speedup:>5.2f}x"
        )

    overall_gain = total_shutil / total_speedcopy
    print("-" * 76)
    print(
        f"overall: shutil={total_shutil:.3f}s "
        f"speedcopy={total_speedcopy:.3f}s "
        f"gain={overall_gain:.2f}x"
    )


def main() -> None:
    """Run benchmark suite for requested sizes and execution mode.

    Raises:
        NotADirectoryError: `share_path` is missing or not a directory.

    """
    args = parse_args()
    print("-=> Speedcopy benchmark script <=-")
    if args.workers > 1:
        print(f"Running in multithreaded mode with {args.workers} workers.")
    else:
        print("Running in single-threaded mode.")

    print(f"Running with file sizes {args.sizes_mb} MB.")
    print(f"Using path: {args.share_path}")
    share_path = Path(args.share_path).expanduser().resolve()
    if not share_path.exists() or not share_path.is_dir():
        msg = f"Path is not an existing directory: {share_path}"
        raise NotADirectoryError(msg)

    copies_per_size = args.repeats * args.workers * args.copies_per_worker * 2
    total_mb = sum(args.sizes_mb) * copies_per_size
    print(
        f"Each size is copied {copies_per_size}x (repeats x workers x "
        "copies-per-worker x 2 methods); total data to move across all "
        f"sizes: {total_mb} MB. Large sizes with default repeats/copies "
        "can take a while - lower --repeats/--copies-per-worker to "
        "speed this up."
    )

    config = RunConfig(
        repeats=args.repeats,
        workers=args.workers,
        copies_per_worker=args.copies_per_worker,
        show_copy_progress=args.copy_progress,
    )

    sizes = args.sizes_mb
    # Not tempfile.TemporaryDirectory: on Windows, mkdtemp treats
    # PermissionError as a name collision and retries with new names, which
    # on a share without create rights looks like a hang instead of failing.
    bench_dir = share_path / f"speedcopy_bench_{uuid.uuid4().hex[:12]}"
    print(f"Creating benchmark directory: {bench_dir}")
    bench_dir.mkdir()
    try:
        results = [
            benchmark_case(
                size_mb=size_mb,
                bench_dir=bench_dir,
                config=config,
            )
            for size_mb in tqdm(sizes, desc="sizes", unit="size")
        ]
    finally:
        print(f"Removing benchmark directory: {bench_dir}")
        shutil.rmtree(bench_dir, ignore_errors=True)
    print_results(results, args.workers)


if __name__ == "__main__":
    main()
