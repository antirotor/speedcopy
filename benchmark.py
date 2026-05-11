"""Benchmark speedcopy against shutil.copyfile on a mounted share path."""

from __future__ import annotations

import argparse
import os
import shutil
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Sequence, Tuple

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
    with filepath.open("wb") as stream:
        for _ in range(full_chunks):
            stream.write(os.urandom(chunk_bytes))
        if remainder:
            stream.write(os.urandom(remainder))


def copy_worker(
    copy_fn: Callable[[str, str], str],
    src: str,
    run_dir: Path,
    worker_id: int,
    copies_per_worker: int,
) -> None:
    """Run copy operations for one worker and remove each destination file."""
    for index in range(copies_per_worker):
        dst = run_dir / f"w{worker_id:02d}_copy{index:03d}.bin"
        copy_fn(src, str(dst))
        dst.unlink()


def run_once(
    copy_fn: Callable[[str, str], str],
    src: str,
    run_dir: Path,
    workers: int,
    copies_per_worker: int,
) -> float:
    """Run one timed benchmark pass and return elapsed seconds.

    Returns:
        Elapsed wall-clock time in seconds.

    """
    started = time.perf_counter()
    if workers == 1:
        copy_worker(copy_fn, src, run_dir, 0, copies_per_worker)
        return time.perf_counter() - started

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                copy_worker,
                copy_fn,
                src,
                run_dir,
                worker,
                copies_per_worker,
            )
            for worker in range(workers)
        ]
        for future in futures:
            future.result()

    return time.perf_counter() - started


def time_method(
    method_name: str,
    copy_fn: Callable[[str, str], str],
    src: str,
    bench_dir: Path,
    config: RunConfig,
) -> float:
    """Time one copy method and return the median run time.

    Returns:
        Median elapsed wall-clock seconds for the method.

    """
    timings: List[float] = []
    for repeat_index in range(config.repeats):
        run_dir = bench_dir / f"{method_name}_run{repeat_index:02d}"
        run_dir.mkdir()
        elapsed = run_once(
            copy_fn,
            src,
            run_dir,
            config.workers,
            config.copies_per_worker,
        )
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

    source = str(src)
    baseline_seconds = time_method(
        "shutil",
        shutil.copyfile,
        source,
        bench_dir,
        config,
    )
    speedcopy_seconds = time_method(
        "speedcopy",
        speedcopy.copyfile,
        source,
        bench_dir,
        config,
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

    config = RunConfig(
        repeats=args.repeats,
        workers=args.workers,
        copies_per_worker=args.copies_per_worker,
    )

    sizes = args.sizes_mb
    with tempfile.TemporaryDirectory(dir=str(share_path)) as temp_dir:
        bench_dir = Path(temp_dir)
        results = [
            benchmark_case(
                size_mb=size_mb,
                bench_dir=bench_dir,
                config=config,
            )
            for size_mb in sizes
        ]
    print_results(results, args.workers)


if __name__ == "__main__":
    main()
