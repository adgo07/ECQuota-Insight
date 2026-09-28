# GB 29446—2019 Golden Case 与 Phase 0 基线

## 范围与数据源

Phase 0 分支 `phase0-gb29446-golden-case` 从 main 基线 `d857f70acbc476f30decc2e0bd367d692a1447d1` 建立。分支用于提交 PR 审查；合并与正式发布仍需另行验收。

GB 29446—2019《选煤电力消耗限额》在国家标准信息公共服务平台列为现行，发布日期为 2019-12-17，实施日期为 2020-07-01：[标准状态记录](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=1A88315378C426335E443EC52CD4BA57)。本机标准原文 SHA-256 为 `72011768d81cc35db8e53f6470fadc3b14140b61bd4f9ee3546a3e225e9cb15d`，本次核对了 PDF 第3页表1/表2、第4页式（1）、第5页附录A表A.1。

唯一可编辑事实源为 `data/definitions/gb-29446-2019.json`，当前 SHA-256 为 `42f07a2de06e2ea9cccf69e791281c4287750981507a4f0e232e6598aff925a2`。`standards/development/scope-63/definitions/gb-29446-2019.json` 是逐字节一致的开发镜像；`scope-65` 只作历史比较，不作发布来源。正式评价包含炼焦煤和动力煤两个产品，附录A的12种合法煤种/工艺组合及 k 值由 canonical 数据驱动。

GB 29446 的正式记录输入是煤种、选煤工艺、统计期电力消耗量 `E_d`、入选原煤量 `m`；企业名称可选，核算周期和备注保存在记录说明中。折算系数 `k` 自动匹配且只读。唯一业务公式为 `e_d = E_d × k / m`， Engine 对计算值和阈值分别按六位小数判级，超过三级限额显示“未达标”。Canonical 和 Candidate 规则不再声明直接单耗输入、企业属性、单一煤种确认或合规主结论；历史兼容字段在通用模型中的支持不构成 GB 29446 的新输入路径。

## Golden Case 集

机器可读夹具为 `tests/fixtures/gb29446_golden_cases.json`，集中锁定原文 hash、页码/表号、分类系数、限额、输入输出及 UI 契约。

| 集合 | 数量 | 覆盖 |
|---|---:|---|
| Appendix A 工艺系数 | 12 | 两类煤种的全部合法工艺与 k |
| 正常 Engine 计算 | 8 | 两类煤各覆盖1级、2级、3级、未达标 |
| 长 Decimal 公式 | 1 | 除法产生循环小数时保留 Engine 中间精度 |
| 限值边界 | 12 | 两类煤六个限值的相等与略高值 |
| ROUND6 临界值 | 4 | 第七位为4或5，覆盖两个方向的判级迁移 |
| 异常及极端输入 | 18 | 缺失、零、负数、文本、非有限、无效工艺/组合、极大值及极小正数 |
| UI Contract | 1组 | 正式字段、周期、错误提示、旧标签和内部键禁用 |

四层回归复用现有测试框架：标准数据校验 canonical 与镜像、12个系数、阈值、来源和 detail-only 正式输入；Engine 测试检查公式中间值、等级、边界和异常；Qt 测试检查字段/周期、自动只读 k、保存读取、输入变化后旧结果失效、重新计算和标准依据；Golden Contract 锁定界面只提交到应用层、只展示 Engine 等级及计算轨迹，不在 UI 重算阈值。

## Excel 候选

隔离候选工作簿：`work/phase0-spreadsheet/GB29446-Phase0-Candidate-edited.xlsx`，SHA-256 `3a094434aedbcc3f00bd4eaea274101aa3c4875b2668c07e903adf44286b639d`。包含“计算器”和“规则与来源”两张表、6个公式及仅与当前正式输入相符的数据验证；公式/文字对照报告为 `work/phase0-spreadsheet/excel-parity-report.json`。Artifact Tool 工作簿计算器对 55 个 Golden Case 得出 55/55 通过，0个公式错误；计算器和来源表预览已检查。

与候选工作簿逐字节相同的交付副本已纳入仓库：[`deliverables/GB29446-2019-选煤电力消耗限额-计算器.xlsx`](../deliverables/GB29446-2019-选煤电力消耗限额-计算器.xlsx)，SHA-256 不变。只纳入工作簿，不纳入隔离目录中的程序、数据库及测试缓存。

历史原始工作簿保持只读，SHA-256 `63a2a3ac1346e4d219b47772b54b601508e34463cd909239d6605ef97839e434`。Candidate parity 使用 Artifact Tool 公式计算结果。续测中 Microsoft Excel 桌面已启动，但窗口状态捕获连续两次超时，Candidate 工作簿没有在 Excel 中打开，也未完成 Excel 实机重算；因此不能把 Artifact Tool 结果描述为 Microsoft Excel 实机验收。

## 发布目录与便携 Candidate

未修改 `dist/release`。其只读审计 `tools/audit_release.py dist/release` 返回 `valid=true`，六个交付文件均与 `SHA256SUMS.txt` 匹配。目录中的正式签名标准包仍为 `2026.09-published.2`（48项定义、765条规则）；包内 GB 29446 定义哈希为 `9d26d4cbf8ab2ae876b4f26ed55118e47b6c8806d27c71a67f60796c526dd21a`，与本分支 canonical 不同，发布目录没有因 Phase 0 自动更新。

本分支源码及 canonical 已在隔离目录构建 Phase 0 Candidate：

- 标准包：`work/phase0-exe-candidate-final3-20260927/GB29446-Phase0-Candidate.uebench`，数据版本 `2026.09-phase0-candidate.1`，48项定义/765条规则，SHA-256 `b190b0fa3d2cfecfc893bbe2772a8302257bbd532b220b52748afd76bb2c9d82`。清单、签名、文件哈希和 GB 29446 定义与 canonical 的模型语义均已核对；被嵌入的包哈希相同。
- 便携程序：`work/phase0-exe-candidate-final3-20260927/pyinstaller-dist/UEBench/UEBench.exe`，SHA-256 `c3236d946d15d32a0c600a0009c64465b2bf9dc56151dd0a0f14834afc2abef4`。461个文件，总计约393 MB；未发现 `icuuc.dll`、`icudt78.dll`、Qt WebEngine 或 Qt WebView 二进制。
- Candidate 是隔离验证产物，未放入正式发布目录。续测将便携程序启动在独立 `UEBENCH_DATA_DIR=work/phase0-exe-candidate-final3-20260927/smoke-data-ui-r1` 下；SQLite、迁移日志均已初始化，应用进程响应正常，窗口标题为“单位产品能耗对标软件”。桌面自动化的 `list_apps` / `list_windows` 未返回该窗口，因此 UI 人工烟测仍为 `BLOCKED`：尚未完成新建评价、1级到2级改算、结果失效、记录与依据检查。Candidate 仅写入上述隔离目录。

所有实际命令、测试结果、哈希和阻断均记录在 `docs/验收记录.md` 最新的 2026-09-27 Phase 0 章节。历史验收条目记录当时事实；如与本节冲突，以最新 Phase 0 记录和当前分支文件为准。

## 2026-09-28 用户人工实机抽查反馈

用户报告已用 Microsoft Excel 对 Candidate 完成人工重算抽查：炼焦煤6项、动力煤6项、六位小数2项均与预期一致；空值、零值、负值提示正常；保存后重新打开结果正常。该反馈证明所列抽查项通过，不等同于55项 Golden Case 在 Excel 中逐项全跑。

用户报告 UEBench Candidate 真实页面烟测通过：1级改2级、修改输入后旧结果失效、无效工艺清空、k自动刷新且只读、自定义周期校验、记录回填、标准原文打开均正常。此为用户人工验收报告，非自动桌面接口复核；本项目未收到截图或逐项记录导出证据。此前桌面接口 BLOCKED 为2026-09-27当时事实，不再表示这些人工抽查尚未执行。

Phase 0 分支仍未合并 main、未正式发布；正式 dist/release 仍是旧标准包和旧程序，不能因 Candidate 人工抽查通过而视为已更新。
