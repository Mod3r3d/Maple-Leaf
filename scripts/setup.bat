@echo off
REM ─────────────────────────────────────────────────────────────
REM  Maple Leaf — Script cai dat nhanh (Windows)
REM  Chay:  scripts\setup.bat
REM ─────────────────────────────────────────────────────────────
setlocal
cd /d "%~dp0.."
echo + Maple Leaf - Cai dat moi truong

REM 1) Kiem tra Python
where python >nul 2>nul
if errorlevel 1 (
    echo [X] Khong tim thay Python. Hay cai Python 3.12+ roi chay lai.
    pause
    exit /b 1
)
echo - Dung Python:
python --version

REM 2) Tao moi truong ao
if not exist ".venv" (
    echo - Dang tao moi truong ao .venv ...
    python -m venv .venv
) else (
    echo - Moi truong ao .venv da ton tai, bo qua.
)

REM 3) Cai dependency
echo - Dang cai dat thu vien ...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q

REM 4) Tao file .env neu chua co
if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    echo - Da tao .env tu .env.example
) else (
    echo - File .env da ton tai, giu nguyen.
)

REM 5) Tao thu muc runtime
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo.
echo [OK] Cai dat xong!
echo.
echo Buoc tiep theo:
echo   1. Mo file .env va dien DISCORD_TOKEN (lay tai https://discord.com/developers/applications)
echo   2. Chay bot:
echo        .venv\Scripts\python.exe -m app.main
echo.
echo Kiem thu:  .venv\Scripts\python.exe -m unittest discover tests
echo.
pause
