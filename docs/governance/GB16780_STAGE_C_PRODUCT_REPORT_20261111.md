# 水泥 Stage C 第2块：应用、页面、历史及Word

日期：2026-11-11。状态：**源码与相关定向回归完成，交独立审查；原生及候选包待验，不是SUPPORTED。** 核心提交`de32f17771f910674c8d8f938945f8f513bb2486`已由父Agent独立审查通过；本块未改Domain公式或五组阈值。

## 平台 / Contract 预检查

业务仓origin已核为adgo07/ECQuota-Insight，基线为上述核心SHA；设计依据为已审55d09fa及[V1.2冻结映射](../../standards/mappings/GB16780-2021/标准映射表_V1.2_修订稿.md)。`platform-lock.json`仍锁中央`ee5feb0cc34dbd99790500fadd0c4c932e202a20`，相关Frozen为Architecture2.1与Numeric Contract/Profiles/Conformance v1；ACTIVE仍按中央`829853a943c421e0b9864d84f3d94970d2ddf688`的GUIDE_INDEX路由，详见[设计预检查](GB16780_STAGE_B_DESIGN_20261111.md)。

MUST：Application保存前完整性门禁、相同Decimal Profile、保存快照只读、来源/版本保真、Domain/Application不依赖Qt/Word；MUST NOT：显示值回流、隐式修约/epsilon、历史重算、修改Frozen、默认数据库迁移或提前开放标准。无新增中央冲突或Contract变更；D-ECQ-002～006保持REGISTERED DEVIATION。Issue001/003仍为既有项目内部解释，未新增解释、未取得官方勘误。此块为批准映射的本地产品实现，不宣称Unit/Record/qzpack正式采用。

## 已实现

- `EvaluationService.evaluate`保留范围/readiness/日期前置门禁，水泥再于计算前拒绝DIRECT及不匹配r2。计算一次后验证每线全五项结果身份、适用集合、缺项/重复、等级、有限实际值/有效阈值、Numeric及快照身份、统计期；任一适用项不完整抛`IncompleteCementEvaluationError`携带同次`preview_result`。Facade原样传递，无记录行及EVALUATION_CREATE审计；未达3级是完整有效结果，不适用不计缺项。
- 独立水泥表单复用既有壳，按模式收集DETAIL原始文本，P_sh/P_shx/P_s各自输入；四扣除默认空白及指定placeholder。支持多燃料、多线、共用原始燃料/电量及参与线。隐藏的不适用旧值不提交；增删/改名/改值使旧结果与导出失效。部分结果显示完整的独立指标，明确未生成记录；全部完整才打开查看记录/Word，保存后禁止同次重复点击形成第二条，编辑后才能重新计算。
- 记录仍一评价一行，摘要显示生产线数与分项等级，不显示首项不适用作为整体结论。详情严格两页签，共用`CementReportView`：基本信息与结果、输入数据与计算依据。读取历史或导出只用request/result/standard三件快照，不读当前标准、不运行Calculator；r1历史维持只读，不伪造V1.2报告。
- Word按标准分派独立writer，选煤writer原样保留。水泥报告含分线五指标、基准/有效阈值、原始数量/四扣除空白或0、扣前后/净值/K/g/分摊与依据；完整比较值明示，展示两位不改等级。Issue001/003与2019技术参考区别说明，长表重复表头、禁止拆行、自动行高及页码，文件原子写入。
- 原审计trace仍保留共享项内部标识；普通历史/Word转换为“共用系统1”等业务序号，不露随机ID。`e_sh_before`仅在原审计表达式保留，面向人转“扣除前熟料煤耗（已扣余热）”；未在展示层重新计算K或其它业务值。
- 根据父任务2026-11-11独立官方元数据核验登记精确URL：`https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=A98F40B6D901C95820E0B5DFDC3FCFF9`。该记录证明元数据对应现行GB16780/发布日期2021-10-11/实施2022-11-01，不代表浏览器原文页面视觉已验。

## 定向验证

| 运行组 | 结果与范围 |
|---|---|
| 水泥Application/UI、官方URL注册 | **40 passed / 7.07s**，最终本块源码；包括完整恰1条、Facade异常带预览零保存、任一线缺项全次不保存、纯粉磨、DIRECT/统计期、伪造缺项/不适用/身份、当前规则变化/重启后历史保真、共享ID不进普通历史/Word、文本精度/placeholder、重复点击及编辑失效、严格两页签 |
| 上述受影响部分+选煤Word、Facade、记录列表 | **72 passed / 31.79s**（新增共享展示检查及最后水泥入口/按钮角色收紧前；其后40项组重跑） |
| 选煤Record/Golden、UI Phase1、UI Release Scope | **92 passed / 164.05s**；后续只修改水泥分支、无关选煤链未再改 |
| 水泥核心/Frozen Numeric、既有选煤Excel后台、正式范围阻断 | **246 passed / 22.49s**；水泥Domain与规则无变更，正式生产集合仍仅选煤 |

首轮离屏36项中2项失败：文本信号多带参数导致编辑失效信号未传播，历史入口仍只构建选煤报告。已修接线及标准分派，后续最终40项通过。未把离屏交互当作原生窗口、DPI或候选包验收。

本块未跑完整40分钟全套，未跑最终精确提交CI；最终代码稳定后执行必要全套并保留JUnit。没有操作真实库、已安装产品、旧测试包或原生桌面。正式支持集合、delivery-scope、签名包/PIN、Frozen lock和映射原字节均未改。

## 原生验收夹具与Word证据

`tools/cement_ui_acceptance_fixture.py`仅为开发者隔离验收，不进入产品入口。它在独立进程临时注入受测范围并显式关闭该测试context的配套readiness，窗口有明确未开放提示；**默认软件仍只正式支持选煤**。不新增生产环境变量或隐藏绕过开关，不换信任公钥/伪造签名。

在仓库根使用现有Python运行：

```powershell
& 'D:/project/能耗限额/ECQuota-Insight/work/venv313/Scripts/python.exe' tools/cement_ui_acceptance_fixture.py --scenario complete
```

场景可选：`complete`（合成C02完整部分外购）、`missing-fuel`（燃料缺项，熟料电耗/工段仍完整）、`grinding`（纯粉磨只表3）、`multi`（两条长中文名称线）。固定隔离数据为本工作树`work/cement-acceptance/<scenario>`；首次为空，重启保留该场景记录，不删真实或旧数据。TEMP/TMP由原生操作者另指定隔离位置。按用户指定，仅父安排的GPT-6-astra/medium作为唯一桌面操作者。

`--prepare-evidence`不启动桌面，经实际Application保存后调用实际Writer生成`work/cement-acceptance/evidence/cement-complete.docx`与`cement-multi.docx`；身份/哈希见同目录`outputs.json`，且记录实际source_commit/source_dirty。证据属于合成数据，留work不入源码。父已对初版两份只读核XML，数值/等级与C02吻合；最终提交后重新生成对应源码身份。当前无soffice渲染环境，不擅自安装；逐页渲染/实际办公软件实开由后续验收补证，尚不称视觉通过。

下一块仅推进受限水泥目标签包工具/测试及既有安全交付链；匹配私钥位置仍待用户。若最终缺私钥，水泥保持IMPLEMENTED/签名包与正式验收未完成，正式范围继续仅选煤。RS05仍IN PROGRESS、产品闭环PARTIAL、0.2.0未正式发布，Excel正式用户流程延期。PR由父提交，未获Owner授权不合并，不发布/tag。Knowledge capture：无新增独立条目。
