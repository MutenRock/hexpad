@echo off
chcp 65001 >nul
title HexPad — Macro
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py --mode macro
pause
