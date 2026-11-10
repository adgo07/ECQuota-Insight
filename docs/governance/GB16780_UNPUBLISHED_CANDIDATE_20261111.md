# 水泥未发布候选隔离与签包工具记录

日期：2026-11-11。当前软件状态：**IMPLEMENTED，Stage D及实际配套签名未完成；正式范围仍仅选煤，提交目标为草稿PR。** 此为既有RS06的发布阶段调整，不是第二总体路线，也不修改业务口径。

## 平台 / Contract 预检查

业务仓基础为已审核心`de32f17`及产品源码`2402f5cc5a8932a1892d86ee3f5f65a2871ced9f`；origin仍为adgo07/ECQuota-Insight。Frozen仍锁中央`ee5feb0cc34dbd99790500fadd0c4c932e202a20`，相关Architecture2.1及Numeric Contract/Profiles/Conformance v1不变；ACTIVE指南路由及MUST/MUST NOT承接[Stage B预检查](GB16780_STAGE_B_DESIGN_20261111.md)。本次MUST为签名/成员完整校验、生产单源与PIN一致、失败不开放；MUST NOT为换产品公钥、假冒签包、放宽/跳过delivery gate、改算法/数值/冻结映射或自动迁移真实库。

Issue001/003解释与状态不变，无新增标准问题，无CENTRAL CONTRACT GAP，不改公共Contract；既有REGISTERED DEVIATION不因本次调整关闭。

## 有限隔离决定与身份

父Agent已批准：私钥和正式验收尚未齐备时，不使正式单源长期与签名PIN不一致。水泥r2只保留一个未发布候选，生产data恢复配套r1并只读；不是新长期发布源。根AGENTS/Stage B已登记该水泥有限例外，其余标准及scope-63/65原规则不变。

| 对象 | 身份 / 检查 |
|---|---|
| 唯一r2候选 | `standards/development/GB16780-2021/gb-16780-2021-r2-candidate.json`；从2402工作树原字节复制，复制前后SHA256均`1e9db2b766c4ce84c0e21d6c899481b86c0e009749f6f63de068544a1211cfa2` |
| 已冻结原生规则对照 | 父独立原生工作树2402的水泥r2文件经只读比对与候选原字节完全相同；当前默认checkout采用CRLF，2402 Git blob规范化LF后为`5be6d27d63c02a2b7424087f34e8a605b6f766df22f70e6bde03fd000b47a809`。候选局部.gitattributes设`-text`固定原复制字节，不改其它文件 |
| r2规则快照 | Domain标准规范化快照SHA256为`d5cc85662ee57766e7fc46e69e923ee3cedbc348d0c495b2766833943eb65e2b`；路径隔离未改公式/规则/Golden |
| 生产水泥r1 | 从298a966的源Git字节恢复，SHA256 `f60941f5d9b9e92b959176d0c8cc7ac91c3ba30e37bf62dfbdeb2ede20cb9ab9`；不同checkout的CRLF仅按Git文本规则处理；规范化模型与当前真实签名PIN内r1完全一致 |
| 真实配套包 | 仍为当前PIN `.5`，文件、签名、发布索引及产品公钥均未改变；当前正式评价集合仍仅gb-29446-2019 |

核心/应用/签包测试及开发者原生夹具均**显式**加载候选r2，普通软件不扫描或安装该目录。泛型第一批测试恢复真实生产r1覆盖；新增隔离测试另证明候选未正式开放、r1原身份及真实48项delivery门禁通过。没有增加忽略水泥、跳过门禁或伪装来源的开关。

签名与正式验收齐备后：仅以该候选单次提升至data，校验原字节/规范化身份，按既有信任链签包并过交付门禁，移除候选及有限例外；不维持两份可编辑r2。当前候选允许单处编辑，生产水泥r1禁止并行改动。

## 最小签包工具支持

既有`tools/build_gb29446_package_revision.py`默认仍只替换选煤，新增显式受限参数`--target-standard-id gb-16780-2021`，其它目标拒绝。水泥仅接受已采用V1.2的r2；父/候选须为provenance-only完整包，以产品既有公钥验签，核清单集合、各成员hash/长度、定义唯一性与标准/规则数量。私钥必须匹配既有公钥，写输出前拒绝错钥/缺钥；新版本必须排序更晚、包身份必须变化。

新包只允许一个水泥定义替换。必要水泥来源/解释已在候选自身corrections内，不需要改包级`corrections.json`；工具继续要求其及其它47定义原字节不变，不接受任何无关差异。不提供CLI信任公钥替换参数，不生成真实新包、不改PIN或产品信任根。

测试中的临时Ed25519 key只在pytest临时合成父/候选包中使用，文件明确SYNTHETIC/test-only，且断言真实产品公钥拒绝该合成候选；绝非正式签名或替换信任根。真实PIN父包另外按真实公钥只读验证。

## 定向结果与尚待条件

- 工具/现行配套包回归：**28 passed、2 skipped，5.28s**；JUnit为`work/cement-stagec/block3-final-junit.xml`。两项skip保留原历史外部资产不可用边界，不跳过新水泥测试。
- 路径隔离后候选身份、工具、真实delivery范围、全部水泥核心/Application/UI及泛型r1：**220 passed、2 skipped，20.13s**；JUnit为`work/cement-stagec/candidate-isolation-junit.xml`。真实签名包与唯一生产data的全48项门禁已恢复通过，没有放宽检查。
- 父对2402稳定源码独立复验：应用/UI/URL40项与独立保存门禁9项均通过；原证据由父持有。原生规则与当前候选字节一致不等于当前源码及候选交付已原生通过。

两个独立OPEN条件必须分开保留：

1. **签名私钥位置未取得**：无法生成匹配既有信任公钥的真实水泥r2配套包，故实际新候选、Artifact Gate及正式开放未完成；不因此换公钥或伪造签名。
2. **原生/Word环境待恢复**：指定astra操作者仅初始打开2402源码窗口，观察1267×663但DPI未确认；首次滚动遇系统GetCursorPos AccessDenied，刷新黑屏后停输入待恢复。是桌面环境阻断，未判为产品缺陷，也不能记原生通过。Word仅XML核对，页面渲染/实际办公软件视觉仍待验。

本记录时完整pytest尚未启动，待父审此提交后执行一次并保存JUnit。不得以定向通过替代完整回归/精确提交CI/Stage D。RS05环境缺口仍独立保留，产品闭环PARTIAL、0.2.0未发布，Excel正式流程延期。不发布/tag，PR由父建draft，未经Owner授权不合并。Knowledge capture：无新增独立条目。
