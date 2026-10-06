@echo off
chcp 65001 >nul
cd /d "%~dp0"
python rec.py
echo.
echo === Chuong trinh da dung. Doc loi o tren (neu co) ===
pause
