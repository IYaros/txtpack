@echo off
chcp 65001 >nul
python "%~dp0txtpack.py" pack "%~1"
if errorlevel 9009 echo Python not found in PATH. Install Python 3 (python.org) and retry.
set "rc=%errorlevel%"
pause
exit /b %rc%
