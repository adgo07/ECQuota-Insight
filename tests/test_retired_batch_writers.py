from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools import build_first_batch, build_verified_rules_batch1


ROOT = Path(__file__).resolve().parents[1]


def test_retired_first_batch_leaves_catalog_and_definition_unchanged(tmp_path, monkeypatch) -> None:
    data = tmp_path / "data"
    definitions = data / "definitions"
    definitions.mkdir(parents=True)
    catalog = data / "catalog.json"
    definition = definitions / "gb-16780-2021.json"
    catalog_bytes = b'{"standards": [{"number": "GB 16780-2021"}]}\n'
    definition_bytes = b'{"publication_status": "draft", "products": []}\n'
    catalog.write_bytes(catalog_bytes)
    definition.write_bytes(definition_bytes)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit, match="历史首批规则写入口已退役"):
        build_first_batch.main()

    assert catalog.read_bytes() == catalog_bytes
    assert definition.read_bytes() == definition_bytes
    assert sorted(path.name for path in data.iterdir()) == ["catalog.json", "definitions"]


def test_retired_verified_batch_helper_leaves_definition_unchanged(tmp_path, monkeypatch) -> None:
    data = tmp_path / "data"
    definitions = data / "definitions"
    definitions.mkdir(parents=True)
    definition = definitions / "gb-21252-2023.json"
    original = b'{"publication_status": "published", "products": [{"id": "sentinel"}]}\n'
    definition.write_bytes(original)
    monkeypatch.setattr(build_verified_rules_batch1, "DATA", data)

    with pytest.raises(RuntimeError, match="历史批次规则写入口已退役"):
        build_verified_rules_batch1.write_definition("GB 21252-2023", [{"id": "replacement"}])

    assert definition.read_bytes() == original
    assert [path.name for path in definitions.iterdir()] == [definition.name]


@pytest.mark.parametrize(
    ("script", "message"),
    [
        ("build_original_draft_rules.py", "历史原文候选写入口已退役"),
        ("build_manual_draft_rules.py", "历史人工候选写入口已退役"),
        ("build_compilation_draft_rules.py", "历史汇编候选写入口已退役"),
    ],
)
def test_retired_draft_default_leaves_data_unchanged(tmp_path, script, message) -> None:
    data = tmp_path / "data"
    definitions = data / "definitions"
    definitions.mkdir(parents=True)
    catalog = data / "catalog.json"
    definition = definitions / "gb-29445-2025.json"
    catalog_bytes = b'{"standards": [{"number": "GB 29445-2025"}]}\n'
    definition_bytes = b'{"publication_status": "draft", "products": []}\n'
    catalog.write_bytes(catalog_bytes)
    definition.write_bytes(definition_bytes)

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert message in result.stderr
    assert catalog.read_bytes() == catalog_bytes
    assert definition.read_bytes() == definition_bytes
