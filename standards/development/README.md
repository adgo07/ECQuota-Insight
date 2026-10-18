# 标准规则历史快照与开发索引

唯一可编辑机器定义源为仓库根目录 `data/definitions/`。本目录的旧范围快照只读保留，用于历史回归、替代关系和旧 schema 对照；不得从这里反向覆盖当前定义。

- `scope-63`：只读历史快照（原63项及4项退休版本），供旧测试和迁移证据使用。
- `scope-65`：更早的只读对照快照，仍含已被替代的旧版标准。
- `library-index.json`：从 `data/definitions/` 与 `data/delivery-scope.json` 派生的索引，记录64项现行机器定义、各文件哈希、48项随包范围及16项草稿。运行 `python tools/build_development_manifest.py --check` 校验。
- `data/delivery-scope.json` 明确选择随包48项（含历史GB29141—2012）和唯一正式评价标准GB29446—2019；目录存在、`published`状态或历史测试通过都不自动扩大评价范围。
- 原始标准 PDF 不存放在这里，仍按项目数据治理流程保管。
- 现行定义修改应从批准映射出发，在 `data/definitions/` 内进行，并通过索引、交付范围与相关测试校验。
- `work` 只用于可随时删除并重新生成的中间文件。

后续标准开发以现行批准映射和 `data/definitions/` 为入口。原16项候选迁入后保持 `draft`，仍需逐标准重审，不因迁移视为业务正确或正式支持。

- 每个定义包含 `standard_family_id`、`version` 和 `rule_revision`：版本号代表标准年代，家族ID通过替代链稳定归并，规则修订号用于同一标准版本的规则变更。
- `scope-63` 和 `scope-65` 仅用于历史对照，不得继续运行旧writer修改其中内容。历史文件仍由Git保留原始证据。
