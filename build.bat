@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [*] 结束可能占用输出文件的进程...

echo     - DouyinSync.exe ^(已安装/打包运行实例^)
taskkill /F /IM DouyinSync.exe /T >nul 2>&1

echo     - 本目录下以 main.py 启动的 python.exe / pythonw.exe ^(开发调试^)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Resolve-Path -LiteralPath '.').Path; ^
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ^
  Where-Object { ^
    $_.Name -match '^(python|pythonw)\\.exe$' -and ^
    $_.CommandLine -and ^
    ($_.CommandLine -like ('*' + $root + '*main.py*')) ^
  } | ForEach-Object { ^
    Write-Host ('    PID ' + $_.ProcessId + ' ' + $_.Name); ^
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue ^
  }"

REM 给文件锁一点时间释放（可选）
timeout /t 1 /nobreak >nul

echo [*] 清理中间产物...
if exist build rmdir /s /q build
if exist dist\_staging rmdir /s /q dist\_staging

echo [*] PyInstaller ^(DouyinSync.spec^)...
pyinstaller --noconfirm --distpath dist\_staging --workpath build DouyinSync.spec
if errorlevel 1 (
  echo [ERROR] PyInstaller 失败，退出码 %ERRORLEVEL%
  exit /b 1
)

echo [*] 同步到 dist\DouyinSync ^(保留旁路数据文件^)...
if not exist dist\DouyinSync mkdir dist\DouyinSync
xcopy /E /I /H /Y dist\_staging\DouyinSync\* dist\DouyinSync\ >nul

echo [*] 准备运行目录...
if not exist dist\DouyinSync\config.json copy /Y config.json dist\DouyinSync\ >nul 2>&1
if not exist dist\DouyinSync\client_secret.json copy /Y client_secret.json dist\DouyinSync\ >nul 2>&1
if not exist dist\DouyinSync\logs mkdir dist\DouyinSync\logs
if not exist dist\DouyinSync\downloads mkdir dist\DouyinSync\downloads

echo [SUCCESS] 构建完成。
echo     运行: dist\DouyinSync\DouyinSync.exe
pause
endlocal
