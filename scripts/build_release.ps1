param(
    [string]$PythonExe,
    [switch]$SkipTests,
    [switch]$SkipInstaller,
    [switch]$SkipDevelopmentManifestCheck
)

# ECQ-RS05: the build must not depend on a repository-local .venv.
#   -PassThru style explicit selection: -PythonExe <path> wins.
# Otherwise fall back to the project venv (developer convenience), then to the
# Python launcher, then to whatever "python" resolves to.  CI passes an explicit
# interpreter from actions/setup-python.
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
$PyInstallerBuild = Join-Path $ProjectRoot "build\uebench"
$PyInstallerDist = Join-Path $ProjectRoot "dist\UEBench"
foreach ($Target in @($PyInstallerBuild, $PyInstallerDist)) {
    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
}

& $PythonExe -m PyInstaller --noconfirm (Join-Path $ProjectRoot "uebench.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 构建失败。"
}

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
    & $Iscc (Join-Path $ProjectRoot "packaging\installer.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup 安装程序构建失败。"
    }
}
