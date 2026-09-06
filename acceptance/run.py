from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SUITES = {
    "uat": [ROOT / "acceptance/features/uat.feature"],
    "demo-en": [ROOT / "acceptance/features/demo-en.feature"],
    "demo-yue": [ROOT / "acceptance/features/demo-yue.feature"],
}


def browser_tools() -> tuple[str | None, str | None]:
    snap_root = Path("/snap/chromium/current/usr/lib/chromium-browser")
    snap_browser = snap_root / "chrome"
    snap_driver = snap_root / "chromedriver"
    if snap_browser.is_file() and snap_driver.is_file():
        return str(snap_browser), str(snap_driver)
    browser = next(
        (
            shutil.which(name)
            for name in (
                "chromium",
                "chromium-browser",
                "google-chrome",
                "google-chrome-stable",
            )
            if shutil.which(name)
        ),
        None,
    )
    return browser, shutil.which("chromedriver")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Dataset Annotator's executable Gherkin suites"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--suite", choices=[*SUITES, "all"], default="uat")
    parser.add_argument(
        "--report-dir", type=Path, default=ROOT / "build/reports/uat"
    )
    args = parser.parse_args()

    selected = [path for paths in SUITES.values() for path in paths]
    if args.suite != "all":
        selected = SUITES[args.suite]

    environment = os.environ.copy()
    inherited_pythonpath = environment.get("PYTHONPATH", "")
    environment.update(
        {
            "DATA_VIEWER_UAT_REPORT_DIR": str(args.report_dir.resolve()),
            "DATA_VIEWER_UAT_PYTHON": sys.executable,
            "PYTHONPATH": os.pathsep.join(
                part for part in (str(ROOT), inherited_pythonpath) if part
            ),
        }
    )
    command = [
        sys.executable,
        "-m",
        "behave",
        *[str(path.relative_to(ROOT)) for path in selected],
        "--no-capture",
    ]
    if args.dry_run:
        return subprocess.run(
            [*command, "--dry-run"], cwd=ROOT, env=environment, check=False
        ).returncode

    browser, driver = browser_tools()
    if not browser or not driver:
        print(
            "Complete GUI UAT skipped: Chromium and chromedriver are both required.",
            file=sys.stderr,
        )
        return 3
    environment["DATA_VIEWER_UAT_BROWSER"] = browser
    environment["DATA_VIEWER_UAT_CHROMEDRIVER"] = driver

    args.report_dir.mkdir(parents=True, exist_ok=True)
    raw_report = args.report_dir / "behave.json"
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = subprocess.run(
        [*command, "--format", "json.pretty", "--outfile", str(raw_report)],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    report_result = subprocess.run(
        [
            sys.executable,
            "acceptance/report.py",
            str(raw_report),
            str(args.report_dir),
            "--started-at",
            started,
            "--suite",
            args.suite,
        ],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    return result.returncode or report_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
