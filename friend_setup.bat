@echo off
title Valo Optimise - Friend Setup
color 0A
echo.
echo  ============================================
echo   VALO OPTIMISE - Developer Setup
echo  ============================================
echo.
echo  This will install: Git, Python, dependencies
echo  and clone the project automatically.
echo.
pause

:: ── Check for winget ──
winget --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] winget not found. Please update Windows or install App Installer from the Microsoft Store.
    pause
    exit /b 1
)

:: ── Install Git ──
echo.
echo [1/4] Installing Git...
winget install --id Git.Git -e --source winget --silent --accept-package-agreements --accept-source-agreements
echo       Git installed.

:: ── Install Python ──
echo.
echo [2/4] Installing Python 3.11...
winget install --id Python.Python.3.11 -e --source winget --silent --accept-package-agreements --accept-source-agreements
echo       Python installed.

:: ── Find Git path and add to PATH ──
set "GIT_PATH=C:\Program Files\Git\cmd"
if exist "%GIT_PATH%\git.exe" (
    set "PATH=%GIT_PATH%;%PATH%"
) else if exist "%LOCALAPPDATA%\Programs\Git\cmd\git.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\Git\cmd;%PATH%"
)

:: ── Find Python path and add to PATH ──
for /d %%i in ("%LOCALAPPDATA%\Programs\Python\Python3*") do set "PY_PATH=%%i"
if defined PY_PATH (
    set "PATH=%PY_PATH%;%PY_PATH%\Scripts;%PATH%"
) else (
    for /d %%i in ("C:\Python3*") do set "PY_PATH=%%i"
    if defined PY_PATH set "PATH=%PY_PATH%;%PY_PATH%\Scripts;%PATH%"
)

:: ── Clone repo ──
echo.
echo [3/4] Cloning Valo Optimise repo...
set "DEST=%USERPROFILE%\Desktop\Valo Optimise"
if exist "%DEST%\" (
    echo       Folder already exists, pulling latest...
    cd /d "%DEST%"
    "%GIT_PATH%\git.exe" pull
) else (
    "%GIT_PATH%\git.exe" clone https://github.com/harveyjenkins03-coder/valo-optimise.git "%DEST%"
    cd /d "%DEST%"
)

:: ── Install Python dependencies ──
echo.
echo [4/4] Installing Python dependencies...
"%PY_PATH%\python.exe" -m pip install --upgrade pip --quiet
"%PY_PATH%\python.exe" -m pip install customtkinter --quiet
echo       Dependencies installed.

:: ── Done ──
echo.
echo  ============================================
echo   Setup complete!
echo  ============================================
echo.
echo  Next steps:
echo  1. Open "Valo Optimise" folder on your Desktop in VS Code
echo  2. Install recommended extensions when prompted (Live Share etc.)
echo  3. Ask Harvey to send you a Live Share link
echo.
echo  To run the app: open a NEW terminal then type  python main.py
echo.
pause
