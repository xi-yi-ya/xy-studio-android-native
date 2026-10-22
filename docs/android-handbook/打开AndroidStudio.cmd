@echo off
setlocal
pushd "%~dp0..\.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\open-android-studio.ps1" 
set "TASK_EXIT=%ERRORLEVEL%"
popd
echo.
echo Exit code: %TASK_EXIT%
pause
exit /b %TASK_EXIT%
