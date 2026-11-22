$here = $PSScriptRoot
$exe = Join-Path $here "TDMS.exe"
$ws = New-Object -ComObject WScript.Shell
if (Test-Path $exe) {
    $target = $exe; $args = ""
} else {
    $py = & python -c "import sys; print(sys.executable)" 2>$null
    if (-not $py) { Write-Host "Python was not found. Install Python and tick 'Add Python to PATH'."; Read-Host "Press Enter to close"; exit 1 }
    $target = Join-Path (Split-Path $py) "pythonw.exe"
    if (-not (Test-Path $target)) { $target = $py }
    $args = '"' + $here + '\tdms_app.py"'
}
foreach ($dir in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))) {
    $lnk = $ws.CreateShortcut("$dir\TDMS.lnk")
    $lnk.TargetPath = $target
    $lnk.Arguments = $args
    $lnk.WorkingDirectory = $here
    $lnk.IconLocation = "$here\app_icon.ico"
    $lnk.Description = "TDMS - Document Management System"
    $lnk.Save()
}
Write-Host "Done. The TDMS icon is now on your Desktop and in the Start menu."
Read-Host "Press Enter to close"
