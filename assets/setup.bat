@echo off
set SCRIPT_DIR=%~dp0
echo Installing required libraries...
pip install requests
if %errorlevel% neq 0 (
    echo.
    echo Pip failed. Is Python in your PATH?
    pause
    exit /b
)
echo Done!
pause
