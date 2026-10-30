@echo off
setlocal
:: Use the folder passed as an argument (drag & drop), otherwise use the current folder
set "TARGET_DIR=%~1"
if "%TARGET_DIR%"=="" set "TARGET_DIR=."

powershell -ExecutionPolicy Bypass -Command ^
    "$dir = Resolve-Path $env:TARGET_DIR; " ^
    "$files = Get-ChildItem -Path $dir -Recurse -File | Where-Object { '.mkv','.mp4','.avi','.mov','.wmv','.flv' -contains $_.Extension.ToLower() }; " ^
    "if ($files) { " ^
    "  $randomFile = $files | Get-Random; " ^
    "  Write-Host 'Folder:   ' $dir; " ^
    "  Write-Host 'Playing:  ' $randomFile.Name; " ^
    "  Start-Process $randomFile.FullName; " ^
    "  Start-Sleep -Seconds 2; " ^
    "} else { " ^
    "  Write-Host 'No video files found in: ' $dir; " ^
    "  pause " ^
    "}"
