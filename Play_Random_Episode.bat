<# : chooser
@echo off
set "INPUT_DIR=%~1"
powershell -sta -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression ([System.IO.File]::ReadAllText('%~f0'))"
exit /b %ERRORLEVEL%
#>

$targetDir = $env:INPUT_DIR

if ([string]::IsNullOrWhitespace($targetDir) -or -not (Test-Path -LiteralPath $targetDir)) {
    $code = @'
using System;
using System.Runtime.InteropServices;

namespace NativeFolderPicker {
    public class FolderPicker {
        [ComImport, Guid("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7"), ClassInterface(ClassInterfaceType.None)]
        private class FileOpenDialog { }

        [ComImport, Guid("42F85136-DB7E-439C-85F1-E4075D135FC8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IFileDialog {
            [PreserveSig] int Show(IntPtr parent);
            [PreserveSig] int SetFileTypes(uint cNames, IntPtr rgFilter);
            [PreserveSig] int SetFileTypeIndex(uint iFileType);
            [PreserveSig] int GetFileTypeIndex(out uint piFileType);
            [PreserveSig] int Advise(IntPtr pfde, out uint pdwCookie);
            [PreserveSig] int Unadvise(uint dwCookie);
            [PreserveSig] int SetOptions(uint fos);
            [PreserveSig] int GetOptions(out uint pfos);
            [PreserveSig] int SetDefaultFolder(IntPtr psi);
            [PreserveSig] int SetFolder(IntPtr psi);
            [PreserveSig] int GetFolder(out IntPtr ppsi);
            [PreserveSig] int GetCurrentSelection(out IntPtr ppsi);
            [PreserveSig] int SetFileName([MarshalAs(UnmanagedType.LPWStr)] string pszName);
            [PreserveSig] int GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string pszName);
            [PreserveSig] int SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle);
            [PreserveSig] int SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string pszText);
            [PreserveSig] int SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string pszLabel);
            [PreserveSig] int GetResult(out IShellItem ppsi);
            [PreserveSig] int AddPlace(IntPtr psi, int alignment);
            [PreserveSig] int SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)] string pszDefaultExtension);
            [PreserveSig] int Close(int hr);
            [PreserveSig] int SetClientGuid(ref Guid guid);
            [PreserveSig] int ClearClientData();
            [PreserveSig] int SetFilter(IntPtr pFilter);
        }

        [ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IShellItem {
            [PreserveSig] int BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
            [PreserveSig] int GetParent(out IShellItem ppsi);
            [PreserveSig] int GetDisplayName(uint sigdnName, [MarshalAs(UnmanagedType.LPWStr)] out string ppszName);
            [PreserveSig] int GetAttributes(uint sfgaoMask, out uint psfgaoAttribs);
            [PreserveSig] int Compare(IShellItem psi, uint hint, out int piOrder);
        }

        public static string ShowDialog(string title) {
            var dialog = (IFileDialog)new FileOpenDialog();
            uint options;
            dialog.GetOptions(out options);
            dialog.SetOptions(options | 0x20 | 0x40); // FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM
            if (!string.IsNullOrEmpty(title)) dialog.SetTitle(title);
            if (dialog.Show(IntPtr.Zero) == 0) {
                IShellItem item;
                dialog.GetResult(out item);
                if (item != null) {
                    string path;
                    item.GetDisplayName(0x80058000, out path); // SIGDN_FILESYSPATH
                    return path;
                }
            }
            return null;
        }
    }
}
'@
    Add-Type -TypeDefinition $code
    $targetDir = [NativeFolderPicker.FolderPicker]::ShowDialog('Select a folder containing video files')
    if ([string]::IsNullOrWhitespace($targetDir)) {
        Write-Host "No folder selected. Exiting..."
        Start-Sleep -Seconds 2
        exit
    }
}

$exts = @('.mp4','.mkv','.avi','.mov','.wmv','.flv','.m4v','.webm','.mpg','.mpeg','.ts','.3gp','.vob','.ogv')
$files = Get-ChildItem -LiteralPath $targetDir -Recurse -File | Where-Object { $exts -contains $_.Extension.ToLower() }
if (-not $files) {
    Write-Host "No video files found in: $targetDir"
    Start-Sleep -Seconds 3
    exit
}

$shuffled = $files | Sort-Object { Get-Random }
Write-Host "=================================================="
Write-Host "Selected Folder : $targetDir"
Write-Host "Total Videos    : $($shuffled.Count)"
Write-Host "=================================================="
Write-Host "Randomized Playlist Order:"
$i = 1
foreach ($f in $shuffled) {
    Write-Host (' {0,3}. {1}' -f $i, $f.Name)
    $i++
}
Write-Host "=================================================="

$playlistPath = Join-Path $env:TEMP 'Random_Video_Playlist.m3u8'
$lines = @('#EXTM3U') + ($shuffled | ForEach-Object { $_.FullName })
Set-Content -Path $playlistPath -Value $lines -Encoding UTF8
Write-Host "Launching randomized playlist in default player..."
Start-Process -FilePath $playlistPath
Start-Sleep -Seconds 3
