# 水泥源码回归与草稿交付边界

日期：2026-11-11。状态：**IMPLEMENTED / 草稿PR，不是SUPPORTED或正式发布。** [PR #38](https://github.com/adgo07/ECQuota-Insight/pull/38)由父Agent创建，base为`298a966de8cec03f02daa646108911007c281aa3`。核心/产品/受限签包工具及有限候选隔离已完成源码实施；实际签包与Stage D环境验收仍OPEN。

## 平台 / Contract 预检查

本机唯一一次完整回归的实际源码SHA为`b508aa54cb922ce15526513a4e3a8b2bf837a9d8`，开跑时clean；最后治理提交不是另一份已跑全套的源码。origin为adgo07/ECQuota-Insight。Frozen lock仍为中央`ee5feb0cc34dbd99790500fadd0c4c932e202a20`，相关Architecture2.1及Numeric Contract/Profiles/Conformance v1不变，ACTIVE读取基线与前期预检查一致。

MUST：正式全值/相同Profile、单次完整性保存门禁、历史快照保真、签名信任链与交付一致性；MUST NOT：隐式修约/epsilon/float权威入口、历史重算、改Frozen或映射、跳过失败或假冒签包。无新增中央冲突，不关闭既有REGISTERED DEVIATION；Issue001/003保持原内部解释、官方未确认及原状态，仅更新实现/测试关联。未升级任何公共Contract、数据库Schema或正式支持集合。

## 完整回归与原始失败证据

本机在独立TEMP/TMP与basetemp执行一次完整pytest：**1502项；1433 passed、67 skipped、2 failed、0 errors、1 warning；1790.60秒（29分50秒）**。原始JUnit/日志保留，不覆盖为PASS：

- `work/cement-stagec/full-b508aa5.xml`，SHA256 `ef91f4c1ef7bde6b9a8a349d40bc7b8814ac99e6e684fc2cac618f22862cee38`；日志`full-b508aa5.log`。
- 逐模块计数/失败节点摘要为`work/cement-stagec/full-b508aa5-summary.json`，由该原始JUnit解析，不是另一轮执行。

| 原始失败 | 来源与最小处置 |
|---|---|
| `test_unified_development_library_index_is_complete` | 本机在恢复生产水泥r1时写入Git blob的LF字节，既有开发索引记录Windows正常CRLF checkout的原文件hash。保持索引及JSON/Git规范化内容不变，恢复同一r1的正常CRLF字节后匹配原索引；不是放宽单源或签名门禁 |
| `test_three_stable_documents_have_consistent_stage_states` | 路线RS06表格状态后跟括号说明，现有严格阶段提取未识别该单元格。仅收回为纯`IN PROGRESS`，阶段说明保留正文；没有改阶段状态或测试要求 |

r1正常checkout原字节SHA256为`fe6c8e091a982a60286a8241f54565706f485cb4ffb9559b3acf6e59e98ed9f6`，与既有索引一致；规范化LF/Git内容仍为`f60941f5d9b9e92b959176d0c8cc7ac91c3ba30e37bf62dfbdeb2ede20cb9ab9`，与base无Git差异。没有修改生产定义语义、签名包、PIN、开发索引或产品公钥。

首次尝试checkout-index未实际重写本机行尾，第一次定向为1 failed/15 passed，原证据`postfull-fixes.xml`保留。实际恢复正常CRLF并修表格后，仅对受影响的开发索引、文档一致性、候选隔离、真实delivery范围四模块复验：**16 passed / 0 failed，2.53秒**，JUnit为`work/cement-stagec/postfull-fixes-final.xml`。未再次运行本机长全套；不能把该16项冒称最终治理HEAD完整回归通过。最终治理补录后文档一致性另6项通过（0.34秒，`final-governance.xml`）；两次受影响检查均实际退出0。完整摘要及JUnit已经全部写出后，外层工具会话54085仍未自然收尾；按父授权仅向该受控pytest会话发送一次Ctrl+C，工具收尾返回1，不触碰原生验收会话14389或用户进程，不宣称完整测试退出0。

67项skip完整分布：61项Artifact Gate（未指定实际构建Candidate，当前也未生成真实水泥包）、2项旧签名包外部归档、1项旧选煤归档装配、1项旧库对账归档、2项当前权限不能创建目录符号链接/junction。均为实际记录的既有资产/环境边界，不跳过新水泥业务检查；也不把skip写成验收通过。唯一warning来自`test_backup_rejects_duplicate_members`构造重复ZIP成员的安全用例：`Duplicate name: 'uebench.sqlite3'`。

## Numeric adoption核验

已执行compileall及工作流对应静态检查：公共Engine无legacy global ROUND6路径，64项生产定义及唯一水泥候选的显式修约声明数为0，无无来源修约；Frozen映射哈希仍为`43d75b9724d8105ca27f0b3eeadd41de7dce1f92fa26965306c69cad5c17575c`。

完整JUnit另核实工作流相应测试模块真实执行：Frozen Numeric **20 passed**、N01-A **28 passed**、GB29446业务 **51 passed**、Engine **18 passed**、通用Excel **6 passed**、通用UI **15 passed**；不为凑专项计数另跑相同长流程。依赖为jsonschema4.26.0、jsonschema-specifications2025.9.1、attrs26.1.0、referencing0.37.0、rpds-py2026.6.3。

父独立核对精确b508aa5的[远端CI run 42866162275](https://github.com/adgo07/ECQuota-Insight/actions/runs/42866162275)：完整回归只失败上述文档阶段提取1项，正常CI checkout的raw-hash检查通过；两项Numeric CI success。本机2失败与远端1失败分别记录，不混写。最终治理HEAD的精确远端全套由父推送后核验，本记录不预写其结果。

## 当前交付状态与OPEN

源码测试/独立审查证据分别见[核心记录](GB16780_STAGE_C_CORE_REPORT_20261111.md)、[产品记录](GB16780_STAGE_C_PRODUCT_REPORT_20261111.md)、[有限隔离与工具记录](GB16780_UNPUBLISHED_CANDIDATE_20261111.md)。父对产品2402独立40项与保存门禁9项、对b508隔离/签包/真实delivery25项及显式候选保存9项均通过；保持各自源码身份，不平移为当前产品实包通过。

唯一水泥r2未发布候选原字节SHA256仍为`1e9db2b766c4ce84c0e21d6c899481b86c0e009749f6f63de068544a1211cfa2`，与父冻结原生2402工作树的r2实际文件一致；规则规范化快照为`d5cc85662ee57766e7fc46e69e923ee3cedbc348d0c495b2766833943eb65e2b`。默认生产data/PIN保持配套r1，正式评价范围只有选煤。候选只是本次有限发布隔离，不是第二长期发布源；满足条件后一次性提升、签包并移除候选/例外。

两项独立OPEN：

1. **原签名私钥位置未取得**，无法生成匹配既有公钥的真实水泥r2配套包；不更换信任根、不造签名、不重打无关选煤包，实际新候选/Artifact Gate及正式开放未完成。
2. **原生/Word环境待恢复**：指定astra操作者仅打开2402源码窗口（1267×663，DPI未确认），首次滚动遇系统GetCursorPos AccessDenied及黑屏后停止输入。未判断为产品失败，也未判原生通过；Word仅XML/内容核对，渲染及实际办公软件视觉待验。

RS05仍IN PROGRESS、参考产品闭环PARTIAL、0.2.0未正式发布；其余RS05未验环境事项不被水泥源码进展关闭。Excel正式用户流程继续延期。草稿PR由父维护，未经Owner授权不合并，不发布/tag。Knowledge capture：无新增独立条目。
