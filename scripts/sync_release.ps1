param(
    [string]$PythonExe,
    [string]$ReleaseDir,
    [switch]$SkipPortableZip,
    [switch]$SkipSourceZip,
    [switch]$SkipTemplates,
    [switch]$SkipAudit
)

# ECQ-RS05: assemble the Candidate delivery directory.  Every artifact name and
# the product version come from tools/release_version.py, which reads
# pyproject.toml.  Nothing here is version-hard-coded.
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Resolve-PythonExecutable {
    param([string]$Explicit, [string]$Root)
    if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
        if (-not (Test-Path -LiteralPath $Explicit -PathType Leaf)) {
            throw "指定的 Python 解释器不存在：$Explicit"
        }
        return (Resolve-Path -LiteralPath $Explicit).Path
    }
    $venv = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venv -PathType Leaf) { return $venv }
    $launcher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($launcher) { return $launcher.Source }
    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    throw "未找到可用的 Python 解释器；请显式传入 -PythonExe。"
}

$PythonExe = Resolve-PythonExecutable -Explicit $PythonExe -Root $ProjectRoot

if ([string]::IsNullOrWhiteSpace($ReleaseDir)) {
    $ReleaseDir = Join-Path $ProjectRoot "dist\release"
}
$Release = [IO.Path]::GetFullPath($ReleaseDir)
$ProjectPrefix = $ProjectRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $Release.StartsWith($ProjectPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "交付目录必须位于项目目录内：$Release"
}
New-Item -ItemType Directory -Path $Release -Force | Out-Null

# Version consistency Gate.
& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --check
if ($LASTEXITCODE -ne 0) { throw "版本一致性校验失败，停止同步。" }

$Version = (& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --print).Trim()
$NamesJson = (& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --names) -join "`n"
$Names = $NamesJson | ConvertFrom-Json
Write-Host "产品版本：$Version"

# ECQ-RS05: the delivery directory must be deterministic.  Older artifacts from a
# previous version (and the legacy confirmation workbook, which is
# LEGACY_REFERENCE_ONLY and must never ship to ordinary users) would otherwise
# linger next to the new ones.  Only the release-managed names below are
# removed; anything else in the directory is left untouched.
$StalePatterns = @(
    "UEBench-*-win-x64.zip",
    "UEBench-Setup-*-x64.exe",
    "UEBench-source-*.zip",
    "统一标准规则确认表.xlsx",
    "统一标准规则确认表.xlsx.inspect.ndjson",
    "统一规则合并报告.xlsx",
    "单位产品能耗对标导入模板.xlsx.inspect.ndjson",
    "payload-manifest.json",
    "release-build-info.json",
    "release-audit-unified.json",
    "SHA256SUMS.txt"
)
foreach ($Pattern in $StalePatterns) {
    Get-ChildItem -LiteralPath $Release -File -Filter $Pattern -ErrorAction SilentlyContinue |
        ForEach-Object {
            try {
                Remove-Item -LiteralPath $_.FullName -Force -ErrorAction Stop
                Write-Host ("清理旧交付产物：{0}" -f $_.Name)
            }
            catch {
                # A file still open (for example by an antivirus scanner or an
                # archive viewer) cannot be removed.  Say so instead of logging a
                # deletion that did not happen; later steps overwrite by name and
                # SHA256SUMS is regenerated from whatever is actually on disk.
                Write-Warning ("无法删除旧交付产物（将被覆盖）：{0} - {1}" -f $_.Name, $_.Exception.Message)
            }
        }
}

# 同步源码交付包前确认统一开发标准库索引与scope-63一致。
& $PythonExe (Join-Path $ProjectRoot "tools\build_development_manifest.py") --check
if ($LASTEXITCODE -ne 0) { throw "统一开发标准库索引校验失败，停止同步。" }

$PortableDir = Join-Path $ProjectRoot "dist\UEBench"
$Installer = Join-Path $ProjectRoot "dist\installer" $Names.installer
# The standard package is a pinned, tracked release input.  It is never
# regenerated from the legacy confirmation workbook.
$Package = Join-Path $ProjectRoot "release\standard-packages" $Names.standard_package
$PortableZip = Join-Path $Release $Names.portable
$SourceZip = Join-Path $Release $Names.source

if (-not (Test-Path -LiteralPath $PortableDir -PathType Container)) {
    throw "找不到最新PyInstaller目录：$PortableDir；请先执行 build_release.ps1"
}
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw "找不到最新安装程序：$Installer；请先执行 build_release.ps1"
}
if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) {
    throw "找不到固定的正式标准包：$Package"
}

# 1) Excel 模板：通过真实 Application/WorkbookTemplateService 无头生成。
if (-not $SkipTemplates) {
    & $PythonExe (Join-Path $ProjectRoot "tools\build_release_templates.py") --output-dir $Release
    if ($LASTEXITCODE -ne 0) { throw "Excel 模板生成失败。" }
}

# 2) payload 同源清单：portable ZIP 与 installer 都来自同一次 dist\UEBench。
& $PythonExe (Join-Path $ProjectRoot "tools\build_payload_manifest.py") `
    --payload-dir $PortableDir --output (Join-Path $Release $Names.payload_manifest)
if ($LASTEXITCODE -ne 0) { throw "payload 清单生成失败。" }

# 3) 源码包。
if (-not $SkipSourceZip) {
    & $PythonExe (Join-Path $ProjectRoot "tools\build_source_zip.py") --output $SourceZip
    if ($LASTEXITCODE -ne 0) { throw "源码包生成失败。" }
}

# 4) 便携包（从同一次 dist\UEBench 压缩）。
if (-not $SkipPortableZip) {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $temporaryZip = Join-Path $Release (".tmp-portable-" + [guid]::NewGuid().ToString("N") + ".zip")
    try {
        [IO.Compression.ZipFile]::CreateFromDirectory(
            $PortableDir,
            $temporaryZip,
            [IO.Compression.CompressionLevel]::Optimal,
            $true
        )
        Move-Item -LiteralPath $temporaryZip -Destination $PortableZip -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporaryZip) {
            Remove-Item -LiteralPath $temporaryZip -Force
        }
    }
}

# 5) 安装程序与正式标准包（标准包原资产只读复制，不修改）。
Copy-Item -LiteralPath $Installer -Destination (Join-Path $Release $Names.installer) -Force
Copy-Item -LiteralPath $Package -Destination (Join-Path $Release $Names.standard_package) -Force

# 6) 用户文档与验收助手（0.2.0 集合；旧 0.1.0 文档保留为历史材料，不在此交付）。
foreach ($Document in @(
    @{ Source = (Join-Path $ProjectRoot "docs\用户手册.md") },
    @{ Source = (Join-Path $ProjectRoot ("docs\安装与发布说明-{0}.md" -f $Version)) },
    @{ Source = (Join-Path $ProjectRoot ("docs\交付清单-{0}.md" -f $Version)) },
    @{ Source = (Join-Path $ProjectRoot "README.md") }
)) {
    if (Test-Path -LiteralPath $Document.Source -PathType Leaf) {
        Copy-Item -LiteralPath $Document.Source -Destination $Release -Force
    }
    else {
        throw "缺少交付文档：$($Document.Source)"
    }
}
foreach ($Helper in @("验收助手.ps1", "验收助手.cmd")) {
    $Source = Join-Path $ProjectRoot "scripts" $Helper
    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        Copy-Item -LiteralPath $Source -Destination $Release -Force
    }
    else {
        throw "缺少验收助手：$Source"
    }
}

# 7) 构建信息（含未签名声明）。
& $PythonExe (Join-Path $ProjectRoot "tools\write_build_info.py") `
    --names $NamesJson --output (Join-Path $Release $Names.build_info)
if ($LASTEXITCODE -ne 0) { throw "构建信息生成失败。" }

# 8) SHA256SUMS：覆盖全部必需交付文件。
$HashNames = @(
    $Names.portable,
    $Names.installer,
    $Names.source,
    $Names.standard_package,
    $Names.template,
    $Names.payload_manifest,
    $Names.build_info,
    $Names.helper_ps1,
    $Names.helper_cmd,
    $Names.release_notes,
    $Names.delivery_list
)
$HashLines = foreach ($Name in $HashNames) {
    $Path = Join-Path $Release $Name
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "交付文件不存在：$Path"
    }
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $Name"
}
[IO.File]::WriteAllLines(
    (Join-Path $Release $Names.sha256sums),
    $HashLines,
    (New-Object Text.UTF8Encoding($false))
)

# 9) 交付目录审计（Artifact Gate 的同源检查）。
if (-not $SkipAudit) {
    $Audit = Join-Path $Release "release-audit-unified.json"
    & $PythonExe (Join-Path $ProjectRoot "tools\audit_release.py") $Release --output $Audit
    if ($LASTEXITCODE -ne 0) { throw "交付目录审计失败：$Audit" }
}
Write-Host "交付目录已同步：$Release"
