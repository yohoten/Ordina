@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo.
echo   Ordina / 归序 ^— 打包脚本（仅 GUI）
echo   ---------------------------------------------
echo.
echo   默认：单目录模式 + UPX 压缩。
echo   可选参数（可组合）：
echo     -Mode onefile   打成单个 exe
echo     -NoUpx          关闭 UPX 压缩
echo     -UpxDir "D:\upx"  手动指定 UPX 目录
echo     -Clean          先清空 build/ 与 dist/
echo     -Zip            额外产出便携 ZIP
echo.
echo   例：build.bat -Mode onefile -Zip
echo   例：build.bat -Clean -Zip
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*

echo.
if errorlevel 1 (
    echo   打包失败，请看上方错误信息。
) else (
    echo   打包流程已结束。
)
echo.
pause
