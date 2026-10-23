@echo off
:: Advanced Wallpaper Randomizer - Fixed & Optimized
:: This batch file runs the embedded PowerShell script below.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content '%~f0' | Select-Object -Skip 5 | Out-String | Invoke-Expression"
exit /b

# --- PowerShell Code Starts Here ---
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$configFile = Join-Path $env:TEMP 'wallpaper_config.txt'
$cacheFile  = Join-Path $env:TEMP 'wallpaper_cache.txt'
$stateFile  = Join-Path $env:TEMP 'wallpaper_state.txt'

# --- Single-instance guard ---
$mutexName = 'Global\WallpaperUltraRandomizer_' + [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true, $mutexName, [ref]$createdNew)
if (-not $createdNew) {
    # Another instance running - just exit quietly (could signal existing instance)
    exit
}

# --- Resolve starting folder ---
$currentDir = $null
if (Test-Path $configFile) {
    $currentDir = (Get-Content $configFile -ErrorAction SilentlyContinue | Select-Object -First 1)
}
if (-not $currentDir -or -not (Test-Path $currentDir)) {
    $currentDir = [Environment]::GetFolderPath('MyPictures')
}
if (-not $currentDir -or -not (Test-Path $currentDir)) {
    $currentDir = $PSScriptRoot
}

# --- Persisted UI state (auto-shuffle, window bounds) ---
$savedState = @{ AutoShuffle = $false; X = -1; Y = -1; W = 500; H = 380 }
if (Test-Path $stateFile) {
    try {
        $raw = Get-Content $stateFile -Raw -ErrorAction SilentlyContinue
        if ($raw) {
            $obj = $raw | ConvertFrom-Json
            foreach ($k in @('AutoShuffle','X','Y','W','H')) {
                if ($null -ne $obj.$k) { $savedState[$k] = $obj.$k }
            }
        }
    } catch { }
}

# --- Win32 wallpaper API ---
$code = @'
[DllImport("user32.dll", CharSet = CharSet.Auto)]
public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
'@
$win32 = Add-Type -MemberDefinition $code -Name 'Win32Wallpaper' -Namespace 'Win32' -PassThru

$script:history = New-Object System.Collections.Generic.List[string]
$script:historyIndex = -1
$script:currentImg = ''
$script:images = @()
$script:currentDir = $currentDir
$script:lastPicked = $null
$script:balloonShown = $false

# --- UI ---
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Wallpaper Ultra Randomizer'
$form.Size = New-Object System.Drawing.Size($savedState.W, $savedState.H)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 25)
$form.ForeColor = [System.Drawing.Color]::White
$form.TopMost = $false
$form.ShowInTaskbar = $true
$form.KeyPreview = $true

$fontTitle = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)
$fontText  = New-Object System.Drawing.Font('Segoe UI', 9)

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = 'Wallpaper Ultra'
$lblTitle.Font = $fontTitle
$lblTitle.Location = New-Object System.Drawing.Point(20, 15)
$lblTitle.AutoSize = $true
$form.Controls.Add($lblTitle)

$lblFolder = New-Object System.Windows.Forms.Label
$lblFolder.Text = 'Folder: ' + $currentDir
$lblFolder.Font = $fontText
$lblFolder.Location = New-Object System.Drawing.Point(20, 55)
$lblFolder.Size = New-Object System.Drawing.Size(300, 40)
$form.Controls.Add($lblFolder)

# Thumbnail preview
$picPreview = New-Object System.Windows.Forms.PictureBox
$picPreview.Location = New-Object System.Drawing.Point(330, 15)
$picPreview.Size = New-Object System.Drawing.Size(140, 80)
$picPreview.SizeMode = 'Zoom'
$picPreview.BorderStyle = 'FixedSingle'
$picPreview.BackColor = [System.Drawing.Color]::FromArgb(40, 40, 40)
$form.Controls.Add($picPreview)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = 'Ready'
$lblStatus.Font = $fontText
$lblStatus.Location = New-Object System.Drawing.Point(20, 95)
$lblStatus.Size = New-Object System.Drawing.Size(450, 20)
$lblStatus.ForeColor = [System.Drawing.Color]::LightGray
$form.Controls.Add($lblStatus)

# --- Core helpers ---
$loadImages = {
    param($path, $forceRefresh)
    $script:images = @()
    if (-not $path -or -not (Test-Path $path)) {
        $lblStatus.Text = 'Folder not found: ' + $path
        $script:images = @()
        return
    }

    if (-not $forceRefresh -and (Test-Path $cacheFile)) {
        $cached = Get-Content $cacheFile -ErrorAction SilentlyContinue | Where-Object { $_ -and (Test-Path $_) }
        if ($cached) {
            $script:images = @($cached)
            $lblStatus.Text = "Loaded $($script:images.Count) images from cache."
        }
    }

    if (-not $script:images -or $script:images.Count -eq 0 -or $forceRefresh) {
        $lblStatus.Text = 'Scanning folder (this may take a moment)...'
        $form.Refresh()
        $exts = @('.jpg','.jpeg','.png','.bmp','.gif','.webp')
        $script:images = @(
            Get-ChildItem -Path $path -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $exts -contains $_.Extension.ToLower() } |
            Select-Object -ExpandProperty FullName
        )
        try { $script:images | Out-File $cacheFile -Encoding UTF8 } catch { }
        $lblStatus.Text = "Found $($script:images.Count) images and cached."
    }

    try { $path | Out-File $configFile -Encoding UTF8 } catch { }

    if ($script:images.Count -eq 0) {
        $lblStatus.Text = 'No images found in this folder. Pick another.'
        $btnRandom.Enabled = $false
        $btnBack.Enabled = $false
    } else {
        $btnRandom.Enabled = $true
        & $updateBackButton
    }
}

$updateBackButton = {
    if ($script:historyIndex -gt 0) {
        $btnBack.Enabled = $true
    } else {
        $btnBack.Enabled = $false
    }
}

$setWallpaper = {
    param($img)
    if ($img -and (Test-Path $img)) {
        $script:currentImg = $img
        [void]$win32::SystemParametersInfo(20, 0, $img, 3)
        $lblStatus.Text = 'Set: ' + [System.IO.Path]::GetFileName($img)
        try {
            $clone = [System.Drawing.Image]::FromFile($img)
            # Dispose old image to release file lock
            if ($picPreview.Image) { $picPreview.Image.Dispose() }
            $picPreview.Image = New-Object System.Drawing.Bitmap $clone
            $clone.Dispose()
        } catch {
            if ($picPreview.Image) { $picPreview.Image.Dispose() }
            $picPreview.Image = $null
        }
    }
}

$pickRandom = {
    if (-not $script:images -or $script:images.Count -eq 0) {
        $lblStatus.Text = 'No images available!'
        return
    }
    $img = $null
    if ($script:images.Count -eq 1) {
        $img = $script:images[0]
    } else {
        # Avoid immediate repeat
        for ($i = 0; $i -lt 6; $i++) {
            $candidate = Get-Random -InputObject $script:images
            if ($candidate -ne $script:lastPicked) { $img = $candidate; break }
        }
        if (-not $img) { $img = Get-Random -InputObject $script:images }
    }
    $script:lastPicked = $img
    $script:history.Add($img)
    $script:historyIndex = $script:history.Count - 1
    & $updateBackButton
    & $setWallpaper $img
}

# --- Buttons ---
$btnRandom = New-Object System.Windows.Forms.Button
$btnRandom.Text = 'Randomize'
$btnRandom.Location = New-Object System.Drawing.Point(20, 130)
$btnRandom.Size = New-Object System.Drawing.Size(100, 40)
$btnRandom.FlatStyle = 'Flat'
$btnRandom.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215)
$btnRandom.Add_Click({ & $pickRandom })
$form.Controls.Add($btnRandom)

$btnBack = New-Object System.Windows.Forms.Button
$btnBack.Text = 'Back'
$btnBack.Location = New-Object System.Drawing.Point(130, 130)
$btnBack.Size = New-Object System.Drawing.Size(80, 40)
$btnBack.FlatStyle = 'Flat'
$btnBack.Enabled = $false
$btnBack.Add_Click({
    if ($script:historyIndex -gt 0) {
        $script:historyIndex--
        & $setWallpaper $script:history[$script:historyIndex]
        & $updateBackButton
    }
})
$form.Controls.Add($btnBack)

$btnOpen = New-Object System.Windows.Forms.Button
$btnOpen.Text = 'Open Location'
$btnOpen.Location = New-Object System.Drawing.Point(220, 130)
$btnOpen.Size = New-Object System.Drawing.Size(120, 40)
$btnOpen.FlatStyle = 'Flat'
$btnOpen.Add_Click({
    if ($script:currentImg -and (Test-Path $script:currentImg)) {
        Start-Process explorer.exe -ArgumentList "/select,`"$($script:currentImg)`""
    }
})
$form.Controls.Add($btnOpen)

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Text = 'Folder'
$btnBrowse.Location = New-Object System.Drawing.Point(350, 130)
$btnBrowse.Size = New-Object System.Drawing.Size(80, 40)
$btnBrowse.FlatStyle = 'Flat'
$btnBrowse.Add_Click({
    $fb = New-Object System.Windows.Forms.FolderBrowserDialog
    $fb.SelectedPath = $script:currentDir
    if ($fb.ShowDialog() -eq 'OK') {
        $script:currentDir = $fb.SelectedPath
        $lblFolder.Text = 'Folder: ' + $script:currentDir
        & $loadImages $script:currentDir $true
    }
})
$form.Controls.Add($btnBrowse)

$btnRefresh = New-Object System.Windows.Forms.Button
$btnRefresh.Text = 'Refresh'
$btnRefresh.Location = New-Object System.Drawing.Point(20, 180)
$btnRefresh.Size = New-Object System.Drawing.Size(100, 30)
$btnRefresh.FlatStyle = 'Flat'
$btnRefresh.Add_Click({
    & $loadImages $script:currentDir $true
})
$form.Controls.Add($btnRefresh)

# --- Auto-shuffle ---
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 60000
$timer.Add_Tick({ & $pickRandom })

$chkAuto = New-Object System.Windows.Forms.CheckBox
$chkAuto.Text = 'Auto-shuffle (1 min)'
$chkAuto.Location = New-Object System.Drawing.Point(140, 184)
$chkAuto.AutoSize = $true
$chkAuto.Checked = [bool]$savedState.AutoShuffle
$chkAuto.Add_CheckedChanged({
    if ($chkAuto.Checked) { $timer.Start() } else { $timer.Stop() }
})
$form.Controls.Add($chkAuto)

# --- Keyboard shortcuts ---
$form.Add_KeyDown({
    param($sender, $e)
    switch ($e.KeyCode) {
        'R' { if ($btnRandom.Enabled) { & $pickRandom }; $e.Handled = $true }
        'B' { if ($btnBack.Enabled)   { $btnBack.PerformClick() }; $e.Handled = $true }
        'O' { $btnOpen.PerformClick(); $e.Handled = $true }
        'F' { $btnBrowse.PerformClick(); $e.Handled = $true }
        'Space' { if ($btnRandom.Enabled) { & $pickRandom }; $e.Handled = $true }
    }
})

# --- Tray icon ---
$notifyIcon = New-Object System.Windows.Forms.NotifyIcon
try {
    $exePath = (Get-Process -Id $PID).Path
    $notifyIcon.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon($exePath)
} catch {
    $notifyIcon.Icon = [System.Drawing.SystemIcons]::Application
}
$notifyIcon.Text = 'Wallpaper Ultra'
$notifyIcon.Visible = $true

$showForm = {
    $form.Show()
    if ($form.WindowState -eq 'Minimized') { $form.WindowState = 'Normal' }
    $form.Activate()
    $form.ShowInTaskbar = $true
}

$hideToTray = {
    $form.Hide()
    $form.ShowInTaskbar = $false
    if (-not $script:balloonShown) {
        $notifyIcon.ShowBalloonTip(2000, 'Wallpaper Ultra', 'Running in tray. Double-click the icon to restore.', [System.Windows.Forms.ToolTipIcon]::Info)
        $script:balloonShown = $true
    }
}

$notifyIcon.Add_DoubleClick({ & $showForm })

$contextMenu = New-Object System.Windows.Forms.ContextMenuStrip
$menuShow = $contextMenu.Items.Add('Show')
$menuShow.Add_Click({ & $showForm })
$menuNext = $contextMenu.Items.Add('Next Wallpaper')
$menuNext.Add_Click({ & $pickRandom })
[void]$contextMenu.Items.Add('-')
$menuExit = $contextMenu.Items.Add('Exit')
$menuExit.Add_Click({
    $notifyIcon.Visible = $false
    [System.Windows.Forms.Application]::Exit()
})
$notifyIcon.ContextMenuStrip = $contextMenu

# --- Form events ---
$form.Add_Resize({
    if ($form.WindowState -eq 'Minimized') { & $hideToTray }
    else { $form.ShowInTaskbar = $true }
})

$form.Add_FormClosing({
    if ($_.CloseReason -eq 'UserClosing' -or $_.CloseReason -eq 'TaskManagerClosing') {
        $_.Cancel = $true
        & $hideToTray
    } else {
        $notifyIcon.Visible = $false
    }
})

$form.Add_FormClosed({
    # Persist UI state
    try {
        $out = [pscustomobject]@{
            AutoShuffle = [bool]$chkAuto.Checked
            X = $form.Location.X
            Y = $form.Location.Y
            W = $form.Width
            H = $form.Height
        }
        $out | ConvertTo-Json -Compress | Out-File $stateFile -Encoding UTF8
    } catch { }
})

# Restore last window position if valid
if ($savedState.X -ge 0 -and $savedState.Y -ge 0) {
    $form.StartPosition = 'Manual'
    $form.Location = New-Object System.Drawing.Point($savedState.X, $savedState.Y)
}

# --- Initial load ---
& $loadImages $currentDir $false
if ($chkAuto.Checked) { $timer.Start() }

# --- Run ---
[System.Windows.Forms.Application]::Run($form)