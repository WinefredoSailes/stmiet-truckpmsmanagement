@echo off
setlocal
title Truck PMS Servicing System
cd /d "%~dp0"

echo ==================================================
echo   Truck PMS ^& Servicing System  -  Launcher
echo ==================================================
echo.

set "ROOT=%~dp0"
set "TRUCK_DIR=%ROOT%truck_pms"
set "VENV_DIR=%TRUCK_DIR%\venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "MANAGE=%TRUCK_DIR%\manage.py"
set "DB_FILE=%TRUCK_DIR%\db.sqlite3"

if exist "%MANAGE%" goto check_python
echo [ERROR] Could not find the app files.
echo Expected to find: "%MANAGE%"
echo.
echo Keep this launcher inside the main project folder and try again.
echo.
pause
exit /b 1

rem ==================================================
rem  1. Find Python
rem ==================================================
:check_python
set "PYEXE="
where py >nul 2>&1
if errorlevel 1 goto try_python
for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)"') do set "PYEXE=%%P"
goto py_done

:try_python
where python >nul 2>&1
if errorlevel 1 goto try_paths
for /f "delims=" %%P in ('python -c "import sys;print(sys.executable)"') do set "PYEXE=%%P"
goto py_done

:try_paths
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" if not defined PYEXE set "PYEXE=%%D\python.exe"
if defined PYEXE goto py_done
for /d %%D in ("C:\Python3*") do if exist "%%D\python.exe" if not defined PYEXE set "PYEXE=%%D\python.exe"
goto py_done

:py_done
if defined PYEXE "%PYEXE%" -c "import sys" >nul 2>&1
if errorlevel 1 goto no_python
echo [Step 1/5] Python found.
echo.

rem ==================================================
rem  2. Set up the app environment (venv + packages)
rem ==================================================
if exist "%VENV_PY%" goto check_venv
goto create_venv

:check_venv
"%VENV_PY%" -c "import django, pip" >nul 2>&1
if errorlevel 1 goto rebuild_venv
echo [Step 2/5] App environment ready.
goto db_check

:rebuild_venv
echo [WARN] App environment looks broken - rebuilding it.
rmdir /s /q "%VENV_DIR%" >nul 2>&1

:create_venv
echo [Step 2/5] Setting up the app environment. One time only...
echo.
"%PYEXE%" -m venv "%VENV_DIR%"
if errorlevel 1 goto setup_fail
echo.
echo   Installing packages... this can take a few minutes.
echo   Do NOT close this window while it is installing.
echo.
"%VENV_PY%" -m pip install --upgrade pip >nul 2>&1
"%VENV_PY%" -m pip install -r "%TRUCK_DIR%\requirements.txt"
if errorlevel 1 goto install_fail
echo.
echo   Packages installed.

rem ==================================================
rem  3. Check database
rem ==================================================
:db_check
set "NEED_SEED=0"
echo [Step 3/5] Checking database...
if exist "%DB_FILE%" goto db_found

echo   No data found.
echo.
echo   If you copied your data from another computer, place this file:
echo     "%DB_FILE%"
echo   and then run this launcher again.
echo.
echo   Or, you can start fresh here with the built-in default accounts.
set /p "SEED_CHOICE=   Start a fresh database with default accounts [Y/N]: "
if /I "%SEED_CHOICE%"=="Y" goto seed_yes

echo.
echo OK - no database was created. Add the data file and run me again.
goto finish

:seed_yes
set "NEED_SEED=1"
goto migrate_step

:db_found
echo   Existing data found - keeping it safe.

rem ==================================================
rem  4. Update database structure + first-run data
rem ==================================================
:migrate_step
echo [Step 4/5] Updating the database structure...
"%VENV_PY%" "%MANAGE%" migrate
if errorlevel 1 goto setup_fail
echo   Done.

if "%NEED_SEED%"=="0" goto port_check
echo   Loading default accounts and sample data...
echo     admin  /  admin123
echo     and other sample accounts.
set "SEED_DEV_PASSWORD=password123"
set "SEED_ADMIN_PASSWORD=admin123"
"%VENV_PY%" "%MANAGE%" seed_data
if errorlevel 1 goto setup_fail
echo   Generating the SOP manual PDFs. One time only.
"%VENV_PY%" "%MANAGE%" build_sop >nul 2>&1
echo   Done.

rem ==================================================
rem  5. Start the server
rem ==================================================
:port_check
netstat -ano | findstr /c:":8000 " | findstr /i "listening" >nul 2>&1
if errorlevel 1 goto start_server
echo [Step 5/5] The system looks like it is already running.
echo   Opening it in your browser...
start "" "http://127.0.0.1:8000"
goto finish

:start_server
set "DJANGO_DEBUG=True"
set "DJANGO_SECRET_KEY=local-dev-secret-key"
set "DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost"
echo [Step 5/5] Starting the system...
echo.
echo   On this computer   : http://127.0.0.1:8000
echo   Other computers    : http://  THIS-PC-IP  :8000
echo   To find THIS-PC-IP, run the command ipconfig
echo.
echo   Keep this window open while using the system.
echo   Close this window to stop the server.
echo   If Windows Firewall asks, choose Allow, then Private networks.
echo.
start "" /b powershell -NoProfile -Command "Start-Sleep -Seconds 6; Start-Process 'http://127.0.0.1:8000'"
"%VENV_PY%" "%MANAGE%" runserver 0.0.0.0:8000
echo.
echo Server stopped. You can close this window now.
goto done

rem ==================================================
rem  Error handling
rem ==================================================
:no_python
echo [ERROR] Python was not found on this computer.
echo.
echo Truck PMS needs Python 3.11 or newer to run.
echo.
echo   1. A browser will now open the Python download page.
echo   2. Download Python 3.12 or 3.13 for Windows.
echo   3. When installing, TICK the box  "Add python.exe to PATH".
echo   4. Click Install Now and wait for it to finish.
echo   5. Run this launcher file again.
echo.
start "" "https://www.python.org/downloads/"
goto finish

:install_fail
echo [ERROR] Could not install the required packages.
echo   Check the Internet connection, then run this file again.
goto finish

:setup_fail
echo [ERROR] Something went wrong during setup.
echo   The message above gives more detail.
goto finish

:done
pause
exit /b 0

:finish
echo.
pause
exit /b 1