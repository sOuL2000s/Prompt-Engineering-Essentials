@echo off
setlocal

:: Improved Wallpaper Randomizer with GUI
:: Features: Folder persistence, Modern UI, Auto-shuffle, Image path display

powershell -ExecutionPolicy Bypass -Command ^
    "Add-Type -AssemblyName System.Windows.Forms;" ^
    "Add-Type -AssemblyName System.Drawing;" ^
    "[System.Windows.Forms.Application]::EnableVisualStyles();" ^
    "" ^
    "$configFile = Join-Path $env:TEMP 'wallpaper_config.txt';" ^
    "$currentDir = if (Test-Path $configFile) { Get-Content $configFile } else { [Environment]::GetFolderPath('MyPictures') };" ^
    "" ^
    "$code = '[DllImport(\"user32.dll\", CharSet = CharSet.Auto)] public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);';" ^
    "$win32 = Add-Type -MemberDefinition $code -Name 'Win32Wallpaper' -Namespace 'Win32' -PassThru;" ^
    "" ^
    "$form = New-Object System.Windows.Forms.Form;" ^
    "$form.Text = 'Wallpaper Pro Randomizer';" ^
    "$form.Size = New-Object System.Drawing.Size(450, 300);" ^
    "$form.StartPosition = 'CenterScreen';" ^
    "$form.FormBorderStyle = 'FixedDialog';" ^
    "$form.MaximizeBox = $false;" ^
    "$form.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 30);" ^
    "$form.ForeColor = [System.Drawing.Color]::White;" ^
    "$form.TopMost = $true;" ^
    "" ^
    "$fontTitle = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold);" ^
    "$fontText = New-Object System.Drawing.Font('Segoe UI', 9);" ^
    "" ^
    "$lblTitle = New-Object System.Windows.Forms.Label;" ^
    "$lblTitle.Text = 'Wallpaper Randomizer';" ^
    "$lblTitle.Font = $fontTitle;" ^
    "$lblTitle.Location = New-Object System.Drawing.Point(20, 20);" ^
    "$lblTitle.AutoSize = $true;" ^
    "$form.Controls.Add($lblTitle);" ^
    "" ^
    "$lblFolder = New-Object System.Windows.Forms.Label;" ^
    "$lblFolder.Text = 'Current Folder: ' + $currentDir;" ^
    "$lblFolder.Font = $fontText;" ^
    "$lblFolder.Location = New-Object System.Drawing.Point(20, 60);" ^
    "$lblFolder.Size = New-Object System.Drawing.Size(400, 40);" ^
    "$form.Controls.Add($lblFolder);" ^
    "" ^
    "$lblStatus = New-Object System.Windows.Forms.Label;" ^
    "$lblStatus.Text = 'Ready';" ^
    "$lblStatus.Font = $fontText;" ^
    "$lblStatus.Location = New-Object System.Drawing.Point(20, 100);" ^
    "$lblStatus.Size = New-Object System.Drawing.Size(400, 40);" ^
    "$lblStatus.ForeColor = [System.Drawing.Color]::LightGray;" ^
    "$form.Controls.Add($lblStatus);" ^
    "" ^
    "$images = @();" ^
    "$loadImages = {" ^
    "  param($path);" ^
    "  $script:images = Get-ChildItem -Path $path -Include *.jpg,*.jpeg,*.png,*.bmp -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName;" ^
    "  $lblStatus.Text = 'Found ' + $script:images.Count + ' images.';" ^
    "  $path | Out-File $configFile;" ^
    "};" ^
    "" ^
    "& $loadImages $currentDir;" ^
    "" ^
    "$btnRandom = New-Object System.Windows.Forms.Button;" ^
    "$btnRandom.Text = 'Randomize Now';" ^
    "$btnRandom.Location = New-Object System.Drawing.Point(20, 150);" ^
    "$btnRandom.Size = New-Object System.Drawing.Size(150, 40);" ^
    "$btnRandom.FlatStyle = 'Flat';" ^
    "$btnRandom.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215);" ^
    "$btnRandom.Add_Click({" ^
    "  if ($script:images.Count -gt 0) {" ^
    "    $img = Get-Random -InputObject $script:images;" ^
    "    $win32::SystemParametersInfo(20, 0, $img, 3);" ^
    "    $lblStatus.Text = 'Set: ' + [System.IO.Path]::GetFileName($img);" ^
    "  } else {" ^
    "    [System.Windows.Forms.MessageBox]::Show('No images found in the selected folder.');" ^
    "  }" ^
    "});" ^
    "$form.Controls.Add($btnRandom);" ^
    "" ^
    "$btnBrowse = New-Object System.Windows.Forms.Button;" ^
    "$btnBrowse.Text = 'Change Folder';" ^
    "$btnBrowse.Location = New-Object System.Drawing.Point(180, 150);" ^
    "$btnBrowse.Size = New-Object System.Drawing.Size(120, 40);" ^
    "$btnBrowse.FlatStyle = 'Flat';" ^
    "$btnBrowse.Add_Click({" ^
    "  $fb = New-Object System.Windows.Forms.FolderBrowserDialog;" ^
    "  $fb.SelectedPath = $currentDir;" ^
    "  if ($fb.ShowDialog() -eq 'OK') {" ^
    "    $script:currentDir = $fb.SelectedPath;" ^
    "    $lblFolder.Text = 'Current Folder: ' + $script:currentDir;" ^
    "    & $loadImages $script:currentDir;" ^
    "  }" ^
    "});" ^
    "$form.Controls.Add($btnBrowse);" ^
    "" ^
    "$timer = New-Object System.Windows.Forms.Timer;" ^
    "$timer.Interval = 60000;" ^
    "$timer.Add_Tick({" ^
    "  $btnRandom.PerformClick();" ^
    "});" ^
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
    "$form.ShowDialog();"
