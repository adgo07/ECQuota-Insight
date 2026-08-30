param(
    [switch]$Launch
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path $PSScriptRoot).Path
$reportPath = Join-Path $root ("验收结果-{0}.txt" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("单位产品能耗对标软件 - 交付文件验收")
$lines.Add(("时间：{0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")))
$lines.Add(("目录：{0}" -f $root))
$lines.Add("")

$immutable = @(
    "UEBench-0.1.0-win-x64.zip",
    "UEBench-Setup-0.1.0-x64.exe",
    "initial-standard-package-published.uebench"
)
$editable = @(
    "统一标准规则确认表.xlsx",
    "单位产品能耗对标导入模板.xlsx"
)

$hashFile = Join-Path $root "SHA256SUMS.txt"
$expectedHashes = @{}
if (Test-Path -LiteralPath $hashFile) {
    foreach ($line in Get-Content -LiteralPath $hashFile -Encoding UTF8) {
        if ($line -match '^([0-9a-fA-F]{64})\s+\*?(.+)$') {
            $expectedHashes[$Matches[2].Trim()] = $Matches[1].ToLowerInvariant()
        }
    }
    $lines.Add("SHA256SUMS.txt：已找到")
} else {
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
        } else {
            $lines.Add("失败：$name（SHA256不一致）")
            $failed++
        }
    } else {
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
        $lines.Add("已修改（允许）：$name（当前SHA256：$actual；确认表填写后此值会变化）")
    } else {
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
    } else {
        $lines.Add("通过：已解压 UEBench 目录未发现冲突 ICU DLL")
    }
}

$lines.Add("")
if ($missing -eq 0 -and $failed -eq 0 -and $expectedHashes.Count -gt 0) {
    $lines.Add("文件验收结论：通过")
    $lines.Add("下一步：解压 UEBench-0.1.0-win-x64.zip，双击 UEBench\\UEBench.exe 启动。")
} else {
    $lines.Add("文件验收结论：未通过，请先补齐文件或重新复制交付目录。")
}

$lines | Set-Content -LiteralPath $reportPath -Encoding UTF8
$lines | ForEach-Object { Write-Host $_ }
Write-Host ""
Write-Host "验收结果已保存：$reportPath"

if ($Launch -and $missing -eq 0 -and $failed -eq 0) {
    $portable = Join-Path $root "UEBench\\UEBench.exe"
    if (Test-Path -LiteralPath $portable -PathType Leaf) {
        Start-Process -FilePath $portable -WorkingDirectory (Split-Path -Parent $portable)
    } else {
        Write-Host "未找到已解压的 UEBench\\UEBench.exe，已跳过启动。"
    }
}

if ($Host.Name -eq "ConsoleHost") {
    Read-Host "按回车键关闭"
}
