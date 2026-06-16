@echo off
chcp 65001 >nul
title HexPad GUI
cd /d "%~dp0"
call venv\Scripts\activate.bat
python gui.py
pause
