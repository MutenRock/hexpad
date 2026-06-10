@echo off
title HexPad — Build EXE
echo.
echo  [BUILD] Generation du .exe HexPad...
echo.

pip install pyinstaller --quiet

pyinstaller --onefile --windowed --icon=assets/icon.ico --name HexPad gui.py

if %errorlevel% neq 0 (
    echo.
    echo  [ERREUR] Build echoue. Verifie les dependances.
    pause
    exit /b 1
)

echo.
echo  [OK] HexPad.exe genere dans dist/
echo  Tu peux le distribuer sans Python installe.
pause
