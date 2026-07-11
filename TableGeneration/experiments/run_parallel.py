"""
Run 5K generation in parallel (3 workers) for faster turnaround.
Each worker gets ~1667 samples, writes to its own output dir.
After all finish, merge into one dataset.

Usage:
  python run_parallel.py --templates templates.json --total 5000 --workers 3
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

PYTHON = sys.executable
BASE = Path(__file__).resolve().parent
RUNNER = BASE / "agents/run_agents.py"
TEMPLATES = BASE / "templates.json"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--templates", type=Path, default=TEMPLATES)
    parser.add_argument("--total", type=int, default=5000)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    total = args.total
    n = args.workers
    chunk = (total + n - 1) // n  # ceil division

    # Base output dir
    base_output = Path("/mnt/workspace/tablenet/data/tablenet_dsw_5k_template")
    base_output.mkdir(parents=True, exist_ok=True)

    processes = []
    logs = []

    for i in range(n):
        start = i * chunk
        count = min(chunk, total - start)
        if count <= 0:
            break

        out_dir = str(base_output / f"part_{i}")
        log_file = f"/tmp/gen_5k_part_{i}.log"

        cmd = [
            PYTHON, str(RUNNER),
            "--target_num", str(count),
            "--balanced_configs", "--balanced_structures",
            "--retry_failed",
            "--max_attempts", str(count * 3),
            "--semantic_mode", "rule",
            "--templates", str(args.templates),
            "--report",
            "--output", out_dir,
            "--chrome_driver_path", "/usr/local/bin/chromedriver",
        ]

        log_fp = open(log_file, "w")
        p = subprocess.Popen(cmd, stdout=log_fp, stderr=subprocess.STDOUT, text=True)
        processes.append(p)
        logs.append((log_fp, log_file))

        print(f"[Worker {i}] PID={p.pid}  generating {count} samples → {out_dir}")
        # Stagger start by 5s to avoid ChromeDriver port conflicts
        time.sleep(5)

    print(f"\nAll {n} workers started. Monitoring...")
    print("Ctrl+C to stop (running processes will continue in background)\n")

    # Monitor progress
    try:
        while any(p.poll() is None for p in processes):
            time.sleep(30)
            for i, (log_fp, log_file) in enumerate(logs):
                if processes[i].poll() is None:
                    # check image count
                    img_dir = base_output / f"part_{i}" / "img"
                    count = len(list(img_dir.glob("*.jpg"))) if img_dir.exists() else 0
                    print(f"  Worker {i}: {count} images")
    except KeyboardInterrupt:
        print("\nMonitoring stopped. Workers continue in background.")

    # Close log files
    for log_fp, _ in logs:
        try:
            log_fp.close()
        except:
            pass

    print("\nDone. Check workers with: ps aux | grep run_agents")
    print(f"Output dirs: {base_output}/part_*")
    print(f"After all finish, merge: cp part_0/img/*.jpg ../img/ && ...")


if __name__ == "__main__":
    main()
