@echo off
setlocal

:: Advanced Wallpaper Randomizer - Fixed Version
:: Features: Tray support, History, Caching, Open Location, Modern UI
powershell -ExecutionPolicy Bypass -Command ^
    "Add-Type -AssemblyName System.Windows.Forms;" ^
    "Add-Type -AssemblyName System.Drawing;" ^
    "[System.Windows.Forms.Application]::EnableVisualStyles();" ^
    "" ^
    "$configFile = Join-Path $env:TEMP 'wallpaper_config.txt';" ^
    "$cacheFile = Join-Path $env:TEMP 'wallpaper_cache.txt';" ^
    "$currentDir = if (Test-Path $configFile) { Get-Content $configFile } else { [Environment]::GetFolderPath('MyPictures') };" ^
    "" ^
    "$code = '[DllImport(\"user32.dll\", CharSet = CharSet.Auto)] public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);';" ^
    "$win32 = Add-Type -MemberDefinition $code -Name 'Win32Wallpaper' -Namespace 'Win32' -PassThru;" ^
    "" ^
    "$history = New-Object System.Collections.Generic.List[string];" ^
    "$historyIndex = -1;" ^
    "$script:currentImg = '';" ^
    "" ^
    "$form = New-Object System.Windows.Forms.Form;" ^
    "$form.Text = 'Wallpaper Ultra Randomizer';" ^
    "$form.Size = New-Object System.Drawing.Size(500, 350);" ^
    "$form.StartPosition = 'CenterScreen';" ^
    "$form.FormBorderStyle = 'FixedDialog';" ^
    "$form.MaximizeBox = $false;" ^
    "$form.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 25);" ^
    "$form.ForeColor = [System.Drawing.Color]::White;" ^
    "$form.TopMost = $true;" ^
    "" ^
    "$fontTitle = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold);" ^
    "$fontText = New-Object System.Drawing.Font('Segoe UI', 9);" ^
    "" ^
    "$lblTitle = New-Object System.Windows.Forms.Label;" ^
    "$lblTitle.Text = 'Wallpaper Ultra';" ^
    "$lblTitle.Font = $fontTitle;" ^
    "$lblTitle.Location = New-Object System.Drawing.Point(20, 20);" ^
    "$lblTitle.AutoSize = $true;" ^
    "$form.Controls.Add($lblTitle);" ^
    "" ^
    "$lblFolder = New-Object System.Windows.Forms.Label;" ^
    "$lblFolder.Text = 'Folder: ' + $currentDir;" ^
    "$lblFolder.Font = $fontText;" ^
    "$lblFolder.Location = New-Object System.Drawing.Point(20, 60);" ^
    "$lblFolder.Size = New-Object System.Drawing.Size(440, 40);" ^
    "$form.Controls.Add($lblFolder);" ^
    "" ^
    "$lblStatus = New-Object System.Windows.Forms.Label;" ^
    "$lblStatus.Text = 'Ready';" ^
    "$lblStatus.Font = $fontText;" ^
    "$lblStatus.Location = New-Object System.Drawing.Point(20, 100);" ^
    "$lblStatus.Size = New-Object System.Drawing.Size(440, 40);" ^
    "$lblStatus.ForeColor = [System.Drawing.Color]::LightGray;" ^
    "$form.Controls.Add($lblStatus);" ^
    "" ^
    "$images = @();" ^
    "$loadImages = {" ^
    "  param($path, $forceRefresh);" ^
    "  if (-not $forceRefresh -and (Test-Path $cacheFile)) {" ^
    "    $script:images = Get-Content $cacheFile;" ^
    "    $lblStatus.Text = 'Loaded ' + $script:images.Count + ' images from cache.';" ^
    "  } else {" ^
    "    $lblStatus.Text = 'Scanning folder (this may take a moment)...';" ^
    "    $form.Refresh();" ^
    "    $script:images = Get-ChildItem -Path $path -Include *.jpg,*.jpeg,*.png,*.bmp -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName;" ^
    "    $script:images | Out-File $cacheFile;" ^
    "    $lblStatus.Text = 'Found ' + $script:images.Count + ' images and cached.';" ^
    "  }" ^
    "  $path | Out-File $configFile;" ^
    "};" ^
    "" ^
    "& $loadImages $currentDir $false;" ^
    "" ^
    "$setWallpaper = {" ^
    "  param($img);" ^
    "  if ($img -and (Test-Path $img)) {" ^
    "    $script:currentImg = $img;" ^
    "    $win32::SystemParametersInfo(20, 0, $img, 3);" ^
    "    $lblStatus.Text = 'Set: ' + [System.IO.Path]::GetFileName($img);" ^
    "  }" ^
    "};" ^
    "" ^
    "$btnRandom = New-Object System.Windows.Forms.Button;" ^
    "$btnRandom.Text = 'Randomize';" ^
    "$btnRandom.Location = New-Object System.Drawing.Point(20, 150);" ^
    "$btnRandom.Size = New-Object System.Drawing.Size(100, 40);" ^
    "$btnRandom.FlatStyle = 'Flat';" ^
    "$btnRandom.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215);" ^
    "$btnRandom.Add_Click({" ^
    "  if ($script:images.Count -gt 0) {" ^
    "    $img = Get-Random -InputObject $script:images;" ^
    "    $script:history.Add($img);" ^
    "    $script:historyIndex = $script:history.Count - 1;" ^
    "    & $setWallpaper $img;" ^
    "  }" ^
    "});" ^
    "$form.Controls.Add($btnRandom);" ^
    "" ^
    "$btnBack = New-Object System.Windows.Forms.Button;" ^
    "$btnBack.Text = 'Back';" ^
    "$btnBack.Location = New-Object System.Drawing.Point(130, 150);" ^
    "$btnBack.Size = New-Object System.Drawing.Size(80, 40);" ^
    "$btnBack.FlatStyle = 'Flat';" ^
    "$btnBack.Add_Click({" ^
    "  if ($script:historyIndex -gt 0) {" ^
    "    $script:historyIndex--;" ^
    "    & $setWallpaper $script:history[$script:historyIndex];" ^
    "  }" ^
    "});" ^
    "$form.Controls.Add($btnBack);" ^
    "" ^
    "$btnOpen = New-Object System.Windows.Forms.Button;" ^
    "$btnOpen.Text = 'Open Location';" ^
    "$btnOpen.Location = New-Object System.Drawing.Point(220, 150);" ^
    "$btnOpen.Size = New-Object System.Drawing.Size(120, 40);" ^
    "$btnOpen.FlatStyle = 'Flat';" ^
    "$btnOpen.Add_Click({" ^
    "  if ($script:currentImg) {" ^
    "    Start-Process explorer.exe -ArgumentList \"/select,`\"$($script:currentImg)`\"\"" ^
    "  }" ^
    "});" ^
    "$form.Controls.Add($btnOpen);" ^
    "" ^
    "$btnBrowse = New-Object System.Windows.Forms.Button;" ^
    "$btnBrowse.Text = 'Folder';" ^
    "$btnBrowse.Location = New-Object System.Drawing.Point(350, 150);" ^
    "$btnBrowse.Size = New-Object System.Drawing.Size(80, 40);" ^
    "$btnBrowse.FlatStyle = 'Flat';" ^
    "$btnBrowse.Add_Click({" ^
    "  $fb = New-Object System.Windows.Forms.FolderBrowserDialog;" ^
    "  $fb.SelectedPath = $currentDir;" ^
    "  if ($fb.ShowDialog() -eq 'OK') {" ^
    "    $script:currentDir = $fb.SelectedPath;" ^
    "    $lblFolder.Text = 'Folder: ' + $script:currentDir;" ^
    "    & $loadImages $script:currentDir $true;" ^
    "  }" ^
    "});" ^
    "$form.Controls.Add($btnBrowse);" ^
    "" ^
    "$timer = New-Object System.Windows.Forms.Timer;" ^
    "$timer.Interval = 60000;" ^
    "$timer.Add_Tick({ $btnRandom.PerformClick() });" ^
    "" ^
    "$chkAuto = New-Object System.Windows.Forms.CheckBox;" ^
    "$chkAuto.Text = 'Auto-shuffle (1 min)';" ^
    "$chkAuto.Location = New-Object System.Drawing.Point(20, 210);" ^
    "$chkAuto.AutoSize = $true;" ^
    "$chkAuto.Add_CheckedChanged({" ^
    "  if ($chkAuto.Checked) { $timer.Start() } else { $timer.Stop() }" ^
    "});" ^
    "$form.Controls.Add($chkAuto);" ^
    "" ^
    "$notifyIcon = New-Object System.Windows.Forms.NotifyIcon;" ^
    "try { $notifyIcon.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon((Get-Process -Id $pid).Path) } catch { $notifyIcon.Icon = [System.Drawing.SystemIcons]::Application }" ^
    "$notifyIcon.Text = 'Wallpaper Ultra';" ^
    "$notifyIcon.Visible = $true;" ^
    "$notifyIcon.Add_DoubleClick({ $form.Show(); $form.WindowState = 'Normal'; $form.Activate() });" ^
    "" ^
    "$contextMenu = New-Object System.Windows.Forms.ContextMenuStrip;" ^
    "$menuShow = $contextMenu.Items.Add('Show');" ^
    "$menuShow.Add_Click({ $form.Show(); $form.WindowState = 'Normal'; $form.Activate() });" ^
    "$menuNext = $contextMenu.Items.Add('Next Wallpaper');" ^
    "$menuNext.Add_Click({ $btnRandom.PerformClick() });" ^
    "$menuExit = $contextMenu.Items.Add('Exit');" ^
    "$menuExit.Add_Click({ $notifyIcon.Visible = $false; $form.Close(); [System.Windows.Forms.Application]::Exit() });" ^
    "$notifyIcon.ContextMenuStrip = $contextMenu;" ^
    "" ^
    "$form.Add_Resize({" ^
    "  if ($form.WindowState -eq 'Minimized') {" ^
    "    $form.Hide();" ^
    "    $notifyIcon.ShowBalloonTip(2000, 'Wallpaper Ultra', 'Minimized to tray. Double-click icon to restore.', [System.Windows.Forms.ToolTipIcon]::Info);" ^
    "  }" ^
    "});" ^
    "" ^
    "$form.Add_FormClosing({ $notifyIcon.Visible = $false });" ^
    "" ^
    "$form.ShowDialog();"
