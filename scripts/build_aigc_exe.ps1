param(
    [switch]$InstallPyInstaller
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "Optional AIGC executable build scaffold"
Write-Host "Supported default mode remains BAT/PowerShell launcher plus Python virtual environment."

if ($InstallPyInstaller) {
    python -m pip install pyinstaller
}

$pyinstaller = python -c "import importlib.util; print('present' if importlib.util.find_spec('PyInstaller') else 'missing')"
if ($pyinstaller -ne "present") {
    Write-Host "PyInstaller is not installed. Rerun with -InstallPyInstaller only after reviewing docs/AIGC_EXE_BUILD_NOTES.md."
    exit 0
}

Write-Host "Building experimental launcher executable..."
python -m PyInstaller --onefile --name AIGC-Program src\program_health_cli.py
Write-Host "Experimental executable output is under dist\. This does not replace the supported launcher workflow."
