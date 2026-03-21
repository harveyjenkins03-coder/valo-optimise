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
git --version >nul 2>&1
if %errorlevel% == 0 (
    echo       Git already installed. Skipping.
) else (
    winget install --id Git.Git -e --source winget --silent
    echo       Git installed.
)

:: ── Install Python ──
echo.
echo [2/4] Installing Python 3.11...
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo       Python already installed. Skipping.
) else (
    winget install --id Python.Python.3.11 -e --source winget --silent
    echo       Python installed.
)

:: ── Refresh PATH ──
call refreshenv >nul 2>&1

:: ── Clone repo ──
echo.
echo [3/4] Cloning Valo Optimise repo...
set DEST=%USERPROFILE%\Desktop\Valo Optimise
if exist "%DEST%" (
    echo       Folder already exists, pulling latest...
    cd /d "%DEST%"
    git pull
) else (
    git clone https://github.com/harveyjenkins03-coder/valo-optimise.git "%DEST%"
    cd /d "%DEST%"
)

:: ── Install Python dependencies ──
echo.
echo [4/4] Installing Python dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install customtkinter --quiet
echo       Dependencies installed.

:: ── Done ──
echo.
echo  ============================================
echo   Setup complete!
echo  ============================================
echo.
echo  Next steps:
echo  1. Open the "Valo Optimise" folder on your Desktop in VS Code
echo  2. Install recommended extensions when prompted (Live Share etc.)
echo  3. Ask Harvey to send you a Live Share link
echo.
echo  To run the app:  python main.py
echo.
pause
