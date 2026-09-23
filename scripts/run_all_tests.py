#!/usr/bin/env python3
"""Run the complete ground-station validation with one friendly command."""

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "test_reports"


def run_step(name, command, required=True, available=True):
    if not available:
        return name, "SKIP", "component is not installed"
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    status = "PASS" if result.returncode == 0 else "FAIL"
    if not required and result.returncode != 0:
        status = "WARN"
    return name, status, result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Run all automated AegisSat ground-station tests"
    )
    parser.add_argument(
        "--hardware",
        action="store_true",
        help="also check the RTL-SDR when rtl_test is installed",
    )
    parser.add_argument(
        "--skip-openmct",
        action="store_true",
        help="skip the Open MCT production build",
    )
    args = parser.parse_args()

    REPORTS.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS / f"validation_{timestamp}.log"

    steps = []
    steps.append(run_step(
        "Python tests",
        [sys.executable, "-m", "pytest", "-q"],
    ))
    steps.append(run_step(
        "Preflight configuration",
        [sys.executable, "scripts/preflight.py"],
        required=False,
    ))

    npm_available = shutil.which("npm") is not None
    node_modules = ROOT / "openmct" / "node_modules"
    openmct_available = npm_available and node_modules.exists()
    if not args.skip_openmct:
        steps.append(run_step(
            "Open MCT build",
            ["npm", "--prefix", "openmct", "run", "build"],
            available=openmct_available,
        ))

    if args.hardware:
        steps.append(run_step(
            "RTL-SDR hardware",
            ["rtl_test", "-t"],
            available=shutil.which("rtl_test") is not None,
        ))

    lines = [
        "=" * 58,
        " AEGISSAT GROUND STATION - AUTOMATIC VALIDATION",
        "=" * 58,
        "",
    ]
    for name, status, output in steps:
        lines.append(f"[{status}] {name}")
        if status in {"FAIL", "WARN"} and output:
            lines.append(output)

    counts = {
        status: sum(1 for _, item_status, _ in steps if item_status == status)
        for status in ("PASS", "FAIL", "WARN", "SKIP")
    }
    lines.extend([
        "",
        "Summary:",
        f"  Passed:  {counts['PASS']}",
        f"  Failed:  {counts['FAIL']}",
        f"  Warnings:{counts['WARN']}",
        f"  Skipped: {counts['SKIP']}",
        "",
        "Result: " + (
            "VALIDATION PASSED" if counts["FAIL"] == 0
            else "VALIDATION FAILED"
        ),
        f"Report: {report_path.relative_to(ROOT)}",
    ])
    report = "\n".join(lines) + "\n"
    report_path.write_text(report, encoding="utf-8")
    print(report, end="")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
