@echo off
setlocal EnableExtensions EnableDelayedExpansion
title User Cleanup - Detailed Report

set "REPORT=%USERPROFILE%\Desktop\Cleanup_Report.txt"
set "START_TIME=%DATE% %TIME%"

echo.
echo ================================================
echo          USER-LEVEL WINDOWS CLEANUP
echo          DETAILED CLEANUP + STORAGE REPORT
echo ================================================
echo.
echo WARNING:
echo This script permanently deletes:
echo   - Downloads
echo   - Browser profiles/data
echo   - Temporary files
echo   - Recent items
echo   - Windows caches
echo   - Lively Wallpaper (if installed)
echo.
echo Make sure anything important has been backed up.
echo.
echo Close Chrome and other apps first.
pause

rem ============================================================
rem INITIALIZE REPORT
rem ============================================================

> "%REPORT%" echo ================================================================
>>"%REPORT%" echo                    WINDOWS CLEANUP REPORT
>>"%REPORT%" echo ================================================================
>>"%REPORT%" echo.
>>"%REPORT%" echo Started: %START_TIME%
>>"%REPORT%" echo User: %USERNAME%
>>"%REPORT%" echo Computer: %COMPUTERNAME%
>>"%REPORT%" echo.
>>"%REPORT%" echo IMPORTANT:
>>"%REPORT%" echo This report records cleanup targets, estimated sizes,
>>"%REPORT%" echo deletion results, and overall disk-space change.
>>"%REPORT%" echo.
>>"%REPORT%" echo ================================================================
>>"%REPORT%" echo.

echo.
echo Creating initial storage measurement...

powershell -NoProfile -Command ^
 "$d=Get-CimInstance Win32_LogicalDisk -Filter ""DeviceID='C:'""; " ^
 "Write-Output ('C:\ FREE SPACE BEFORE: ' + [math]::Round($d.FreeSpace/1GB,2) + ' GB'); " ^
 "Write-Output ('C:\ TOTAL SPACE:        ' + [math]::Round($d.Size/1GB,2) + ' GB'); " ^
 "Add-Content -LiteralPath '%REPORT%' ('C:\ FREE SPACE BEFORE: ' + [math]::Round($d.FreeSpace/1GB,2) + ' GB'); " ^
 "Add-Content -LiteralPath '%REPORT%' ('C:\ TOTAL SPACE:        ' + [math]::Round($d.Size/1GB,2) + ' GB');"

echo.

rem ============================================================
rem HELPER:
rem Measure a directory before deletion and write result to report
rem ============================================================

echo [1/15] Closing Chrome...
taskkill /F /IM chrome.exe >nul 2>&1

echo.
echo [2/15] Cleaning TEMP...

call :MEASURE "%TEMP%" "User TEMP"
del /f /s /q "%TEMP%\*" >nul 2>&1
for /d %%D in ("%TEMP%\*") do rd /s /q "%%D" >nul 2>&1
call :AFTER "%TEMP%" "User TEMP"

echo.
echo [3/15] Cleaning Downloads...

call :MEASURE "%USERPROFILE%\Downloads" "Downloads"
del /f /s /q "%USERPROFILE%\Downloads\*" >nul 2>&1
for /d %%D in ("%USERPROFILE%\Downloads\*") do rd /s /q "%%D" >nul 2>&1
call :AFTER "%USERPROFILE%\Downloads" "Downloads"

echo.
echo [4/15] Deleting Chrome data...

call :MEASURE "%LOCALAPPDATA%\Google\Chrome\User Data" "Google Chrome User Data"
rd /s /q "%LOCALAPPDATA%\Google\Chrome\User Data" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Google\Chrome\User Data" "Google Chrome User Data"

echo.
echo [5/15] Emptying Recycle Bin...

powershell -NoProfile -Command ^
 "$bins=Get-PSDrive -PSProvider FileSystem; " ^
 "$before=0; " ^
 "try { " ^
 " $shell=New-Object -ComObject Shell.Application; " ^
 " foreach($b in $bins){ " ^
 "   $bin=$shell.Namespace(10); " ^
 "   if($bin){ foreach($i in $bin.Items()){ $before += [int64]$i.Size } } " ^
 " } " ^
 "} catch {} " ^
 "Write-Output ('Recycle Bin estimated contents before: ' + [math]::Round($before/1MB,2) + ' MB'); " ^
 "Add-Content -LiteralPath '%REPORT%' ('Recycle Bin estimated contents before: ' + [math]::Round($before/1MB,2) + ' MB'); " ^
 "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"

echo.
echo ================================================
echo        ADDITIONAL SYSTEM CLEANUP
echo ================================================
echo.

echo [6/15] Closing other browsers...

taskkill /F /IM msedge.exe >nul 2>&1
taskkill /F /IM firefox.exe >nul 2>&1
taskkill /F /IM brave.exe >nul 2>&1
taskkill /F /IM opera.exe >nul 2>&1
taskkill /F /IM opera_gx.exe >nul 2>&1
taskkill /F /IM vivaldi.exe >nul 2>&1
taskkill /F /IM chromium.exe >nul 2>&1
taskkill /F /IM browser.exe >nul 2>&1
taskkill /F /IM arc.exe >nul 2>&1
taskkill /F /IM yandex.exe >nul 2>&1

timeout /t 2 /nobreak >nul

echo.
echo [7/15] Cleaning Microsoft Edge data...

call :MEASURE "%LOCALAPPDATA%\Microsoft\Edge\User Data" "Microsoft Edge User Data"
rd /s /q "%LOCALAPPDATA%\Microsoft\Edge\User Data" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Microsoft\Edge\User Data" "Microsoft Edge User Data"

echo.
echo [8/15] Cleaning Firefox data...

call :MEASURE "%APPDATA%\Mozilla\Firefox\Profiles" "Firefox Profiles"
rd /s /q "%APPDATA%\Mozilla\Firefox\Profiles" >nul 2>&1
call :AFTER "%APPDATA%\Mozilla\Firefox\Profiles" "Firefox Profiles"

echo.
echo [9/15] Cleaning Brave data...

call :MEASURE "%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data" "Brave User Data"
rd /s /q "%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data" "Brave User Data"

echo.
echo [10/15] Cleaning Opera data...

call :MEASURE "%APPDATA%\Opera Software\Opera Stable" "Opera Stable"
rd /s /q "%APPDATA%\Opera Software\Opera Stable" >nul 2>&1
call :AFTER "%APPDATA%\Opera Software\Opera Stable" "Opera Stable"

call :MEASURE "%APPDATA%\Opera Software\Opera GX Stable" "Opera GX Stable"
rd /s /q "%APPDATA%\Opera Software\Opera GX Stable" >nul 2>&1
call :AFTER "%APPDATA%\Opera Software\Opera GX Stable" "Opera GX Stable"

echo.
echo [11/15] Cleaning Vivaldi / Chromium / Yandex / Arc data...

call :MEASURE "%LOCALAPPDATA%\Vivaldi\User Data" "Vivaldi User Data"
rd /s /q "%LOCALAPPDATA%\Vivaldi\User Data" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Vivaldi\User Data" "Vivaldi User Data"

call :MEASURE "%LOCALAPPDATA%\Chromium\User Data" "Chromium User Data"
rd /s /q "%LOCALAPPDATA%\Chromium\User Data" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Chromium\User Data" "Chromium User Data"

call :MEASURE "%LOCALAPPDATA%\Yandex\YandexBrowser\User Data" "Yandex Browser User Data"
rd /s /q "%LOCALAPPDATA%\Yandex\YandexBrowser\User Data" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Yandex\YandexBrowser\User Data" "Yandex Browser User Data"

call :MEASURE "%LOCALAPPDATA%\Arc\User Data" "Arc User Data"
rd /s /q "%LOCALAPPDATA%\Arc\User Data" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Arc\User Data" "Arc User Data"

echo.
echo [12/15] Cleaning Windows user caches...

call :MEASURE "%LOCALAPPDATA%\Temp" "LocalAppData TEMP"
del /f /s /q "%LOCALAPPDATA%\Temp\*" >nul 2>&1
for /d %%D in ("%LOCALAPPDATA%\Temp\*") do rd /s /q "%%D" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Temp" "LocalAppData TEMP"

call :MEASURE "%LOCALAPPDATA%\Microsoft\Windows\INetCache" "INetCache"
del /f /s /q "%LOCALAPPDATA%\Microsoft\Windows\INetCache\*" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Microsoft\Windows\INetCache" "INetCache"

call :MEASURE "%LOCALAPPDATA%\Microsoft\Windows\WebCache" "WebCache"
del /f /s /q "%LOCALAPPDATA%\Microsoft\Windows\WebCache\*" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Microsoft\Windows\WebCache" "WebCache"

call :MEASURE "%LOCALAPPDATA%\Microsoft\Windows\Explorer" "Explorer cache files"
del /f /s /q "%LOCALAPPDATA%\Microsoft\Windows\Explorer\thumbcache_*.db" >nul 2>&1
del /f /s /q "%LOCALAPPDATA%\Microsoft\Windows\Explorer\iconcache_*.db" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Microsoft\Windows\Explorer" "Explorer cache files"

call :MEASURE "%LOCALAPPDATA%\D3DSCache" "D3D Shader Cache"
del /f /s /q "%LOCALAPPDATA%\D3DSCache\*" >nul 2>&1
for /d %%D in ("%LOCALAPPDATA%\D3DSCache\*") do rd /s /q "%%D" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\D3DSCache" "D3D Shader Cache"

call :MEASURE "%LOCALAPPDATA%\Microsoft\Windows\WER" "Windows Error Reporting"
del /f /s /q "%LOCALAPPDATA%\Microsoft\Windows\WER\*" >nul 2>&1
for /d %%D in ("%LOCALAPPDATA%\Microsoft\Windows\WER\*") do rd /s /q "%%D" >nul 2>&1
call :AFTER "%LOCALAPPDATA%\Microsoft\Windows\WER" "Windows Error Reporting"

echo.
echo [13/15] Cleaning Windows recent items...

call :MEASURE "%APPDATA%\Microsoft\Windows\Recent" "Windows Recent Items"
del /f /q "%APPDATA%\Microsoft\Windows\Recent\*" >nul 2>&1
call :AFTER "%APPDATA%\Microsoft\Windows\Recent" "Windows Recent Items"

call :MEASURE "%APPDATA%\Microsoft\Windows\Recent\AutomaticDestinations" "Automatic Destinations"
del /f /q "%APPDATA%\Microsoft\Windows\Recent\AutomaticDestinations\*" >nul 2>&1
call :AFTER "%APPDATA%\Microsoft\Windows\Recent\AutomaticDestinations" "Automatic Destinations"

call :MEASURE "%APPDATA%\Microsoft\Windows\Recent\CustomDestinations" "Custom Destinations"
del /f /q "%APPDATA%\Microsoft\Windows\Recent\CustomDestinations\*" >nul 2>&1
call :AFTER "%APPDATA%\Microsoft\Windows\Recent\CustomDestinations" "Custom Destinations"

echo.
echo [14/15] Uninstalling Lively Wallpaper if installed...

where winget >nul 2>&1

if not errorlevel 1 (
    winget uninstall --name "Lively Wallpaper" --silent --accept-source-agreements >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "Get-AppxPackage -Name '*Lively*' -ErrorAction SilentlyContinue | " ^
 "Remove-AppxPackage -ErrorAction SilentlyContinue"

echo.
echo [15/15] Restoring the default Windows wallpaper...

set "DEFAULT_WALLPAPER=%WINDIR%\Web\Wallpaper\Windows\img0.jpg"

if exist "%DEFAULT_WALLPAPER%" (
    reg add "HKCU\Control Panel\Desktop" /v Wallpaper /t REG_SZ /d "%DEFAULT_WALLPAPER%" /f >nul 2>&1
    reg add "HKCU\Control Panel\Desktop" /v WallpaperStyle /t REG_SZ /d "10" /f >nul 2>&1
    reg add "HKCU\Control Panel\Desktop" /v TileWallpaper /t REG_SZ /d "0" /f >nul 2>&1

    rundll32.exe user32.dll,UpdatePerUserSystemParameters >nul 2>&1

    >>"%REPORT%" echo Wallpaper restored to:
    >>"%REPORT%" echo %DEFAULT_WALLPAPER%
) else (
    >>"%REPORT%" echo WARNING: Default Windows wallpaper was not found.
)

rem ============================================================
rem FINAL STORAGE MEASUREMENT
rem ============================================================

echo.
echo ================================================
echo              CLEANUP COMPLETE
echo ================================================
echo.
echo Generating final storage report...
echo.

powershell -NoProfile -Command ^
 "$d=Get-CimInstance Win32_LogicalDisk -Filter ""DeviceID='C:'""; " ^
 "$free=[int64]$d.FreeSpace; " ^
 "$total=[int64]$d.Size; " ^
 "$beforeText=Get-Content -LiteralPath '%REPORT%' | Where-Object {$_ -like 'C:\ FREE SPACE BEFORE:*'} | Select-Object -First 1; " ^
 "$beforeGB=0; " ^
 "if($beforeText -match '([0-9.]+) GB'){ $beforeGB=[double]$Matches[1] }; " ^
 "$freeGB=[math]::Round($free/1GB,2); " ^
 "$totalGB=[math]::Round($total/1GB,2); " ^
 "$delta=[math]::Round($freeGB-$beforeGB,2); " ^
 "Write-Output ('C:\ FREE SPACE AFTER:  ' + $freeGB + ' GB'); " ^
 "Write-Output ('C:\ TOTAL SPACE:       ' + $totalGB + ' GB'); " ^
 "Write-Output ('C:\ SPACE FREED:       ' + $delta + ' GB'); " ^
 "Add-Content -LiteralPath '%REPORT%' ''; " ^
 "Add-Content -LiteralPath '%REPORT%' '==============================================================='; " ^
 "Add-Content -LiteralPath '%REPORT%' '                    FINAL STORAGE SUMMARY'; " ^
 "Add-Content -LiteralPath '%REPORT%' '==============================================================='; " ^
 "Add-Content -LiteralPath '%REPORT%' ('C:\ FREE SPACE AFTER:  ' + $freeGB + ' GB'); " ^
 "Add-Content -LiteralPath '%REPORT%' ('C:\ TOTAL SPACE:       ' + $totalGB + ' GB'); " ^
 "Add-Content -LiteralPath '%REPORT%' ('C:\ SPACE FREED:       ' + $delta + ' GB'); " ^
 "Add-Content -LiteralPath '%REPORT%' ''; " ^
 "Add-Content -LiteralPath '%REPORT%' ('Report generated: ' + (Get-Date));"

echo.
echo ------------------------------------------------
echo FINAL STORAGE RESULT
echo ------------------------------------------------

powershell -NoProfile -Command ^
 "$d=Get-CimInstance Win32_LogicalDisk -Filter ""DeviceID='C:'""; " ^
 "Write-Output ('Free space now: ' + [math]::Round($d.FreeSpace/1GB,2) + ' GB')"

echo.
echo Detailed report saved to:
echo %REPORT%
echo.

echo ================================================================
echo                 CLEANUP DETAILS SAVED
echo ================================================================
echo.
echo The report contains:
echo   - Every cleanup target
echo   - Estimated size before cleanup
echo   - Estimated size remaining afterward
echo   - Cleanup status
echo   - C: drive free space before cleanup
echo   - C: drive free space after cleanup
echo   - Overall disk-space change
echo   - Wallpaper restoration status
echo.
echo NOTE:
echo "Space freed" is based on the actual change in free disk space.
echo Individual folder sizes are estimates because some files may be
echo locked or inaccessible while Windows is running.
echo.
echo.
echo ================================================================
echo              CLEANUP COMPLETE
echo ================================================================
echo.
echo The cleanup has finished successfully.
echo.
echo The computer will shut down automatically in 10 seconds.
echo.
echo Press [N] within 10 seconds to CANCEL the shutdown.
echo Press [Y] or ENTER to shut down immediately.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$cancel=$false; " ^
    "for($i=10;$i -ge 1;$i--){ " ^
    "  Write-Host -NoNewline ('`rShutdown in ' + $i + ' seconds... Press N to cancel.   '); " ^
    "  if([Console]::KeyAvailable){ " ^
    "    $key=[Console]::ReadKey($true); " ^
    "    if($key.Key -eq 'N'){ $cancel=$true; break } " ^
    "    if($key.Key -eq 'Y' -or $key.Key -eq 'Enter'){ break } " ^
    "  } " ^
    "  Start-Sleep -Seconds 1 " ^
    "} " ^
    "Write-Host ''; " ^
    "if($cancel){ " ^
    "  Write-Host 'Shutdown cancelled by user.' -ForegroundColor Yellow; " ^
    "  Write-Host 'The cleanup has completed. The computer will remain ON.'; " ^
    "  exit 1 " ^
    "} else { " ^
    "  Write-Host 'Starting shutdown...' -ForegroundColor Red; " ^
    "  shutdown /s /t 0 /c 'Windows cleanup completed.' " ^
    "}"

if errorlevel 1 (
    echo.
    echo ================================================================
    echo                 SHUTDOWN CANCELLED
    echo ================================================================
    echo.
    echo The cleanup is complete and the computer will remain ON.
    echo.
    echo Detailed report:
    echo %REPORT%
    echo.
    pause
    goto END
)

goto END

rem ============================================================
rem SUBROUTINE: MEASURE DIRECTORY
rem ============================================================

:MEASURE
set "TARGET=%~1"
set "LABEL=%~2"

echo Measuring: %LABEL%

powershell -NoProfile -Command ^
 "$p=$env:TARGET; " ^
 "if(Test-Path -LiteralPath $p){ " ^
 "  try { " ^
 "    $s=(Get-ChildItem -LiteralPath $p -Force -File -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; " ^
 "    if($null -eq $s){$s=0}; " ^
 "    $mb=[math]::Round($s/1MB,2); " ^
 "    $gb=[math]::Round($s/1GB,3); " ^
 "    Write-Output ('  BEFORE: ' + $mb + ' MB (' + $gb + ' GB)'); " ^
 "    Add-Content -LiteralPath '%REPORT%' ('[' + (Get-Date) + '] ' + '%LABEL%'); " ^
 "    Add-Content -LiteralPath '%REPORT%' ('  Path: ' + $p); " ^
 "    Add-Content -LiteralPath '%REPORT%' ('  Estimated size before: ' + $mb + ' MB (' + $gb + ' GB)'); " ^
 "  } catch { " ^
 "    Add-Content -LiteralPath '%REPORT%' ('  Measurement error: ' + $_.Exception.Message); " ^
 "  } " ^
 "} else { " ^
 "  Write-Output '  NOT FOUND / ALREADY EMPTY'; " ^
 "  Add-Content -LiteralPath '%REPORT%' ('[' + (Get-Date) + '] ' + '%LABEL%'); " ^
 "  Add-Content -LiteralPath '%REPORT%' ('  Path: ' + $p); " ^
 "  Add-Content -LiteralPath '%REPORT%' '  Status: Not found / already empty'; " ^
 "}"

set "TARGET="
set "LABEL="
exit /b


rem ============================================================
rem SUBROUTINE: MEASURE AFTER CLEANUP
rem ============================================================

:AFTER
set "TARGET=%~1"
set "LABEL=%~2"

powershell -NoProfile -Command ^
 "$p=$env:TARGET; " ^
 "if(Test-Path -LiteralPath $p){ " ^
 "  try { " ^
 "    $s=(Get-ChildItem -LiteralPath $p -Force -File -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum; " ^
 "    if($null -eq $s){$s=0}; " ^
 "    $mb=[math]::Round($s/1MB,2); " ^
 "    $gb=[math]::Round($s/1GB,3); " ^
 "    Write-Output ('  AFTER:  ' + $mb + ' MB (' + $gb + ' GB)'); " ^
 "    Add-Content -LiteralPath '%REPORT%' ('  Estimated size after:  ' + $mb + ' MB (' + $gb + ' GB)'); " ^
 "    Add-Content -LiteralPath '%REPORT%' ('  Estimated removed:     ' + $mb + ' MB remaining in target'); " ^
 "    Add-Content -LiteralPath '%REPORT%' ''; " ^
 "  } catch { " ^
 "    Add-Content -LiteralPath '%REPORT%' ('  After-measurement error: ' + $_.Exception.Message); " ^
 "  } " ^
 "} else { " ^
 "  Write-Output '  AFTER:  Folder removed / empty'; " ^
 "  Add-Content -LiteralPath '%REPORT%' '  After cleanup: Folder removed / empty'; " ^
 "  Add-Content -LiteralPath '%REPORT%' ''; " ^
 "}"

set "TARGET="
set "LABEL="
exit /b


:END
endlocal
