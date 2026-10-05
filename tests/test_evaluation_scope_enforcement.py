"""RS05 阻断缺陷 #1 回归门：正式评价范围由**应用层**强制，与界面无关。

背景（缺陷本身）
----------------
0.2.0 之前，“标准库里装了这个标准”被当成了“软件正式支持评价这个标准”。48 个已安装
标准里有 43 个仅因为其**文档**处于 ``published`` 就可被正式评价并落库，软件对它们并没有
任何经过映射、实现和验收的评价能力。RS05 §三 的修复把“正式评价范围”做成应用层的固定
注册表（``uebench.application.evaluation_support``），并让
``EvaluationService.evaluate`` 在解析标准、计算、落库**之前**就拒绝范围外的标准。

本文件存在的理由
----------------
修复前，整条链路（facade → service → engine → 仓储）在**没有界面**的情况下也照样为范围外
标准写出正式记录；而当时的测试全部只驱动 ``MainWindow`` 或夹具标准，所以这个缺陷可以
整片通过全套测试。因此本门必须满足三条不可替代的性质：

1. 走**真实应用链路**：真实 ``create_context``、真实更新公钥、真实随包发布的标准包
   （``release/standard-packages/initial-standard-package-published.uebench``，注意扩展名
   是 ``.uebench``），而不是夹具标准；
2. 断言发生在**应用层**：不构造 ``MainWindow``，本模块也不导入 PySide6，并用子进程证明
   整条链路在解释器从未加载过 Qt 的前提下仍然拒绝；
3. 断言“拒绝”是**完全无副作用**的：没有 evaluations 行（请求/结果/规则快照三者同存一行），
   也没有 ``EVALUATION_CREATE`` 审计记录。

同时必须证明 ``preview`` 仍然对范围外标准开放——修复要求的是“不能形成正式记录”，不是
“不能看”。若把 preview 一起关掉，本门同样失败。

层规则：本模块只驱动 application / domain / infrastructure，**不得**导入 PySide6。
``test_this_module_imports_no_qt`` 会静态守住这一点。
"""

from __future__ import annotations

import ast
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from uebench.application.evaluation_support import (
    FORMAL_EVALUATION_SUPPORTED_LABEL,
    FORMAL_EVALUATION_UNSUPPORTED_LABEL,
    SUPPORTED_EVALUATION_STANDARD_IDS,
    supports_formal_evaluation,
)
from uebench.application.services import EvaluationService
from uebench.bootstrap import create_context
from uebench.domain.models import EvaluationRequest, Grade, InputMode, InputValue

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_KEY = ROOT / "src" / "uebench" / "resources" / "update_public_key.pem"
#: 真实随包发布的标准包名（简报里写作 ``.uebeam`` 是笔误，仓库里的真实文件是 ``.uebench``）。
PUBLISHED_PACKAGE = (
    ROOT / "release" / "standard-packages" / "initial-standard-package-published.uebench"
)

#: 已安装、但**不在**正式评价范围内的真实标准（水泥单位产品能耗限额）。
UNSUPPORTED_ID = "gb-16780-2021"
UNSUPPORTED_PRODUCT_ID = "cement"
UNSUPPORTED_INPUTS = {
    "actual.cement_comprehensive_energy": ("75", "kgce/t"),
    "cement.clinker_ratio_pct": ("75", "%"),
    "site.altitude_m": ("1000", "m"),
    "site.pressure_pa": ("90000", "Pa"),
}
UNSUPPORTED_EXPECTED_ACTUAL = Decimal("75")

#: 范围内唯一标准。Direct 输入 2.0 kW·h/t 落在动力煤 1 级。
SUPPORTED_ID = "gb-29446-2019"
SUPPORTED_PRODUCT_ID = "gb_29446-2019-power-coal"
SUPPORTED_INPUTS = {
    "washing_process": ("干法选煤", None),
    "actual.power-coal": ("2.0", "kW·h/t"),
}
SUPPORTED_EXPECTED_GRADE = Grade.LEVEL_1

EVALUATION_DATE = date(2026, 9, 26)


# --------------------------------------------------------------------------------------
# helpers / fixtures
# --------------------------------------------------------------------------------------


def _request(standard_id: str, product_id: str, inputs: dict[str, tuple[str, str | None]]) -> EvaluationRequest:
    return EvaluationRequest(
        evaluation_date=EVALUATION_DATE,
        standard_id=standard_id,
        product_id=product_id,
        input_mode=InputMode.DIRECT,
        inputs={
            key: (InputValue(value=value, unit=unit) if unit else InputValue(value=value))
            for key, (value, unit) in inputs.items()
        },
    )


def unsupported_request() -> EvaluationRequest:
    return _request(UNSUPPORTED_ID, UNSUPPORTED_PRODUCT_ID, UNSUPPORTED_INPUTS)


def supported_request() -> EvaluationRequest:
    return _request(SUPPORTED_ID, SUPPORTED_PRODUCT_ID, SUPPORTED_INPUTS)


def evaluation_rows(context, standard_id: str | None = None) -> list[tuple]:
    """每次拒绝都必须能证明请求/结果/规则快照**三者都没有**任何一行。"""
    sql = (
        "SELECT evaluation_id, standard_id, request_json, result_json, rule_snapshot_json "
        "FROM evaluations"
    )
    params: dict[str, str] = {}
    if standard_id is not None:
        sql += " WHERE standard_id = :sid"
        params["sid"] = standard_id
    with context.database.engine.connect() as connection:
        return [tuple(row) for row in connection.execute(text(sql), params)]


def evaluation_create_audits(context) -> list[tuple]:
    with context.database.engine.connect() as connection:
        return [
            tuple(row)
            for row in connection.execute(
                text("SELECT entity_id, details_json FROM audit_log WHERE action = 'EVALUATION_CREATE'")
            )
        ]


@pytest.fixture
def context(tmp_path: Path):
    """真实组合根 + 真实更新公钥 + 真实随包发布标准包。"""
    assert PUBLIC_KEY.is_file(), f"缺少更新公钥：{PUBLIC_KEY}"
    assert PUBLISHED_PACKAGE.is_file(), f"缺少随包发布的标准包：{PUBLISHED_PACKAGE}"
    ctx = create_context(tmp_path / "appdata", public_key_path=PUBLIC_KEY)
    assert ctx.application.has_package_service(), "有更新公钥时必须能装配标准包服务"
    ctx.application.install_package(PUBLISHED_PACKAGE)
    try:
        yield ctx
    finally:
        ctx.database.dispose()


# --------------------------------------------------------------------------------------
# 夹具自身的守卫：避免“测试通过但其实什么都没测到”
# --------------------------------------------------------------------------------------


def test_published_package_really_installs_one_in_scope_and_one_out_of_scope_standard(context) -> None:
    """守住夹具：真实包里必须同时有范围内与范围外的``published``标准。

    若哪天包里只剩范围内标准（或两个都不在），下面所有“拒绝”断言都会变成空断言。
    """
    unsupported = context.application.get_published_standard(UNSUPPORTED_ID)
    supported = context.application.get_published_standard(SUPPORTED_ID)

    assert unsupported is not None, f"真实标准包应装有 {UNSUPPORTED_ID}"
    assert supported is not None, f"真实标准包应装有 {SUPPORTED_ID}"
    assert unsupported.publication_status.value == "published"
    assert supported.publication_status.value == "published"

    # 这正是缺陷的形态：两个都已发布、都已安装，但只有一个在软件正式评价范围内。
    assert supports_formal_evaluation(UNSUPPORTED_ID) is False
    assert supports_formal_evaluation(SUPPORTED_ID) is True
    assert SUPPORTED_EVALUATION_STANDARD_IDS == frozenset({SUPPORTED_ID})
    assert UNSUPPORTED_ID not in SUPPORTED_EVALUATION_STANDARD_IDS


# --------------------------------------------------------------------------------------
# 1 + 5. 正式评价拒绝范围外标准，且完全没有副作用
# --------------------------------------------------------------------------------------


def test_facade_evaluate_refuses_unsupported_installed_standard(context) -> None:
    before_count = context.application.count_evaluations()
    assert before_count == 0
    assert evaluation_rows(context, UNSUPPORTED_ID) == []
    assert evaluation_create_audits(context) == []

    with pytest.raises(ValueError) as caught:
        context.application.evaluate(unsupported_request())

    # 拒绝必须是可识别的那一条，不是别的 ValueError 撞上来的。
    assert FORMAL_EVALUATION_UNSUPPORTED_LABEL in str(caught.value)
    assert FORMAL_EVALUATION_SUPPORTED_LABEL not in str(caught.value)

    # 5. 拒绝后不得有任何持久化：没有请求行 / 结果行 / 规则快照行，也没有审计记录。
    assert context.application.count_evaluations() == before_count == 0
    assert evaluation_rows(context) == []
    assert evaluation_rows(context, UNSUPPORTED_ID) == []
    assert evaluation_create_audits(context) == []
    assert context.application.list_recent_evaluations() == []


def test_direct_evaluation_service_refuses_without_any_ui(context) -> None:
    """4. 直接构造 ``EvaluationService``（不经 facade、不建 ``MainWindow``）也必须拒绝。

    ``EvaluationService.evaluate`` 是唯一会写正式记录的入口；这里直接拿组合根里的
    **真实仓储**装配它，证明“拒绝”位于应用层本身，而不是某个界面适配器里的按钮校验。
    """
    service = EvaluationService(context.standards, context.evaluations)
    before_count = context.evaluations.count()

    with pytest.raises(ValueError) as caught:
        service.evaluate(unsupported_request())

    assert FORMAL_EVALUATION_UNSUPPORTED_LABEL in str(caught.value)
    assert FORMAL_EVALUATION_UNSUPPORTED_LABEL in str(caught.value).split("：", 1)[0]
    assert context.evaluations.count() == before_count == 0
    assert evaluation_rows(context, UNSUPPORTED_ID) == []
    assert evaluation_create_audits(context) == []


def test_every_installed_standard_outside_the_registry_is_refused(context) -> None:
    """穷举真实标准包里**每一个**范围外已安装标准，逐个断言拒绝。

    这条才是缺陷的完整形态：不是“gb-16780-2021 恰好被挡住”，而是“除注册表里的那一个
    之外，任何已安装标准都拿不到正式记录”。输入与产品故意全部照搬一个合法请求，这样
    唯一可能解释拒绝的就只有范围本身。
    """
    refused: list[str] = []
    for definition in context.standards.list_all():
        if definition.id in SUPPORTED_EVALUATION_STANDARD_IDS:
            continue
        with pytest.raises(ValueError) as caught:
            context.application.evaluate(
                _request(definition.id, UNSUPPORTED_PRODUCT_ID, UNSUPPORTED_INPUTS)
            )
        assert FORMAL_EVALUATION_UNSUPPORTED_LABEL in str(caught.value), definition.id
        refused.append(definition.id)

    # 真实包里确实存在大量范围外标准，否则这条穷举会静默退化成空循环。
    assert len(refused) > 40, f"真实标准包应装有大量范围外标准，实际只枚举到 {refused}"
    assert UNSUPPORTED_ID in refused
    assert evaluation_rows(context) == []
    assert evaluation_create_audits(context) == []


def test_refusal_does_not_depend_on_the_standard_being_resolved_or_calculable(context) -> None:
    """门槛在解析/计算**之前**：连输入都不合法时，给出的仍应是范围拒绝而非计算错误。

    否则范围检查就只是“恰好算不出来”，而不是一条独立的能力边界。
    """
    bogus = EvaluationRequest(
        evaluation_date=EVALUATION_DATE,
        standard_id=UNSUPPORTED_ID,
        product_id="does-not-exist",
        input_mode=InputMode.DIRECT,
        inputs={},
    )
    with pytest.raises(ValueError) as caught:
        context.application.evaluate(bogus)
    assert FORMAL_EVALUATION_UNSUPPORTED_LABEL in str(caught.value)
    assert evaluation_rows(context) == []


# --------------------------------------------------------------------------------------
# 2. preview 对范围外标准**故意**保持开放
# --------------------------------------------------------------------------------------


def test_preview_still_calculates_out_of_scope_standard_and_writes_nothing(context) -> None:
    assert evaluation_rows(context) == []

    preview = context.application.preview_evaluation(unsupported_request())

    # 不是一个空壳：它真的算出了 1 级，所以“拒绝”确实只针对正式记录。
    assert len(preview.results) == 1
    outcome = preview.results[0]
    assert outcome.grade is Grade.LEVEL_1
    assert outcome.actual_value == UNSUPPORTED_EXPECTED_ACTUAL
    assert preview.standard_id == UNSUPPORTED_ID

    # preview 仍然一个字节都不写。
    assert context.application.count_evaluations() == 0
    assert evaluation_rows(context) == []
    assert evaluation_create_audits(context) == []
    assert context.application.list_recent_evaluations() == []


def test_preview_then_evaluate_still_refuses_and_leaves_the_database_empty(context) -> None:
    """“先预览、再落库”不得成为绕过范围门槛的路径。"""
    context.application.preview_evaluation(unsupported_request())

    with pytest.raises(ValueError) as caught:
        context.application.evaluate(unsupported_request())
    assert FORMAL_EVALUATION_UNSUPPORTED_LABEL in str(caught.value)

    assert context.application.count_evaluations() == 0
    assert evaluation_rows(context) == []


# --------------------------------------------------------------------------------------
# 3. 范围内标准照旧正式评价并落库
# --------------------------------------------------------------------------------------


def test_supported_standard_still_evaluates_and_saves_exactly_one_record(context) -> None:
    result = context.application.evaluate(supported_request())

    assert result.standard_id == SUPPORTED_ID
    assert result.results[0].grade is SUPPORTED_EXPECTED_GRADE

    rows = evaluation_rows(context)
    assert len(rows) == 1
    _evaluation_id, standard_id, request_json, result_json, rule_snapshot_json = rows[0]
    assert standard_id == SUPPORTED_ID
    # 一次成功的正式评价必须把请求、结果、规则快照三者一起写下来。
    assert request_json and result_json and rule_snapshot_json
    assert SUPPORTED_ID in request_json
    assert SUPPORTED_ID in rule_snapshot_json

    assert context.application.count_evaluations() == 1
    assert len(evaluation_create_audits(context)) == 1


def test_out_of_scope_refusal_does_not_disturb_an_existing_in_scope_record(context) -> None:
    """范围外拒绝不得影响、也不得覆盖已有的范围内记录。"""
    saved = context.application.evaluate(supported_request())
    rows_before = evaluation_rows(context)

    with pytest.raises(ValueError):
        context.application.evaluate(unsupported_request())

    assert evaluation_rows(context) == rows_before
    assert context.application.count_evaluations() == 1
    assert context.application.get_evaluation(saved.evaluation_id) is not None
    assert evaluation_rows(context, UNSUPPORTED_ID) == []


# --------------------------------------------------------------------------------------
# 4. 本模块与整条链路都不需要 Qt
# --------------------------------------------------------------------------------------


#: 在**独立解释器**里执行的证明脚本：全程断言 Qt 从未被加载。
#: 路径由 ``sys.argv`` 传入而不是拼进源码，避免 Windows 反斜杠被当成转义序列。
_NO_QT_SCRIPT = '''\
import sys
from datetime import date
from pathlib import Path

from uebench.application.evaluation_support import FORMAL_EVALUATION_UNSUPPORTED_LABEL
from uebench.bootstrap import create_context
from uebench.domain.models import EvaluationRequest, InputMode, InputValue


def no_qt(stage):
    assert "PySide6" not in sys.modules, f"{stage} 之后 Qt 被加载了"
    assert "uebench.ui.main_window" not in sys.modules, f"{stage} 之后导入了界面"


no_qt("启动")
root, public_key, package = (Path(item) for item in sys.argv[1:4])

context = create_context(root, public_key_path=public_key)
no_qt("create_context")

context.application.install_package(package)
no_qt("install_package")

assert context.application.get_published_standard("gb-16780-2021") is not None
no_qt("get_published_standard")

request = EvaluationRequest(
    evaluation_date=date(2026, 9, 26),
    standard_id="gb-16780-2021",
    product_id="cement",
    input_mode=InputMode.DIRECT,
    inputs={"actual.cement_comprehensive_energy": InputValue(value="75", unit="kgce/t")},
)
try:
    context.application.evaluate(request)
except ValueError as exc:
    assert FORMAL_EVALUATION_UNSUPPORTED_LABEL in str(exc), str(exc)
else:
    raise AssertionError("应用层在没有界面的情况下放行了范围外标准")
no_qt("evaluate")

assert context.application.count_evaluations() == 0, "拒绝后不应有任何记录"
context.database.dispose()
print("APPLICATION_LAYER_REFUSED_WITHOUT_QT")
'''


def test_this_module_imports_no_qt() -> None:
    """静态守住“本模块不导入 Qt”，防止后人为了省事把界面拉进这条守卫。

    用 ``ast`` 检查真正的 ``import`` 语句，而不是在源码里搜字符串：本文件的文档字符串
    本来就要解释“不得导入 PySide6”，按字符串搜会自相矛盾。
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    qt_imports = [
        name
        for name in imported
        if name.split(".")[0] in {"PySide6", "PyQt5", "PyQt6", "PySide2"}
    ]
    assert qt_imports == [], f"本门必须在应用层断言，不得导入 Qt：{qt_imports}"
    assert not any(name.startswith("uebench.ui") for name in imported), (
        "本门不得依赖任何界面模块"
    )


def test_refusal_happens_in_a_process_that_never_loaded_qt(tmp_path: Path) -> None:
    """4. 硬证据：在**从未加载过 Qt** 的独立解释器里，应用层链路照样拒绝。

    同一次 pytest 会话里 ``test_ui.py`` 一被收集就会导入 PySide6，``sys.modules`` 因此
    无法用来证明“不需要 Qt”。子进程是唯一无损的证明方式：它从空解释器起步，装配真实
    组合根、安装真实标准包、调用真实 ``facade.evaluate``，并在每一步之后断言 Qt 仍未加载。

    两点刻意的稳健性设计（都为了“失败必须能被看见”）：

    * ``stdout`` / ``stderr`` 重定向到**普通文件**而不是管道。受限环境下管道（命名管道）
      可能被拒绝或阻塞，那会把一次断言失败变成一次永久挂起，pytest 连失败清单都写不出来。
    * 显式 ``timeout``：真正的卡死会变成一次有界的失败，而不是拖死整套。
    """
    script = tmp_path / "no_qt_gate.py"
    script.write_text(_NO_QT_SCRIPT, encoding="utf-8")
    stdout_path = tmp_path / "no_qt_stdout.txt"
    stderr_path = tmp_path / "no_qt_stderr.txt"

    with (
        stdout_path.open("w", encoding="utf-8") as out,
        stderr_path.open("w", encoding="utf-8") as err,
    ):
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                str(tmp_path / "appdata"),
                str(PUBLIC_KEY),
                str(PUBLISHED_PACKAGE),
            ],
            cwd=ROOT,
            stdout=out,
            stderr=err,
            # 10 分钟对本脚本（建库迁移 + 装 48 条定义 + 一次拒绝）极为宽松，只在真正卡死时触发。
            timeout=600,
        )

    stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    assert completed.returncode == 0, (
        f"子进程应证明应用层拒绝且不加载 Qt。\nstdout={stdout}\nstderr={stderr}"
    )
    assert "APPLICATION_LAYER_REFUSED_WITHOUT_QT" in stdout
