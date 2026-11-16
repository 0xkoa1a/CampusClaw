"""Run the repository's established high-confidence source secret scanner."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    baseline = Path(__file__).with_name("security_baseline.py")
    result = subprocess.run(
        [sys.executable, str(baseline), "--root", str(args.root.resolve())],
        check=False,
    )
    if result.returncode == 0:
        print("Secret baseline scan passed.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
