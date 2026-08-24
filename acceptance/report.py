from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def feature_path(feature: dict) -> str:
    location = str(feature.get("location", "acceptance/features/uat.feature"))
    return location.rsplit(":", 1)[0]


def build_reports(raw_path: Path, output: Path, started_at: str, suite: str) -> bool:
    features = json.loads(raw_path.read_text(encoding="utf-8"))
    scenarios = []
    test_executions = ET.Element("testExecutions", {"version": "1"})
    report_files: dict[str, ET.Element] = {}

    for feature in features:
        path = feature_path(feature)
        report_file = report_files.setdefault(
            path, ET.SubElement(test_executions, "file", {"path": path})
        )
        for element in feature.get("elements", []):
            if element.get("type") not in {"scenario", "scenario_outline"}:
                continue
            steps = element.get("steps", [])
            results = [step.get("result") or {} for step in steps]
            passed = bool(results) and all(r.get("status") == "passed" for r in results)
            duration = sum(float(r.get("duration", 0) or 0) for r in results)
            diagnostics = [
                str(r["error_message"]) for r in results if r.get("error_message")
            ]
            name = str(element.get("name", "unnamed scenario"))
            scenarios.append(
                {
                    "feature": path,
                    "name": name,
                    "passed": passed,
                    "duration_ms": round(duration * 1000),
                    "diagnostics": diagnostics,
                    "steps": [
                        {
                            "name": str(step.get("name", "")),
                            "passed": (step.get("result") or {}).get("status") == "passed",
                        }
                        for step in steps
                    ],
                }
            )
            case = ET.SubElement(
                report_file,
                "testCase",
                {"name": name, "duration": str(round(duration * 1000))},
            )
            if not passed:
                failure = ET.SubElement(
                    case,
                    "failure",
                    {"message": diagnostics[0] if diagnostics else "scenario failed"},
                )
                failure.text = "\n".join(diagnostics)

    overall = bool(scenarios) and all(item["passed"] for item in scenarios)
    artifacts = sorted(
        str(path.relative_to(output))
        for path in output.rglob("*")
        if path.is_file() and path != raw_path
    )
    checklist = {
        "repository": "to-sora/data_viewer",
        "commit": git_commit(),
        "suite": suite,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "passed": overall,
        "artifacts": artifacts,
        "scenarios": scenarios,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "checklist.json").write_text(
        json.dumps(checklist, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    ET.indent(test_executions)
    ET.ElementTree(test_executions).write(
        output / "sonar-test-execution.xml", encoding="utf-8", xml_declaration=True
    )
    return overall


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--suite", required=True)
    args = parser.parse_args()
    return 0 if build_reports(args.raw, args.output, args.started_at, args.suite) else 1


if __name__ == "__main__":
    raise SystemExit(main())
