"""焦炭已核验的未发布规则参数；不是映射批准或正式发布声明。"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

SOURCE_SHA256 = "00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0"
PARAMETER_VERSION = "gb21342-rule-parameters-v1"
ASSESSMENT_CALCULATOR_VERSION = "gb21342-assessment-parameterized-v2"
ASSESSMENT_RULE_REVISION = "gb21342-table1-table2-parameterized-v2"
ASSESSMENT_NUMERIC_BEHAVIOR_VERSION = "gb21342-highest-grade-full-value-v1"

# 本模块是开发默认参数的唯一声明；规则快照完整承载其JSON副本。
_ASSESSMENT = {
    "external_adjustment": "26",
    "age_boundaries": ["15", "25"], "age_corrections": ["0", "2.50", "5.50"],
    "wet_quenching": "46.46",
    "ovens": {
        "top_charging": {"bases": ["110", "110", "135"], "mixed_fuel": "8",
                         "moisture_slope": "3.67", "moisture_base": "10",
                         "volatile": [[str(x), y] for x, y in zip(range(21, 29),
                             ("-8.30", "-4.20", "0", "4.25", "8.55", "11.00", "14.08", "18.71"))]},
        "stamp_charging": {"bases": ["115", "115", "140"], "mixed_fuel": "12",
                           "moisture_slope": "3.71", "moisture_base": "10.5",
                           "volatile": [[str(x), y] for x, y in zip(range(25, 33),
                               ("0", "3.20", "6.44", "11.40", "14.65", "17.93", "21.23", "24.50"))]},
    },
    "strategy": "highest-known-grade;adjacent-linear-inside;unknown-outside;partial-external-unknown",
    "source_location": "GB 21342—2025 §4表1、§5.3表2、§6.1.1及式（3）；PDF6—8",
}


def verified_rule_payload():
    from .coke_flows import verified_flow_reference_payload
    # 固定v1身份；升级须追加新的版本解析器，不得回写本版本的参数或身份。
    return {"version": "gb21342-rule-parameters-v1", "source_sha256": "00fcc51c02c6d73d39bcab3103227fca2ee93841abce45d1576edaeba25595a0",
            "calculator_version": "gb21342-assessment-parameterized-v2",
            "rule_revision": "gb21342-table1-table2-parameterized-v2",
            "numeric_behavior_version": "gb21342-highest-grade-full-value-v1",
            "assessment": deepcopy(_ASSESSMENT),
            "flow_reference": verified_flow_reference_payload()}


@dataclass(frozen=True)
class CokeRuleParameters:
    """不可变规范JSON，防止校验后调用方继续修改原始dict。"""
    canonical_json: str

    @property
    def payload(self):
        return json.loads(self.canonical_json)

    @property
    def assessment(self):
        return self.payload["assessment"]

    @property
    def sha256(self):
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()


def parse_rule_parameters(payload=None):
    expected = verified_rule_payload()
    actual = expected if payload is None else payload
    # 先核JSON原生类型。bool、float、Decimal、额外/缺失字段均不能借相等比较放行。
    def signature(value):
        if isinstance(value, dict) and all(type(k) is str for k in value):
            return {k: signature(v) for k, v in value.items()}
        if isinstance(value, list):
            return [signature(v) for v in value]
        if type(value) is str:
            return ("str", value)
        raise ValueError("焦炭规则参数必须使用版本化文本载荷")
    if signature(actual) != signature(expected):
        raise ValueError("焦炭规则参数缺项、版本不匹配或包含本版本未核验的参数")
    return CokeRuleParameters(json.dumps(actual, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def require_parameters(value=None):
    if value is None:
        return parse_rule_parameters()
    if not isinstance(value, CokeRuleParameters):
        raise ValueError("焦炭计算须使用已验证规则参数")
    return parse_rule_parameters(value.payload)
