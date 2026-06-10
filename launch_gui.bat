@echo off
title HexPad GUI
python gui.py
if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] Verifie que Python et les dependances sont installes.
    echo Lance install.bat si besoin.
    pause
)
