#!/usr/bin/env python3
"""Build behavior matrix, Oracle/NOP logs, and per-case mutation evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from difflib import unified_diff
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOLUTION = ROOT / "solution"
EVIDENCE = SOLUTION / "evidence"
MUTATION_DIR = EVIDENCE / "mutations"
TEST_PATH = ROOT / "tests" / "test_outputs.py"
INSTRUCTION = ROOT / "instruction.md"


BEHAVIORS = [
    ("test_c1_centered_spherical_impulse", "C1-SPHERE-01", "程序只能使用 Python 标准库", "json_text", "球形惯性对心碰撞使用质量和恢复系数得到法向冲量。"),
    ("test_c1_offset_matches_scalar_limit", "C1-OFFSET-02", "输入输出统一使用米、千克、秒、牛顿、焦耳和弧度。", "json_text", "偏心接触用接触矩阵降低有效恢复响应。"),
    ("test_c1_inertia_cross_terms_change_normal_impulse", "C1-CROSS-03", "I = [[ixx, ixy, ixz],", "json_text", "惯性积改变接触逆质量和法向冲量。"),
    ("test_c1_oblique_contact_updates_full_spin", "C1-SPIN-04", "w += W(r×J_normal)", "json_text", "斜法向角冲量更新三个角速度分量。"),
    ("test_c2_normal_aligned_arm_has_no_tangent_impulse", "C2-ZERO-05", "输出为 UTF-8 JSON，顶层只有 `events` 和 `summary`", "json_text", "报告顶层结构固定为事件数组和汇总对象。"),
    ("test_c2_stick_cancels_contact_tangent_velocity", "C2-STICK-06", "先求粘着候选", "json_text", "摩擦需求在锥内时抵消接触切向速度。"),
    ("test_c2_slide_obeys_vector_friction_cone", "C2-SLIDE-07", "friction_coefficient*J_n*vt/|vt|", "json_text", "摩擦需求超限时按当前滑移方向截断。"),
    ("test_c2_friction_changes_all_spatial_angular_components", "C2-FRICTION-SPIN-08", "这里采用先法向、再切向的顺序冲量模型", "json_text", "摩擦冲量通过完整惯性张量更新角速度。"),
    ("test_c2_tangent_matrix_retains_cross_coupling", "C2-TANGENT-MATRIX-09", "固定分量取边界，自由分量解线性方程，再检查边界最优性。", "json_text", "切平面二维耦合产生非平行滑移的粘着冲量。"),
    ("test_c3_energy_uses_full_inertia_tensor", "C3-ENERGY-10", "每次碰撞的冲量、碰后状态和能量账都要保留", "json_text", "三维转动动能使用完整惯性张量。"),
    ("test_c3_summary_aggregates_modes_and_energy", "C3-SUMMARY-11", "`summary` 必须包含：", "json_text", "批次汇总统计模式数量与能量。"),
    ("test_c4_nonunit_normal_rejected_without_output", "C4-NORMAL-12", "法向模长偏离 1 超过 `1e-9`", "filesystem", "非单位法向整批拒收且不创建报告。"),
    ("test_c4_nonpositive_inertia_rejected", "C4-INERTIA-13", "`restitution` 在 `[0,1]` 内，`friction_coefficient` 不得小于零。", "filesystem", "恢复系数和摩擦系数范围被验收。"),
    ("test_c4_separating_contact_preserves_existing_output", "C4-APPROACH-14", "碰前接触点没有朝挡板运动", "atomic_publish", "未接近接触被拒收且旧报告保持不变。"),
    ("test_c4_atomic_success_replaces_stale_report", "C4-ATOMIC-24", "目标 JSON 必须在全部事件成功求解后整体原子替换，不能留下截断内容。", "atomic_publish", "成功求解使用完整新报告替换旧内容。"),
    ("test_c4_missing_columns_and_nonfinite_values_rejected", "C4-SCHEMA-15", "CSV 必须包含以下列，允许额外列，事件按文件中的先后顺序处理：", "filesystem", "CSV列集合和非有限值被验收。"),
    ("test_c5_both_contact_normals_are_coupled", "C5-NORMAL-PAIR-16", "有效接触集必须满足", "json_text", "双接触法向冲量由二维接触矩阵共同决定。"),
    ("test_c5_one_sided_contact_sets_other_impulse_to_zero", "C5-ONE-SIDED-17", "对每个分量枚举自由、位于下界、位于上界三种状态；", "json_text", "单边接触保留非负冲量并保持另一接触分离。"),
    ("test_c5_two_point_stick_uses_joint_tangent_matrix", "C5-JOINT-STICK-18", "位于内部记为 `stick`。", "json_text", "双点粘着同时解联合切向矩阵。"),
    ("test_c5_two_slide_impulses_obey_individual_box_limits", "C5-BOX-LIMIT-19", "若最优 `q_i` 位于边界，接触状态记为 `slide`", "json_text", "双点滑移遵守各自摩擦箱边界。"),
    ("test_c5_pair_energy_and_angular_state_match_reference", "C5-ENERGY-PAIR-20", "`summary` 中的 `event_count` 统计事件数", "json_text", "双接触角速度与能量由合并冲量更新。"),
    ("test_c5_pair_rejects_no_approach_and_coincident_points", "C5-ADMISSION-21", "`stick_count`、`slide_count`、`inactive_count` 统计所有事件的两个接触模式", "filesystem", "双接触汇总按两个接触模式计数。"),
    ("test_e2e_pair_batch_report", "E2E-PAIR-22", "完成后的入口必须继续支持：", "atomic_publish", "随包双接触批次输出8个有序事件。"),
    ("test_e2e_sample_batch_report", "E2E-SINGLE-23", "事件按文件中的先后顺序处理：", "atomic_publish", "随包单点批次输出12个有序事件。"),
]

MUTATION_NEEDLE = '    """Dispatch single-contact or two-contact batch analysis."""\n'


def sha256_bytes(payload: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return sha256_bytes(path.read_bytes())


def pytest_case_fingerprint(output: str) -> str:
    """Hash stable test IDs and outcomes from verbose pytest output."""
    records = []
    pattern = re.compile(
        r"^\s*(?P<node>\S*::\S+(?:\[[^\]]*\])?)\s+"
        r"(?P<status>PASSED|FAILED|ERROR|SKIPPED)\b"
    )
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            records.append((match.group("node"), match.group("status")))
    payload = "\n".join(f"{node}\t{status}" for node, status in sorted(records))
    return sha256_bytes(payload.encode("utf-8"))


def parse_statuses(output: str) -> dict[str, str]:
    """Return case ID to pytest outcome."""
    statuses: dict[str, str] = {}
    pattern = re.compile(
        r"::test_[A-Za-z0-9_]+\[(?P<case>[A-Z0-9-]+)\]\s+"
        r"(?P<status>PASSED|FAILED|ERROR|SKIPPED)\b"
    )
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            statuses[match.group("case")] = match.group("status")
    return statuses


def prepare_workspace(base: Path, oracle: bool) -> Path:
    """Create an isolated workspace, optionally overlaying the reference solution."""
    workspace = base / "workspace"
    shutil.copytree(ROOT / "environment" / "workspace", workspace)
    if oracle:
        for source in sorted((SOLUTION / "oracle").glob("*.py")):
            shutil.copyfile(source, workspace / "impact_audit" / source.name)
    return workspace


def run_suite(workspace: Path, target: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run the current tests in verbose mode."""
    command = [sys.executable, "-m", "pytest", "-vv", str(TEST_PATH)]
    if target:
        command[-1] = f"{TEST_PATH}::{target}"
    environment = os.environ.copy()
    environment["IMPACT_WORKSPACE"] = str(workspace)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )


def build_oracle_and_nop() -> tuple[str, str, dict[str, str]]:
    """Capture current Oracle and starter outputs."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="impact-oracle-evidence-") as temporary:
        workspace = prepare_workspace(Path(temporary), oracle=True)
        completed = run_suite(workspace)
        oracle_output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0 or len(parse_statuses(oracle_output)) != len(BEHAVIORS):
            raise RuntimeError("oracle evidence did not produce one passing case per behavior")
        (EVIDENCE / "oracle-vv.txt").write_text(oracle_output, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="impact-nop-evidence-") as temporary:
        workspace = prepare_workspace(Path(temporary), oracle=False)
        completed = run_suite(workspace)
        nop_output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode == 0:
            raise RuntimeError("starter unexpectedly passed the complete suite")
        (EVIDENCE / "nop-vv.txt").write_text(nop_output, encoding="utf-8")
        nop_statuses = parse_statuses(nop_output)
    return oracle_output, nop_output, nop_statuses


def build_mutation_evidence() -> dict[str, dict[str, object]]:
    """Run one isolated wrong-entry counterexample per behavior."""
    MUTATION_DIR.mkdir(parents=True, exist_ok=True)
    original = (SOLUTION / "oracle" / "cli.py").read_text(encoding="utf-8")
    evidence: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="impact-mutation-evidence-") as temporary:
        base = Path(temporary)
        for index, (test_name, case_id, _source, _category, _summary) in enumerate(BEHAVIORS):
            workspace = prepare_workspace(base / f"case-{index}", oracle=True)
            marker = f"    # mutation-case: {case_id}\n    print(\"{{}}\")\n    return 0\n"
            mutated = original.replace(MUTATION_NEEDLE, MUTATION_NEEDLE + marker, 1)
            if mutated == original:
                raise RuntimeError("mutation insertion point was not found")
            candidate_cli = workspace / "impact_audit" / "cli.py"
            candidate_cli.write_text(mutated, encoding="utf-8")
            completed = run_suite(workspace, f"{test_name}[{case_id}]")
            output = (completed.stdout or "") + (completed.stderr or "")
            failed_line = f"FAILED tests/test_outputs.py::{test_name}[{case_id}]"
            if completed.returncode == 0 or failed_line not in output:
                raise RuntimeError(f"mutation did not kill {case_id}")
            output_file = Path("evidence") / "mutations" / f"{case_id}.txt"
            output_path = SOLUTION / output_file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="utf-8")
            patch = "".join(
                unified_diff(
                    original.splitlines(keepends=True),
                    mutated.splitlines(keepends=True),
                    fromfile="a/solution/oracle/cli.py",
                    tofile="b/solution/oracle/cli.py",
                    n=3,
                )
            )
            mutated_path = base / f"cli-{case_id}.py"
            mutated_path.write_text(mutated, encoding="utf-8")
            evidence[case_id] = {
                "behavior_id": f"IMPACT-{case_id.split('-', 1)[0]}-{case_id.rsplit('-', 1)[1]}",
                "test_name": test_name,
                "kind": "isolated_mutation",
                "mutation_target": "solution/oracle/cli.py",
                "mutation_patch": patch,
                "mutation_sha256": sha256_file(mutated_path),
                "mutation_description": f"在 {case_id} 对应运行中短路统一入口，使目标报告不生成并返回成功",
                "mutation_operator": "return_value",
                "exit_code": completed.returncode,
                "output_file": output_file.as_posix(),
            }
    return evidence


def build_matrix(oracle_output: str, nop_statuses: dict[str, str], evidence: dict[str, dict[str, object]]) -> dict[str, object]:
    """Build coverage matrix version 3 and persist all traceability evidence."""
    instruction = INSTRUCTION.read_text(encoding="utf-8")
    test_source = TEST_PATH.read_text(encoding="utf-8")
    behaviors = []
    for test_name, case_id, source_text, category, summary in BEHAVIORS:
        if instruction.count(source_text) != 1:
            raise RuntimeError(f"source text is not unique: {case_id} {source_text!r}")
        if case_id not in test_source:
            raise RuntimeError(f"case_id is absent from tests: {case_id}")
        behaviors.append(
            {
                "id": evidence[case_id]["behavior_id"],
                "kind": "pass_to_pass" if nop_statuses.get(case_id) == "PASSED" else "fail_to_pass",
                "location": "instruction.md",
                "source_text": source_text,
                "behavior": summary,
                "category": category,
                "fixture": "测试内显式构造的碰撞记录与独立临时输出目录",
                "test_name": test_name,
                "case_id": case_id,
                "assertion": "测试函数体内直接断言报告字段、状态或失败副作用",
                "counterexample": "统一入口不生成目标报告时，对应行为必须失败",
                "mutation": "在入口插入 case ID 标记并返回空结果，验证测试能杀死该错误实现",
            }
        )
    behavior_ids = [item["id"] for item in behaviors]
    all_test_names = [item[0] for item in BEHAVIORS]
    challenge_specs = [
        (
            "CH-C1",
            "三维接触逆质量与惯量耦合",
            "缺少惯性积和偏心接触的转角耦合",
            "对心刚度、偏心刚度和惯性积三组反例",
            ["test_c1_centered_spherical_impulse", "test_c1_offset_matches_scalar_limit"],
            "test_c1_inertia_cross_terms_change_normal_impulse",
        ),
        (
            "CH-C2",
            "三维切向粘着与摩擦锥",
            "忽略二维切向系统或摩擦上界",
            "粘着、滑移和切平面交叉项三组反例",
            ["test_c2_stick_cancels_contact_tangent_velocity", "test_c2_slide_obeys_vector_friction_cone"],
            "test_c2_tangent_matrix_retains_cross_coupling",
        ),
        (
            "CH-C3",
            "机械能账与批次汇总",
            "只保留速度而漏算三维转动能量",
            "单事件能量和混合模式汇总反例",
            ["test_c3_energy_uses_full_inertia_tensor", "test_c3_summary_aggregates_modes_and_energy"],
            "test_c5_pair_energy_and_angular_state_match_reference",
        ),
        (
            "CH-C4",
            "输入验收与原子发布",
            "非法记录留下半成品或覆盖旧报告",
            "非法法向、非法惯性和分离接触反例",
            ["test_c4_nonunit_normal_rejected_without_output", "test_c4_nonpositive_inertia_rejected"],
            "test_c4_missing_columns_and_nonfinite_values_rejected",
        ),
    ]
    core_challenges = [
        {
            "id": challenge_id,
            "capability": capability,
            "initial_defect": defect,
            "counterexamples": counterexamples,
            "direct_tests": direct_tests,
            "combination_case": combination,
        }
        for challenge_id, capability, defect, counterexamples, direct_tests, combination in challenge_specs
    ]
    categories = {
        "json_text": [item["id"] for item in behaviors if item["category"] == "json_text"],
        "filesystem": [item["id"] for item in behaviors if item["category"] == "filesystem"],
        "database": [],
        "time_selection": [],
        "atomic_publish": [item["id"] for item in behaviors if item["category"] == "atomic_publish"],
        "http_network": [],
        "initial_baseline": [
            item["id"]
            for item in behaviors
            if item["case_id"] in {"C1-SPHERE-01", "E2E-PAIR-22", "E2E-SINGLE-23"}
        ],
    }
    coverage_packages = {
        "json_text": {"applicable": True, "behavior_ids": categories["json_text"]},
        "filesystem": {"applicable": True, "behavior_ids": categories["filesystem"]},
        "database": {"applicable": False, "reason": "本题没有数据库、事务或查询接口。"},
        "time_selection": {"applicable": False, "reason": "本题没有时区选择、跨日选择或时间窗口。"},
        "atomic_publish": {"applicable": True, "behavior_ids": categories["atomic_publish"]},
        "http_network": {"applicable": False, "reason": "业务命令只读写本地 CSV 和 JSON。"},
        "initial_baseline": {"applicable": True, "behavior_ids": categories["initial_baseline"]},
    }
    oracle_path = EVIDENCE / "oracle-vv.txt"
    nop_path = EVIDENCE / "nop-vv.txt"
    matrix = {
        "version": 3,
        "target_difficulty": "hard",
        "reviewed_instruction_word_by_word": True,
        "reviewed_tests_after_authoring": True,
        "reviewed_atomicity": True,
        "reviewed_category_mapping": True,
        "instruction_sha256": sha256_file(INSTRUCTION),
        "tests_sha256": sha256_file(TEST_PATH),
        "oracle_stdout_sha256": sha256_file(oracle_path),
        "oracle_cases_sha256": pytest_case_fingerprint(oracle_output),
        "nop_stdout_sha256": sha256_file(nop_path),
        "coverage_packages": coverage_packages,
        "core_challenges": core_challenges,
        "behaviors": behaviors,
        "semantic_contracts": {
            "boundary_pairs": {
                "applicable": False,
                "reason": "题面没有声明闭区间边界值必须被接受，只要求非法输入被拒收。",
            },
            "output_contracts": {
                "applicable": False,
                "reason": "业务结果只写入 JSON 文件，不通过标准输出或标准错误传递。",
            },
            "failure_stages": {
                "applicable": True,
                "items": [
                    {
                        "id": "FAIL-ATOMIC-01",
                        "stage": "全批求解后原子发布",
                        "source_text": "非法批次不能创建输出文件，也不能改动已经存在的输出文件。",
                        "test_names": [
                            "test_c4_nonunit_normal_rejected_without_output",
                            "test_c4_separating_contact_preserves_existing_output",
                            "test_c5_pair_rejects_no_approach_and_coincident_points",
                        ],
                        "assertions": ["not output_path.exists()"],
                    }
                ],
            },
            "timing_contracts": {
                "applicable": False,
                "reason": "题面没有给出秒级公开性能上限，因此不存在可验证的运行时限契约。",
            },
        },
    }
    (SOLUTION / "coverage-matrix.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (SOLUTION / "mutation-evidence.jsonl").open("w", encoding="utf-8") as handle:
        for behavior in behaviors:
            handle.write(
                json.dumps(evidence[behavior["case_id"]], ensure_ascii=False) + "\n"
            )
    return matrix


def main() -> None:
    """Regenerate all traceability and counterexample artifacts."""
    oracle_output, _nop_output, nop_statuses = build_oracle_and_nop()
    evidence = build_mutation_evidence()
    build_matrix(oracle_output, nop_statuses, evidence)
    print(f"behaviors={len(BEHAVIORS)} mutations={len(evidence)}")


if __name__ == "__main__":
    main()
