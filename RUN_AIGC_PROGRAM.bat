@echo off
setlocal
cd /d "%~dp0"

if "%AIGC_SAFE_MODE%"=="" set AIGC_SAFE_MODE=1
if "%AIGC_PROGRAM_PORT%"=="" set AIGC_PROGRAM_PORT=8501

echo AIGC local program launcher
echo Safe mode: %AIGC_SAFE_MODE%
echo Port: %AIGC_PROGRAM_PORT%
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer, then run scripts\setup_aigc_local.ps1.
  pause
  exit /b 1
)

if "%AIGC_INSTALL_DEPENDENCIES%"=="1" (
  echo Installing dependencies because AIGC_INSTALL_DEPENDENCIES=1
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
  )
)

echo Running local health check...
python .\src\aigc.py health --write
if errorlevel 1 (
  echo Health check failed. Review the output above before launching.
  pause
  exit /b 1
)

echo Launching AIGC Operator Cockpit...
python -m streamlit run .\src\dashboard\operator_cockpit_app.py --server.port %AIGC_PROGRAM_PORT%
if errorlevel 1 (
  echo AIGC Operator Cockpit failed to launch. Try: set AIGC_INSTALL_DEPENDENCIES=1 then rerun this file.
  pause
  exit /b 1
)

pause
