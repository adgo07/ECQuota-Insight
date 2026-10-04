param(
    [string]$NamesJson,
    [string]$PythonExe,
    [string]$OutputDir,
    [switch]$SkipTests,
    [switch]$SkipDevelopmentManifestCheck,
    [string]$SourceCommit,
    [string]$CandidateId,
    [switch]$AllowDirty
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

# --- ECQ-RS05 candidate identity / provenance --------------------------------
# The product version alone cannot tell two Candidates apart: every artifact
# name and the embedded build identity carry rc-<commit prefix>, and a Candidate
# that claims to be formal must come from a clean checkout.
function Resolve-SourceCommit {
    # ECQ-RS05 发布溯源：显式提交**只能确认**当前 HEAD，不能替换它。
    # 旧实现让 -SourceCommit 直接覆盖 git rev-parse HEAD，于是可以在一棵干净的
    # 新源码树上生成 rc-<旧提交> 的身份并声明 source_dirty=false —— 字段齐全、
    # 校验和自洽，却没有绑定真实来源。这里改为：显式值必须等于 HEAD，否则拒绝。
    param([string]$Explicit, [string]$Root)
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "未找到 git；候选构建必须能追溯到精确提交。"
    }
    $head = (& git -C $Root rev-parse HEAD 2>$null | Select-Object -First 1)
    if ($null -ne $head) { $head = ([string]$head).Trim().ToLowerInvariant() }
    if ([string]::IsNullOrWhiteSpace($head) -or $head -notmatch '^[0-9a-f]{40}$') {
        throw "无法确定当前提交（git rev-parse HEAD）；候选构建必须能追溯到精确提交。"
    }
    if ([string]::IsNullOrWhiteSpace($Explicit)) {
        return $head
    }
    $commit = ([string]$Explicit).Trim().ToLowerInvariant()
    if ($commit -notmatch '^[0-9a-f]{40}$') {
        throw "源提交必须是 40 位十六进制 SHA：$commit"
    }
    if ($commit -ne $head) {
        throw ("显式 -SourceCommit 与当前 git HEAD 不一致，拒绝构建：" +
               "显式=$commit，HEAD=$head。候选身份必须绑定被构建的实际提交；" +
               "若确实要构建另一个提交，请先 checkout 到该提交。")
    }
    return $head
}

function Test-SourceDirty {
    param([string]$Root)
    # Fail closed: a working tree whose state cannot be read must never be
    # reported as clean.
    $status = & git -C $Root status --porcelain 2>$null
    if ($LASTEXITCODE -ne 0) { throw "无法确定工作区状态（git status 失败）：$Root" }
    return (@($status | Where-Object { $_ -ne "" }).Count -gt 0)
}

$SourceCommit = Resolve-SourceCommit -Explicit $SourceCommit -Root $ProjectRoot
if (Test-SourceDirty -Root $ProjectRoot) {
    if (-not $AllowDirty) {
        throw "工作区存在未提交改动，拒绝正式候选构建（source_dirty 必须为 false）。请先提交或清理改动；仅本地实验可使用 -AllowDirty。"
    }
    Write-Warning "工作区存在未提交改动：本构建仅用于本地实验，不可作为正式候选交付。"
}
if ([string]::IsNullOrWhiteSpace($CandidateId)) {
    $CandidateId = (& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --source-commit $SourceCommit --print-candidate-id).Trim()
    if ($LASTEXITCODE -ne 0) { throw "无法由源提交推导候选标识。" }
}
else {
    $CandidateId = $CandidateId.Trim()
}
Write-Host "源提交：$SourceCommit"
Write-Host "候选标识：$CandidateId"

# --- version source of truth (never hard-coded) ------------------------------
$RequiredNameKeys = @("portable", "installer", "source", "standard_package", "template", "sha256sums",
    "payload_manifest", "build_info", "helper_ps1", "helper_cmd", "release_notes", "delivery_list")
$Version = (& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --print).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Version)) {
    throw "无法从 tools/release_version.py 取得产品版本。"
}
$NamesFromTool = ((& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --names `
            --source-commit $SourceCommit --candidate-id $CandidateId) -join "`n")
if ($LASTEXITCODE -ne 0) { throw "无法取得候选产物文件名。" }
$NamesJsonResolved = if ([string]::IsNullOrWhiteSpace($NamesJson)) { $NamesFromTool } else { $NamesJson }
$Names = $NamesJsonResolved | ConvertFrom-Json
$NamesTool = $NamesFromTool | ConvertFrom-Json
foreach ($Key in $RequiredNameKeys) {
    if (-not $Names.PSObject.Properties.Name.Contains($Key)) {
        throw "产物文件名清单缺少 $Key。"
    }
    # A caller-supplied name list that disagrees with this commit's identity
    # would silently ship files whose names do not match the ACTIVE marker.
    if ([string]$Names.$Key -ne [string]$NamesTool.$Key) {
        throw "调用方提供的产物文件名与本次候选身份不一致（$Key）：$($Names.$Key) != $($NamesTool.$Key)"
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

# ECQ-RS05 §11: the embedded build identity must exist in the payload BEFORE the
# payload manifest is generated, so the manifest covers and hashes it.  One
# build timestamp is shared with release-build-info.json and ACTIVE-CANDIDATE.json
# so the three documents cannot disagree.
$BuildTimeUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$IdentityArgs = @(
    "--names", $NamesFromTool,
    "--payload-dir", $PayloadDir,
    "--source-commit", $SourceCommit,
    "--candidate-id", $CandidateId,
    "--built-at", $BuildTimeUtc
)
if ($AllowDirty) { $IdentityArgs += "--allow-dirty" } else { $IdentityArgs += "--require-clean" }
& $PythonExe (Join-Path $ProjectRoot "tools\write_build_info.py") @IdentityArgs
if ($LASTEXITCODE -ne 0) { throw "内嵌构建标识写入失败（payload 不可追溯）。" }

# --- installer ---------------------------------------------------------------
# The installer ships the GB 29446 import template, and packaging\installer.iss
# reads it from dist\release.  It must therefore exist BEFORE ISCC runs, even
# when the Candidate is assembled into a different -OutputDir.  Generating it
# here (rather than only during assembly below) is what makes the build order
# correct; the tool is deterministic, so the later call is a cheap no-op.
& $PythonExe (Join-Path $ProjectRoot "tools\build_release_templates.py") `
    --output-dir (Join-Path $ProjectRoot "dist\release")
if ($LASTEXITCODE -ne 0) { throw "Excel 模板生成失败，停止安装程序构建。" }

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
Write-Host "安装程序候选后缀：-$CandidateId"
# The Candidate identity reaches the installer as an Inno preprocessor symbol,
# never through version.iss (which must stay commit-independent).
& $Iscc "/DMyAppCandidateSuffix=-$CandidateId" (Join-Path $ProjectRoot "packaging\installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 安装程序构建失败。" }
$Installer = Join-Path $ProjectRoot "dist\installer" $Names.installer
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw "未找到安装程序：$Installer"
}

# --- assemble the Candidate --------------------------------------------------
# §11: the Candidate directory is emptied first, so a previous build's payload
# can never be mixed into this one.  A locked file is a hard failure: silently
# skipping it would leave a directory that looks complete but is not.
$ProtectedTargets = @(
    $ProjectRoot,
    (Join-Path $ProjectRoot "dist"),
    (Join-Path $ProjectRoot "dist\UEBench"),
    (Join-Path $ProjectRoot "build")
)
if ($ProtectedTargets -contains $Release) {
    throw "拒绝清空受保护目录：$Release"
}
if (Test-Path -LiteralPath $Release) {
    Write-Host "清空候选目录（防止旧构建产物混入）：$Release"
    Get-ChildItem -LiteralPath $Release -Force | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop
    }
}
else {
    New-Item -ItemType Directory -Path $Release -Force | Out-Null
}

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

# 6) Build information (full provenance + unsigned-release declaration).
& $PythonExe (Join-Path $ProjectRoot "tools\write_build_info.py") `
    --names $NamesFromTool --output (Join-Path $Release $Names.build_info) `
    --payload-manifest (Join-Path $Release $Names.payload_manifest) `
    --source-commit $SourceCommit --candidate-id $CandidateId --built-at $BuildTimeUtc
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

# 8) §11 单一 ACTIVE Candidate：装配完成即写入 ACTIVE 标记，Artifact Gate 会校验它。
#    该文件不在 SHA256SUMS.txt 内：命名本次装配的文档不能同时是被它固定的文件。
#    若 Gate 未通过，标记会被删除，绝不允许一个失败的目录自称 ACTIVE。
#
#    只有干净检出才能声明 ACTIVE：-AllowDirty 的本地实验目录既不写 ACTIVE 标记，
#    也不运行 Artifact Gate（它必然因 source_dirty=true 失败），只是让开发者拿到
#    一份可检查的产物。正式构建（CI）从不传 -AllowDirty。
if ($AllowDirty) {
    Write-Warning "本地实验模式（-AllowDirty）：不写 ACTIVE-CANDIDATE.json，也不运行 Artifact Gate；$Release 不可作为正式候选交付。"
}
else {
    $ActiveMarker = Join-Path $Release "ACTIVE-CANDIDATE.json"
    & $PythonExe (Join-Path $ProjectRoot "tools\write_build_info.py") `
        --names $NamesFromTool --active-marker $ActiveMarker `
        --payload-manifest (Join-Path $Release $Names.payload_manifest) `
        --source-commit $SourceCommit --candidate-id $CandidateId --built-at $BuildTimeUtc
    if ($LASTEXITCODE -ne 0) { throw "ACTIVE 候选标记写入失败。" }

    # 9) The Artifact Gate, run against the directory we just produced.
    Write-Host "以 Candidate 目录运行 Artifact Gate：$Release"
    $PreviousArtifactDir = $env:UEBENCH_ARTIFACT_DIR
    $env:UEBENCH_ARTIFACT_DIR = $Release
    try {
        $GateBase = Join-Path $ProjectRoot ("work\pytest-artifact-gate-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        New-Item -ItemType Directory -Path $GateBase -Force | Out-Null
        & $PythonExe -m pytest (Join-Path $ProjectRoot "tests\test_release_artifacts.py") `
            -q -ra -p no:cacheprovider --basetemp $GateBase
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Artifact Gate 未通过，撤销 ACTIVE 标记：$ActiveMarker"
            if (Test-Path -LiteralPath $ActiveMarker) {
                Remove-Item -LiteralPath $ActiveMarker -Force
            }
            throw "Artifact Gate 未通过：$Release"
        }
    }
    finally {
        $env:UEBENCH_ARTIFACT_DIR = $PreviousArtifactDir
        if ($GateBase -and (Test-Path -LiteralPath $GateBase)) {
            Remove-Item -LiteralPath $GateBase -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Candidate 已生成并通过 Artifact Gate：$Release"
    Write-Host "ACTIVE 候选：$CandidateId（源提交 $SourceCommit）"
}

Get-ChildItem -LiteralPath $Release -File | Sort-Object Name |
    ForEach-Object { Write-Host ("  {0,12}  {1}" -f $_.Length, $_.Name) }
