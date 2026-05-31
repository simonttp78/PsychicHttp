#!/usr/bin/env python3
"""
Run a full PlatformIO build matrix with a clean cache before each environment.

Why this exists:
- The VS Code PlatformIO extension may spawn helper processes (project init/metadata)
  that interfere with long matrix runs in integrated terminals.
- This runner isolates PlatformIO state, kills known helper processes before each step,
  and enforces a timeout per environment to avoid hangs.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Target:
    project_dir: Path
    env: str

    @property
    def label(self) -> str:
        return f"{self.project_dir}:{self.env}"


def build_matrix(root: Path, group: str) -> list[Target]:
    root_targets = [
        Target(root, "arduino2"),
        Target(root, "arduino2-ssl"),
        Target(root, "arduino2-regex"),
        Target(root, "arduino3"),
        Target(root, "arduino3-ssl"),
        Target(root, "arduino3-regex"),
        Target(root, "pioarduino-c6"),
        Target(root, "mathieu"),
        Target(root, "hoeken"),
        Target(root, "ci"),
    ]

    example_targets = [
        Target(root / "examples" / "pio-arduino", "arduino2"),
        Target(root / "examples" / "pio-arduino", "arduino2-ssl"),
        Target(root / "examples" / "pio-arduino", "arduino2-regex"),
        Target(root / "examples" / "pio-arduino", "arduino3"),
        Target(root / "examples" / "pio-arduino", "arduino3-ssl"),
        Target(root / "examples" / "pio-arduino", "arduino3-regex"),
        Target(root / "examples" / "pio-arduino", "waveshare-4-3-touchscreen"),
        Target(root / "examples" / "websockets", "default"),
        Target(root / "examples" / "esp-idf-pio", "s3"),
    ]

    benchmark_targets = [
        Target(root / "benchmark" / "arduinomongoose", "default"),
        Target(root / "benchmark" / "espasyncwebserver", "default"),
        Target(root / "benchmark" / "psychichttp", "default"),
        Target(root / "benchmark" / "psychichttp", "v2-dev"),
        Target(root / "benchmark" / "psychichttps", "default"),
    ]

    if group == "root":
        return root_targets
    if group == "examples":
        return example_targets
    if group == "benchmarks":
        return benchmark_targets
    return root_targets + example_targets + benchmark_targets


def kill_helper_processes() -> None:
    # Ignore errors: helper may not exist.
    patterns = [
        "python -m platformio -c vscode project init --ide vscode --environment hoeken",
        "platformio -c vscode project init --ide vscode --environment hoeken",
    ]
    for pattern in patterns:
        subprocess.run(["pkill", "-9", "-f", pattern], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sanitize(value: str) -> str:
    return value.replace("/", "_").replace(":", "_").replace(" ", "_")


def append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run_target(
    target: Target,
    pio_bin: Path,
    timeout_sec: int,
    core_dir: Path,
    logs_dir: Path,
    summary_file: Path,
    index: int,
    total: int,
) -> str:
    kill_helper_processes()

    pio_dir = target.project_dir / ".pio"
    shutil.rmtree(pio_dir, ignore_errors=True)

    start_line = f"START [{index}/{total}] {target.label}"
    print(start_line, flush=True)
    append_line(summary_file, start_line)

    log_file = logs_dir / f"{sanitize(str(target.project_dir))}_{sanitize(target.env)}.log"

    env = os.environ.copy()
    env["PLATFORMIO_CORE_DIR"] = str(core_dir)
    env["CI"] = "true"

    with log_file.open("w", encoding="utf-8") as log:
        try:
            completed = subprocess.run(
                [str(pio_bin), "run", "-e", target.env],
                cwd=str(target.project_dir),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_sec,
                check=False,
            )
            status = "PASS" if completed.returncode == 0 else "FAIL"
            line = f"{status} {target.label} rc={completed.returncode} log={log_file}"
            print(line, flush=True)
            append_line(summary_file, line)
            return status
        except subprocess.TimeoutExpired:
            # Best-effort cleanup if the command hung.
            subprocess.run(["pkill", "-9", "-f", f"platformio run -e {target.env}"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            line = f"TIMEOUT {target.label} after={timeout_sec}s log={log_file}"
            print(line, flush=True)
            append_line(summary_file, line)
            return "TIMEOUT"


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PsychicHttp PlatformIO build matrix with cache cleanup per env.")
    parser.add_argument("--group", choices=["all", "root", "examples", "benchmarks"], default="all")
    parser.add_argument("--filter", default="", help="Optional substring filter applied to '<project_dir>:<env>'.")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds per environment (default: 900).")
    parser.add_argument("--core-dir", default="/tmp/pio-core-matrix", help="Isolated PLATFORMIO_CORE_DIR.")
    parser.add_argument("--summary", default="", help="Optional summary file path. Default: /tmp/pio-matrix-summary-<timestamp>.txt")
    parser.add_argument("--repo-root", default="/Users/simon/Repositories/PsychicHttp")
    parser.add_argument("--pio-bin", default="/Users/simon/.platformio/penv/bin/platformio")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)

    root = Path(args.repo_root).resolve()
    pio_bin = Path(args.pio_bin).resolve()
    core_dir = Path(args.core_dir).resolve()

    if not root.exists():
        print(f"Repository root not found: {root}", file=sys.stderr)
        return 2
    if not pio_bin.exists():
        print(f"PlatformIO binary not found: {pio_bin}", file=sys.stderr)
        return 2

    targets = build_matrix(root, args.group)
    if args.filter:
        filt = args.filter.lower()
        targets = [t for t in targets if filt in t.label.lower()]

    if not targets:
        print("No targets selected.")
        return 0

    timestamp = int(time.time())
    summary_file = Path(args.summary).resolve() if args.summary else Path(f"/tmp/pio-matrix-summary-{timestamp}.txt")
    logs_dir = Path(f"/tmp/pio-matrix-logs-{timestamp}")

    ensure_dir(core_dir)
    ensure_dir(logs_dir)
    summary_file.write_text("", encoding="utf-8")

    print(f"Summary: {summary_file}")
    print(f"Logs:    {logs_dir}")
    print(f"Targets: {len(targets)}")

    results = {"PASS": 0, "FAIL": 0, "TIMEOUT": 0}

    for idx, target in enumerate(targets, start=1):
        status = run_target(
            target=target,
            pio_bin=pio_bin,
            timeout_sec=args.timeout,
            core_dir=core_dir,
            logs_dir=logs_dir,
            summary_file=summary_file,
            index=idx,
            total=len(targets),
        )
        results[status] += 1

    append_line(summary_file, "DONE")

    print("---")
    print(f"PASS={results['PASS']} FAIL={results['FAIL']} TIMEOUT={results['TIMEOUT']}")
    print(f"Summary: {summary_file}")

    return 0 if results["FAIL"] == 0 and results["TIMEOUT"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
