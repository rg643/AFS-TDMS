@echo off
cd /d "%~dp0"
title TDMS Web Server
set PY=python
where py >nul 2>nul
if not errorlevel 1 set PY=py
%PY% --version >nul 2>nul
if errorlevel 1 goto nopython
%PY% -c "import flask, PIL" >nul 2>nul
if errorlevel 1 echo Installing the needed packages - one time only - please wait...
if errorlevel 1 %PY% -m pip install flask pillow waitress
%PY% -c "import waitress" >nul 2>nul
if errorlevel 1 %PY% -m pip install waitress
echo.
%PY% tdms_web.py
echo.
echo ------------------------------------------------------------
echo The server stopped. Please read the messages above.
echo If there is an error, send me a photo of this window.
echo ------------------------------------------------------------
pause
exit /b 0

:nopython
echo.
echo Python was not found on this computer.
echo Install Python 3 from python.org and tick  Add python.exe to PATH  during the installation.
echo.
pause
exit /b 1
