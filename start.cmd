@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo Plant Counter - Setup and Start
echo ==========================================
echo.

if not exist "app.py" (
    echo ERROR: app.py not found.
    goto :error
)

if not exist "templates\index.html" (
    echo ERROR: templates\index.html not found.
    goto :error
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/5] Creating Python 3.11 environment...

    py -3.11 -c "import struct; assert struct.calcsize('P') * 8 == 64" >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python 3.11 x64 or Python Launcher not found.
        echo Install Python 3.11 x64 with Python Launcher.
        goto :error
    )

    py -3.11 -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo [1/5] Using existing .venv environment.
)

set "PYTHON=%~dp0.venv\Scripts\python.exe"

echo.
echo [2/5] Updating pip...
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :error

echo.
echo [3/5] Installing PyTorch CPU...
"%PYTHON%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :error

echo.
echo [4/5] Installing application dependencies...
"%PYTHON%" -m pip install flask ultralytics opencv-python numpy openpyxl reportlab
if errorlevel 1 goto :error

if not exist "static" mkdir "static"
if not exist "static" goto :error

echo.
echo [5/5] Checking libraries...
"%PYTHON%" -c "import flask, cv2, numpy, sqlite3, torch; from ultralytics import YOLO; from openpyxl import Workbook; from reportlab.platypus import SimpleDocTemplate; print('PyTorch:', torch.__version__); print('All libraries loaded successfully.')"
if errorlevel 1 (
    echo.
    echo Check Microsoft Visual C++ Redistributable x64.
    echo https://aka.ms/vs/17/release/vc_redist.x64.exe
    goto :error
)

echo.
echo ==========================================
echo Starting application...
echo Open http://127.0.0.1:5000 in your browser.
echo Keep this window open.
echo Press Ctrl+C to stop.
echo ==========================================
echo.

"%PYTHON%" app.py
if errorlevel 1 goto :error

echo.
echo Application stopped.
pause
exit /b 0

:error
echo.
echo ERROR: Setup or application failed.
echo Copy the error message above.
pause
exit /b 1