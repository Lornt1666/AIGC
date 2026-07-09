# AIGC EXE Build Notes

## Current Supported Mode

The supported local program mode is:

```text
BAT/PowerShell launcher + Python virtual environment + local Streamlit cockpit
```

This is preferred because it is transparent, easy to debug, and does not hide Python/runtime errors.

## Experimental EXE Scaffold

An optional scaffold exists:

```powershell
.\scripts\build_aigc_exe.ps1
```

To install PyInstaller and attempt an experimental build:

```powershell
.\scripts\build_aigc_exe.ps1 -InstallPyInstaller
```

## Important Boundary

Do not claim AIGC has a production EXE until the packaged executable is tested on a clean Windows machine.

The executable scaffold is not a replacement for:

- `RUN_AIGC_PROGRAM.bat`
- `scripts/run_aigc_program.ps1`
- `scripts/setup_aigc_local.ps1`

## Recommended Release Path

1. Keep launcher workflow as the official supported path.
2. Validate local program with Python.
3. Test PyInstaller separately.
4. Only document EXE as supported after clean-machine testing.

## Safety Boundary

Executable packaging must not add:

- external submission;
- credential use;
- secret retrieval;
- production deployment;
- self-approval;
- platform-rule bypass.
