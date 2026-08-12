@echo off
REM ============================================================
REM  Jinclaw Tauri dev backend launcher (start_backend.bat)
REM  Works on cmd.exe, no PowerShell execution policy required.
REM  %~dp0 = absolute directory of this bat (= project root)
REM ============================================================

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8000"
set "MAX_WAIT=20"
set "LOG_DIR=logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "dt=%%I"
set "TS=%dt:~0,8%_%dt:~8,6%"
set "LOG=%~dp0%LOG_DIR%\backend_%TS%.log"

:check_port
powershell -NoProfile -Command "$c=New-Object Net.Sockets.TcpClient; try { $c.Connect('%HOST%',%PORT%); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>nul
exit /b %ERRORLEVEL%

call :check_port
if %ERRORLEVEL%==0 (
    echo TAURI_SRV_READY backend already up on %HOST%:%PORT%
    exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
    echo [ERR] python.exe not found in PATH. Install Python 3.10+ and add it to PATH.
    exit /b 1
)

echo Starting backend... log=%LOG%

REM start /MIN /I: start minimized, ignore current env, separate process.
start "jinclaw_backend_%TS%" /MIN /I cmd /c "cd /d ""%~dp0"" & python main.py >> ""%LOG%"" 2>>&1"

set "ELAPSED=0"
:wait_loop
if %ELAPSED% geq %MAX_WAIT% goto :timeout
call :check_port
if %ERRORLEVEL%==0 (
    ping -n 1 -w 500 127.0.0.1 >nul
    echo TAURI_SRV_READY backend up on %HOST%:%PORT% log=%LOG%
    exit /b 0
)
ping -n 1 -w 400 127.0.0.1 >nul
set /a ELAPSED=ELAPSED+1
goto :wait_loop

:timeout
echo [ERR] timed out waiting %HOST%:%PORT% after %MAX_WAIT%s. See log: %LOG%
exit /b 1
