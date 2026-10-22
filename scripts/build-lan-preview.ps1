param([string]$Label = ('v1.2.1-lan-preview-' + (Get-Date -Format 'yyyyMMdd-HHmmss')))
$ErrorActionPreference = 'Stop'
if ($Label -notmatch '^[a-zA-Z0-9.-]+$') { throw 'Invalid local preview label' }
$root = Split-Path $PSScriptRoot -Parent
$release = Join-Path $root "releases\$Label"
if (Test-Path -LiteralPath $release) { throw 'Preview already exists; use a new label.' }
$buildRoot = Join-Path $root "local-data\windows-build-$Label"
if (Test-Path -LiteralPath $buildRoot) { throw 'Build directory already exists; use a new label.' }
New-Item -ItemType Directory -Path $buildRoot | Out-Null
$previousPath = $env:PATH
Push-Location $root
try {
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Vue build failed' }
    $env:PATH = "$root\.venv\Scripts;$env:SystemRoot\System32;$env:SystemRoot"
    & "$root\.venv\Scripts\python.exe" -m PyInstaller --additional-hooks-dir "$root\scripts\pyinstaller-hooks" --clean --onedir --windowed --name XY-Studio --distpath "$buildRoot\dist" --workpath "$buildRoot\work" --specpath $buildRoot --icon "$root\studio\assets\xy-studio.ico" --add-data "$root\studio\assets;studio/assets" --add-data "$root\studio\skills;studio/skills" --add-data "$root\frontend\dist;frontend/dist" --hidden-import keyring.backends.Windows --hidden-import PySide6.QtWebChannel --hidden-import PySide6.QtWebEngineCore --hidden-import PySide6.QtWebEngineWidgets --exclude-module PySide6.QtPdf main.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
    New-Item -ItemType Directory -Path $release | Out-Null
    Copy-Item -LiteralPath "$buildRoot\dist\XY-Studio" -Destination $release -Recurse
    Copy-Item -LiteralPath "$root\docs\ANDROID-NATIVE.md" -Destination $release
    Write-Output "Local preview: $release\XY-Studio\XY-Studio.exe"
} finally { $env:PATH = $previousPath; Pop-Location }
