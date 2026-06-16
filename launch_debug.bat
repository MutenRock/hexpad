@echo off
chcp 65001 >nul
title HexPad — Debug
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py --mode debug
pause
