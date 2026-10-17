@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
echo LegacyVault eKYC - first-time setup for Windows x64
echo Read HUONG_DAN_CHAY.txt if Python 3.12 is not installed.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
  echo.
  echo SETUP FAILED. Keep this window open and read the error above.
  echo See HUONG_DAN_CHAY.txt for troubleshooting.
  pause
  exit /b 1
)
echo.
echo SETUP COMPLETE. Double-click start.cmd to run the prototype.
pause
