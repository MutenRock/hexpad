@echo off
chcp 65001 >nul
title HexPad
cd /d "%~dp0"

IF NOT EXIST venv\Scripts\activate.bat (
    echo [HexPad] Environnement introuvable. Lance install.bat d'abord.
    pause & exit /b 1
)

call venv\Scripts\activate.bat
python gui.py
if errorlevel 1 (
    echo.
    echo [HexPad] Erreur au lancement. Appuie sur une touche pour fermer.
    pause
)
