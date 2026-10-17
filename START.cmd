@echo off
set PYTHONUTF8=1
cd /d "%~dp0"
if not defined EKYC_BASE_DIR set "EKYC_BASE_DIR=%~dp0"
if not exist "%EKYC_BASE_DIR%\.venv\Scripts\python.exe" (
  echo Khong tim thay moi truong Python. Chay setup.cmd; xem README.md.
  pause
  exit /b 1
)
echo LegacyVault eKYC v2.2: http://127.0.0.1:8879
echo Dung bang Ctrl+C. Anh chi duoc xu ly trong bo nho.
"%EKYC_BASE_DIR%\.venv\Scripts\python.exe" -B runtime.py
pause
