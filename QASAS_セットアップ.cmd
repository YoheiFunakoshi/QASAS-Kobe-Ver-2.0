@echo off
setlocal
cd /d "%~dp0"

where py.exe >nul 2>&1
if %errorlevel%==0 (
    py.exe -3 -m pip install -r "%~dp0requirements.txt"
    goto :result
)

where python.exe >nul 2>&1
if %errorlevel%==0 (
    python.exe -m pip install -r "%~dp0requirements.txt"
    goto :result
)

echo Python 3 が見つかりません。
pause
exit /b 1

:result
if %errorlevel% neq 0 (
    echo セットアップに失敗しました。
) else (
    echo セットアップが完了しました。
)
pause
