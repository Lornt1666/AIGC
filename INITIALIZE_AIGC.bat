@echo off
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\initialize_aigc.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo AIGC initialization did not complete. Review the displayed receipt and error.
  pause
)
exit /b %EXIT_CODE%
