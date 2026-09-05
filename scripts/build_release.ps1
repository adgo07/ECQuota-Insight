param(
    [switch]$SkipTests,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "未找到项目虚拟环境：$PythonExe"
}

if (-not $SkipTests) {
    # 使用项目内临时目录，避免构建机系统 TEMP 权限异常。
    $TestBase = Join-Path $ProjectRoot ("work\pytest-release-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
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
