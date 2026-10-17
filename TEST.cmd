@echo off
set PYTHONUTF8=1
cd /d "%~dp0"
if not defined EKYC_BASE_DIR set "EKYC_BASE_DIR=%~dp0"
"%EKYC_BASE_DIR%\.venv\Scripts\python.exe" -B -X utf8 test_face_detection.py
if errorlevel 1 goto end
"%EKYC_BASE_DIR%\.venv\Scripts\python.exe" -B -X utf8 test_regressions.py
if errorlevel 1 goto end
"%EKYC_BASE_DIR%\.venv\Scripts\python.exe" -B -X utf8 test_document_side.py
if errorlevel 1 goto end
"%EKYC_BASE_DIR%\.venv\Scripts\python.exe" -B -X utf8 test_face_reference.py
if errorlevel 1 goto end
where node >nul 2>nul
if errorlevel 1 goto skip_node
node test_ui.cjs
if errorlevel 1 goto end
:skip_node
"%EKYC_BASE_DIR%\.venv\Scripts\python.exe" -B -X utf8 test_face_detection_real_models.py
if errorlevel 1 goto end
"%EKYC_BASE_DIR%\.venv\Scripts\python.exe" -B -X utf8 test_locked_face_real_models.py
if errorlevel 1 goto end
"%EKYC_BASE_DIR%\.venv\Scripts\python.exe" -B -X utf8 test_side_real_models.py
if errorlevel 1 goto end
"%EKYC_BASE_DIR%\.venv\Scripts\python.exe" -B -X utf8 test_supplied_images.py
echo Xong. Cac bo can anh ca nhan tu bo qua neu chua dat EKYC_TEST_PHOTOS. Neu da dat, ket qua doi chieu anh nam trong TEST_RESULTS.json.
:end
pause
