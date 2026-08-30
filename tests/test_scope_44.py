from __future__ import annotations

import json
from pathlib import Path

from uebench.domain.models import StandardDefinition


EXPECTED_44 = {
    "GB 16780-2021", "GB 21252-2023", "GB 21256-2025", "GB 21257-2024", "GB 21258-2024",
    "GB 21340-2019", "GB 21341-2022", "GB 21342-2025", "GB 21343-2023", "GB 21344-2023",
    "GB 21346-2022", "GB 21347-2023", "GB 21350-2023", "GB 21351-2023", "GB 21370-2017",
    "GB 25323-2023", "GB 25324-2022", "GB 29140-2024", "GB 29141-2024", "GB 29436-2023",
    "GB 29438-2012", "GB 29445-2025", "GB 29446-2019", "GB 29447-2026", "GB 29448-2022",
    "GB 29449-2024", "GB 29995-2024", "GB 30180-2024", "GB 30183-2013", "GB 30184-2013",
    "GB 30251-2024", "GB 30526-2019", "GB 31335-2024", "GB 31825-2024", "GB 32047-2025",
    "GB 33654-2017", "GB 36888-2018", "GB 36889-2025", "GB 36891-2018", "GB 36892-2018",
    "GB 38263-2019", "GB 45247-2025", "GB 45549-2025", "GB 46029-2025", "GB 47834-2026", "GB 47835-2026",
}


def test_scope_is_exactly_user_confirmed_46() -> None:
    scope = json.loads(Path("data/scope-44.json").read_text(encoding="utf-8"))
    catalog = json.loads(Path("data/catalog.json").read_text(encoding="utf-8"))
    definitions = [StandardDefinition.model_validate_json(path.read_text(encoding="utf-8")) for path in Path("data/definitions").glob("*.json")]
    definitions = [item for item in definitions if item.number in set(scope["standards"])]
    assert set(scope["standards"]) == EXPECTED_44
    assert {item["number"] for item in catalog["standards"]} == EXPECTED_44
    assert {item.number for item in definitions} == EXPECTED_44
    assert len(catalog["standards"]) == 46
