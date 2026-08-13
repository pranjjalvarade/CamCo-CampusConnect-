@echo off
title CamCo - Campus Connect
echo.
echo  ================================================
echo    CamCo - Campus Connect
echo    Starting Flask development server...
echo  ================================================
echo.

cd /d "d:\Lifewater\CamCo(Minor Project)"
call venv\Scripts\activate

echo  Server running at: http://127.0.0.1:5000
echo  Press Ctrl+C to stop the server.
echo.

start "" http://127.0.0.1:5000
python app.py

pause
