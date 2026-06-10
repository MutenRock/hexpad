@echo off
:menu
cls
title HexPad - Cyber Controller
echo ================================
echo   HH  HH   EEEEE  XX  XX
echo   HH  HH   EE      XXXX
echo   HHHHHH   EEEE     XX
echo   HH  HH   EE      XXXX
echo   HH  HH   EEEEE  XX  XX
echo            HexPad v1.0.0
echo ================================
echo.
echo  [1] Gamepad   (programme 1)
echo  [2] WebSocket (programme 2)
echo  [3] Macros    (programme 3)
echo  [4] Debug     (programme 4)
echo  [5] Quitter
echo.
set /p c="Choix : "
if "%c%"=="1" (python main.py --program 1 & pause & goto menu)
if "%c%"=="2" (python main.py --program 2 & pause & goto menu)
if "%c%"=="3" (python main.py --program 3 & pause & goto menu)
if "%c%"=="4" (python main.py --mode debug & pause & goto menu)
if "%c%"=="5" exit
goto menu
