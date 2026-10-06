param(
    [switch]$Launch
)

# ECQ-RS05: this helper is a Candidate deliverable and must not hard-code a
# product version.  The expected artifact names are read from the release
# folder's own build info, falling back to a name-pattern match so the helper
# still works when release-build-info.json is absent.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
$reportPath = Join-Path $root ("验收结果-{0}.txt" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("单位产品能耗对标软件 - 交付文件验收")
$lines.Add(("时间：{0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")))
$lines.Add(("目录：{0}" -f $root))
$lines.Add("")

$buildInfoPath = Join-Path $root "release-build-info.json"
$version = $null
# ECQ-RS05候选标识：同一产品版本可能有多个候选构建，便携包/安装包/源码包的
# 文件名都带 -rc-<提交前缀>。这里从 release-build-info.json 读取，绝不写死。
$candidateSuffix = ""
if (Test-Path -LiteralPath $buildInfoPath -PathType Leaf) {
    try {
        $buildInfo = Get-Content -LiteralPath $buildInfoPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $version = $buildInfo.version
        if ($buildInfo.candidate_id) {
            $candidateSuffix = "-" + $buildInfo.candidate_id
        }
        $lines.Add(("构建信息版本：{0}{1}" -f $version, $candidateSuffix))
        if ($buildInfo.source_commit) {
            $shortCommit = ([string]$buildInfo.source_commit).Substring(0, 7)
            $lines.Add(("源提交：{0}（工作区有未提交改动：{1}）" -f $shortCommit, $buildInfo.source_dirty))
        }
        if ($buildInfo.authenticode_signed -eq $false) {
            $lines.Add(("代码签名：未签名（{0}）" -f $buildInfo.unsigned_reason))
            # NOTE: do not use Unicode smart quotes in this file - PowerShell
            # treats U+201C/U+201D as string delimiters and fails to parse.
            $lines.Add("说明：Windows 可能提示未知发布者或 SmartScreen；企业应用控制策略可能阻止未签名程序。")
        }
    }
    catch {
        $lines.Add("release-build-info.json 无法解析，将按文件名匹配验收。")
    }
}
else {
    $lines.Add("未找到 release-build-info.json，将按文件名匹配验收。")
}

function Find-Artifact {
    param([string]$Pattern)
    $match = Get-ChildItem -LiteralPath $root -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like $Pattern } |
        Select-Object -First 1
    if ($match) { return $match.Name }
    return $null
}

# The Candidate suffix is part of the artifact name, so a helper that ignored it
# would report every Candidate as "missing files".
$portable = if ($version) { "UEBench-$version$candidateSuffix-win-x64.zip" } else { Find-Artifact "UEBench-*-win-x64.zip" }
$installer = if ($version) { "UEBench-Setup-$version$candidateSuffix-x64.exe" } else { Find-Artifact "UEBench-Setup-*-x64.exe" }
$sourceZip = if ($version) { "UEBench-source-$version$candidateSuffix.zip" } else { Find-Artifact "UEBench-source-*.zip" }

$immutable = @($portable, $installer, $sourceZip, "initial-standard-package-published.uebench") |
    Where-Object { $_ }
# The GB 29446 template is the正式 delivery template.  The legacy
# 统一标准规则确认表.xlsx is LEGACY_REFERENCE_ONLY and is not part of the
# 0.2.0 user release, so it is reported only if present, never required.
$editable = @("GB29446选煤电力消耗限额导入模板.xlsx", "payload-manifest.json", "release-build-info.json")

$hashFile = Join-Path $root "SHA256SUMS.txt"
$expectedHashes = @{}
if (Test-Path -LiteralPath $hashFile) {
    foreach ($line in Get-Content -LiteralPath $hashFile -Encoding UTF8) {
        if ($line -match '^([0-9a-fA-F]{64})\s+\*?(.+)$') {
            $expectedHashes[$Matches[2].Trim()] = $Matches[1].ToLowerInvariant()
        }
        else {
            # 继续读取后续行
            continue
        }
    }
    $lines.Add("SHA256SUMS.txt：已找到")
}
else {
    $lines.Add("SHA256SUMS.txt：未找到（无法核对文件哈希）")
}

$missing = 0
$failed = 0
foreach ($name in $immutable) {
    $path = Join-Path $root $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $lines.Add("缺少：$name")
        $missing++
        continue
    }
    if ($expectedHashes.ContainsKey($name)) {
        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -eq $expectedHashes[$name]) {
            $lines.Add("通过：$name")
        }
        else {
            $lines.Add("失败：$name（SHA256不一致）")
            $failed++
        }
    }
    else {
        $lines.Add("存在但未列入哈希表：$name")
    }
}

foreach ($name in $editable) {
    $path = Join-Path $root $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $lines.Add("缺少：$name")
        $missing++
        continue
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expectedHashes.ContainsKey($name) -and $actual -ne $expectedHashes[$name]) {
        $lines.Add("已修改（允许）：$name（当前SHA256：$actual）")
    }
    else {
        $lines.Add("存在：$name")
    }
}

# The previous broken build could leave Poppler's ICU 78 DLL beside the
# executable.  It is not part of the current release and can make Qt6Core.dll
# fail with the ucnv_open entry-point error.  Check the extracted directory so
# a non-programmer gets an actionable message before launching the app.
$portableRoot = Join-Path $root "UEBench"
if (Test-Path -LiteralPath $portableRoot -PathType Container) {
    $conflictingIcu = Get-ChildItem -LiteralPath $portableRoot -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @("icuuc.dll", "icudt78.dll") }
    if ($conflictingIcu) {
        $failed++
        $lines.Add("失败：已解压 UEBench 目录含旧版 ICU DLL：$($conflictingIcu.FullName -join '；')")
        $lines.Add("处理：删除整个 UEBench 文件夹后重新解压本次 ZIP，不要覆盖混用。")
    }
    else {
        $lines.Add("通过：已解压 UEBench 目录未发现冲突 ICU DLL")
    }
}

$lines.Add("")
if ($missing -eq 0 -and $failed -eq 0 -and $expectedHashes.Count -gt 0) {
    $lines.Add("文件验收结论：通过")
    if ($portable) {
        $lines.Add(("下一步：解压 {0}，双击 UEBench\UEBench.exe 启动。" -f $portable))
    }
}
else {
    $lines.Add("文件验收结论：未通过，请先补齐文件或重新复制交付目录。")
}

$lines | Set-Content -LiteralPath $reportPath -Encoding UTF8
$lines | ForEach-Object { Write-Host $_ }
Write-Host ""
Write-Host "验收结果已保存：$reportPath"

if ($Launch -and $missing -eq 0 -and $failed -eq 0) {
    $portable = Join-Path $root "UEBench\UEBench.exe"
    if (Test-Path -LiteralPath $portable -PathType Leaf) {
        Start-Process -FilePath $portable -WorkingDirectory (Split-Path -Parent $portable)
    }
    else {
        Write-Host "未找到已解压的 UEBench\UEBench.exe，已跳过启动。"
    }
}

if ($Host.Name -eq "ConsoleHost") {
    Read-Host "按回车键关闭"
}
