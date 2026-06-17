@echo off
chcp 65001 >nul
title HexPad Launcher
cd /d "%~dp0"

IF EXIST venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python launcher.py
if errorlevel 1 (
    echo.
    echo [HexPad] Erreur au lancement. Appuie sur une touche pour fermer.
    pause
)
