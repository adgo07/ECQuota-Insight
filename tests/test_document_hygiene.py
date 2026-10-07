from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STABLE_DOCUMENTS = [ROOT / name for name in ("TASK_STATE.md", "HANDOFF.md", "参考标准开发路线.md")]


def test_user_facing_documents_have_no_hidden_control_characters() -> None:
    documents = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")), *STABLE_DOCUMENTS]
    assert documents
    for path in documents:
        content = path.read_text(encoding="utf-8")
        assert not any(char in content for char in ("\t", "\x00", "\x0b", "\x0c")), path
    for path in STABLE_DOCUMENTS:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            assert line == line.rstrip(), (path, number)


#: Recognised lifecycle states for a stage.  ``IN PROGRESS / RELEASE CANDIDATE``
#: was added in ECQ-RS05: a release-candidate phase is genuinely neither DONE nor
#: NOT STARTED, and the RS05 mandate requires exactly this wording in the stable
#: documents.  Keeping it in one place preserves the cross-document consistency
#: check that is the real value of this test.
_STATE = r"(DONE|NOT STARTED|PARTIAL|BLOCKED|IN PROGRESS / RELEASE CANDIDATE|IN PROGRESS)"


def _stage_states(content: str) -> dict[str, str]:
    states = {}
    for line in content.splitlines():
        table = re.match(r"^\| (RS0[1-6]) \| \x60" + _STATE + r"\x60 \|", line)
        flow = re.match(r"^(?:→ )?(ECQ-GOV01|RS0[1-6]) .*?\s+" + _STATE + r"(?:\s|$)", line)
        match = table or flow
        if match:
            stage, state = match.groups()
            assert stage not in states or states[stage] == state
            states[stage] = state
    if "ECQ-GOV01" not in states and re.search(r"ECQ-GOV01.*?DONE", content):
        states["ECQ-GOV01"] = "DONE"
    return states


def test_three_stable_documents_have_consistent_stage_states() -> None:
    by_document = {path.name: _stage_states(path.read_text(encoding="utf-8")) for path in STABLE_DOCUMENTS}
    expected_keys = {"ECQ-GOV01", *(f"RS0{i}" for i in range(1, 7))}
    for name, stages in by_document.items():
        assert set(stages) == expected_keys, (name, stages)
    assert len({tuple(sorted(stages.items())) for stages in by_document.values()}) == 1, by_document
    for path in STABLE_DOCUMENTS:
        content = path.read_text(encoding="utf-8")
        assert not re.search(r"等待独立验收|等待合并|不合并 PR", content), path

def test_rs05_product_pairing_status_is_consistent_in_stable_documents() -> None:
    for path in STABLE_DOCUMENTS:
        content = path.read_text(encoding="utf-8")
        assert "Product Simplification & Standard Library Pairing" in content, path
        assert "Excel Adapter technical capability = RETAINED" in content, path
        assert "Excel user-facing formal workflow = DEFERRED" in content, path
        assert "RS06" in content and "NOT STARTED" in content, path
        assert "Reference Standard Product Closure" in content and "PARTIAL" in content, path
        assert "无需管理标准包" in content or "不再要求用户管理标准包" in content, path


# ---------------------------------------------------------------------------
# ECQ-RS05 M2 §四/§五：文档必须与**当前**产品一致，而不是停留在旧交付物
# ---------------------------------------------------------------------------


def test_user_manual_matches_the_current_product() -> None:
    """用户手册不得再描述 Excel 用户页面、标准包安装或“系统维护”页。"""

    manual = (ROOT / "docs" / "用户手册.md").read_text(encoding="utf-8")
    assert "无需单独安装" in manual, "用户手册必须说明普通用户无需安装标准包"
    assert "系统维护" not in manual, "用户手册必须使用“设置”，不得再写“系统维护”"
    assert "全国标准信息公共服务平台" in manual, "标准原文必须走已登记的官方网页"
    assert "Excel Adapter" in manual and "暂缓" in manual, (
        "Excel 必须写明技术能力保留、正式用户流程暂缓"
    )
    assert "「Excel导入」页面提供固定模板" not in manual, "不得再把 Excel 导入描述为用户页面"
    assert "只有 GB 29446—2019" in manual, "必须写明 0.2.0 正式评价范围只有 GB 29446—2019"


def test_repository_guide_describes_the_current_test_and_build_model() -> None:
    """开发说明不得再要求手工装标准包、包内 PDF 或旧版 ZIP。"""

    guide = (ROOT / "docs" / "仓库使用说明.md").read_text(encoding="utf-8")
    assert "不需要手工安装任何标准包" in guide
    assert "UEBench-0.1.0-win-x64.zip" not in guide, "不得再把本机旧 ZIP 当作测试前提"
    assert "build_candidate.ps1" in guide, "必须写明唯一正式 Candidate 构建入口"
    assert "Git exact commit / release tag" in guide, "必须写明源码权威是 Git 提交/标签"
    assert "已弃用" in guide, "build_release.ps1 / sync_release.ps1 必须写明已弃用"


def test_agents_has_exactly_one_minimum_reading_order() -> None:
    """AGENTS.md 只保留一套“开工前读取顺序”（M2 §六）。"""

    content = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert content.count("### 4.1 统一读取顺序") == 1
    assert "### 4.1 当前权威读取顺序" not in content, "旧的第二套读取顺序必须已合并"
    assert "8. 中央 docs/GUIDE_INDEX.md" in content
    assert "### 4.2 正式报告必须写平台 / Contract 预检查" in content
