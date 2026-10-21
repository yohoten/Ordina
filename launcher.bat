@echo off
chcp 65001 >nul
title Ordina / 归序 v3.0

cd /d "%~dp0"

echo ============================================
echo   Ordina / 归序  -  按用途分类的文件整理工具
echo ============================================
echo.
echo 正在启动图形界面，请稍候...
echo.

where python >nul 2>nul
if %errorlevel%==0 (
    python -m ordina gui
) else (
    py -3 -m ordina gui
)

if %errorlevel% neq 0 (
    echo.
    echo [错误] 启动失败，错误码: %errorlevel%
    echo 请确认已安装 Python 3.9+ 且包含 tkinter 组件。
    echo 也可以改用命令行模式:  python -m ordina cli --help
    echo.
    pause
)
