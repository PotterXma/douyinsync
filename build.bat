@echo off
REM build.bat          - interactive (pause at end)
REM build.bat nopause  - CI / automation (no pause)
REM set SKIP_BUILD_PAUSE=1 - same as nopause
setlocal EnableExtensions
cd /d "%~dp0"

REM UTF-8 console when supported (reduces mojibake in Cursor/VS integrated terminal)
chcp 65001 >nul 2>&1

echo [*] Stopping processes that may lock build outputs...
echo     - DouyinSync.exe
taskkill /F /IM DouyinSync.exe /T >nul 2>&1

echo     - python.exe / pythonw.exe (this repo main.py)
REM 2>nul: hide PowerShell stderr (often garbled under OEM code pages)
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0scripts\build_kill_dev_python.ps1" 2>nul
if errorlevel 1 echo [WARN] Kill-helper script returned non-zero, continuing...

REM timeout breaks when stdin is redirected (e.g. IDE); ping is a portable 1s delay
ping 127.0.0.1 -n 2 >nul

echo [*] Cleaning staging dirs...
if exist "build" rmdir /s /q "build"
if exist "dist\_staging" rmdir /s /q "dist\_staging"

echo [*] PyInstaller (DouyinSync.spec)...
pyinstaller --noconfirm --distpath "dist\_staging" --workpath "build" "DouyinSync.spec"
if errorlevel 1 goto :fail_pyi

echo [*] Sync to dist\DouyinSync (merge, keep sidecar files)...
if not exist "dist\DouyinSync" mkdir "dist\DouyinSync"
xcopy /E /I /H /Y "dist\_staging\DouyinSync\*" "dist\DouyinSync\" >nul
if errorlevel 1 goto :fail_xcopy

echo [*] Preparing run folder...
if not exist "dist\DouyinSync\config.json" (
  if exist "config.json" copy /Y "config.json" "dist\DouyinSync\" >nul 2>&1
)
if not exist "dist\DouyinSync\config.json" if exist "config.example.json" copy /Y "config.example.json" "dist\DouyinSync\config.json" >nul 2>&1
if not exist "dist\DouyinSync\client_secret.json" copy /Y "client_secret.json" "dist\DouyinSync\" >nul 2>&1
if not exist "dist\DouyinSync\logs" mkdir "dist\DouyinSync\logs"
if not exist "dist\DouyinSync\downloads" mkdir "dist\DouyinSync\downloads"

echo [SUCCESS] Build done.
echo     Run: dist\DouyinSync\DouyinSync.exe
goto :maybe_pause

:fail_pyi
echo [ERROR] PyInstaller failed. Code %ERRORLEVEL%
endlocal
exit /b 1

:fail_xcopy
echo [ERROR] xcopy sync failed. Code %ERRORLEVEL%
endlocal
exit /b 1

:maybe_pause
if /I "%~1"=="nopause" goto :finish
if defined SKIP_BUILD_PAUSE goto :finish
pause
:finish
endlocal
goto :eof
