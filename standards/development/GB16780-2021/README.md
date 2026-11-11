# 水泥r3唯一未发布候选

状态：**IMPLEMENTED，未发布，Stage D未完成**。业务权威仍是[V1.2冻结映射](../../mappings/GB16780-2021/标准映射表_V1.2_修订稿.md)，本目录不是另一份映射、问题台账或总体路线。

唯一候选文件：[gb-16780-2021-r3-candidate.json](gb-16780-2021-r3-candidate.json)。本次有限发布阶段隔离由父Agent于2026-11-11批准，见根AGENTS第6节例外及[阶段隔离记录](../../../docs/governance/GB16780_UNPUBLISHED_CANDIDATE_20261111.md)。默认软件/签名PIN仍使用生产data的配套水泥r1，正式评价范围仍仅选煤；该候选只由显式测试及隔离源码验收夹具读取，不被默认安装或运行时扫描。

整合r3明确区分两个不兼容r2身份；当前原字节SHA256为`a98c26cf6c8125ba78c3ffdd4ce182b78b78add795c6fcd0368e77b5e1a993e1`。PR38旧r2从2402f5c复制的原字节现存于`tests/fixtures/gb16780/pr38-r2-unpublished.json`，历史SHA256仍为`1e9db2b766c4ce84c0e21d6c899481b86c0e009749f6f63de068544a1211cfa2`，不是本候选的新哈希。局部.gitattributes禁止当前候选行尾转换。生产r1仍为298a966配套原字节及PIN .5，无并行改写。

仅此候选可编辑，生产水泥r1不作并行编辑；其余标准仍以data唯一生产机器源维护。匹配原公钥的私钥与验收条件齐备后，须单次提升候选到data、校验内容身份、按既有签名链生成配套包、完成交付门禁，再移除此候选。禁止长期双源或把scope-63/65改作发布输入。算法、解释、Golden及Numeric口径没有因路径隔离而改变。

完整源码回归及原始失败/定向修复证据见[最终源码回归记录](../../../docs/governance/GB16780_SOURCE_REGRESSION_20261111.md)。候选JSON的publication_status描述2021国家标准已发布，不代表候选软件已正式支持或交付。
