@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Uu tien Python 3.12/3.11 (Python 3.14 chua co nhieu thu vien); neu khong co thi dung python mac dinh
set PY=python
py -3.12 --version >nul 2>&1 && set PY=py -3.12
if "%PY%"=="python" py -3.11 --version >nul 2>&1 && set PY=py -3.11
if "%PY%"=="python" py -3.13 --version >nul 2>&1 && set PY=py -3.13
echo Dang dung: %PY%
%PY% --version
%PY% -m pip install --upgrade pip
%PY% -m pip install numpy sounddevice keyboard anthropic pygame PyQt6 faster-whisper edge-tts gTTS groq pillow qrcode
rem gTTS: pip tu lui ve ban cu 2.2.4 do xung dot phien ban "click"; ep len ban moi (khong dung toi click khi chay)
%PY% -m pip install --no-deps --upgrade gTTS==2.5.4
echo.
echo === Xong. Neu co chu ERROR o tren, hay chup lai gui cho toi ===
pause
