@echo off
chcp 65001 >nul
echo Fetching latest Garmin data...
cd /d "C:\Users\LiorKeren\garmin-coach"
python fetch_data.py

echo.
echo Detecting local IP...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "169.254" ^| findstr /v "127.0"') do (
    set LOCAL_IP=%%a
    goto :found
)
:found
set LOCAL_IP=%LOCAL_IP: =%

echo Starting local server on port 8080...
start "Garmin Server" cmd /k python -m http.server 8080

echo.
echo ===================================
echo Open on phone (same WiFi):
echo http://%LOCAL_IP%:8080/dashboard.html
echo ===================================
echo.
start http://%LOCAL_IP%:8080/dashboard.html
echo Done!
pause
