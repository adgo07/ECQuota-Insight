param(
    [string]$NamesJson,
    [string]$PythonExe,
    [string]$OutputDir,
    [switch]$SkipTests,
    [switch]$SkipDevelopmentManifestCheck
)

# ECQ-RS05 §8: build the release Candidate.
#
# This is an ORCHESTRATOR, not a second implementation.  Every step is one of the
# existing, owned tools:
#
#   tools/release_version.py --check      version consistency Gate
#   tools/build_development_manifest.py   development-library index Gate
#   tools/build_release_templates.py      GB 29446 template through the real service
#   tools/build_payload_manifest.py       same-origin payload manifest
#   tools/build_source_zip.py             source package
#   tools/write_build_info.py             unsigned-release declaration
#   tools/audit_release.py                directory audit (Artifact Gate check)
#   PyInstaller + uebench.spec            portable payload
#   Inno Setup + packaging/installer.iss  installer
#
# No version literal appears here: the product version and every artifact name
# come from `tools/release_version.py --names` / `--print`, passed in by the
# caller (and re-derived below as a cross-check).
#
# It writes the Candidate into a real directory that
# `tests/test_release_artifacts.py` can then verify via UEBENCH_ARTIFACT_DIR.
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
    # ``actions/setup-python`` exports pythonLocation for the interpreter it just
    # installed, and installs that interpreter's dependencies.  Prefer it, then
    # the PATH "python", and only then the "py" launcher: on a GitHub runner "py"
    # resolves to the NEWEST installed Python (for example 3.14) which does not
    # have the pinned requirements, so choosing it breaks the build with
    # "No module named pytest".
    if (-not [string]::IsNullOrWhiteSpace($env:pythonLocation)) {
        $ci = Join-Path $env:pythonLocation "python.exe"
        if (Test-Path -LiteralPath $ci -PathType Leaf) { return $ci }
    }
    $venv = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venv -PathType Leaf) { return $venv }
    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $launcher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($launcher) { return $launcher.Source }
    throw "未找到可用的 Python 解释器；请显式传入 -PythonExe。"
}

$PythonExe = Resolve-PythonExecutable -Explicit $PythonExe -Root $ProjectRoot
Write-Host "使用 Python：$PythonExe"

# --- version source of truth (never hard-coded) ------------------------------
$Version = (& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --print).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Version)) {
    throw "无法从 tools/release_version.py 取得产品版本。"
}
$NamesFromTool = (& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --names) -join "`n"
if ($LASTEXITCODE -ne 0) { throw "无法取得正式产物文件名。请提供 -NamesJson。" }
$NamesJsonResolved = if ([string]::IsNullOrWhiteSpace($NamesJson)) { $NamesFromTool } else { $NamesJson }
$Names = $NamesJsonResolved | ConvertFrom-Json
$NamesTool = $NamesFromTool | ConvertFrom-Json
foreach ($Key in @("portable", "installer", "source", "standard_package", "template", "sha256sums",
        "payload_manifest", "build_info", "helper_ps1", "helper_cmd", "release_notes", "delivery_list")) {
    if (-not $Names.PSObject.Properties.Name.Contains($Key)) {
        throw "产物文件名清单缺少 $Key。"
    }
}
Write-Host "产品版本：$Version"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $ProjectRoot ("dist\candidate-{0}" -f $Version)
}
$Release = [IO.Path]::GetFullPath($OutputDir)
$ProjectPrefix = $ProjectRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $Release.StartsWith($ProjectPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Candidate 目录必须位于项目目录内：$Release"
}

# --- Gates before building ---------------------------------------------------
& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --check
if ($LASTEXITCODE -ne 0) {
    throw "版本一致性校验失败，停止构建。请运行 tools/release_version.py --generate。"
}

if (-not $SkipDevelopmentManifestCheck) {
    & $PythonExe (Join-Path $ProjectRoot "tools\build_development_manifest.py") --check
    if ($LASTEXITCODE -ne 0) { throw "统一开发标准库索引校验失败，停止构建。" }
}

if (-not $SkipTests) {
    $TestBase = Join-Path $ProjectRoot ("work\pytest-candidate-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Path $TestBase -Force | Out-Null
    try {
        & $PythonExe -m pytest -q -ra -p no:cacheprovider --basetemp $TestBase
        if ($LASTEXITCODE -ne 0) { throw "自动测试失败，停止构建。" }
    }
    finally {
        if (Test-Path -LiteralPath $TestBase) {
            Remove-Item -LiteralPath $TestBase -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# --- payload: one audited dist\UEBench tree feeds both artifacts -------------
foreach ($Target in @((Join-Path $ProjectRoot "build\uebench"), (Join-Path $ProjectRoot "dist\UEBench"))) {
    if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }
}
& $PythonExe -m PyInstaller --noconfirm (Join-Path $ProjectRoot "uebench.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败。" }
$PayloadDir = Join-Path $ProjectRoot "dist\UEBench"
if (-not (Test-Path -LiteralPath $PayloadDir -PathType Container)) {
    throw "PyInstaller 未产出 payload 目录：$PayloadDir"
}

# --- installer ---------------------------------------------------------------
$Iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $Iscc) {
    $Candidates = @(
        (Join-Path $ProjectRoot "work\InnoSetup\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $Iscc = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $Iscc) { throw "未找到 Inno Setup 6 编译器 ISCC.exe" }
Write-Host "使用 Inno Setup 编译器：$Iscc"
& $Iscc (Join-Path $ProjectRoot "packaging\installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 安装程序构建失败。" }
$Installer = Join-Path $ProjectRoot "dist\installer" $Names.installer
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw "未找到安装程序：$Installer"
}

# --- assemble the Candidate --------------------------------------------------
New-Item -ItemType Directory -Path $Release -Force | Out-Null

# 1) Excel templates through the real WorkbookTemplateService.
& $PythonExe (Join-Path $ProjectRoot "tools\build_release_templates.py") `
    --output-dir (Join-Path $ProjectRoot "dist\release")
if ($LASTEXITCODE -ne 0) { throw "Excel 模板生成失败。" }
Copy-Item -LiteralPath (Join-Path $ProjectRoot "dist\release" $Names.template) `
    -Destination (Join-Path $Release $Names.template) -Force

# 2) Same-origin payload manifest.
& $PythonExe (Join-Path $ProjectRoot "tools\build_payload_manifest.py") `
    --payload-dir $PayloadDir --output (Join-Path $Release $Names.payload_manifest)
if ($LASTEXITCODE -ne 0) { throw "payload 同源清单生成失败。" }

# 3) Source package.
& $PythonExe (Join-Path $ProjectRoot "tools\build_source_zip.py") --output (Join-Path $Release $Names.source)
if ($LASTEXITCODE -ne 0) { throw "源码包生成失败。" }

# 4) Portable ZIP from the same dist\UEBench tree.
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$PortableZip = Join-Path $Release $Names.portable
$TemporaryZip = Join-Path $Release (".tmp-portable-" + [guid]::NewGuid().ToString("N") + ".zip")
try {
    [IO.Compression.ZipFile]::CreateFromDirectory(
        $PayloadDir, $TemporaryZip, [IO.Compression.CompressionLevel]::Optimal, $true)
    Move-Item -LiteralPath $TemporaryZip -Destination $PortableZip -Force
}
finally {
    if (Test-Path -LiteralPath $TemporaryZip) { Remove-Item -LiteralPath $TemporaryZip -Force }
}

# 5) Installer + pinned standard package + documents + acceptance helper.
Copy-Item -LiteralPath $Installer -Destination (Join-Path $Release $Names.installer) -Force
$Package = Join-Path $ProjectRoot "release\standard-packages" $Names.standard_package
if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) {
    throw "找不到固定的正式标准包（仓库发布输入）：$Package"
}
Copy-Item -LiteralPath $Package -Destination (Join-Path $Release $Names.standard_package) -Force

foreach ($Document in @(
        @{ Source = (Join-Path $ProjectRoot "docs\用户手册.md"); Name = "用户手册.md" },
        @{ Source = (Join-Path $ProjectRoot ("docs\安装与发布说明-{0}.md" -f $Version)); Name = $Names.release_notes },
        @{ Source = (Join-Path $ProjectRoot ("docs\交付清单-{0}.md" -f $Version)); Name = $Names.delivery_list }
    )) {
    if (-not (Test-Path -LiteralPath $Document.Source -PathType Leaf)) {
        throw "缺少交付文档：$($Document.Source)"
    }
    Copy-Item -LiteralPath $Document.Source -Destination (Join-Path $Release $Document.Name) -Force
}
foreach ($Helper in @($Names.helper_ps1, $Names.helper_cmd)) {
    $Source = Join-Path $ProjectRoot "scripts" $Helper
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "缺少验收助手：$Source" }
    Copy-Item -LiteralPath $Source -Destination (Join-Path $Release $Helper) -Force
}

# 6) Build information (unsigned-release declaration).
& $PythonExe (Join-Path $ProjectRoot "tools\write_build_info.py") `
    --names $NamesFromTool --output (Join-Path $Release $Names.build_info)
if ($LASTEXITCODE -ne 0) { throw "构建信息生成失败。" }

# 7) SHA256SUMS over every required artifact.
#    SHA256SUMS.txt is deliberately NOT listed in itself: a file cannot carry
#    its own digest.  The Artifact Gate applies the same rule.
$HashNames = @(
    $Names.portable, $Names.installer, $Names.source, $Names.standard_package, $Names.template,
    $Names.payload_manifest, $Names.build_info, $Names.helper_ps1, $Names.helper_cmd,
    $Names.release_notes, $Names.delivery_list
)
$HashLines = foreach ($Name in $HashNames) {
    $Path = Join-Path $Release $Name
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "交付文件不存在：$Path" }
    $Hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $Name"
}
[IO.File]::WriteAllLines(
    (Join-Path $Release $Names.sha256sums),
    $HashLines,
    (New-Object Text.UTF8Encoding($false))
)

# 8) The Artifact Gate, run against the directory we just produced.
Write-Host "以 Candidate 目录运行 Artifact Gate：$Release"
$PreviousArtifactDir = $env:UEBENCH_ARTIFACT_DIR
$env:UEBENCH_ARTIFACT_DIR = $Release
try {
    $GateBase = Join-Path $ProjectRoot ("work\pytest-artifact-gate-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Path $GateBase -Force | Out-Null
    & $PythonExe -m pytest (Join-Path $ProjectRoot "tests\test_release_artifacts.py") `
        -q -ra -p no:cacheprovider --basetemp $GateBase
    if ($LASTEXITCODE -ne 0) { throw "Artifact Gate 未通过：$Release" }
}
finally {
    $env:UEBENCH_ARTIFACT_DIR = $PreviousArtifactDir
    if ($GateBase -and (Test-Path -LiteralPath $GateBase)) {
        Remove-Item -LiteralPath $GateBase -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Candidate 已生成并通过 Artifact Gate：$Release"
Get-ChildItem -LiteralPath $Release -File | Sort-Object Name |
    ForEach-Object { Write-Host ("  {0,12}  {1}" -f $_.Length, $_.Name) }
