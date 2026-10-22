@echo off
setlocal

:: Use PowerShell to create a simple GUI
powershell -ExecutionPolicy Bypass -Command ^
    "Add-Type -AssemblyName System.Windows.Forms;" ^
    "Add-Type -AssemblyName System.Drawing;" ^
    "$fb = New-Object System.Windows.Forms.FolderBrowserDialog;" ^
    "$fb.Description = 'Select your Wallpaper Folder';" ^
    "if ($fb.ShowDialog() -ne 'OK') { exit };" ^
    "$dir = $fb.SelectedPath;" ^
    "Write-Host 'Loading images from ' $dir '...';" ^
    "$images = Get-ChildItem -Path $dir -Include *.jpg,*.jpeg,*.png,*.bmp -Recurse | Select-Object -ExpandProperty FullName;" ^
    "if ($images.Count -eq 0) { [System.Windows.Forms.MessageBox]::Show('No images found in ' + $dir); exit };" ^
    "$code = '[DllImport(\"user32.dll\", CharSet = CharSet.Auto)] public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);';" ^
    "$win32 = Add-Type -MemberDefinition $code -Name 'Win32Wallpaper' -Namespace 'Win32' -PassThru;" ^
    "$form = New-Object System.Windows.Forms.Form;" ^
    "$form.Text = 'Wallpaper Randomizer';" ^
    "$form.Size = New-Object System.Drawing.Size(300, 150);" ^
    "$form.StartPosition = 'CenterScreen';" ^
    "$form.FormBorderStyle = 'FixedDialog';" ^
    "$form.TopMost = $true;" ^
    "$btn = New-Object System.Windows.Forms.Button;" ^
    "$btn.Text = 'Randomize';" ^
    "$btn.Font = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold);" ^
    "$btn.Dock = 'Fill';" ^
    "$btn.Add_Click({" ^
    "  $img = Get-Random -InputObject $images;" ^
    "  $win32::SystemParametersInfo(20, 0, $img, 3);" ^
    "});" ^
    "$form.Controls.Add($btn);" ^
    "$form.ShowDialog();"
