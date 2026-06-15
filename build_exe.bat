@echo off
setlocal EnableDelayedExpansion
title HexPad v2 — Build EXE
color 0D

echo.
echo  ^+--------------------------------------------------^+
echo  ^|   HexPad v2  ^|  Build PyInstaller                 ^|
echo  ^+--------------------------------------------------^+
echo.

:: Verif Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERREUR] Python introuvable. Installe Python 3.10+
    pause & exit /b 1
)

:: Verif / install deps
echo  [1/4] Installation des dependances...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo  [ERREUR] pip install a echoue.
    pause & exit /b 1
)

:: Generation icone si absente
echo  [2/4] Preparation des assets...
if not exist assets mkdir assets
if not exist assets\icon.ico (
    python assets\make_icon.py
)

:: Clean precedent build
echo  [3/4] Nettoyage du build precedent...
if exist dist\HexPad.exe del /f /q dist\HexPad.exe
if exist build rmdir /s /q build

:: Build
echo  [4/4] Compilation PyInstaller...
pyinstaller hexpad.spec --noconfirm --clean

if %errorlevel% neq 0 (
    echo.
    echo  [ERREUR] Build echoue. Verifie la console ci-dessus.
    pause & exit /b 1
)

echo.
echo  +--------------------------------------------------+
echo  ^|  OK  ^|  dist\HexPad.exe pret a distribuer        ^|
echo  +--------------------------------------------------+
echo.
echo  Taille :
for %%F in (dist\HexPad.exe) do echo    %%~zF octets
echo.
set /p _open="  Ouvrir dist\ ? [O/n] "
if /i "!_open!"=="O" explorer dist\
pause
