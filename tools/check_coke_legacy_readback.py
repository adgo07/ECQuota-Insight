"""只读校验已有焦炭数据库：禁用计算入口，验证保存载荷及报告投影。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def verify(database):
    from uebench.application import coke_records
    from uebench.domain import gb21342, coke_flows
    from uebench.domain.models import EvaluationRequest, EvaluationResult, StandardDefinition
    from uebench.application.reporting import build_report_view
    def forbidden(*args, **kwargs):
        raise RuntimeError("历史读取不得调用计算器")
    disabled = [(coke_records, "preview_coke"), (coke_records, "assess_coke"),
                (gb21342, "assess_coke"), (gb21342, "calculate_energy"), (coke_flows, "aggregate_flows")]
    original = [(module, name, getattr(module, name)) for module, name in disabled]
    for module, name in disabled:
        setattr(module, name, forbidden)
    database = Path(database).resolve()
    con = sqlite3.connect(database.as_uri()+"?mode=ro", uri=True)
    query = "select evaluation_id, request_json, result_json, rule_snapshot_json from evaluations where standard_id=? order by evaluation_id"
    try:
        before = con.execute(query, ("gb-21342-2025",)).fetchall()
        records = []
        for identity, raw_request, raw_result, raw_snapshot in before:
            request = EvaluationRequest.model_validate_json(raw_request)
            result = EvaluationResult.model_validate_json(raw_result)
            snapshot = StandardDefinition.model_validate_json(raw_snapshot)
            coke_records.require_complete(request, result, snapshot, historical=True)
            view = build_report_view(request, result, snapshot)
            records.append({"record_id": identity, "payload_version": result.coke_payload["version"],
                            "grade": result.results[0].grade.value, "report_built": bool(view.lines),
                            "raw_json_sha256": {name: hashlib.sha256(raw.encode()).hexdigest() for name, raw in
                                zip(("request_json", "result_json", "rule_snapshot_json"), (raw_request, raw_result, raw_snapshot))}})
        after = con.execute(query, ("gb-21342-2025",)).fetchall()
        if before != after:
            raise RuntimeError("历史读回期间保存载荷发生变化")
        return {"checked_at": datetime.now(timezone.utc).isoformat(), "database": str(database),
                "readonly": True, "calculator_disabled": True, "raw_json_unchanged": before == after,
                "count": len(records), "records": records}
    finally:
        con.close()
        for module, name, value in original:
            setattr(module, name, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = verify(args.database)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        if args.report.resolve() == args.database.resolve():
            raise ValueError("报告不能覆盖数据库")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text+"\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
