@echo off
chcp 65001 >nul
title HexPad — Gamepad
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py --mode gamepad
pause
