$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if ($env:AIGC_SKIP_DEPENDENCY_INSTALL -ne "1") {
    python -m pip install -r requirements.txt
}

python -m streamlit run .\src\dashboard\operator_cockpit_app.py
