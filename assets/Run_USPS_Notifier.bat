@echo off
set SCRIPT_DIR=%~dp0
echo Checking for USPS mail...
python "%SCRIPT_DIR%..\scripts\check_mail.py"
pause
