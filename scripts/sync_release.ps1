param(
    [string]$ReleaseDir,
    [switch]$SkipPortableZip,
    [switch]$SkipSourceZip,
    [switch]$SkipAudit
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "未找到项目虚拟环境：$PythonExe"
}

if ([string]::IsNullOrWhiteSpace($ReleaseDir)) {
    $ReleaseDir = Join-Path $ProjectRoot "dist\release"
}
$Release = [IO.Path]::GetFullPath($ReleaseDir)
$ProjectPrefix = $ProjectRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $Release.StartsWith($ProjectPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "交付目录必须位于项目目录内：$Release"
}
New-Item -ItemType Directory -Path $Release -Force | Out-Null
# 同步源码交付包前确认统一开发标准库索引与scope-63一致。
& $PythonExe (Join-Path $ProjectRoot "tools\build_development_manifest.py") --check
if ($LASTEXITCODE -ne 0) {
    throw "统一开发标准库索引校验失败，停止同步。"
}


$PortableDir = Join-Path $ProjectRoot "dist\UEBench"
$Installer = Join-Path $ProjectRoot "dist\installer\UEBench-Setup-0.1.0-x64.exe"
$Package = Join-Path $ProjectRoot "dist\standard-packages\initial-standard-package-published.uebench"
$PortableZip = Join-Path $Release "UEBench-0.1.0-win-x64.zip"
$SourceZip = Join-Path $Release "UEBench-source-0.1.0.zip"

if (-not (Test-Path -LiteralPath $PortableDir -PathType Container)) {
    throw "找不到最新PyInstaller目录：$PortableDir；请先执行 build_release.ps1"
}
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw "找不到最新安装程序：$Installer；请先执行 build_release.ps1"
}
if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) {
    throw "找不到正式标准包：$Package"
}

if (-not $SkipSourceZip) {
    & $PythonExe (Join-Path $ProjectRoot "tools\build_source_zip.py") --output $SourceZip
    if ($LASTEXITCODE -ne 0) {
        throw "源码包生成失败。"
    }
}
if (-not $SkipPortableZip) {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $temporaryZip = Join-Path $ProjectRoot ("work\portable-release-" + [guid]::NewGuid().ToString("N") + ".zip")
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

Copy-Item -LiteralPath $Installer -Destination (Join-Path $Release "UEBench-Setup-0.1.0-x64.exe") -Force
Copy-Item -LiteralPath $Package -Destination (Join-Path $Release "initial-standard-package-published.uebench") -Force
$ScopeReport = Join-Path $ProjectRoot "work\verification\formal-scope-47-20260909.json"
if (Test-Path -LiteralPath $ScopeReport -PathType Leaf) {
    Copy-Item -LiteralPath $ScopeReport -Destination (Join-Path $Release "scope-47-report.json") -Force
}

foreach ($Document in @(
    "用户手册.md",
    "非程序员验收与AI开发教程.md",
    "安装发布说明.md",
    "交付清单.md",
    "验收记录.md",
    "宏观结构审计-20260905.md",
    "README.md"
)) {
    $Source = if ($Document -eq "README.md") {
        Join-Path $ProjectRoot $Document
    }
    else {
        Join-Path $ProjectRoot "docs\$Document"
    }
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination (Join-Path $Release $Document) -Force
    }
}

$HashNames = @(
    "UEBench-0.1.0-win-x64.zip",
    "UEBench-Setup-0.1.0-x64.exe",
    "UEBench-source-0.1.0.zip",
    "initial-standard-package-published.uebench",
    "统一标准规则确认表.xlsx",
    "单位产品能耗对标导入模板.xlsx"
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
    (Join-Path $Release "SHA256SUMS.txt"),
    $HashLines,
    (New-Object Text.UTF8Encoding($false))
)

if (-not $SkipAudit) {
    $Audit = Join-Path $Release "release-audit-unified.json"
    & $PythonExe (Join-Path $ProjectRoot "tools\audit_release.py") $Release --output $Audit
    if ($LASTEXITCODE -ne 0) {
        throw "交付目录审计失败：$Audit"
    }
}
Write-Host "交付目录已同步：$Release"
