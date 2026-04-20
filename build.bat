@echo off
echo [*] Stopping the application...
taskkill /F /IM DouyinSync.exe 2>nul

echo [*] Cleaning old builds safely...
rmdir /s /q build
rmdir /s /q dist\DouyinSync
del /f /q DouyinSync.spec 2>nul

echo [*] Compiling DouyinSync via PyInstaller...
pyinstaller --noconfirm --onedir --windowed --name "DouyinSync" --hidden-import="pystray" --hidden-import="PIL" --hidden-import="googleapiclient" --hidden-import="google_auth_oauthlib" --hidden-import="google_auth_httplib2" "main.py"

echo [*] Preparing Distribution Folder...
copy config.json dist\DouyinSync\ 2>nul
copy client_secret.json dist\DouyinSync\ 2>nul
mkdir dist\DouyinSync\logs 2>nul
mkdir dist\DouyinSync\downloads 2>nul

echo [SUCCESS] Build completed!
echo [*] Next Steps:
echo   1. Navigate to 'dist\DouyinSync\'
echo   2. Run 'DouyinSync.exe'
pause
