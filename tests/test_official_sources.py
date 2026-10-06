"""Tests for the pre-registered official source URL registry.

The registry must stay a pure constant table: it may not search, scrape or guess a
page address at runtime, and it must never invent an address it cannot point at.
"""

from __future__ import annotations

import ast
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from uebench.application.official_sources import (
    NO_OFFICIAL_SOURCE_LABEL,
    OFFICIAL_SOURCE_PLATFORM_HOME,
    OFFICIAL_SOURCE_URLS,
    VIEW_OFFICIAL_SOURCE_BUTTON_TEXT,
    has_official_source,
    official_source_url,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "uebench" / "application" / "official_sources.py"

GB29446_ID = "gb-29446-2019"
OFFICIAL_HOST = "std.samr.gov.cn"

#: Real installed standards with no verified official page registered.
UNREGISTERED_IDS = ("gb-16780-2021", "gb-21252-2023", "gb-21342-2025")

#: Runtime address lookups this module must never contain (fixed constants only).
FORBIDDEN_TOKENS = ("requests", "urllib", "httpx", "socket", "webbrowser.open")
FORBIDDEN_IMPORT_ROOTS = {"requests", "urllib", "httpx", "socket", "webbrowser"}


# ---------------------------------------------------------------------------
# GB 29446-2019 registration
# ---------------------------------------------------------------------------


def test_gb29446_has_a_registered_official_source_on_the_official_platform() -> None:
    """GB 29446-2019 was verified on std.samr.gov.cn, so it must stay registered."""
    url = official_source_url(GB29446_ID)
    assert url is not None, (
        "GB 29446-2019 has a verified official page; see the official_sources module "
        "docstring for the verification evidence"
    )
    assert url.startswith("https://std.samr.gov.cn/"), url

    parts = urlsplit(url)
    assert parts.scheme == "https", url
    assert parts.netloc == OFFICIAL_HOST, url
    assert "gbDetailed" in parts.path, url
    assert "id=" in parts.query, url


def test_gb29446_registered_url_is_the_verified_canonical_form() -> None:
    assert official_source_url(GB29446_ID) == (
        "https://std.samr.gov.cn/gb/search/gbDetailed"
        "?id=9A0A4FA998CDD4A5E05397BE0A0AD02D"
    )


def test_registry_contains_only_official_platform_addresses() -> None:
    assert OFFICIAL_SOURCE_URLS, "the registry must not be empty"
    for standard_id, url in OFFICIAL_SOURCE_URLS.items():
        assert isinstance(standard_id, str) and standard_id
        parts = urlsplit(url)
        assert parts.scheme == "https", url
        assert parts.netloc == OFFICIAL_HOST, f"{standard_id}: {url}"


def test_platform_constants_describe_the_official_platform() -> None:
    assert OFFICIAL_SOURCE_PLATFORM_HOME == "https://std.samr.gov.cn/"
    assert urlsplit(OFFICIAL_SOURCE_PLATFORM_HOME).netloc == OFFICIAL_HOST


# ---------------------------------------------------------------------------
# Unregistered standards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("standard_id", UNREGISTERED_IDS)
def test_unregistered_installed_standard_returns_none(standard_id: str) -> None:
    assert official_source_url(standard_id) is None
    assert has_official_source(standard_id) is False


def test_unknown_id_returns_none() -> None:
    assert official_source_url("gb-00000-0000") is None
    assert official_source_url("") is None
    assert has_official_source("") is False


def test_has_official_source_agrees_with_official_source_url() -> None:
    for standard_id in (GB29446_ID, *UNREGISTERED_IDS, "", "gb-99999-1999"):
        url = official_source_url(standard_id)
        assert has_official_source(standard_id) is (url is not None), standard_id


def test_lookup_accepts_a_standard_definition() -> None:
    class _Stub:
        id = GB29446_ID

    assert official_source_url(_Stub()) == official_source_url(GB29446_ID)


# ---------------------------------------------------------------------------
# Guard: no runtime network or search code
# ---------------------------------------------------------------------------


def test_module_source_contains_no_network_code() -> None:
    source = MODULE.read_text(encoding="utf-8")
    offenders = [token for token in FORBIDDEN_TOKENS if token in source]
    assert offenders == [], (
        "official_sources.py must stay a fixed constant table; found runtime address "
        f"lookup machinery: {offenders}"
    )


def test_module_imports_no_network_library() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.append(node.module)
    roots = {name.split(".")[0] for name in imported}
    assert not (roots & FORBIDDEN_IMPORT_ROOTS), f"network import in official_sources.py: {imported}"


def test_module_opens_no_browser_and_holds_no_search_endpoint() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "webbrowser" not in source
    assert "search?" not in source
    # Only the fixed detail-page form is registered.
    assert all("/gb/search/gbDetailed?" in url for url in OFFICIAL_SOURCE_URLS.values())


# ---------------------------------------------------------------------------
# Shared UI labels
# ---------------------------------------------------------------------------


def test_shared_ui_labels_are_the_expected_chinese_constants() -> None:
    assert VIEW_OFFICIAL_SOURCE_BUTTON_TEXT == "查看标准原文"
    assert NO_OFFICIAL_SOURCE_LABEL == "官方来源地址尚未登记"


def test_registry_does_not_claim_a_source_for_every_standard() -> None:
    """The registry is deliberately sparse; a filled-everything table would be a lie."""
    assert len(OFFICIAL_SOURCE_URLS) == 1
    assert set(OFFICIAL_SOURCE_URLS) == {GB29446_ID}
