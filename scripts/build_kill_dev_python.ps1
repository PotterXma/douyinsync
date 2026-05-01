# Stops python.exe / pythonw.exe that were started with this repo's main.py (dev runs locking PyInstaller outputs).
$ErrorActionPreference = 'SilentlyContinue'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^(python|pythonw)\.exe$' -and
        $_.CommandLine -and
        ($_.CommandLine -like ('*' + $repoRoot + '*main.py*'))
    } |
    ForEach-Object {
        Write-Host ('    PID ' + $_.ProcessId + ' ' + $_.Name)
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

exit 0
