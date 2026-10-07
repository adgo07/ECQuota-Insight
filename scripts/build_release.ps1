param(
    [string]$PythonExe,
    [switch]$SkipTests,
    [switch]$SkipInstaller,
    [switch]$SkipDevelopmentManifestCheck,
    [string]$SourceCommit,
    [string]$CandidateId,
    [switch]$AllowDirty
)

# ECQ-RS05: the build must not depend on a repository-local .venv.
#   -PassThru style explicit selection: -PythonExe <path> wins.
# Otherwise fall back to the project venv (developer convenience), then to the
# Python launcher, then to whatever "python" resolves to.  CI passes an explicit
# interpreter from actions/setup-python.
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# ECQ-RS05 M2 §二 —— DEPRECATED：本脚本不再是正式发布路径。
#
#   scripts/build_candidate.ps1 是**唯一正式 Candidate 构建入口**，它自己完成
#   版本一致性 Gate、Development-manifest Gate、严格 literal full suite、
#   PyInstaller 载荷、打包后自检、溯源写入、SHA256SUMS、ACTIVE 标记与 Artifact Gate。
#
# 本脚本只保留为历史/内部组装工具（排查旧链路用）；普通维护者不需要它。
Write-Warning "DEPRECATED: scripts/build_release.ps1 不再是正式发布路径；唯一正式 Candidate 构建入口是 scripts/build_candidate.ps1。"

function Resolve-PythonExecutable {
    param([string]$Explicit, [string]$Root)

    if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
        if (-not (Test-Path -LiteralPath $Explicit -PathType Leaf)) {
            throw "指定的 Python 解释器不存在：$Explicit"
        }
        return (Resolve-Path -LiteralPath $Explicit).Path
    }
    # ``actions/setup-python`` exports pythonLocation and installs the pinned
    # dependencies into that interpreter.  Prefer it, then PATH "python", and
    # only then "py": on a GitHub runner "py" resolves to the newest installed
    # Python (for example 3.14), which lacks the requirements and fails with
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
& $PythonExe -c "import sys; print('Python', sys.version)"
if ($LASTEXITCODE -ne 0) { throw "Python 解释器不可用：$PythonExe" }

# --- ECQ-RS05 candidate identity / provenance --------------------------------
# The product version alone cannot tell two Candidates apart, so every artifact
# name and the embedded build identity carry rc-<commit prefix>.  A formal
# Candidate must come from a clean checkout: a dirty tree is refused unless the
# caller explicitly asks for a local experiment with -AllowDirty.
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
$NamesJson = ((& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --names `
            --source-commit $SourceCommit --candidate-id $CandidateId) -join "`n")
if ($LASTEXITCODE -ne 0) { throw "无法取得候选产物文件名。" }
Write-Host "源提交：$SourceCommit"
Write-Host "候选标识：$CandidateId"

# ECQ-RS05: refuse to build a release whose version artifacts have drifted from
# pyproject.toml.  This is the version consistency Gate.
& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --check
if ($LASTEXITCODE -ne 0) {
    throw "版本一致性校验失败，停止构建。请运行 tools/release_version.py --generate。"
}

if (-not $SkipDevelopmentManifestCheck) {
    # 发布前确认Git中的统一开发标准库索引仍与scope-63定义一致。
    & $PythonExe (Join-Path $ProjectRoot "tools\build_development_manifest.py") --check
    if ($LASTEXITCODE -ne 0) {
        throw "统一开发标准库索引校验失败，停止构建。"
    }
}

if (-not $SkipTests) {
    # 使用项目内临时目录，避免构建机系统 TEMP 权限异常。
    $TestBase = Join-Path $ProjectRoot ("work\pytest-release-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Path $TestBase -Force | Out-Null
    try {
        & $PythonExe -m pytest -q -p no:cacheprovider --basetemp $TestBase
        if ($LASTEXITCODE -ne 0) {
            throw "自动测试失败，停止构建。"
        }
    }
    finally {
        # 只清理本次创建的测试目录，不触碰已有 work 文件。
        if (Test-Path -LiteralPath $TestBase) {
            Remove-Item -LiteralPath $TestBase -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# 只清理本项目明确的 PyInstaller 输出，防止旧版 DLL 残留到新包。
# §11（单一 ACTIVE Candidate）：默认候选装配目录 dist\release 也必须清空。它一旦
# 重建过 payload 就是过期目录（其 payload-manifest 描述的是上一份 payload），留着
# 只会让验收者把旧产物当成新候选。文件被占用时硬失败，不静默跳过。
$PyInstallerBuild = Join-Path $ProjectRoot "build\uebench"
$PyInstallerDist = Join-Path $ProjectRoot "dist\UEBench"
$DefaultReleaseDir = Join-Path $ProjectRoot "dist\release"
foreach ($Target in @($PyInstallerBuild, $PyInstallerDist)) {
    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
}
if (Test-Path -LiteralPath $DefaultReleaseDir) {
    Write-Host "清空候选目录（防止旧构建产物混入）：$DefaultReleaseDir"
    Get-ChildItem -LiteralPath $DefaultReleaseDir -Force | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop
    }
}

& $PythonExe -m PyInstaller --noconfirm (Join-Path $ProjectRoot "uebench.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败。"
}

# ECQ-RS05 §11: the embedded build identity is written into the payload BEFORE
# tools/build_payload_manifest.py runs, so the payload manifest covers and
# hashes it.  It is deliberately NOT written into version.iss or any generated
# version file, which must stay commit-independent.
$PayloadDir = Join-Path $ProjectRoot "dist\UEBench"
if (-not (Test-Path -LiteralPath $PayloadDir -PathType Container)) {
    throw "PyInstaller 未产出 payload 目录：$PayloadDir"
}
$BuildTimeUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$IdentityArgs = @(
    "--names", $NamesJson,
    "--payload-dir", $PayloadDir,
    "--source-commit", $SourceCommit,
    "--candidate-id", $CandidateId,
    "--built-at", $BuildTimeUtc
)
if ($AllowDirty) { $IdentityArgs += "--allow-dirty" } else { $IdentityArgs += "--require-clean" }
& $PythonExe (Join-Path $ProjectRoot "tools\write_build_info.py") @IdentityArgs
if ($LASTEXITCODE -ne 0) { throw "内嵌构建标识写入失败（payload 不可追溯）。" }

if (-not $SkipInstaller) {
    # The installer ships the GB 29446 import template, so it must exist before
    # ISCC runs.  Generate it headlessly through the real application facade -
    # never by asking a human to open the GUI and save a workbook.
    & $PythonExe (Join-Path $ProjectRoot "tools\build_release_templates.py") `
        --output-dir (Join-Path $ProjectRoot "dist\release")
    if ($LASTEXITCODE -ne 0) {
        throw "Excel 模板生成失败，停止安装程序构建。"
    }

    $Iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
    if (-not $Iscc) {
        $Candidates = @(
            (Join-Path $ProjectRoot "work\InnoSetup\ISCC.exe"),
            "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            "C:\Program Files\Inno Setup 6\ISCC.exe"
        )
        $Iscc = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $Iscc) {
        throw "未找到Inno Setup 6编译器ISCC.exe"
    }
    # The Candidate identity reaches the installer through an Inno preprocessor
    # symbol -- never through version.iss, which stays version-only.  ISCC's /D
    # defines the value as a string, so /DMyAppCandidateSuffix=-rc-abcdef0 makes
    # {#MyAppCandidateSuffix} expand to -rc-abcdef0.
    Write-Host "安装程序候选后缀：-$CandidateId"
    & $Iscc "/DMyAppCandidateSuffix=-$CandidateId" (Join-Path $ProjectRoot "packaging\installer.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup 安装程序构建失败。"
    }
}
