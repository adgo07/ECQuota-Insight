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
    & $PythonExe -m pytest
}
& $PythonExe -m PyInstaller --noconfirm (Join-Path $ProjectRoot "uebench.spec")
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
}
