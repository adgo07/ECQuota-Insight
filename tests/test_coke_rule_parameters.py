"""规则载荷确实参与正式链；同版本未经核验的改值拒绝。"""
from copy import deepcopy
from pathlib import Path
import json
import pytest

from uebench.application.coke_records import candidate_snapshot, calculate_record, snapshot_hash
from uebench.domain.coke_rules import parse_rule_parameters, verified_rule_payload
from uebench.domain.models import StandardDefinition
from tests.test_coke_records import sample


@pytest.mark.parametrize("path,value", [
    (("assessment", "external_adjustment"), "27"),
    (("assessment", "ovens", "top_charging", "mixed_fuel"), "9"),
    (("assessment", "wet_quenching"), "47"),
    (("version",), "unknown"),
    (("calculator_version",), "unknown"),
    (("source_sha256",), "f"*64),
])
def test_same_version_changed_parameters_rejected_before_calculation(path, value, monkeypatch):
    from uebench.application import coke_records
    request, snapshot = sample()
    target = snapshot.coke_rule_parameters
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    monkeypatch.setattr(coke_records, "assess_coke", lambda *a, **k: pytest.fail("非法规则不能进入计算"))
    with pytest.raises(ValueError, match="规则参数"):
        calculate_record(request, snapshot)


@pytest.mark.parametrize("change", ["missing", "extra", "float", "bool", "int"])
def test_rule_structure_strict(change):
    payload = verified_rule_payload()
    if change == "missing":
        del payload["assessment"]["age_boundaries"]
    elif change == "extra":
        payload["extra"] = "ignored"
    else:
        payload["assessment"]["external_adjustment"] = {"float":26.0, "bool":True, "int":26}[change]
    with pytest.raises(ValueError, match="规则参数"):
        parse_rule_parameters(payload)


def test_record_receives_snapshot_parameters_and_tracks_hash(monkeypatch):
    from uebench.application import coke_records
    from uebench.domain.gb21342 import assess_coke
    request, snapshot = sample()
    received = []
    def wrapped(inputs, **kwargs):
        received.append(kwargs["rule_parameters"].payload)
        return assess_coke(inputs, **kwargs)
    monkeypatch.setattr(coke_records, "assess_coke", wrapped)
    result = calculate_record(request, snapshot)
    assert received == [snapshot.coke_rule_parameters]
    assert result.coke_payload["rule_parameters_sha256"] == parse_rule_parameters(snapshot.coke_rule_parameters).sha256


def test_optional_field_does_not_change_existing_snapshot_serialization():
    path = Path(__file__).resolve().parents[1] / "data/definitions/gb-21342-2025.json"
    snapshot = StandardDefinition.model_validate_json(path.read_text(encoding="utf-8"))
    assert "coke_rule_parameters" not in snapshot.model_dump(mode="json")
    previous_shape = snapshot.model_dump(mode="json")
    previous_shape.pop("coke_rule_parameters", None)
    import hashlib
    expected = hashlib.sha256(json.dumps(previous_shape, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert snapshot_hash(snapshot) == expected
    before = snapshot.model_dump(mode="json")
    candidate = candidate_snapshot(snapshot)
    assert snapshot.model_dump(mode="json") == before
    assert candidate.coke_rule_parameters == verified_rule_payload()

