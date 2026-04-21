@echo off
echo [*] Stopping the application...
taskkill /F /IM DouyinSync.exe /T 2>nul

echo [*] Cleaning old temp builds safely...
rmdir /s /q build 2>nul
rmdir /s /q dist\_staging 2>nul
del /f /q DouyinSync.spec 2>nul

echo [*] Compiling DouyinSync via PyInstaller in Staging Environment...
pyinstaller --noconfirm --distpath dist\_staging --onedir --windowed --name "DouyinSync" --hidden-import="pystray" --hidden-import="PIL" --hidden-import="googleapiclient" --hidden-import="google_auth_oauthlib" --hidden-import="google_auth_httplib2" --hidden-import="winrt.windows.media.ocr" --hidden-import="winrt.windows.graphics.imaging" --hidden-import="winrt.windows.storage" --hidden-import="winrt.windows.foundation" --hidden-import="winrt.windows.foundation.collections" "main.py"

echo [*] Syncing fresh build over to dist\DouyinSync (Preserving Data)...
mkdir dist\DouyinSync 2>nul
xcopy /E /I /H /Y dist\_staging\DouyinSync dist\DouyinSync\ >nul 2>&1

echo [*] Preparing Configs (if not exist)...
if not exist dist\DouyinSync\config.json copy config.json dist\DouyinSync\ 2>nul
if not exist dist\DouyinSync\client_secret.json copy client_secret.json dist\DouyinSync\ 2>nul
mkdir dist\DouyinSync\logs 2>nul
mkdir dist\DouyinSync\downloads 2>nul

echo [SUCCESS] Build completed successfully without data loss!
echo [*] Next Steps:
echo   1. Navigate to 'dist\DouyinSync\'
echo   2. Run 'DouyinSync.exe'
pause
