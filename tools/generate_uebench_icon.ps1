param(
    [string]$OutputPath = (Join-Path $PSScriptRoot "..\packaging\uebench.ico")
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

function New-IconPng([int]$size) {
    $bitmap = New-Object System.Drawing.Bitmap($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.Color]::Transparent)

    $margin = [Math]::Max(1, [int]($size * 0.06))
    $radius = [Math]::Max(2, [int]($size * 0.20))
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $diameter = $radius * 2
    $width = $size - ($margin * 2)
    $height = $width
    $path.AddArc($margin, $margin, $diameter, $diameter, 180, 90)
    $path.AddArc($size - $margin - $diameter, $margin, $diameter, $diameter, 270, 90)
    $path.AddArc($size - $margin - $diameter, $size - $margin - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($margin, $size - $margin - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    $background = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(23, 54, 93))
    $graphics.FillPath($background, $path)

    $stroke = [Math]::Max(1, [int]($size * 0.075))
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::White, $stroke)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $arcBox = [int]($size * 0.27)
    $arcX = [int](($size - $arcBox) / 2)
    $arcY = [int]($size * 0.26)
    $graphics.DrawArc($pen, $arcX, $arcY, $arcBox, $arcBox, 205, 130)
    $centerX = [int]($size / 2)
    $centerY = [int]($size * 0.49)
    $graphics.DrawLine($pen, $centerX, $centerY, [int]($size * 0.70), [int]($size * 0.35))

    $accent = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(245, 166, 35))
    $dot = [Math]::Max(2, [int]($size * 0.13))
    $graphics.FillEllipse($accent, [int]($size * 0.68), [int]($size * 0.65), $dot, $dot)
    $graphics.Dispose()
    $background.Dispose()
    $accent.Dispose()
    $pen.Dispose()
    $path.Dispose()

    $stream = New-Object System.IO.MemoryStream
    $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
    $bytes = $stream.ToArray()
    $stream.Dispose()
    # Prefix with a comma so PowerShell keeps the byte array as one value
    # instead of enumerating it into an Object[] return value.
    return ,$bytes
}

$sizes = @(16, 24, 32, 48, 64, 128, 256)
$images = @{}
foreach ($size in $sizes) {
    $images[$size] = New-IconPng $size
}

$directory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$file = [System.IO.File]::Open($OutputPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
$writer = New-Object System.IO.BinaryWriter($file)
$writer.Write([uint16]0)
$writer.Write([uint16]1)
$writer.Write([uint16]$sizes.Count)
$offset = 6 + (16 * $sizes.Count)
foreach ($size in $sizes) {
    $data = $images[$size]
    $dimension = if ($size -eq 256) { [byte]0 } else { [byte]$size }
    $writer.Write($dimension)
    $writer.Write($dimension)
    $writer.Write([byte]0)
    $writer.Write([byte]0)
    $writer.Write([uint16]1)
    $writer.Write([uint16]32)
    $writer.Write([uint32]$data.Length)
    $writer.Write([uint32]$offset)
    $offset += $data.Length
}
foreach ($size in $sizes) {
    $writer.Write($images[$size])
}
$writer.Flush()
$writer.Dispose()
$file.Dispose()
Write-Host "已生成图标：$OutputPath"
