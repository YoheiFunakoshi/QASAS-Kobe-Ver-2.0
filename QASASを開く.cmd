@echo off
setlocal
cd /d "%~dp0"

where pyw.exe >nul 2>&1
if %errorlevel%==0 (
    start "" pyw.exe -3 "%~dp0QASAS_app.pyw"
    exit /b 0
)

where pythonw.exe >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw.exe "%~dp0QASAS_app.pyw"
    exit /b 0
)

echo Python 3 が見つかりません。
echo Python 3 をインストール後、もう一度実行してください。
pause
exit /b 1
