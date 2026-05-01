# DouyinSync PyInstaller onedir build (mirrors repo-root build.bat).
# Usage:
#   pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_douyinsync.ps1
#   pwsh -File .\scripts\build_douyinsync.ps1 -NoPause    # CI / automation
param(
    [switch]$NoPause
)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repoRoot

Write-Host '[*] Stopping processes that may lock build outputs...'
Write-Host '    - DouyinSync.exe'
Get-Process -Name 'DouyinSync' -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host '    - python.exe / pythonw.exe (this repo main.py)'
try {
    & powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File (Join-Path $repoRoot 'scripts\build_kill_dev_python.ps1') 2>$null
} catch {
    Write-Host '[WARN] Kill-helper failed or unavailable, continuing...'
}

Start-Sleep -Seconds 1

Write-Host '[*] Cleaning staging dirs...'
Remove-Item -LiteralPath (Join-Path $repoRoot 'build') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $repoRoot 'dist\_staging') -Recurse -Force -ErrorAction SilentlyContinue

Write-Host '[*] PyInstaller (DouyinSync.spec)...'
$pyiArgs = @(
    '--noconfirm'
    '--distpath', (Join-Path $repoRoot 'dist\_staging')
    '--workpath', (Join-Path $repoRoot 'build')
    (Join-Path $repoRoot 'DouyinSync.spec')
)
& pyinstaller @pyiArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyInstaller failed. Code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host '[*] Sync to dist\DouyinSync (merge, keep sidecar files)...'
$dest = Join-Path $repoRoot 'dist\DouyinSync'
$src = Join-Path $repoRoot 'dist\_staging\DouyinSync'
if (-not (Test-Path -LiteralPath $src)) {
    Write-Host '[ERROR] Staging folder missing:' $src
    exit 1
}
New-Item -ItemType Directory -Path $dest -Force | Out-Null
cmd /c "xcopy /E /I /H /Y `"$src\*`" `"$dest\`" >nul"
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] xcopy sync failed. Code' $LASTEXITCODE
    exit 1
}

Write-Host '[*] Preparing run folder...'
$cfg = Join-Path $repoRoot 'config.json'
$cfgExample = Join-Path $repoRoot 'config.example.json'
$destCfg = Join-Path $dest 'config.json'
$cs = Join-Path $repoRoot 'client_secret.json'
if (-not (Test-Path -LiteralPath $destCfg)) {
    if (Test-Path -LiteralPath $cfg) {
        Copy-Item -LiteralPath $cfg -Destination $dest -Force
    } elseif (Test-Path -LiteralPath $cfgExample) {
        Copy-Item -LiteralPath $cfgExample -Destination $destCfg -Force
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $dest 'client_secret.json')) -and (Test-Path -LiteralPath $cs)) {
    Copy-Item -LiteralPath $cs -Destination $dest -Force
}
foreach ($sub in @('logs', 'downloads')) {
    $p = Join-Path $dest $sub
    if (-not (Test-Path -LiteralPath $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
    }
}

Write-Host '[SUCCESS] Build done.'
Write-Host '    Run:' (Join-Path $dest 'DouyinSync.exe')

if (-not $NoPause) {
    pause
}

exit 0
