# Construit dist\SyncAusha-Setup.exe : dependances, tests, PyInstaller, Inno Setup.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { python -m venv .venv }
$python = ".venv\Scripts\python.exe"
& $python -m pip install --quiet --upgrade pip
& $python -m pip install --quiet -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Installation des dependances impossible" }

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Des tests echouent : construction annulee" }

& $python -m PyInstaller --noconfirm --clean --windowed --name SyncAusha `
    --icon syncausha\assets\icon.ico `
    --add-data "syncausha\assets;syncausha\assets" `
    run_syncausha.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a echoue" }

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 introuvable. Installez-le : winget install -e --id JRSoftware.InnoSetup" }

& $iscc installer\syncausha.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup a echoue" }
Write-Host "OK : dist\SyncAusha-Setup.exe"
