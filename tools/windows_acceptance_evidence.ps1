param(
    [Parameter(Mandatory = $true)][string]$ArtifactDir,
    [string]$OutputDir,
    [string]$SelfCheckExe,
    [string]$DataDir,
    [switch]$SkipLaunch,
    # A human operator sets this ONLY after actually dragging the window between
    # two monitors with different DPI and observing correct behaviour.  This tool
    # never infers that result from the display count.
    [switch]$CrossMonitorDragVerified,
    [string]$CrossMonitorDragNote
)

# ECQ-RS05 §15: record the real Windows acceptance environment.
#
# This tool only *records facts*.  It does not invent a PASS.  Anything it cannot
# establish on this machine (for example a Windows 11 run, or dragging a window
# between two monitors) is written out as BLOCKED with the concrete reason, so
# the acceptance record stays honest.
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path (Resolve-Path $ArtifactDir).Path "windows-acceptance"
}
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$findings = [System.Collections.Generic.List[object]]::new()
function Add-Finding {
    param([string]$Check, [string]$Status, [string]$Detail)
    $findings.Add([pscustomobject]@{ check = $Check; status = $Status; detail = $Detail })
}

# ---- environment -----------------------------------------------------------
$os = Get-CimInstance Win32_OperatingSystem
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$screens = @()
try {
    Add-Type -AssemblyName System.Windows.Forms
    $screens = [System.Windows.Forms.Screen]::AllScreens | ForEach-Object {
        [pscustomobject]@{
            device  = $_.DeviceName
            bounds  = "$($_.Bounds.Width)x$($_.Bounds.Height)"
            primary = $_.Primary
        }
    }
}
catch {
    $screens = @()
}

$dpiRegistry = Get-ItemProperty -Path "HKCU:\Control Panel\Desktop" -Name LogPixels -ErrorAction SilentlyContinue
$environment = [ordered]@{
    os_caption      = $os.Caption
    os_version      = $os.Version
    os_build        = $os.BuildNumber
    os_arch         = $os.OSArchitecture
    is_windows_10   = ($os.BuildNumber -lt 22000)
    is_windows_11   = ($os.BuildNumber -ge 22000)
    locale          = (Get-Culture).Name
    ui_locale       = (Get-UICulture).Name
    system_locale   = $os.Locale
    account_name    = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    is_administrator = $isAdmin
    account_type    = if ($isAdmin) { "administrator" } else { "standard" }
    powershell      = $PSVersionTable.PSVersion.ToString()
    screen_count    = $screens.Count
    screens         = $screens
    log_pixels      = if ($dpiRegistry) { $dpiRegistry.LogPixels } else { $null }
    session_name    = $env:SESSIONNAME
    timestamp_utc   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

# ---- artifacts under test --------------------------------------------------
$artifactDirResolved = (Resolve-Path $ArtifactDir).Path
$artifactFiles = @()
foreach ($file in Get-ChildItem -LiteralPath $artifactDirResolved -File -ErrorAction SilentlyContinue) {
    if ($file.Extension -in @(".zip", ".exe")) {
        $artifactFiles += [pscustomobject]@{
            name   = $file.Name
            size   = $file.Length
            sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
}

# ---- offline state ---------------------------------------------------------
$offline = $null
try {
    $probe = Test-Connection -ComputerName "8.8.8.8" -Count 1 -Quiet -ErrorAction SilentlyContinue
    $offline = -not $probe
}
catch {
    $offline = $null
}

if ($environment.is_windows_11) {
    Add-Finding -Check "Windows 11 实机" -Status "PASS" -Detail "Build $($environment.os_build)"
}
else {
    Add-Finding -Check "Windows 11 实机" -Status "BLOCKED" `
        -Detail "本机为 Windows 10 Build $($environment.os_build)，无 Windows 11 环境可用；不伪造 PASS。"
}
Add-Finding -Check "Windows 10 实机" -Status $(if ($environment.is_windows_10) { "PASS" } else { "BLOCKED" }) `
    -Detail "$($environment.os_caption) Build $($environment.os_build)"

# ECQ-RS05: detecting a second display is NOT evidence that the cross-monitor
# drag test passed.  Only a human who actually performed the drag (and observed
# the window re-scale correctly on both monitors) may attest to it, via
# -CrossMonitorDragVerified.  Without that attestation this tool reports
# PENDING-MANUAL even when two monitors are present, and BLOCKED when the
# hardware cannot support the test at all.
if ($CrossMonitorDragVerified) {
    Add-Finding -Check "多显示器拖动窗口" -Status "PASS" `
        -Detail ("操作者实测声明（$($environment.screen_count) 个显示器）：" +
                 $(if ([string]::IsNullOrWhiteSpace($CrossMonitorDragNote)) { '未附说明' } else { $CrossMonitorDragNote }))
}
elseif ($environment.screen_count -ge 2) {
    Add-Finding -Check "多显示器拖动窗口" -Status "PENDING-MANUAL" `
        -Detail ("检测到 $($environment.screen_count) 个显示器，但拖动实测尚未执行/记录；" +
                 "本工具不因显示器数量判定通过。实测后请用 -CrossMonitorDragVerified -CrossMonitorDragNote 重新运行。")
}
else {
    Add-Finding -Check "多显示器拖动窗口" -Status "BLOCKED" `
        -Detail "本机仅 $($environment.screen_count) 个显示器，无法进行不同 DPI 显示器之间拖动窗口的实测。"
}
Add-Finding -Check "DPI 100/125/150/175/200 实机实测" -Status "BLOCKED" `
    -Detail "单显示器环境无法逐一实测 5 档 DPI 并跨屏拖动；需在具备多显示器与可调缩放的验收机上执行。当前 LogPixels=$($environment.log_pixels)"

if ($environment.account_type -eq "standard") {
    Add-Finding -Check "标准（非管理员）账户" -Status "PASS" -Detail $environment.account_name
}
else {
    Add-Finding -Check "标准（非管理员）账户" -Status "BLOCKED" -Detail "当前为管理员账户"
}

if ($offline -eq $true) {
    Add-Finding -Check "离线运行" -Status "PASS" -Detail "未连通外部网络"
}
elseif ($offline -eq $false) {
    Add-Finding -Check "离线运行" -Status "OBSERVED-ONLINE" -Detail "当前可连通外网；离线断言需在断网环境复测"
}
else {
    Add-Finding -Check "离线运行" -Status "BLOCKED" -Detail "无法判定连通性"
}

# ---- package self-check ----------------------------------------------------
if (-not [string]::IsNullOrWhiteSpace($SelfCheckExe) -and (Test-Path -LiteralPath $SelfCheckExe -PathType Leaf)) {
    if ([string]::IsNullOrWhiteSpace($DataDir)) {
        $DataDir = Join-Path $OutputDir "self-check-data"
    }
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    $reportPath = Join-Path $OutputDir "self-check.json"
    & $SelfCheckExe --self-check --output $reportPath --data-dir $DataDir
    $code = $LASTEXITCODE
    Add-Finding -Check "打包后可执行自检" -Status $(if ($code -eq 0) { "PASS" } else { "FAIL" }) `
        -Detail "exit=$code report=$reportPath"
}
else {
    Add-Finding -Check "打包后可执行自检" -Status "SKIP" -Detail "未提供 -SelfCheckExe，未执行"
}

$record = [ordered]@{
    schema          = "ecq.windows-acceptance.v1"
    artifact_dir    = $artifactDirResolved
    artifacts       = $artifactFiles
    environment     = $environment
    offline         = $offline
    findings        = $findings
    generated_at    = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

$jsonPath = Join-Path $OutputDir "windows-acceptance.json"
$record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding UTF8

Write-Host "== 环境 =="
$environment.GetEnumerator() | Where-Object { $_.Key -ne "screens" } | ForEach-Object { Write-Host ("  {0,-18} {1}" -f $_.Key, $_.Value) }
Write-Host "== 结论 =="
$findings | ForEach-Object { Write-Host ("  [{0,-15}] {1} - {2}" -f $_.status, $_.check, $_.detail) }
Write-Host ""
Write-Host "记录已保存：$jsonPath"
