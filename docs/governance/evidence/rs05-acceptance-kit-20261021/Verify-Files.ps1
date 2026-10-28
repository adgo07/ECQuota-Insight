# 只读取并核对本目录 manifest.json 中的三个交付文件；不运行安装器。
$ErrorActionPreference = 'Stop'

try {
    $manifestPath = Join-Path $PSScriptRoot 'manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.schema -ne 'ecquota.rs05.acceptance-kit.v1') {
        throw '清单 schema 不匹配。'
    }
    $files = @($manifest.files)
    if ($files.Count -ne 3) {
        throw "清单应包含 3 个资产，实际为 $($files.Count) 个。"
    }

    $assetRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'assets'))
    $prefix = $assetRoot.TrimEnd('\') + '\'
    $failed = $false
    foreach ($entry in $files) {
        $relative = [string]$entry.path
        if ([string]::IsNullOrWhiteSpace($relative) -or [IO.Path]::IsPathRooted($relative)) {
            throw "非法相对路径：$relative"
        }
        $fullPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ($relative -replace '/', '\')))
        if (-not $fullPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "资产路径越界：$relative"
        }
        if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
            Write-Output "FAIL 缺失：$relative"
            $failed = $true
            continue
        }
        $expectedSize = [long]$entry.size_bytes
        $expectedHash = ([string]$entry.sha256).ToLowerInvariant()
        if ($expectedHash -notmatch '^[0-9a-f]{64}$') {
            throw "清单哈希格式错误：$relative"
        }
        $actualSize = (Get-Item -LiteralPath $fullPath).Length
        $actualHash = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualSize -ne $expectedSize -or $actualHash -ne $expectedHash) {
            Write-Output "FAIL 大小或 SHA256 不符：$relative"
            $failed = $true
        }
        else {
            Write-Output "PASS $relative ($actualSize bytes)"
        }
    }
    if ($failed) { exit 1 }
    Write-Output '全部 3 个资产已通过大小和 SHA256 校验。'
    exit 0
}
catch {
    Write-Error "文件核验失败：$($_.Exception.Message)"
    exit 1
}
