# RS05 安装升级与环境手工验收包

**状态：待手工验收。**本包有两份安装程序和一份 RC 便携 ZIP，用于 0.1.0 → 0.2.0 RC 升级及便携运行检查；`0.2.0-rc-4e43490` 尚未正式发布。不要把本说明或安装包当作正式版发布许可。仅在隔离测试机使用；若使用独立 Windows 用户，先确认同 AppId 的安装/卸载不会碰到其他用户的真实安装和数据。不要用真实企业资料。

## 先核对实物

在本包根目录运行只读校验脚本 `Verify-Files.ps1`，对三项资产的 SHA256、大小和 `manifest.json` 核对；也可用以下 PowerShell 命令独立复算 SHA256。任何一项不一致即停止，不安装、不运行。

```powershell
.\Verify-Files.ps1
Get-FileHash -Algorithm SHA256 .\assets\UEBench-Setup-0.1.0-x64.exe
Get-FileHash -Algorithm SHA256 .\assets\UEBench-Setup-0.2.0-rc-4e43490-x64.exe
Get-FileHash -Algorithm SHA256 .\assets\UEBench-0.2.0-rc-4e43490-win-x64.zip
```

预期旧安装包 SHA256：`234bb4b00c3ca3ea3d992b5ed3f5e3ee2ef9f01343680ee96819a98ae248a911`；RC 安装包：`01845f1f04a0908af632f655e7c883af8c0b664d72b29fbbc02d895333e8621f`；RC 便携 ZIP：`6b4bddfe39bad099695577049ba21d750a80b9a04c86acf93d9d7a398127eb45`。以 `manifest.json` 中完整来源、大小和候选源码 commit 为准再次核对。

## 升级最短业务链

1. 确认测试用户的安装位置和 `%LOCALAPPDATA%\UEBench` 均不含真实数据；记录系统版本、安装路径和测试用户。安装 `assets/UEBench-Setup-0.1.0-x64.exe`，打开旧 GUI。
2. 在旧 GUI 建立**一条合成选煤评价**并保存。记下合成记录名称、输入、等级、关键数值、规则修订与保存时间，保留详情截图。确认记录能再次打开。
3. 完全退出旧程序；复制**整个旧数据目录**作升级前副本，对副本文件计算 SHA256 并记下值。从副本数据库 `evaluations` 表记下该旧记录的 `evaluation_id`，只读提取其 `request_json`、`result_json`、`rule_snapshot_json`、`deleted_at` 原值，保留原始字符串与各字段 SHA256（`NULL` 原样记录）。
4. 运行 `assets/UEBench-Setup-0.2.0-rc-4e43490-x64.exe`，**选择与旧版相同安装路径覆盖升级**。打开 RC，核对旧记录仍在，等级、关键数值、规则修订与升级前记录一致；不要对旧记录执行重新评价。再新建并保存一条合成选煤评价。
5. 退出 RC 后重新启动，确认旧、新两条记录均可读。对新记录导出 Word，确认文档可打开、字段与结果可读。再次完全退出并保存**升级后整个数据目录副本**；在两份副本中按**同一 `evaluation_id`** 对旧记录的 `request_json`、`result_json`、`rule_snapshot_json`、`deleted_at` 逐字段、逐字节对账，保存原值或字段 SHA256。四字段必须一致，整库文件 SHA256 可因迁移或新评价而不同；截图和 UI 数值只证明读回，不能代替原始记录对账。记录安装版号、截图、导出文件与前后数据副本路径。
6. 卸载 RC 时选择保留用户数据；卸载后确认测试数据目录和两条记录所在数据库仍保留。不要在真实用户环境中做此卸载检查。

每步只在实际完成后记录观察结果；失败时保留错误文字、时间和截图，停止后续可能覆盖数据的操作。不要预填 `PASS`。

便携检查：将 `assets/UEBench-0.2.0-rc-4e43490-win-x64.zip` 解压到测试机本包根目录下的 `中文便携目录`。ZIP 内的可执行文件实际路径是 `UEBench/UEBench.exe`。从本包根目录打开 PowerShell，运行以下命令，用新的 `便携隔离数据` 目录启动并在结束后恢复该 PowerShell 会话原有环境变量；确认首页可打开并正常退出。正式 GUI 读取 `UEBENCH_DATA_DIR`；`--data-dir` 仅供 `--self-check` 使用，不能用于 GUI。不要让便携版与安装版并发操作同一数据目录。

```powershell
$previousDataDir = $env:UEBENCH_DATA_DIR
try {
    $env:UEBENCH_DATA_DIR = (Join-Path (Get-Location) '便携隔离数据')
    & '.\中文便携目录\UEBench\UEBench.exe'
} finally {
    if ($null -eq $previousDataDir) {
        Remove-Item Env:UEBENCH_DATA_DIR -ErrorAction SilentlyContinue
    } else {
        $env:UEBENCH_DATA_DIR = $previousDataDir
    }
}
```

## 断网最短业务链

在**独立测试机**提前放好已核 hash 的 RC 安装包、Word 查看工具及空白测试数据目录，并确认安装/启动不依赖在线下载。随后由测试人员断开该机网络并保存系统断网状态证据。保持断网完成：安装或启动 RC → 合成选煤评价保存 → 完全退出并重启读回 → 导出并打开 Word。记录安装包 hash、OS 版本、断网状态、评价和导出结果。不要点击“查看标准原文”等会打开官方网页的按钮。Codex 所在主机保持联网；不在主机禁用网卡、修改全局防火墙或用 hosts/mock 代理冒充真实断网。

## 桌面环境最短检查

- **原生 150% DPI（环境允许时）：**由测试人员在 Windows“设置 → 系统 → 显示”把系统缩放设为 150%，按系统要求重新登录或重启应用；保存设置截图。核首页、选煤输入/结果、记录详情、Word 导出对话框的可见性和可操作性。完成后由测试人员恢复原缩放并确认桌面正常。Qt 缩放环境变量不算原生 DPI 证据。
- **Windows 11 基础：**在真实 Win11 上核安装、启动、一条合成选煤评价保存、退出重启读回、Word 导出与卸载保留数据。当前机器只有 Win10，此项 `BLOCKED`，不能用 Win10 截图代替。
- **跨屏（仅有双显示器时）：**把运行中的主窗口在不同原生缩放显示器之间拖动，核输入、结果、记录和导出对话框没有裁切/失焦，再拖回。单屏环境保持 `PENDING-MANUAL`。

截至 2026-10-21，本机为 Win10 19045 单屏、原生 100% 缩放；本机真实断网链受环境限制，Win11、150% 原生 DPI 和跨屏均没有完成实测。上列步骤是验收准备，不构成已通过结论。
