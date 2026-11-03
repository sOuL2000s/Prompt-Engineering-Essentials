@echo off
setlocal enableextensions enabledelayedexpansion
title Play Random Video Playlist

set "INPUT_DIR=%~1"

powershell -sta -NoProfile -ExecutionPolicy Bypass -Command ^
    "$targetDir = $env:INPUT_DIR;" ^
    "if ([string]::IsNullOrWhitespace($targetDir) -or -not (Test-Path -LiteralPath $targetDir)) {" ^
    "    Add-Type -AssemblyName System.Windows.Forms;" ^
    "    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog;" ^
    "    $dialog.Description = 'Select a folder containing video files';" ^
    "    $dialog.ShowNewFolderButton = $false;" ^
    "    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {" ^
    "        $targetDir = $dialog.SelectedPath;" ^
    "    } else {" ^
    "        Write-Host 'No folder selected. Exiting...';" ^
    "        Start-Sleep -Seconds 2;" ^
    "        exit;" ^
    "    }" ^
    "}" ^
    "$exts = @('.mp4','.mkv','.avi','.mov','.wmv','.flv','.m4v','.webm','.mpg','.mpeg','.ts','.3gp','.vob','.ogv');" ^
    "$files = Get-ChildItem -LiteralPath $targetDir -Recurse -File | Where-Object { $exts -contains $_.Extension.ToLower() };" ^
    "if (-not $files) {" ^
    "    Write-Host \"No video files found in: $targetDir\";" ^
    "    Start-Sleep -Seconds 3;" ^
    "    exit;" ^
    "}" ^
    "$shuffled = $files | Sort-Object { Get-Random };" ^
    "Write-Host '==================================================';" ^
    "Write-Host \"Selected Folder : $targetDir\";" ^
    "Write-Host \"Total Videos    : $($shuffled.Count)\";" ^
    "Write-Host '==================================================';" ^
    "Write-Host 'Randomized Playlist Order:';" ^
    "$i = 1;" ^
    "foreach ($f in $shuffled) {" ^
    "    Write-Host (' {0,3}. {1}' -f $i, $f.Name);" ^
    "    $i++;" ^
    "}" ^
    "Write-Host '==================================================';" ^
    "$playlistPath = Join-Path $env:TEMP 'Random_Video_Playlist.m3u8';" ^
    "$lines = @('#EXTM3U') + ($shuffled | ForEach-Object { $_.FullName });" ^
    "Set-Content -Path $playlistPath -Value $lines -Encoding UTF8;" ^
    "Write-Host 'Launching randomized playlist in default player...';" ^
    "Start-Process -FilePath $playlistPath;" ^
    "Start-Sleep -Seconds 3"
