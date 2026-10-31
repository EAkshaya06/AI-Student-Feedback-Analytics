@echo off
setlocal
cd /d "%~dp0backend"
echo Starting AI Student Feedback Analytics...
echo When the server is ready, open http://127.0.0.1:5000 in your browser.
echo Keep this window open while you use the project.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 app.py
) else (
    python app.py
)
echo.
echo The project has stopped. Press any key to close this window.
pause >nul
