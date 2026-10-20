@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo === F1 Engineer Bot - Windows EXE build ===
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtualenv...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv. Install Python 3.11+ and retry.
    exit /b 1
  )
)

set "PY=.venv\Scripts\python.exe"

echo Installing / refreshing app + PyInstaller...
"%PY%" -m pip install -U pip
"%PY%" -m pip install -e .
"%PY%" -m pip install "pyinstaller>=6.0"

echo.
echo Building F1EngineerBot.exe (windowed onedir - this can take several minutes)...
"%PY%" -m PyInstaller --noconfirm --clean f1_engineer.spec
if errorlevel 1 (
  echo Build FAILED.
  exit /b 1
)

set "OUT=dist\F1EngineerBot"
if not exist "%OUT%" (
  echo Expected output folder missing: %OUT%
  exit /b 1
)

echo Seeding .env / voices / data beside the exe...
if not exist "%OUT%\.env" (
  if exist ".env" (
    copy /Y ".env" "%OUT%\.env" >nul
  ) else if exist ".env.example" (
    copy /Y ".env.example" "%OUT%\.env" >nul
  )
)

if not exist "%OUT%\voices" (
  if exist "voices" (
    xcopy /E /I /Y "voices" "%OUT%\voices" >nul
  ) else (
    mkdir "%OUT%\voices"
    mkdir "%OUT%\voices\custom"
  )
)

if not exist "%OUT%\data" mkdir "%OUT%\data"

echo Creating Desktop shortcut...
"%PY%" packaging\make_shortcut.py
if errorlevel 1 (
  echo Shortcut creation failed - you can still double-click:
  echo   %CD%\%OUT%\F1EngineerBot.exe
)

echo.
echo DONE.
echo Double-click:  %CD%\%OUT%\F1EngineerBot.exe
echo Or use the Desktop shortcut: F1 Engineer Bot
echo Edit API keys in:  %CD%\%OUT%\.env
echo.
pause
