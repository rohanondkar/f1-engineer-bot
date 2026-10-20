@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtualenv...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -U pip
  ".venv\Scripts\python.exe" -m pip install -e .
)

REM Keep src on path so renames / stale editable installs still work
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM Refresh editable install if package entrypoint is broken (e.g. after folder rename)
".venv\Scripts\python.exe" -c "import f1_engineer.__main__" 1>nul 2>nul
if errorlevel 1 (
  echo Refreshing package install...
  ".venv\Scripts\python.exe" -m pip install -e . -q
)

".venv\Scripts\python.exe" -m f1_engineer %*
