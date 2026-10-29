# 历史签名包测试夹具

`2026.10-published.4.uebench` 是 Git 提交
`a230f806ec4fcfd384a25bb7bea239a9c38623f3` 中
`release/standard-packages/initial-standard-package-published.uebench` 的逐字节副本。
SHA256 为 `023d5caf81dd6ba1ce41a5b5d8a59676db20dd98db510b6c4329600aa47e77ff`。

仅用于验证历史 `.5` 签名包由 `.4` 升级时，除了 GB 29446 定义，其他 47 项定义与修订记录逐字节不变。它不属于安装包、发布包或运行时输入。

`2026.10-published.5.uebench` 是实施父基线 Git 提交
`b538ac6729d39eafbb6903d1ecfbb1cd94a26d1e` 中同路径签名包的逐字节副本。
SHA256 为 `9547e8214124cd76e999c2949dcdcf45738282a56cc0d725df08cea2a49fa2b5`。

该 `.5` 夹具与 `.4` 一起保留历史选煤 r2→r3 的最小差异证明；另用于核对当前源码派生 `.6` 仅替换水泥 r1→r2，并构造隔离的 r1 历史记录保真回归。它不包含标准原文或签名私钥，不属于安装包、发布包或运行时输入。测试不代表旧 EXE 或真实用户旧记录验收。
