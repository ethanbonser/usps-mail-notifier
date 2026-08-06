@echo off
set SCRIPT_DIR=%~dp0
echo Starting USPS Mail Notifier Listener in background...
wscript.exe "%SCRIPT_DIR%..\scriptsun_background.vbs"
echo.
echo The listener is now running in the background.
echo You can use your Telegram bot to interact with it.
pause
