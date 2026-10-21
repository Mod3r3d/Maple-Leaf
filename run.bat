@echo off
chcp 65001 >nul
title Maple Leaf Bot
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ===================================================
echo     🍁 MAPLE LEAF DISCORD BOT — KHỞI CHẠY
echo ===================================================
echo.

REM 1. Kiểm tra môi trường ảo .venv
if not exist ".venv\Scripts\python.exe" (
    echo [!] Chưa tìm thấy môi trường ảo .venv.
    echo [*] Đang tự động chạy cài đặt ban đầu (scripts\setup.bat)...
    echo.
    call "scripts\setup.bat"
    if errorlevel 1 (
        echo [X] Cài đặt thất bại. Vui lòng kiểm tra lại Python trên máy.
        pause
        exit /b 1
    )
)

REM 2. Kiểm tra file .env
if not exist ".env" (
    echo [*] Chưa có file .env — đang tạo từ .env.example...
    copy /y ".env.example" ".env" >nul
)

REM 3. Kiểm tra DISCORD_TOKEN
findstr /R /C:"^DISCORD_TOKEN=..*" ".env" >nul
if errorlevel 1 (
    echo ========================================================
    echo  ⚠️  CẢNH BÁO: Bạn chưa điền DISCORD_TOKEN trong file .env!
    echo ========================================================
    echo  1. Vào: https://discord.com/developers/applications
    echo  2. Tạo/Chọn Bot -> Reset Token -> Copy Token.
    echo  3. Dán Token vào dòng DISCORD_TOKEN=... trong file .env.
    echo ========================================================
    echo.
    set /p open_env="Bạn có muốn mở file .env bằng Notepad ngay bây giờ không? (y/n): "
    if /i "!open_env!"=="y" (
        notepad .env
    )
    echo Sau khi điền Token, hãy chạy lại file run.bat này nhé!
    pause
    exit /b 1
)

REM 4. Khởi chạy bot
echo [*] Đang khởi động Maple Leaf Bot...
echo     Nhấn Ctrl+C để dừng bot bất kỳ lúc nào.
echo.
".venv\Scripts\python.exe" -m app.main

if errorlevel 1 (
    echo.
    echo [X] Bot đã dừng do phát sinh lỗi.
    pause
)
