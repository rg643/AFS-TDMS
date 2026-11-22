@echo off
rem Gives TDMS Web a secure https link that works from ANY network.
rem Needs cloudflared.exe - free - in this folder or in PATH.
cd /d "%~dp0"
set CF=cloudflared
if exist "%~dp0cloudflared.exe" set CF="%~dp0cloudflared.exe"
%CF% --version >nul 2>nul
if errorlevel 1 goto nocf
echo.
echo Keep Run_Server.bat running in its own window.
echo Below you will see a link like  https://something-random.trycloudflare.com
echo Share that link with your team. The link changes every time you start this.
echo.
%CF% tunnel --url http://localhost:8080
pause
exit /b 0

:nocf
echo.
echo cloudflared was not found.
echo Download  cloudflared-windows-amd64.exe  from Cloudflare, rename it to  cloudflared.exe
echo and put it in this folder. Then run this file again.
echo.
pause
exit /b 1
