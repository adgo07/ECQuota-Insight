"""水泥正式保存策略；与界面及存储实现无关。"""
from __future__ import annotations
import hashlib
import json

from uebench.domain.gb16780 import (
    ACTUALS, CALCULATOR_VERSION, NUMERIC_BEHAVIOR_VERSION, PRODUCT_ID, adopted,
)
from uebench.domain.models import Grade, InputMode
from .gb29446 import GB29446_PERIOD_OPTIONS, decode_period_notes

MODE_LABELS = {
    "integrated": "自产熟料并生产水泥", "partial_purchase": "部分外购熟料生产水泥",
    "clinker_only": "仅生产熟料", "purchased_clinker_grinding": "全部外购熟料粉磨站",
}
APPLICABLE = {
    "integrated": frozenset(ACTUALS), "partial_purchase": frozenset(ACTUALS),
    "clinker_only": frozenset({"clinker.comprehensive", "clinker.electricity", "clinker.coal"}),
    "purchased_clinker_grinding": frozenset({"cement-preparation.electricity"}),
}
COMPLETE_GRADES = {Grade.LEVEL_1, Grade.LEVEL_2, Grade.LEVEL_3, Grade.NOT_QUALIFIED}


def require_formal_request(request, snapshot):
    if request.input_mode is not InputMode.DETAIL:
        raise ValueError("水泥正式评价仅支持原始明细计算，不接受直接输入最终单位值。")
    if not adopted(snapshot) or request.product_id != PRODUCT_ID:
        raise ValueError("配套水泥规则尚未采用V1.2及对应评价产品，不能形成正式记录。")


class IncompleteCementEvaluationError(ValueError):
    """正式评价未保存；携带同一次执行的部分预览，不能误报成功。"""

    def __init__(self, preview_result, problems):
        self.preview_result = preview_result
        self.problems = tuple(problems)
        super().__init__("部分预览，尚未生成记录：" + "；".join(self.problems))


def completeness_problems(request, result, snapshot, *, require_period=True):
    problems = []
    if (not adopted(snapshot) or request.input_mode is not InputMode.DETAIL
            or request.product_id != PRODUCT_ID or result.product_id != PRODUCT_ID
            or result.standard_id != request.standard_id or result.rule_revision != snapshot.rule_revision
            or result.standard_version != snapshot.version or request.standard_id != snapshot.id
            or result.numeric_contract_version != "v1"
            or result.calculator_version != CALCULATOR_VERSION
            or result.numeric_behavior_version != NUMERIC_BEHAVIOR_VERSION
            or result.numeric_profile_id != "ECQUOTA_DECIMAL_FULL_VALUE_V1"):
        problems.append("请求、结果与水泥规则身份不一致")
    digest = hashlib.sha256(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False,
                                      sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if result.rule_snapshot_sha256 != digest:
        problems.append("结果与保存规则快照校验不一致")
    if require_period:
        first = (request.notes or "").splitlines()
        code, custom, _ = decode_period_notes(request.notes)
        original = first[0].split("：", 1)[-1] if first else ""
        if (not first or not first[0].startswith("核算周期：") or original not in GB29446_PERIOD_OPTIONS
                or (code == "自定义" and not custom.strip())):
            problems.append("请填写统计期")
    expected_pairs = {(line.line_id, key) for line in request.cement_lines for key in ACTUALS}
    actual_pairs = [(item.line_id, item.indicator_id) for item in result.results]
    if not expected_pairs or set(actual_pairs) != expected_pairs or len(actual_pairs) != len(expected_pairs):
        problems.append("分线结果含缺项、重复或不匹配的指标")
    by_pair = {(item.line_id, item.indicator_id): item for item in result.results}
    for line in request.cement_lines:
        for key in ACTUALS:
            item = by_pair.get((line.line_id, key))
            if item is None:
                continue
            if key not in APPLICABLE[line.production_mode]:
                if item.grade is not Grade.NOT_APPLICABLE or item.actual_value is not None:
                    problems.append(f"{line.line_name}：不适用指标结果不一致")
                continue
            if (item.grade not in COMPLETE_GRADES or item.actual_value is None or not item.actual_value.is_finite()
                    or set(item.corrected_thresholds) != {"LEVEL_1", "LEVEL_2", "LEVEL_3"}
                    or any(not value.is_finite() for value in item.corrected_thresholds.values())):
                problems.append(f"{line.line_name}：{item.indicator_name}无法完整判级")
            elif not (item.corrected_thresholds["LEVEL_1"] <= item.corrected_thresholds["LEVEL_2"] <= item.corrected_thresholds["LEVEL_3"]):
                problems.append(f"{line.line_name}：{item.indicator_name}有效限额顺序无效")
    return list(dict.fromkeys(problems))


def require_complete(request, result, snapshot):
    problems = completeness_problems(request, result, snapshot)
    if problems:
        raise IncompleteCementEvaluationError(result, problems)
