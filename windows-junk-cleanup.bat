@echo off
title User Cleanup
echo.
echo ========================================
echo        USER-LEVEL WINDOWS CLEANUP
echo ========================================
echo.
echo Close Chrome and other apps first.
pause

echo.
echo [1/5] Closing Chrome...
taskkill /F /IM chrome.exe >nul 2>&1

echo [2/5] Cleaning TEMP...
del /f /s /q "%TEMP%\*" >nul 2>&1
for /d %%D in ("%TEMP%\*") do rd /s /q "%%D" >nul 2>&1

echo [3/5] Cleaning Downloads...
del /f /s /q "%USERPROFILE%\Downloads\*" >nul 2>&1
for /d %%D in ("%USERPROFILE%\Downloads\*") do rd /s /q "%%D" >nul 2>&1

echo [4/5] Deleting Chrome data...
rd /s /q "%LOCALAPPDATA%\Google\Chrome\User Data" >nul 2>&1

echo [5/5] Emptying Recycle Bin...
powershell -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"

echo.
echo ========================================
echo              CLEANUP COMPLETE
echo ========================================
echo.
pause