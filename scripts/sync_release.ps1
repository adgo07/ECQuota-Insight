param(
    [string]$PythonExe,
    [string]$ReleaseDir,
    [switch]$SkipPortableZip,
    [switch]$SkipSourceZip,
    [switch]$SkipTemplates,
    [switch]$SkipAudit,
    [string]$SourceCommit,
    [string]$CandidateId,
    [switch]$AllowDirty
)

# ECQ-RS05: assemble the Candidate delivery directory.  Every artifact name and
# the product version come from tools/release_version.py, which reads
# pyproject.toml.  Nothing here is version-hard-coded.
#
# §11 (single ACTIVE Candidate): this directory is EMPTIED before assembly, so a
# previous build's payload can never be mixed into the new one, and a successful
# assembly leaves an ACTIVE-CANDIDATE.json naming exactly what it holds.
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# ECQ-RS05 M2 §二 —— DEPRECATED：本脚本不再是正式发布路径。
#
#   scripts/build_candidate.ps1 是**唯一正式 Candidate 构建入口**（含 Artifact Gate）。
# 本脚本只保留为历史/内部组装工具，配合已弃用的 scripts/build_release.ps1 排查旧链路；
# 普通维护者不需要它。
Write-Warning "DEPRECATED: scripts/sync_release.ps1 不再是正式发布路径；唯一正式 Candidate 构建入口是 scripts/build_candidate.ps1。"

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

# --- ECQ-RS05 candidate identity / provenance --------------------------------
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
        throw "工作区存在未提交改动，拒绝正式候选装配（source_dirty 必须为 false）。请先提交或清理改动；仅本地实验可使用 -AllowDirty。"
    }
    Write-Warning "工作区存在未提交改动：本目录仅用于本地实验，不可作为正式候选交付。"
}
if ([string]::IsNullOrWhiteSpace($CandidateId)) {
    $CandidateId = (& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --source-commit $SourceCommit --print-candidate-id).Trim()
    if ($LASTEXITCODE -ne 0) { throw "无法由源提交推导候选标识。" }
}
else {
    $CandidateId = $CandidateId.Trim()
}

# Version consistency Gate.
& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --check
if ($LASTEXITCODE -ne 0) { throw "版本一致性校验失败，停止同步。" }

$Version = (& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --print).Trim()
$NamesJson = ((& $PythonExe (Join-Path $ProjectRoot "tools\release_version.py") --names `
            --source-commit $SourceCommit --candidate-id $CandidateId) -join "`n")
if ($LASTEXITCODE -ne 0) { throw "无法取得候选产物文件名。" }
$Names = $NamesJson | ConvertFrom-Json
Write-Host "产品版本：$Version"
Write-Host "源提交：$SourceCommit"
Write-Host "候选标识：$CandidateId"

# §11: the active Candidate directory is emptied BEFORE assembly.  A previous
# build's payload must never survive next to the new one, and a locked file is a
# hard failure -- silently continuing would leave a mixed directory that looks
# complete.
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

# 2) 内嵌构建标识：必须在 payload 清单之前写入 dist\UEBench，清单才会覆盖并哈希它。
#    与 release-build-info.json 共用同一个构建时间戳，两份文档不会互相矛盾。
$BuildTimeUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$IdentityArgs = @(
    "--names", $NamesJson,
    "--payload-dir", $PortableDir,
    "--source-commit", $SourceCommit,
    "--candidate-id", $CandidateId,
    "--built-at", $BuildTimeUtc
)
if ($AllowDirty) { $IdentityArgs += "--allow-dirty" } else { $IdentityArgs += "--require-clean" }
& $PythonExe (Join-Path $ProjectRoot "tools\write_build_info.py") @IdentityArgs
if ($LASTEXITCODE -ne 0) { throw "内嵌构建标识写入失败（payload 不可追溯）。" }

# 3) payload 同源清单：portable ZIP 与 installer 都来自同一次 dist\UEBench。
& $PythonExe (Join-Path $ProjectRoot "tools\build_payload_manifest.py") `
    --payload-dir $PortableDir --output (Join-Path $Release $Names.payload_manifest)
if ($LASTEXITCODE -ne 0) { throw "payload 清单生成失败。" }

# 4) 源码包。
if (-not $SkipSourceZip) {
    & $PythonExe (Join-Path $ProjectRoot "tools\build_source_zip.py") --output $SourceZip
    if ($LASTEXITCODE -ne 0) { throw "源码包生成失败。" }
}

# 5) 便携包（从同一次 dist\UEBench 压缩）。
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

# 7) 构建信息（完整溯源：候选标识、源提交、标准包身份、payload 树哈希、未签名声明）。
& $PythonExe (Join-Path $ProjectRoot "tools\write_build_info.py") `
    --names $NamesJson --output (Join-Path $Release $Names.build_info) `
    --payload-manifest (Join-Path $Release $Names.payload_manifest) `
    --source-commit $SourceCommit --candidate-id $CandidateId --built-at $BuildTimeUtc
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

# 10) §11 单一 ACTIVE Candidate：只有装配并审计成功之后才写入 ACTIVE 标记。
#     该文件不在 SHA256SUMS.txt 内：命名本次装配的文档不能同时是被它固定的文件。
#     只有干净检出才能声明 ACTIVE：-AllowDirty 的本地实验（source_dirty=true）不会
#     写标记，且 audit_release 本身也会拒绝脏构建（本地实验可配合 -SkipAudit）。
if ($AllowDirty) {
    Write-Warning "本地实验模式（-AllowDirty）：不写 ACTIVE-CANDIDATE.json；$Release 不可作为正式候选交付。"
}
else {
    $ActiveMarker = Join-Path $Release "ACTIVE-CANDIDATE.json"
    & $PythonExe (Join-Path $ProjectRoot "tools\write_build_info.py") `
        --names $NamesJson --active-marker $ActiveMarker `
        --payload-manifest (Join-Path $Release $Names.payload_manifest) `
        --source-commit $SourceCommit --candidate-id $CandidateId --built-at $BuildTimeUtc
    if ($LASTEXITCODE -ne 0) { throw "ACTIVE 候选标记写入失败。" }
    Write-Host "ACTIVE 候选：$CandidateId（源提交 $SourceCommit）"
}
Write-Host "交付目录已同步：$Release"
