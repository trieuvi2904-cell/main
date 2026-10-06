@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
py -3.12 --version >nul 2>&1 && set PY=py -3.12
if "%PY%"=="python" py -3.11 --version >nul 2>&1 && set PY=py -3.11
%PY% rec.py
echo.
echo === Chuong trinh da dung. Doc loi o tren (neu co) ===
pause
