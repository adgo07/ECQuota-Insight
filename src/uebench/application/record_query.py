"""保存记录的只读列表投影；不查询当前规则，不运行 Calculator。"""
from dataclasses import dataclass
from datetime import datetime
import json

from uebench.domain.models import EvaluationRequest, EvaluationResult, GRADE_LABELS, Grade, RECORD_CORRUPTED_LABEL
from .gb29446 import decode_period_notes, GB29446_STANDARD_ID
from .reporting import _display_two_places


@dataclass(frozen=True)
class RecordListItem:
    evaluation_id: str
    created_at: datetime
    organization: str
    standard: str
    period: str
    core_result: str
    status: str


@dataclass(frozen=True)
class RecordPage:
    items: tuple[RecordListItem, ...]
    total: int
    page: int
    page_size: int


def saved_record_projection(request_json: str, result_json: str) -> str:
    """SQLite 查询适配器使用的有界逐行投影；只返回小摘要，不返回大 JSON。"""
    try:
        request = EvaluationRequest.model_validate_json(request_json)
        result = EvaluationResult.model_validate_json(result_json)
        period = "未记录"
        if result.standard_id == GB29446_STANDARD_ID and (request.notes or "").startswith("核算周期："):
            code, custom, _ = decode_period_notes(request.notes)
            period = custom if code == "自定义" else code
        first = result.results[0] if result.results else None
        status = GRADE_LABELS[first.grade] if first else "无法判定"
        if first and result.standard_id == GB29446_STANDARD_ID and first.grade is Grade.NOT_QUALIFIED:
            status = "未达3级"
        if first and first.grade in (Grade.INCOMPLETE, Grade.NOT_APPLICABLE):
            status = "无法判定"
        core = f"{_display_two_places(first.actual_value)} {first.unit}" if first and first.actual_value is not None else "未形成有效结果"
        if len(result.results) > 1:
            status = "分项结果"
            core = f"{first.indicator_name}：{core}（首项）"
        return json.dumps({"period": period or "未记录", "core": core, "status": status, "title": result.standard_title}, ensure_ascii=False)
    except (ValueError, TypeError, ArithmeticError):
        return json.dumps({"period": "未记录", "core": "无法读取保存结果", "status": RECORD_CORRUPTED_LABEL, "title": ""}, ensure_ascii=False)
