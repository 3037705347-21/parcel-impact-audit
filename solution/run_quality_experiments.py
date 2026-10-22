#!/usr/bin/env python3
"""Run baseline, reference, partial-fix, and bypass experiments."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "C1": (0.14, "test_c1_"),
    "C2": (0.18, "test_c2_"),
    "C3": (0.10, "test_c3_"),
    "C4": (0.10, "test_c4_"),
    "C5": (0.30, "test_c5_"),
    "E2E": (0.18, "test_e2e_"),
}


def _score_xml(path: Path) -> tuple[float, dict[str, bool]]:
    """Compute grouped score from a JUnit report."""
    tree = ET.parse(path)
    statuses: dict[str, bool] = {}
    for case in tree.findall(".//testcase"):
        name = case.attrib.get("name", "")
        failed = case.find("failure") is not None or case.find("error") is not None
        statuses[name] = not failed
    score = 0.0
    for weight, prefix in GROUPS.values():
        relevant = [
            passed
            for name, passed in statuses.items()
            if name.startswith(prefix)
        ]
        if relevant and all(relevant):
            score += weight
    return round(score, 6), statuses


def _run_case(name: str, setup: callable) -> tuple[float, Path]:
    """Run one workspace variation and preserve its test output."""
    evidence_dir = ROOT / "solution" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = evidence_dir / f"{name}.log"
    with tempfile.TemporaryDirectory(prefix=f"impact-{name}-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(ROOT / "environment" / "workspace", workspace)
        setup(workspace)
        junit = Path(temporary) / "junit.xml"
        environment = os.environ.copy()
        environment["IMPACT_WORKSPACE"] = str(workspace)
        command = [
            sys.executable,
            "-m",
            "pytest",
            str(ROOT / "tests" / "test_outputs.py"),
            "-q",
            f"--junitxml={junit}",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        score, statuses = _score_xml(junit)
        lines = [
            f"case: {name}",
            f"workspace: {workspace}",
            "command: " + " ".join(command),
            f"process_returncode: {completed.returncode}",
            "test_status:",
        ]
        lines.extend(
            f"  {test_name}: {'PASS' if passed else 'FAIL'}"
            for test_name, passed in sorted(statuses.items())
        )
        lines.extend(
            [
                "pytest_output:",
                completed.stdout.rstrip(),
                completed.stderr.rstrip(),
                f"weighted_reward: {score:.6f}",
                "",
            ]
        )
        evidence.write_text("\n".join(lines), encoding="utf-8")
        print(f"{name}: {score:.6f}")
        return score, evidence


def _install_module_files(workspace: Path, files: list[str]) -> None:
    """Install selected experiment files into the package."""
    for filename in files:
        name = Path(filename).name
        destination = name
        if name.endswith("_model.py") or name == "model.py":
            destination = "model.py"
        elif name.endswith("_cli.py") or name == "cli.py":
            destination = "cli.py"
        shutil.copyfile(
            ROOT / "solution" / filename,
            workspace / "impact_audit" / destination,
        )


def main() -> None:
    """Run the complete experiment matrix and write its structured record."""
    baseline_score, baseline_evidence = _run_case("baseline", lambda workspace: None)
    oracle_score, oracle_evidence = _run_case(
        "oracle",
        lambda workspace: _install_module_files(
            workspace,
            [
                "oracle/model.py",
                "oracle/linalg.py",
                "oracle/pair.py",
                "oracle/cli.py",
                "oracle/__init__.py",
                "oracle/__main__.py",
            ],
        ),
    )

    partial_scores: dict[str, tuple[float, Path]] = {}
    partial_scores["C1"] = _run_case(
        "partial-c1",
        lambda workspace: _install_module_files(
            workspace, ["oracle/linalg.py", "partial_c1_model.py"]
        ),
    )
    partial_scores["C2"] = _run_case(
        "partial-c2",
        lambda workspace: _install_module_files(
            workspace, ["oracle/linalg.py", "oracle/model.py"]
        ),
    )
    partial_scores["C3"] = _run_case(
        "partial-c3",
        lambda workspace: _setup_partial_c3(workspace),
    )
    partial_scores["C4"] = _run_case(
        "partial-c4",
        lambda workspace: _install_module_files(
            workspace, ["oracle/linalg.py", "partial_c4_model.py", "oracle/cli.py"]
        ),
    )
    partial_scores["C5"] = _run_case(
        "partial-c5",
        lambda workspace: _install_module_files(
            workspace,
            [
                "oracle/linalg.py",
                "oracle/pair.py",
                "partial_c4_model.py",
                "oracle/cli.py",
            ],
        ),
    )

    bypass_empty = _run_case(
        "bypass-empty",
        lambda workspace: _install_module_files(workspace, ["bypass_empty_cli.py"]),
    )

    def hardcoded(workspace: Path) -> None:
        _install_module_files(workspace, ["bypass_hardcoded_cli.py"])
        shutil.copyfile(
            ROOT / "solution" / "reference-answer.json",
            workspace / "reference-answer.json",
        )

    bypass_hardcoded = _run_case("bypass-hardcoded", hardcoded)
    bypass_truncated = _run_case(
        "bypass-truncated",
        lambda workspace: _install_module_files(workspace, ["bypass_truncated_cli.py"]),
    )

    results = {
        "baseline": {
            "reward": baseline_score,
            "evidence": str(baseline_evidence.relative_to(ROOT)),
        },
        "oracle": {
            "reward": oracle_score,
            "evidence": str(oracle_evidence.relative_to(ROOT)),
        },
        "partials": [
            {
                "challenge_id": challenge,
                "reward": score,
                "evidence": str(evidence.relative_to(ROOT)),
            }
            for challenge, (score, evidence) in partial_scores.items()
        ],
        "bypasses": [
            {
                "id": "B1",
                "description": "空对象输出，不读取批次也不执行碰撞计算",
                "reward": bypass_empty[0],
                "evidence": str(bypass_empty[1].relative_to(ROOT)),
            },
            {
                "id": "B2",
                "description": "忽略输入并回放随包批次生成的固定报告",
                "reward": bypass_hardcoded[0],
                "evidence": str(bypass_hardcoded[1].relative_to(ROOT)),
            },
            {
                "id": "B3",
                "description": "正常退出但只写出截断的JSON",
                "reward": bypass_truncated[0],
                "evidence": str(bypass_truncated[1].relative_to(ROOT)),
            },
        ],
    }
    output = ROOT / "solution" / "quality-gate-results.json"
    output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _setup_partial_c3(workspace: Path) -> None:
    """Install complete physics while omitting the validation challenge."""
    _install_module_files(workspace, ["oracle/linalg.py"])
    shutil.copyfile(
        ROOT / "solution" / "oracle" / "model.py",
        workspace / "impact_audit" / "physics_model.py",
    )
    _install_module_files(workspace, ["partial_c3_model.py", "partial_c3_cli.py"])


if __name__ == "__main__":
    main()
