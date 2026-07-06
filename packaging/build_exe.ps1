param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$srcRoot = Join-Path $repoRoot "src"
$distRoot = Join-Path $repoRoot "dist"
$buildRoot = Join-Path $repoRoot "build"
$basePortableName = "JuliangRPA-portable"
$portableName = $basePortableName
if (-not [string]::IsNullOrWhiteSpace($Version)) {
    $safeVersion = $Version.Trim() -replace '[\\/:*?"<>|]', '-'
    $portableName = "{0}-{1}" -f $basePortableName, $safeVersion
}
$portableDir = Join-Path $distRoot $portableName
$exeName = "JuliangRPA"

if (Test-Path $portableDir) {
    $oldPortableDir = Join-Path $distRoot ("{0}.old-{1}" -f $portableName, (Get-Date -Format "yyyyMMddHHmmss"))
    try {
        Move-Item -LiteralPath $portableDir -Destination $oldPortableDir -Force
        Write-Host "Existing portable package moved to: $oldPortableDir"
    }
    catch {
        $portableDir = Join-Path $distRoot ("{0}-{1}" -f $portableName, (Get-Date -Format "yyyyMMddHHmmss"))
        Write-Host "Existing portable package is in use. Creating new package: $portableDir"
    }
}

$env:PYTHONPATH = $srcRoot

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $exeName `
    --paths $srcRoot `
    --collect-all playwright `
    --collect-submodules juliang_rpa `
    (Join-Path $srcRoot "juliang_rpa\gui_entry.py")

New-Item -ItemType Directory -Force $portableDir | Out-Null
Copy-Item (Join-Path $distRoot "$exeName\*") $portableDir -Recurse -Force

Copy-Item (Join-Path $repoRoot "config") (Join-Path $portableDir "config") -Recurse -Force
New-Item -ItemType Directory -Force (Join-Path $portableDir ".auth") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $portableDir "logs") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $portableDir "recordings") | Out-Null

$playwrightRoot = Join-Path $env:LOCALAPPDATA "ms-playwright"
if (-not (Test-Path $playwrightRoot)) {
    throw "Playwright browser directory not found: $playwrightRoot. Run: python -m playwright install chromium"
}

$latestChromium = Get-ChildItem $playwrightRoot -Directory |
    Where-Object { $_.Name -like "chromium-*" } |
    Sort-Object Name |
    Select-Object -Last 1

$browserDirs = @()
if ($latestChromium) {
    $browserDirs += $latestChromium
}
$browserDirs += Get-ChildItem $playwrightRoot -Directory |
    Where-Object { $_.Name -like "ffmpeg-*" -or $_.Name -like "winldd-*" } |
    Sort-Object Name

if (-not $browserDirs) {
    throw "No Chromium directory found in Playwright browser directory. Run: python -m playwright install chromium"
}

$bundledRoot = Join-Path $portableDir "ms-playwright"
New-Item -ItemType Directory -Force $bundledRoot | Out-Null
foreach ($dir in $browserDirs) {
    Copy-Item $dir.FullName (Join-Path $bundledRoot $dir.Name) -Recurse -Force
}

$readme = @"
Juliang Ad RPA Portable

Version: $($Version.Trim())

Usage:
1. Double click JuliangRPA.exe.
2. On first use, open the login page, finish login, then save the login state.
3. The GUI can prefer local Chrome. If local Chrome is unavailable, it falls back to bundled Chromium in ms-playwright.
4. Presets are saved in config/ad_presets.yaml, login state in .auth, logs/screenshots in logs.

Move/copy this whole folder. Do not copy only the exe.
"@
$readme | Set-Content -Encoding UTF8 (Join-Path $portableDir "README.txt")
if (-not [string]::IsNullOrWhiteSpace($Version)) {
    $Version.Trim() | Set-Content -Encoding UTF8 (Join-Path $portableDir "VERSION.txt")
}

Write-Host "Portable package created: $portableDir"
