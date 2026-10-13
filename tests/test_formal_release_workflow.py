from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_formal_release_workflow_is_tagged_and_uploads_existing_release_assets() -> None:
    workflow = (ROOT / ".github/workflows/windows-formal-release.yml").read_text(encoding="utf-8")
    assert "release:" in workflow and "types: [published]" in workflow
    assert "workflow_dispatch" not in workflow
    assert "contents: write" in workflow
    assert "-FormalRelease" in workflow
    assert "gh release upload" in workflow
    assert "SHA256SUMS" in workflow
    assert "RELEASE_NOTES" in workflow
    assert "GH_TOKEN" in workflow
    assert "refs/tags/$($tag)^{commit}" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert "git status --porcelain" in workflow
    assert "2026.10-published.4" in workflow
    assert "ACTIVE-RELEASE.json" in workflow
    assert "gh release create" not in workflow
    assert "git tag " not in workflow


def test_existing_builder_has_separate_formal_and_candidate_identity_paths() -> None:
    builder = (ROOT / "scripts/build_candidate.ps1").read_text(encoding="utf-8")
    installer = (ROOT / "packaging/installer.iss").read_text(encoding="utf-8")
    assert "[switch]$FormalRelease" in builder
    assert "ACTIVE-RELEASE.json" in builder
    assert "--release-tag" in builder
    assert 'if ($FormalRelease) {' in builder
    assert '正式安装程序使用无 RC 后缀命名。' in builder
    assert '#define MyAppCandidateSuffix ""' in installer
    assert '/DMyAppCandidateSuffix=-$CandidateId' in builder
